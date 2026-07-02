# claude-glm 扩展 50 用例测试报告（并发 agents 执行）

日期：2026-06-12。执行方式：4 个并发 agent 跑 40 个无破坏性用例（每套件内部 10 用例再并发，
峰值约 40 路并发会话），全部完成后 1 个 agent 严格串行执行 10 个故障注入用例。
与 Top-30 基线批次（tests/LAST-RUN-REPORT.md，31/31 PASS）完全不重复。

## 总成绩：47/50 PASS，3 个真实发现（1 中 2 低风险）

| 套件 | 范围 | 结果 | 墙钟 |
|------|------|------|------|
| T 高级工具调用 | 并行工具、多处编辑、5000 行工具输出、错误恢复、深层目录、TodoWrite、4 轮依赖链 | 10/10 | 192s |
| S 会话与上下文 | 三跳 resume、--continue、/compact、CLAUDE.md、fork、token 累积、流式 usage | 10/10¹ | 263s |
| P 协议与格式 | 事件序列、partial messages、计费字段、截断语义、认证失败、num_turns | 9/10² | — |
| R 压力与鲁棒性 | 60k/150k 输入、连发、同目录并发、提示注入、约束遵循、二进制 | 10/10 | 277s |
| X 韧性与安全（串行故障注入） | 路由器/适配器宕机自愈、竞态、密钥扫描、未认证探测 | 8/10 | — |

¹ S9 首轮断言缺陷（种子会话与 resume 的 prompt 构造差 ~1.4k token），改为比较两次连续
resume 后 PASS：input_tokens 30592→30970 单调增长，证实 usage 修复后上下文核算正常。
² P3 断言语义错误重判 PASS（duration_api_ms 为跨 API 调用累计值，可合法大于墙钟）；
P5 串行复测 PASS（131s 正常 end_turn），原 FAIL 为 40 路并发下排队超时（容量特征）。

## 3 个真实发现

### P7（中）：认证失败不快速失败
CCR 对错误密钥 6ms 即返回 401，但 claude CLI 反复重试 60s+ 不退出、无可读错误。
运维风险有限（wrapper 固定注入正确 token），但密钥配置错误时排障体验差。
缓解：文档化"401 挂起 → 检查 ANTHROPIC_AUTH_TOKEN"；上游属 Claude Code 重试策略。

### X5（低）：未知模型名被默认路由静默吞掉
请求 `no-such-model-xyz` 返回 HTTP 200 正常应答（默认路由 → glm-5.1）。拼错模型名
不会得到任何告警。属 ccr 设计行为；如需严格语义可在 custom-router.js 对未知模型显式抛错。

### X10（低）：路由器根路径未鉴权泄露版本横幅
无认证 GET `http://127.0.0.1:3456/` 返回 200 与 `{"message":"LLMs API","version":"1.0.51"}`。
推理端点 POST /v1/messages 已正确 401。仅绑定 127.0.0.1，风险为本机指纹识别。

## 韧性结论（X 套件，全部 PASS 项）

- `ccr stop` → wrapper 自愈并应答：12s；`kill -9` + 陈旧 pid → 10s 恢复
- 适配器(4010)宕机 → `ensure_anthropic_adapter` 自动拉起
- `ccr restart` 竞态：在途请求被 SDK 重试兜住（rc=0），30s 内健康
- 恢复延迟 SLO：含自愈全程 8-16s（限值 120s）
- 密钥扫描：311 个文件（CCR 日志/适配器日志/会话 JSONL/全部测试产物）对 3 个密钥零命中
- `~/.config/claude-glm/env` 权限 600

## 运维观察（不计 PASS/FAIL）

- **>128KB prompt 必须走 stdin**：Linux MAX_ARG_STRLEN 限制 argv 单参数 ~128KiB；
  150k 字符经 stdin 全链路成功（55363 input tokens，12.7s）
- **并发负载下排队显著**：相同请求 duration 波动 9s→127s→46s（≈14 倍），无缓存加速；
  长文生成（3356 output tokens）串行 131s、40 路并发下 >300s——容量规划需按排队模型估算
- 流式中间事件 usage 为 0，非零 usage 仅在最终聚合（适配器仅在 message_delta 回传）；
  Claude Code 端核算正确，可作后续观察项
- 模型对宽松提示偶有语义等价回答（"Reply OK" → "好的"），严格提示词消除

## 生产就绪度评估

结合基线 31/31 与本批 47/50：**claude-glm 已具备生产级 harness 的核心能力**——
工具调用全矩阵、会话管理（含 compact/fork/resume）、token 核算与 auto-compact（本轮修复）、
故障自愈、并发隔离、密钥卫生均达标。遗留 3 项均有明确缓解且不阻断上线；
真正需要纳入容量规划的是并发排队延迟（建议按峰值 QPS 压测建立 SLO 曲线）。

## 证据位置

- 各套件产物：`/tmp/claude-glm-50/{T,S,P,R,X}/`（每用例 status/note/stdout/stderr/工件）
- 套件报告：`/tmp/claude-glm-50/<套件>/report.md`
- P5 复测：`/tmp/claude-glm-50/P5-rerun/`
