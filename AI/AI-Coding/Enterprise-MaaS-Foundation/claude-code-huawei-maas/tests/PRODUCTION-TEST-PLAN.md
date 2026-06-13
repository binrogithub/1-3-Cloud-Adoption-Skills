# claude-glm 生产级 Harness 测试计划

目标：验证 `claude-glm`（Claude Code + CCR + LiteLLM + Huawei MaaS glm-5.1）达到与原生
`claude`（Anthropic 后端）一致的生产可用性。

链路：`claude CLI -> ccr(3456) -> LiteLLM Anthropic Adapter(4010)/LiteLLM(4000) -> MaaS glm-5.1`

判定原则：每个用例有明确命令与可机判的预期结果。`[C]` 表示进入 Top 30 并发批次，
`[S]` 表示必须串行执行（破坏性或互斥），`[M]` 表示需人工/交互验证。

---

## A. 基础协议与可用性

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| A1 [C] | 最小对话 | `claude-glm --print 'Reply with OK only'` | 退出码 0，输出含 `OK` |
| A2 [C] | JSON 输出格式 | `--print --output-format json` | 合法 JSON，`subtype=success`，`is_error=false` |
| A3 [C] | stream-json 流式 | `--print --output-format stream-json --verbose` | 每行合法 JSON，末尾出现 `type:result` 事件 |
| A4 [C] | 退出码语义 | A1 后检查 `$?` | 成功为 0；失败请求非 0 |
| A5 [C] | stderr 清洁度 | A1 同时捕获 stderr | stderr 无 ERROR/Exception 噪声 |
| A6 [C] | 版本与管理子命令 | `claude-glm --version` | 输出 Claude Code 版本，不被 wrapper 注入 `--model` 干扰 |
| A7 [C] | stop_reason 语义 | JSON 输出检查 | `stop_reason=end_turn`，`terminal_reason=completed` |

## B. 模型路由与标识

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| B1 [C] | modelUsage 上报 | JSON 输出 `modelUsage` | 存在且非空；记录实际模型名（当前为别名 `claude-opus-4-6`） |
| B2 [C] | 上下文窗口声明 | `modelUsage.*.contextWindow` | 与 MaaS 真实限制一致（120000）。若报 200000 而后端实际 196608 token 上限，判 FAIL（会导致 auto-compact 失效与上下文溢出） |
| B3 [C] | 路由隔离：plain claude 不受影响 | `claude --version`、检查 `claude` 无 wrapper 环境 | 原 `claude` 命令不经 3456 路由 |
| B4 [S] | webSearch 路由 | 搜索意图 prompt 走 `LiteLLM Provider,glm-5.1` | CCR 日志显示路由到 /v1/responses；无本地 WebFetch 工具调用 |
| B5 [S] | image 路由 | 带图片输入 | 路由到 `litellm-chat,glm-5.1`，LiteLLM 重写为 vision 模型 |
| B6 [C] | 显式 --model 透传 | `claude-glm --model claude-opus-4-6 --print ...` | wrapper 不重复注入，正常应答 |

## C. 工具调用（agentic loop 可靠性 — 生产化的核心）

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| C1 [C] | Bash 工具单次调用 | `--allowedTools Bash` 让模型执行 `echo <marker>` | 输出含 marker，无工具 JSON 解析错误 |
| C2 [C] | Read 工具 | 预置含密语文件，要求读取并复述 | 输出含密语 |
| C3 [C] | Write 工具 | 要求创建指定内容文件（acceptEdits） | 文件落盘且内容正确 |
| C4 [C] | Edit 工具 | 预置文件，要求替换指定词 | 文件被正确修改，无多余改动 |
| C5 [C] | Glob/Grep 工具 | 在目录树中找含 marker 的文件 | 正确报告文件名 |
| C6 [C] | 多工具链（write→read→报告） | 单 prompt 触发 ≥2 轮工具循环 | `num_turns ≥ 3`，最终答案正确 |
| C7 [C] | 工具参数含特殊字符 | marker 含引号/空格/中文 | 工具调用参数不被截断/转义错误 |
| C8 [S] | 并行工具调用 | 要求同时读两个文件 | 模型一次发出多个 tool_use 块且 harness 正确执行（GLM 经转换层常见薄弱点） |
| C9 [M] | 工具拒绝处理 | 交互模式拒绝一次权限 | 模型优雅降级，不死循环重试 |
| C10 [S] | TodoWrite/Task 等内置复杂 schema | 触发任务列表类工具 | schema 校验通过，无 input JSON 畸形 |

## D. 多轮与会话管理

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| D1 [C] | session_id 合法且 JSONL 落盘 | JSON 输出 + 检查 projects 目录 | UUID 格式；对应 session 文件存在 |
| D2 [C] | --resume 续聊记忆 | 第 1 次注入 token，`--resume <sid>` 询问 | 第 2 次回答含 token |
| D3 [S] | /compact 行为 | 长会话执行 compact | 压缩成功且会话可继续（MaaS 历史薄弱点） |
| D4 [S] | 溢出恢复 | 构造超限会话，`claude-glm-recover <sid>` | 生成恢复包 `/tmp/claude-glm-recovery-*.md` 且新会话可用 |
| D5 [M] | 交互模式 header 模型显示 | 启动交互式 `claude-glm` | header 显示路由模型而非误导性名称 |

## E. 上下文与 Token 核算

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| E1 [C] | usage tokens 非零 | JSON `usage.input_tokens/output_tokens` | 必须 >0。为 0 意味着成本统计、context-left 指示、auto-compact 阈值全部失效（生产阻断项） |
| E2 [C] | 长输入（~30k 字符） | 大 prompt 单次请求 | 成功应答，无 `prompt length` 错误 |
| E3 [C] | 大输出 | 要求输出 100 行编号 | ≥80 行（验证 8192 输出帽合理性） |
| E4 [S] | 接近 120k 上限 | 渐进填充上下文 | 在声明窗口内不报错；超限时错误信息可读 |
| E5 [C] | 延迟 SLO | 简单 prompt 的 `duration_ms` | < 60s（并发下 < 120s） |

## F. 错误处理与韧性（全部串行）

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| F1 [S] | 路由器宕机自愈 | `ccr stop` 后运行 claude-glm | wrapper 检测不健康→重启→请求成功 |
| F2 [S] | 陈旧 pid 文件 | 杀进程留 pid 文件 | 健康检查识别假活，自动恢复 |
| F3 [S] | 后端 4010/4000 不可用 | 停 LiteLLM 后请求 | 可读错误（非挂死），退出码非 0 |
| F4 [S] | 错误 API key | 篡改 env 后请求 | 明确 auth 错误提示，指向修复方法 |
| F5 [S] | 请求超时 | 模拟慢后端 | 按 API_TIMEOUT_MS 超时并报错，不僵死 |
| F6 [S] | 重启竞态 | 快速连续 stop/start | 30s 内恢复健康，无端口占用死锁 |

## G. 并发与稳定性

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| G1 [C] | 30 路并发会话 | 本批次全部用例同时启动 | 全部完成，无串话（每例 marker 唯一） |
| G2 [C] | 会话隔离 | 两个并发会话注入不同密语互查 | 各自只知道自己的密语 |
| G3 [C] | 负载中路由器健康 | 并发期间 `curl 127.0.0.1:3456/` | 持续 200 |
| G4 [S] | 持续负载 30 分钟 | 循环请求 | 无内存泄漏（RSS 稳定）、无 fd 泄漏 |
| G5 [S] | 限流行为 | 超出 MaaS QPS | 429 可读、可重试，不导致会话损坏 |

## H. 国际化与边界输入

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| H1 [C] | 中文问答 | `用中文回答：1+1等于几？只回答数字` | 输出 `2` |
| H2 [C] | Emoji/Unicode | 含 emoji 的输入输出 | 不乱码、不截断 |
| H3 [C] | Shell 特殊字符 prompt | 引号/反斜杠/`$()` | 原样理解，无注入或解析错误 |
| H4 [C] | 空白 prompt | 仅空格的 prompt | 优雅处理（报错或正常应答），不挂起 |
| H5 [C] | 严格 JSON 输出 | 要求输出精确 JSON | result 可被 `json.loads` 解析（工具调用 JSON 可靠性的代理指标） |

## I. 安全与权限

| ID | 用例 | 命令/方法 | 预期结果 |
|----|------|-----------|----------|
| I1 [C] | 默认权限拦截 | 不带 allowedTools 要求写文件 | 文件不落盘，`permission_denials` 体现拦截 |
| I2 [S] | 密钥不泄漏 | grep 所有日志/输出 | MaaS key 不出现在任何日志、JSON 输出、CCR 日志 |
| I3 [S] | env 文件权限 | `stat ~/.config/claude-glm/env` | 0600 |

---

## Top 30 并发批次（按生产风险排序）

入选标准：可非交互执行、相互无破坏、各自独立工作目录。每例唯一 marker 防串话。

| # | 用例ID | 验证点 |
|---|--------|--------|
| 1 | A1 | 最小对话可用 |
| 2 | A2 | JSON 输出协议 |
| 3 | A3 | stream-json 流式协议 |
| 4 | A7 | stop_reason/terminal_reason 语义 |
| 5 | E1 | usage tokens 非零（成本/auto-compact 基石） |
| 6 | B1 | modelUsage 上报 |
| 7 | B2 | contextWindow 与真实限制一致 |
| 8 | C1 | Bash 工具调用 |
| 9 | C2 | Read 工具 |
| 10 | C3 | Write 工具 |
| 11 | C4 | Edit 工具 |
| 12 | C5 | Glob/Grep 工具 |
| 13 | C6 | 多工具链 agentic loop |
| 14 | C7 | 工具参数特殊字符 |
| 15 | D1 | session JSONL 落盘 |
| 16 | D2 | --resume 记忆 |
| 17 | E2 | 30k 长输入 |
| 18 | E3 | 大输出 |
| 19 | E5 | 延迟 SLO |
| 20 | H1 | 中文问答 |
| 21 | H2 | Emoji/Unicode |
| 22 | H3 | Shell 特殊字符 |
| 23 | H4 | 空白 prompt |
| 24 | H5 | 严格 JSON 输出 |
| 25 | I1 | 默认权限拦截 |
| 26 | G2 | 并发会话隔离（成对） |
| 27 | G3 | 负载中路由器健康 |
| 28 | A6 | --version 管理命令 |
| 29 | B6 | 显式 --model 透传 |
| 30 | A5 | stderr 清洁度 |

执行器：`tests/concurrent-top30.sh`。串行批次（F 系列、D3/D4、G4/G5、I2/I3 等）在并发批次
全绿后单独执行，避免相互污染。
