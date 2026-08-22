# PRD：时间驱动保活收口（v1 closure）

状态：D1-A + D2 已落地（代码+门禁），K3/K4 待时间窗与定性
前置：`docs/PRD_TIME_DRIVEN_KEEPALIVE_V1.md`（实现已交付并部署，commit `b7c986e`）

## 0. 产品摘要

**保活机制有效，主要目标已达成。** 严格按 `isApiErrorMessage` 统计（不是文本 grep）：

    01:16:51  Connection refused        ← 38123 配置事故，已修
    01:52:58 ~ 05:14:20  共 6 条        ← 间隔 180.3–181.9s，饥饿断流
    06:13:03 保活部署之后               ← 新增 0 条

线上实测保活确实在发（15s 一次），上游真死时客户端能拿到
`event: error / MAAS_IDLE_TIMEOUT`，客户端中止会被记为 `MAAS_CLIENT_ABORTED`
并累加 `client_aborts`，10 次连续中止后 `active_requests` 归零、新请求正常服务
（无容量泄漏）。

**但 PRD 的两条验收没有兑现**，其中一条的门禁被写成了接受缺陷的形状。

## 1. 缺口

### K1 — 最坏字节间隔是 2× 周期，不是 PRD 要求的周期+容差（P1，发布阻塞）

慢速上游实测（每 60s 一个 reasoning 块，`MAAS_KEEPALIVE_INTERVAL=15`）：

    字节到达间隔序列: [0.0, 15.0, 15.0, 15.0, 15.0, 15.0, 30.0]
    >>> 最大间隔 = 30.0s     （PRD 验收 #1 要求 ≤17s）

根因在 `adapter/server.js:497-518`：

    const keepaliveTimer = setInterval(() => {
      ...
      const elapsed = Date.now() - lastClientByteAt;
      if (elapsed < KEEPALIVE_INTERVAL) return;      ← 只要抖动一点点就整周期跳过
      ...
    }, KEEPALIVE_INTERVAL);

固定周期 `setInterval` 配上 `elapsed < INTERVAL` 的守卫：任何一次定时器抖动、
或一个真实上游字节落在窗口中段，都会让这一拍**整拍作废**，下一次机会要等满一个
周期 → 最坏间隔退化为 **2 × INTERVAL**。

### K2 — 门禁把缺陷写成了验收标准（P1，发布阻塞）

`tests/test_keepalive.py:175`：

    # Assert ≤ 5s (2s * 2 + 1s jitter) — without keepalive, gaps would be ≈10s.
    assert max_gap <= 5.0

注释直白写着按 `2 × interval` 取阈值。也就是说 **K1 的行为被当成预期写进了断言**，
这条门禁对 K1 永远无鉴别力；生产 15s 周期对应的实际容忍度是 31s，而 PRD 写的是 17s。

这是本仓库反复出现的同一种失真的新变体：**先实现，再把阈值调到实现能过**。

### K3 — 观察窗未满（P2，时间问题，非代码问题）

PRD 验收 #7 要求"部署后 24h 内新增 0 条"。部署于 06:13:03，核查时仅过约 20 分钟。
当前证据（新增 0 条）方向正确，但**窗口没到，不能算兑现**。

## 2. 决策

### D1：保活改为"到点即发"，去掉整拍作废

二选一，推荐 A：

- **A（推荐）自重排定时器**：每次写出客户端字节后 `clearTimeout` + 按
  `INTERVAL` 重新 `setTimeout`。语义直接等于"距上一个客户端字节满 INTERVAL 就发"，
  最坏间隔 = INTERVAL + 一次定时器抖动。
- B 提高轮询频率：`setInterval(INTERVAL / 4)` 保留 elapsed 守卫，最坏间隔
  = INTERVAL × 1.25。改动更小但仍有 25% 余量，且多 4 倍空转。

### D2：门禁阈值回到 PRD 口径

`max_gap <= INTERVAL + 2s`（用小 INTERVAL 跑，如 2s → 阈值 4s），并**先证明
修复前该断言失败**（当前实现在 2s 周期下会出现 4s 间隔）。禁止再用
"interval × 2" 作为容差理由；抖动容差是常数项，不是倍数项。

### D3：不采用

- 不改 `MAAS_KEEPALIVE_INTERVAL` 的默认值（15s 本身是合理的）。
- 不改 idle/total 超时语义（D4 的 150s 已生效并验证）。
- 不动 thinking 块计数心跳（与时间驱动叠加，取先到者）。

## 3. 验收标准

1. **K1 反向门**：慢速上游场景下，客户端最大字节间隔 ≤ `INTERVAL + 2s`；
   修复前用同一用例必须失败（当前实测 2× 周期）。
2. **K2**：`tests/test_keepalive.py` 的阈值改为常数容差；改完后对当前实现跑一遍，
   必须 **FAIL**；对修复后的实现跑，必须 PASS。两次结果都要留证据。
3. **生产复测**：部署后用慢速真实轮次（长思考）采样客户端字节间隔，
   最大值 < `INTERVAL + 5s`。
4. **K3 观察窗**：部署后满 24h，按 `isApiErrorMessage` 严格统计，
   `response stopped arriving` 新增为 0。**统计口径必须用该标志位，不得用文本 grep**
   ——本次核查中文本 grep 产生了 4 条假阳性（会话正文引用了这句错误文案）。
5. 运行态新鲜度（`/opt` 与仓库 SHA 一致 + MainPID 变化 + `/status` 版本）；
   `make verify-offline` 全绿；真实 HOME 配置未被改动。

## 4. 不需要重做的部分（已实测通过）

| 项 | 证据 |
| --- | --- |
| 保活在发 | 间隔序列 `[0, 15, 15, 15, 15, 15, 30]`，前 5 拍准点 |
| 上游真死可诊断 | 客户端收到 `event: error` + `MAAS_IDLE_TIMEOUT` |
| 客户端中止留痕 | `last_error_code=MAAS_CLIENT_ABORTED`，`client_aborts` 递增 |
| 无容量泄漏 | 连打 10 次中止后 `active_requests=0`，新请求正常服务 |
| 部署到位 | `/opt` 与仓库 SHA 同为 `b9c6a7e2…`，MainPID 11681，`idle_ms=150000` |
| 测试 | 658 passed |

## 5. 实施顺序

1. D2 先改门禁阈值 → 跑一遍证明当前实现 FAIL（把缺陷钉住）
2. D1-A 改定时器 → 同一门禁转 PASS
3. 部署 + §3.3 生产复测
4. 等满 §3.4 的 24h 窗口后结案，再做 release 决定

## 6. 实施记录（2026-08-21）

### D2 门禁收紧 — 已落地

`tests/test_keepalive.py` 两条反向门改为 `MAAS_KEEPALIVE_INTERVAL=3`、阈值
`INTERVAL + 2s = 5s`（常数容差，非 `2× INTERVAL`）。

**为什么 INTERVAL=3 而非 2**：INTERVAL=2 时 bug 最大值 = 4.0s = 阈值 4.0s，
`<=` 判过，门禁对 K1 零鉴别力。INTERVAL=3 时 bug 最大值 = 6.0s > 5.0s，FAIL。

**修复前证据**（钉死缺陷）：

    test_slow_reasoning_client_byte_interval FAILED
    gaps: ['3.0', '6.0', '1.0', '5.0', '6.0', '3.0', '3.0']  MAX 6.0s > 5.0s

### D1-A 自重排定时器 — 已落地

`adapter/server.js`：`setInterval(INTERVAL)` + `elapsed < INTERVAL` 守卫 →
自重排 `setTimeout`。每次 `clientWrite` 清除 pending timer 并重新 `setTimeout`，
语义 = "距上一个客户端字节满 INTERVAL 即发"。

实现要点：
- `keepaliveTimer` / `scheduleKeepalive` / `keepaliveTick` 声明在 `clientWrite`
  之前，避免 TDZ（`message_start` 是第一次 clientWrite）。
- `keepaliveTick` 用 `let` 先赋 no-op，真实 body 在 thinking 状态声明后赋值；
  `scheduleKeepalive` 通过 `() => keepaliveTick()` 间接引用，确保 fire-time 解析。
- `cleanup` 改 `clearTimeout`。

**修复后证据**：

    test_slow_reasoning_client_byte_interval PASSED
    test_usage_only_trickle_client_byte_interval PASSED
    gaps: [3.0, 3.0, 3.0, 1.0, 3.0, 3.0, 3.0, 3.0, 3.0]  MAX 3.0s ≤ 5.0s

    make verify-offline → 658 passed（与基线一致，无回归）

### K3 观察窗 — 未满（P2）

部署 06:13:03 CST，窗口 8/22 06:13 才到。需等满后再按 `isApiErrorMessage`
严格统计。

### K4 stream protocol error — 待定性（P1）

2026-08-21T01:16:44Z (09:16:44 CST) 一条 `API Error: stream protocol error`，
在 06:13 部署之后 3 小时。PRD 写于 06:36 看不到它。已排除保活 ping 形状
（`event: ping\ndata: {}` 缺 `"type":"ping"`）的嫌疑——真实 claude CLI
跑 usage_only_trickle 和 slow_reasoning 两次 rc=0，客户端完全接受。原因
待查，不能当偶发放过。结案条件应按标志位口径统计全部 API 错误，不只是
"response stopped arriving" 一类。
