# PRD：发布收口 v4（补全层零命中定性 + 记账修正）

状态：Phase 0 已落地（D4 记账修正 + D2 拒因分类），待部署 + 取样期
前置：
- `docs/PRD_RELEASE_CLOSURE_V3.md`（T1–T4 已交付并部署，commit `eb4336c`）
- `docs/PRD_RELEASE_CLOSURE_V2.md`（R1/R5 已交付，commit `8a35e6b`）

核查时间：2026-08-22 09:45 CST，核查人：独立复验（非实施方自评）

## 0. 产品摘要

**V3 交付的四项里，T2/T4 已核销并在生产得到验证；T1 上线后对真实故障零命中。**

已核销：

| 项 | 生产证据 |
| --- | --- |
| T2 `client_bytes` | 真值 19843 / 2707 / 904 / 242，与 `upstream_chunks` 同向，不再恒 0 |
| T4 `protocol_error_reason` | 捕获 `"tool_args_malformed"` — **V3 §3.6 达成**，R4 根因由推断升级为证据 |
| 补全层可用性 | `tool_truncated_closeable` 正向用例 `repaired:1`、0 个 error 帧、`message_stop` 正常 |
| 部署新鲜度 | SHA 一致 / MainPID 276781 / `/status` 新字段齐全 |
| 回归 | `make verify-offline` 673 passed |

**但补全层在生产上一次都没生效**，这是本轮的全部内容。

## 1. 缺口

### U1 — 补全层生产零命中，用户可见失败率未改善（P1，发布阻塞）

部署后 28 分钟（09:17:02 → 09:45），81 个 `request_end`：

    tool_args_repaired          = 0
    tool_args_repair_rejected   = { "gate2_struct": 3 }
    MAAS_STREAM_PROTOCOL 请求数 = 3        →  失败率 3.7% (3/81)

三次真实坏 JSON **全部**在闸门 2 被拒，补全一次都没应用。T1 上线前后，用户撞到的
硬失败没有任何变化。

闸门 2 只在三种形态下拒绝：字符串未终止、键无值、尾随逗号/冒号。而
"值完整、只差闭合括号"这一类（`{"city":"Beijing"`）闸门 2 **是接受的**——
正向用例已证明。

**因此可以推断：线上的真实故障形态不是"截断在完整值之后"。** 它落在
未终止字符串、键无值、或者根本不是 JSON（单引号 Python dict、非 JSON 包装）
这些类别里。**如果是后者，T1 是照着一个不发生的失败模式设计的，靠补括号永远救不回来。**

这个推断目前**无法证实**，因为拒因不可观测——见 U2。

### U2 — parse 失败的形态被丢弃，且原始错误消息不能直接落盘（P1，发布阻塞）

`adapter/server.js:810` 的 `catch { ... }` 丢弃了 `JSON.parse` 的异常对象。
没有它就无法判断 T1 该修闸门 2、该扩范围、还是该重新划范围。

Node v22.23.2 实测，错误消息的区分度足够：

| `JSON.parse` 消息 | 输入形态 | 可补性 |
| --- | --- | --- |
| `Unexpected end of JSON input` | `{"city":`（键无值）、空串 | 不可补（值真缺） |
| `Unterminated string in JSON at position N` | `{"city":"Beij` | 不可补（丢字符） |
| `Expected ',' or '}' after property value` | `{"city":"Beijing"` ✅ / `{"n":12` ⚠️ / `{"cmd":"echo "hi""}` ⚠️ | 混合 |
| `Expected ',' or ']' after array element` | `{"paths":["a","b"` | 混合（元素可能缺失） |
| `Expected property name or '}'` | `{'city': 'Beijing'}`（单引号方言） | 需方言归一化 |
| `Expected double-quoted property name` | `{"a":1,`（尾随逗号） | 不可补 |
| `Unexpected token 'g', "get_weathe"... is not valid JSON` | 根本不是 JSON | 不可补 |

**关键约束**：最后一类消息**内嵌了 payload 的 10 字符摘录**
（`"get_weathe"...`）。原始 message 直接落盘会把工具参数内容漏进日志，
与 V2 D3 的"不记录 prompt/tool 正文"约定冲突，也会让
`test_observability.py` 的 canary/key 不泄漏门禁形同虚设。

所以**只能落分类枚举，不能落原始消息**。

### U3 — `error_counts` 双计，而门槛条款读的就是这个计数器（P2）

    /status: error_counts = { "MAAS_STREAM_PROTOCOL": 6 }   ← 实际 3 个请求
    recent_errors 中同一 request_id、同一毫秒出现两次

隔离台架复现：单个 `tool_malformed` 请求 → `error_counts: {"MAAS_STREAM_PROTOCOL": 2}`，
而 `tool_args_repair_rejected` 正确计 1。

来源是 V2 D1 的副作用：`lifecycle.js:386` 的 `_fail()` 调 `this._onTimeout(code)`，
`server.js:494` 的 `onTimeout` 里记一次 `recordError`；终态路径 `server.js:859`
再记一次。`_fail` 在 V2 之后不再只服务于 timeout，回调名和职责已经不匹配。

影响面：
- V3 §3.9 的 5% 补全率门槛，分母/分子口径被污染
- §3.7 观察窗按 `error_counts` 统计会翻倍
- `recent_errors` 环形缓冲 20 格，每个错误占 2 格，有效深度砍半

客户端协议面正常（实测只收到 1 个 `event: error` 帧），仅影响观测与判据。

### U4 — V3 §3.7 观察窗当前为 3，不通过（P1）

窗口以 09:17 新部署为起点，28 分钟内已有 3 次 `MAAS_STREAM_PROTOCOL`。
与上一轮不同，这次不是曝光不足——81 个请求是有效样本。按 PRD 全量口径，
这条明确不通过。

## 2. 决策

### D1：Phase 0 —— 只做诊断分类与记账修正，不动补全逻辑

本轮**禁止**在拿到真实分布之前改闸门 2 或扩大补全范围。现在写 T1 的修法是猜。

Phase 0 交付物仅两项：

1. **拒因分类**（D2）
2. **`error_counts` 单次记账**（D4）

部署后进入取样期，取满样本再按 D3 的预置规则分支。

### D2：落分类枚举，绝不落原始消息

在 `catch (err)` 中按 `err.message` 前缀映射到常量枚举，写入
`repair.reject_class`（结构化日志）与 `/status.tool_args_reject_classes`（计数）：

| 枚举值 | 匹配前缀 |
| --- | --- |
| `end_of_input` | `Unexpected end of JSON input` |
| `unterminated_string` | `Unterminated string in JSON` |
| `expected_comma_or_close` | `Expected ',' or '}'` / `Expected ',' or ']'` |
| `dialect_property_name` | `Expected property name or '}'` |
| `expected_quoted_name` | `Expected double-quoted property name` |
| `not_json` | `Unexpected token` |
| `other` | 以上均不匹配 |

同时记录 `args_len`（字节数，整数）。

**硬约束**：
- 不得写入 `err.message` 原文（`not_json` 一类内嵌 payload 摘录）
- 不得写入 `call.arguments` 的任何片段，包括首尾字符
- `args_len` 是唯一允许的定量字段

门禁：`test_observability.py` 新增用例——构造含 canary 的坏 tool args，
断言 stderr 全文不含 canary，且 `reject_class` 被正确分类。

### D3：预先承诺的分支规则（取样满足后按此执行，不得事后择优）

取样门槛：**≥ 10 次不同 `request_id` 的 `tool_args_malformed` 失败**。
按当前 3.7% 的失败率与观测到的流量，约需 270 个请求。

| 主导类别（占比 ≥ 60%） | 分支 | 动作 |
| --- | --- | --- |
| `expected_comma_or_close` | **A** | 闸门 2 当前已接受此类中的可闭合形态，却仍被拒 → 说明闭合后 `JSON.parse` 二次失败（截断数字、未转义引号）。收紧而非放宽：在闭合后增加"末值完整性"检查，并把该类计入不可补，**不扩大补全** |
| `dialect_property_name` / `expected_quoted_name` | **B** | 方言问题。新增**方言归一化层**（单引号→双引号、未加引号的 key 补引号），归一化后**仍须走完整三道闸门 + schema 校验**。归一化层单独计量 `tool_args_normalized` |
| `end_of_input` / `unterminated_string` | **C** | 值真缺，补全在原理上无解。T1 关闭，写入 Known limitations，改为优化失败文案（明确告知是上游工具参数格式问题，建议重试），并评估 `tool_choice`/提示词侧规避 |
| `not_json` | **D** | 上游返回的根本不是 JSON。属上游契约问题，升级为独立议题，不在本 PRD 范围内解决 |
| 无类别达 60% | **E** | 混合形态。按占比最高的两类各自执行对应分支，但**总补全率目标不设**，以"不引入静默错误"优先 |

**规则先于数据落纸，取样后照表执行。** 事后调整分支归属需在 PRD 中留修订记录并说明理由。

### D4：`error_counts` 单次记账

- 移除 `server.js:494` `onTimeout` 回调中的 `recordError`，只保留终态路径
  （`server.js:859`）——`onTimeout` 仍负责 `sendSseError` 与 `cleanup`
- 或将 `recordError` 改为按 `requestId` 去重（幂等记账），二选一，推荐前者（更少状态）
- 门禁：`test_observability.py` 新增——单个失败请求跑完后，
  `error_counts` 中该 code 计数必须**恰好为 1**，`recent_errors` 中该 `request_id`
  **恰好出现一次**。修复前该用例必须 FAIL（当前为 2）

### D5：不采用

- 不放宽"补全结果不得为 `{}`"的契约
- 不对坏 JSON 做重试（副作用风险，且上游是同一模型）
- 不因 U1 回退 T1（正向用例有效，闸门设计正确，问题是覆盖面而非正确性）
- 不在取样满足前改动闸门 2
- 不用 `err.message` 原文入日志

## 3. 验收标准

### Phase 0（本轮实施）

1. **D2 分类门**：7 个枚举各有一条用例，输入 → `reject_class` 映射正确。
2. **D2 泄漏门**：含 canary 的坏 tool args → stderr 不含 canary，
   且 `reject_class == "not_json"` 或对应类别被正确记录。修复前该用例不存在，
   新增后必须对当前实现跑通。
3. **D4 记账门**：单失败请求 → `error_counts[code] == 1` 且
   `recent_errors` 中该 request_id 出现 1 次。**修复前必须 FAIL（当前为 2）**，
   修复后 PASS，双向证据留存。
4. **回归**：`make verify-offline` 全绿，总数 ≥ 673 + 新增用例数。
5. **运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；MainPID 变化；`/status` 可达。

### Phase 1（取样后，分支确定再执行）

6. **取样充分性**：累计 ≥ 10 次不同 `request_id` 的 `tool_args_malformed`，
   给出 `reject_class` 分布表（含各类计数与占比）。
7. **分支执行**：按 D3 表格照章执行，分支对应的验收标准在分支确定后补入本 PRD §3。
8. **不变量**：无论走哪个分支，`tests/test_adapter_contract.py:221`
   （`tool_malformed` 不得降级成 `{}`）必须保持绿。

### Phase 2（窗口）

9. **观察窗**：以 Phase 1 部署时刻为起点满 24h，在
   `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计，
   新增为 0。不得收窄口径，不得用文本 grep。
10. **容量观察**：≥ 6h，`ss -tnp | grep :3000` 为空时采样 `/status` 至少 3 次，
    `active_requests` 必须为 0。
11. **补全率**：`tool_args_repaired / 总 tool 调用数`，按 D4 修正后的口径统计。
    > 5% 记为上游质量发现，需单独结论。
12. **`make verify-live`** 7 道 gate 全绿；真实 HOME（`~/.claude/`）未被改动。

## 4. 实施顺序

1. D4 记账门先跑出 FAIL（钉死双计）→ 移除 `onTimeout` 中的 `recordError` → 转 PASS
2. D2 分类枚举 + 泄漏门 + 分类门
3. `make verify-offline` 重取基线 → 部署 → §3.5 运行态三项核对
4. 进入取样期，直到 §3.6 的 10 次门槛达成
5. 按 D3 表格确定分支，把该分支的验收补进本 PRD §3，再实施
6. Phase 2 双窗口并行计时
7. 全部达标 → v1.1 release notes → 发布/关闭决定

## 5. 关闭条件

§3 全部 12 项达标前，**不关闭项目**。

三条不得走捷径的：

- **§3.3 必须先 FAIL**。`error_counts` 双计是当前可观测的既成事实，
  改完直接绿说明门禁没打在缺陷上。
- **D3 的分支规则先于数据落纸**。取样结果出来后照表执行；
  如果发现规则不合适，改规则要留修订记录，不能默默换一个更好写的分支。
- **U1 的性质要说清楚**。T1 不是"修好了但没触发"，是**对真实故障零命中**。
  在 Phase 1 落地并观察到 `tool_args_repaired > 0` 之前，
  release notes 里不得声称"坏 JSON 已支持补全"——只能说"补全层已上线，
  覆盖截断类形态"。
