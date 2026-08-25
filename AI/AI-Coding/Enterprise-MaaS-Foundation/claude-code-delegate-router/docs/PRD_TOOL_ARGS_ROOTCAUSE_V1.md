# PRD — Tool Args Root Cause V1（124.81.97.217 `stream protocol error` 调查与修复）

状态: 待实施
作者: Claude（全部事实经独立取证）
日期: 2026-08-25
调查对象: `root@124.81.97.217`（ecs-maas-test，CentOS 8）
被调查构建: `14154eb7297df8084135…`
前序: PRD_LOOP_CONTINUITY_V1+V2 / PRD_RUNTIME_RESILIENCE_V1

---

## 0. 结论摘要

`API Error: stream protocol error` 有**两层原因**，必须分开处理：

| 层 | 结论 |
| --- | --- |
| **为什么用户看得见它** | 217 的 `MAAS_TOOL_ARG_MODE` 未设置 → 默认 `observe` → 已经写好并验证过的恢复链路（L1-A 重试，实测成功率 17/18）**一次都没执行**。这是**可立即修复**的配置缺陷。 |
| **为什么会产生畸形参数** | 上游 GLM-5.2 在 `Bash` 工具的参数上产出非法 JSON。指纹高度固定，**适配器无法修复**，只能靠重试规避。 |

---

## 1. 取证

### 1.1 217 当前状态（uptime 5.16h）

```
error_counts        {'MAAS_AUTH_REJECTED': 1, 'MAAS_CLIENT_ABORTED': 6, 'MAAS_STREAM_PROTOCOL': 7}
reject_classes      {'not_json': 7}
repair_rejected     {'gate2_struct': 7}
tool_args_retry     {'attempted': 0, 'succeeded': 0}      ← 重试从未执行
tool_args_degraded  0
stop_reasons        {'tool_use': 233, 'end_turn': 21, 'max_tokens': 1}
```

7 次失败 / 233 次工具回合 ≈ **3.0%**。

### 1.2 模式确认

```
/etc/claude-code-proxy/maas.env      MAAS_TOOL_ARG_MODE 出现 0 次
/proc/<MainPID>/environ              MAAS_TOOL_ARG_MODE 未设置 → 默认 observe
adapter/server.js:784                const TOOL_ARG_MODE = process.env.MAAS_TOOL_ARG_MODE || "observe"
```

`server.js:1213` 的重试分支被 `if (TOOL_ARG_MODE === "enforce")` 包着，
observe 走 else → `ctrl._setProtocolError(...)` 直接硬失败。
**这解释了 `retry.attempted = 0` 与 7 次错误并存的矛盾。**

### 1.3 畸形 payload 指纹（7/7 完全一致）

```
len=38 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=38 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=41 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=41 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=39 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=39 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
len=41 class=not_json first=123 braces=1/1 brackets=0/0 quotes=7 bslash=0 lt/gt=0/0
```

合并 83.10 的 6 例（`len ∈ {38,39}`，其余字段逐项相同），
**共 13 个样本，`double_quote` 恒为 7、`backslash` 恒为 0、括号恒平衡。**

客户端侧两台都指向同一个工具：**`Bash`**。

### 1.4 从指纹能确定的事实

1. **不是截断。** 括号 1/1 平衡；`reject_class` 是 `not_json`（Node 报
   "Unexpected token"），不是 `unterminated_string`（读到 EOF 仍在字符串内）。
2. **不是 `<tool_call` 改写标记。** `is_markup=false`，`lt`/`gt` 恒为 0。
3. **引号是奇数（7）。** 合法 JSON 对象的引号必然成对。
4. **模型从未产出转义符。** `backslash` 在 13/13 样本中恒为 0。

### 1.5 根因假设（**尚未确证**）

第 4 点是最有信息量的：`Bash` 工具的 `command` 参数里，
shell 命令天然含双引号（`grep "foo" file`）。若模型**没有转义**内层引号，
结果正是：`{` 开头、括号平衡、引号总数变成奇数、反斜杠为 0、
JSON.parse 在意外 token 处失败——**与 13/13 观测逐项吻合**。

> **这是假设，不是结论。** 本项目此前已有一次由类比得出的
> `<tool_call` 假设被生产观测推翻的记录（RELEASE_NOTES_v1.1）。
> 在抓到一个真实 payload 之前，不得把它写进任何结论性文档。

### 1.6 为什么三道闸门修不了

闸门 2 只做**括号闭合补全**，针对的是截断。此处括号本就平衡、内容未截断，
缺的是字符串内部的引号语义。按 `PRD_RELEASE_CLOSURE_V6 §D2` 判定表，
属**分支 C：值真缺，补全在原理上无解**。

对 `Bash` 的 `command` 尤其危险：任何「重新加引号」的猜测都会**静默改变
将被执行的 shell 命令**。这比失败更糟。**明确不做参数修复。**

---

## 2. 修复项

### R1 (P0) — 217 立即开启 enforce

```
/etc/claude-code-proxy/maas.env  追加  MAAS_TOOL_ARG_MODE=enforce
systemctl restart claude-code-maas-proxy
```

验证：`/proc/<MainPID>/environ` 含该变量。
预期效果：按 83.10 实测的 **17/18（94%）** 重试成功率，
当前 3.0% 的失败率应降到 ~0.2%。

> 83.10 已于 2026-08-24 23:25 完成同样处置，改后 `error_counts` 归空。

### R2 (P0) — bootstrap 必须写入该变量，否则每台新机重犯

`scripts/bootstrap.sh` 原本**根本不写**这个变量，所以 217（我用旧 bootstrap
安装）落地即 observe。这不是运维疏漏，是**产品缺陷**：
修复代码随版本发布，但默认不生效。

补丁已在 83.10 的工作树中完成但**尚未提交**：

- 默认 `OPT_TOOL_ARG_MODE="enforce"`，写入 env 文件；
- 新增 `--tool-arg-mode off|observe|enforce`；
- **取值校验**（拼错即 die）——没有这条的话拼错会静默退回 observe，
  正是本 PRD 要消灭的失效模式；
- dry-run 回显同步。

实测：默认 `enforce`；`--tool-arg-mode observe` 生效；`bogus` 被拒。
`tests/test_bootstrap.py` 37 passed，全量 749 passed。

**动作**：提交该补丁；217 用新 bootstrap 复核（或按 R1 手工补齐）。

### R3 (P1) — 诊断缺 `tool_name`

`repair` 结构里没有工具名，导致「是不是永远是 Bash」这个问题**只能靠翻客户端
会话记录**才能回答（我这次是这么做的，且 217 上 7 次服务端错误只有 2 次能在
客户端 JSONL 里对上——覆盖率不足）。

工具名来自**客户端自己提交的 schema**，不是模型生成内容，不涉敏感数据。

**动作**：`repair` 增加 `tool_name` 字段。

### R4 (P1) — 抓一个真实 payload，确证或推翻 §1.5

在既有安全约束下启用一次定向抓取：

- `MAAS_DEBUG_CAPTURE_ARGS=1`，**默认关**，仅本次排查临时开启；
- 写 `/var/log/claude-maas-debug/`，`0600 root:root`；
- **不进 journald**；上限 10 条；**24h 后删除**；
- 只抓 `reject_class=not_json` 且 `is_markup=false` 的样本。

抓到后写入 release notes 的 Known limitations，
并**明确标注假设是被证实还是被推翻**。

### R5 (P2) — 上游 4xx 状态码透传

与本次调查相邻的既有缺陷（`PRD_UPSTREAM_PROFILE_V1 §D5`）：
适配器把上游 4xx 一律回成 502。已有实际危害证据——
智谱返回 `429 code 1113 余额不足`，客户端看到 502 并重试 10 次，
而这是充值前**永远不会成功**的计费错误。

建议把 D5 从 P2 提到 **P1**：它会把一切上游拒绝伪装成「服务端临时故障」。

### R6 (P2) — 无告警

两台主机都没有对 `MAAS_STREAM_PROTOCOL` 的任何监控。
本次是用户先感知、再人工排查。建议 `/status` 计数接入现有巡检。

---

## 3. 验收门禁

沿用项目规矩：**每条必须附「回退修复后该门禁 FAIL」的证据**。

| 门 | 断言 | 反向用例 |
| --- | --- | --- |
| R1-G | 217 `/proc/<MainPID>/environ` 含 `MAAS_TOOL_ARG_MODE=enforce`；注入畸形 args 后 `tool_args_retry.attempted` 递增 | 改回 observe 后必须 FAIL（**当前即为红**：attempted=0） |
| R2-G | 全新 bootstrap 安装出的 env 文件含 `MAAS_TOOL_ARG_MODE=enforce`；`--tool-arg-mode bogus` 被拒 | 移除默认值/校验后必须 FAIL |
| R3-G | 畸形参数的 `request_end.repair` 含 `tool_name` | 回退后必须 FAIL（当前即为红） |
| R4-G | 抓取文件权限 0600、不出现在 journald、条数 ≤10、24h 后不存在 | 放宽任一约束必须 FAIL |
| R5-G | 上游 429 → 客户端收到 429（非 502） | 修复前必须 FAIL（当前即为红，已实测） |

R1-G / R3-G / R5-G **修复前即为红**，天然具备鉴别力，无需另造反向用例。

---

## 4. 明确不做

- **不修复畸形参数本身。** 对 `Bash.command` 重新加引号会静默改变将被执行的
  shell 命令，风险高于失败。恢复手段只用「重新问上游要一次」（L1-A）。
- **不为凑样本人为构造生产失败**（项目既有规则）。R4 只抓自然发生的样本。
- **不改变 key 存放拓扑**。

---

## 5. 建议顺序

1. **R1**（217 开 enforce —— 一条命令 + 一次重启，立即止血）
2. **R2**（提交 bootstrap 补丁，堵住下一台机器复发）
3. **R3**（加 `tool_name`，让服务端自己能回答「是不是总是 Bash」）
4. **R4**（抓一次 payload，把 §1.5 从假设变成结论或推翻它）
5. **R5 / R6**

R1 与 R2 之间无依赖，可并行。
