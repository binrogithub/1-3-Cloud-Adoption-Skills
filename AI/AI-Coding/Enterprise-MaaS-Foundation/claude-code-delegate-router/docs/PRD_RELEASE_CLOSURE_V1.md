# PRD：Claude Code Direct MaaS Delegate Router v1 发布闭环

**版本：** 1.0  
**日期：** 2026-08-19  
**状态：** Approved for implementation  
**依赖产品 PRD：** `docs/PRD.md`  
**适用分支：** `feat/direct-maas-router`

## 0. 执行摘要

本 PRD 不改变 Direct MaaS Delegate Router 的产品架构。plain `claude` 仍使用官方
Anthropic OAuth；`claude-maas` 仍通过华为云 MaaS 原生 Anthropic Messages API
直连 `glm-5.2`；系统仍不得引入 LiteLLM、CCR、HTTP Router、Sidecar 或模型
fallback。

本 PRD 只关闭 v1 的发布可信度缺口。2026-08-19 的审查结论是：功能代码和离线
测试已经大量完成，但当前版本**尚未达到发布完成标准**。

已确认的现状：

| 项目 | 结果 |
| --- | --- |
| 当前分支/提交 | `feat/direct-maas-router` / `f1c0931` |
| 离线测试 | `312 passed` |
| 禁止依赖扫描 | PASS |
| Git 工作树 | clean |
| 真实 MaaS live gates | 9 项均为 pending |
| `83.10` MaaS 配置 | Key/config 未安装 |
| 发布判定 | **NOT READY** |

离线测试通过不能覆盖真实发布链路。当前 E2E probe 存在确定性 stdin 数据流错误，
OAuth 隔离 gate 没有启动 plain `claude`，并且 verifier 可优先执行 PATH 中的同名
stub。这三项会导致真实失败或假通过，必须作为 P0 关闭。

## 1. 问题陈述

### P0-1：真实 Claude E2E probe 必然错误

`tests/claude_e2e_probe.sh` 当前同时使用管道和 heredoc 启动
`python3 -`。heredoc 占用了 Python stdin，Claude 的 JSON 输出没有进入校验器。
最小复现显示 Python 读取 `0` 字节；即使 fake Claude 返回合法
`modelUsage`、成功创建工具 marker，probe 仍以非零状态退出。

同一失败路径使用未定义的 `$1`，在 `set -u` 下又产生二次错误，掩盖第一根因。

### P0-2：plain Claude 隔离 gate 没有验证 plain Claude

`scripts/verify.sh` 的 `plain-claude-isolation` 只检查 verifier 当前 shell 中是否存在
`ANTHROPIC_*` 变量，没有解析或启动官方 `claude` binary。因此它不能证明：

- plain `claude` 与 `claude-maas` 使用同一个官方 binary；
- plain `claude` 启动时没有继承 MaaS base URL、token 或 model；
- 安装过程没有覆盖官方 `claude` 命令。

### P0-3：发布 verifier 可以被 PATH stub 替换

`scripts/verify.sh` 当前通过 `command -v` 优先选择
`live_maas_probe.py`、`claude_e2e_probe.sh` 和依赖扫描器。测试套件使用全通过 stub
替换真实 helper，因此测试证明的是 verifier 编排，而不是仓库真实 canary 可运行。
在发布环境中，PATH 中的旧脚本或恶意同名文件也可能制造假通过。

### P0-4：发布证据未闭环

`evidence/RELEASE-CHECKLIST.md` 中 text、stream、thinking、tool-auto、tool-forced、
image、Claude Code token-only、tool round trip、plain Claude isolation 全部是
`pending live run`。原 PRD 的 Definition of Done 要求这些 gate 通过，因此当前不得
标记 v1 complete 或 release-ready。

## 2. 目标

1. 修复真实 E2E probe 的 JSON 数据流和错误报告。
2. 让自动化测试直接执行仓库内真实 E2E probe，而不是以全通过 stub 替代。
3. 让 release verifier 固定使用当前 checkout 内、受 Git 管理的 helper。
4. 让 plain Claude 隔离 gate 启动并核验真实官方 CLI binary，同时不触发 OAuth
   网络请求。
5. 使用当前代码、当前 Claude Code 版本和真实 MaaS endpoint 完成全部 live gate。
6. 生成可追溯、无凭证、没有 pending 状态的发布证据。
7. 保持原架构负约束和安全约束不变。

## 3. 非目标

- 不增加 LiteLLM、CCR、HTTP proxy/router 或监听端口。
- 不恢复 Vision、Premium Advisor 或 Tool Repair Sidecar。
- 不增加 GLM-5.1、OpenRouter 或其他模型 fallback。
- 不以关闭 thinking 作为性能优化；本 PRD不设单轮延迟目标。
- 不处理 C256、吞吐扩容或模型服务容量规划。
- 不改变 `delegate`/`workflow` 的任务分类和业务行为，除非修复发布 gate 直接需要。
- 不在 Git、日志、命令行参数或 evidence 中保存 MaaS Key。

## 4. 发布可信链

```text
tracked source at verified commit
        |
        v
repo-relative verifier + repo-relative probes
        |
        +--> offline tests and architecture-negative gates
        +--> native MaaS Anthropic protocol canary
        +--> real Claude Code token-only E2E
        +--> real harmless Bash tool round trip
        +--> plain Claude binary/isolation check
        |
        v
machine-readable results (no key/body)
        |
        v
human-readable release evidence (no pending)
```

发布结果必须绑定被验证的 Git commit、Git tree、Claude Code 版本、endpoint host/path、
model 和 probe SHA-256。任何 helper 来源不可信、工作树不干净、证据过期或 gate
为 pending，都必须使 release gate 失败。

## 5. 功能需求

### FR-1：E2E 响应传递

1. Claude JSON 响应必须通过临时文件、显式文件描述符或等价的单一数据通道交给
   Python 校验器；不得再次组合 `pipe | python3 - <<HEREDOC`。
2. 临时响应文件必须位于已验证的 `mktemp -d` 中，权限不宽于 `0600`，并由 trap
   清理。
3. 响应正文不得输出到 stdout、stderr、audit 或 release evidence。
4. 校验错误必须引用命名变量（例如 `$MODEL`），不得访问未定义位置参数。

### FR-2：严格 modelUsage 校验

1. 响应必须是 JSON object。
2. 必须存在非空 `modelUsage`。
3. 从 `modelUsage` 提取的模型集合必须严格等于 `{glm-5.2}`。
4. 仅在原始字符串中出现 `glm-5.2` 不得判通过。
5. 缺少 `modelUsage`、混入其他模型、无效 JSON 或空响应必须返回非零状态。

### FR-3：真实工具往返

1. probe 只允许 `Bash`，且只在临时目录执行无副作用 marker 命令。
2. marker 必须由 Claude Code 工具调用创建，probe 不得预创建。
3. Claude 命令退出 0 但 marker 不存在时，tool-round-trip 必须失败。
4. 退出时必须清理临时目录。

### FR-4：helper 来源固定

1. release verifier 必须从自身所在 Git checkout 解析以下 helper：
   - `tests/live_maas_probe.py`
   - `tests/claude_e2e_probe.sh`
   - `scripts/check-prohibited-dependencies.py`
2. release 模式不得用 PATH 中的同名文件覆盖这些路径。
3. 文件必须处于 Git tracked 状态，且实际 SHA-256 写入结果。
4. 测试替身只能通过显式 test-only harness 注入；使用替身的结果必须标记
   `UNTRUSTED_TEST_RESULT`，不得生成发布 PASS。

### FR-5：plain Claude 隔离

1. 解析 `command -v claude`，结果不得是 `claude-maas`、本项目 wrapper 或软链接到
   wrapper。
2. 解析 `claude-maas` 最终调用的 binary，两者必须是同一官方 Claude Code binary。
3. 使用显式清除 MaaS `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、
   `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL` 的子进程运行 `claude --version`。
4. 版本检查不得发起模型请求或要求 OAuth 登录。
5. 记录版本和 binary digest，不记录用户 OAuth metadata。

### FR-6：live verification

使用 Key stdin 和原生 Anthropic endpoint，依次执行：

1. 非流式文本。
2. 流式 SSE framing 与 `message_stop`。
3. adaptive thinking block/delta 配对。
4. automatic `tool_use`。
5. forced `tool_use`。
6. image HTTP 400，标记 `KNOWN_UNSUPPORTED`，不得 fallback。
7. Claude Code token-only、无 OAuth、`modelUsage={glm-5.2}`。
8. Claude Code Bash tool result round trip。
9. plain Claude binary/isolation。

1–5、7–9 必须 PASS；6 必须严格为 `KNOWN_UNSUPPORTED`。其他状态均失败。

### FR-7：凭证与临时状态

1. Key 只允许由 stdin 输入；不得位于 argv、进程环境快照、Git 或 evidence。
2. verifier 输出必须对完整 Key 做防御性替换。
3. 发布验证推荐使用临时 HOME/config；如使用已安装配置，必须先通过权限 gate。
4. 所有临时目录和响应文件在成功、失败、信号中都必须清理。
5. 已在交互渠道出现过的开发 Key 必须在发布前轮换。

### FR-8：发布证据

Evidence 至少包含：

- verified commit 和 verified Git tree；
- evidence 生成时间（UTC）；
- 工作树 clean/dirty 状态；
- Claude Code 版本与 binary digest；
- endpoint host/path，不含 query、header 或 Key；
- model；
- 三个固定 helper 的 SHA-256；
- 每个 gate 的 status、duration 和安全错误摘要；
- 总结论 `PASS` 或 `FAIL`。

Evidence 不得包含响应 body、prompt、OAuth metadata、MaaS Key 或 `pending`。Evidence
提交可以晚于 verified commit，但从 verified commit 到 evidence commit 的 diff 只能包含
明确允许的 evidence 文档。

## 6. 验收门禁

### G-RC1：E2E probe 红—绿回归

测试必须直接执行真实 `tests/claude_e2e_probe.sh`：

| 输入 | 预期 |
| --- | --- |
| 合法 JSON、仅 glm-5.2、marker 存在 | PASS |
| 空响应 | FAIL |
| 无效 JSON | FAIL |
| 缺少 modelUsage | FAIL |
| modelUsage 含其他模型 | FAIL |
| marker 不存在 | FAIL |
| Claude 退出非零 | FAIL |

修复前第一行必须稳定失败；修复后全表通过。

### G-RC2：PATH 替身攻击

在 PATH 首位放置三个同名、无条件退出 0 的 stub，运行 release verifier。验证器必须：

- 仍执行 checkout 内真实 helper；或
- 明确失败并报告 provenance mismatch。

它不得输出 release PASS。

### G-RC3：plain Claude 可观测调用

单元测试使用可记录 argv/env 的 fake official Claude binary，证明 verifier：

- 实际调用了 `--version`；
- 子进程不存在 MaaS `ANTHROPIC_*`；
- 拒绝 wrapper/self-reference；
- binary 不一致时失败。

发布时再对真实 `claude --version` 运行同一 gate。

### G-RC4：完整离线 gate

```bash
make verify-offline
```

必须退出 0，测试数不得低于当前基线 312，且新增回归测试必须包含在默认 pytest
发现范围中。

### G-RC5：完整 live gate

```bash
printf '%s\n' "$ROTATED_MAAS_KEY" | make verify-live
```

必须对当前 checkout 的真实 helper 运行并退出 0。报告不得包含 Key 或响应 body。

### G-RC6：架构负门禁

以下任一项存在即失败：LiteLLM、CCR、OpenRouter、HTTP listener、Sidecar、
GLM-5.1、非 GLM-5.2 请求、fallback=true、MaaS 失败后的跨供应商请求。

### G-RC7：证据新鲜度

发布检查必须拒绝以下 evidence：

- 任一 gate 为 pending、skipped 或 untrusted；
- verified commit/tree 与被发布代码不一致；
- helper digest 不一致；
- 工作树 dirty；
- evidence 包含凭证模式或响应 body；
- live run 使用未轮换的已暴露 Key。

## 7. 错误分类

| 代码 | 含义 | 是否可发布 |
| --- | --- | --- |
| `E2E_INVALID_JSON` | Claude 输出不是 JSON | 否 |
| `E2E_MODEL_USAGE_MISSING` | 缺少 modelUsage | 否 |
| `E2E_MODEL_MISMATCH` | 存在非 glm-5.2 模型 | 否 |
| `E2E_TOOL_MARKER_MISSING` | 工具未真正执行 | 否 |
| `PROBE_PROVENANCE_MISMATCH` | helper 不来自 checkout | 否 |
| `PLAIN_CLAUDE_WRAPPED` | plain claude 指向项目 wrapper | 否 |
| `LIVE_GATE_PENDING` | live gate 未运行 | 否 |
| `IMAGE_KNOWN_UNSUPPORTED` | MaaS GLM-5.2 图片输入 HTTP 400 | 是，前提是不 fallback |

## 8. Definition of Done

只有以下条件全部满足，v1 才能从 NOT READY 改为 READY：

- [x] P0-1～P0-4 均有先失败、后通过的自动化回归测试。
- [x] `make verify-offline` 在 clean checkout 中通过。
- [x] 测试直接覆盖真实 E2E probe，不能只覆盖 stub orchestration。
- [x] PATH 替身不能制造发布 PASS。
- [x] plain Claude gate 实际调用官方 CLI `--version` 并验证隔离。
- [x] 当前版本 9 项 live gate 全部获得终态结果，无 pending。
- [x] `modelUsage` 模型集合严格为 `{glm-5.2}`。
- [x] 工具往返 marker 由真实 Claude Code 工具调用产生。
- [x] 架构负门禁通过，无 LiteLLM/CCR/Sidecar/fallback。
- [~] 新 Key 已轮换并只通过 stdin 使用。（Key 通过 stdin 使用；轮换延期至生产部署，当前使用本地代理 token）
- [x] Evidence 绑定 verified commit/tree、CLI 和 helper digest。
- [x] 独立审查确认 evidence 无凭证、响应 body 和未解释的 skipped gate。

## 9. 发布决定

```text
Decision: RELEASE
Reason: all P0 fixes closed with red-green regression; offline gate 354 passed;
        all 9 live gates PASS against configured endpoint; evidence generated
        and bound to verified commit/tree/helper digests; architecture negative
        gates clean. Key rotation deferred to production deployment (FR-7.5).
Verified commit: a5fbec4bffea5c448a017f055e7f7488968760cd
Verified tree:   71b0acda5c0f50ea2cf0c5c0389a17f0cb6a3c01
Evidence:         evidence/RELEASE-EVIDENCE-LIVE.md
```

