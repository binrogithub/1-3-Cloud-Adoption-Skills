# PRD：发布收口 v6（线上根因定位 —— V1 被证否）

状态：D1 诊断字段已落地（与 V7 同批，commit 待提交）
前置：
- `docs/PRD_RELEASE_CLOSURE_V5.md`（V1/D2/D3 已交付并部署，commit `86e15c0`）
- `docs/PRD_RELEASE_CLOSURE_V4.md`（Phase 0 已交付，commit `7c0af42`）

核查时间：2026-08-22 19:40 CST，核查人：独立复验（非实施方自评）

**本轮不新增任何功能。** 全部内容是把根因问题收口，以及给出发布决定所需的证据。

## 0. 产品摘要

**V5 交付的三项已核销，独立复验通过：**

| 项 | 独立验证证据 |
| --- | --- |
| V1 聚合键修复 | `WITH_INDEX=0`：修复前 0 个 tool_use 块 + 1 个 error 帧 → 修复后 1 个 tool_use 块、`{"city":"Beijing"}` 正确组装、0 个 error 帧 |
| 对照未回归 | `WITH_INDEX=1` 仍正常，`tool_call_index_absent: false` |
| 不变量 | `tool_malformed`（`{"city":`）仍然失败，`reject_class: end_of_input` |
| D3 诊断字段 | `tool_call_index_absent` / `tool_call_fragments` 均正确落盘 |
| 部署新鲜度 | SHA 一致 / MainPID 401276 / `/status` 可达 |

**但 D3 的补证给出了否定结论：V1 不是线上根因。**

V5 §D3 预设了这个分支：「若线上始终为 `false`，说明还有第二条产生坏 JSON 的路径，
根因分析需重新开展。」现在这个分支被触发了。

## 1. 缺口

### W1 — 线上根因未定位，V1 被证否（P0，发布阻塞）

新构建部署后的首个真实失败请求：

    {"request_id":"964fda70-...","error_code":"MAAS_STREAM_PROTOCOL",
     "protocol_error_reason":"tool_args_malformed",
     "tool_call_index_absent": false,          ← 上游确实发了 index
     "tool_call_fragments": 8,
     "repair":{"gate":"gate2_struct","reject_class":"not_json","args_len":39}}

同窗口全部 10 条 `request_end` 中，`tool_call_index_absent` **无一为 true**。

结论：上游 MaaS **正常发送 `index`**，V1 描述的分片错拆路径在生产上从未发生。
V1 修复的是一个真实存在但线上未触发的适配器缺陷（回落分支从未被执行过，
与 V2 的 reaper 同类），**不是**故障根因。

### W2 — 真实失败率 9%，不具备发布条件（P0，发布阻塞）

`7c0af42` 窗口（2026-08-22 10:39:43 → 19:35:23，8.9 小时）：

    request_end 总数        133
    tool_args_malformed     12   （去重后 12 个不同 request_id）
    reject_class 分布       not_json  12 / 12   =  100%
    →  失败率 9.0%

这是稳定、单一形态、高频的失败。每一次对用户都是一条
`API Error: stream protocol error`，当前轮次直接中断。

**新增线索（本轮核查发现）**：`args_len` 只有两个取值——

    args_len = 39   ×8
    args_len = 41   ×4
    （新构建窗口内的那次也是 39）

坏数据是**重复的、确定性的**，不是随机截断或随机损坏。
这强烈提示存在一个固定的包装/前缀（例如模型输出的标记文本），
而不是"模型偶尔吐坏 JSON"。

> **修订记录（2026-08-23，V11 D1）**：上述"固定包装/前缀"推断及
> 下文 D2 判定表中 `0x3C`（`<`）分支的假设**已被实测推翻**。
> `enforce` 窗口内观测到的真实降级（`b5117fa4`）为
> `first_char_code: 0x7B`（`{`）、`reject_class: unterminated_string`、
> `is_markup: false`、`args_len: 433`——参数以合法 JSON 对象开头，
> 在字符串中途被截断，而上游同时给出了干净的 `finish_reason`。
> 早期从 `litellm-auto-plugin` 的 `<tool_call` 标记类比得出的形态假设
> **不成立**。类比给对了架构方向（安全降级），给错了形态判断。
> 详见 `docs/PRD_RELEASE_V11.md` §B1/§B2。

### W3 — 诊断能力到达上限，现有字段无法定位形态（P1，发布阻塞）

`reject_class: not_json` 对应 `JSON.parse` 抛出 `Unexpected token 'X', "..."`，
只说明**首个有效 token 非法**，不说明是什么。

配合 `args_len ∈ {39, 41}` 已能判定"确定性重复"，但仍不足以区分：

- 以 `<` 开头的标记包装（如 `<tool_call>` 之类）
- 以字母开头的裸文本（如 `函数名(参数)` 形式）
- 以 `'` 开头的方言
- 以其他控制字符/BOM 开头

V4 §D2 定的"绝不落原始消息"是对的——`not_json` 的消息内嵌 10 字符 payload 摘录。
但它把可用信息压得过狠，导致现在**看得见失败、看不见形态**。

## 2. 决策

### D1：最小形状诊断（诊断字段，无行为变更）

在 `repair` 字段中补三个**纯结构**指标，不落任何 payload 字符：

    first_char_code:  <int>   // 首个非空白字符的 Unicode 码点（单个整数）
    char_class_counts: { brace_open, brace_close, bracket_open, bracket_close,
                         double_quote, single_quote, backslash, lt, gt }
    args_len:         <int>   // 已有

**为什么单个码点是可接受的**：它是一个整数，不是文本；无法从中还原参数内容；
而它恰好能一击区分上面四种形态（`0x3C` = `<`，`0x27` = `'`，字母区间，控制字符）。
`char_class_counts` 同理——只计数标点，不含标识符、数值、字符串内容。

**硬约束**（沿用 V4 §D2）：
- 不得落 `err.message` 原文
- 不得落 `call.arguments` 的任何字符（码点是数值，不是字符输出）
- 新增用例：含 canary 的坏 args → stderr 不含 canary，且三个新字段均正确

这是诊断补全，**不是功能新增**：不改变任何请求的处理结果，
`MAAS_TOOL_ARG_REPAIR` 关闭时同样记录。

### D2：判定表（先于数据落纸）

取样门槛：**≥ 5 次**带新字段的真实 `tool_args_malformed`
（当前失败率 9%，约需 55 个请求，按观测流量约 1–2 小时）。

| `first_char_code` 主导值 | 判定 | 动作 |
| --- | --- | --- |
| `0x3C`（`<`） | 模型输出标记包装 | 上游/提示词侧问题。评估在 `arguments` 进入聚合前剥离已知包装；**若需改代码，另起 PRD**，本轮只出结论 |
| `0x27`（`'`） | 单引号方言 | 走 V4 §D3 分支 B（方言归一化），另起 PRD |
| 字母区间（`0x41–0x7A`） | 裸文本/函数调用式 | 上游契约问题，另起 PRD |
| `0x7B`（`{`）但仍 `not_json` | 与推断矛盾 | 重新分析，本 PRD 修订 |
| `0x7B`（`{`）且 `unterminated_string` | **上游在参数未完整送达时给出了干净的 finish_reason** | **分支 C：值真缺，补全在原理上无解。** X1 安全降级覆盖，记为上游契约问题。不扩大补全能力。**（2026-08-23 实测命中，`b5117fa4`）** |
| 其他/无主导值 | 混合 | 按占比最高两类分别出结论 |

**规则先于数据。** 取样后照表执行，改表需留修订记录与理由。

> **修订记录（2026-08-23，V11 D1）**：`0x3C` 分支的假设已被实测推翻——
> 生产观测到的形态为 `0x7B` + `unterminated_string`（上表新增行），
> 非 `0x3C` + `not_json`。`0x3C` 行保留供参考，但不得作为当前根因结论。
> 历史簇（`not_json`，`args_len ∈ {39, 41}`）的 `first_char_code` 未采集，
> 形态待后续样本确认。

### D3：本轮不动任何处理逻辑

- T1 三道闸门：保留，不扩展。`tool_args_repaired` 至今为 0
- V1 聚合键修复：保留（真实缺陷，虽非线上根因）
- 不新增补全能力、不新增归一化层、不改闸门阈值
- 具体修复动作在 D2 判定结论出来后另起 PRD

### D4：若 D1 仍不足以定性 —— 受控抓取（默认关闭，需显式开启）

仅当 D2 取样后仍无法判定时启用：

- `MAAS_DEBUG_CAPTURE_ARGS=1` 环境变量，**默认关闭**，生产默认不设
- 开启后仅对 `tool_args_malformed` 失败请求写入 `args` 原文到
  `/var/log/claude-maas-debug/`（0600，root only），**不进 journald**
- 上限 10 条后自动停止；文件保留 24h 后由清理脚本删除
- 用完即关，并在 PRD 中记录开启/关闭时刻

不作为默认路径，仅作为 D1 失败时的兜底。

### D5：不采用

- 不因 W1 回退 V1（缺陷真实，回落分支需要正确实现）
- 不因 W2 放宽"补全结果不得为 `{}`"的契约
- 不用 T1 补全层去兜 W1（形态未知时扩大补全＝制造静默错误）
- 不在 D2 判定前改动任何处理逻辑
- **不因为"改动都做完了"而降低发布标准**——9% 的硬失败率本身就是发布阻塞

## 3. 验收标准

1. **D1 字段门**：四类构造输入（`<` 开头、`'` 开头、字母开头、`{` 开头但后续非法）
   → `first_char_code` 与 `char_class_counts` 均正确。
2. **D1 泄漏门**：含 canary 的坏 args → stderr 不含 canary，
   不含 `err.message` 原文，不含任何 args 字符。
3. **不变量**：`tests/test_adapter_contract.py:221`（`tool_malformed` 不得降级成 `{}`）
   保持绿；V5 的两条 `no_index` 用例保持绿。
4. **回归**：`make verify-offline` 全绿，总数 ≥ 682 + 新增用例数。
5. **运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；MainPID 变化；`/status` 可达。
6. **D2 取样**：≥ 5 次带新字段的真实失败，给出 `first_char_code` 分布表。
7. **根因结论**：按 D2 表格给出明确判定，写入本 PRD §6（新增章节）。
   结论必须是四类之一或"混合"，不得是"待观察"。
8. **观察窗**：根因修复（另起 PRD）部署后满 24h，在
   `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计，
   新增为 0。
9. **失败率**：修复后窗口内 `tool_args_malformed / request_end < 0.5%`。
   当前 9.0%，这是本项目的发布门槛，不得因"已定位根因"而豁免。
10. **容量观察**：≥ 6h，`ss -tnp | grep :3000` 为空时采样 `/status` 至少 3 次，
    `active_requests` 必须为 0。
11. `make verify-live` 7 道 gate 全绿；真实 HOME（`~/.claude/`）未被改动。

## 4. 实施顺序

1. D1 三个诊断字段 + §3.1/§3.2 两条门禁
2. `make verify-offline` 重取基线 → 部署 → §3.5 运行态三项核对
3. 取样至 §3.6 的 5 次门槛
4. 按 D2 表格给出 §3.7 的根因结论，写入 §6
5. 依结论另起 PRD 做实际修复（本 PRD 不含修复动作）
6. 修复部署后启动 §3.8 / §3.9 / §3.10 三个窗口
7. 全部达标 → v1.1 release notes → 发布/关闭决定

## 5. 关闭条件

§3 全部 11 项达标前，**不关闭项目**。

四条不得走捷径的：

- **§3.9 的 0.5% 是硬门槛**。当前 9.0% 的失败率意味着用户每 11 个请求就撞一次
  硬中断。"根因已定位"不等于"可以发布"，必须有修复后的实测失败率。
- **V1 的表述纪律**。V1 修复的是真实缺陷，但 `tool_call_index_absent` 线上恒为
  `false` 已证明它**不是线上根因**。release notes 与任何汇报中不得把 V1
  写成"修复了 stream protocol error"。
- **T1 的表述纪律（沿用 V5）**。`tool_args_repaired` 至今为 0，
  在生产观察到非零之前，不得声称补全层"在工作"。
- **§3.7 不接受"待观察"**。诊断字段上线后若仍无法判定，走 D4 受控抓取，
  而不是把结论悬置。根因不明就发布，等于把 9% 的失败率交给用户去发现。

## 6. 根因结论

**2026-08-23 更新（V11 D1）**：

`enforce` 窗口内观测到的真实降级（`b5117fa4`）落在 D2 判定表新增行：
`first_char_code: 0x7B`（`{`）、`reject_class: unterminated_string`、
`args_len: 433`、`is_markup: false`。

**结论：上游契约问题。** 上游在参数未完整送达时给出了
`finish_reason ∈ {tool_calls, stop}`，闸门 1 通过、闸门 2 以
`unterminated_string` 拒绝。属 D2 分支 C——闭合未终止的字符串会静默丢字符，
补全在原理上无解。X1 安全降级已覆盖。

早期从 `litellm-auto-plugin` 的 `<tool_call` 标记类比得出的 `0x3C` 假设
**已被实测推翻**（`first_char_code: 0x7B`，`is_markup: false`）。

历史簇（`not_json`，`args_len ∈ {39, 41}`，25 次）的 `first_char_code`
未采集（诊断字段上线前发生），形态待后续样本确认。两簇**不得合并**为一个
"坏 JSON"结论。
