# PRD：发布收口 v5（工具调用分片聚合键缺陷）

状态：D1-D3 已落地（聚合键修复 + 反向门 + 诊断字段），待部署 + 取样期
前置：
- `docs/PRD_RELEASE_CLOSURE_V4.md`（Phase 0 已交付并部署，commit `7c0af42`）
- `docs/PRD_RELEASE_CLOSURE_V3.md`（T1–T4 已交付，commit `eb4336c`）

核查时间：2026-08-22 10:45 CST，核查人：独立复验（非实施方自评）

## 0. 产品摘要

**V4 Phase 0 已核销，独立复验通过：**

| 项 | 独立验证证据 |
| --- | --- |
| U3 双计修正 | 隔离台架单失败请求 → `error_counts: {MAAS_STREAM_PROTOCOL: 1}`（修复前为 2） |
| U2 拒因分类 | 三种形态分别落 `end_of_input` / `unterminated_string` / `expected_comma_or_close`，`args_len` 齐全 |
| 不泄漏原文 | 日志中无 `err.message` 原文、无 payload 摘录 |
| 记账上界 | `_recordedErrors` 有 1000/500 上界，无无界增长 |
| 部署新鲜度 | SHA 一致 / MainPID 319428 / `/status` 新字段齐全 |

**但取样期刚开始，第一条生产样本就推翻了取样的前提。**

第一条真实失败的 `reject_class` 是 `not_json`。顺着这个线索做 A/B，
发现坏 JSON **不是上游发来的，是适配器自己拼出来的**。

## 1. 缺口

### V1 — 工具调用分片聚合键错误，`index` 缺失即毁掉整个工具调用（P0，发布阻塞）

`adapter/server.js:747`：

    const k = call.index ?? toolCalls.size;

OpenAI 流式协议中，一个工具调用的 `arguments` 会分多个 chunk 送达。
当上游**省略 `index`** 时，回落值 `toolCalls.size` 会随着分片写入不断增长：

    分片 1  '{"city"'    → k = size = 0  → 存入，size 变 1
    分片 2  ': "Beij'    → k = size = 1  → 存入，size 变 2
    分片 3  'ing"}'      → k = size = 2  → 存入，size 变 3

一个工具调用被拆成 **3 个独立的"工具调用"**，每个持有一段 JSON 碎片，
随后逐个 `JSON.parse` 失败 → `protocolError` → `MAAS_STREAM_PROTOCOL`。

**A/B 证据**（同一份上游内容，唯一变量是 delta 里带不带 `index`，
探针 `/root/ping-probe/frag_upstream.js` + `fragtest.py`）：

    WITH_INDEX=1  →  error frames 0，tool_use 块 1 个，{"city":"Beijing"} 正确组装
    WITH_INDEX=0  →  error frames 1，tool_use 块 0 个，
                     error_counts {MAAS_STREAM_PROTOCOL: 1}
                     reject_class "other"，protocol_error_reason "tool_args_malformed"

碎片形态与生产样本吻合：`ing"}` → `Unexpected token 'i'` → `not_json`；
`, "unit": "C"}` → `Unexpected token ','` → `not_json`；
`"city": "Beijing"` → `Unexpected non-whitespace character after JSON` → `other`。
生产观测到的 `not_json` 与本地复现的 `other` 属同一机制的不同分片边界。

**尚未证实的一环**：本 A/B 证明"上游省略 `index` 时适配器会自毁"，
**没有**证明线上 MaaS 确实省略了 `index`。这一步必须补证——见 D3。

### V2 — T1 补全层建在错误的层上（P1）

若 V1 成立，T1 的三道闸门一直在尝试修复**适配器自己拼坏的字符串**。
这解释了 V3/V4 观测到的两个现象：

- `tool_args_repaired = 0`：碎片不是"截断的完整 JSON"，任何闭合策略都救不回来
- 失败集中在闸门 2：碎片以 `ing"}` / `, "unit"` 这类非 JSON 开头的片段呈现

T1 的闸门设计本身没有错（正向用例 `tool_truncated_closeable` 有效），
但它解决的问题在生产上可能根本不存在。

### V3 — 现有测试全部提供 `index`，从未覆盖缺失路径（P1）

`tests/helpers/fake_upstream.js` 的 `tool_valid` / `tool_malformed` /
`tool_truncated_*` / `tool_oversized` 全部在 delta 中显式给出 `index: 0`。
680 条用例中**没有一条**走 `call.index === undefined` 的回落分支。

这是本仓库门禁盲区的又一形态：**回落分支从未被执行过**。
与 V2 的 reaper（交付后从未触发）同类。

### V4 — V4 PRD 的取样规则前提失效（P1）

`PRD_RELEASE_CLOSURE_V4.md` §D3 的分支表建立在"坏 JSON 来自上游"这一前提上，
分支 A–E 全部是"如何扩展补全能力"。若 V1 成立，正确动作是修聚合键，
而不是在分支表里挑一个。该表需要修订，取样门槛需要重新定义。

## 2. 决策

### D1：按 OpenAI 流式语义修正聚合键

新工具调用的标志是 **`id` 或 `function.name` 出现**；只带 `arguments` 的 delta
是对**当前工具调用**的续写。

    // 新调用：显式 index，或出现 id / name
    // 续写：无 index 且无 id/name → 归入当前打开的调用
    let k;
    if (call.index !== undefined && call.index !== null) {
      k = call.index;
    } else if (call.id || call.function?.name) {
      k = toolCalls.size;              // 新调用开始
    } else {
      k = currentToolKey;              // 续写当前调用
    }

`currentToolKey` 在每次确定 `k` 后更新。禁止继续使用"`toolCalls.size` 作为
续写键"这一语义——它把"已有多少个调用"当成了"当前是第几个调用"。

### D2：反向门（修复前必须失败）

`tests/helpers/fake_upstream.js` 新增两个场景：

- `tool_fragments_no_index`：一个工具调用，`arguments` 分 3 片，delta 中**不带** `index`，
  末尾 `finish_reason: tool_calls`
- `tool_two_calls_no_index`：两个工具调用，各自首片带 `id` + `name`，后续片只带 `arguments`，
  全程不带 `index`

断言：

1. 客户端收到 `tool_use` 块数量正确（1 / 2），`input` 完整等于
   `{"city":"Beijing"}`（及第二个调用的参数）
2. `error_counts` 为空，`tool_args_reject_classes` 为空
3. **修复前两条用例必须 FAIL**（当前实测：0 个 tool_use 块 + 1 个 error 帧），
   修复后 PASS，双向证据留存

### D3：补证线上上游是否省略 `index`（与 D1 同批上线）

结构化日志的 `repair` 字段之外，新增请求级字段：

    tool_call_index_absent: <bool>   // 本请求是否出现过 index 缺失的 tool_calls delta
    tool_call_fragments:    <int>    // 收到的 tool_calls delta 分片总数

**这是把 V1 从"本地可复现的缺陷"升级为"线上根因"的唯一手段。**
在观察到 `tool_call_index_absent: true` 出现在真实失败请求上之前，
V1 只能表述为"适配器存在的缺陷"，不得表述为"线上故障的根因"。

若线上始终为 `false`，说明还有第二条产生坏 JSON 的路径，V1 修复照做，
但根因分析需重新开展。

### D4：修订 V4 的取样规则

- V4 §D3 的分支表**挂起**，不在 V1 修复与 D3 补证完成前执行
- V1 修复部署后重新开始取样。若 `tool_args_malformed` 归零，
  T1 降级为纯安全网（保留，不扩展）
- V4 §3.6 的"≥10 次失败"门槛相应改为：修复后窗口内
  `tool_args_malformed` **累计为 0**；若仍非 0，再按修订后的分支表处理

### D5：不采用

- 不因 V2 移除 T1。闸门设计正确、正向用例有效，作为安全网保留
- 不放宽"补全结果不得为 `{}`"的契约
- 不用补全层去兜 V1（那是用一个层的缺陷去掩盖另一个层的缺陷）
- release notes 在 `tool_args_repaired > 0` 出现前，不得声称"支持坏 JSON 补全"

## 3. 验收标准

1. **D2 反向门**：两条新用例修复前 FAIL、修复后 PASS，双向证据留存。
2. **不变量**：`tests/test_adapter_contract.py:221`（`tool_malformed` 不得降级成 `{}`）
   保持绿；`tool_valid` 等既有工具用例全绿。
3. **D3 补证**：线上出现至少一次带 `tool_call_index_absent` 判定的工具调用请求，
   并据此给出"V1 是否为线上根因"的明确结论。
4. **回归**：`make verify-offline` 全绿，总数 ≥ 680 + 新增用例数。
5. **运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；MainPID 变化；`/status` 可达。
6. **观察窗**：以本轮部署为起点满 24h，在 `/root/.claude-maas/projects/` 下按
   `isApiErrorMessage === true` **全量**统计，新增为 0。
7. **工具调用健康度**：窗口内 `tool_args_malformed` 累计为 0；
   若非 0，给出 `reject_class` 分布并按 D4 处理。
8. **容量观察**：≥ 6h，`ss -tnp | grep :3000` 为空时采样 `/status` 至少 3 次，
   `active_requests` 必须为 0。
9. `make verify-live` 7 道 gate 全绿；真实 HOME（`~/.claude/`）未被改动。

## 4. 实施顺序

1. D2 两条反向门先写 → 对当前实现跑出 FAIL（钉死 V1）
2. D1 修聚合键 → 同一门禁转 PASS
3. D3 两个日志字段
4. `make verify-offline` 重取基线 → 部署 → §3.5 运行态三项核对
5. D3 补证：观察线上 `tool_call_index_absent` 的真实取值，给出根因结论
6. §3.6 / §3.7 / §3.8 三个窗口并行计时
7. 全部达标 → v1.1 release notes → 发布/关闭决定

## 5. 关闭条件

§3 全部 9 项达标前，**不关闭项目**。

三条不得走捷径的：

- **§3.1 必须先 FAIL**。当前实测 `WITH_INDEX=0` 下 0 个 tool_use 块 + 1 个 error 帧，
  这是既成事实；新用例若一上来就绿，说明它没打在缺陷上。
- **§3.3 是根因结论的唯一依据**。本地 A/B 只证明了"适配器在 `index` 缺失时自毁"，
  没有证明"线上上游省略了 `index`"。没有 D3 的日志证据，
  V1 只能写成"修复了一个适配器缺陷"，不能写成"修复了线上故障根因"。
- **V2 的表述纪律**。T1 至今 `tool_args_repaired = 0`。
  在生产观察到非零之前，任何文档中都不得声称补全层"在工作"——
  它只是"已上线且未被触发"。
