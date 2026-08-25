# PRD — Runtime Resilience V1（装机前置校验 + 流错误自动续跑）

状态: 待实施
作者: Claude（事实经独立取证）
日期: 2026-08-24
相关构建: `14154eb7297df8084135…`
前序: PRD_UPSTREAM_PROFILE_V1 / PRD_LOOP_CONTINUITY_V1+V2

---

## 0. 范围

两个互相独立的工作包：

- **WP-A**：bootstrap 缺少 python3 版本前置校验，导致装机在最后一道门
  以**错误的归因**失败（2026-08-24 在 124.81.97.217 实测复现）。
- **WP-B**：出现 `API Error: stream protocol error` 时，等待 100s 后自动
  发送 `continue` 续跑，最多重试 **2 次**，仍失败则放弃。

两者都不新增产品功能，WP-A 是装机健壮性，WP-B 是把一个**已经存在的人工
动作**（人手敲 `continue`）自动化。

---

## WP-A — bootstrap 缺少 python3 版本前置校验

### A1 问题（实测复现）

124.81.97.217（CentOS 8，默认 `python3` 为 **3.6.8**）上执行 bootstrap：

```
bootstrap: verify: adapter /status ok (port 3100)
bootstrap: verify: auth enforcement ok (anonymous request rejected with 401)
bootstrap: verify: launcher on PATH ok
bootstrap: verify: upstream canary (live MaaS request)
bootstrap: verify: FAIL — upstream canary failed (exit 1)
bootstrap:   the adapter is running but MaaS rejected the request.
bootstrap:   check: key validity, URL correctness, and MaaS service status.
```

**报错归因是错的。** MaaS 从未拒绝任何请求。真实原因：

```
$ python3 tests/live_maas_probe.py ...
  File "tests/live_maas_probe.py", line 24
    from __future__ import annotations
    ^
SyntaxError

$ python3.9 tests/live_maas_probe.py ...
  text: HTTP 200 — PASS
  overall: PASS
```

`tests/live_maas_probe.py` 使用 `from __future__ import annotations`(3.7+)
与 `dataclasses`(3.7+)。canary 因**语法错误**退出 1，而 bootstrap 把
「exit 1」一律解释成「上游拒绝」。

后果：装机者会去排查 key、URL、MaaS 服务状态——三个方向全是错的。
本次我用 `python3.9` 手工复跑才定位到真因。

### A2 修复

1. **前置校验**：bootstrap 在任何写盘动作**之前**检查
   `python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)'`，
   不满足则直接失败并给出可执行的修复指引
   （CentOS 8：`dnf install python39`，并说明它不替换系统默认 `python3`）。
2. **允许指定解释器**：新增 `--python <path>`（或读 `MAAS_PYTHON` 环境变量），
   canary 与所有内联 python 调用统一走该解释器，缺省 `python3`。
3. **区分失败原因**：canary 的非零退出必须区分
   *无法执行*（解释器/语法/缺依赖）与 *上游拒绝*（HTTP 非 2xx），
   两者的提示文案不同。禁止把前者报成后者。
4. 最低版本写入 `docs/OPERATIONS.md` 的前置条件一节。

> 注：**运行时不受影响**。`client/claude-maas`、`claude-maas-setup.sh`、
> bootstrap 的内联 python 均无 3.7+ 语法（我已逐一 grep 确认），
> 3.6 环境下 `claude-maas` 实测可正常工作。只有 canary 需要 3.7+。

---

## WP-B — `stream protocol error` 自动续跑

### B1 需求

出现 `API Error: stream protocol error` 时：**等待 100s → 发送 `continue`
续跑 → 最多重试 2 次 → 仍失败则放弃。**

### B2 背景（为什么这件事值得自动化）

历史实测（n=25，见 PRD_LOOP_CONTINUITY_V1 §2.3）：

| 后继 | 次数 | 占比 |
| --- | --- | --- |
| 客户端自动恢复 | 8 | 32% |
| **人类手工输入 `continue`** | 12 | **48%** |
| 会话直接结束 | 5 | 20% |

**48% 的情况下，人做的事就是敲一个 `continue`。** 本 WP 把这个动作自动化，
覆盖的正是当前需要人工介入的那一半。

### B3 检测信号：不得用字符串匹配 stdout

`API Error: stream protocol error` 这串文本可能出现在模型正文里
（例如模型在讨论这个错误），grep stdout 会误判。

**权威信号**是会话 JSONL 里的结构化标记 —— 我已实测确认该标记存在：

```json
{"type":"assistant", "isApiErrorMessage": true,
 "message": {"stop_reason": "stop_sequence",
             "content": [{"type":"text","text":"API Error: stream protocol error"}]}}
```

判定规则：会话的**最后一条** assistant 记录同时满足
`isApiErrorMessage === true` **且** 正文以 `API Error: stream protocol error` 开头。
两个条件缺一不可。

### B4 续跑必须锁定同一会话

`-c/--continue` 的语义是「最近一次会话」，并发跑多个任务时会**串台**。
必须用显式会话 id：

- 首次调用传 `--session-id <uuid>`（自己生成）；
- 重试时用 `--resume <同一个 uuid> -p "continue"`。

禁止使用 `--continue`。

### B5 重试策略

```
attempt 0 : 正常执行
  ↓ 检测到 stream protocol error
sleep 100s → attempt 1 : --resume <uuid> -p "continue"
  ↓ 仍失败
sleep 100s → attempt 2 : --resume <uuid> -p "continue"
  ↓ 仍失败
放弃：非零退出 + 结构化记录，不再重试
```

- 重试上限 **2 次**（总计最多 3 次执行），可由 `MAAS_AUTO_CONTINUE_MAX` 覆盖；
- 间隔 **100s**，可由 `MAAS_AUTO_CONTINUE_DELAY` 覆盖；
- 默认**开启**，`MAAS_AUTO_CONTINUE=0` 关闭。

> 100s 与实测吻合：智谱侧限流约 **80s** 恢复（PRD_UPSTREAM_PROFILE_V1 §D6），
> 100s 留有余量。

### B6 只重试这一个错误

**必须重试**：`stream protocol error`（含 `tool_args_malformed`、
`tool_markup_as_args` 两个 protocol_error_reason）。

**禁止重试**：`401 authentication_error`、`400`、`503 OVER_CAPACITY`、
`MAAS_CLIENT_ABORTED`（用户主动中断）。这些要么重试无用，要么会放大问题。
`429` 单列讨论：属可退避错误，但当前适配器**把上游 429 回成了 502**
（PRD_UPSTREAM_PROFILE_V1 §D5），在 D5 修好之前无法可靠识别，本 WP 不覆盖。

### B7 副作用风险（必须写入文档）

`continue` 会让模型继续未完成的回合，**已执行过的工具调用可能被重复执行**。

对本 WP 覆盖的具体失败原因而言，风险是**低**的：L1-B 的 protocol error
发生在工具参数畸形、X1 保证**该工具从未被执行**的路径上（
PRD_LOOP_CONTINUITY_V1 §L1-B）。也就是说触发重试的那一刻，
该回合没有产生工具副作用。

但残余风险仍存在：同一回合中**排在畸形调用之前**的工具已经执行完毕，
`continue` 后模型可能重做。因此：

- 文档必须写明该风险；
- 对写盘/发布类高副作用任务，建议显式 `MAAS_AUTO_CONTINUE=0`。

### B8 实现位置

| 层 | 处理 |
| --- | --- |
| `scripts/delegate`（Python，已以子进程方式调 `claude-maas -p`） | 接入 supervisor |
| `scripts/workflow` | 接入同一 supervisor |
| 新增 `client/claude-maas-run`（headless 包装器） | 供临时 `-p` 任务使用 |
| **交互式 TUI** | **不在范围内** —— 无法可靠注入按键，明确声明不支持 |

supervisor 实现为单一可复用模块，三处共用，不重复实现。

### B9 可观测性

每次重试写一条结构化审计记录（沿用 `~/.claude-hybrid` 审计目录）：

```json
{"type":"auto_continue","session_id":"<uuid>","attempt":1,
 "trigger":"stream_protocol_error","delay_s":100,"outcome":"succeeded|failed|abandoned"}
```

并暴露累计计数 `auto_continue_{attempted,succeeded,abandoned}`。
**没有这组计数就无法判断该机制是在救场还是在空转。**

---

## 3. 验收门禁

沿用项目规矩：**每条必须附「回退修复后该门禁 FAIL」的证据**。

| 门 | 断言 | 反向用例 |
| --- | --- | --- |
| A-G1 | `python3` < 3.7 时 bootstrap **在写盘前**失败，且提示为版本问题而非上游问题 | 去掉前置校验后必须 FAIL（当前即为红，已在 217 实测） |
| A-G2 | `--python /usr/bin/python3.9` 时 canary 正常执行 | 忽略该参数后必须 FAIL |
| A-G3 | canary 因解释器/语法失败 → 文案为「无法执行」；HTTP 非 2xx → 文案为「上游拒绝」，两者不同 | 合并成同一文案后必须 FAIL |
| B-G1 | 注入一次 protocol error → supervisor 等待 `MAAS_AUTO_CONTINUE_DELAY` 后以 `--resume <同一 uuid> -p continue` 重试 | 改成 `--continue` 后必须 FAIL（断言命令行含该 uuid） |
| B-G2 | 连续 3 次失败 → 恰好尝试 2 次重试后放弃，非零退出 | 上限改为无限后必须 FAIL |
| B-G3 | 正文中**出现**该错误串但 `isApiErrorMessage` 为 false → **不触发**重试 | 改回 grep stdout 后必须 FAIL |
| B-G4 | 401 / 400 / OVER_CAPACITY / client_aborted → 不触发重试 | 放开错误白名单后必须 FAIL |
| B-G5 | 第 1 次重试即成功 → 审计记录 `attempt:1, outcome:succeeded`，计数器 +1 | 去掉审计写入后必须 FAIL |

B-G1/B-G2 用假的 `claude` 桩程序驱动，不消耗真实上游配额，也不依赖
真实故障复现（项目既有规则：**不为了凑样本人为构造生产失败**）。

---

## 4. 建议顺序

1. **WP-A**（装机阻塞，改动小，A-G1 当前即为红）
2. **B3 + B4**（检测信号与会话锁定 —— 做错这两点，后面全是隐患）
3. **B5 + B6**（重试策略与错误白名单）
4. **B9**（可观测性，与 B5 同批）
5. **B7 + B8 文档**（副作用风险与不支持交互式的声明）

WP-A 与 WP-B 之间无依赖，可并行。
