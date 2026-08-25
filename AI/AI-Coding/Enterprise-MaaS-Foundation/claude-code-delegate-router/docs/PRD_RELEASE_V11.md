# PRD：根因表述更正与发布收尾（v11）

状态：D1 已实施，待 §3.2 verify-live + §3.7 窗口届满
前置：`docs/PRD_RELEASE_V10.md`（测试隔离已交付 `1e5c58c`）、
`docs/PRD_RELEASE_V9.md`（判据补全）、`docs/PRD_RELEASE_V8.md`（`enforce` 生效 `dacfb75`）

核查时间：2026-08-23 04:10 CST，核查人：独立复验（非实施方自评）
实施时间：2026-08-23，实施人：Claude（OAuth session）

## 0. 摘要

**V10 已核销，且窗口内出现了第一次真实降级——X1 在生产上首次生效。**

| 项 | 证据 |
| --- | --- |
| V10 隔离生效 | `tests/conftest.py` autouse 设 `ENV_FILE` 指向空文件；`test_env_isolation.py` 已建 |
| **生产配置未被迁就** | `/etc/claude-code-proxy/maas.env` 中 `MAAS_TOOL_ARG_MODE=enforce` **保持不变**（V10 §3.2 的关键条件） |
| **窗口完整** | `/opt` 与仓库 `server.js` SHA 仍为 `7edc1ae0…`；MainPID 仍为 509396；`ActiveEnterTimestamp` 仍为 01:50:47 —— 未产生新制品、未重启。**（M9 注：此为核查时快照，该窗口后被 V1/V2 部署打断，当前窗口见 §3.7）** |
| 工作树 | `git status` 干净；`git tag` 仅 `v1.0`，未提前打标 |

**窗口内首次降级（`b5117fa4`）**：

    state: completed        degraded: true       硬失败: 0
    repair.mode: "enforce"  gate: gate2_struct   is_markup: false
    reject_class: "unterminated_string"          args_len: 433
    first_char_code: 123 (= "{")
    char_class_counts: brace_open 1 / brace_close 0 / double_quote 24 / backslash 16

三个结论，逐条都改变了此前的记载。

## 1. 缺口

### B1 — `<tool_call` 标记假设被推翻（P1，文档更正）

V6 §0、V7 §0、v1.1 release notes 的 Known limitations 都记录了同一个假设：

> 形态特征为 `args_len ∈ {39, 41}`、`not_json`，提示固定包装/前缀，
> 假设 `first_char_code = 0x3C`（`<tool_call`）

实测 `first_char_code: 123`（`0x7B` = `{`）、`is_markup: false`。
**参数以合法 JSON 对象开头，不是标记包装。** 假设推翻。

这个假设当初是从 `litellm-auto-plugin` 的 `TOOL_MARKUP_PREFIX = b"<tool_call"`
类比来的。类比给了正确的**架构**方向（安全降级），但给错了**形态**判断。
文档必须更正，否则后续维护者会照着一个已被证否的线索排查。

### B2 — 至少两种失败形态，新形态 n=1（P1）

| 形态 | 样本 | `args_len` | `reject_class` | 首字符 |
| --- | --- | --- | --- | --- |
| 历史簇 | 12 次（`7c0af42` 窗口）+ 13 次（`86e15c0` 窗口） | 39 / 41 | `not_json` | 未记录（诊断字段当时未上线） |
| 本次 | 1 次（当前窗口） | 433 | `unterminated_string` | `{` |

两者**不是同一形态**。历史簇短、确定性重复、首 token 非法；本次长、
以 `{` 开头、在字符串中途截断。

本次形态的性质是**上游在给出干净 finish_reason 的同时截断了参数**——
闸门 1（要求 `finishReason ∈ {tool_use, end_turn}`）**通过了**，
才轮到闸门 2 以 `unterminated_string` 拒绝。即上游声称"说完了"，
但参数在字符串中间就没了。

按 V6 §D2 的判定表，`unterminated_string` 属**分支 C**：值真缺，
补全在原理上无解——闭合引号会静默丢字符，比失败更糟。

### B3 — 窗口与容量观察均未届满（P0，纯时间）

    24h 窗口      01:50:47 → 2026-08-24 01:50:47    已过 2h19m
    6h 容量观察   01:50:47 → 2026-08-23 07:50:47    已过 2h19m

当前窗口统计：`request_end` **172**、降级 **1**、硬失败 **0**。
降级率 **0.58%**，远低于 12% 上限，也远低于 9.0% 的历史基线。

按 V8 §D2 判读表，当前落在「0 硬失败 / 1–4 降级」格 = 样本不足。
按 0.58% 的速率与 ~78 请求/小时的流量推算，24h 窗口预计累计约 1900 请求、
约 11 次降级，**≥5 的门槛大概率自然达成**，无需延长。

### B4 — `make verify-live` 未在当前构建重跑（P1）

上次 7 道 gate 全绿取自 `ae22fd4d…` 构建。当前为 `7edc1ae0…`，
中间经过 V8 D3（`degraded` 字段）。V10 §3.6 已要求重跑，尚未执行。

### B5 — V9 §D2 的 `/status.tool_arg_mode` 未实现（P2，可降级处理）

`/status` 仍无 `tool_arg_mode` 字段。但 V9 §Z2 想要的"窗口有效性运行态证据"
**已由 `repair.mode` 提供**——本次降级日志中 `"mode": "enforce"` 即是直接证据，
且它出现在窗口内的真实请求上，比周期采样 `/status` 更有说服力。

因此不再要求实现 `/status.tool_arg_mode`（该改动会触发重启并让窗口重新计时，
代价大于收益）。改为：窗口结束时以窗口内**任意一条** `repair.mode == "enforce"`
日志作为有效性证据。若窗口内一条 `repair` 日志都没有，则回落到
`/proc/<pid>/environ` 快照（窗口首尾各一次）。

## 2. 决策

### D1：更正根因表述（必须先于发布）

在以下位置把 `<tool_call` 假设改为实测结论，并保留"假设被推翻"的痕迹：

- `docs/RELEASE_NOTES_v1.1.md` 的 Known limitations
- `docs/PRD_RELEASE_CLOSURE_V6.md` §0 与 §D2 判定表（加修订记录）
- `docs/PRD_RELEASE_V7.md` §0 的"旁证"段落（加修订记录）

更正后的表述（固定文本）：

> 坏工具参数存在至少两种形态。历史簇（25 次，`7c0af42` / `86e15c0` 窗口）为
> `args_len ∈ {39, 41}`、`reject_class: not_json`，诊断字段上线前发生，首字符未采集。
> `enforce` 窗口内观测到的形态为 `args_len: 433`、`reject_class: unterminated_string`、
> `first_char_code: 0x7B`（`{`）、`is_markup: false`——**参数以合法 JSON 开头，
> 在字符串中途被截断，而上游同时给出了干净的 finish_reason**。
> 早期从 `litellm-auto-plugin` 的 `<tool_call` 标记类比得出的假设**已被实测推翻**。

**禁止**把已推翻的假设留在文档里不加标注。

### D2：形态分簇统计规则（先于窗口结束落纸）

窗口结束时按 `reject_class` 分簇统计，每簇给出计数、占比、`args_len` 区间、
`first_char_code` 分布。结论按簇给出，**不得合并成一个"坏 JSON"总结**。

### D3：`unterminated_string` 簇的处理方针

**不做任何补全扩展。** 理由：闭合未终止的字符串会静默丢失字符，
产出一个语法合法、语义错误的参数去执行工具——这比失败严重。
V6 §D2 分支 C 的判断在本次样本上成立。

处理方式：X1 安全降级已经覆盖（用户得到可读文案 + 干净结束该轮），
写入 Known limitations，并记为**上游契约问题**：
上游在参数未完整送达时给出了 `finish_reason ∈ {tool_calls, stop}`。
后续动作（向 MaaS 侧反馈 / 评估请求侧 `max_tokens` 配置）另起议题，不阻塞本次发布。

### D4：窗口判读沿用现有规则

V8 §D2 判读表 + V9 §D1 的 0/0 出口规则不变。当前落在 1–4 降级格；
若窗口届满时降级数 ≥5，直接进 §3 判定；若仍为 1–4，按 V8 §D2 延长至多 24h；
若届满时 `request_end` ≥ 200 且降级 ≥ 5，视为样本充分。

### D5：不采用

- 不实现 `/status.tool_arg_mode`（B5 已有等价证据，且会让窗口重新计时）
- 不因新形态而扩大补全能力（D3）
- 不为凑样本人为构造生产失败（沿用 V8 §D5）
- 不修改生产 `maas.env` 来迁就任何门禁（沿用 V10 §D5）
- 不在 §3 全绿前打 `v1.1` tag

## 3. 发布检查表（收尾）

代码与门禁：

1. `make verify-offline` 全绿（V10 实施后重跑，本轮进行中）
2. `make verify-live` 7 道 gate 全绿 —— **在 `7edc1ae0…` 构建上重跑**
3. 窗口完整性：`git status` 干净；`/opt` 与仓库 SHA 仍为 `7edc1ae0…`；
   MainPID 仍为 509396 —— 证明门禁修复未产生新制品、未重启

文档：

4. D1 的三处更正完成，且保留"假设被推翻"的修订痕迹
5. D2 的分簇统计表写入 release notes
6. D3 的方针写入 Known limitations

运行态取证：

7. 24h 窗口届满（**2026-08-25 04:33:40 CST**）
   **M9 (PRD LOOP_CONTINUITY_V2)：原窗口 2026-08-23 01:50:47 → 2026-08-24 01:50:47
   已被部署打断两次（01:25:15 及 04:33:40），且被观测的代码已实质变更（新增
   L1-A 重试与 L1-B 错误终止）。旧窗口数据对新构建无效，以 V2 部署时刻重开窗口。**
8. 窗口内 `request_end` ≥ 200
9. 按 V8 §D2 + V9 §D1 判读，写明落入哪一格
10. `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计。
    **M4 (PRD LOOP_CONTINUITY_V2)：原「stream protocol error 新增为 0」标准与
    L1-B 直接冲突——L1-B 的设计意图就是产生可自愈的 protocol error。**
    改写为两条正交标准：
    (a) 窗口内 `stop_reason=end_turn` 且正文仅为降级文本的回合数 = 0（任务连续性）
    (b) 窗口内 protocol error 中，客户端自动恢复比例 ≥ 32%（失败可自愈性）
    (b) 的 32% 基线取自本项目历史实测（n=25，8 次自动恢复）
11. 降级率写入 Known limitations；> 12% 阻塞发布（当前 0.58%）
12. 窗口有效性证据：窗口内至少一条 `repair.mode == "enforce"`
    （**已具备**：`b5117fa4`）
13. 6h 容量观察（**2026-08-24 10:33:40 CST** 届满）：`ss -tnp | grep :3000` 为空时
    `active_requests` 为 0，采样 ≥ 3 次。
    **M9：旧采样（01:56、04:04）取自 PID 509396，进程已不在，作废。需在新窗口内重新采样。**
14. V9 §D3 的发布后守望项写入 release notes

发布动作：

15. 全绿 → 打 `v1.1` tag → release notes 定稿

## 4. 结论

**当前不可发布。** 实质阻塞两条，均非代码：

- §3.7 的 24h 窗口还剩约 21.7 小时
- §3.2 的 `make verify-live` 需在当前构建上重跑

其余为文档更正（D1）与窗口届满后的统计工作。

**趋势是好的**：降级率 0.58%（基线 9.0%），硬失败 0，X1 在生产上首次证明有效，
`repair.mode == "enforce"` 提供了窗口有效性的直接证据。

**但根因表述必须更正后才能发布**——把一个已被实测推翻的假设写在
release notes 里发出去，比不写更糟。

### 实施记录

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| D1 `RELEASE_NOTES_v1.1.md` | ✅ | Known limitations 改为双簇表述 + 假设推翻痕迹；根因归属更新；部署模式更新 |
| D1 `PRD_RELEASE_CLOSURE_V6.md` | ✅ | §0 新增修订记录；§D2 判定表新增 `0x7B + unterminated_string` 行 + 修订记录；§6 根因结论填写 |
| D1 `PRD_RELEASE_V7.md` | ✅ | §0 旁证段落新增修订记录，标注假设推翻 |
| §3.14 发布后守望项 | ✅ | `RELEASE_NOTES_v1.1.md` 新增 Post-release watch 节，V9 D3 三条触发条件全落 |
| §3.1 verify-offline 数字 | ✅ | 706 passed（build `7edc1ae0…`），原 697 已更正 |
| T1 表述自洽 | ✅ | 改为「截断位置区别」——可闭合截断 vs 字符串中途截断，闸门 2 按设计区分 |
| Deployment mode 表述 | ✅ | 「distribution」改为「single data point, not a distribution」 |
| §3.1 verify-offline | ✅ | 706 passed / 0 failed（V10 交付，文档变更不影响） |
| §3.3 窗口完整性 | ✅ | 仅改 `docs/`，`adapter/` 未动，窗口继续计时 |
| §3.2 verify-live | ⏳ | 需在 `b8c7069b…` 构建上重跑，需 MaaS key |
| §3.7 窗口届满 | ⏳ | 2026-08-25 04:33:40 CST（M9 重开） |
