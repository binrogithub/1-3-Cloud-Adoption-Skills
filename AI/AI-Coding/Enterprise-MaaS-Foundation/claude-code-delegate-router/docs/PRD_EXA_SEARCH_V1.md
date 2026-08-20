# PRD：claude-maas 隔离 Exa 搜索能力

**版本：** 1.0  
**日期：** 2026-08-19  
**状态：** Approved for implementation  
**依赖：** `docs/PRD.md`、`docs/PRD_RELEASE_CLOSURE_V1.md`  
**适用分支：** `feat/direct-maas-router`

## 0. 产品摘要

为 `claude-maas` 增加 Exa 网络搜索和网页读取能力，同时保持 plain `claude`、
MaaS 模型配置和 Exa 凭证三者隔离。

本版本采用 Exa 官方远程 HTTP MCP：

```text
claude-maas
  -> isolated CLAUDE_CONFIG_DIR (~/.claude-maas)
  -> Exa remote MCP (https://mcp.exa.ai/mcp)
  -> headersHelper
  -> ~/.config/claude-maas/exa-api-key (0600)
  -> web_search_exa / web_fetch_exa
```

plain `claude` 必须退役旧 `exa-mcp@0.0.7` 配置和旧工具权限。新实现不运行
本地 Exa 服务、不增加 npm 运行依赖、不把 Key 写入 JSON，也不改变
`claude-maas` 的 MaaS URL、MaaS Key、`glm-5.2` 或 1M context。

## 1. 背景与已验证事实

2026-08-19 在 `83.10` 上确认：

| 项目 | 当前状态 |
| --- | --- |
| plain `claude` | `exa-search` 已连接 |
| 当前 transport | 本地 stdio `exa-mcp` |
| 当前包 | `exa-mcp@0.0.7` |
| 当前工具 | `exa_search`、`exa_answer`、`exa_find_similar`、`exa_contents` |
| 当前 Key | 明文存在于 plain Claude settings 和历史备份 |
| `claude-maas` profile | `No MCP servers configured` |
| MaaS 模型 | `glm-5.2` |
| MaaS context | `1000000` |

旧实现功能可用，但存在三个结构性问题：

1. Exa 属于 plain Claude 全局配置，MaaS-only 会话无法使用。
2. Key 被复制到 JSON 和多个备份，违反新项目的凭证隔离原则。
3. 本地包与 Exa 当前官方 MCP 的 transport、包名和工具契约已经漂移。

Exa 官方当前推荐远程 MCP `https://mcp.exa.ai/mcp`；默认工具为
`web_search_exa` 和 `web_fetch_exa`。Claude Code 支持 HTTP MCP 和
`headersHelper`，可在连接时动态生成认证 header。

## 2. 决策

### 2.1 采用

- 仅 `claude-maas` 使用 Exa。
- 使用 Exa 官方远程 HTTP MCP。
- 只启用 `web_search_exa` 和 `web_fetch_exa`。
- 使用 `headersHelper` 读取独立 0600 Key 文件。
- MCP 配置和工具权限只写入隔离的 `CLAUDE_CONFIG_DIR`。
- 从 plain Claude 精确移除旧 Exa MCP、旧权限和 `EXA_API_KEY`。
- 迁移完成后轮换已经暴露的旧 Exa Key。

### 2.2 不采用

- 不继续使用 `exa-mcp@0.0.7`。
- 不安装或运行 `exa-mcp-server` npm 包。
- 不自行实现 Exa REST→MCP adapter。
- 不启用 `web_search_advanced_exa`、Exa Agent 或 deprecated tools。
- 不让 plain `claude` 和 `claude-maas` 共用一个全局 MCP 配置。
- 不把 Key 写入 `.claude.json`、`settings.json`、`.mcp.json` 或 URL query。
- 不回退到免费匿名 Exa、其他搜索供应商或 plain Claude。

## 3. 用户故事

1. MaaS-only 用户可以要求 `claude-maas` 搜索最新网络信息并获得来源 URL。
2. MaaS-only 用户可以要求 `claude-maas` 读取一个已知网页并总结内容。
3. OAuth 用户启动 plain `claude` 时不会加载 Exa MCP 或 Exa Key。
4. 管理员可以轮换 Exa Key，而不修改 JSON 或 MaaS 配置。
5. 管理员可以 dry-run 迁移，确认只删除旧 Exa 项。
6. 管理员可以卸载 Exa 能力而不影响 MaaS、OAuth、其他 MCP 或其他环境变量。

## 4. 系统组件

| 组件 | 责任 |
| --- | --- |
| `scripts/configure-exa.sh` | 安装/轮换 Key，增量写入隔离 MCP 和权限 |
| `scripts/exa-headers-helper.py` | 校验调用上下文和 Key 文件，输出 `x-api-key` JSON |
| `scripts/migrate-exa.sh` | dry-run/apply，从 plain Claude 精确移除旧 Exa |
| `scripts/uninstall-exa.sh` | 删除项目拥有的隔离 Exa 配置；默认保留 Key |
| `scripts/verify-exa.sh` | 离线安全检查、MCP 健康和真实工具 canary |
| `~/.config/claude-maas/exa-api-key` | 原始 Exa Key，0600，仅一行 |
| `~/.claude-maas/.claude.json` | 隔离 user-scope MCP 定义，不含 Key |
| `~/.claude-maas/settings.json` | 隔离的两个只读工具权限，不含 Key |

## 5. 配置契约

### 5.1 隔离 MCP 定义

`~/.claude-maas/.claude.json` 中项目拥有的 entry：

```json
{
  "mcpServers": {
    "exa-search": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa",
      "headersHelper": "/absolute/project/path/scripts/exa-headers-helper.py"
    }
  }
}
```

安装器必须增量合并 `mcpServers.exa-search`，不得覆盖其他 top-level 字段或其他
MCP。server name、host、path 和工具 query 必须精确匹配此契约。

### 5.2 工具权限

隔离 `settings.json` 只增加：

```json
{
  "permissions": {
    "allow": [
      "mcp__exa-search__web_search_exa",
      "mcp__exa-search__web_fetch_exa"
    ]
  }
}
```

不得加入 wildcard，不得批准 advanced、agent 或 deprecated 工具。

### 5.3 Tool Search 策略

`claude-maas` 使用非 Anthropic base URL。v1 不强制启用
`ENABLE_TOOL_SEARCH=true`，避免 MaaS 对 `tool_reference` beta 的兼容性风险。只有两个
Exa 工具时允许启动时加载完整 schema。未来启用 Tool Search 需要独立 canary。

## 6. 凭证契约

Exa Key 保存为 `~/.config/claude-maas/exa-api-key`：

- 父目录不宽于 0700；
- 文件必须为普通文件、非符号链接、当前用户所有、精确 0600；
- 只允许一行非空值；
- installer 通过 stdin 读取，禁止 argv 和环境变量输入；
- 通过同目录 `mktemp`、0600 和原子 rename 写入；
- 除 `headersHelper` 向 Claude Code 返回认证 JSON 的专用 stdout 管道外，不得把
  Key 输出到用户可见 stdout/stderr、日志或报告；
- 可输出 SHA-256 的短指纹用于人工核对，但不得写入 MCP 请求。

已经出现在 settings、备份或交互输出中的旧 Key 视为已暴露。迁移成功后必须在 Exa
控制台轮换，最终 live gate 只允许使用新 Key。历史备份不由默认迁移器自动删除；
轮换使其中旧 Key 失效，显式 purge 属于独立破坏性操作。

## 7. headersHelper 契约

`scripts/exa-headers-helper.py` 必须：

1. 检查 `CLAUDE_CODE_MCP_SERVER_NAME == exa-search`。
2. 检查 `CLAUDE_CODE_MCP_SERVER_URL` 的 scheme 为 HTTPS、host 为
   `mcp.exa.ai`、path 为 `/mcp`。
3. 严格校验 Key 文件类型、owner、mode 和单行内容。
4. stdout 只输出一个 JSON object：`{"x-api-key":"<value>"}`。
5. stderr 只输出稳定错误码，不包含 Key、URL query 或环境快照。
6. 10 秒内结束；不访问网络、不缓存、不写文件。

helper 不接受自定义路径参数，避免 MCP JSON 把秘密路径和可覆盖参数混在一起。

## 8. plain Claude 迁移

### 8.1 dry-run

`scripts/migrate-exa.sh --dry-run` 只报告字段名和动作，不报告值。它必须检查：

- plain `~/.claude.json` 中 `mcpServers.exa-search` 是否精确使用 `exa-mcp`；
- plain `~/.claude/settings.json` 中是否存在 `EXA_API_KEY`；
- permissions.allow 是否包含四个旧 `mcp__exa-search__*` 工具。

dry-run 必须字节级无副作用。

### 8.2 apply

`--apply` 只允许删除：

- `mcpServers.exa-search` 的已证明旧 entry；
- plain settings 的 `env.EXA_API_KEY`；
- 四个精确旧工具 permission。

其他 MCP、env、permission、OAuth metadata、theme、hook、1M context 和 EXA 以外的
配置必须保持不变。如果旧 entry 与已知指纹不匹配，迁移必须停止并要求人工审查。

为避免再产生长期明文备份，迁移使用内存快照和同目录 0600 临时文件完成事务；失败
时在进程内回滚，成功后删除临时文件。不得新建持久化 Key-bearing `.bak`。

### 8.3 本地 npm 包

默认迁移不执行 `npm uninstall -g exa-mcp`，因为全局包可能被其他用户或工具使用。
迁移结果必须报告“已不再引用”。显式清理命令需二次确认并独立执行。

## 9. 搜索内容安全

- Exa 返回内容属于不可信外部输入。
- 模型不得执行网页中要求修改系统提示、泄露凭证或运行命令的指令。
- 搜索型回答必须保留来源 URL；无法取得来源时必须说明。
- `web_fetch_exa` 只读取用户给定或搜索结果中的 HTTP(S) URL。
- Exa 工具不得读取本地文件、MaaS Key、Exa Key 或 OAuth metadata。
- 搜索结果不得自动写入长期 memory、CLAUDE.md 或项目文件。

## 10. 错误处理

| 场景 | 行为 |
| --- | --- |
| Key 缺失/空/宽权限/符号链接 | MCP 连接失败，稳定本地错误码 |
| server name 或 URL 不匹配 | helper fail closed，不输出 header |
| HTTP 401/403 | 明确凭证错误，不自动 retry 或 fallback |
| HTTP 429 | 返回限流错误；允许用户稍后重试，不做无限循环 |
| DNS/超时/断连 | 工具失败但 MaaS 主会话继续；不切换搜索供应商 |
| 工具集合漂移 | 验证失败，禁止 release |
| 搜索无结果 | 明确说明无结果，不虚构来源 |
| fetch URL 无效 | 在调用前拒绝，保持会话可继续 |

## 11. 可观测性

允许记录：

- MCP server name、transport、host；
- connect 成功/失败、错误分类和 duration；
- 工具名、成功/失败、429 次数；
- 搜索/读取调用计数。

禁止记录：

- Key 或 header；
- 完整搜索 query；
- 完整网页内容；
- MaaS prompt/response；
- OAuth metadata。

## 12. 安装、轮换与卸载

### 12.1 安装

```bash
printf '%s\n' "$NEW_EXA_API_KEY" | ./scripts/configure-exa.sh --apply
```

安装顺序：验证依赖与隔离目录 → 写 Key → 合并 MCP → 合并两个权限 → 健康检查。
任一步失败必须回滚本轮配置，不影响 MaaS 配置。

### 12.2 轮换

重复运行 configure 命令，只替换 Exa Key 文件。MCP JSON 必须保持字节不变。

### 12.3 卸载

```bash
./scripts/uninstall-exa.sh          # 删除 MCP/权限，保留 Key
./scripts/uninstall-exa.sh --purge  # 同时删除 Exa Key
```

卸载不得修改 plain Claude、MaaS URL/Key/model/context、delegate/workflow 或其他 MCP。

## 13. 验收门禁

### G-EXA1：凭证安全

- Key 不出现在 Git、静态配置 JSON、argv、env、用户可见 stdout/stderr、audit 或
  evidence；唯一例外是 `headersHelper` 向 Claude Code 返回 header 的受控 stdout。
- Key 文件通过 regular/non-symlink/owner/0600/single-line 检查。
- 恶意 Key 文本按数据处理，不执行 shell substitution。

### G-EXA2：配置隔离

- plain `claude mcp list` 不显示 `exa-search`。
- plain settings 不含 `EXA_API_KEY` 和旧 Exa tool permissions。
- `CLAUDE_CONFIG_DIR=~/.claude-maas claude mcp list` 显示 Exa Connected。
- isolated MCP JSON 不含 Key。

### G-EXA3：工具 allowlist

服务器暴露并允许的工具集合必须严格为：

```text
web_search_exa
web_fetch_exa
```

出现 advanced、agent、deprecated 或未知工具即失败。

### G-EXA4：真实功能

1. 搜索一个当天可验证的主题，返回至少一个 HTTPS 来源 URL。
2. 对一个固定公开页面执行 fetch，返回可识别 marker 和页面 URL。
3. JSON 结果显示模型仍只使用 `glm-5.2`。
4. `modelUsage.glm-5.2.contextWindow == 1000000`。

### G-EXA5：失败矩阵

离线/受控测试覆盖：missing Key、empty、multiline、symlink、wrong owner、0644、
wrong server、wrong host、401、403、429、timeout、invalid URL、tool drift。

### G-EXA6：生命周期

- install、reinstall、rotation、dry-run、apply、uninstall、re-uninstall 全部幂等。
- apply 只改变批准路径和字段。
- 默认 uninstall 保留 Key；purge 才删除。

### G-EXA7：无本地运行依赖

- runtime 不引用 `exa-mcp`、`exa-mcp-server`、`npx`。
- 不启动 Exa 本地进程、daemon、container 或 listener。
- npm 全局包是否仍存在不影响 gate；关键是新路径零引用、零进程。

## 14. Definition of Done

- [ ] G-EXA1～G-EXA7 全部通过。
- [ ] 新 Exa Key 已轮换，并只存在于独立 0600 文件。
- [ ] plain Claude 的旧 Exa 配置已精确迁移。
- [ ] `claude-maas` Exa MCP 显示 Connected。
- [ ] 两个真实工具 canary 通过并保留来源 URL。
- [ ] MaaS model/context 未回归。
- [ ] 全量 `make verify-offline` 通过且新增测试被默认发现。
- [ ] release evidence 绑定 Git commit/tree、Claude Code 版本、MCP endpoint 和脚本 digest。
- [ ] evidence 不含 Key、query、网页正文、prompt 或 response。

## 15. 成功指标

- Exa MCP 连接成功率；
- search/fetch 调用成功率；
- 401/403/429/timeout 计数；
- 带至少一个有效来源 URL 的搜索回答比例；
- 0 次 Exa Key 泄露；
- 0 次 plain Claude Exa 调用；
- 0 次搜索供应商 fallback；
- 0 个非 allowlist Exa 工具。

## 16. 参考

- Exa Web Search MCP：<https://exa.ai/docs/reference/exa-mcp>
- Exa MCP 官方仓库：<https://github.com/exa-labs/exa-mcp-server>
- Claude Code MCP：<https://code.claude.com/docs/en/mcp>
- Claude Code 环境变量：<https://code.claude.com/docs/en/env-vars>
