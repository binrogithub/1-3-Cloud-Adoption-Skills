# PRD — Agent Loop Continuity V2（收口）

状态: 已实施（M1 部署 + M2/M3 门禁修复 + M4 标准改写）
作者: Claude（独立复核，非采信实施方自述）
日期: 2026-08-24
实施日期: 2026-08-24
前序: PRD_LOOP_CONTINUITY_V1（实施方报告全部完成，715 passed）

---

## 0. 先确认：主体修复是真的有效

以下为我独立取证，不是转述：

| 证据 | 值 |
|---|---|
| 部署后 3h、936 个 assistant 回合中，`stop_reason=end_turn` 且正文仅为降级文本的回合 | **0**（修复前为 6） |
| `tool_args_retry` | attempted 18 / succeeded **17（94%）** |
| L1-B 生效证据 | `MAAS_STREAM_PROTOCOL: 1` + 客户端 `isApiErrorMessage: 1`（可自愈路径） |
| G2 反向门禁（我把 `continue` 改回 `break` 实跑） | **FAIL** —— 有鉴别力 |
| G5 反向门禁（我删掉循环后 protocol-error 块并恢复 `end_turn` 实跑） | **FAIL** —— 有鉴别力 |

L1-A 的 94% 重试成功率是本轮最高价值的改动：18 次畸形里 17 次真正完成了工具调用，
而不是"失败得更体面"。这一条应当保留并写入 release notes。

以下问题不推翻上述结论，但其中 M1 会让上述一半成果**没有真正上线**。

---

## 1. 缺陷清单

### M1 (P0) — 生产跑的构建不是被测的构建，L2 与 L4 未上线

```
/opt/claude-code-maas-proxy/server.js               sha256 95b6a6dd0ffb9c6d44a6ac60335e8257fb41f3fee9388e46a40dedf22f773177
/root/claude-code-delegate-router/adapter/server.js sha256 b8c7069b5a2c1ee55aa74edb1e54706345d5c5cc43e5b2a8a3a400727727a775
```

`make verify-offline` 的 715 passed 跑的是 repo 文件；systemd
`ExecStart=/usr/bin/node /opt/claude-code-maas-proxy/server.js` 跑的是 `/opt`。
两者 diff 显示 `/opt` 是一个**中间版本**：

| 条目 | repo | /opt（生产） |
|---|---|---|
| L1-A 重试 | 有 | 有 |
| L1-B 错误终止 | 有 | 有 |
| **L2 `continue`（不丢弃后续合法工具调用）** | 有 | **无** —— 仍是 `_setProtocolError` + `break` |
| **L4 `stop_reasons` / `degradedNoToolEmitted`** | 有 | **无** —— 完全不存在 |

实测佐证：生产 `/status` 无 `stop_reasons`、无 `degraded_no_tool_emitted` 字段。

后果：

1. L2 未上线 —— 模型一次发多个工具调用、第一个畸形时，后续合法调用在生产上仍被丢弃。
2. L4 未上线 —— **专门用来发现"任务被中断"的指标在生产上不存在。**
   本轮 PRD 的核心教训（指标与产品目标不同轴）在生产侧尚未闭环。

修复：`scripts/bootstrap.sh --dest /opt/claude-code-maas-proxy` 重新部署 + 重启，
并加门禁 M1-G（见 §2）。

> 这与项目历史上的 worktree divergence 是同一类问题：**验收跑源码，进程跑旧文件。**

### M2 (P1) — G1 没有鉴别力

我把 L1-B 完整回退（删除循环后的 protocol-error 块、恢复
`ctrl.finishReason = "end_turn"`）后实跑：

```
test_g5_no_silent_end_turn_only_degradation_text  FAILED
test_g1_no_silent_end_turn                        PASSED   <-- 应当失败
```

原因：G1 未设 `MAAS_TOOL_ARG_RETRY=0`，`tool_malformed` 场景下重试成功并产出真实
`tool_use`，于是无论 L1-B 在不在，G1 都绿。**G1 实际只覆盖 L1-A，不覆盖它注释里
声称覆盖的 L1-B。**

修复：拆成两条 —— `test_g1_retry_path`（重试开）与 `test_g1_no_retry_must_error`
（`MAAS_TOOL_ARG_RETRY=0`，断言收到 SSE `error` 帧且 `stop_reason != end_turn`）。
后者必须附回退即 FAIL 的证据。

### M3 (P1) — `test_g3_no_retry_when_text_already_streamed` 是恒真空测试

该测试自己的注释写明：

> To test the "already streamed" guard we'd need a scenario with
> text-then-malformed-tool. For now, verify that the retry path does not produce
> duplicate message_start **(which it shouldn't regardless)**.

断言 `len(message_starts) <= 1` 对任何实现都成立。这条测试零信息量，却计入了
"8 条全绿"。

需要区分清楚两件事：

- **PRD V1 §L1-A 的硬约束（已流出文本时禁止重试）在代码里确实没有实现** ——
  调用点 `server.js:1084` 无 `textStarted` / `thinkingStarted` 守卫。
- **但这不构成缺陷**：实现选择了非流式定向重试（`stream: false` +
  `tool_choice` 强制同名函数），只取 `tool_calls[0].function.arguments` 填入
  `tool_use.input`，**不会向客户端重复输出任何正文**。约束因实现路径改变而失去必要性。

真正的缺陷只是 M3：一条恒真测试冒充了对该约束的验证。

修复：删除该测试，或补一个 `text_then_malformed_tool` fake-upstream 场景，
断言客户端收到的 text_delta 拼接结果**只出现一次**。

### M4 (P1) — V11 §3 的验收标准与 L1-B 直接冲突

`docs/PRD_RELEASE_V11.md:165`：

> 窗口内 `stream protocol error` 新增为 0

**L1-B 的设计意图就是产生 protocol error**（用可自愈的硬失败替换 0% 自愈的静默
end_turn）。生产已出现 1 次。该标准在新设计下永远不可能绿。

修复：改写为两条正交标准 ——

```
(a) 窗口内 stop_reason=end_turn 且正文仅为降级文本的回合数 = 0     （任务连续性）
(b) 窗口内 protocol error 中，客户端自动恢复比例 >= 32%           （失败可自愈性）
```

(b) 的 32% 基线取自本项目历史实测（n=25，8 次自动恢复）。

### M5 (P2) — G5 的 docstring 与实现不符，生产口径未入门禁

`tests/test_loop_continuity.py` 文件头写 `G5: full JSONL scan`，实际实现是
单请求合成检查。生产口径的全量扫描目前只有我手工跑过（结果 0）。

修复：docstring 改为与实现一致；把生产口径扫描做成 `scripts/verify.sh` 的一条
live 门禁（扫描 `/root/.claude-maas/projects/`，只统计窗口内时间戳）。

### M6 (P2) — 重试的 token 消耗不计入客户端 usage

`retryToolCallArgs` 额外发起一次上游请求（本窗口 18 次），其
`usage` 从未累加进返回给客户端的 `message_delta.usage`。计费与统计偏低。

修复：把重试响应的 `usage.prompt_tokens` / `completion_tokens` 累加进本请求的
usage，并在 `request_end` 增加 `retry_tokens` 字段。

### M7 (P2) — 重试的上下文缺口

重试用的是原始 `openaiReq.messages`，**不含本回合已经流出的 assistant 正文**。
若模型先输出一段说明再调用工具，重试时模型看不到自己刚说过的话，
生成的参数可能与已流出正文不一致。`tool_choice` 强制同名函数缓解了大部分风险，
但不能消除。

修复：把本回合已聚合的 assistant 文本作为一条 `assistant` message 追加到重试
请求的 messages 中（在 nudge 之前）。

### M8 (P2) — 重试占用并发槽，与 total watchdog 的交互未验证

`TOOL_ARG_RETRY_TIMEOUT_MS` 默认 30000。重试发生在请求生命周期内，
最坏情况每个请求多占用一个并发槽 30s，`capacity = 8`。
且未验证 `MAAS_TOTAL_TIMEOUT`（600s）看门狗在重试进行中触发时，
并发槽是否仍被正确释放 —— 这正是本项目 R1 P0 容量泄漏的同一条路径。

修复：加门禁 —— 构造"重试期间 total watchdog 触发"用例，
断言 `active_requests` 归零且 `reaped_slots` 不增长。回退 `finally` 中的
`cleanup` 后该门禁必须 FAIL。

### M9 — 24h enforce 窗口已被打断，且构建已变，必须重开

```
原窗口     2026-08-23 01:50:47 → 2026-08-24 01:50:47（build 7edc1ae0）
实际重启   2026-08-24 01:25:15（新进程，NRestarts=0）
```

窗口在**差 25 分 32 秒**届满时被部署打断，收集到 23h34m 数据。
且被观测的代码已经实质变更（新增重试与错误终止），旧窗口数据对新构建无效。

处置：不必为凑满 24h 而回滚。按 §2 完成 M1 重新部署后，
**以新构建为准重开 24h 窗口**，验收标准用 M4 改写后的 (a)(b) 两条。
旧窗口的 23h34m 数据在 release notes 中作为"前一构建的观测"保留，不得计入新窗口。

---

## 2. 验收门禁

沿用 V1 的规矩：**每条门禁必须附"回退修复后该门禁 FAIL"的证据**，
未附反向证据的不计入验收。

| 门 | 断言 | 反向用例 |
|---|---|---|
| M1-G | `sha256(/opt/claude-code-maas-proxy/server.js) == sha256(adapter/server.js)`，且 `/status` 同时含 `stop_reasons` 与 `degraded_no_tool_emitted` | 部署旧文件后必须 FAIL |
| M2-G | `MAAS_TOOL_ARG_RETRY=0` + 畸形 args → 客户端收到 SSE `error` 帧，且不存在 `stop_reason=end_turn` | 回退 L1-B 后必须 FAIL（V1 的 G1 在此条件下**不会**失败，已实测） |
| M3-G | `text_then_malformed_tool` 场景 → 客户端 text_delta 拼接结果中该段正文只出现 1 次 | 改成流式重试后必须 FAIL |
| M4-G | live：窗口内 (a) 静默 end_turn 回合数 = 0；(b) protocol error 自动恢复率 >= 32% | (a) 用旧构建数据跑必须 FAIL（旧值为 6） |
| M8-G | 重试进行中触发 total watchdog → `active_requests` 归零 | 把 `cleanup` 移出 `finally` 后必须 FAIL |

已由我独立验证具备鉴别力、无需重做的：**G2、G5**。

---

## 3. 与 v1.1 发布的关系

**当前不可打 v1.1 标**，唯一的硬阻塞是 M1：生产运行的构建缺少 L2 与 L4，
其中 L4 是本轮教训的落地点。M1 修复是一次重新部署，成本很低。

M2/M3 属于门禁质量问题，不改变运行时行为，可与 M1 同批合入。
M4 必须在重开窗口**之前**改写，否则新窗口的验收标准自相矛盾。
M6/M7/M8 可进 v1.2，但 M8 涉及并发槽，若不修则必须写入 Known limitations。

Known limitations 需新增一条：

> 工具参数畸形时，适配器会向上游定向重试一次（实测成功率 17/18）。
> 重试失败时以 protocol error 终止本回合（历史实测约 32% 由客户端自动恢复），
> 不再静默结束。重试的 token 消耗当前未计入返回的 usage。
