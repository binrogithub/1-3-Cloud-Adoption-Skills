# Epics: Claude Code 直连 LiteLLM 的 GLM-5.2 服务侧适配

来源 PRD: [PRD.md](./PRD.md)

## 1. 交付物确认

本项目只交付两个核心输出件：

1. Claude Code 客户端配置脚本：`scripts/configure-claude-code-litellm.sh`
2. LiteLLM 服务侧插件：`litellm_plugins/cc_glm52_guard/`

非交付物：

1. 不交付客户端 router。
2. 不交付客户端 forky。
3. 不修改 Claude Code 源码。
4. 不 fork LiteLLM core。

## 2. 已确认决策

| 决策项 | 结论 |
|---|---|
| 客户端形态 | Claude Code 原生客户端，只配置 LiteLLM endpoint/key/model |
| 服务入口 | LiteLLM 是唯一客户端入口 |
| 默认执行模型 | MaaS GLM-5.2，按 196K 上下文窗口做服务侧保护 |
| 上下文 soft limit | 180K |
| compact trigger | 150K |
| tool result 清理 trigger | 100K |
| compact summary 模型 | Opus-4.8 |
| 图片/多模态 | 有 OAuth 时前端 Opus-4.8 优先；无 OAuth 或 image block 到达后端时使用 `vision-openrouter` |
| 搜索 | 有 OAuth 使用 Claude Code 原生搜索；无 OAuth 使用 LiteLLM 后端搜索兜底 |
| Capability mode | 客户端脚本 `auto` 检测 OAuth；后端用 `frontend_capable` / `backend_fallback` 执行分流 |
| 服务侧 adapter 形态 | 当前主机生产默认使用 LiteLLM 同侧 Anthropic adapter；不部署任何客户端 adapter/router/forky |
| forky 形态 | 不上客户端；只复用协议转换思路和 fixture，不保留旧 wrapper/daemon |
| LiteLLM 改造方式 | custom callback/pre-call hook 插件，避免深 fork |
| GLM-5.2 endpoint 来源 | 从当前主机 `claude-glm`/LiteLLM 配置获取 |
| LiteLLM 部署形态 | 使用当前容器部署，容器 `litellm_proxy`，镜像 `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3` |
| 插件许可 | 允许做 LiteLLM 插件 |

当前主机配置事实：

```text
LiteLLM native URL: http://127.0.0.1:4000
Claude Code production URL: http://127.0.0.1:4010
Claude Code production transport: LiteLLM-side Anthropic adapter
LiteLLM config: /root/LiteLLM/assets/config/litellm_config.yaml
GLM alias: glm-5.2
Claude Code external alias: claude-opus-4-6
GLM provider model: openai/glm-5.2
GLM api_base env: HUAWEI_MAAS_API_BASE
GLM api_base value: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
GLM api_key env: HUAWEI_MAAS_API_KEY_0
Vision alias: vision-openrouter
```

## 3. 遗留事项确认

### 3.1 仍需确认

| ID | 遗留事项 | 影响 | Owner | 阻塞项 |
|---|---|---|---|---|
| OI-01 | GLM-5.2 request/response、streaming、tool call 细节仍需真实 fixture 校验；endpoint 已确认 | 决定参数清洗和 SSE 兼容边界 | 实现团队 | EPIC-03, EPIC-04, EPIC-10 |
| OI-02 | Opus-4.8 的 provider credential/env name 需与客户平台最终配置对齐；模型版本已确认 | 决定 `opus-summary` 具体配置 | 客户/平台团队 | EPIC-05 |
| OI-03 | Claude Code 前端 Opus-4.8 多模态请求样例仍需采集；后端视觉 alias 已确认为 `vision-openrouter` | 决定 image block fixture 和前后端分流细节 | 实现团队 | EPIC-06 |
| OI-04 | LiteLLM 后端搜索 provider 和 `websearch_interception` 生产配置仍需确认；无 OAuth 的后端兜底策略已确认 | 决定后端搜索生产可用性 | 客户安全/合规 | EPIC-07 |
| OI-05 | 当前 LiteLLM 容器部署的插件挂载路径和重启窗口需确认 | 决定发布步骤 | 平台团队 | EPIC-09 |
| OI-06 | LiteLLM 原生 `/v1/messages` 到 MaaS GLM 的 `/responses` 路径不兼容；当前使用 4010 adapter，后续需决定是否修复 LiteLLM 原生路径或长期保留 sidecar | 决定最终入口是否从 4010 收敛回 4000 | 实现团队/平台团队 | EPIC-08, EPIC-09 |
| OI-07 | Claude Code 当前版本发出的真实 `/v1/messages` 请求样例 | 决定插件兼容测试 fixture | 实现团队 | EPIC-03, EPIC-10 |
| OI-08 | GLM-5.2 真实可用上下文窗口压测结果 | 决定 180K soft limit 是否需要下调 | 实现团队 | EPIC-05 |

### 3.2 不再开放的问题

| ID | 原问题 | 当前结论 |
|---|---|---|
| CI-01 | summary model 用什么 | 用 Opus-4.8 |
| CI-02 | 图片是否 OCR/caption 降级 | 默认不用；前端 Opus-4.8 优先，后端走 `vision-openrouter` |
| CI-03 | 客户端是否安装 router/forky | 不安装 |
| CI-04 | 能否改 Claude Code 上下文配置 | 不依赖客户端改配置 |
| CI-05 | forky 是否直接塞进 LiteLLM 包 | 不塞；当前只保留 LiteLLM 同侧 Anthropic adapter，不使用客户端 forky |
| CI-06 | LiteLLM 部署形态 | 使用当前容器部署 |
| CI-07 | 是否允许做 LiteLLM 插件 | 允许 |
| CI-08 | 搜索默认路径 | 有 OAuth 用 Claude Code 原生搜索；无 OAuth 用 LiteLLM 后端搜索 |
| CI-09 | 如何让后端知道无 OAuth | 客户端脚本 auto 检测后使用 backend model alias，并可写 `CLAUDE_CODE_CAPABILITY_MODE` |

## 4. Epic 总览

| Epic | 名称 | 优先级 | 主要产出 |
|---|---|---|---|
| EPIC-01 | 项目骨架与交付物基线 | P0 | 目录、README、配置模板 |
| EPIC-02 | Claude Code 客户端配置脚本 | P0 | `configure-claude-code-litellm.sh` |
| EPIC-03 | LiteLLM 插件基础框架 | P0 | `cc_glm52_guard` callback |
| EPIC-04 | GLM-5.2 模型路由与参数清洗 | P0 | 默认文本/代码路径 |
| EPIC-05 | 196K 上下文保护与 Opus-4.8 compact | P0 | context management 注入/修正 |
| EPIC-06 | 多模态请求路由 | P1 | 前端 Opus-4.8 优先，后端 `vision-openrouter` |
| EPIC-07 | OAuth 感知搜索分流 | P1 | 有 OAuth 前端搜索；无 OAuth 后端 `litellm_web_search` 兜底 |
| EPIC-08 | LiteLLM 同侧 Anthropic adapter 生产路径 | P0 | 4010 adapter 接入、健康检查、E2E |
| EPIC-09 | 部署、配置与观测 | P0 | LiteLLM 配置样例、日志字段 |
| EPIC-10 | 测试与验收套件 | P0 | 单测、fixture、端到端验收脚本 |

## 5. Epic 参考文件映射

复用原则：可以复用 forky、CCR、`claude-glm` 和 adapter 里的转换、过滤、trace、测试代码；不能复用会让客户终端安装 router/forky 的部署形态。客户端交付仍只有配置脚本，服务端交付仍是 LiteLLM 插件。

| Epic | 参考文件 | 对应复用点 |
|---|---|---|
| EPIC-01 项目骨架与交付物基线 | `/root/codex-huawei-maas/README.md`; `/root/codex-huawei-maas/SKILL.md` | 文档结构、脚本目录、测试目录组织 |
| EPIC-02 Claude Code 客户端配置脚本 | `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/scripts/configure-claude-glm.sh`; `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | env 输入、幂等执行、脱敏输出、smoke test；必须删除 CCR/forky 安装逻辑 |
| EPIC-03 LiteLLM 插件基础框架 | `/root/LiteLLM/docker-compose.yml`; `/root/LiteLLM/assets/config/litellm_config.yaml`; `/root/.claude-code-router/plugins/claude-thinking-filter.js` | 当前容器插件挂载方式、配置命名、Claude-only 参数过滤；不能照抄删除 `context_management` |
| EPIC-04 GLM-5.2 模型路由与参数清洗 | `/root/.claude-code-router/custom-router.js`; `/root/.claude-code-router/config.json`; `/root/litellm-anthropic-adapter/server.js`; `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs` | 模型 allowlist、未知模型拒绝、Anthropic/OpenAI 参数转换、tool_use/tool_result 转换 |
| EPIC-05 196K 上下文保护与 Opus-4.8 compact | `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/scripts/configure-claude-glm.sh`; `/root/.claude-code-router/config.json`; `/root/LiteLLM/assets/config/litellm_config.yaml` | 180K auto-compact 阈值经验、long context route 经验、当前 GLM-5.2 token 配置 |
| EPIC-06 多模态请求路由 | `/root/.claude-code-router/custom-router.js`; `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs`; `/root/.codex-forky/codex-forky-responses-bridge.cjs`; `/root/LiteLLM/assets/config/litellm_config.yaml` | image block 检测、image 归一化、`vision-openrouter` 后端视觉模型配置 |
| EPIC-07 OAuth 感知搜索分流 | `/root/.claude-code-router/plugins/claude-websearch-to-responses.js`; `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | WebSearch 到 LiteLLM search 工具转换、搜索意图识别、后端搜索配置生成 |
| EPIC-08 LiteLLM 同侧 Anthropic adapter 生产路径 | `/root/litellm-anthropic-adapter/server.js`; `/root/.codex-forky/codex-forky-responses-bridge.cjs`; `/root/codex-huawei-maas/scripts/codex-glm-ccr-responses-shim.cjs` | 已验证的 Anthropic->OpenAI chat 转换、SSE 转换、tool loop 转换、trace 脱敏、队列/重试；不能复用客户端部署形态 |
| EPIC-09 部署、配置与观测 | `/root/LiteLLM/docker-compose.yml`; `/root/LiteLLM/.env`; `/root/LiteLLM/assets/config/litellm_config.yaml`; `/root/codex-huawei-maas/scripts/configure-codex-glm.sh` | 当前容器部署、env 脱敏、配置模板生成、验证命令 |
| EPIC-10 测试与验收套件 | `/root/codex-huawei-maas/tests/test-shim-transform.js`; `/root/codex-huawei-maas/tests/fixtures/responses-tool-request.json`; `/root/1-3-Cloud-Adoption-Skills/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-huawei-maas/tests/concurrent-top30.sh`; `/root/codex-huawei-maas/tests/PRODUCTION-TEST-PLAN.md` | 单测 fixture、tool loop、并发、生产验收用例 |

## EPIC-01: 项目骨架与交付物基线

### 目标

建立项目目录、文档、配置模板和最小开发约束，保证后续实现围绕两个交付物展开。

### 范围

1. 创建 `scripts/`、`litellm_plugins/cc_glm52_guard/`、`tests/`。
2. 创建项目 `README.md`。
3. 固化两个输出件说明。
4. 添加示例环境变量文件。

### 任务

1. 建立目录结构。
2. 添加 `README.md`，说明客户端无 router/forky 约束。
3. 添加 `config.example.yaml`，覆盖 GLM-5.2、Opus-4.8、`vision-openrouter`、原生搜索默认策略。
4. 添加 `.env.example`，只保留变量名，不写真实密钥。

### 验收标准

1. 项目目录与 PRD 的目录规划一致。
2. README 能让实现人员理解交付物边界。
3. 示例配置不包含真实 secret。

### 依赖

无。

## EPIC-02: Claude Code 客户端配置脚本

### 目标

提供一个幂等脚本，让客户机器上的原生 Claude Code 直接指向 LiteLLM。

### 范围

1. 生成或更新 Claude Code 所需环境配置。
2. 不安装任何本地代理或后台服务。
3. 输出 smoke test 命令。
4. 支持 dry-run。
5. 支持 `--capability-mode auto|frontend|backend`。
6. auto 模式检测 Claude Code OAuth；无 OAuth 时选择 backend fallback 模型别名。

### 用户故事

作为客户终端用户，我只安装 Claude Code，然后执行一个脚本，就能使用企业 LiteLLM endpoint。

### 任务

1. 实现 `scripts/configure-claude-code-litellm.sh`。
2. 支持输入 `LITELLM_BASE_URL`、`LITELLM_API_KEY`、`CLAUDE_CODE_MODEL_ALIAS`。
3. 当前主机默认模型别名为 `claude-opus-4-6`。
4. 当前主机默认后端兜底模型别名为 `claude-opus-4-6-backend`。
5. 检测 `claude` 是否在 PATH。
6. 检测本机 Claude Code OAuth 状态，不读取或输出 token 内容。
7. 输出当前配置摘要，mask API key。
8. 提供 `--dry-run` 和 `--print-env`。
9. 自动发现当前主机 4010 LiteLLM-side Anthropic adapter；未发现时回退 4000 LiteLLM native endpoint。

### 验收标准

1. 脚本不安装 router/forky。
2. 脚本可重复执行，重复执行不产生冲突配置。
3. 脚本执行后 Claude Code 请求发往 LiteLLM。
4. key 输出必须脱敏。
5. 有 OAuth 时 mode 为 `frontend_capable`；无 OAuth 时 mode 为 `backend_fallback`。
6. backend fallback 时默认模型别名能被 LiteLLM 插件识别。

### 依赖

1. LiteLLM endpoint 和 virtual key。
2. 客户端允许设置环境变量或 shell profile。

## EPIC-03: LiteLLM 插件基础框架

### 目标

实现可被 LiteLLM 加载的 `cc_glm52_guard` custom callback，作为后续路由、上下文、多模态、审计逻辑的承载点。

### 范围

1. 插件 Python package。
2. `proxy_handler_instance` 导出。
3. `async_pre_call_hook` 实现。
4. 结构化 JSON 处理。
5. 最小单元测试。

### 用户故事

作为平台管理员，我可以在 LiteLLM 配置里加载插件，而不修改 LiteLLM core。

### 任务

1. 创建 `litellm_plugins/cc_glm52_guard/__init__.py`。
2. 创建 `callback.py`。
3. 实现配置读取：阈值、模型别名、搜索策略、多模态策略、capability mode。
4. 实现请求识别：Claude Code `/v1/messages`、普通 chat、count_tokens。
5. 实现审计 metadata 注入。
6. 支持从 metadata、backend model alias、环境变量识别 `backend_fallback`。
6. 添加加载示例。

### 验收标准

1. LiteLLM 配置 `callbacks: cc_glm52_guard.proxy_handler_instance` 可加载。
2. 插件加载失败时有明确错误。
3. 单测覆盖空请求、普通文本请求、非法结构请求。

### 依赖

1. LiteLLM 目标版本。
2. Claude Code 真实请求样例。

## EPIC-04: GLM-5.2 模型路由与参数清洗

### 目标

将 Claude Code 外部模型别名稳定路由到 GLM-5.2，并清理 MaaS 后端不支持的参数。

### 范围

1. 默认文本/代码请求路由 GLM-5.2。
2. 外部模型名保持 Claude Code 兼容。
3. 内部模型配置使用 MaaS OpenAI-compatible endpoint。
4. 参数 allowlist/drop/transform。

### 用户故事

作为 Claude Code 用户，我选择 `claude-opus-4-6`，但服务侧实际使用企业 GLM-5.2 执行代码任务。

### 任务

1. 实现 external model 到 internal route model 的映射。
2. 清理 GLM-5.2 不支持参数。
3. 保留 tool_use/tool_result 结构所需字段。
4. 处理 `max_tokens`、`temperature`、`top_p` 等基础参数。
5. 写入 `internal_route_model=glm-5.2` 审计字段。

### 验收标准

1. 普通代码问答能路由到 GLM-5.2。
2. 不因未知参数导致 MaaS 400。
3. 模型映射在日志中可追踪。

### 依赖

1. OI-01 GLM-5.2 request/response fixture 校验。
2. OI-07 Claude Code 请求样例。

## EPIC-05: 196K 上下文保护与 Opus-4.8 compact

### 目标

在客户端不改上下文配置的前提下，服务侧保护 GLM-5.2 196K 窗口，并用 Opus-4.8 执行 compact summary。

### 范围

1. 默认注入 `context_management`。
2. 已有 `context_management` 时合并并夹紧阈值。
3. 100K 清理旧 tool results。
4. 150K 调用 Opus-4.8 compact。
5. 180K soft limit 保护。
6. 196K hard limit 防溢出。

### 用户故事

作为 Claude Code 用户，我可以进行长上下文代码任务，不需要手工调整客户端上下文设置，也不容易撞到 GLM-5.2 context overflow。

### 任务

1. 实现 token 估算函数。
2. 未提供 `context_management` 时注入默认 edits。
3. 已提供 edits 时保留用户意图并修正危险阈值。
4. 配置 `general_settings.context_management_summary_model=opus-summary`。
5. compact 失败时记录错误并执行预设策略。
6. 写入 `context_action`、`summary_model`、`input_tokens_estimated`。

### 验收标准

1. 100K 以上触发旧 tool results 清理。
2. 150K 以上触发 Opus-4.8 compact。
3. 180K 附近不触发 GLM-5.2 context overflow。
4. compact 后后续 Claude Code 轮次可继续。
5. summary 调用成本可在日志中统计。

### 依赖

1. OI-02 Opus-4.8 provider credential/env name。
2. OI-08 GLM-5.2 窗口压测结果。

## EPIC-06: 多模态请求路由

### 目标

识别 Claude Code 发来的图片/多模态请求。前端可处理时使用 Opus-4.8；进入后端时路由到当前 LiteLLM 视觉模型 `vision-openrouter`。

### 范围

1. 识别 Anthropic image content block。
2. 识别文件图片或截图类输入。
3. 后端兜底路由到 `vision-openrouter`。
4. 多模态结果可回灌后续代码流程。

### 用户故事

作为 Claude Code 用户，我可以上传截图或图片；前端优先用 Opus-4.8 处理，后端兜底使用 `vision-openrouter`，不会把图片错误发给 GLM-5.2。

### 任务

1. 实现 image block 检测。
2. 实现 `multimodal_route=true` 审计字段。
3. 复用当前 LiteLLM `vision-openrouter` 模型别名。
4. 验证纯文本请求不误路由。
5. 验证多模态回答后可继续普通代码任务。

### 验收标准

1. 图片请求前端优先使用 Opus-4.8；进入后端时路由到 `vision-openrouter`。
2. 纯文本/代码请求仍路由 GLM-5.2。
3. 不默认使用 OCR/caption 降级路径。

### 依赖

1. OI-03 Claude Code 前端 Opus-4.8 多模态请求样例。
2. Claude Code 图片请求样例。

## EPIC-07: OAuth 感知搜索分流

### 目标

按 OAuth 状态分流搜索能力：有 OAuth 时使用 Claude Code 原生搜索；无 OAuth / `backend_fallback` 时使用 LiteLLM 服务侧搜索兜底。

### 范围

1. 搜索策略配置化，默认 `native`。
2. 有 OAuth / `frontend_capable` 时不接管前端原生搜索。
3. 无 OAuth / `backend_fallback` 且有搜索意图时注入 `litellm_web_search`。
4. 支持 `websearch_interception` 配置。
5. 支持 search provider 配置。
6. 搜索审计字段。

### 用户故事

作为企业管理员，我可以让有 OAuth 的 Claude Code 使用原生搜索；无 OAuth 的客户端自动走 LiteLLM 后端搜索兜底。

### 任务

1. 设计 `search_mode`: `native` / `backend_forced` / `disabled`。
2. 配置 LiteLLM `websearch_interception` 示例。
3. 支持 Perplexity/Tavily/Exa/SearXNG 等 provider 替换。
4. 实现 backend fallback 搜索意图检测和 `litellm_web_search` 注入。
5. 写入 `capability_mode`、`search_backend_used`、`fallback_reason`。
6. 增加搜索路径验收 fixture。

### 验收标准

1. `frontend_capable` 不注入后端搜索工具。
2. `backend_fallback` 搜索意图注入 `litellm_web_search`。
3. 后端搜索开启时结果可审计。
4. 搜索 provider 可通过配置替换。

### 依赖

1. OI-04 后端搜索 provider 和 `websearch_interception` 生产配置。
2. 搜索 provider key。

## EPIC-08: LiteLLM 同侧 Anthropic adapter 生产路径

### 目标

当 LiteLLM 原生 `/v1/messages` 路径不足以稳定支持 Claude Code tool loop 时，使用 LiteLLM 同侧 Anthropic adapter 作为当前生产入口。

### 范围

1. 定义 Claude Code -> adapter -> LiteLLM chat 的服务侧接入边界。
2. 不部署到客户端。
3. 使用 `GET /health` 做健康检查。
4. 保留未来收敛回 LiteLLM native 4000 的开关。

### 用户故事

作为平台工程师，如果 LiteLLM 原生 Anthropic 路径对 MaaS GLM 不稳定，我可以在服务侧启用 4010 adapter，而不影响客户端安装约束。

### 任务

1. 固化 4010 adapter 输入输出协议。
2. 复用 `/root/litellm-anthropic-adapter/server.js` 的 Anthropic/OpenAI chat 转换逻辑。
3. 定义启用开关。
4. 定义回滚方式。
5. 写入 adapter 使用时的审计字段。
6. 确认 adapter 只读取 LiteLLM virtual key，不读取旧 `CLAUDE_GLM_ROUTER_KEY` / `LITELLM_CCR_KEY`。

### 验收标准

1. adapter 不出现在客户端。
2. Claude Code 通过 4010 可完成文本和工具调用。
3. adapter 开启时能处理复杂 tool loop 或 SSE 修复场景。
4. adapter 关闭后可显式回退到 4000 native 路径做验证。

### 依赖

1. OI-06 LiteLLM native `/v1/messages` 修复或长期保留 adapter 的决策。
2. EPIC-10 tool loop 压测结果。

## EPIC-09: 部署、配置与观测

### 目标

形成可部署、可审计、可灰度、可回滚的 LiteLLM 服务侧配置。

### 范围

1. `config.example.yaml`。
2. 环境变量模板。
3. 日志字段。
4. key/team/budget 建议。
5. 灰度和回滚说明。

### 用户故事

作为平台管理员，我可以把插件接入现有 LiteLLM，并看到每个请求的模型路由、上下文动作、搜索/多模态/fallback 情况。

### 任务

1. 编写 LiteLLM config example。
2. 明确环境变量命名。
3. 定义审计字段输出格式。
4. 添加当前容器部署说明和插件挂载方式。
5. 添加版本锁定建议。
6. 添加 rollback checklist。

### 验收标准

1. 配置可直接作为部署模板。
2. 不泄露 secret。
3. 每次 fallback 都有日志。
4. LiteLLM 升级不需要 core patch。

### 依赖

1. OI-05 当前容器部署的插件挂载路径和重启窗口。
2. 客户日志/监控系统。

## EPIC-10: 测试与验收套件

### 目标

建立覆盖客户端配置、插件路由、上下文、多模态、搜索、streaming 和 tool loop 的测试套件。

### 范围

1. 单元测试。
2. 请求 fixture。
3. 端到端 smoke test。
4. 压测脚本。
5. 客户验收 checklist。

### 用户故事

作为实现团队，我可以在每次改插件或升级 LiteLLM 后快速确认 Claude Code 仍能稳定工作。

### 任务

1. 添加 `tests/test_model_routing.py`。
2. 添加 `tests/test_context_management.py`。
3. 添加 `tests/test_multimodal_routing.py`。
4. 添加 OAuth/capability mode 搜索策略测试。
5. 添加 30 轮 tool loop 验收脚本。
6. 添加 100K/150K/180K 上下文压测 fixture。
7. 添加 streaming SSE 兼容测试。

### 验收标准

1. 单测覆盖插件核心分支。
2. 30 轮 tool loop 不丢 tool_use id。
3. 180K 附近不触发 context overflow。
4. 图片请求不误发 GLM-5.2。
5. 有 OAuth 的 Claude Code 原生搜索路径有验证；无 OAuth/backend fallback 搜索注入有验证。

### 依赖

1. OI-01 GLM-5.2 request/response fixture 校验。
2. OI-07 Claude Code 真实请求样例。
3. 可用测试 key。

## 6. 建议执行顺序

1. EPIC-01: 项目骨架与交付物基线
2. EPIC-02: Claude Code 客户端配置脚本
3. EPIC-03: LiteLLM 插件基础框架
4. EPIC-04: GLM-5.2 模型路由与参数清洗
5. EPIC-05: 196K 上下文保护与 Opus-4.8 compact
6. EPIC-10: 测试与验收套件的 P0 子集
7. EPIC-06: 多模态请求路由
8. EPIC-07: OAuth 感知搜索分流
9. EPIC-08: LiteLLM 同侧 Anthropic adapter 生产路径
10. EPIC-09: 部署、配置与观测

说明：当前主机 EPIC-08 已进入默认主路径，因为 LiteLLM native `/v1/messages` 到 MaaS GLM 的 `/responses` 路径未通过验证。

## 7. M1 最小可验收切片

M1 只做最小闭环：

1. 原生 Claude Code 通过配置脚本直连 LiteLLM 同侧 Anthropic endpoint。
2. LiteLLM 插件加载成功。
3. 普通文本/代码任务路由到 GLM-5.2。
4. 服务侧自动注入 `context_management`。
5. 150K 以上可触发 Opus-4.8 compact。
6. 基础日志包含 external_model、internal_route_model、input_tokens_estimated、context_action。

M1 不强制包含：

1. 后端 `vision-openrouter` 完整路径。
2. 完整生产后端搜索 provider 接入。
3. 生产级 dashboard。
4. 生产级 dashboard。

## 8. M2/M3 验收切片

### M2

1. 100K/150K/180K 上下文压测。
2. 30 轮 tool loop 压测。
3. streaming SSE 兼容测试。
4. 确认 4010 adapter 是否长期保留，或是否收敛回 LiteLLM native 4000。

### M3

1. 图片请求前端 Opus-4.8 优先，后端路由 `vision-openrouter`。
2. 有 OAuth 的 Claude Code 原生搜索路径验证。
3. 无 OAuth 的后端搜索兜底路径验证。
4. 多模态结果能继续进入代码流程。

## 9. 关键风险跟踪

| 风险 | 关联 Epic | 当前处理 |
|---|---|---|
| GLM-5.2 tool loop 不稳定 | EPIC-04, EPIC-08, EPIC-10 | 当前主路径使用 4010 adapter；并行跟踪 LiteLLM native 修复 |
| 196K 标称窗口与实际窗口不一致 | EPIC-05, EPIC-10 | 180K soft limit + 压测校准 |
| Opus-4.8 summary 成本高 | EPIC-05, EPIC-09 | 150K 才触发，日志记录 summary token |
| LiteLLM 版本变更影响 callback/context_management | EPIC-03, EPIC-09, EPIC-10 | 固定版本 + 回归测试 |
| 多模态与代码模型上下文切换质量不稳定 | EPIC-06, EPIC-10 | 前端 Opus-4.8 优先；后端 `vision-openrouter` 只做理解，后续回灌文本摘要 |
| 搜索职责不清 | EPIC-07 | capability mode 明确分流：有 OAuth 前端搜索，无 OAuth 后端搜索 |
