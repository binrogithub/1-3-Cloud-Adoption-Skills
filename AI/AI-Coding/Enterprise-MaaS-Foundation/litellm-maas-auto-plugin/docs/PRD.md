# PRD: Claude Code 直连 LiteLLM 的 GLM-5.2 服务侧适配方案

## 1. 背景

客户侧已明确：Claude Code 客户端不能安装 router、forky 或其他本地代理组件。之前的 `claude-glm`、`claude-forky` 客户端侧方案不可接受。新的方案必须把协议适配、上下文保护、搜索兜底、图片兜底、模型路由等能力集中放到 LiteLLM 服务侧。

目标是让 Claude Code 作为原生客户端使用，只通过一个 LiteLLM endpoint 接入企业 MaaS 后端的 GLM-5.2 196K 上下文模型，并在必要时路由 Opus、多模态模型和搜索服务。

## 2. 目标

1. Claude Code 客户端保持原生形态，不安装 router/forky，不改本地上下文配置。
2. 客户端只配置 LiteLLM 地址、API Key 和模型名。
3. LiteLLM 成为唯一对外入口，承载鉴权、审计、计费、路由、上下文保护和协议兼容。
4. 默认代码执行模型使用 MaaS 侧 GLM-5.2，服务侧按 196K 上下文窗口做保护。
5. 上下文压缩 summarization 使用 Opus-4.8 模型。
6. 图片/多模态请求优先使用 Claude Code 前端 Opus-4.8 能力；进入后端时使用当前 LiteLLM 视觉模型，不做低质量文本化替代作为默认路径。
7. 搜索/图片能力按客户端 OAuth 状态分流：有 OAuth 时优先使用 Claude Code 前端原生能力；无 OAuth 时使用 LiteLLM 后端搜索和视觉模型兜底。

## 3. 输出件

本项目交付两个核心输出件：

1. Claude Code 客户端配置脚本：`scripts/configure-claude-code-litellm.sh`
2. LiteLLM 服务侧插件：`litellm_plugins/cc_glm52_guard/`

当前主机的生产验证路径已调整为：

```text
Claude Code 原生客户端
  -> LiteLLM 同侧 Anthropic adapter: http://127.0.0.1:4010
  -> LiteLLM chat completions: http://127.0.0.1:4000/v1/chat/completions
  -> MaaS GLM-5.2
```

原因：本机 LiteLLM 原生 `/v1/messages` 到 MaaS GLM 的路径会进入不兼容的 `/responses` 调用；4010 adapter 已验证可完成 Claude Code 文本与工具调用。该 adapter 属于 LiteLLM 服务侧能力，不部署到客户终端。

目录规划：

```text
litellm-maas-plugin/
  docs/
    PRD.md
  scripts/
    configure-claude-code-litellm.sh
  litellm_plugins/
    cc_glm52_guard/
      __init__.py
      callback.py
      config.example.yaml
      README.md
  tests/
    test_context_management.py
    test_model_routing.py
    test_multimodal_routing.py
```

### 3.1 Claude Code 客户端配置脚本

脚本目标：

1. 只配置 Claude Code 指向 LiteLLM 的必要环境变量或配置文件。
2. 不安装 router、forky、本地代理或额外客户端守护进程。
3. 支持幂等执行和回滚提示。
4. 输出当前生效的 LiteLLM endpoint、model alias 和 key 来源。
5. 支持 `--capability-mode auto|frontend|backend`：`auto` 检测本机 Claude Code OAuth 状态；有 OAuth 使用 `frontend_capable`，无 OAuth 使用 `backend_fallback`。

脚本职责范围：

```text
输入:
  LITELLM_BASE_URL  # 当前主机默认 http://127.0.0.1:4010；未检测到 adapter 时回退 http://127.0.0.1:4000
  LITELLM_API_KEY
  CLAUDE_CODE_MODEL_ALIAS
  CLAUDE_CODE_CAPABILITY_MODE

输出:
  Claude Code 可直接使用的配置
  最小 smoke test 命令
```

推荐默认：

```bash
export ANTHROPIC_BASE_URL=https://litellm.company.example
export ANTHROPIC_API_KEY=<customer_virtual_key>
export ANTHROPIC_MODEL=claude-opus-4-6
export CLAUDE_CODE_CAPABILITY_MODE=frontend_capable
```

验收条件：

1. 新机器只安装 Claude Code 后可执行脚本完成接入。
2. 脚本不安装或启动任何本地代理。
3. 脚本执行后 `claude` 直连 LiteLLM。

### 3.2 LiteLLM 服务侧插件

插件目标：

1. 作为 LiteLLM custom callback/pre-call hook 加载。
2. 承担 Claude Code 到 GLM-5.2 的服务侧兼容策略。
3. 不修改 LiteLLM core。
4. 可独立测试、升级、回滚。

插件职责：

1. 模型别名映射：将 Claude Code 外部模型名映射到内部 GLM-5.2、Opus-4.8、LiteLLM 视觉模型。
2. 上下文保护：注入或修正 `context_management`。
3. 196K 预算控制：按 180K soft limit 做预警、compact 或拒绝。
4. Opus compact：超过阈值时使用 `opus-summary`，目标模型版本为 Opus-4.8。
5. 多模态路由：前端 Opus-4.8 原生能力优先；后端识别 image block 后路由到当前 LiteLLM 视觉模型别名 `vision-openrouter`。
6. 搜索策略：`frontend_capable` 使用 Claude Code 原生搜索；`backend_fallback` 为搜索意图注入 `litellm_web_search`，由 LiteLLM `websearch_interception` 兜底。
7. 参数清洗：移除或转换 GLM-5.2 MaaS 不支持的参数。
8. 审计元数据：写入 routing、context、fallback 等信息。

插件加载方式草案：

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance
```

验收条件：

1. 插件可被 LiteLLM 配置加载。
2. 插件不要求客户端侧改上下文配置。
3. 插件可通过单元测试覆盖模型路由、上下文注入、多模态识别。
4. 插件升级不要求 fork LiteLLM 主包。

## 4. 非目标

1. 不要求修改 Claude Code 源码。
2. 不要求在客户终端安装本地代理、router、forky 或证书劫持组件。
3. 不深 fork LiteLLM 主代码库。
4. 不把完整 forky 逻辑内嵌到 LiteLLM core。
5. 不承诺 GLM-5.2 原生支持 Claude/Anthropic 的全部私有行为；缺口由服务侧 adapter/hook 兼容。

## 5. 客户端使用方式

客户端只需配置：

```bash
export ANTHROPIC_BASE_URL=https://litellm.company.example
export ANTHROPIC_API_KEY=<customer_virtual_key>
claude
```

当前主机推荐对外模型名：

```text
claude-opus-4-6
```

说明：该模型名是 Claude Code 侧的兼容模型别名，不代表后端一定调用 Anthropic Opus。LiteLLM 根据策略路由到 GLM-5.2、Opus-4.8 或当前 LiteLLM 视觉模型。

## 6. 总体架构

```text
Claude Code 原生客户端
  |
  | Anthropic /v1/messages
  | /v1/messages/count_tokens
  v
LiteLLM Proxy
  |
  |-- Auth / key / team / audit / usage
  |
  |-- Claude Code compatibility hook
  |     |-- model alias 清洗
  |     |-- Anthropic beta/header 兼容
  |     |-- context_management 注入或修正
  |     |-- 196K 上下文预算保护
  |     |-- search/image 路由判断
  |
  |-- LiteLLM native Anthropic endpoint adapter
  |     `-- 当前主机未作为生产默认，因 MaaS /responses 路径不兼容
  |
  |-- 默认文本/代码路径
  |     v
  |   MaaS GLM-5.2 196K
  |
  |-- 上下文压缩路径
  |     v
  |   Opus summary model
  |
  |-- 图片/多模态路径
  |     v
  |   Multimodal model
  |
  |-- 搜索路径
  |     v
  |   OAuth present: Claude Code native search
  |   OAuth absent: LiteLLM websearch_interception + Search provider
  |
  `-- 当前生产 cc-anthropic-adapter sidecar
        |-- 复杂 tool_use/tool_result 映射
        |-- 流式 Anthropic SSE 修复
        |-- 极限上下文 pack/compact
        `-- 调用 LiteLLM chat completions
```

## 7. 组件设计

### 7.1 LiteLLM Proxy

LiteLLM 是唯一暴露给 Claude Code 的 endpoint，负责：

1. 暴露 Anthropic-compatible `/v1/messages`。
2. 暴露 `/v1/messages/count_tokens`。
3. 管理 virtual key、team、budget、audit log。
4. 将 Claude Code 请求路由到 GLM-5.2、Opus、多模态模型或搜索服务。
5. 执行服务侧上下文管理策略。

### 7.2 Claude Code Compatibility Hook

以 LiteLLM custom callback/pre-call hook 形式实现，保持轻量，不修改 LiteLLM core。

职责：

1. 识别 Claude Code 请求。
2. 将外部模型别名映射到内部路由模型。
3. 在客户端未提供 `context_management` 时注入默认策略。
4. 在客户端提供 `context_management` 时修正阈值，避免超过 GLM-5.2 服务侧预算。
5. 识别图片 content block，并路由到多模态模型。
6. 识别 capability mode 和搜索意图：有 OAuth 时前端优先，无 OAuth 时启用服务侧搜索兜底。
7. 对不支持参数做 allowlist/drop/transform，避免 MaaS 后端 400。

### 7.3 cc-anthropic-adapter Sidecar

该组件是服务侧 sidecar，不部署在客户端。当前主机已用 `/root/litellm-anthropic-adapter/server.js` 验证可用，作为生产默认传输路径，直到 LiteLLM 原生 `/v1/messages` 到 MaaS GLM 的路径修复。

触发条件：

1. LiteLLM 原生转换不足以稳定支持 Claude Code tool loop。
2. GLM-5.2 对 Anthropic tool_use/tool_result 格式兼容不稳定。
3. 需要更细粒度控制 Anthropic SSE event。
4. 需要比 LiteLLM context management 更强的上下文 packing。

部署建议：

1. 与 LiteLLM 同 namespace/compose。
2. 只暴露内网地址。
3. 对 Claude Code 暴露 Anthropic `/v1/messages`，内部调用 LiteLLM `/v1/chat/completions`。
4. 可独立灰度、回滚和压测。

不建议把完整 sidecar 逻辑放进 LiteLLM 包内，避免 LiteLLM 升级时产生深 fork 维护成本。LiteLLM 插件仍负责服务侧策略；sidecar 只负责协议稳定转换。

## 8. 模型路由策略

| 场景 | 目标模型 | 说明 |
|---|---|---|
| 默认代码生成/修改/工具调用 | GLM-5.2 196K | 主力执行模型 |
| 上下文 compact summary | Opus-4.8 | 用户已决策，优先保证摘要质量 |
| 图片、多模态输入 | 前端 Opus-4.8；后端 `vision-openrouter` | 不默认 OCR/caption 降级 |
| 搜索 | 有 OAuth: Claude Code 原生搜索；无 OAuth: LiteLLM 后端搜索 | 由客户端脚本检测并通过 backend model alias/metadata 表达 |
| GLM-5.2 失败且可重试 | fallback deployment | 同模型多实例优先 |

当前主机已验证的 LiteLLM/GLM-5.2 配置来源：

```text
LiteLLM container: litellm_proxy
LiteLLM image: ghcr.io/berriai/litellm:v1.83.14-stable.patch.3
LiteLLM native URL: http://127.0.0.1:4000
Claude Code production URL on this host: http://127.0.0.1:4010
Config file: /root/LiteLLM/assets/config/litellm_config.yaml
GLM model alias: glm-5.2
Claude Code external alias on this host: claude-opus-4-6
GLM provider model: openai/glm-5.2
GLM api_base env: HUAWEI_MAAS_API_BASE
GLM api_base value: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
GLM api_key env: HUAWEI_MAAS_API_KEY_0
Current max_input_tokens: 192000
Current vision alias: vision-openrouter
```

## 9. 196K 上下文策略

GLM-5.2 标称 196K 上下文，但服务侧不能按 196K 打满。需要预留输出、工具 schema、系统提示、tokenizer 误差和供应商实现误差。

推荐参数：

```text
hard_limit: 196000
soft_input_limit: 180000
compact_trigger: 150000
clear_tool_results_trigger: 100000
reserved_output_tokens: 8192 或 16384
tokenizer_error_margin: 5%-8%
```

LiteLLM 配置要点：

```yaml
router_settings:
  enable_pre_call_checks: true

model_list:
  - model_name: claude-opus-4-6
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    model_info:
      max_input_tokens: 192000
```

服务侧默认注入：

```yaml
context_management:
  edits:
    - type: clear_tool_uses_20250919
      trigger:
        type: input_tokens
        value: 100000
      keep:
        type: tool_uses
        value: 3
    - type: compact_20260112
      trigger:
        type: input_tokens
        value: 150000
```

compact summary model：

```yaml
general_settings:
  context_management_summary_model: opus-summary

model_list:
  - model_name: opus-summary
    litellm_params:
      model: anthropic/claude-opus-4.8
      api_key: os.environ/OPUS_48_API_KEY
```

说明：

1. Claude Code 客户端不需要知道这些阈值。
2. 客户端即使没有发 `context_management`，LiteLLM hook 也要注入。
3. 如果客户端已经发了 `context_management`，服务侧不能盲目覆盖，需要合并并夹紧阈值。
4. `compact_20260112` 的触发阈值不得低于 LiteLLM 要求的下限。

## 10. 搜索策略

搜索策略由 capability mode 决定：

| Capability mode | 触发来源 | 搜索路径 |
|---|---|---|
| `frontend_capable` | Claude Code 本机 OAuth 存在 | Claude Code 原生搜索 |
| `backend_fallback` | Claude Code 本机 OAuth 不存在，或显式配置 backend | LiteLLM 后端 `websearch_interception` |

客户端脚本在 `--capability-mode auto` 时检测本机 OAuth。无 OAuth 时默认使用后端模型别名 `claude-opus-4-6-backend`，让 LiteLLM 插件即使收不到客户端自定义环境变量，也能识别 `backend_fallback`。

后端搜索启用条件：

1. 请求 capability mode 为 `backend_fallback`。
2. 请求存在搜索意图。
3. LiteLLM 已配置 `websearch_interception` 和 search provider。

后端搜索配置草案：

```yaml
litellm_settings:
  callbacks:
    - websearch_interception
  websearch_interception_params:
    enabled_providers:
      - openai
      - bedrock
      - azure
      - vertex_ai
    search_tool_name: enterprise-search

search_tools:
  - search_tool_name: enterprise-search
    litellm_params:
      search_provider: perplexity
      api_key: os.environ/PERPLEXITY_API_KEY
```

供应商可替换为 Tavily、Exa、SearXNG、Google PSE 等。

## 11. 图片与多模态策略

默认策略：

1. `frontend_capable`：Claude Code 前端可处理的多模态请求，使用前端 Opus-4.8 能力。
2. `backend_fallback`：进入 LiteLLM 后端的图片/多模态请求，使用当前 LiteLLM 视觉模型别名 `vision-openrouter`。
3. 无论 mode 如何，只要 image block 到达 LiteLLM，插件必须路由到 `vision-openrouter`，避免把图片发给 GLM-5.2。

当请求包含 image block、文件图片或截图类内容：

1. LiteLLM hook 识别多模态输入。
2. 路由到 `vision-openrouter` 模型别名。
3. 多模态模型返回文本分析或可继续参与 tool loop 的回答。
4. 如果该任务后续转为纯代码修改，可回到 GLM-5.2。

配置草案：

```yaml
model_list:
  - model_name: vision-openrouter
    litellm_params:
      model: openrouter/openai/gpt-4o
      api_key: os.environ/OpenRouter_API_KEY
      api_base: https://openrouter.ai/api/v1
    model_info:
      supports_vision: true
```

当前主机已有 `vision-openrouter` 配置；后续实现以当前 LiteLLM 容器配置为准。

不建议默认使用 OCR/caption 降级，因为截图、UI、图表、架构图类任务对视觉布局和语义有要求。

## 12. 配置草案

```yaml
model_list:
  - model_name: claude-opus-4-6
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
      max_tokens: 8192
    model_info:
      max_input_tokens: 192000

  - model_name: claude-opus-4-6-backend
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
      max_tokens: 8192
    model_info:
      max_input_tokens: 192000

  - model_name: opus-summary
    litellm_params:
      model: anthropic/claude-opus-4.8
      api_key: os.environ/OPUS_48_API_KEY

  - model_name: vision-openrouter
    litellm_params:
      model: openrouter/openai/gpt-4o
      api_key: os.environ/OpenRouter_API_KEY
      api_base: https://openrouter.ai/api/v1
    model_info:
      supports_vision: true

router_settings:
  enable_pre_call_checks: true

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  context_management_summary_model: opus-summary

litellm_settings:
  callbacks:
    - custom_callbacks.cc_glm_guard
  drop_params: false
```

如启用后端搜索：

```yaml
litellm_settings:
  callbacks:
    - custom_callbacks.cc_glm_guard
    - websearch_interception
  websearch_interception_params:
    enabled_providers:
      - openai
    search_tool_name: enterprise-search

search_tools:
  - search_tool_name: enterprise-search
    litellm_params:
      search_provider: perplexity
      api_key: os.environ/PERPLEXITY_API_KEY
```

## 13. 请求处理流程

### 13.1 普通代码任务

```text
Claude Code -> LiteLLM /v1/messages
LiteLLM hook 注入 context_management
LiteLLM 检查 token budget
LiteLLM 转发到 GLM-5.2
GLM-5.2 返回 text/tool_use
LiteLLM 返回 Anthropic-compatible stream
Claude Code 执行工具
```

### 13.2 超长上下文任务

```text
Claude Code -> LiteLLM /v1/messages
LiteLLM 估算输入 token
超过 100K: 清理旧 tool_result
超过 150K: 调用 Opus-4.8 生成 summary
LiteLLM 注入 compaction summary
转发压缩后请求到 GLM-5.2
响应中带 compaction block / applied_edits
```

### 13.3 图片任务

```text
Claude Code front-end Opus-4.8 handles image when possible
Fallback: Claude Code -> LiteLLM /v1/messages with image block
LiteLLM hook 识别 image content
路由到 vision-openrouter
LiteLLM 视觉模型完成图片理解
后续纯代码任务可回到 GLM-5.2
```

### 13.4 搜索任务

```text
有 OAuth: Claude Code 原生搜索

无 OAuth / backend_fallback:
Claude Code -> LiteLLM /v1/messages
LiteLLM 插件识别 backend_fallback + 搜索意图
LiteLLM 插件注入 litellm_web_search 工具
LiteLLM websearch_interception 捕获搜索工具
调用企业搜索 provider
将搜索结果交给目标模型生成最终回答
```

## 14. 关键实现要求

1. 自定义 hook 必须结构化处理 JSON，不做脆弱字符串替换。
2. token 估算要保守，未知 tokenizer 使用 LiteLLM token_counter 或 cl100k fallback，并加误差余量。
3. streaming 必须保持 Anthropic SSE 事件兼容。
4. tool_use/tool_result 的 id、顺序、role 不能破坏。
5. compaction 失败时不能静默丢上下文；必须记录错误并按策略原样转发或返回明确错误。
6. 图片路由必须发生在调用 GLM-5.2 前，避免不支持多模态的后端报错。
7. 所有 fallback 都要进入审计日志，便于客户复盘。

## 15. 观测与审计

需要记录以下字段：

1. request_id
2. user/team/key alias
3. external_model
4. internal_route_model
5. input_tokens_estimated
6. output_tokens
7. context_action: none / clear_tool_uses / compact / reject
8. summary_model: opus-summary / opus-4.8 / none
9. multimodal_route: true/false
10. search_backend_used: true/false
11. capability_mode: frontend_capable / backend_fallback
12. fallback_reason
13. provider_error_code
14. latency breakdown

## 16. 验收标准

### 16.1 客户端验收

1. 全新机器只安装 Claude Code。
2. 只配置 `ANTHROPIC_BASE_URL` 和 `ANTHROPIC_API_KEY`。
3. 不安装 router、forky、本地代理。
4. 能完成普通代码问答、读文件、改文件、多轮 tool loop。

### 16.2 上下文验收

1. 100K token 以上自动清理旧 tool results。
2. 150K token 以上自动调用 Opus-4.8 compact。
3. 180K soft limit 附近不触发 GLM-5.2 context overflow。
4. compact 后 Claude Code 后续轮次仍能继续工作。

### 16.3 搜索验收

1. 有 OAuth 时默认使用 Claude Code 原生搜索。
2. 无 OAuth 时后端搜索意图注入 `litellm_web_search` 并由 LiteLLM 搜索兜底处理。
3. 搜索 provider、query、结果摘要进入日志。

### 16.4 图片验收

1. 有 OAuth 时图片输入前端优先使用 Opus-4.8；无 OAuth 或 image block 到达后端时自动路由到 `vision-openrouter`。
2. 纯文本/代码请求不误路由到多模态模型。
3. 多模态回答后能继续进入代码修改流程。

### 16.5 稳定性验收

1. 连续 30 轮 tool loop 不丢 tool_use id。
2. streaming 模式 Claude Code 不报协议解析错误。
3. 后端模型 5xx 时返回可理解错误或执行配置的 fallback。
4. LiteLLM 升级不需要重改 core patch。

## 17. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| GLM-5.2 对 Claude Code tool loop 兼容不足 | 任务中断 | 当前生产默认经 4010 LiteLLM 同侧 Anthropic adapter；同时保留 LiteLLM native 修复路径 |
| 196K 实际可用窗口低于标称 | context overflow | 180K soft limit + 150K compact |
| Opus-4.8 summary 成本较高 | 成本上升 | 只在 150K 以上触发，记录 summary token |
| LiteLLM context_management 行为变更 | 压缩不稳定 | 固定 LiteLLM 版本，回归测试 |
| 多模态模型与代码模型切换导致上下文不一致 | 回答质量波动 | 前端 Opus-4.8 优先；后端视觉模型只做图片理解，后续摘要回灌 GLM-5.2 |
| 搜索前后端职责不清 | 结果不可控 | capability mode 明确分流：有 OAuth 走前端，无 OAuth 走 LiteLLM 后端 |

## 18. 里程碑

### M1: PoC

1. Claude Code 直连 LiteLLM 同侧 Anthropic endpoint。
2. GLM-5.2 完成普通代码任务。
3. LiteLLM hook 注入 context_management。
4. Opus-4.8 summary model 配通。

### M2: 上下文与工具稳定

1. 100K/150K/180K 压测。
2. 30 轮 tool loop 压测。
3. streaming SSE 兼容测试。
4. 确定 4010 adapter 是否长期保留，或是否收敛回 LiteLLM native 4000。

### M3: 搜索与多模态

1. 有 OAuth 时 Claude Code 原生搜索路径验证。
2. 无 OAuth 时 LiteLLM 搜索兜底路径验证。
3. 图片请求前端 Opus-4.8 优先，后端路由 `vision-openrouter`。
4. 多模态结果回到代码流程。

### M4: 生产化

1. key/team/budget 配置。
2. 审计日志与 dashboard。
3. 灰度发布与回滚。
4. 客户现场验收。

## 19. 待确认事项

1. GLM-5.2 MaaS OpenAI-compatible request/response 细节仍需通过真实请求 fixture 校验；endpoint 已从本机 `claude-glm`/LiteLLM 配置确认。
2. Opus-4.8 的具体 provider credential/env name 需与客户平台最终配置对齐；模型版本已确认。
3. 多模态后端使用当前 LiteLLM 视觉模型 `vision-openrouter`；前端使用 Opus-4.8。
4. 搜索按 OAuth 状态分流：有 OAuth 使用 Claude Code 原生能力；无 OAuth 使用 LiteLLM 后端搜索兜底。
5. LiteLLM 部署形态已确认使用当前容器部署。
6. 客户侧已允许做 LiteLLM 插件；当前主机已采用 LiteLLM 同侧 Anthropic adapter 作为生产传输层，不进入客户终端。

## 20. 可复用代码资产

本项目允许复用既有 `forky`、CCR、`claude-glm` 和 LiteLLM adapter 代码中的协议转换、路由、过滤、trace、测试逻辑。但复用边界必须清楚：不能把客户端侧 router/forky 安装形态带回客户终端；客户端仍只交付配置脚本，服务端能力落在 LiteLLM 插件和同侧 Anthropic adapter。

### 20.1 资产清单

| 文件 | 可复用内容 | 注意事项 |
|---|---|---|
| `/root/LiteLLM/assets/config/litellm_config.yaml` | 当前 LiteLLM 模型别名、GLM-5.2 MaaS 配置、`vision-openrouter` 配置、`max_input_tokens`/成本字段 | 作为服务端配置事实来源；不得复制真实密钥 |
| `/root/LiteLLM/docker-compose.yml` | 当前容器部署、插件挂载模式、配置文件挂载模式、镜像版本 | 用于 EPIC-09 部署方案；沿用当前容器，不重建新入口 |
| `/root/.claude-code-router/config.json` | 当前 `claude-glm` 路由事实、LiteLLM adapter 路径、`vision-openrouter`/image route、long context 阈值经验 | 只作为现状参考；新方案不要求客户端安装 CCR |
| `/root/.claude-code-router/custom-router.js` | 模型 allowlist、未知模型拒绝策略、image content 检测和路由放行逻辑 | 可移植到 LiteLLM 插件的模型校验和多模态识别 |
| `/root/.claude-code-router/plugins/claude-thinking-filter.js` | `thinking`/`redacted_thinking` 请求和流式响应过滤思路 | 不能照抄删除 `context_management`；本项目需要注入/保留 context management |
| `/root/.claude-code-router/plugins/claude-websearch-to-responses.js` | Claude WebSearch 到 LiteLLM search 工具的转换、搜索意图识别、SSE thinking 过滤 | 用于无 OAuth/backend fallback 的后端搜索兜底 |
| `/root/litellm-anthropic-adapter/server.js` | Anthropic `/v1/messages` 到 OpenAI chat 的消息、tool、image、streaming SSE 转换 | 当前主机生产传输层参考实现；不作为客户端组件 |
| `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs` | Responses 输入到 Anthropic messages、tool 转换、image block 归一化、trace 脱敏、队列/重试、Anthropic SSE 到 Responses | 可用于 EPIC-04/06/08/10 的转换和测试参考 |
| `/root/.codex-forky/codex-forky-responses-bridge.cjs` | 更完整的 forky Responses bridge、tool_use/tool_result 处理、流式事件转换、可选 sidecar 设计 | 只作为服务端 sidecar 兜底参考；不要复用 Codex OAuth 路径到本项目默认主线 |
| `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | env/config 生成、模型目录生成、`vision-openrouter` image route、可选 search transformer 生成、验证脚本结构 | 只复用配置生成和验证思想；不复用安装 CCR 的客户端行为 |
| `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/scripts/configure-claude-glm.sh` | `claude-glm` 包装器、LiteLLM adapter 接入、180K auto-compact 阈值经验、验证流程 | 仅参考客户端配置脚本的输入/幂等/脱敏输出；不得安装 CCR/adapter 到客户终端 |
| `/root/codex-huawei-maas/tests/test-shim-transform.js` | shim 转换单测结构 | 用于 EPIC-10 测试结构参考 |
| `/root/codex-huawei-maas/tests/fixtures/responses-tool-request.json` | tool request fixture | 用于 EPIC-10 fixture 起点 |
| `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/tests/concurrent-top30.sh` | Claude tool loop/并发/输出格式生产验收用例 | 用于 EPIC-10 端到端验收参考 |

### 20.2 Epic 对应参考文件

| Epic | 主要参考文件 | 复用说明 |
|---|---|---|
| EPIC-01 项目骨架与交付物基线 | `/root/codex-huawei-maas/README.md`, `/root/codex-huawei-maas/SKILL.md` | 参考文档组织和脚本/测试目录结构 |
| EPIC-02 Claude Code 客户端配置脚本 | `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/scripts/configure-claude-glm.sh`, `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | 只复用 env 输入、幂等、脱敏输出、smoke test 思路；删除 CCR/forky 安装逻辑 |
| EPIC-03 LiteLLM 插件基础框架 | `/root/LiteLLM/docker-compose.yml`, `/root/LiteLLM/assets/config/litellm_config.yaml`, `/root/.claude-code-router/plugins/claude-thinking-filter.js` | 参考当前插件挂载方式、配置命名和参数过滤；保留 context management |
| EPIC-04 GLM-5.2 模型路由与参数清洗 | `/root/.claude-code-router/custom-router.js`, `/root/.claude-code-router/config.json`, `/root/litellm-anthropic-adapter/server.js`, `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs` | 复用模型 allowlist、未知模型拒绝、Anthropic/OpenAI 参数转换和 tool 转换思路 |
| EPIC-05 196K 上下文保护与 Opus-4.8 compact | `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/scripts/configure-claude-glm.sh`, `/root/.claude-code-router/config.json`, `/root/LiteLLM/assets/config/litellm_config.yaml` | 复用 180K 阈值经验和当前 GLM-5.2 `max_input_tokens`；实现改为 LiteLLM 插件注入 context management |
| EPIC-06 多模态请求路由 | `/root/.claude-code-router/custom-router.js`, `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs`, `/root/.codex-forky/codex-forky-responses-bridge.cjs`, `/root/LiteLLM/assets/config/litellm_config.yaml` | 复用 image block 检测、image block 归一化和 `vision-openrouter` 配置 |
| EPIC-07 OAuth 感知搜索分流 | `/root/.claude-code-router/plugins/claude-websearch-to-responses.js`, `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | 有 OAuth 走 Claude Code 原生搜索；无 OAuth/backend fallback 复用 `websearch_interception` 转换和配置生成 |
| EPIC-08 LiteLLM 同侧 Anthropic adapter 生产路径 | `/root/litellm-anthropic-adapter/server.js`, `/root/.codex-forky/codex-forky-responses-bridge.cjs`, `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs` | 复用 adapter、bridge、SSE、tool loop、trace/重试能力，作为服务端同侧生产路径参考 |
| EPIC-09 部署、配置与观测 | `/root/LiteLLM/docker-compose.yml`, `/root/LiteLLM/.env`, `/root/LiteLLM/assets/config/litellm_config.yaml`, `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | 复用当前容器挂载、env 脱敏、配置生成和验证方式 |
| EPIC-10 测试与验收套件 | `/root/codex-huawei-maas/tests/test-shim-transform.js`, `/root/codex-huawei-maas/tests/fixtures/responses-tool-request.json`, `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/tests/concurrent-top30.sh`, `/root/codex-huawei-maas/tests/PRODUCTION-TEST-PLAN.md` | 复用单测 fixture、tool loop、并发和生产验收结构 |

## 21. 参考文档

1. LiteLLM `/v1/messages`: https://docs.litellm.ai/docs/anthropic_unified/
2. LiteLLM Claude Code Quickstart: https://docs.litellm.ai/docs/tutorials/claude_responses_api
3. LiteLLM Claude Code Context Management: https://docs.litellm.ai/docs/claude_code_context_management
4. LiteLLM Claude Code WebSearch: https://docs.litellm.ai/docs/tutorials/claude_code_websearch
5. LiteLLM custom call hooks: https://docs.litellm.ai/docs/proxy/call_hooks
6. LiteLLM context window pre-call checks: https://docs.litellm.ai/docs/proxy/reliability
