# PRD：Claude MaaS 流式可靠性生产闭环 v2

> 状态：Ready for approval  
> 目标环境：`119.8.83.10`  
> 产品入口：`claude-maas`  
> 固定模型：华为云 MaaS `glm-5.2`  
> 文档日期：2026-08-20  
> 优先级：P0  
> 性质：缺口闭环 PRD；只覆盖 v1 尚未进入真实运行链路的部分

## 0. 结论

`PRD_MAAS_STREAM_WAIT_RELIABILITY_V1` **尚未完成**。

已交付的 Python 深模块及其单元/内存内 fake-upstream 测试，可作为语义原型和迁移测试 oracle；但它没有被当前生产服务导入或调用。目标主机实际处理 `claude-maas` 请求的仍是 2026-08-04 启动的 Node 协议适配器，仓库中没有该适配器的权威源码，线上 `/status` 返回 404。因而当前用户请求仍不具备 v1 所要求的三层超时、真实取消传播、finish-aware EOF、背压、生产并发保护和脱敏状态观测。

2026-08-20 复核证据：

| 项目 | 结果 |
|---|---|
| 仓库 HEAD | `d840f13` |
| 完整离线测试 | 516 passed |
| 生产进程 | Node，本地 `127.0.0.1:3000` |
| 生产启动时间 | 2026-08-04 10:24:48 CST |
| 生产产物 SHA-256 | `b0d7df992d24b2746652d4c1554e45b74c51fc34de4a1885be3bd355f522bd75` |
| Python 可靠性模块生产引用 | 0 |
| 生产 `/status` | HTTP 404 |
| 新可靠性版本发布/回滚证据 | 不存在；现有 release evidence 指向旧提交 `a5fbec4` |

所以，“516 tests passed”只能证明新增类在自己的测试模型中工作，不能证明线上 `Waiting for API response` 已获得可靠性修复。

## Problem Statement

### P0：实现与生产数据面断开

当前存在两条互不相连的实现链：

```text
测试链：fake upstream -> Python RequestHandler -> stream_reliability classes -> assertions

生产链：Claude Code -> Node adapter -> Huawei MaaS -> Node SSE conversion -> Claude Code
```

生产链没有调用测试链中的任何可靠性控制。继续完善 Python 类不会改变用户看到的行为。

### P0：旧生产适配器仍会把异常流伪装为成功

当前 Node 适配器：

- 在未看到可信 finish reason 时，仍以默认 `end_turn` 结束；
- 无条件补发 `message_delta` 与 `message_stop`；
- 工具参数 JSON 解析失败时降级为 `{}`，可能执行错误工具输入；
- SSE 已发头后发生异常，仍尝试返回普通 JSON 502，无法保证合法的 Anthropic SSE error；
- 没有 connect/header、idle、total 三层 watchdog；
- 没有将客户端断开接到上游 `AbortController`；
- `res.write()` 不处理 drain，工具参数与 SSE buffer 无生产上限；
- 没有请求级状态、并发准入和 loopback-only status。

### P0：项目架构文档互相冲突

项目主 README、基础 PRD 和 Operations 仍声明“无本地 HTTP 代理、无协议转换、无运行时 SSE/reasoning repair”，而流可靠性 v1 又要求把控制模块放入现有本地协议适配器。生产事实上已经运行本地 Node 适配器。

若不先完成架构变更控制，任何实现都会同时满足新 PRD、违反现有产品不变量。本 PRD 的批准应明确取代以下旧约束：

- 不允许任何本地 HTTP listener；
- 不允许任何运行时 SSE/finish/reasoning 兼容控制；
- MaaS 请求一定直接由 Claude Code 命中华为原生 Anthropic endpoint。

替代后的新不变量是：**只允许一个项目自有、仅 loopback 监听、单模型单上游、无路由决策的 Anthropic↔MaaS 协议适配器。** 它不是 Sidecar、模型 router 或 fallback gateway。

### P1：当前门禁没有鉴别力

- G-WAIT1 只断言新类能记录 hidden state，没有在旧生产实现上先失败。
- G-WAIT2–7 运行的是测试文件自建 `RequestHandler`，没有经过真实 HTTP、fetch、SSE writer 或客户端 socket。
- G-WAIT9 的“C256”是单线程顺序执行 256 次计数器调用，不是 256 个并发连接，也没有内存、timer、listener 或死锁检测。
- G-WAIT10–12 没有候选端口、产物 checksum、live E2E 或实际回滚证据。

### P1：原型实现仍有协议与安全缺口

即使未来选择复用其语义，现有原型也不能直接视为完成：

- content index 关闭后可以再次打开，不符合“每个 index 最多打开一次”；
- 孤立 `message_stop` 可以在没有 `message_start`、finish reason 或关闭全部 block 时被接受；
- 已发生 protocol error 后仍可能在 finalize 中合成成功终止；
- status 把未知来源地址视为 loopback，未 fail closed；
- status 缺少各状态数量、oldest active age、last success、last error；
- metrics 的 outcome/error 字段接受任意字符串，破坏输出字段白名单的零泄漏边界；
- 并发 guard 不是线程安全/事件循环原子语义，也未接真实准入路径。

## Goals

1. 让 v1 的可靠性控制真正进入 `claude-maas` 的生产请求数据面。
2. 将生产适配器权威源码、协议契约测试、部署方法纳入同一仓库。
3. 让正常长 reasoning 保持活动且不可见；真正静默、超总时限或提前 EOF 有界失败。
4. 让客户端取消在 1 秒内 abort 上游并释放全部资源。
5. 让错误在 HTTP headers 前后分别使用正确的 HTTP/Anthropic SSE 语义。
6. 让 C256 门禁验证真实本地 HTTP 适配器，而不是计数器类。
7. 建立候选端口、checksum、灰度切换和真实回滚证据闭环。
8. 保持 API URL、API key、`glm-5.2`、1M context、Exa 隔离与 plain Claude 隔离不变。

## Non-goals

- 不消除 Claude Code 自身的 `Waiting for API response` 文案。
- 不显示或记录 GLM reasoning，不合成 thinking/signature。
- 不关闭 thinking 来追求时延。
- 不引入 LiteLLM、CCR、Sidecar、OpenRouter、第二模型或 fallback。
- 不新增模型选择、动态路由、负载均衡或多租户 gateway。
- 不修改华为 MaaS URL 或 key，不把 secret 写入仓库、产物或证据。
- 不承诺真实 MaaS C256；live concurrency 默认最多 C8。
- 不优化 prompt、Agent 轮数、工具选择或模型质量。

## User Stories

1. As a `claude-maas` user, I want long hidden reasoning to keep the request alive, so that normal model work is not mistaken for a stall.
2. As a user, I want a truly silent upstream to fail with a stable retryable error, so that I never wait indefinitely.
3. As a user, I want a premature EOF excluded from successful history, so that later turns do not rely on incomplete output.
4. As a user, I want text and tool calls to remain Anthropic-compatible, so that Claude Code behavior does not regress.
5. As a user, I want malformed or oversized tool arguments to fail instead of becoming `{}`, so that an unintended tool action cannot run.
6. As a user, I want Ctrl-C or disconnect to cancel MaaS promptly, so that abandoned work stops consuming capacity.
7. As an OAuth user, I want plain `claude` unchanged, so that MaaS infrastructure cannot intercept Anthropic OAuth traffic.
8. As a MaaS-only user, I want all model traffic to remain `glm-5.2` on the configured Huawei endpoint, so that there is no silent fallback.
9. As an operator, I want a safe status view of connecting, hidden-active, visible-streaming and terminal states, so that slow and stuck requests can be distinguished.
10. As an operator, I want status and logs to expose only enumerated metadata, so that prompts, responses, reasoning, tool data and credentials cannot leak.
11. As an operator, I want connect, idle and total timeout values validated at startup, so that invalid configuration fails before accepting traffic.
12. As an operator, I want client backpressure respected, so that a slow reader cannot create unbounded memory growth.
13. As a release owner, I want old and candidate adapters tested through the same external HTTP contract, so that the gate proves the defect and its fix.
14. As a release owner, I want the deployed checksum tied to a source commit, so that production behavior is reproducible.
15. As a release owner, I want a tested one-command rollback that leaves URL/key untouched, so that a bad release can be reversed safely.
16. As a capacity owner, I want C256 local connections to produce bounded admission/rejection and no deadlock, so that adapter limits are real.
17. As a security owner, I want status access to fail closed unless the socket peer is positively identified as loopback, so that future bind mistakes do not expose diagnostics.
18. As a maintainer, I want one canonical runtime implementation, so that Python and Node semantics cannot silently drift.

## Architecture Decision

### Considered approaches

| Approach | Advantages | Risks | Decision |
|---|---|---|---|
| A. Implement the reliability controller in the existing Node adapter runtime | Smallest production change; native `fetch`, `AbortController`, HTTP/SSE backpressure and socket lifecycle; no new process | Requires translating the Python prototype semantics | **Selected** |
| B. Replace the complete adapter with a Python HTTP service | Can reuse classes directly | Rewrites a working protocol converter; changes process/runtime/deployment; larger rollback surface | Rejected for v2 |
| C. Keep Node and invoke Python as subprocess/Sidecar | Reuses code superficially | Two processes, cancellation and backpressure cross-process complexity, violates no-Sidecar invariant | Rejected |

### Approved target architecture

```text
claude-maas
    -> single loopback-only Node protocol adapter
        -> one RequestLifecycleController per request
        -> fixed Huawei MaaS endpoint + fixed glm-5.2
```

The adapter performs only deterministic protocol conversion and reliability control. It cannot select providers/models, retry on another model, proxy OAuth credentials, or expose a non-loopback listener.

The current Python implementation may be used temporarily as a semantic oracle. At release there must be exactly one authoritative runtime implementation. Python code that is not executed in production must be labeled test-only/non-authoritative or removed; it must not be cited as proof of production behavior.

## Required Components

### 1. Version-controlled production adapter

- Move the authoritative Node adapter source into the project.
- Produce a deterministic deployable artifact from that source.
- Keep host config and secrets external; deployment must not overwrite the existing URL/key environment file.
- Embed or expose a non-secret build identity: source commit plus artifact SHA-256.

### 2. RequestLifecycleController

One controller instance per accepted request owns:

- state transitions;
- connect/header, idle and total timers;
- last application-layer upstream byte time;
- upstream AbortController;
- client aborted/response closed/process shutdown listeners;
- open content-block registry and all-ever-used index set;
- trustworthy finish reason;
- backpressure waits;
- size accounting;
- sanitized request metrics;
- exactly-once cleanup.

All terminal paths call one idempotent finalize/abort routine. No request-level timer, listener, buffer or metric object may survive terminal cleanup.

### 3. Active watchdogs

- Connect/header timeout starts immediately before upstream fetch and is cancelled only after valid response headers.
- Idle timeout is a real scheduled watchdog, refreshed by every upstream body byte/chunk including reasoning, usage, ping, text and tool fragments.
- Total timeout is scheduled once and never refreshed.
- Timeouts abort fetch/body iteration and emit the correct pre-header HTTP error or post-header SSE error.
- Passive `check_timeout()` methods that only run when another chunk arrives do not satisfy this requirement.

### 4. Reasoning observation and filtering

- Inspect each decoded upstream delta before filtering.
- Count reasoning chunks and UTF-8 bytes and refresh upstream activity.
- Strip reasoning fields before any client write, log, metric label, status object, error or snapshot.
- Mixed reasoning+visible deltas preserve only visible content/tool fields.
- Never synthesize visible progress, thinking block or signature.

### 5. Strict Anthropic stream state machine

- Exactly one `message_start` and, on success, exactly one `message_stop`.
- A content index may be opened only once for the entire stream, not merely once concurrently.
- Deltas must match the currently open block type.
- `message_stop` is valid only after `message_start`, all blocks are closed, a trustworthy finish reason exists, and no protocol error has occurred.
- Once a protocol error occurs, success finalization is permanently impossible.
- EOF without trustworthy finish reason is `MAAS_STREAM_EOF`.
- A finish reason permits local completion only in protocol order: flush buffered decoder data, close open block, emit message_delta if needed, emit message_stop.
- Partial, malformed or oversized tool arguments are never converted to `{}` and never emitted as executable tool input.

### 6. Error boundary

Before response headers, return sanitized Anthropic-shaped JSON with correct HTTP status. After SSE begins, emit exactly one legal `event: error` and close without `message_stop`.

| Code | HTTP | Retryable | Notes |
|---|---:|---|---|
| `MAAS_CONNECT_TIMEOUT` | 504 | yes | no response headers |
| `MAAS_IDLE_TIMEOUT` | 504 | yes | no application bytes |
| `MAAS_TOTAL_TIMEOUT` | 504 | yes | wall-clock bound |
| `MAAS_UPSTREAM_HTTP` | safe mapping | 429/5xx yes; auth/other 4xx no | preserve safe status and bounded Retry-After only |
| `MAAS_STREAM_EOF` | 502 | yes | no trustworthy finish |
| `MAAS_STREAM_PROTOCOL` | 502 | no | malformed framing/state |
| `MAAS_TOOL_ARGS_TOO_LARGE` | 422 | no | never execute |
| `MAAS_CLIENT_ABORTED` | no write | no | peer is gone |
| `MAAS_OVER_CAPACITY` | 503 | yes | include bounded Retry-After |

Raw upstream bodies and raw exception messages must not be forwarded because they may contain URLs, headers or content. Client messages use fixed safe templates plus stable codes.

### 7. Backpressure, limits and concurrency

- Await `drain` whenever a client write returns false; abort the wait on disconnect/timeout.
- Enforce independent configurable limits for request body, undecoded SSE buffer, one SSE event, aggregate tool arguments and active requests.
- Limits count bytes, not JavaScript string code units.
- Concurrency admission is atomic within the event loop and wraps the real request lifecycle.
- Over-capacity requests fail before upstream fetch and are not queued.
- Capture active and peak concurrency; never record request content.

### 8. Sanitized status and metrics

Retain `/health` and add a separate status endpoint that performs no MaaS call. Access is allowed only when the actual socket peer address is positively loopback; missing/unknown addresses fail closed.

Status fields are a fixed schema:

- build version and artifact checksum prefix;
- uptime;
- active and peak request counts;
- count by enumerated state;
- oldest active age;
- last success time;
- last stable error code;
- configured connect/idle/total timeout and capacity values.

Outcome, error code and state accept enums only. Dynamic prompt/response/tool/URL/exception strings can never become metric values.

### 9. Architecture documentation and contract

On approval and implementation, update the project README, foundational PRD, Operations and architecture tests so they all state the same rule:

- exactly one project-owned loopback protocol adapter is allowed for `claude-maas`;
- no Sidecar, LiteLLM, CCR, OpenRouter, fallback or second provider/model;
- plain OAuth Claude never points to it;
- listener address must equal loopback and is verified at startup/test time;
- runtime source and deployment checksum are version-controlled and auditable.

The previous blanket ban on any local listener/runtime SSE control is superseded only to this narrow extent.

## Testing Decisions

### A. External-contract red/green harness

Start both legacy and candidate Node adapters as child processes on ephemeral loopback ports. Drive them through real HTTP sockets against the same deterministic fake upstream server. Do not import internal production classes in acceptance tests.

The frozen legacy artifact must demonstrate at least these red failures:

1. hidden reasoning cannot be observed as activity;
2. EOF without finish reason becomes false success;
3. client disconnect does not abort upstream;
4. permanent silence has no required idle failure;
5. malformed tool JSON degrades to `{}`;
6. status is absent.

The candidate must turn the same tests green. Store the legacy artifact checksum, candidate commit and test output as evidence.

### B. Deterministic fault matrix

The fake upstream must support:

- accepts TCP but never returns headers;
- headers then silence;
- reasoning every N milliseconds then valid text/tool/finish;
- continuous reasoning past total timeout;
- fragmented UTF-8 and fragmented SSE lines;
- usage/ping-only activity;
- malformed JSON/SSE;
- upstream 401, 403, 429 with Retry-After, 5xx;
- EOF before finish, EOF midway through tool args;
- finish reason with missing local terminal events;
- oversized request/event/buffer/tool arguments;
- delayed or blocked client reads.

Each case asserts client wire result, exact terminal state, upstream abort, cleanup, error code/retryability, and zero sensitive-data leakage.

### C. Real concurrency gate

- C1/C16/C64/C256 mean simultaneous HTTP client connections to the candidate adapter.
- Use a barrier so admitted requests overlap at the fake upstream.
- Configure a known capacity lower than C256 and assert admitted count never exceeds it; excess clients receive 503 promptly.
- Assert no deadlock, process crash, unhandled rejection, unbounded queue, post-test active request, timer/listener growth or sustained memory growth.
- Report wall time, peak concurrency and peak RSS with explicit thresholds chosen from a measured C1 baseline.

### D. Protocol and security tests

- Validate raw SSE framing and exact message/block ordering.
- Validate no success stop after any protocol error.
- Validate closed index cannot reopen.
- Validate unknown status peer fails closed.
- Inject high-entropy canaries into key, URL query, prompt, response, reasoning, tool args/results and exception text; scan stdout, stderr, journal, status, HTTP/SSE errors and evidence for exact zero matches.
- Validate `outcome`, `state`, `error_code` reject arbitrary strings.

### E. Live candidate canary

Run the candidate on an alternate loopback port using the existing host configuration read-only. Do not persistently edit `claude-maas` config; override the candidate base URL only for the canary process.

Required live checks:

1. health/status without upstream billing;
2. non-streaming text;
3. streaming start/delta/stop;
4. automatic and forced tool use;
5. real Claude Code `--print` and Bash tool round trip;
6. `modelUsage` set exactly `{glm-5.2}`;
7. `contextWindow == 1000000`;
8. Exa remains available only to `claude-maas`;
9. plain Claude binary/config/network isolation unchanged;
10. URL/key fingerprints equal pre-change values without exposing values;
11. live C1 repeat and budgeted live C8; no C256 cloud test.

## Acceptance Gates

### G-CLOSE1：生产接线

Repository-owned candidate adapter handles a real HTTP request and its request path constructs the lifecycle controller. A test that removes/bypasses the controller must fail.

### G-CLOSE2：真实红—绿

The same external contract suite fails on the frozen legacy artifact for the original defect and passes on the candidate. A comment describing what a naive adapter would do is not evidence.

### G-CLOSE3：三层主动超时

Connect, idle and total fault cases terminate within configured threshold +1 second, abort upstream and emit correct pre/post-header error semantics.

### G-CLOSE4：hidden activity

Reasoning-only activity longer than idle threshold succeeds when total is not exceeded; reasoning canary appears nowhere in client or operational surfaces.

### G-CLOSE5：终止与工具安全

EOF without finish fails; protocol error can never finalize as success; every successful stream has one legal stop; partial/invalid/oversized tool arguments are never executable.

### G-CLOSE6：取消、背压与清理

Client disconnect aborts upstream within 1 second; blocked drain is cancellable; all terminal cases leave zero active requests and no request-owned timer/listener.

### G-CLOSE7：状态与零泄漏

Real loopback status reports required aggregates during a long reasoning request. Non-loopback and unknown peer access are denied. Full canary scan is zero-match.

### G-CLOSE8：真实 C256

Socket-level C256 completes without deadlock/crash/unbounded queue; configured capacity is never exceeded; excess requests receive 503; memory/timer/listener thresholds pass.

### G-CLOSE9：架构一致性

README、foundational PRD、Operations、architecture contract and deployed topology agree on the narrowly allowed loopback adapter. No LiteLLM/CCR/Sidecar/fallback/second model; plain Claude remains isolated.

### G-CLOSE10：候选 live 回归

All offline gates plus alternate-port live text/stream/tool/Claude Code/Exa/model/1M/config-fingerprint checks pass.

### G-CLOSE11：部署一致性

Release evidence links source commit, source tree, candidate artifact SHA-256, installed artifact SHA-256, service start time and gate summary. Candidate and installed hashes match; evidence contains no secret.

### G-CLOSE12：真实回滚演练

After candidate cutover, run one-command rollback to the saved legacy artifact, verify health/minimal text and unchanged URL/key fingerprints, then redeploy the candidate and repeat the smoke gates. Record both transitions.

## Release Procedure

1. Freeze and checksum the current production artifact.
2. Build/copy candidate deterministically from a clean source commit.
3. Run full offline suite and external-contract fault/C256 gates.
4. Start candidate on alternate loopback port with existing config read-only.
5. Run live candidate gates and secret scan.
6. Confirm zero active production requests or complete a bounded drain window.
7. Preserve the old artifact as rollback target; atomically install the candidate and restart the service.
8. Verify installed checksum, start time, health/status, text/stream/tool and Claude Code smoke.
9. Perform the rollback drill, then restore candidate and reverify.
10. Write immutable release evidence containing only safe metadata.

Deployment code and host configuration remain separate. No step edits API URL/key values, and no command may print them; only one-way fingerprints may be compared.

## Rollback Requirements

- One non-interactive command restores the saved, checksummed prior artifact and restarts the service.
- Rollback never restores or edits the host secret/config file.
- A failed deployment automatically stops before touching the production artifact.
- If post-cutover smoke fails, rollback is mandatory before further diagnosis.
- Operations documentation must no longer claim that rollback requires no service restart once the module is production-wired.

## Definition of Done

1. The production adapter source and deploy recipe are version-controlled.
2. Exactly one canonical runtime implementation exists and is used by the systemd service.
3. G-CLOSE1 through G-CLOSE12 all pass with timestamped evidence.
4. The old implementation demonstrably fails the red contract and the candidate passes it.
5. Real HTTP paths enforce active timeouts, cancellation, strict termination, backpressure, size limits and concurrency.
6. Real status is loopback-only, fail-closed and shows hidden-active versus idle safely.
7. `glm-5.2`, 1M context, API URL/key fingerprints, Exa isolation and plain Claude isolation are unchanged.
8. Source commit, candidate hash and deployed hash match release evidence.
9. Actual rollback and redeploy have both been exercised successfully.
10. Logs, status, errors, journal and evidence pass exact secret/content canary scans.
11. Architecture docs and automated invariants no longer contradict the approved topology.
12. Full test suite passes from a clean worktree; no unrelated user changes are modified.

## Traceability to v1

| v1 gate | Current status | v2 closure |
|---|---|---|
| G-WAIT1 | Not proven red on legacy runtime | G-CLOSE2 |
| G-WAIT2–4 | Class-level fake only | G-CLOSE3–4 |
| G-WAIT5 | Prototype has state-machine gaps; production defaults EOF to success | G-CLOSE5 |
| G-WAIT6 | Callback class only; no real fetch abort | G-CLOSE6 |
| G-WAIT7 | Partial object scan only | G-CLOSE7 |
| G-WAIT8 | Static diff only; docs conflict | G-CLOSE9–10 |
| G-WAIT9 | Sequential counter, not concurrent adapter | G-CLOSE8 |
| G-WAIT10 | No candidate/deployed linkage | G-CLOSE11 |
| G-WAIT11 | Offline tests pass; no new production/live behavior | G-CLOSE10 |
| G-WAIT12 | No new-version rollback drill | G-CLOSE12 |

## Approval Boundary

Approving this PRD authorizes one narrow architecture change: the repository may own and deploy the already-required loopback-only MaaS protocol adapter with reliability control. It does **not** authorize a Sidecar, general HTTP router, multiple providers/models, fallback, OAuth proxying, or changes to the existing Huawei URL/key.

