# E1/B2 修复计划（claude-glm 生产化）

日期：2026-06-12。来源：tests/LAST-RUN-REPORT.md 的两个 FAIL 项。

## 根因

### E1：usage.input_tokens/output_tokens 恒为 0

链路 `claude -> ccr(3456) -> litellm-anthropic-adapter(4010) -> LiteLLM(4000) -> MaaS glm-5.1`。

- 非流式：adapter 正确转换 `usage.prompt_tokens/completion_tokens`（实测 9/118）。
- 流式（Claude Code 实际路径）：adapter `proxyStreaming` 未发送
  `stream_options: {"include_usage": true}`，LiteLLM 默认不在流尾 chunk 回传 usage，
  adapter 的 `message_delta.usage` 永远是 0/0。
- 实测 LiteLLM 4000 在带 `include_usage` 时正确回传最终 usage chunk。

后果：成本统计失效、context-left 指示失效、auto-compact 永不触发 →
长会话裸奔到 MaaS 硬限 196608 token 直接报错（历史上 `claude-glm-recover` 存在的根因）。

### B2：contextWindow 声明 200000，与 MaaS 真实限制不符

- Claude Code 2.1.175 按模型名查内置表得 200000（glm-5.1 等未知名也回落到 200000）。
- 反编译确认：`CLAUDE_CODE_MAX_CONTEXT_TOKENS` 仅在 `DISABLE_COMPACT` 同时设置时才被读取
  （`if(tH.DISABLE_COMPACT && process.env.CLAUDE_CODE_MAX_CONTEXT_TOKENS)`），
  wrapper 中单独 export 它是死配置；声明窗口本身不可覆盖。
- 可用替代：`CLAUDE_CODE_AUTO_COMPACT_WINDOW=<tokens>`（等价 `/autocompact <tokens>`），
  直接把 auto-compact 触发窗口固定为指定 token 数，独立于声明窗口。
- MaaS glm-5.1 真实输入硬限：196608 token（实测报错
  `prompt length 197218 must less than the maximum input length 196608`）。

## 修改项

| # | 文件 | 修改 | 目的 |
|---|------|------|------|
| 1 | `/root/litellm-anthropic-adapter/server.js` | `proxyStreaming` 上游请求体加 `stream_options:{include_usage:true}` | 修 E1 |
| 2 | `/root/.local/bin/claude-glm` | 删除死配置 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`；新增 `CLAUDE_CODE_AUTO_COMPACT_WINDOW`（默认 180000，可被环境覆盖） | 修 B2 实质问题 |
| 3 | `scripts/configure-claude-glm.sh`（本仓库） | wrapper 模板同步上述两项 | skill 与部署一致 |
| 4 | `SKILL.md` / `README.md` | 修正 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 相关描述 | 文档不再误导 |
| 5 | `tests/concurrent-top30.sh` B2 用例 | 断言改为：wrapper 配置的 auto-compact 窗口 ≤ 190000（低于硬限），E1 继续断言 usage>0 | 测生产语义而非不可达的窗口声明 |

窗口取 180000 的理由：硬限 196608 - 单轮最大增量（输出 8192 + 工具结果余量 ≈ 8k）≈ 180k，
不过度浪费上下文。可用 `CLAUDE_GLM_AUTO_COMPACT_WINDOW` 覆盖。

## 不改的内容

- 保留 `claude-opus-4-6` 别名路由（声明窗口 200000 改不掉，改模型名也一样是 200000；
  别名不影响修复后的 auto-compact 正确性）。
- 不动 CCR 配置与 LiteLLM 配置（usage 在这两跳验证为透传）。

## 验证

1. 重启 adapter 后逐跳 curl：4010 流式 `message_delta.usage` 非零。
2. `claude-glm --print --output-format json` → `usage.input_tokens/output_tokens > 0`。
3. 重跑 `tests/concurrent-top30.sh` 全批次，预期 31/31 PASS、工具调用无回归。
