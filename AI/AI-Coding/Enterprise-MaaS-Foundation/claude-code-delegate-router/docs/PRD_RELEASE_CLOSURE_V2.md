# PRD：发布收口 v2（容量泄漏 + 运行态 + 可观测性）

状态：D1-D4 已落地并部署（commit 8a35e6b），R3 观察窗进行中，R4 待复现定性
前置：
- `docs/PRD_TIME_DRIVEN_KEEPALIVE_V1.md`（实现已交付，commit `b7c986e`）
- `docs/PRD_KEEPALIVE_CLOSURE_V1.md`（K1/K2 代码侧已修，**尚未提交**）

核查时间：2026-08-21 22:35 CST，核查人：独立复验（非实施方自评）

## 0. 产品摘要

**K1/K2 已真修，独立复验通过。但发布仍被 5 项阻塞，其中 1 项是 P0。**

独立 A/B 台架（`/root/ping-probe/gap.py`，旧代码取自 `git show b7c986e:adapter/server.js`）：

| 配置 | OLD `b7c986e` | NEW 工作树 | 判定 |
| --- | --- | --- | --- |
| `INTERVAL=3` slow_reasoning | MAX 6.0s > 5.0 | MAX 3.0s | 反向门成立 |
| `INTERVAL=15`（生产值）slow_reasoning | MAX 20.0s > 17（违反 PRD） | MAX 15.0s | 生产配置下合规 |

`pytest tests/test_keepalive.py` → 6 passed。门禁阈值已是常数容差且在 `INTERVAL=3`
下具备鉴别力。`cleanup` 中的 `clearTimeout`（`server.js:616`）正确。

**本轮的核心发现不是保活，而是一条一直存在、比 K1 严重的容量泄漏。**

## 1. 缺口

### R1 — 并发槽永久泄漏，8 次即全站不可用（P0，发布阻塞）

实测（生产实例 MainPID 11681）：

    22:35:13  active_requests=1  oldest_active_age_ms=8110493   (2h15m)
    22:35:23  active_requests=1  oldest_active_age_ms=8120521   (仍在增长)
    ss -tnp | grep :3000  →  无任何 ESTABLISHED 连接
    MAAS_TOTAL_TIMEOUT = 600000 ms

客户端连接已不存在，请求槽被占用 2h20m，超出 total timeout **13 倍**且持续增长。
`capacity=8`，泄漏 8 次后 `acquire()` 恒返回 false，适配器完全停止接单，
只能靠重启恢复。

根因（结构性）：`adapter/server.js:615` 的 `cleanup(ctrl)` **不在 `finally` 中**。

    } catch (err) { ... }          // 只兜住 for-await 内的抛错
    ...  // 关块、工具块、ctrl.finalize()、clientWrite —— 均可抛
    if (!res.writableEnded) res.end();
    cleanup(ctrl);                 // ← 顺序执行，任何提前退出都跳过它

    function cleanup(c) {
      if (keepaliveTimer) clearTimeout(keepaliveTimer);
      concurrencyGuard.release();          // 全仓库唯一释放点
      activeControllers.delete(c.requestId);
      res.removeListener("close", onClose);
    }

`concurrencyGuard.release()` 在整个仓库只有这一个调用点（`server.js:617`）。
`for await` 不返回、或 catch 之后到 `cleanup` 之间任一处抛错，槽即永久泄漏。
`onClose` 只调 `ctrl.abort()`，不释放槽；total watchdog 同理。

**为什么现有门禁没抓到**：`PRD_KEEPALIVE_CLOSURE_V1.md` §4 记的
"无容量泄漏｜连打 10 次中止后 `active_requests=0`" 只覆盖 client-abort 这条
**会正常释放**的路径，对本缺陷零鉴别力。这是本仓库反复出现的同一种失真：
用一条走得通的路径去证明"没有泄漏"。

回归性质：该缺陷存在于 `b7c986e` 及更早版本，**不是本轮保活改动引入的**。

### R2 — 改动未提交、线上仍是旧代码（P1，发布阻塞）

    git log -1        → b7c986e（保活特性，非本轮修复）
    git status        → M adapter/server.js
                        M tests/test_keepalive.py
                        ?? docs/PRD_KEEPALIVE_CLOSURE_V1.md
    仓库 adapter/server.js       607c2a1dba5f7fb3d32d3d113d3c422e457f25af9...
    /opt/.../server.js           b9c6a7e2f47266ecb5152d320f5257df53d38ed7...
    MainPID 11681，ActiveEnterTimestamp 2026-08-21 06:13:03 CST（未变）

即 K1 修复**尚未进入生产**。线上此刻最坏字节间隔仍是 30s。
"测试全过"与"线上已修"是两件事。

### R3 — K3 观察窗因部署而重新计时，且统计口径过窄（P1）

原窗口以 06:13:03 部署为起点，本应 8/22 06:13 满 24h。一旦部署新构建，
被观察的制品发生变化，窗口需重新计时。

另：`PRD_KEEPALIVE_CLOSURE_V1.md` §3.4 只统计 `response stopped arriving`
一句话。按该口径部署后确为 0，但按 `isApiErrorMessage === true` 的全量口径
**不是 0**——见 R4。结案口径必须是标志位全量，不得挑单一文案。

统计位置必须是 `/root/.claude-maas/projects/`（launcher 设
`CLAUDE_CONFIG_DIR=$HOME/.claude-maas`）。在 `~/.claude/projects/` 下统计会得到
一个"干净的 0"，无证据力。

### R4 — 09:16:44 的 stream protocol error 已定性来源，根因未知（P2）

    2026-08-21T01:16:44.184Z (= 09:16:44 CST)  API Error: stream protocol error
    /root/.claude-maas/projects/-root/acd37b29-....jsonl

来源已确定：即适配器自身的 `MAAS_STREAM_PROTOCOL`
（`lifecycle.js:318` `_fail(ErrorCodes.STREAM_PROTOCOL, State.UPSTREAM_FAILED)`
→ `server.js:113` 文案 "stream protocol error"），当前 `/status` 的
`last_error_code` 仍是该值。

已排除的嫌疑：保活 ping 形状。适配器发 `event: ping` + `data: {}`（缺
`"type":"ping"`，偏离 Anthropic 官方形状），但用**真实 `claude` CLI** 实测
`usage_only_trickle`（2s 一次 ping，全程 81s）与 `slow_reasoning`，两次 `rc=0`，
客户端完全接受。ping 不是原因。

根因查不下去的原因是 R5。

### R5 — 生产可观测性缺失，任何线上故障不可诊断（P1，发布阻塞）

    journalctl -u claude-code-maas-proxy  →  全部历史 43 行，除启动横幅无任何内容
    adapter/server.js 中 console.error 仅 3 处，全部是启动期参数校验
    /status 的 last_error_code 是单槽，后写覆盖先写
    state_counts 至今只有 {"client_aborted": 1}

一个对外发布的服务，其全部诊断面是一个会被覆盖的单槽快照。R4 无法定性正是
这一设计的直接后果，且发布后每一次线上故障都会重复这一处境。

## 2. 决策

### D1：`cleanup` 移入 `finally`，并补一条兜底释放

- `streamMaas` 的 acquire 之后整体包 `try { ... } finally { cleanup(ctrl) }`，
  `cleanup` 做成幂等（`_released` 标志，重复调用不重复 `release()`）。
- `onClose` 与 total watchdog 的终态路径同样走 `cleanup`，不再依赖顺序执行抵达。
- 兜底：`activeControllers` 增加清扫器，对 `age > TOTAL_TIMEOUT + 60s` 的条目
  强制 `cleanup` 并记 `MAAS_SLOT_REAPED`。兜底是安全网，**不替代** D1 的结构修复。

### D2：R1 反向门（必须先失败）

新增 `tests/test_capacity_leak.py`：

1. **注入式**：让 `ctrl.finalize()` 抛错（或用 `MAAS_TEST_THROW_AFTER=finalize`
   测试钩子），发一个请求，断言请求结束后 `active_requests == 0`。
   当前实现必须 **FAIL**。
2. **饱和式**：以 `MAAS_MAX_CONCURRENCY=2` 触发 2 次泄漏路径，断言第 3 个请求
   仍能被服务（非 429/503）。当前实现必须 **FAIL**。
3. 两条门禁在修复前的 FAIL 输出与修复后的 PASS 输出都要留证据。

禁止用 client-abort 路径证明"无泄漏"——该路径本来就会释放，无鉴别力。

### D3：结构化请求日志（最小可诊断集）

每个请求终态写一行 JSON 到 stdout（journald 收），字段：
`request_id`、`state`、`error_code`、`duration_ms`、`upstream_status`、
`client_bytes`、`upstream_chunks`、`outcome`。
`/status` 增加 `error_counts`（按 code 累计，不覆盖）与
`recent_errors`（环形缓冲，最近 20 条，含时间戳与 code）。

**不记录**：prompt/completion 正文、reasoning 内容、API key。
新增 `tests/test_observability.py` 断言：终态必写一行；日志行中不含 canary
`CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh`；不含 key 片段。

### D4：ping 形状对齐官方（P3，顺手）

`data: {}` → `data: {"type":"ping"}`。实测客户端两种都接受，但没有理由偏离
官方形状。与 R4 无因果关系，不得记为 R4 的修复。

### D5：不采用

- 不改 `MAAS_KEEPALIVE_INTERVAL` 默认值（15s 合理）。
- 不改 idle/total 超时语义（150s / 600s 已生效并验证）。
- 不因 R1 回退保活改动（两者无关，保活修复独立成立）。
- 不用重启掩盖 R1（重启会杀掉在途流，是事故不是修复）。

## 3. 验收标准

1. **R1 反向门**：D2 的两条用例，修复前 FAIL、修复后 PASS，双向证据齐全。
2. **R1 生产验证**：部署后连续观察 ≥ 6h，`/status` 的 `active_requests` 在
   无在途连接时（`ss -tnp | grep :3000` 为空）必须为 0。至少采样 3 次。
3. **R2 运行态新鲜度**：`git status` 干净；`/opt` 与仓库 `server.js`、
   `lifecycle.js` 的 SHA-256 逐一相等；MainPID 发生变化；`/status` 可达。
   三项缺一不可。
4. **R3 观察窗**：以**新构建的部署时刻**为起点满 24h，在
   `/root/.claude-maas/projects/` 下按 `isApiErrorMessage === true` 全量统计，
   新增为 0。不得只统计单一文案，不得用文本 grep（文本 grep 已产生过 4 条假阳性）。
5. **R5 可观测性**：D3 的门禁通过；且在窗口内至少能从 journald 复原一次
   完整请求终态（人工触发一次 `MAAS_IDLE_TIMEOUT` 验证日志确实落盘）。
6. **R4**：在 D3 上线后，若窗口内复现 `MAAS_STREAM_PROTOCOL`，须给出根因；
   若未复现，记为"已具备诊断能力的未复现项"，**不得记为已修复**。
7. **回归**：`make verify-offline` 全绿，且总数 ≥ 658 + 新增用例数（本轮基线
   658 passed 是在 K1 修复**之前**取的，修复后需重新取基线）。
8. `make verify-live` 7 道 gate 全绿；真实 HOME（`~/.claude/`）配置未被改动。

## 4. 实施顺序

1. 先提交当前 K1/K2 改动（含 `PRD_KEEPALIVE_CLOSURE_V1.md`），不要与 R1 混在一个 commit
2. D2 写反向门 → 跑出 FAIL，钉死 R1
3. D1 结构修复 → 同一门禁转 PASS
4. D3 结构化日志 + 门禁
5. D4 ping 形状
6. `make verify-offline` 重取基线 → 部署（`adapter/deploy.sh`）→ §3.3 运行态三项核对
7. §3.2 的 6h 容量观察 + §3.4 的 24h 错误窗口（并行计时）
8. 两个窗口都满且 §3 全项达标 → 出 v1.1 release notes，做发布决定

## 5. 发布决定

在 §3 全部 8 项达标前，**不发布**。

R1 单独即构成 P0：一个会在 8 次故障后完全停摆、且无日志可诊断的服务，
不具备对外发布条件。R2 意味着当前线上跑的仍是带 K1 缺陷的旧构建。
