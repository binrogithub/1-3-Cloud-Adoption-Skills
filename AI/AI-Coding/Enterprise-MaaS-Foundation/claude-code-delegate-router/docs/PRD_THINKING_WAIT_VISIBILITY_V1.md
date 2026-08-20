# PRD：思考期等待可见性（stream progress v1）

状态：已交付
相关：`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`（现行 reasoning 隐藏不变量）
外部来源：`/root/litellm-auto-plugin/docs/archive/PRD-anthropic-stream-guard.md`、
`PRD-glm-loop-breaker.md`（本 PRD 的取舍证据来自这两份）

## 0. 产品摘要

Claude Code 在 119.8.83.10 上长时间停在 `Waiting for API response`。这不是挂死，
是**思考期静默**：glm-5.2 把思维链放在 `reasoning_content` 流式吐出，适配器按
现行不变量整段丢弃，于是从 `message_start` 到首个可见 token 之间**一个字节都不写**。

本 PRD 只解决"等待期间客户端什么都收不到"，**不改模型思考行为**，不碰凭证拓扑，
不改协议翻译的其余部分。

## 1. 证据

### 1.1 静默是实测的，不是推测

生产 `/status` 抓到的在途请求：

    "state_counts": {"upstream_active_hidden": 1},
    "oldest_active_age_ms": 176313

`upstream_active_hidden` = 上游在持续送数据、客户端一个字节收不到，已持续 176 秒
（该请求随后正常完成，不是死锁）。

同一把 Key 直连上游，一句话的简单问题：

| 配置 | 首个可见内容 | 被丢弃的 reasoning | 总耗时 |
| --- | --- | --- | --- |
| 默认（思考开） | **20.53s** | 1145 字符 | 21.92s |
| `thinking:{type:"disabled"}` | 5.89s | 0 | 7.81s |
| `enable_thinking:false` | 22.36s | 1113 字符 | 23.55s（**参数被上游忽略**） |

简单问题静默 20 秒；真实轮次带 4 万 token 上下文和工具定义时就是上面那 176 秒。

### 1.2 这是既有行为，不是本次部署引入的

`tests/fixtures/legacy_server.js` 中 `reasoning_content` 出现 **0 次**——legacy 从未
处理过 reasoning，效果同样是丢弃。8-20 部署的新适配器只是把这件事**显式化**
（`ReasoningFilter` + `recordReasoning()` 刷新 idle 计时器）并让它可观测
（`upstream_active_hidden` 状态）。

### 1.3 关思考已被上游项目量化否决

`PRD-glm-loop-breaker.md` §2：同一上游、同一 key，仅改 thinking 配置——

| | `reasoning_tokens` | `len(reasoning_content)` |
| --- | --- | --- |
| thinking 关闭 | 0 | — |
| thinking 开启 | 640 | 2822 字符真实推理 |

且关闭后 **Agent 无法脱离死循环**（temperature 0 下"复读上下文中最相似片段"成为
确定性最优解，客户端自身无法脱困）。`PRD-anthropic-stream-guard.md` §1 同样结论。

**因此本 PRD 的前提是：thinking 保持开启。** §1.1 表里的 B 行只作为静默成本的
标尺，不作为方案。

### 1.4 LiteLLM 那套解决的不是这个问题

- ASG 保持 thinking 开启，修的是 LiteLLM `streaming_iterator.py` 把首个
  `content_block_start` 硬编码成 `text` 再塞 `thinking_delta` 的协议违规
  （症状是 effort=max 解析失败，不是等待）。
- ARF 在 Anthropic 边界把 thinking 摘掉，只给 OpenAI 客户端留 `reasoning_content`。

本项目移植的是 **ARF 那一半**，并且**正在生效**——静默正是它生效的结果。ASG 在这里
没有对应物（本适配器自己拼 SSE，不存在那个 bug）。**即便在 LiteLLM 链路上，ASG 合成
的 thinking 块也会被 ARF 摘掉**，所以那条链路的 Claude Code 同样看不到思考过程。

### 1.5 一个待核实的事实（P0，先查再定 D1）

若 247 生产上 `ARF_HIDE_REASONING=false`，则 Claude Code 在 LiteLLM 链路上**确实**
看得到 thinking 流，方案 B 就有生产先例。**实施前必须先查这个环境变量的实际取值**，
不要按默认值假设。查法：247 上 litellm 服务的 EnvironmentFile / 容器 env。

## 2. 决策

### D1（核心）：等待期间给客户端什么

| 方案 | 客户端表现 | reasoning 泄漏面 | 代价 |
| --- | --- | --- | --- |
| **A. 仅 SSE ping** | 连接可证活；**`Waiting for API response` 文案不变** | 零 | 不解决用户可见的抱怨 |
| **B. 转发真实 reasoning 为 thinking 块** | 思考过程逐字流出 | **变大**：reasoning 进入终端与会话历史 | 推翻现行不变量；需改 leak-scan 测试 |
| **C. 合成空 thinking 块 + 心跳增量（推荐）** | 客户端切到"思考中"并有活动感 | 零（不写入任何模型文本） | 需要确认 Claude Code 对无 signature 的 thinking 块的接受度 |

**推荐 C，并把 A 作为 C 的地板**（C 不可行时退回 A）。B 需要单独的产品决策与
安全评审，本 PRD 默认不采纳。

C 的具体形态：进入 `upstream_active_hidden` 后发
`content_block_start {type:"thinking"}`，随后按固定间隔发 `thinking_delta`
（内容为占位/进度标记，**不含模型任何原文**），首个可见 token 到达前发
`content_block_stop` 关闭该块，再照常开 text 块。

### D2：总超时

本次部署引入了 legacy 没有的 **600s 总超时**。思考开启时长轮次有被 `MAAS_TOTAL_TIMEOUT`
掐断的真实风险（legacy 会一直等）。决定：上调默认值并可经 env 覆盖，具体值由
§4 验收 #5 的实测分布决定，不拍脑袋。

### D3：不采用

- 不关思考（§1.3）。
- 不改 `reasoning_content` 的隐藏策略（除非 D1 选 B，另走评审）。
- 不引入第二个 listener、不引入 Sidecar（架构不变量）。
- 不动 `/etc/claude-code-proxy/maas.env` 的 URL 与 Key。

## 3. 影响面

| 文件 | 变更性质 |
| --- | --- |
| `adapter/server.js` | 流式路径新增进度块/ping 发射 |
| `adapter/lifecycle.js` | 状态机需允许 thinking 块的开/闭并计入 block 配对校验 |
| `tests/test_adapter_protocol_security.py` | leak-scan 需断言进度块**不含**模型原文 |
| `tests/test_adapter_contract.py` | SSE 框架不变量：thinking 块必须在 text 块前闭合 |
| `docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md` | 记录不变量的例外（合成块 ≠ 转发 reasoning） |

**入站方向同样要处理**：客户端下一轮可能把 thinking 块回传。适配器在
Anthropic→OpenAI 翻译时必须丢弃入站 `thinking`/`redacted_thinking` 块
（ASG 的 `STRIPPED_REQUEST_KEYS` 是同一件事）。这条容易漏，漏了会在第二轮才炸。

## 4. 验收标准

每条都要求先证明修复前失败（本仓库的反向门纪律）。

1. **静默窗口实测下降**：同一 prompt、同一 Key，记录 `message_start` 到**首个
   client 可见事件**的间隔；修复前 = 首个可见 token 的时间（20s 量级），修复后
   必须 ≤2s。**用实测秒数断言，不用"有事件"这种无鉴别力断言。**
2. **零泄漏**：把高熵 canary 注入上游 `reasoning_content`，扫描客户端 SSE 全文、
   `/status`、stdout/stderr，命中数必须为 0（沿用既有 leak-scan 手法）。
3. **协议合法**：thinking 块与 text 块的 start/stop 严格配对，`thinking_delta`
   只出现在 thinking 块内；用 `tests/live_maas_probe.py --probe thinking` 校验。
4. **真实 E2E**：`claude-maas --print --output-format json` 走完整工具轮次，
   `stop_reason` 与 `modelUsage` 非空（这是 8-20 那次 message_delta 缺失的教训——
   只看 `result` 文本对不对发现不了终端事件缺失）。
5. **总超时定值有依据**：采集 ≥20 个真实轮次的思考时长分布，取 p99×2 作为默认值。
6. **变异门**：把进度块发射改成 no-op，验收 #1 必须失败。绿灯不能靠"存在即通过"。
7. **运行态新鲜度**：部署后以 `/status` 的 `version` 字段 + 一次真实请求确认跑的是
   新产物（8-20 已踩过"文件换了进程没换"）。
8. `make verify-offline` 全绿且不产生上游流量（与 V3 发布门 R3 一致）。

## 5. 非目标

- 不改善上游本身的思考速度。
- 不做多模型路由、不做 fallback。
- 不把 reasoning 落盘或写日志。

## 6. 实施顺序

0. 先查 §1.5 的 `ARF_HIDE_REASONING` 实际取值，确认 D1 不需要改选 B。
1. 入站 thinking 块丢弃（先做，否则第二轮才暴露）。
2. lifecycle 状态机支持合成 thinking 块。
3. server.js 发射进度块 + ping；验收 #1/#6 的测量脚手架同步落地。
4. leak-scan 与 SSE 契约测试扩展。
5. D2 总超时定值（依赖 #5 的采样）。
6. 部署 + 运行态新鲜度复验。

## 7. 与在途工作的关系

`docs/PRD_UNIFIED_INSTALL_V3_RELEASE_GATE.md`（R1 重言式反向门、R2 轮询 5s、
R3 测试打生产）尚未实施。两者互不阻塞，但**建议先做 V3**：R3 不修的话，本 PRD
验收 #8 的"不产生上游流量"无法成立。
