# PRD：发布判据补全（v9 —— 零故障窗口的出口）

状态：执行中（§3.1 已修复）
前置：`docs/PRD_RELEASE_V8.md`（D3 已交付 `4520224`，`enforce` 已生效 `dacfb75`）

核查时间：2026-08-23 02:00 CST，核查人：独立复验（非实施方自评）

**本 PRD 改一条判据、加一个字段、修一个测试隔离缺陷。**

### 执行记录

**§3.1 修复（2026-08-23）**：`make verify-offline` 在构建 `7edc1ae0…` 上首跑
6 failed / 694 passed。根因：`adapter/server.js:24` 的 `loadEnvFile` 默认读取
`/etc/claude-code-proxy/maas.env`（含 `MAAS_TOOL_ARG_MODE=enforce`），测试子进程
经 `os.environ` 继承，导致未显式设 mode 的测试实际跑在 enforce 而非预期 observe。

- `test_tool_repair.py` 4 道反向门：预期 observe 硬失败，实际 enforce 降级（200 + message_stop + end_turn）
- `test_observability.py::test_error_counts_single_count`：预期 `MAAS_STREAM_PROTOCOL` 错误计数 = 1，实际 enforce 降级无错误
- `test_tool_degradation.py::test_tool_markup_classified_separately`：enforce 降级不设 `protocolError`，`protocol_error_reason` 为 null

修复：新增 `tests/conftest.py`，在 pytest 启动时设
`ENV_FILE=/tmp/claude-code-proxy-test-env-absent`（不存在路径），使 `loadEnvFile` no-op。
测试通过 `extra_env` 独占 `MAAS_TOOL_ARG_MODE` 控制。复跑 **700 passed / 0 failed**。

## 0. 状态

**V8 §3 的代码与门禁项全部就绪，独立复验清单：**

| 项 | 证据 |
| --- | --- |
| D3 降级标记（enforce） | `tool_malformed` → `degraded` 字段落盘，`event:error` 0、`message_stop` 1、`stop_reason: end_turn`、降级文案送达 |
| D3 降级标记（observe） | 同场景 → `outcome: upstream_failed`、无降级块，与旧行为一致 |
| `enforce` 真实生效 | `/proc/509396/environ` 含 `MAAS_TOOL_ARG_MODE`；systemd `EnvironmentFile=/etc/claude-code-proxy/maas.env` 注入，非"只写文件未被读取" |
| `/status` 新字段 | `tool_args_degraded: 0`、`tool_markup_seen: 0` 已暴露 |
| 部署新鲜度 | `git status` 干净；`/opt` 与仓库 SHA 一致（`7edc1ae0…`）；MainPID 509396 |
| 未提前打标 | `git tag` 仅 `v1.0`，`v1.1` 未打 |

**唯一的实质阻塞是时间**：窗口 2026-08-23 01:50:47 起，
核查时仅过 **6 分钟**，24h 到期时间为 **2026-08-24 01:50:47**。

## 1. 缺口

### Z1 — V8 D2 判读表的 0/0 格没有出口，会把发布锁死（P1，判据缺陷）

V8 §D2：

    | 0 硬失败 | 0 降级 | **无证据** | 窗口作废。故障未复现 ≠ 已解决，按 D3 结案 |

两个问题：

1. 笔误——固定结案表述在 **D4**，不在 D3
2. **"窗口作废"没有说明发布是阻塞还是放行**

按当前趋势，0/0 是大概率结局：`65b6fcd` 窗口（22:40 起）80 请求 0 故障；
`dacfb75` 窗口（01:50 起）25 请求 0 故障。历史基线是
`7c0af42` 窗口的 9.0%（12/133）与 `86e15c0` 窗口的 4.1%（13/314）。
坏参数在最近约 5 小时内一次都没出现。

若照字面执行"窗口作废"，发布将无限期等待一个**我们无法制造、且明令禁止人为制造**
（V8 §D5"不为了凑样本人为构造生产失败"）的故障。这不是一个有意义的门禁。

### Z2 — 窗口有效性的证据不是一等公民（P2）

`enforce` 是否全程生效，目前只能靠 `/proc/<pid>/environ` 证明。
`repair.mode` 字段确实存在（`server.js:992`），但**只在发生修复尝试时才写**——
零故障窗口里一条都不会有。

一个 24h 窗口的全部效力建立在"进程处于 enforce"这一前提上，
而该前提在窗口内没有可周期性采样的运行态证据。

### Z3 — 窗口与容量观察均刚开始（P0，纯时间）

    24h 窗口      01:50:47 → 2026-08-24 01:50:47   已过 6 分钟
    6h 容量观察   01:50:47 → 2026-08-23 07:50:47   已过 6 分钟

## 2. 决策

### D1：0/0 格的出口规则（替换 V8 §D2 该行）

窗口结束时若 **硬失败 = 0 且 降级 = 0**，**允许发布**，当且仅当以下全部成立：

1. **X1 有效性已由离线反向门证明**（不依赖生产样本）：
   `enforce` 下 `event:error` = 0、`tool_use` 块 = 0、`message_stop` = 1、
   `stop_reason: end_turn`、降级文案送达；`observe` 下行为与旧版逐项一致
2. **窗口有效性可证**：`enforce` 在窗口首、尾各有一次运行态证据（D2 的 `mode` 字段）
3. **流量下限**：窗口内 `request_end` ≥ **200**。
   这一条区分"没有故障"与"没有流量"——按历史 4.1% 的基线，
   200 次请求出现 0 故障的概率约为 0.02%，足以判定故障率已显著低于基线；
   不足 200 则延长窗口，每次延长 24h，最多两次
4. **Known limitations 使用 V8 §D4 的固定表述**，不得改写为"已修复"
5. **诊断字段全部保留**：`reject_class` / `first_char_code` / `char_class_counts` /
   `degraded` / `tool_args_degraded` / `tool_markup_seen`
6. **定义发布后守望**（D3）

理由：把发布阻塞在一个无法复现、且禁止人为制造的故障上，不是有鉴别力的门禁。
X1 的正确性由离线反向门保证；生产样本只能提高置信，不能作为唯一依据。
风险是有界的——最坏情况是旧的硬失败行为重现，而那恰好是可观测、可回滚的。

其余三格（0/≥5、0/1–4、≥1/任意）沿用 V8 §D2 不变。

### D2：`/status` 暴露运行模式（唯一的代码改动）

    /status 增加： "tool_arg_mode": "off" | "observe" | "enforce"

用途仅为窗口有效性取证，无行为变更。
门禁：`MAAS_TOOL_ARG_MODE=enforce` 启动 → `/status.tool_arg_mode == "enforce"`；
不设该变量 → `"observe"`。

### D3：发布后守望（v1.1 发布起 7 天）

| 触发条件 | 动作 |
| --- | --- |
| `tool_args_degraded` > 0 | 按实测降级率更新 Known limitations，并用 `first_char_code` 分布定性根因 |
| `stream protocol error` 复现（`isApiErrorMessage` 全量口径） | 说明 X1 有漏网路径，按 V8 §D2 的"≥1 硬失败"格处理 |
| 单日降级率 > 12% | 切回 `MAAS_TOOL_ARG_MODE=observe` + 重启，重新评估 |

守望项写入 release notes，不写入代码。

### D4：不采用

- 不人为构造生产故障凑样本（沿用 V8 §D5）
- 不把 `enforce` 设为代码默认值（保留一键回退）
- 不因窗口零故障而删除 T1 / X1 / X3 任何一层
- 不在 §3 全绿前打 `v1.1` tag
- **不把"故障未复现"写成"已修复"**

## 3. 发布检查表（在 V8 §3 基础上修订）

代码与门禁：

1. `make verify-offline` 全绿（本轮重跑，结果见执行记录）
2. `make verify-live` 7 道 gate 全绿 —— **需在当前构建（`7edc1ae0…`）上重跑**，
   上次全绿是在 `ae22fd4d…` 构建上取的
3. D2 `tool_arg_mode` 双向门禁通过
4. 运行态新鲜度：`git status` 干净；`/opt` 与仓库 `server.js`、`lifecycle.js`
   SHA-256 逐一相等；`/status` 可达

运行态取证：

5. 窗口首尾各一次 `/status.tool_arg_mode == "enforce"` 快照存档
6. 24h 窗口届满（**2026-08-24 01:50:47**）
7. 窗口内 `request_end` ≥ 200
8. 按 V8 §D2 + 本 PRD §D1 判读，写明落入哪一格
9. `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` **全量**统计，
   窗口内 `stream protocol error` 新增为 0
10. 降级率写入 Known limitations；> 12% 阻塞发布
11. 根因结论：D1 的固定表述或"已定位未修复"，不接受"待观察"
12. 6h 容量观察（**2026-08-23 07:50:47** 届满）：`ss -tnp | grep :3000` 为空时
    `active_requests` 为 0，采样 ≥ 3 次
13. D3 守望项写入 release notes

发布动作：

14. 以上全绿 → 打 `v1.1` tag → release notes 定稿

## 4. 时间线

    2026-08-23 01:50:47   enforce 生效，窗口开始
    2026-08-23 07:50:47   6h 容量观察届满（§3.12）
    2026-08-24 01:50:47   24h 窗口届满（§3.6）
    届满后                 判读 → §3 全绿 → 打 tag

D2 的 `mode` 字段部署会重启进程。**若在窗口内部署，窗口重新计时。**
建议二选一：

- **A（推荐）**：立即部署 D2，窗口从新部署时刻重新计时。
  代价是推迟约 1 小时，收益是窗口全程有可采样的有效性证据
- **B**：窗口结束后再加 D2，本次窗口的有效性用 `/proc/<pid>/environ` 快照佐证
  （已取一次，需在窗口结束前再取一次）

## 5. 结论

**当前不可发布。** 唯一实质阻塞是时间：24h 窗口已过 6 分钟。

代码侧除 D2 一个诊断字段外无需改动。V8 §D2 的 0/0 死锁由本 PRD §D1 解除——
在离线反向门已证明 X1 有效、且窗口流量达到 200 次请求下限的前提下，
零故障窗口**允许发布**，Known limitations 如实记录"未复现"。
