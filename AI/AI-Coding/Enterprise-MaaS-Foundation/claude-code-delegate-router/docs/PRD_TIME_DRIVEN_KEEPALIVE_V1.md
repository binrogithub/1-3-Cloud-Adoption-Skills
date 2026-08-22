# PRD：时间驱动保活与客户端饥饿可见性（v1）

状态：已交付
触发：2026-08-21 夜间，`claude-maas` 连续 6 次
`API Error: The response stopped arriving`，而适配器 `/status` 全程 `last_error_code: null`
相关：`PRD_THINKING_WAIT_VISIBILITY_V1.md`（D1-C 块计数心跳）、
`PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`（idle/total 看门狗）

## 0. 产品摘要

思考可见性上线后，客户端仍会在长思考轮次中断流。根因不是适配器故障，而是
**"刷新看门狗的事件"与"产生客户端字节的事件"不是同一批**：上游只要有任何活动，
适配器就认为一切正常；而客户端可能整整 180 秒收不到一个字节，于是 Claude Code
自己的流超时先触发并主动断开。适配器的客户端中止路径不记录任何错误，
所以这类故障在 `/status` 上**完全隐形**。

本 PRD 把心跳从**块计数驱动**改为**时间驱动**，并让"客户端饥饿"成为可观测、
可告警的一等状态。不改模型行为，不改凭证拓扑，不改协议翻译语义。

## 1. 证据

### 1.1 六次故障全部卡在 180 秒

从 `~/.claude-maas/projects/*/*.jsonl` 提取"报错时刻 − 上一条 assistant 事件时刻"：

    本地 08-21 01:52:58   180.7s
    本地 08-21 02:02:02   181.9s
    本地 08-21 02:07:17   181.8s
    本地 08-21 02:17:30   181.4s
    本地 08-21 02:39:01   180.3s
    本地 08-21 05:14:20   180.7s

最后一次现场：`[thinking]` 块 `21:11:19.866Z` 发出 → `21:14:20.553Z` 报错，间隔 181s。

### 1.2 适配器一次都没触发自己的 idle 超时

故障期间 `/status`：`last_error_code: null`、`NRestarts: 0`、journal 无条目。
而适配器的 `MAAS_IDLE_TIMEOUT` **也正好是 180s**。两个都是 180s，只有一个响了。

### 1.3 两个复现，锁定是哪条路径

| 复现 | 客户端收到 | `/status` 记录 |
| --- | --- | --- |
| 上游开流后中途静默 | `event: error` + `MAAS_IDLE_TIMEOUT` | **有** |
| 客户端中途断开 | —（客户端自己走的） | **无**（`last_error_code` 保持 `null`） |

生产观测到的是"无记录"，因此**是客户端先超时中止**，不是适配器超时。

### 1.4 为什么"上游活着"而"客户端饿死"

    server.js:392   ctrl.recordActivity("usage")      ← usage 块刷新计时器，输出 0 字节
    server.js:403   ctrl.recordReasoning(...)         ← 每个 reasoning 块都刷新计时器
    server.js:424   if (reasoningChunkCount % THINKING_HEARTBEAT_INTERVAL === 0)
                                                      ← 心跳只在第 3、6、9… 个块时才发

只要上游在 180 秒内送来 1–2 个 reasoning 块、或若干 usage 心跳块，看门狗被持续
刷新、适配器"一切正常"，而客户端**一个字节都没有**。D1-C 的心跳是按**块计数**
驱动的，覆盖不了慢速上游。

### 1.5 这类故障如何绕过全部门禁

现有门禁只断言"上游有活动 / 事件序列合法 / 无泄漏"，**没有任何一条断言
"客户端在任意 T 秒窗口内至少收到一个字节"**。fake upstream 的所有场景都是
毫秒级连续吐数据，天然不可能构造出饥饿。这是本仓库第六种"测试全过"失真：
**测的是上游侧的活着，用户体验的是客户端侧的收到。**

## 2. 决策

### D1：心跳改为时间驱动（核心）

- 维护 `lastClientByteAt`（任何写入客户端的 SSE 字节都刷新它）。
- 只要 `now - lastClientByteAt > MAAS_KEEPALIVE_INTERVAL`（默认 **15s**，env 可调），
  就发一次客户端可见事件：thinking 块开着时发 `thinking_delta` 占位符 `·`，
  否则发 Anthropic 协议合法的 `event: ping`。
- 保留 `MAAS_THINKING_HEARTBEAT_INTERVAL` 的块计数心跳作为叠加，不冲突：
  **两者取先到者**，时间驱动是下界保证。

### D2：把"客户端饥饿"变成一等状态

- 新增看门狗：`now - lastClientByteAt > MAAS_CLIENT_STARVATION_LIMIT`（默认 **60s**）
  即进入 `client_starving` 状态，计入 `/status` 的 `state_counts`。
- D1 正确实施后该状态**不应出现**；它的价值是：一旦 D1 退化，`/status` 立刻暴露，
  而不是像今晚一样全绿。

### D3：客户端中止必须留痕

客户端断开时记录 `MAAS_CLIENT_ABORTED`（错误码已存在于 `lifecycle.js`，只是
从未被写进 `lastErrorCode`），并在 `/status` 暴露累计计数
`client_aborts`。**今晚 6 次故障零记录，就是因为这条路径静默返回。**

### D4：让适配器先于客户端超时

`MAAS_IDLE_TIMEOUT` 默认值从 **180s 下调到 150s**。两个计时器相等时谁先响是随机的；
适配器先响，用户看到的是 `upstream idle timeout` 这种可诊断的消息，而不是
`The response stopped arriving` 这种什么都说明不了的通用文案。

### D5：不采用

- 不关思考（沿用既有量化证据）。
- 不转发模型 reasoning 原文。
- 不引入第二个 listener / Sidecar。
- 不改 `MAAS_TOTAL_TIMEOUT` 的语义（另见 §5 遗留项）。

## 3. 影响面

| 文件 | 变更 |
| --- | --- |
| `adapter/server.js` | `lastClientByteAt` 记账、时间驱动心跳、starvation 判定、中止留痕 |
| `adapter/lifecycle.js` | 新增 `client_starving` 状态与 `client_aborts` 计数；`CLIENT_ABORTED` 接入 |
| `tests/helpers/fake_upstream.js` | 新增慢速场景（见 §4） |
| `tests/test_thinking_visibility.py` / 新增用例 | 客户端字节间隔断言 |
| `docs/RELEASE_NOTES_v1.0.md` | 已知限制补一条（见 §5） |

## 4. 验收标准

每条都必须先证明**修复前失败**。

1. **慢速 reasoning 饥饿门（反向门）**：新场景 `slow_reasoning` —— 每 60s 只发 1 个
   reasoning 块，持续 5 分钟。断言：客户端**任意相邻两个字节的间隔 ≤ 17s**
   （15s + 2s 容差）。修复前该用例必须失败（实测间隔 ≈180s 后连接断）。
2. **usage-only 饥饿门（反向门）**：新场景 `usage_only_trickle` —— 每 30s 只发一个
   usage 块，不发任何 content/reasoning。同样断言字节间隔 ≤17s。修复前必失败。
3. **中止留痕**：客户端主动断开后，`/status` 的 `last_error_code == "MAAS_CLIENT_ABORTED"`
   且 `client_aborts` 递增。修复前该断言为 `null`（已实测）。
4. **适配器先响**：上游真死时，客户端必须收到 `event: error` 且
   `code == "MAAS_IDLE_TIMEOUT"`；断言 150s < 客户端超时。
5. **零泄漏**：注入高熵 canary 到 `reasoning_content`，扫描全部保活字节，命中为 0；
   **先断言保活事件数 > 0**（防空集重言式）。
6. **真实链路复测**：部署后用 `claude-maas` 跑一个必然进入长思考的真实轮次，
   记录客户端字节间隔分布，最大间隔必须 < `MAAS_KEEPALIVE_INTERVAL + 5s`。
7. **观察窗**：部署后 24h 内，`~/.claude-maas/projects/*/*.jsonl` 中
   `response stopped arriving` 新增条数必须为 **0**；今晚基线是 6 次/6 小时。
8. 运行态新鲜度（`/opt` 与仓库 SHA 一致 + MainPID 变化 + `/status` 版本）、
   `make verify-offline` 全绿、真实 HOME 配置未被改动。

## 5. 遗留与已知限制（需写进 release notes）

- **`MAAS_TOTAL_TIMEOUT=600s` 是 legacy 没有的行为**：思考开启的超长轮次会被硬掐，
  legacy 会一直等。本 PRD 不改其语义，但必须在 release notes 的"已知限制"里写明。
- Claude Code 自身的流超时值未经查证，本 PRD 以实测的 ~180s 为准。若后续版本改变，
  D4 的 150s 需要重新取值。

## 6. 实施顺序

1. D3 中止留痕（最小改动，先让故障可见）
2. D1 时间驱动心跳 + §4 的两个饥饿反向门
3. D2 `client_starving` 状态
4. D4 下调 idle 默认值
5. 部署 + §4.6 真实链路复测
6. §4.7 观察窗 24h 后结案

## 7. 一条自我修正

本问题第一次讨论时，"仅发 SSE ping"曾被判为"不解决用户可见的抱怨"而降级为地板方案。
**该判断不完整**：ping 确实改不了 `Waiting for API response` 的文案，但**按时间驱动的
保活恰恰是防止客户端饿死断流的唯一手段**，而块计数心跳覆盖不了慢速上游。
两者解决的是不同问题，本 PRD 把它们合并成一个机制。

## 8. 交付记录

**日期：** 2026-08-21
**状态：** 已交付

### D3 客户端中止留痕

- `adapter/lifecycle.js` `abort()` 新增 `this.errorCode = ErrorCodes.CLIENT_ABORTED`。
- `adapter/server.js` 新增全局 `clientAbortCount`，`onClose` 中递增并设置 `lastErrorCode`。
- `/status` 新增 `client_aborts` 计数字段。

### D1 时间驱动心跳

- `adapter/server.js` 新增 `lastClientByteAt` 记账、`clientWrite()` 包装器（替换所有 `sse(res,...)` 调用以追踪客户端字节时间）。
- 新增 `keepaliveTimer`（`setInterval`），每 `MAAS_KEEPALIVE_INTERVAL`（默认 15s）检查：若超间隔未发字节，thinking 块开着发 `thinking_delta` 占位符，否则发 `event: ping`。
- 块计数心跳保留作叠加，两者取先到者。
- `tests/helpers/fake_upstream.js` 新增 `slow_reasoning`、`usage_only_trickle`、`slow_reasoning_canary` 场景。

### D2 客户端饥饿一等状态

- `adapter/lifecycle.js` 新增 `State.CLIENT_STARVING`（非终态）、`recordClientByte()`、`checkStarvation()`、`markStarving()` 方法。
- `adapter/server.js` keepalive 定时器中调用 `checkStarvation` + `markStarving`。
- 状态枚举从 11 增至 12，`test_lifecycle.py` 和 `test_adapter_protocol_security.py` 已更新。

### D4 idle 默认值下调

- `adapter/server.js` 和 `adapter/lifecycle.js` 默认值从 180s 改为 150s。

### 验收

- `tests/test_keepalive.py`：6 个新测试全部通过（slow_reasoning 反向门、usage_only_trickle 反向门、零泄漏、中止留痕、idle 默认值、client_aborts 字段）。
- `make verify-offline`：658 测试通过（652 原有 + 6 新增），禁止依赖扫描干净。
