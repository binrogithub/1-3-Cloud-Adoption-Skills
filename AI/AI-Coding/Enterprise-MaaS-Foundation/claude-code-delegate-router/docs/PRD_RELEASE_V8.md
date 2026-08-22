# PRD：发布执行（v8 —— go/no-go）

状态：待执行
前置：`docs/PRD_RELEASE_V7.md`（X1–X4 已交付并部署，commit `65b6fcd`；
release notes `e2c3c77`）

核查时间：2026-08-23 01:15 CST，核查人：独立复验（非实施方自评）

**本 PRD 不含功能开发。** 除 §2 D3 的一个诊断字段外，全部是运行态取证与发布操作。

## 0. 状态

**代码侧已就绪，独立复验清单：**

| 项 | 证据 |
| --- | --- |
| X1 安全降级（enforce） | `tool_malformed` → `event:error` **0** 个、`tool_use` 块 **0** 个、`message_stop` 1 个、`stop_reason: end_turn`、降级文案正确送达 |
| X4 灰度开关有效性 | 同场景 `observe` → `event:error` **1** 个、无降级块、`outcome: upstream_failed`，与旧行为逐项一致 |
| V6 形状诊断 | `first_char_code` / `args_len` / `reject_class` 均落盘 |
| 部署新鲜度 | `git status` 干净；`/opt` 与仓库 `server.js` SHA 一致（`ae22fd4d…`）；MainPID 454440 |
| 离线回归 | `make verify-offline`（本轮重跑，结果见 §3.1） |
| **在线门禁** | `make verify-live` **7 道 gate 全绿** |
| release notes 表述纪律 | v1.1 已写明 `tool_args_repaired = 0`、V1 非根因、降级率基线 9.0%，未夸大 |

**阻塞项全部在运行态，不在代码。**

## 1. 缺口

### Y1 — 生产运行在 `observe`，X1 未生效，发布判据未被测量（P0）

`adapter/server.js:589`：`MAAS_TOOL_ARG_MODE || "observe"`。
`/etc/claude-code-proxy/maas.env` 与 systemd unit 均未设该变量 → 生产为 `observe`。

`observe` 的定义就是"行为与旧版完全一致"。因此：

- V7 §4.1 的"硬失败清零"窗口**尚未开始计时**
- 线上此刻遇到坏工具参数，用户仍会收到 `API Error: stream protocol error`

v1.1 release notes 已经写好，但**它描述的行为在生产上没有生效**。

### Y2 — 根因归属零样本（P1）

当前构建窗口（22:40:09 起，2.5h，80 个 `request_end`）：

    tool_args_malformed   0
    MAAS_STREAM_PROTOCOL  0
    first_char_code       0 条

V7 §4.3 要求"根因有归属，允许已定位未修复，不允许未定位"。
`<tool_call`（`0x3C`）假设**既未确认也未推翻**。

### Y3 — "0 次失败"的误读风险（P1）

历史基线：`7c0af42` 窗口 8.9h / 133 请求 / 12 次失败 = **9.0%**；
`86e15c0` 窗口合计 314 请求 / 13 次失败 = **4.1%**。
按此基线，80 个请求的期望失败数是 3–7 次，实测 **0**。

**这个 0 不是修复的结果。** `observe` 模式下 X1 不生效；且日志显示
`tryRepairToolArgs` 一次都没被调用（`first_char_code` 零条），
即 `JSON.parse` 从未失败——坏参数根本没出现。这是流量特征或上游行为变化，
不是本项目的任何改动导致的。

**风险**：把这个 0 读成"问题已解决"，会导致在没有任何降级证据的情况下发布。

### Y4 — 缺少区分"降级生效"与"没有失败"的字段（P1）

X1 生效时，请求的终态是 `outcome: completed`、`protocol_error_reason: null`，
仅能由 `repair.attempted=true && repair.applied=false` 间接推断。
没有显式标记，§3 的发布证据无法干净统计。

## 2. 决策

### D1：切 `enforce` 的操作与前置

- 在 `/etc/claude-code-proxy/maas.env` 写入 `MAAS_TOOL_ARG_MODE=enforce`
- **重启会杀掉在途流**（本项目既有结论）。切换须在低活跃时段执行，
  并在切换前后各取一次 `/status` 快照存档
- 切换后立即核对 `/status` 可达 + MainPID 变化 + `/opt` SHA 未变
  （只改 env，不改二进制；SHA 必须保持 `ae22fd4d…`）

### D2：`enforce` 窗口的判读规则（先于数据落纸）

24h 窗口结束后，按下表判读，**不得事后择规则**：

| 硬失败数 | 降级数 | 判读 | 动作 |
| --- | --- | --- | --- |
| 0 | ≥ 5 | X1 生效且有证据 | §4.1/§4.2 通过 |
| 0 | 1–4 | 生效但样本不足 | 窗口延长至降级数 ≥ 5，最多再延 24h |
| 0 | 0 | **无证据** | 窗口作废。故障未复现 ≠ 已解决，按 D3 结案 |
| ≥ 1 | 任意 | X1 有漏网路径 | 阻塞发布，定位该路径 |

"降级数"以 D3 的显式字段统计，不用间接推断。

### D3：补一个显式降级标记（唯一的代码改动）

结构化日志与 `/status` 各加一项：

    request_end 增加：  "degraded": true|false
    /status 增加：      "tool_args_degraded"  （计数）

`degraded` 仅在 `enforce` 模式下因工具参数不可用而发出降级文本块时为 `true`。
`observe` 模式恒为 `false`。

门禁：`enforce` + `tool_malformed` → `degraded: true` 且计数递增；
`observe` + 同场景 → `degraded: false` 且计数不变。

### D4：窗口内零失败时的结案方式

若 D2 落入"0 / 0"格，**不得**声称问题已解决。结案表述固定为：

> 坏工具参数故障在 v1.1 观察窗口内未复现。历史基线 9.0%（`7c0af42` 窗口
> 12/133），形态特征为 `reject_class: not_json`、`args_len ∈ {39, 41}`、
> `tool_call_index_absent: false`。安全降级路径（X1）已具备并通过离线门禁验证，
> 但**未在生产触发过**。诊断字段保留，复现即可定性。

并在 release notes 的 Known limitations 中原样保留该表述。

### D5：不采用

- 不因窗口零失败而删除 T1/X1/X3 任何一层
- 不把 `enforce` 设为代码默认值（默认仍是 `observe`，生产靠 env 显式开启，
  保留一键回退能力）
- 不为了凑样本人为构造生产失败
- 不在 §3 全绿前打 v1.1 tag

## 3. 发布检查表（go/no-go）

代码与门禁：

1. `make verify-offline` 全绿，总数 ≥ 682 + D3 新增用例数
2. `make verify-live` 7 道 gate 全绿 —— **本轮已完成（全绿）**
3. D3 双向门禁通过（`enforce` → `degraded:true`；`observe` → `degraded:false`）
4. 运行态新鲜度：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；`/status` 可达

运行态取证：

5. `MAAS_TOOL_ARG_MODE=enforce` 已写入 env 并生效（`/status` 或日志可证）
6. `enforce` 窗口满 24h，按 D2 表格判读并写明落入哪一格
7. 在 `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计，
   窗口内 `stream protocol error` 新增为 **0**
8. 降级率写入 release notes Known limitations；若 > 12%（基线 9.0% +3pp），
   阻塞发布
9. 根因归属按 D2/D4 给出明确结论（"已定位未修复"或 D4 的固定表述二选一，
   不接受"待观察"）
10. 容量观察 ≥ 6h：`ss -tnp | grep :3000` 为空时 `active_requests` 为 0，
    采样 ≥ 3 次（当前已有 1 次：01:09 采样 active=0、连接数 0）

发布动作：

11. 以上全部通过 → 打 `v1.1` tag → release notes 定稿

## 4. 执行顺序

1. D3 显式降级字段 + §3.3 双向门禁
2. `make verify-offline` 重取基线
3. 部署（二进制变更，走 `adapter/deploy.sh`）→ §3.4 运行态核对
4. 写入 `MAAS_TOOL_ARG_MODE=enforce` → 重启 → §3.5 确认生效
5. 启动 24h 窗口（§3.6/§3.7/§3.8）与 6h 容量观察（§3.10），并行计时
6. 按 D2 判读 → 按 D4 或"已定位"结案 → §3.9
7. §3 全绿 → 打 tag → 发布

### 执行记录

| 步骤 | 状态 | 时刻 (UTC) | 证据 |
| --- | --- | --- | --- |
| 1. D3 字段 + 双向门禁 | ✅ 完成 | 2026-08-22T17:40Z | commit `4520224`；`server.js` +6 行；3 个门禁用例 |
| 2. verify-offline | ✅ 全绿 | 2026-08-22T17:40Z | 700 passed（基线 682 + 新增） |
| 3. 部署 | ✅ 完成 | 2026-08-22T17:49Z | `/opt/server.js` SHA `7edc1ae0…`；rollback target `ae22fd4d…` 已存；MainPID 454440→509140 |
| 4. 切 enforce | ✅ 生效 | 2026-08-22T17:50Z | `/proc/<PID>/environ` 确认 `MAAS_TOOL_ARG_MODE=enforce`；MainPID 509396 |
| 5. 24h 窗口 | ⏳ 计时中 | 起点 2026-08-22T17:50Z | 判读时间：2026-08-23T17:50Z |
| 6. D2 判读 | ⏸ 待窗口结束 | — | — |
| 7. 打 tag 发布 | ⏸ 待 §3 全绿 | — | — |

**当前状态：代码侧全部完成，生产 enforce 已生效，24h 观察窗口计时中。**
阻塞项仅剩 §3 第 5–10 项（运行态证据收集），无代码工作。

## 5. 回滚

任一时刻发现 `enforce` 引入新问题：

- 第一手段：`MAAS_TOOL_ARG_MODE=observe` + 重启（行为立即回到 v1.1 之前语义，
  不需要回滚二进制）
- 第二手段：`adapter/rollback.sh` 回到 `86e15c0` 的制品
- 两种回滚都要在 PRD 中记录时刻与触发原因

## 6. 结论

**当前不可发布。** 阻塞项是 §3 的第 5–9 项，全部是运行态证据，
代码侧除 D3 一个诊断字段外无需改动。

最短路径：D3（约半小时）→ 部署 → 切 `enforce` → 等 24h → 判读 → 发布。
