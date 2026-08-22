# PRD：发布收口 v3（坏 JSON 补全 + 观测面修正 + 挂起路径门禁）

状态：D1-D5 已落地，待部署 + 观察窗
前置：
- `docs/PRD_RELEASE_CLOSURE_V2.md`（R1/R5/D4 已交付并部署，commit `8a35e6b`）
- `docs/PRD_KEEPALIVE_CLOSURE_V1.md`（K1/K2 已交付，commit `93a4b30`）

核查时间：2026-08-22 02:50 CST，核查人：独立复验（非实施方自评）

## 0. 产品摘要

**V2 的 R1 是真修好了，独立复验通过。** 用与线上事故同形的 idle-hang 场景做 A/B：

| 失败模式 | OLD `93a4b30` | NEW `HEAD` |
| --- | --- | --- |
| idle-hang（`silence` 场景，无异常、无 socket） | `active_requests=1` 持续 30s+ → **LEAK** | 立即归还 → **PASS** |
| client-abort | `active_requests=0` → PASS | `active_requests=0` → PASS |

第二行是本轮方法论上最重要的一条：**client-abort 路径在新旧代码上都通过，零鉴别力**——
而这正是 `PRD_KEEPALIVE_CLOSURE_V1.md` §4 用来证明"无容量泄漏"的那条路径。
有了对照才能确认：那条证据当时就是空的。

`make verify-offline` → **664 passed**（658 基线 + 6 新增），exit 0，无回归。
部署新鲜度三项齐（SHA 一致 / MainPID 196772 / `/status` 新字段齐全）。
结构化日志确已进 journald（每请求一行 `request_end`）。

**但发布/关闭仍被 5 项阻塞，其中 T1 是产品决定，T2 是观测面失真。**

## 1. 缺口

### T1 — `stream protocol error` 稳定复发且在加速，根因指向 GLM-5.2 坏 tool JSON（P1，发布阻塞）

按 `isApiErrorMessage === true` 全量统计（位置：`/root/.claude-maas/projects/`），
自 06:13 保活部署以来**不是 1 次，是 4 次**：

    2026-08-22 00:51:07 CST    ← 间隔 0.7h
    2026-08-22 00:11:54 CST    ← 间隔 2.8h
    2026-08-21 21:25:21 CST    ← 间隔 12.1h
    2026-08-21 09:16:44 CST

频率在收敛。**四次全部发生在 `tool_result` 的下一轮**，报错的 assistant 消息
都是先出了 `text` 然后中断（同一会话 `acd37b29`）。

根因路径已指认：

    adapter/server.js:572   JSON.parse(call.arguments) 抛错 → ctrl.protocolError = true
    adapter/lifecycle.js:318 finalize() → _fail(STREAM_PROTOCOL, UPSTREAM_FAILED)
    adapter/server.js:113   → 客户端文案 "stream protocol error"

`tests/helpers/fake_upstream.js` 的 `tool_malformed` 场景
（`arguments: '{"city":'`）复现的就是这条路径，
`tests/test_adapter_contract.py:221` 还专门断言"不得降级成 `{}`"。
**即当前行为是设计行为，不是 bug。**

产品决定（本轮已拍板）：**改为先尝试补全，补不回来才失败。**

### T2 — `client_bytes` 结构性恒为 0，恰好是饥饿断流的判定字段（P1，发布阻塞）

    adapter/server.js:705    client_bytes: res.bytesWritten || 0

实测（Node 原生行为）：

    res.bytesWritten        = undefined     ← http.ServerResponse 上没有此属性
    res.socket.bytesWritten = 699           ← 正确来源

线上日志印证：一条 `upstream_chunks=553`、`duration_ms=23707` 的正常请求，
`client_bytes` 也是 0。

`tests/test_observability.py:173` 只断言 `"client_bytes" in entry`——
**字段在，值无意义，门禁照过**。这是本仓库"无鉴别力断言"的又一变体：
新增了一个观测字段，但没有任何用例断言它的值有区分能力。

危害是定向的：`client_bytes=0` 是饥饿断流的签名，现在健康请求也是 0，
两者不可区分。整个项目折腾数轮的那个问题，新加的观测面恰好看不见。

### T3 — 两条新反向门覆盖的是 throw 路径，线上事故是 hang（P1）

`tests/test_capacity_leak.py` 的两条用例都用
`MAAS_TEST_THROW_AFTER=for_await` 注入**抛错**。而 V2 记录的线上事故是
**挂起**（2h20m、无 socket、无异常）——`finally` 对挂起无效，真正救回来的是
`onTimeout` 里新增的 `cleanup(ctrl)`（`server.js:348`）。

`grep -rn "reaper\|watchdog" tests/*.py` 只有一条
`assert "reaped_slots" in status`（字段存在性）。即：

- watchdog 归还槽的路径：**零回归门禁**（本轮由人工 A/B 验证，无自动门禁）
- reaper 兜底清扫：**从未被执行过**（`reaped_slots` 至今为 0，无用例触发）

将来任何人改动 `onTimeout`，门禁不会响。

### T4 — 13 处 protocolError 映射到同一个 error code，日志无法区分（P2）

`grep -n "protocolError = true"` 命中 13 处（`server.js` 3 处 + `lifecycle.js` 10 处），
全部收敛到 `MAAS_STREAM_PROTOCOL`。D3 的结构化日志记了 `error_code`，
但没记**哪一条分支**触发。下次复发仍然分不清是坏 tool JSON、块配对违规、
还是 tool args 超限（`MAX_TOOL_ARGS_BYTES`）。

T1 的根因指认目前是**基于时序相关性的推断**，不是日志证据。

### T5 — R3 观察窗按 PRD 自己的口径当前不通过（P1）

`PRD_KEEPALIVE_CLOSURE_V1.md` §3.4 与 `PRD_RELEASE_CLOSURE_V2.md` §3.4 写的都是
"按 `isApiErrorMessage === true` 全量统计，新增为 0"。

旧 06:13 窗口全量统计是 **4**，不是 0。只有把口径收窄到
`response stopped arriving` 那一句才是 0——而收窄口径正是 V2 §3.4 明令禁止的
（"不得只统计单一文案"）。因此"旧窗口 8/22 06:13 满"这条**满不了**。

新构建（01:23 部署）后确为 0，但截至 02:50 只跑了 1.4h、会话记录 27 条，
曝光量不足以支撑任何结论。

## 2. 决策

### D1：tool args 坏 JSON 补全 —— 三道闸门，任何一道不过就照旧失败

补全**不是**放宽"不得降级成 `{}`"的契约，而是在其之前插入一个受限的恢复层。
截断本质上是有歧义的（`{"city":"Beijing"` 也可能原本是
`{"city":"Beijing","unit":"C"}`），所以补全必须由证据授权，不能靠猜。

**闸门 1（来源）**：只在上游给出**干净的工具调用终止**时尝试补全，即
`choice.finish_reason ∈ {tool_calls, stop}`。若为 `length`（被 max_tokens 截断）
或流结束时无 finish_reason，**不补全**——那种情况参数是真缺，补出来就是编造。

**闸门 2（结构）**：只做结构性闭合，且仅限"最后一个 token 是完整值"的情形。

允许：
- 为未闭合的 `{` / `[` 追加 `}` / `]`

禁止（命中即判不可补，照旧失败）：
- 闭合未终止的字符串（`{"city":"Beij` → 中途截断会静默丢字符）
- 最后一个 token 是 key、`:`、或尾随 `,`（`{"city":` → 键无值）
- 插入任何值，包括 `null` / `""` / `{}` / `[]`
- 丢弃任何键，或丢弃带部分值的键

**闸门 3（语义）**：补全结果必须通过该工具 `input_schema` 校验——
`required` 字段全部存在，顶层属性类型匹配。schema 来自请求体
`body.tools[].input_schema`（`server.js:234` 已在手），不需要新增依赖。
工具未找到或无 schema 时降级为"仅闸门 1+2"，并在日志中标记 `schema: absent`。

**绝对禁止**：补全结果为 `{}`。`tests/test_adapter_contract.py:221` 的契约保持不变，
`tool_malformed` 那条现有用例**必须继续 FAIL**——这是本决策不越界的判据。

开关：`MAAS_TOOL_ARG_REPAIR=0` 关闭（默认开启）。与 `MAAS_THINKING_DISABLED` 同属
kill switch 语义，生产不得设置。

### D2：补全必须可计量，不得静默成功

- `/status` 新增 `tool_args_repaired`（补全成功计数）、
  `tool_args_repair_rejected`（按闸门分类计数：`gate1_finish` / `gate2_struct` / `gate3_schema`）
- 结构化日志新增 `repair: {attempted, applied, gate, schema}` 字段
- **门槛条款**：soak 窗口内若 `tool_args_repaired / 总 tool 调用数 > 5%`，
  记为**上游质量发现**，需单独结论，**不得**因为"补全都成功了"就判通过。
  补全是安全网，补全率高说明上游在退化。

### D3：`client_bytes` 改为写入侧计数，并配双向门禁

- 在 `clientWrite` 与 ping 分支各累加 `clientBytesWritten`（不用 `res.socket.bytesWritten`：
  socket 在 close 后可能为 null，且含 TCP/HTTP 头开销，不是"给客户端的协议字节"）
- 门禁**双向**：
  - 正向：`reasoning_then_text` 正常请求，日志 `client_bytes > 0` 且与实际读到的字节数同量级
  - 反向：`silence` 场景（客户端一个内容字节都没拿到，仅 keepalive），
    断言 `client_bytes` 能把两者区分开
- 禁止再用 `assert "client_bytes" in entry` 这类存在性断言充数

### D4：补齐 hang 路径与 reaper 的反向门

- `test_capacity_leak.py` 新增 `test_idle_hang_releases_slot`：
  `silence` 场景 + 低 idle/total 超时，断言流结束后 `active_requests == 0`。
  **修复前（`93a4b30`）必须 FAIL**（已人工验证：active=1 持续 30s+），
  修复后 PASS。
- 新增 `test_reaper_releases_orphan_slot`：用测试钩子
  （`MAAS_TEST_SKIP_CLEANUP=1`，仅在 `NODE_ENV=test` 下生效）制造一个watchdog
  也不归还的孤儿槽，断言 reaper 在 `TOTAL_TIMEOUT + 60s` 后归还且
  `reaped_slots` 递增。reaper 是 V2 交付的兜底，**至今从未被执行过**。

### D5：`protocol_error_reason` 落日志

13 处 `protocolError = true` 各带一个常量原因串
（`tool_args_malformed` / `tool_args_oversized` / `block_pairing` / `message_ordering` / ...），
写进 `ctrl.protocolErrorReason`，由结构化日志与 `/status.recent_errors` 输出。

**这是 T1 根因从"推断"升级为"证据"的唯一手段**，必须先于 D1 上线或与之同批。

### D6：不采用

- 不放宽"不得降级成 `{}`"的契约（D1 三道闸门是收紧后的例外，不是放宽）
- 不对坏 JSON 做重试（重试会放大 tool 副作用风险，且上游是同一模型）
- 不改 `MAAS_KEEPALIVE_INTERVAL` / idle / total 超时语义
- 不因 T1 回退 V2 的 R1/R5 改动
- 不用重启掩盖任何一项

## 3. 验收标准

1. **D1 正向门**：新增 fixture `tool_truncated_closeable`
   （`arguments: '{"city":"Beijing"'` + `finish_reason: tool_calls`）→ 补全成功，
   客户端收到完整 `tool_use` 块，`input == {"city":"Beijing"}`。
2. **D1 反向门（三条，缺一不可）**：
   - `tool_malformed`（`'{"city":'`，键无值）→ 闸门 2 拒绝，**仍然失败**，
     `test_adapter_contract.py:221` 保持绿
   - 新增 `tool_truncated_midstring`（`'{"city":"Beij'`）→ 闸门 2 拒绝，仍然失败
   - 新增 `tool_truncated_by_length`（`'{"city":"Beijing"'` + `finish_reason: length`）
     → 闸门 1 拒绝，仍然失败
3. **D1 schema 门**：构造 `required: ["city","unit"]` 而补全结果只有 `city` 的用例
   → 闸门 3 拒绝，仍然失败。
4. **D3 双向门**：正向 `client_bytes > 0`；反向 `silence` 场景可区分。
   两条都要在修复前对当前实现跑一遍——正向门必须 **FAIL**（当前恒为 0）。
5. **D4**：`test_idle_hang_releases_slot` 对 `93a4b30` FAIL、对 HEAD PASS，双向证据留存；
   `test_reaper_releases_orphan_slot` 观察到 `reaped_slots` 从 0 变 1。
6. **D5 + T1 根因确认**：soak 窗口内至少捕获 1 次
   `protocol_error_reason == "tool_args_malformed"` 的日志，**T1 的根因方成立**。
   若窗口内捕获到的是别的 reason，T1 的定性推翻，重新分析。
   若一次都没复现，记为"已具备诊断能力的未复现项"，**不得记为已修复**。
7. **T5 观察窗**：以本轮部署时刻为起点满 24h，在 `/root/.claude-maas/projects/` 下按
   `isApiErrorMessage === true` **全量**统计，新增为 0。
   不得收窄到单一文案，不得用文本 grep。
8. **容量观察**：部署后 ≥ 6h，在 `ss -tnp | grep :3000` 为空时采样 `/status`
   至少 3 次，`active_requests` 必须为 0。
9. **补全率**：D2 的 5% 门槛条款结论明确（通过 / 记为上游质量发现）。
10. **回归**：`make verify-offline` 全绿，总数 ≥ 664 + 新增用例数；
    `make verify-live` 7 道 gate 全绿；真实 HOME（`~/.claude/`）未被改动。
11. **运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
    SHA-256 逐一相等；MainPID 变化；`/status` 可达。

## 4. 实施顺序

1. D5（`protocol_error_reason`）先行——没有它，T1 的根因永远是推断
2. D3 正向门先跑出 FAIL（钉死 `client_bytes` 恒 0）→ 改写入侧计数 → 转 PASS
3. D4 两条门禁：`idle_hang` 对 `93a4b30` 跑出 FAIL → 对 HEAD 转 PASS；reaper 门补齐
4. D1 三道闸门 + §3.2/§3.3 的四条反向门（先写门禁，再写补全实现）
5. D2 计量字段
6. `make verify-offline` 重取基线 → 部署 → §3.11 运行态三项核对
7. §3.7 的 24h 窗口 + §3.8 的 6h 容量观察（并行计时）
8. 全部达标 → v1.1 release notes → 发布/关闭决定

## 5. 关闭条件

§3 全部 11 项达标前，**不关闭项目**。

特别提示两条不得走捷径的：

- **§3.2 的第一条**：`tool_malformed` 现有用例必须**继续失败**。如果实施过程中
  这条用例变绿了，说明补全越过了"不得降级成 `{}`"的契约线，是事故不是进展。
- **§3.6**：T1 的根因目前是时序相关性推断。没有 `protocol_error_reason` 的日志证据，
  "坏 JSON 补全修复了 R4"这句话不成立——只能说"上线了一个补全层"。
