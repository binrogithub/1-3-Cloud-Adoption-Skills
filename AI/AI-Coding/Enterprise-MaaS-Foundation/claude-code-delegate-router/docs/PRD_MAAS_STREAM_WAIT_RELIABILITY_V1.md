# PRD：Claude MaaS 流式等待可靠性与可观测性 v1

> 状态：Ready for implementation  
> 目标环境：`119.8.83.10`  
> 产品入口：`claude-maas`  
> 目标模型：华为云 MaaS `glm-5.2`  
> 文档日期：2026-08-20  
> 优先级：P0（可靠性与可诊断性）

## 0. 执行摘要

用户在 `claude-maas` 交互界面中长时间看到 `Waiting for API response`，容易将正常的 GLM 隐式 reasoning 长尾误判为 API 断连，也无法判断请求是否仍在推进。

2026-08-20 在目标环境的现场证据表明：Claude Code、本地 MaaS 协议适配器和华为云 MaaS 之间的 TCP 连接均保持 `ESTABLISHED`；华为 MaaS 在等待期间持续返回 `reasoning_content`，但当前适配器只转发 `delta.content` 和最终工具调用，因此 Claude Code 在首个可见文本或工具事件出现前没有可展示内容。一次被用户认为“卡住”的请求最终在约 110 秒后成功完成，并产生 7 个结构化工具调用。后续完整会话也以 `end_turn` 正常结束。

因此，本 PRD 不把“所有 Waiting 都消失”设为目标，也不关闭 thinking、不暴露思维链、不伪造 Anthropic thinking signature。v1 的目标是：准确区分“上游仍在持续 reasoning”与“真正断流”，让真正的无响应在有界时间内失败并可重试，补齐安全的流终止语义，并提供不含敏感内容的实时可观测证据。

## Problem Statement

### 用户问题

当 `claude-maas` 长时间显示 `Waiting for API response` 时，用户无法回答以下问题：

1. MaaS 是否仍在推理？
2. 网络或代理是否已经断流？
3. 请求是否会最终完成？
4. 是否应该继续等待、主动中断或重新发送？
5. 如果请求失败，失败发生在 Claude Code、本地协议适配器还是华为云 MaaS？

当前实现将 GLM 的 `reasoning_content` 作为不可见的 provider artifact 丢弃，这是保护 Claude Code 协议兼容性和避免无效 thinking signature 的正确方向；但实现没有把“收到不可见 reasoning 字节”记录为上游活动，也没有完整的空闲超时、总时限、客户端断开传播、流式终止修复和请求级观测状态。这使“仍在工作”和“已经卡死”在用户与运维视角下表现相同。

### 已验证事实

1. 目标服务在排查期间保持 active，未发生自动重启。
2. Claude Code 到本地适配器、本地适配器到华为云 MaaS 的 TCP 连接均保持建立。
3. 在一个约 64K input-token 的请求中，MaaS 持续向适配器返回数据，而 Claude Code 在首个可见内容前只收到协议起始事件。
4. 该请求最终约 110 秒完成，usage 为约 64,318 input tokens、4,110 output tokens，并产生 7 个工具调用。
5. 同一会话后续增长到约 104,202 input tokens，最终以 `end_turn` 成功结束；没有发现 400、401、429 或 5xx API 错误记录。
6. 当前适配器识别并转发 `delta.content`，缓存工具调用，但没有处理 `delta.reasoning_content`。
7. 原 `litellm-auto-plugin` 同样不会把 GLM reasoning 展示给 Claude Code：它先修复 thinking/text SSE 块，再由 GLM reasoning filter 删除 thinking、signature 并压缩索引。
8. 原 plugin 没有让正常长 reasoning 在 Claude Code 中显示进度；它主要解决协议正确性、提前结束和可观测性问题。

### 根因

根因不是 API URL、API key、服务进程或 TCP 连接失效，而是两个因素叠加：

- GLM-5.2 在复杂、长上下文任务中可能长时间生成 reasoning，首个可见文本或工具调用有明显长尾；
- 当前 OpenAI-to-Anthropic 流适配器丢弃 reasoning，但没有把 reasoning 字节纳入活动检测和安全的请求状态机，导致正常长尾与真正断流不可区分。

## Solution

构建一个请求级的“流活动与终止控制”深模块，置于现有单模型协议适配器内部。该模块不理解 prompt 内容，也不改变模型路由；它只消费上游流的结构元数据与字节活动，维护请求状态、控制计时器、传播取消、保证 Anthropic SSE 终止合法，并输出脱敏指标。

从用户视角：

- 正常 reasoning 可以继续运行，不会因“暂时没有可见文本”而被误杀；
- 真正没有任何上游字节的请求会在配置的空闲窗口后有界失败，由 Claude Code 显示可重试错误；
- 运维可以判断请求处于连接、隐式 reasoning、可见输出、工具生成、完成、客户端取消或超时中的哪一类状态；
- 请求不会在客户端退出后继续占用 MaaS 资源；
- 上游提前断流不会被伪装成成功回答。

### 核心状态机

每个请求拥有独立状态，不允许跨请求共享可变流状态：

1. `accepted`：本地已接受并校验请求。
2. `connecting`：正在等待上游连接及响应头。
3. `upstream_active_hidden`：持续收到 reasoning 或其他不可见上游字节，但尚无可见内容。
4. `visible_streaming`：已向 Claude Code 发送文本或结构化工具事件。
5. `completing`：已看到可信的上游 finish reason，正在关闭内容块。
6. `completed`：已发送合法的 `message_stop`。
7. `client_aborted`：客户端断开，已取消上游请求。
8. `connect_timeout`：在响应头时限内未连接成功。
9. `idle_timeout`：在空闲时限内没有收到任何上游字节。
10. `total_timeout`：请求超过总 wall-clock 上限。
11. `upstream_failed`：上游返回错误、格式不可恢复或在没有可信 finish reason 时提前结束。

`upstream_active_hidden` 是本 PRD 的关键状态：它代表 UI 可能仍显示 Waiting，但系统已经证明 MaaS 正在工作。

## User Stories

1. As a `claude-maas` user, I want a long reasoning request to remain alive while MaaS is still sending data, so that normal model thinking is not mistaken for a hang.
2. As a `claude-maas` user, I want a truly silent upstream request to fail within a bounded period, so that I do not wait forever.
3. As a `claude-maas` user, I want Claude Code to receive a valid retryable API error after a real stall, so that the session can recover without corrupting history.
4. As a `claude-maas` user, I want successful text and tool responses to remain unchanged, so that reliability work does not alter model behavior.
5. As a `claude-maas` user, I want my current MaaS URL and key to remain unchanged, so that the repair does not create a credential migration.
6. As a `claude-maas` user, I want the model to remain `glm-5.2`, so that the repair cannot silently fall back to another model.
7. As a `claude-maas` user, I want the context window to remain 1M, so that reliability work does not reduce session capacity.
8. As a user who interrupts Claude Code, I want the in-flight upstream request cancelled promptly, so that I stop consuming MaaS capacity after cancellation.
9. As a user resuming a session, I want incomplete upstream output excluded from successful history, so that subsequent turns are not based on a false completion.
10. As a user receiving tool calls, I want structured `tool_use` blocks preserved, so that tools continue to execute through the standard Claude Code UI.
11. As a security owner, I want reasoning content to remain hidden from Claude Code, so that provider-internal reasoning is not exposed or persisted.
12. As a security owner, I want logs to omit prompts, responses, tool arguments, URLs containing credentials and API keys, so that diagnostics do not become a secret store.
13. As an operator, I want to see whether active requests are connecting, receiving hidden reasoning or streaming visible content, so that I can distinguish slow from stuck.
14. As an operator, I want per-request time-to-headers, first-upstream-byte, first-visible-delta and total duration, so that latency can be attributed to the correct boundary.
15. As an operator, I want hidden reasoning byte and chunk counts without content, so that I can prove upstream activity safely.
16. As an operator, I want stable error codes for connect timeout, idle timeout, total timeout, upstream HTTP failure, malformed stream and client abort, so that incidents can be grouped automatically.
17. As an operator, I want liveness and sanitized aggregate request status exposed only on loopback, so that I can inspect health without issuing a paid model request.
18. As an operator, I want an upstream failure before response headers represented as an HTTP error, so that clients receive a conventional failure.
19. As an operator, I want a failure after SSE has begun represented as an Anthropic SSE error event, so that the wire protocol remains valid.
20. As an operator, I want missing terminal events synthesized only when a trustworthy finish reason has already been received, so that incomplete answers are never reported as successful.
21. As an operator, I want a premature EOF without a finish reason treated as failure, so that data loss is visible.
22. As an operator, I want timers and abort handlers cleaned up for every terminal state, so that long-running service memory does not leak.
23. As an operator, I want response writes to respect backpressure, so that slow clients cannot create unbounded buffers.
24. As a release owner, I want deterministic fault-injection tests for silent upstreams and premature EOF, so that the bug cannot regress without a real cloud incident.
25. As a release owner, I want the deployed adapter checksum to match version-controlled source, so that production behavior is reproducible.
26. As a release owner, I want configuration and secrets to stay outside version-controlled code, so that code deployment cannot overwrite host credentials.
27. As a release owner, I want a canary on an alternate loopback port before cutover, so that production is not used as the first test environment.
28. As a release owner, I want a one-command rollback to the prior adapter artifact, so that a protocol regression can be reversed quickly.
29. As a capacity owner, I want C256 deterministic adapter testing to produce no deadlock or unbounded memory growth, so that local concurrency limits are understood independently of MaaS limits.
30. As a capacity owner, I want live concurrency tests kept small and cost-bounded, so that reliability verification does not create uncontrolled MaaS spend.

## Implementation Decisions

### 1. 保持单模型、单上游架构

- `claude-maas` 仍然 100% 使用华为云 MaaS `glm-5.2`。
- 不新增 LiteLLM、CCR、Sidecar、第二模型、fallback 或动态路由。
- 现有本地进程定义为“协议适配器”，只完成 Anthropic Messages 与当前 MaaS OpenAI-compatible endpoint 之间的协议转换，不承担模型选择。
- API URL、API key、客户端入口和 1M context 配置保持不变。

### 2. 版本化代码与主机配置分离

- 协议适配器的权威源码和测试必须进入当前项目的版本控制。
- 运行时环境变量、URL、Key、端口和 systemd 配置继续作为主机配置管理，不写入源码或仓库。
- 部署产物必须能够由版本化源码确定性生成或复制，并记录 SHA-256。
- 发布证据必须同时记录源码 commit、产物 SHA-256 和服务启动时间，但不得记录 secret 值。

### 3. 上游活动监测深模块

该模块提供一个稳定接口：接收原始上游 chunk、结构化事件和生命周期信号，输出状态迁移、计时器决策和脱敏指标。

- 每收到任何上游 body 字节都刷新 `last_upstream_activity_at`。
- `reasoning_content`、可见文本、工具参数、usage、SSE ping 和其他合法 chunk 都算活动。
- 只有“没有收到任何上游字节”才触发 idle timeout。
- 仅收到 TCP ACK 不算应用层活动。
- 所有状态必须按请求隔离；禁止全局“最后活动时间”。

### 4. 三层时间边界

时间值必须可通过非敏感环境变量配置，并在启动时校验范围。v1 默认值：

| 边界 | 默认值 | 定义 |
|---|---:|---|
| connect/header timeout | 60 秒 | 请求发往上游后，等待 HTTP 响应头的最大时间 |
| upstream idle timeout | 180 秒 | 两个上游 body chunk 之间允许的最大静默时间 |
| total request timeout | 600 秒 | 单次模型请求从转发到终止的最大 wall-clock 时间 |

- reasoning chunk 会刷新 idle timeout，但不会刷新 total timeout。
- 超时误差应不超过 1 秒。
- 超时错误必须包含稳定错误码和可重试属性，不包含 prompt、response 或 key。
- 总时限是防止“持续输出但永不结束”的最后边界，不是单轮性能目标。

### 5. GLM reasoning 策略

- 保持上游 thinking/reasoning 能力，不通过本 PRD关闭 thinking。
- 识别 `reasoning_content` 及经过验证的同义字段，仅记录 chunk 数和 UTF-8 字节数。
- 不把原始 reasoning 作为 `text_delta` 发给 Claude Code。
- 不向 Claude Code合成 thinking block、`thinking_delta` 或 signature。
- 不插入“正在思考”等可见占位文本，避免污染最终答案和会话历史。
- 不把 reasoning 内容写入日志、指标、状态端点、错误消息或测试快照。

### 6. Anthropic SSE 终止状态机

适配器必须追踪：`message_start` 是否发送、每个内容块的类型与开闭状态、是否观察到可信 finish reason、`message_delta` 和 `message_stop` 是否发送。

- 已观察到可信 finish reason，但缺少本地终止事件时，可以按协议顺序补齐当前 block stop、`message_delta` 和 `message_stop`。
- 未观察到可信 finish reason 的 EOF、解析失败或连接中止不得合成为成功。
- SSE 尚未开始时，失败返回结构化 HTTP 502/504。
- SSE 已开始时，失败发送合法的 Anthropic `event: error` 后关闭连接。
- 每个成功流恰好一个 `message_start` 和一个 `message_stop`。
- 每个内容索引最多打开一次，并且必须在终止前关闭。
- `text_delta` 只能位于 text block；`input_json_delta` 只能位于 tool-use block。

### 7. 客户端取消传播

- 客户端 request aborted、response close 或进程退出必须触发同一个幂等取消路径。
- 取消路径通过 `AbortController` 终止上游 fetch 和 body iterator。
- 取消后停止解析、停止写客户端、清理所有 timers/listeners，并记录 `client_aborted`。
- 从检测客户端断开到发出上游 abort 的目标时间不超过 1 秒。

### 8. 流式背压与内存边界

- 客户端写缓冲满时必须等待 drain，不得无限调用 write。
- SSE 单事件解析设定可配置上限；超过上限时不得记录 payload。
- 工具参数仍需完整组装后才能形成可执行 `tool_use`，但聚合大小必须有显式上限，超过时以不可重试协议错误终止，不能降级为 `{}` 执行。
- 请求 body、SSE buffer、tool-call aggregate 和并发请求数都必须有独立上限。
- 所有限制触发都使用稳定错误码并计数。

### 9. 错误分类

| 错误码 | 场景 | HTTP/SSE 语义 | 默认可重试 |
|---|---|---|---|
| `MAAS_CONNECT_TIMEOUT` | 等待上游响应头超时 | 504 或 SSE api_error | 是 |
| `MAAS_IDLE_TIMEOUT` | 上游 body 在 180 秒内无任何字节 | 504 或 SSE api_error | 是 |
| `MAAS_TOTAL_TIMEOUT` | 单请求超过 600 秒 | 504 或 SSE api_error | 是 |
| `MAAS_UPSTREAM_HTTP` | 上游返回非 2xx | 保留安全 status 映射 | 取决于 4xx/5xx |
| `MAAS_STREAM_EOF` | 无 finish reason 的提前 EOF | 502 或 SSE api_error | 是 |
| `MAAS_STREAM_PROTOCOL` | 不可恢复的流结构错误 | 502 或 SSE api_error | 否 |
| `MAAS_TOOL_ARGS_TOO_LARGE` | 工具参数超过上限 | 422 或 SSE invalid_request_error | 否 |
| `MAAS_CLIENT_ABORTED` | 客户端主动断开 | 不再写客户端 | 否 |
| `MAAS_OVER_CAPACITY` | 本地并发超过上限 | 503 + Retry-After | 是 |

不得把超时转换成空的成功回答，也不得在失败后发送 `message_stop` 表示成功。

### 10. 脱敏可观测性

每个请求生成随机 request ID。结构化日志和指标允许记录：

- request ID；
- 模型固定值；
- 状态迁移；
- 上游 HTTP status；
- 请求 body 字节数和协议估算 token 数；
- connect、headers、first upstream byte、first visible delta、finish 和总耗时；
- reasoning chunk/byte 数；
- visible text byte 数；
- tool-call 数，不记录工具名和参数；
- outcome、稳定错误码和 retryable；
- 当前/峰值并发。

严禁记录：

- API key、Authorization、x-api-key；
- prompt、system prompt、response text；
- reasoning 内容；
- tool arguments、tool results、文件内容；
- 完整上游 URL query；
- Claude 会话正文。

### 11. 本地状态端点

- 保留现有 liveness 语义。
- 增加 loopback-only 的 sanitized status，至少返回：服务版本、uptime、active request count、各状态数量、oldest active age、last success time、last error code 和配置后的 timeout 数值。
- status 不执行上游模型调用，不返回 request body、prompt、response、key 或 reasoning。
- 非 loopback 访问必须拒绝，即使将来监听地址误配置为非 loopback。

### 12. 并发与过载

- 并发上限可配置并有安全默认值。
- 超过上限的新请求应快速返回 `MAAS_OVER_CAPACITY`，不得排入无界队列。
- C256 只作为本地适配器的确定性测试门禁，使用 fake upstream；它不承诺华为云 MaaS 在真实 C256 下全部成功。
- live concurrency 验证默认不超过 C8，并要求显式预算和限流保护。

### 13. 发布与回滚

1. 在独立 loopback 端口启动候选版本。
2. 运行 deterministic protocol、fault injection 和 Claude Code canary。
3. 确认生产端口没有活跃请求，或等待 drain 窗口结束。
4. 原子替换部署产物并重启服务。
5. 验证 health、文本、流式、工具调用、模型和 1M context。
6. 若 gate 失败，恢复上一个已校验产物并重启。

切换不得修改 API URL、API key 或 `claude-maas` 客户端配置。

## Testing Decisions

### 测试原则

- 测试外部协议行为和状态结果，不断言私有函数实现。
- 时间相关测试使用 fake clock 或短测试阈值，不在单元测试中真实等待 60/180/600 秒。
- fake upstream 必须能确定性产生 response headers、reasoning-only chunks、text chunks、tool chunks、finish reason、EOF、错误 status 和永久静默。
- 每个故障测试必须验证客户端结果、上游是否被取消、timer/listener 是否清理、日志是否脱敏。
- 修复采用 red-green：先证明当前实现无法通过，再提交最小实现使其通过。

### 单元测试模块

1. **活动监测器**
   - reasoning chunk 持续到达时不得触发 idle timeout。
   - text、tool、usage 和 ping 均刷新 idle timer。
   - 仅 TCP 存活但没有应用层 chunk 时必须触发 idle timeout。
   - total timeout 不被任何 chunk 刷新。

2. **SSE 终止状态机**
   - 正常 text 流严格结束。
   - 正常 tool-use 流严格结束。
   - 有 finish reason、缺 terminal events 时安全补齐。
   - 无 finish reason 的 EOF 返回 error，绝不伪装成功。
   - 重复 stop、错配 block 类型和乱序索引被拒绝或安全处理。

3. **reasoning 过滤**
   - reasoning-only chunk 不出现在客户端 payload。
   - reasoning 文本不出现在日志、指标、状态和错误中。
   - reasoning 后的 text/tool 内容完整保留。
   - 不生成 thinking block 或 signature。

4. **取消传播**
   - 客户端断开后上游 fetch 被 abort。
   - 多个 close/abort 信号不会重复终止或抛出未处理异常。
   - timers 和 listeners 在所有终态清理。

5. **背压和大小限制**
   - write 返回 false 时等待 drain。
   - 客户端断开时等待 drain 可被取消。
   - 超大 SSE event 和 tool arguments 有界失败。

6. **可观测性**
   - 每个 outcome 产生一次终态记录。
   - 指标区分 hidden-active、visible-streaming、timeout 和 client-aborted。
   - 用高熵假 key、prompt、reasoning 和 tool args 做泄漏扫描，输出中必须零命中。

### 集成测试

1. fake upstream 每秒发送 reasoning，持续时间超过测试 idle threshold，随后发送 text 和 finish；请求必须成功。
2. fake upstream 发 headers 后永久静默；必须触发 `MAAS_IDLE_TIMEOUT`。
3. fake upstream 持续发送 reasoning 但超过 total threshold；必须触发 `MAAS_TOTAL_TIMEOUT`。
4. fake upstream 有 finish reason 但缺 Anthropic terminal events；适配器必须补齐且只补一次。
5. fake upstream 在 tool arguments 中途断流；不得执行部分或 `{}` 工具。
6. 客户端在 reasoning 阶段断开；上游必须在 1 秒内取消。
7. C1、C16、C64、C256 下无死锁、无 timer 泄漏、无未处理 rejection、内存保持在门限内。

### 现有回归基线

- 现有完整离线测试套件必须保持通过；本 PRD建立时基线为 354 tests passed，后续以新增测试后的总数为准。
- 复用现有 Anthropic SSE contract probe 验证 event framing、block/delta 配对和 `message_stop`。
- 复用现有 Claude Code token-only E2E，验证 `modelUsage` 只包含 `glm-5.2`。
- 复用现有真实 Bash tool round trip。
- 复用 plain Claude 与 `claude-maas` 配置隔离门禁。

### Live 验证

1. 文本请求成功且 result marker 正确。
2. 流式请求以 `message_start` 开始、`message_stop` 结束。
3. 自动工具和强制工具均产生合法 `tool_use`。
4. `modelUsage` 模型集合严格等于 `{glm-5.2}`。
5. `contextWindow == 1000000`。
6. API URL 和 Key 指纹与发布前一致；不得输出 key 本身。
7. live C1 连续多次无 API Error；live C8 在预算内验证，无死锁。
8. status 能在长 reasoning 期间显示 `upstream_active_hidden` 或等价聚合状态。

## 验收门禁

### G-WAIT1：原始缺陷红灯

在旧版本上运行“持续 reasoning、延迟 text”的 fake upstream：测试必须证明旧实现无法报告 hidden activity、没有 idle/total 状态边界或无法传播取消。若测试在旧版本直接通过，说明没有覆盖本次缺陷。

### G-WAIT2：正常长 reasoning 不误杀

reasoning chunk 间隔小于 idle threshold、总时长大于 idle threshold 的请求必须成功；reasoning 内容不得出现在客户端或日志。

### G-WAIT3：真实静默有界失败

上游在 headers 后无任何 body 字节时，必须在 idle threshold + 1 秒内产生 `MAAS_IDLE_TIMEOUT`，并取消上游。

### G-WAIT4：总时限

上游持续产生 hidden activity 但不结束时，必须在 total threshold + 1 秒内产生 `MAAS_TOTAL_TIMEOUT`。

### G-WAIT5：终止正确性

- 有可信 finish reason 才允许补齐成功终止事件。
- 无 finish reason 的 EOF 必须失败。
- 成功流必须且只能有一个 `message_stop`。

### G-WAIT6：客户端取消

客户端断开到上游 abort 不超过 1 秒；请求终态为 `client_aborted`，无后续客户端写入。

### G-WAIT7：敏感数据零泄漏

日志、status、错误和测试产物对注入的 key、prompt、reasoning、tool args、tool results 执行精确扫描，必须零命中。

### G-WAIT8：架构不变量

- 无 LiteLLM、CCR、Sidecar、新模型或 fallback 依赖。
- API URL、API key、`glm-5.2` 和 1M context 未改变。
- plain Claude 配置未受影响。

### G-WAIT9：本地并发

fake upstream C256 测试无死锁、无进程崩溃、无无界队列、无未处理 rejection；超过配置并发上限时快速返回 503。

### G-WAIT10：部署一致性

版本化源码 commit、候选产物 SHA-256 和已部署产物 SHA-256 可关联；服务启动后的 SHA-256 与发布证据一致。

### G-WAIT11：完整回归

完整离线 gate、协议 canary、Claude Code E2E、工具回环、模型与 1M context gate 全部通过。

### G-WAIT12：回滚演练

候选版本部署后能够恢复上一版本，并重新通过 health 与最小文本 canary；回滚不接触 URL 和 Key。

## 非功能要求

- 除模型和网络耗时外，适配器对首个可见 delta 的新增 P95 延迟小于 50ms。
- idle/connect/total timeout 的触发误差小于等于 1 秒。
- 客户端取消传播小于等于 1 秒。
- 进程不得因单请求解析错误退出。
- 请求级状态必须在终态后释放；稳定运行不得出现与请求总数线性增长的 timer/listener。
- 日志默认结构化、可轮转；DEBUG 也不得记录敏感内容。
- 新增状态端点仅允许 loopback。

## Definition of Done

1. 权威适配器源码和测试进入当前项目版本控制。
2. 原始缺陷测试完成红—绿证明。
3. 活动监测、三层 timeout、取消传播和终止状态机全部实现。
4. reasoning 保持上游启用、客户端隐藏且零日志泄漏。
5. 所有错误拥有稳定错误码和正确 HTTP/SSE 语义。
6. status 能区分 hidden-active 与真正 idle。
7. 完整离线和 live gates 通过。
8. `glm-5.2`、1M context、URL、Key 和 plain Claude 隔离保持不变。
9. 部署产物与源码 checksum 一致。
10. 发布证据包含时间、commit、checksum、测试摘要和回滚结果，不包含 secret。
11. 当前项目工作树除本需求实现外无意外改动。
12. 操作文档说明“Waiting 不一定是错误”、状态判读、超时错误与回滚步骤。

## Out of Scope

- 不承诺消除 Claude Code 的 `Waiting for API response` 文案。
- 不把 GLM reasoning 展示给 Claude Code。
- 不伪造 Anthropic thinking block 或 signature。
- 不插入可见“正在思考”占位文字。
- 不关闭 thinking 作为提速方案。
- 不设华为云 MaaS 单轮模型时延 SLO。
- 不改变 API URL、API key、模型、1M context 或 max output tokens。
- 不引入 LiteLLM、CCR、HTTP 业务路由、Sidecar 或 fallback。
- 不修改 Exa MCP、OAuth Claude 或 plain Claude 配置。
- 不在本 PRD优化 Agent 轮次数、prompt、工具选择或模型质量。
- 不承诺真实华为云 MaaS C256 全成功；C256 仅验证本地适配器可靠性。

## Further Notes

### 与旧 plugin 的关系

本方案继承旧 plugin 的两项正确原则：

1. GLM reasoning 在上游保持启用，但不作为 Claude Code 的 thinking block 暴露。
2. 流式终止必须是协议正确、可验证且不能把不完整响应伪装为成功。

本方案不迁移 LiteLLM callback 框架，而是把必要的活动检测、终止状态机、取消传播和脱敏观测收敛为当前轻量协议适配器中的深模块。

### 对“Waiting”的正确解释

`Waiting for API response` 只能说明 Claude Code 尚未获得可显示的 text/tool 内容，不能单独证明 API 已断开。发布后应按以下顺序判断：

1. 状态为 `upstream_active_hidden`：MaaS 正在返回 reasoning，继续等待或由用户主动取消。
2. 状态为 `visible_streaming`：已经开始向客户端输出。
3. 状态长时间为 `connecting`：检查 connect/header timeout。
4. 状态进入 `idle_timeout`：上游应用层真正静默，允许重试。
5. 状态进入 `total_timeout`：请求持续活动但超过产品总时限，允许重试或拆分任务。

### 发布前不可省略的现场证据

- 同一请求的上游字节活动时间线；
- Claude Code 可见事件时间线；
- 状态机转换和终态；
- URL/Key 指纹未变化证明；
- 模型与 1M context 证明；
- fault-injection、C256 local、live C1/C8 和 rollback 结果。
