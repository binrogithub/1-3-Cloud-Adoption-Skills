# PRD — Release V13（v1.2 收口 + 残余可见错误）

状态: 已实施（S1/S3-a/S3-b/S3-c/S4 落地并部署；S5 窗口已重开；S2 tag 待窗口届满）
作者: Claude（全部事实经独立取证，非采信自述）
日期: 2026-08-25
被复核构建: `d45fbc568533fd50dd8b…`（`b39f7e9`）
前序: PRD_RELEASE_V12 / PRD_UPSTREAM_PROFILE_V1 / PRD_RUNTIME_RESILIENCE_V1 / PRD_TOOL_ARGS_ROOTCAUSE_V1

---

## 0. 结论

**代码质量已达发布标准。** 不能打 v1.2 标只因两件事：
一条门禁**建立在错误前提上、会永远红**（S1），以及**浸泡窗口未届满**（S5）。

另有一项用户实际感知的问题需单独处理：`enforce` 把可见错误压掉了 92%，
但**没有压到零**，而交互式会话对残余部分**没有任何自动恢复手段**（S3）。

---

## 1. 我独立验证通过的部分

以下均为我自己执行，不是转述：

| 项 | 我的验证 | 结果 |
| --- | --- | --- |
| 离线全量 | 自跑 `make verify-offline`（494s） | **780 passed / 0 failed** |
| 生产发布门 | 自跑 `scripts/verify.sh`（key 经管道注入，不进 argv） | **all gates PASS** |
| N1-G 监听合规 | `window-check-v12.sh` | **PASS** — 已按 D10 改写为 option B，逐个校验 build ✓ auth ✓ hardened ✓ |
| N2-G capture 克隆 | 同上 | **PASS** |
| 部署一致性 | `/opt` 与 repo 的 server.js SHA | **一致** `d45fbc56…` |
| 工作树 | `git status` | 干净 |
| **D5 上游状态透传** | **反向门禁**：把流式路径的 `sendJson` / `_fail` 顺序调回旧序后重跑 | **2 条测试 FAILED** — 有鉴别力 |

`b39f7e9` 落地了 `UPSTREAM_PROFILE_V1` 与 `RUNTIME_RESILIENCE_V1` 的绝大部分：
profile 参数化、python 前置校验、`auto_continue.py`、`claude-maas-run`、
`UPSTREAMS.md`、探针去字面量化、429 透传、window-check 改写（25 文件 / +2639 行）。

### 1.1 enforce 的生产实证

```
tool_args_retry      {'attempted': 12, 'succeeded': 11}     ← 91.7%
tool_args_degraded   1
MAAS_STREAM_PROTOCOL 1
客户端可见 API error  1（本次服务启动以来全量扫描）
```

对照开启 enforce 之前的同一台主机：同类畸形出现 6 次，
`retry.attempted = 0`，**6 次全部变成可见硬失败**。

---

## 2. 阻塞项

### S1 (P0) — N4-G 建立在错误前提上，会永远红

`scripts/window-check-v12.sh` 头部注释原文：

> N4-G — /status stop_reasons sum == journald request_end count since service
> boot (**both sides reset together, so the equality is exact**)

**这个前提是错的。** `adapter/server.js:1290`：

```js
const finalStopReason = ctrl.protocolError ? null : (ctrl.finishReason || null);
if (finalStopReason) { stopReasonCounts[finalStopReason] = ... }
```

**失败的请求按设计不计入 `stop_reasons`，但计入 `request_end`。**
两者只有在「零失败」时才相等——这在生产上既不现实也不应作为发布判据。

我的实测（服务启动 02:47:19 起）：

```
request_end 总数        125
带 stop_reason 的       124
stop_reason 为 null      1  →  state=upstream_failed  error_code=MAAS_STREAM_PROTOCOL
```

差值恰好等于失败请求数。**这是门禁缺陷，不是产品缺陷。**

**修复**：断言改为

```
sum(stop_reasons) + count(request_end 中 stop_reason 为 null) == count(request_end)
```

并同步改写头部注释，删除「both sides reset together」这个错误论断。

> 危害不止于「误报一次」：一条恒红的门禁会训练所有人忽略它，
> 从而**掩盖真实回归**。这是本项目门禁反模式清单的又一形态：
> **判据基于一个从未验证过的假设**。

### S2 (P0) — 线上跑的代码仍然没有 tag

```
git tag        v1.0  v1.1
v1.1        →  5a5dc28
线上        →  b39f7e9 (d45fbc56…)
```

中间隔着 **6 个 commit**，包含 loop-continuity 的 P0 修复、全部安全加固、
以及本轮的 profile / resilience 工作。「已发布的东西」与「正在跑的东西」
仍不是同一份代码，**回滚与追溯没有锚点**。

处置：S1 / S5 完成后打 `v1.2`。tag 说明须写明它同时包含
LOOP_CONTINUITY_V1+V2、SECURITY_HARDENING_V1、UPSTREAM_PROFILE_V1、
RUNTIME_RESILIENCE_V1、RELEASE_V12 五批工作。

### S3 (P1) — 残余可见错误：交互式会话没有任何自动恢复

用户实际反馈的问题。当前链路：

```
畸形参数 → L1-A 重试 1 次 → 成功 91.7%
                          ↓ 失败 8.3%
                     L1-B 降级 + protocol error → 客户端历史自愈率 ~32%
                                                ↓ 其余需人工 continue
```

两个可改进点，都有具体证据支撑：

**S3-a：重试只做一次，且次数写死。**
`adapter/server.js:1220` 只调用 `retryToolCallArgs` 一次，没有循环；
`MAAS_TOOL_ARG_RETRY` 仅是开关，无次数配置。
既然第 1 次的成功率是 **11/12**，若各次近似独立，
加一次重试可把残余从 **8.3% 压到约 0.7%**。
代价：失败请求最坏多占用一个并发槽 `TOOL_ARG_RETRY_TIMEOUT_MS`（默认 30s），
需与 M8（重试占槽，尚未设门禁）一并评估。

**S3-b：重试提示语是通用的，没有针对已观测的失败形状。**
`PRD_TOOL_ARGS_ROOTCAUSE_V1` 的 13/13 样本指纹显示：
括号平衡、引号为奇数 7、**`backslash` 恒为 0**、工具恒为 `Bash`。
当前 nudge 只说「参数必须是合法 JSON」。应针对性补一句
**「字符串值内部的双引号必须转义」**，直接对准观测到的形状。
这是零风险改动（只改提示词，不改解析逻辑）。

**S3-c：交互式不在 `auto_continue` 覆盖范围内。**
`scripts/auto_continue.py` 只接在 `scripts/delegate` 与 `client/claude-maas-run`，
按 `PRD_RUNTIME_RESILIENCE_V1 §B8` 明确不支持交互式 TUI。
**用户遇到错误的场景恰恰是交互式。** 本 PRD 不改变该结论
（注入按键仍不可靠），但必须在文档里写清楚：
交互式下残余错误需人工 `continue`，这是已知且有意的边界。

> 明确不做：**不尝试修复畸形参数本身**。对 `Bash.command` 重新加引号
> 会静默改变将被执行的 shell 命令，风险高于失败（V6 §D2 分支 C）。

### S4 (P1) — `repair` 仍无 `tool_name`

`grep -c tool_name adapter/server.js` = **0**，`PRD_TOOL_ARGS_ROOTCAUSE_V1 §R3` 未实施。
我这次要回答「是不是总是 Bash」，仍然只能翻客户端会话记录，
而 217 上 7 次服务端错误只有 2 次能在客户端对上——**覆盖率不足**。

工具名来自客户端提交的 schema，非模型生成内容，不涉敏感数据。

### S5 — 浸泡窗口未届满（纯时间门）

```
elapsed          1.11h / 24h
request_end      125 / 200
MAAS_AUTH_REJECTED  1（发生在服务启动瞬间，需确认可解释）
```

S1 修复需重启服务 → 窗口会再次重置。因此**先修 S1，再开窗口**，
不要反过来。

---

## 3. 验收门禁

沿用项目规矩：**每条必须附「回退修复后该门禁 FAIL」的证据**。

| 门 | 断言 | 反向用例 |
| --- | --- | --- |
| S1-G | `sum(stop_reasons) + null_stop_reason_count == request_end`；且在**存在失败请求**的窗口内仍为 PASS | 改回原等式后必须 FAIL（**当前即为红**：124 vs 125） |
| S3a-G | 第 1 次重试失败、第 2 次成功 → 客户端收到真实 `tool_use`，`retry.attempted` +2、`succeeded` +1 | 上限改回 1 后必须 FAIL |
| S3a-G2 | 重试进行中触发 total watchdog → `active_requests` 归零、`reaped_slots` 不增长（M8 遗留） | 把 `cleanup` 移出 `finally` 后必须 FAIL |
| S3b-G | 重试请求体的 nudge 含转义要求；且**不含** `call.arguments` 的任何片段 | 删掉该句后必须 FAIL |
| S4-G | 畸形参数的 `request_end.repair` 含 `tool_name` | 回退后必须 FAIL（**当前即为红**：值为 None） |
| S5-G | 24h 届满、`request_end ≥ 200`、每条 `MAAS_AUTH_REJECTED` 可解释 | 纯时间门 |

S1-G 与 S4-G **修复前即为红**，天然具备鉴别力，无需另造反向用例。

已由我独立验证具备鉴别力、无需重做：**D5 上游状态透传**（回退后 2 条 FAILED）。

---

## 4. 建议顺序

1. **S1**（改断言，几行；它现在恒红，会掩盖真实回归）
2. **S3-b**（提示词补一句，零风险，直接对准 13/13 观测形状）
3. **S4**（加 `tool_name`，让服务端自己能回答归因问题）
4. **S3-a**（第 2 次重试；须与 S3a-G2 的并发槽门禁同批）
5. 重启 → 重开 24h 窗口（**S5**）
6. 全绿 → 打 **v1.2**（**S2**）

S3-c 只需文档声明，可并入任一批次。
1–4 一次重启即可全部生效，**不要分多次重启反复重置窗口**。

---

## 5. 实施记录（2026-08-25）

| 项 | 状态 | 证据 |
|---|---|---|
| S1 | ✅ | 断言改为 `sum(stop_reasons) + null-stop == request_end`；头部错误注释删除。生产（含 3 个失败请求）`211+3==214` PASS；旧等式 206≠209 必红。测试 8/8（含「漏记请求必须 FAIL」的反向门） |
| S3-a | ✅ | 重试循环化，`MAAS_TOOL_ARG_RETRIES` 默认 2；`retry_attempts` 记入 repair。S3a-G：一败一成 → attempted+2 / succeeded+1 / 客户端收到真实 tool_use；反向：`=1` 时 attempted==1 |
| S3a-G2 | ✅ | watchdog 在重试挂起期触发 → `active_requests` 归零、`reaped_slots` 不增、进程存活。配套：clientWrite/ping 加 write-after-end 守卫（无守卫时该场景会以未处理 `ERR_STREAM_WRITE_AFTER_END` 崩溃进程） |
| S3-b | ✅ | nudge 增加内层双引号转义要求（对准 13/13 观测形状）；S3b-G 同时断言 nudge **不含**畸形 args 片段 |
| S3-c | ✅ | OPERATIONS 明确：交互式残余错误需人工 `continue`，已知且有意的边界 |
| S4 | ✅ | `repair.tool_name`（malformed 主路径）；S4-G 断言 `request_end.repair.tool_name == get_weather` |
| S5 | ✅ 窗口已重开 | 单次重启后 `window-check --record`，基线 15 |
| S2 | ⏳ | 窗口届满且 ≥200 请求后打 `v1.2`（tag 说明含五批工作） |

离线全量 **789 passed / 0 failed**；生产 `verify.sh` 全门 PASS；部署 hash 一致
（`900161d8…`）。测试新增 `tests/test_release_v13.py`（6 例，自带可控
fake-upstream：flaky/hang/capture，不触共享 fixture、不耗真实配额）。

**顺带完成（前序 PRD）**：R1 在 217 核验为已生效（env 文件与运行时 environ 均
`MAAS_TOOL_ARG_MODE=enforce`，服务 active）；R2 此前已随 `b39f7e9` 提交。
**217 留意项**：其 `:3000/status` 返回登录重定向页而非适配器 JSON——3000 端口
疑似被其他服务占用或端口已变，请维护者核实（不影响 V13 门禁）。
