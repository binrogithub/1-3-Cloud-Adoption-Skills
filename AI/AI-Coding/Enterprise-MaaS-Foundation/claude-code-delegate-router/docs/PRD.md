# PRD：Claude Code Direct MaaS Delegate Router

状态：v1.0，设计已确认  
日期：2026-08-19  
项目目录：`/root/claude-code-delegate-router`  
产品边界：无 LiteLLM、无 Claude Code Router、无 Sidecar

## 1. 产品摘要

本项目为 Claude Code 提供两个彼此隔离、行为明确的入口：

- `claude`：保留官方 Claude Code 的 Anthropic OAuth 登录和原生传输，负责高判断任务、图片任务、规划和委托编排。
- `claude-maas`：无需 Anthropic 登录，使用独立的华为云 MaaS Key，通过 MaaS 原生 Anthropic Messages API 直接调用 `glm-5.2`。

当用户已登录 Anthropic 时，`claude` 可以把普通编码、测试、文档、批处理和其他执行类任务，通过 `delegate` 或 `workflow` 显式委托给 `claude-maas`。当用户未登录 Anthropic 时，可以直接使用 `claude-maas` 完成 MaaS-only 工作。

本项目名称中的 Router 是“任务级路由器”，不是 HTTP Router。系统不启动本地代理、不转换协议、不监听端口，也不在一次会话内暗中切换供应商。

```text
已登录 Anthropic：

user -> claude -> Anthropic OAuth
          |  规划、高风险、图片、复杂问题：留在当前会话
          |
          +-> delegate/workflow -> claude-maas
                                   -> Huawei MaaS Anthropic API
                                   -> glm-5.2

未登录 Anthropic：

user -> claude-maas -> Huawei MaaS Anthropic API -> glm-5.2
```

## 2. 背景与已验证事实

原 `litellm-auto-plugin` 的核心链路是 Claude Code `/v1/messages` → LiteLLM → 华为 MaaS，并通过插件处理 Anthropic/OpenAI 协议转换、流式事件、thinking、工具调用、模型路由和 Sidecar。

华为 MaaS 现已提供原生 Anthropic 入口。2026-08-19 在实际 MaaS 环境中完成以下不经过 LiteLLM、CCR 或其他 Router 的验证：

| 用例 | 结果 |
| --- | --- |
| `POST /anthropic/v1/messages` 非流式文本 | 通过；返回 Anthropic `message`、`thinking`、`text`、usage |
| Anthropic SSE 流 | 通过；事件最终以 `message_stop` 结束 |
| pretty-JSON / 无前缀 SSE 行 | 未复现 |
| `message_stop` 后 OpenAI `[DONE]` | 未复现 |
| `thinking: {"type":"adaptive"}` | 通过；thinking/text block 与 delta 类型匹配 |
| 自动 `tool_choice` | 通过；返回结构化 `tool_use` |
| 强制指定工具 | 通过；不再返回原先的 schema 400 |
| Claude Code 2.1.228，全新配置、无 OAuth、token-only | 通过；`modelUsage` 为 `glm-5.2` |
| Claude Code 完整工具往返 | 通过；`tool_use → Bash → tool_result → final` |
| 图片输入 | 不支持；HTTP 400 |

因此，协议转换与已修复问题不再需要常驻运行时中间件。原项目中的兼容知识应保留为发布前回归探针，而不是继续保留 LiteLLM/CCR。

## 3. 产品目标

### 3.1 必须实现

1. 保持原生 `claude` 命令、OAuth 凭证、配置和网络路径不变。
2. 提供独立 `claude-maas` 命令，未登录 Anthropic 时也能直接调用华为 MaaS `glm-5.2`。
3. `claude-maas` 的所有模型流量必须 100% 指向配置的华为 MaaS `glm-5.2`。
4. 提供 OAuth 模式下的任务分类、`delegate` 单任务委托与 `workflow` 工作流委托。
5. 凭证、配置、审计和 Claude Code 状态必须相互隔离。
6. 委托必须具备验收命令、两次尝试上限、超时、最大 turns、并发上限和明确升级语义。
7. 提供可重复的直连 Anthropic API 与真实 Claude Code 验证套件。
8. 安装、升级和卸载必须幂等且可逆。

### 3.2 明确非目标

- 不部署或依赖 LiteLLM。
- 不安装或依赖 `@musistudio/claude-code-router`/CCR。
- 不实现 HTTP 代理、协议转换服务或本地监听端口。
- 不使用 Vision/Premium/Tool Repair Sidecar。
- 不调用 OpenRouter。
- 不自动 fallback 到 GLM-5.1、Anthropic API Key 模型或其他供应商。
- 不为 MaaS-only 模式伪造图片理解能力。
- 不在 v1 实现多租户虚拟 Key、中心化 ACL、计费数据库或 Prometheus 网关指标。
- 不读取、复制、代理或重放 Anthropic OAuth token。

## 4. 用户与使用模式

### 4.1 用户画像

1. Claude Pro/Max 用户：希望保留订阅体验，同时把大量执行 token 转移到华为 MaaS。
2. 无 Anthropic 登录用户：希望把官方 Claude Code CLI 作为客户端，直接使用华为 MaaS。
3. 自动化用户：希望 CI、批处理和周期任务只消耗 MaaS，不依赖 OAuth 会话。
4. 安全/平台负责人：希望供应商选择显式、凭证不串用、失败不静默跨境或跨供应商。

### 4.2 模式 A：OAuth Orchestrator

入口为原生 `claude`。它通过 CLAUDE.md 策略和 advisory hook 分类任务：

**保留在 OAuth Claude：**

- 架构与跨服务设计；
- 安全、认证、加密、支付、PCI 和生产事故；
- 多子系统复杂调试、竞态和多次失败后的根因分析；
- 高风险 PR review、基础设施和数据库迁移决策；
- 所有图片、截图和视觉输入；
- 超出 GLM 已验证上下文边界且无法拆分的任务；
- MaaS 委托失败两次后的升级任务。

**委托给 `claude-maas`：**

- 普通代码生成和单模块修改；
- 单元测试、文档、repo summary；
- CI 修复、机械重构和格式迁移；
- 低/中风险 review；
- 批量、循环、CI、定时和多任务 fan-out 工作流。

分类结果只是任务级决策，不改变当前 OAuth 会话的 `ANTHROPIC_*` 环境或 transport。

### 4.3 模式 B：MaaS-only

入口为 `claude-maas`。不要求 `claude /login`，不检查或使用 OAuth 状态。所有文本和工具请求直接进入 MaaS `glm-5.2`。

MaaS-only 模式不提供隐藏 premium pool。图片请求、不可恢复的容量错误或模型能力不足必须明确返回给用户，不得自动调用其他供应商。

## 5. 系统架构

### 5.1 组件

| 组件 | 职责 |
| --- | --- |
| `claude` | 官方 OAuth 客户端；不由本项目包装或替换 |
| `claude-maas` | 隔离启动器；只为子进程注入 MaaS base URL、token 和模型 |
| `claude-select` | 可选显式选择器：`native`、`maas`、`status` |
| `delegate` | 接受结构化 brief，运行一次有界 `claude-maas -p`，执行验收并审计 |
| `workflow` | 并发 fan-out 或 whole-workflow 委托；强制 disjoint scope |
| OAuth policy | 任务分类、升级规则和禁止项 |
| route hint hook | 只提供确定性提示，不阻塞、不修改 transport |
| verifier | 原始 Anthropic 协议、真实 Claude Code、隔离和安全回归测试 |
| installer/uninstaller | 幂等安装与精确卸载，不触碰 OAuth 凭证 |

### 5.2 不存在的组件

```text
NO LiteLLM
NO CCR
NO non-loopback HTTP daemon
NO :4000 / :3456 / :3458 (non-loopback)
NO OpenRouter
NO Sidecar
NO model fallback chain
```

**窄例外**：一个项目自有、仅 loopback（127.0.0.1）监听的 Anthropic↔MaaS 协议适配器
（`adapter/server.js`）用于 `claude-maas`。它单模型单上游、无路由决策、无 fallback、
无网关依赖，不是 Sidecar 或 HTTP proxy。详见
`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`。
**不变量的准确含义（PRD UPSTREAM_PROFILE_V1 D4 澄清）**：「单模型单上游」
约束的是**每个适配器实例的基数**——一个实例在任一时刻只服务一个模型、
对接一个上游、无路由、无 fallback——**不是**绑定 `glm-5.2` 这个字面量，
也不是全局只允许一个实例。模型、URL、key 由部署配置（env 文件）决定；
多个 profile 实例（如 `claude-glm`）各自独立且须满足同等安全水位，
由 `scripts/window-check-v12.sh` 的 N1-G 门禁逐实例校验。


## 6. MaaS 直连契约

### 6.1 非敏感配置

默认配置文件：`~/.config/claude-maas/config.json`，权限 `0600`：

```json
{
  "anthropic_base_url": "https://api-ap-southeast-1.modelarts-maas.com/anthropic",
  "model": "glm-5.2",
  "context_tokens": 1000000,
  "max_output_tokens": 32768
}
```

安装器必须允许覆盖 base URL、模型和上下文值，但 v1 只验收 `glm-5.2`。其他模型名属于未验证配置，必须在 `status` 中标记为 unsupported，而不能继承 GLM-5.2 的能力声明。

### 6.2 凭证存储

MaaS Key 保存到 `~/.config/claude-maas/api-key`：

- 文件模式必须为 `0600`；
- 父目录模式必须不宽于 `0700`；
- 文件只包含一行原始 Key；
- wrapper 以数据方式读取，不 `source`、不 `eval`；
- Key 不得出现在 argv、shell profile、Git、日志、审计、错误输出或进程标题中；
- 安装器接受 stdin，环境变量只作为显式备选；
- 更新 Key 采用临时文件 + 原子 rename。

### 6.3 `claude-maas` 子进程环境

只在 wrapper 子进程中导出：

```text
ANTHROPIC_BASE_URL=<config.anthropic_base_url>
ANTHROPIC_AUTH_TOKEN=<api-key file>
ANTHROPIC_MODEL=glm-5.2
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.2
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.2
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.2
CLAUDE_CONFIG_DIR=~/.claude-maas
CLAUDE_CODE_MAX_CONTEXT_TOKENS=<config.context_tokens>
```

同时必须：

- `unset ANTHROPIC_API_KEY`，只保留一个鉴权来源；
- `unset CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX` 等其他 provider 开关；
- 不修改父进程环境；
- 不写 `~/.claude/settings.json`、`~/.claude.json` 或 shell profile；
- 对普通运行传递 `--model glm-5.2`，对 `--version`、`doctor`、`mcp` 等管理命令避免插入无效参数。

## 7. Sidecar 与 fallback 退役决策

### 7.1 Vision Sidecar

删除。OAuth 模式的图片任务留在具备原生 vision 能力的 Claude。MaaS-only 模式当前对图片返回明确不支持，不把图片发送到 Luna、OpenRouter 或其他模型，也不把生成的 caption 注入 GLM。

### 7.2 Premium Advisor Sidecar

删除。OAuth Claude 本身就是 premium pool、规划器和失败升级目标。MaaS-only 是单模型产品，不承诺 premium fallback。

### 7.3 Premium Tool Repair Sidecar

删除。正常工具调用由 MaaS 原生 Anthropic tool contract 和 Claude Code 执行。委托中出现无效工具参数时，允许同一 GLM-5.2 任务进行一次带失败证据的重试；仍失败则返回 `needs_escalation`。

### 7.4 模型 fallback

删除 GLM-5.1、OpenRouter 和任何跨供应商 fallback。429/5xx 只允许在相同 endpoint、相同模型、相同任务的两次总尝试范围内重试。

### 7.5 运行时兼容插件

删除 `anthropic_stream_guard`、`anthropic_reasoning_filter`、`smart_router`、`glm_loop_breaker` 和 `tool_argument_guard` 的运行时注册。其有价值的已知缺陷转化为 verifier 断言。

循环风险由 runner 的 `max-turns`、wall-clock timeout、最多两次模型尝试和用户可中断行为限制；不再修改采样参数或动态注入 premium advice。

## 8. 委托契约

### 8.1 Brief

`delegate` 接受 JSON 或 `--file`：

```json
{
  "task_type": "unit_test_generation",
  "goal": "为 src/parser.py 增加边界测试",
  "scope": ["src/parser.py", "tests/test_parser.py"],
  "constraints": ["不修改公共 API"],
  "acceptance": "pytest tests/test_parser.py -q",
  "context_notes": "只提供完成任务所需的最小上下文",
  "max_attempts": 2,
  "max_turns": 12
}
```

要求：

- `task_type`、`goal` 必填；
- `max_attempts` 强制限制到 `1..2`，调用方不能提高；
- `max_turns` 必须受服务端/runner 上限控制；
- brief 必须自包含，但不得复制整个 OAuth 对话历史；
- scope 为空时默认拒绝写操作型委托；
- acceptance 使用显式工作目录和 timeout；
- shell 命令属于调用者授权的项目范围，审计中只记录命令指纹或名称，不记录敏感输出。

### 8.2 Result

```json
{
  "status": "success",
  "summary": "新增解析器边界测试并通过。",
  "files_changed": ["tests/test_parser.py"],
  "verification": {
    "cmd": "pytest tests/test_parser.py -q",
    "passed": true,
    "evidence_tail": "12 passed"
  },
  "attempts": 1,
  "duration_s": 42.1,
  "tokens": {"in": 2100, "out": 540},
  "model": "glm-5.2"
}
```

允许状态：`success`、`needs_escalation`、`budget_exhausted`、`capacity_error`、`invalid_brief`、`unsupported_capability`。

### 8.3 Workflow

支持两种模式：

- `fanout`：多个 disjoint-scope item 并发调用 `delegate`；
- `suborchestrate`：一个完整但有界的工作流 brief 交给 `claude-maas`。

v1 的并发 scope 必须完全不重叠。任一路径出现在两个 item 中时，整个 fan-out 在启动前拒绝。并发默认 3，可配置但受硬上限控制。失败项成为 OAuth premium remainder；失败比例超过 30% 时，工作流返回 abort/reclassify，而不是继续消耗 MaaS。

MaaS-only 调用方收到相同的结构化失败结果，但不存在自动 OAuth 接手。

## 9. OAuth 编排策略

### 9.1 安装方式

策略以 marker-fenced block 合并到 `~/.claude/CLAUDE.md`，hook 以 additive merge 写入 `~/.claude/settings.json`。不得覆盖用户已有内容或整个 `hooks` 对象。

### 9.2 强制不变量

1. OAuth token 只由官方 `claude` 进程持有和提交。
2. 不在 OAuth 会话设置任何 MaaS `ANTHROPIC_*` 环境变量。
3. 图片永不委托给当前不支持图片的 MaaS endpoint。
4. 高风险任务永不因关键词误判而强制下放；hint 是 advisory。
5. 委托失败两次后，同一 item 不得再次委托。
6. 自动化、CI 和周期任务优先直接调用 `claude-maas`，不消耗 OAuth。

## 10. 错误处理

| 条件 | 行为 |
| --- | --- |
| API Key 缺失/空/权限过宽 | wrapper 启动前失败，指出修复路径，不显示部分 Key |
| MaaS 401/403 | 立即失败；不重试、不切换 OAuth |
| MaaS 429 | 遵循有上限的 `Retry-After`；总尝试仍不超过两次 |
| MaaS 5xx/连接中断 | 同模型最多一次重试；之后结构化失败 |
| SSE 不合规 | verifier/release gate 失败；运行时不猜测修复 |
| 工具调用两次失败 | OAuth 模式升级；MaaS-only 返回失败 |
| 图片输入 | `unsupported_capability:image`；OAuth policy 应在委托前拦截 |
| Claude CLI 不存在 | 安装器/launcher 报告缺失，不自动安装未固定版本 |
| OAuth 不存在 | plain `claude` 保持官方登录行为；`claude-maas` 不受影响 |
| MaaS 配置不存在 | `claude-maas` 在启动前说明 setup 命令 |
| workflow scope 重叠 | 启动任何 worker 前拒绝 |
| acceptance timeout | 本次尝试失败，记录截断后的非敏感证据 |

## 11. 安全与隐私

- 所有 secret-bearing 文件 `0600`；目录 `0700`。
- 所有审计日志默认 `0600`。
- Key 不进入 prompt、brief、Claude memory、Git 或异常堆栈。
- 日志只记录模型名、状态、token、时延、task/workflow ID 和截断后的验证证据。
- 不记录用户 prompt 正文和工具参数正文。
- `status` 仅显示 endpoint host、模型和 Key 指纹前后不可逆摘要，不显示 Key。
- 安装器不得从 shell history 读取或恢复 Key。
- 卸载默认保留审计与 Claude MaaS 会话状态，明确告知位置；`--purge` 必须单独显式请求。
- 由于用户在交互渠道提供过测试 Key，部署验收后应轮换该 Key。

## 12. 可观测性

v1 使用本地 JSONL：`~/.claude-hybrid/route-audit.jsonl`。

每条记录最多包括：

```json
{
  "ts": "2026-08-19T12:00:00-0300",
  "task_id": "a1b2c3d4",
  "workflow": "optional-id",
  "route": "maas",
  "model": "glm-5.2",
  "attempt": 1,
  "outcome": "success",
  "duration_s": 42.1,
  "tokens_in": 2100,
  "tokens_out": 540,
  "fallback": false
}
```

`fallback` 必须始终为 `false`；发现其他值视为产品不变量被破坏。`route-stats` 输出 MaaS attempts、成功率、升级率、token 和超时数，不需要 LiteLLM spend database。

## 13. 安装、迁移与卸载

### 13.1 安装

> **更新（v1.0 交付）：** 统一安装器 `scripts/bootstrap.sh` 已取代上述
> 分步安装接口。一条命令安装完整栈（env 文件 + systemd 单元 + 适配器 +
> 客户端配置 + 启动器）。详见 `docs/PRD_UNIFIED_INSTALL_V1.md` 和
> `README.md` Quick start。以下为原始设计接口，保留作为历史参考。

预期接口：

```bash
printf '%s\n' "$HUAWEI_MAAS_API_KEY" | ./scripts/install.sh \
  --base-url https://api-ap-southeast-1.modelarts-maas.com/anthropic \
  --model glm-5.2

./scripts/configure-policy.sh   # 仅 OAuth 编排用户需要
./scripts/verify.sh
```

安装 `claude-maas`、`Claude-maas` 兼容链接、`claude-select`、`delegate`、`workflow` 和配置。不得安装 npm gateway 包或启动 systemd/pm2/docker 服务。

### 13.2 从 `claude-glm`/LiteLLM 迁移

迁移器先 `--dry-run`，只移除具备所有权证据的旧集成内容：

- 旧 `claude-glm` wrapper 和隔离配置；
- 旧策略 marker block 和本项目明确拥有的 hook；
- LiteLLM base URL、虚拟 Key approval 和模型映射，仅在匹配记录的 endpoint 与指纹时；
- 不删除 OAuth token、Anthropic API Key、用户自定义 hooks、MCP、主题或偏好。

迁移不操作 LiteLLM 服务端；服务端退役是独立运维变更，不属于客户端安装器权限范围。

### 13.3 卸载

默认卸载只删除本项目 marker、hook entry、agent/skills、wrapper 和软链接。保留 `~/.claude-maas`、Key 和审计以便恢复，并提示用户如何显式 purge/revoke。

## 14. 验证与验收标准

### 14.1 协议 canary

直接对 MaaS Anthropic endpoint 运行：

1. 非流式文本返回 `type=message`、`role=assistant`、content list、usage。
2. SSE 每个非空行必须具有合法 SSE 前缀。
3. 每个 `data:` payload 必须是 JSON；不得出现 `[DONE]`。
4. 事件最后一个类型必须是 `message_stop`。
5. `thinking_delta` 只出现在 thinking block；`text_delta` 只出现在 text block。
6. 自动和强制工具均产生结构化 `tool_use`，不出现原始 `<tool_call>` 文本。

### 14.2 Claude Code E2E

使用临时空 `CLAUDE_CONFIG_DIR`：

1. 只设置 `ANTHROPIC_AUTH_TOKEN`，不设置 `ANTHROPIC_API_KEY`，无 OAuth 登录也能返回指定 marker。
2. 输出 `modelUsage` 只包含 `glm-5.2`。
3. 允许一个无副作用 Bash 工具，在临时目录产生 marker，模型能接收 tool result 并完成最终回答。
4. 测试后删除临时目录，Key 不出现在 stdout/stderr。

### 14.3 隔离验收

- 安装前后对 `~/.claude/settings.json`、`~/.claude.json`、OAuth metadata、shell profile 和 `command -v claude` 做快照；未安装 policy 时必须字节不变。
- 安装 policy 后，只允许 marker block 与指定 hook entry 发生 additive diff。
- plain `claude` 子进程不得继承 MaaS base URL/token/model。
- `claude-maas` 子进程不得读取 OAuth credential。
- `claude-maas --version` 与 plain `claude --version` 对应同一个官方 CLI binary 版本。

### 14.4 Sidecar/Router 负验收

以下任一项存在即验收失败：

- 运行中的 `ccr`、LiteLLM、本项目非 loopback HTTP listener；
- 配置或依赖出现 OpenRouter；
- 请求审计出现 `glm-5.1` 或非 `glm-5.2` 模型；
- Vision/Premium/Tool Repair Sidecar 代码路径；
- 安装器执行 `npm install @musistudio/claude-code-router`；
- fallback 字段为 true；
- MaaS-only 失败后出现 Anthropic/OpenRouter 请求。

**窄例外**：项目自有一个仅 loopback 监听的协议适配器（`adapter/server.js`），
用于 `claude-maas` 的 Anthropic↔MaaS 协议转换。它绑定 `127.0.0.1`（启动时校验，
拒绝非 loopback），单模型单上游，无路由决策，无 fallback，无网关依赖。它不是
Sidecar、模型 router 或 HTTP proxy。详见
`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`。

## 15. 发布门槛与成功指标

### 15.1 Definition of Done

- 单元测试、离线 fixture、协议 canary 和 Claude Code E2E 全部通过。
- token-only、无 OAuth 直连实测通过。
- 工具往返实测通过。
- plain Claude/OAuth 隔离实测通过。
- 图片限制有明确文档和错误，不发生 Sidecar 调用。
- 安装/重复安装/卸载/重复卸载通过。
- dry-run 字节级无副作用。
- 仓库扫描确认无 Key、LiteLLM、CCR、OpenRouter 和 fallback 运行依赖。

### 15.2 运营指标

- 委托任务成功率；
- 委托升级率，目标 15%–35%；
- OAuth 模式 MaaS token coverage，目标 40%–70%；
- batch/workflow MaaS token coverage，目标不低于 90%；
- 0 次 OAuth token 暴露或重放；
- 0 次隐藏跨供应商请求；
- 0 次由 Router/Sidecar 引入的会话或缓存重置。

## 16. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| MaaS Anthropic 行为未来回归 | 每次安装/发布运行协议 canary；失败即阻断 |
| GLM 不支持图片 | OAuth policy 留在 Claude；MaaS-only 明确报错 |
| OAuth 编排策略漂移 | advisory hook、route-stats、可审计升级记录 |
| 并发 worker 冲突 | v1 强制 disjoint scope，冲突前置拒绝 |
| 429 风暴 | concurrency governor、bounded Retry-After、总尝试上限 2 |
| 工具循环消耗 | `max-turns`、wall timeout、最多两次 task attempts |
| 本地 Key 泄漏 | 0600 raw secret file、stdin 安装、日志 redaction、轮换 |
| 误把任务 Router 实现成 HTTP Router | Sidecar/Router 负验收与依赖扫描 |

## 17. 后续版本候选

以下仅在新需求和新 PRD 下考虑：

- 华为 MaaS 原生 vision 模型的显式 `claude-maas-vision` profile；
- 多用户本地 key broker；
- 企业中心化预算/审计服务；
- worktree 隔离的并行 workflow；
- MaaS 官方 Anthropic token-count endpoint 与模型 discovery。

这些候选不得以“顺手保留 Sidecar”的方式进入 v1。

## 18. 参考

- Claude Code LLM Gateway Protocol：`https://code.claude.com/docs/en/llm-gateway-protocol`
- 参考项目：`claude-code-oauth-delegate-router`
- 现有能力来源：`/root/litellm-auto-plugin`
- 批准设计：`docs/plans/2026-08-19-direct-maas-delegate-router-design.md`
- 实施计划：`docs/plans/2026-08-19-direct-maas-delegate-router-implementation.md`
