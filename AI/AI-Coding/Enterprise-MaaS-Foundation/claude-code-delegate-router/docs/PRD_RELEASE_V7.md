# PRD：发布收口 v7（采纳 litellm-auto-plugin 的两层解法）

状态：X1-X4 + V6 D1 已落地，待部署（observe 模式）+ 取样期
前置：
- `docs/PRD_RELEASE_CLOSURE_V6.md`（诊断补全，待实施）
- `docs/PRD_RELEASE_CLOSURE_V5.md`（V1/D2/D3 已交付，commit `86e15c0`）

参考实现：`/root/litellm-auto-plugin`
（`litellm_plugins/anthropic_stream_guard/callback.py`、
`litellm_plugins/tool_argument_guard/callback.py`）

核查时间：2026-08-22 19:50 CST

**范围变更声明**：上一轮的约束是"不再新增功能"。本 PRD **突破了该约束**——
因为参考实现给出的关键手段（安全降级）是行为变更，不是诊断。
若不接受该变更，本项目只能以 9.0% 的硬失败率发布，或无限期停留在根因排查中。
这个取舍需要显式确认。

## 0. 摘要

**同一问题在 `litellm-auto-plugin` 存在，且已有成熟解法。** 同一模型（GLM on
Huawei MaaS）、同一类故障（工具参数非 JSON / 原始工具标记）。

参考实现的分层：

| 层 | 组件 | 做法 |
| --- | --- | --- |
| 协议层 | `anthropic_stream_guard` | `TOOL_MARKUP_PREFIX = b"<tool_call"`；检测到原始标记**不改写**，计数 `asg_unparsed_tool_markup_total`，抛具名错误 `UnparsedToolMarkupError` → HTTP 502 `UNPARSED_TOOL_MARKUP` |
| 语义层 | `tool_argument_guard` | 缓冲整个 tool call → 用请求内 `input_schema` 验证 → 确定性归一化白名单 → Premium 侧车修一次 → 用**原** schema 复验 → 仍失败则替换为安全文本块、干净结束该轮、**不执行工具** |

灰度：`TOOL_ARG_GUARD_MODE = off | observe | enforce`，默认 `observe`。

**与 ccdr 最关键的差异是最后一步。** ccdr 现状：坏 args → `protocolError` →
整条流失败 → 用户看到 `API Error: stream protocol error`，该轮硬中断。
参考实现：修不好 → 替换为可读文本 → 该轮干净结束 → 会话继续。

**这一步不依赖根因定位**，可以把 9.0% 的硬中断转成 9.0% 的软降级。

### 对 V6 假设的旁证

`<tool_call>` + `</tool_call>` = 23 字节外壳。ccdr 实测坏 args 为
**39 / 41 字节**、确定性重复、`reject_class: not_json`（首 token 非法）：

    23 + 16 = 39      23 + 18 = 41

高度吻合，但仍是假设。V6 §D1 的 `first_char_code` 一个整数即可确认（`0x3C` = `<`）。

> **修订记录（2026-08-23，V11 D1）：此旁证已被实测推翻。**
> `enforce` 窗口内观测到的真实降级（`b5117fa4`）为
> `first_char_code: 0x7B`（`{`）、`reject_class: unterminated_string`、
> `is_markup: false`、`args_len: 433`——参数以合法 JSON 对象开头，
> 在字符串中途被截断，**不是** `<tool_call` 标记包装。
>
> 上述 23 字节外壳的吻合是巧合：历史簇（`not_json`，`args_len ∈ {39, 41}`）
> 的 `first_char_code` 从未被采集（诊断字段上线前发生），无法确认其首字符。
> 本次观测的是**另一种形态**，两者不是同一根因。
>
> 从 `litellm-auto-plugin` 的 `<tool_call` 标记类比给出了正确的**架构**方向
> （安全降级），但错误的**形态**判断。类比结论不得作为根因依据。
> 详见 `docs/PRD_RELEASE_V11.md` §B1。

## 1. 采纳项

### X1 — 安全降级：坏工具参数不得再终止整条流（P0，发布前置）

现状（`adapter/server.js:824/828`）：`ctrl._setProtocolError("tool_args_malformed")`
→ `break` → `finalize()` → `_fail(STREAM_PROTOCOL)` → 客户端收到 `event: error`，
该轮内容全部作废。

改为：工具参数不可用时，**该工具块替换为一个 text 块**，内容为固定的安全文案，
随后正常发 `content_block_stop` / `message_delta` / `message_stop`，
`stop_reason: end_turn`。**不执行任何工具**，不伪造 `input`。

安全文案（照搬参考实现语义，中文化）：

    所请求的工具调用未被执行：模型生成的参数不符合该工具的接口约定。
    可以用修正后的参数重试。

不变量：
- 绝不用 `{}` 或任何编造的参数执行工具（`test_adapter_contract.py:221` 的契约在此
  语义下继续成立——不是"降级成 `{}`"，是"不执行 + 明示"）
- 已发出的 text/thinking 块保留，不回收
- `protocol_error_reason` 仍写 `tool_args_malformed`，便于统计

### X2 — 具名分类：把"原始工具标记"和"坏 JSON"分开（P1）

参考实现把 `<tool_call` 单列为 `UNPARSED_TOOL_MARKUP`，与一般的参数格式错误区分。
ccdr 采纳同一区分：

- 新增 `protocol_error_reason: "tool_markup_as_args"`，在 `arguments` 以
  `<tool_call` 开头时使用
- `/status` 增加 `tool_markup_seen` 计数
- **不改写、不剥壳**（参考实现明确"NOT rewrite improvised markup"）——
  剥壳是猜测模型意图，属 X3 的归一化范畴，需 schema 复验背书

### X3 — 确定性归一化白名单，替代通用括号闭合（P1）

T1 现有的三道闸门是**语法**层面的（闭合括号）。参考实现的归一化是**schema 导向**的，
逐条可解释、幂等、且每条都用原 schema 复验。ccdr 采纳其中与本场景相关且不引入
新依赖的子集：

| 规则 | 语义 | 采纳 |
| --- | --- | --- |
| R1-wrapper | `{"input": {...}}` 且 `input` 是唯一字段、内层过原 schema → 解包 | 采纳 |
| R5-remove-unknown | 移除 schema 未声明且 `additionalProperties: false` 的字段 | 采纳 |
| R6-null-empty | schema 允许空对象时 `null` → `{}` | 采纳 |
| R2-snake-camel / R3-primitive-coerce / R4-schema-defaults | 需要更完整的 schema 遍历 | 暂不采纳，留待根因定性后评估 |
| RT-* 工具特定规则 | 与 ccdr 工具集不对应 | 不采纳 |

**每条规则应用后必须用原 schema 复验**，复验不过则回退到未归一化的输入并走 X1 降级。
T1 的三道闸门保留在归一化之前（语法闭合仍是有效的第一步）。

### X4 — 三态灰度

`MAAS_TOOL_ARG_MODE = off | observe | enforce`，默认 **`observe`**：

- `off`：完全关闭（等同当前行为，硬失败）
- `observe`：走完整判定链并记录全部指标，但**最终仍按当前行为硬失败**——
  用于在不改变用户可见行为的前提下积累数据
- `enforce`：启用 X1 安全降级与 X3 归一化

上线顺序：先 `observe` 跑满一个窗口拿到分布，再切 `enforce`。

## 2. 不采纳项

| 参考实现的做法 | 不采纳理由 |
| --- | --- |
| Premium 侧车修复（换更强模型修参数） | ccdr 是单进程直连回环代理，引入第二个模型端点会破坏其核心卖点（单跳、无代理链），且与 `PRD.md` 的禁用依赖扫描冲突 |
| `jsonschema` 库做完整 Draft7 校验 | ccdr 是 Node 且刻意零第三方依赖（`scripts/check-prohibited-dependencies.py`）。继续用现有的 `validateAgainstSchema`（`required` + 顶层类型），不做完整校验 |
| Prometheus 指标 | ccdr 用 `/status` + 结构化日志，不引入 metrics 端点 |
| HTTP 502 具名错误码 | ccdr 的失败路径走 SSE `event: error`，保持现有错误码体系，仅增加 `protocol_error_reason` 取值 |

## 3. 验收标准

1. **X1 降级门（正向）**：`tool_malformed` 场景在 `enforce` 模式下 →
   客户端收到 0 个 `event: error`、1 个 text 块含安全文案、
   `message_stop` 正常、`stop_reason: end_turn`。
2. **X1 降级门（反向/不变量）**：同场景下**没有任何 `tool_use` 块**被发出，
   `input` 从未出现 `{}`。`test_adapter_contract.py:221` 保持绿
   （其断言应改为"不得发出 tool_use 块"，语义等价且更强）。
3. **X1 `observe` 门**：同场景在 `observe` 模式下行为与当前完全一致
   （1 个 `event: error`，无 text 降级块）——证明灰度开关真实有效。
4. **X2 分类门**：`arguments` 以 `<tool_call` 开头 →
   `protocol_error_reason: "tool_markup_as_args"`，`tool_markup_seen` 递增；
   普通坏 JSON 仍为 `tool_args_malformed`。两者不得混淆。
5. **X3 规则门**：R1/R5/R6 各一条正向用例 + 一条"复验不过则回退"的反向用例。
   每条规则修复前 FAIL、修复后 PASS。
6. **V6 诊断**：`first_char_code` 等字段先于本 PRD 或与之同批上线，
   并给出线上 `first_char_code` 分布，确认或推翻 `0x3C` 假设。
7. **回归**：`make verify-offline` 全绿，总数 ≥ 682 + 新增用例数。
8. **运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；MainPID 变化；`/status` 可达。

## 4. 发布判据（本 PRD 的核心）

发布**不再要求根因清零**，改为要求"失败可控且可解释"。三条同时成立方可发布：

1. **硬失败清零**：`enforce` 模式部署后满 24h，在
   `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计，
   `stream protocol error` 新增为 **0**。
   （降级路径不产生 API Error，因此这一条是可达的。）
2. **降级率可见且有上界**：窗口内
   `tool_args_malformed / request_end` 有明确数值并写入 release notes 的
   Known limitations。当前基线 9.0%。**若 enforce 后该值 > 12%（基线 +3pp），
   视为降级掩盖了新问题，阻塞发布。**
3. **根因有归属**：`first_char_code` 分布给出明确结论，
   写入 Known limitations 并指明后续动作（本项目内解决 / 上游议题 / 提示词侧规避）。
   **允许"已定位未修复"，不允许"未定位"。**

以及沿用前序 PRD 的运行态条件：

4. 容量观察 ≥ 6h，`ss -tnp | grep :3000` 为空时 `active_requests` 为 0（采样 ≥3 次）
5. `make verify-live` 7 道 gate 全绿；真实 HOME（`~/.claude/`）未被改动

## 5. 实施顺序

1. V6 §D1 的诊断字段（`first_char_code` 等）——不阻塞后续，但越早越好
2. X4 三态开关（先落开关，默认 `observe`）
3. X1 安全降级 + §3.1/§3.2/§3.3 三条门禁
4. X2 具名分类 + §3.4
5. X3 归一化白名单 R1/R5/R6 + §3.5
6. `make verify-offline` 重取基线 → 部署（`observe`）→ §3.8 运行态核对
7. `observe` 窗口取样 → 确认 `first_char_code` 分布与降级率基线
8. 切 `enforce` → 启动 §4.1 的 24h 窗口 + §4.4 的 6h 容量观察
9. §4 五条全部成立 → v1.1 release notes → **发布**

## 6. 表述纪律（沿用并补充）

- **T1**：`tool_args_repaired` 至今为 0。在生产观察到非零前，不得声称补全层"在工作"
- **V1**：`tool_call_index_absent` 线上恒为 `false`，不得把 V1 写成
  "修复了 stream protocol error"
- **X1**：安全降级是**把硬失败换成软失败**，不是修复。release notes 必须写明
  降级率，不得只写"已修复 stream protocol error"
- **X3**：归一化规则每一条都要能用一句话解释它为什么不改变语义。
  解释不出来的规则不得进白名单
