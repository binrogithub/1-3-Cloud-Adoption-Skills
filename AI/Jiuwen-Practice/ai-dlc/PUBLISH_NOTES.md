# PUBLISH NOTES — AI-DLC 公开发布整理

> 本文件记录从 `/root/DevTeam/ai-dlc`（分支 `task/design-required`）整理到本目录的内容审查结论。
> 生成日期：2026-09-02。这不是正式 README，是发布准备记录。

---

## 1. 从原仓库带过来的顶层目录/文件

| 目录/文件 | 带过来？ | 理由 |
|---|---|---|
| `.gitignore` | ✅ | 干净，排除 `.env`、`.claude/`、`.ai-dlc/tasks/` 等，适合公开 |
| `README.md` | ✅ 原样保留 | 内容是项目门面，但**不适合直接作为公开项目首页**（见§3 人工决定事项） |
| `CHANGELOG.md` | ✅ 已脱敏 | 机器路径和 IP 已替换为占位符；内部人名 "Robin" 保留（见§3） |
| `install.sh` | ✅ 已脱敏 | `/root/DevTeam` → `<workspace-root>`，`/root/.local/bin/python3.12` → `python3.12`，`/root/.jiuwenswarm` → `${HOME}/.jiuwenswarm`。部分 `/root/` 默认值保留（见§3） |
| `bin/` | ✅ 已脱敏 | `plan.py`、`report.py` 的 shebang 改为 `#!/usr/bin/env python3`；`report.py` 注释中的 `/root/DevTeam` 已替换。`plan.py` 中的 `/root/.local/bin/jiuwenswarm` 等默认值保留（见§3） |
| `config/` | ✅ 原样保留 | `collapsed.config.yaml`（5 个配置键）和 `maas.template.env`（占位模板 `MAAS_API_KEY=__REPLACE_WITH_YOUR_KEY__`），无敏感内容 |
| `docs/` | ✅ 已脱敏 | 12 个 PRD/设计文档。已替换：IP `124.81.97.217` → `<host-ip>`，`/root/DevTeam` → `<workspace-root>`，`/root/.jiuwenswarm` → `<gateway-home>`，`/root/.claude-glm` → `<cc-glm-config>` 等。`/proc/<MainPID>/root/...` 保留（通用 Linux procfs 路径） |
| `openspec/specs/` | ✅ 原样保留 | 21 个 spec 定义文件，通用流程规范，无敏感内容 |
| `openspec/config.yaml` | ✅ 原样保留 | 通用 spec-driven 配置模板 |
| `openspec/changes/archive/` | ✅ 已脱敏 | 归档变更 `2026-09-01-uidesigner-opendesign`，"Robin" → "the product owner" |
| `openspec/changes/2026-09-01-vivo-maas-launch/` | ❌ 排除 | **客户商业敏感**：描述 Vivo（巴西最大移动运营商）基于华为云 MaaS 的 AI 模型服务发布网站，包含产品定价、模型目录、合规信息。这是客户交付工作产物，公开会提前暴露未发布的产品（见§3） |
| `supervisor/skills/` | ✅ 原样保留 | 3 个 SKILL.md 文件（ai-dlc、ai-dlc-doctor、ui-designer），引用 `jiuwenswarm` 作为上游工具名（概念性引用，非路径） |
| `scripts/` | ✅ 已脱敏 | 3 个 shell 脚本，`/root/.jiuwenswarm` → `${HOME}/.jiuwenswarm`，`/root/.local` → `${HOME}/.local` |
| `targets/` | ✅ 已脱敏 | 6 个 JSON 文件。`claude-glm.json`、`claude-maas.json`、`claude.json` 的 `/root/` 路径改为 `~/`；`codex.json`、`copilot.json`、`cursor.json` 原本就用 `<project-root>` 占位符 |
| `tests/` | ✅ 已脱敏 | 60 个文件。`/root/.local/bin/python3.12` → `python3.12`，`/root/DevTeam` → `<workspace-root>`，`/root/.ad-unmask-check` → `<tmp>/ad-unmask-check`，`mktemp -d /root/ai-dlc-l7t-XXXXXX` → `/tmp/ai-dlc-l7t-XXXXXX`。部分测试中的 `/root/.jiuwenswarm` 保留（见§3） |
| `evidence/` | ❌ 排除 | 见§2 |
| `.ai-dlc/` | ❌ 排除 | 内部状态文件：`argentina-design-probe.json`（包含 `/root/.local/bin/jiuwenswarm`、`/opt/open-design/` 等机器路径）、`attic/route-and-speed-hand-draft/`（内部旧设计草案）。这些是内部工作产物，不适合公开 |

---

## 2. evidence/ 目录的处理方式和理由

**处理方式：整体排除。**

**体积：** 429 个文件，6.6 MB（占原仓库总体积 7.8 MB 的 85%）。

**内容性质：** evidence/ 是 AI-DLC 各版本的内部基准测试和端到端验证证据，包括：
- CSV 解析器基准测试（`four-run-baseline/`，428K）
- 各版本 E2E 测试记录（`v0.1.0-e2e/` 到 `v0.5.0-e2e/`，合计约 1.3M）
- DevTeam 角色移除证据（`v0.9.0-devteam/`，1.9M）
- Landing 验收证据（`v0.9.0-landing/`，2.6M）
- 其他版本证据（合计约 0.5M）

**排除理由：**

1. **机器路径泄露：** 约 80 个文件包含 557 处机器专属路径，包括 `/root/DevTeam/ojtest2`、`/root/.jiuwenswarm/...`、`/root/.claude-maas/projects/-root-DevTeam/...`、`/root/LiteLLM-Huawei-MaaS-Proxy`、`/root/1-3-Cloud-Adoption-Skills` 等。逐文件脱敏工作量大且容易遗漏。

2. **完整 LLM 对话记录：** 11 个 JSONL 文件（约 3.9 MB）包含完整的 LLM 会话帧（`chat.reasoning` 推理链、`chat.tool_call` 工具调用参数、`chat.delta` 流式输出）。虽然内容是技术性的（编写 spec、proposal、设计文档），但工具调用参数中嵌入了机器路径，且这些推理链是否适合公开需要人工判断。

3. **内部基础设施信息：** 包含内部项目名（`LiteLLM-Huawei-MaaS-Proxy`、`1-3-Cloud-Adoption-Skills`）、GitHub 用户名（`binrogithub`）、systemd 服务路径和 PID、华为云 MaaS 基础设施引用。

4. **对公开用户价值有限：** evidence/ 是内部开发验证材料，对使用 AI-DLC 工具的外部用户没有直接用途。工具功能已通过 README、CHANGELOG、docs/、tests/ 充分文档化。

5. **无敏感数据但非公开产物：** 审查确认 evidence/ 不包含真实密钥、私有 IP、客户数据或个人身份信息。内容本质上是技术基准数据，但体积和机器路径密度使得整体排除比逐文件脱敏更合理。

**注意：** README.md 第 76 行引用了 `evidence/four-run-baseline/`。排除 evidence/ 后该引用指向不存在的目录，需要在 README 重写时处理（见§3）。

---

## 3. 需要人工决定的事项

以下逐条列出，不要笼统一句话带过：

### 3.1 开源许可证（LICENSE）
原仓库没有 LICENSE 文件。**不要擅自添加**——许可证选择是人的决定。需要确认：
- 用什么协议（MIT / Apache-2.0 / GPL-3.0 / 其他）？
- 是否有第三方代码需要兼容其许可证（如 OpenDesign 引用）？

### 3.2 README.md 需要人工再润色
现有 README.md 不适合直接作为公开项目首页：
- **缺少面向外部读者的介绍**：开头假设读者知道 "delegated orchestrator"、"the plane"、"csvmini" 等内部概念，没有 "这是什么 / 给谁用 / 怎么快速上手" 的说明
- **引用内部指标**：第 12-20 行引用 "4,963,611 input tokens, 0/4 correct deliveries" 等内部测量数据
- **引用已退役的内部系统**：tag `v0.5.1-delegated-final`、`v0.8.0` 等
- **引用不存在的目录**：第 76 行引用 `evidence/four-run-baseline/`（已排除）
- **命名内部工具**：第 123 行 "Never modify openspec / openjiuwen / delegate / delegate-router / jiuwenswarm source"，外部读者不知道这些是什么
- **不重写产品定位**，但建议人工补充：项目简介、适用场景、前置条件、快速开始、许可证

### 3.3 "jiuwenswarm" / "openjiuwen" / "delegate-router" 内部工具名
这些名称出现在 README.md、CHANGELOG.md、bin/plan.py、install.sh、scripts/、docs/、supervisor/skills/、tests/、openspec/specs/ 中（50+ 处）。它们是上游网关/编排工具的名称。需要确认：
- `jiuwenswarm` 是否是公开已知的项目？如果是内部/专有工具名，是否需要替换为通用名称？
- `openjiuwen`、`delegate-router`、`delegate` 同理
- 注意：替换这些名称涉及代码逻辑变更（`FORBIDDEN_DIR_MARKERS`、systemd 服务名、路径默认值等），不是简单的文本替换

### 3.4 bin/plan.py 和 install.sh 中的硬编码 `/root/` 默认值
以下默认值保留在代码中（均有 `AI_DLC_*` 环境变量可覆盖，但默认值是机器专属的）：
- `bin/plan.py:267` — `CLIENT = os.environ.get("AI_DLC_CLIENT", "/root/.local/bin/jiuwenswarm")`
- `bin/plan.py:275` — `"/root/.jiuwenswarm/agent/workspace/skills"`
- `bin/plan.py:1450` — `"/etc/systemd/system/jiuwenswarm-gateway.service"`
- `bin/plan.py:2748` — `f"/root/.jiuwenswarm/agent/sessions/"`
- `install.sh:63` — `PROJECT_ROOT=/root/DevTeam`（已脱敏为 `<workspace-root>`，但可能影响功能）
- `install.sh` 多处 — `/root/.jiuwenswarm` 默认值

**建议：** 将默认值改为 `~/.local/bin/jiuwenswarm` 或要求必须设置环境变量。但这是代码设计决策，需要人确认。

### 3.5 tests/ 中保留的 `/root/` 路径
部分测试文件中仍有 `/root/.jiuwenswarm`、`/root/.claude` 等路径，这些是测试 systemd 网关配置的 fixture。脱敏可能破坏测试逻辑。需要确认：
- 这些测试是否只在特定机器上运行？
- 是否应该用环境变量替换硬编码路径？

### 3.6 `openspec/changes/2026-09-01-vivo-maas-launch/` — 客户商业敏感
已排除。该变更描述为 Vivo（巴西最大移动运营商）基于华为云 MaaS 构建 AI 模型服务发布网站，包含：
- 产品定价方案（Starter/Business/Enterprise）
- 模型目录（GLM-5.2、Qwen2.5-72B、DeepSeek-V3、Llama-3.3-70B）
- 数据驻留信息（圣保罗）、合规认证（LGPD、ISO 27001）
- Vivo 与华为云的合作关系

**如果 Vivo/华为云已授权公开，可以加回来。否则保持排除。**

### 3.7 "Robin" — 内部人名
出现在 CHANGELOG.md（第 3、89 行）和多个 docs/ 文件中，作为产品负责人/决策者。CHANGELOG.md 中的引用已保留（脱敏会改变历史记录的含义）。docs/ 中的 "Robin" 引用也已保留。需要确认：
- 是否需要将 "Robin" 替换为匿名化称呼（如 "the product owner"）？
- openspec/changes/archive/ 中的 "Robin" 已替换为 "the product owner"

### 3.8 `nexu-io/open-design` — GitHub 组织引用
`docs/prd-uidesigner-opendesign.md` 和 `scripts/install-opendesign.sh` 引用 `https://github.com/nexu-io/open-design`。需要确认该 GitHub 组织是否公开可见。如果是私有组织，这个引用会泄露它。

### 3.9 `.ai-dlc/` 目录排除
`.ai-dlc/argentina-design-probe.json` 包含 `/root/.local/bin/jiuwenswarm`、`/opt/open-design/` 等机器路径和内部探测记录。`.ai-dlc/attic/route-and-speed-hand-draft/` 是内部旧设计草案。已整体排除。如果 `attic/` 中的设计文档有公开价值，可以单独审查后加入。

### 3.10 `targets/claude.json` 中的中文角色描述
`targets/claude.json` 的 `role` 字段是中文（"交互壳 — 命令入口、人机交互、状态展示"）。如果面向国际公开，可能需要翻译为英文。这是产品决策，不擅自修改。

---

## 4. PR 描述草稿

```
## AI-DLC — Spec-Driven Coding Lifecycle for Claude Code

AI-DLC is a collapsed execution runtime that makes Claude Code the
executor in a spec-driven development lifecycle. Claude Code reads,
writes, and runs tests itself inside a per-task git worktree. Strict
spec validation (`openspec validate --strict`) is the plan criterion.
A human reads the deliverable and holds the merge gate.

### Architecture

- **2 gates**: G-DELIVER-1 (landed files/bytes from the real git diff
  + spec validation) and MERGE_GATE (human, rationale required)
- **4 states**: Working / Checking / Ready / Needs your decision
- **Task flow**: ROUTE → WORK → CHECK → REPORT → MERGE_GATE

### What's in this release

- `bin/plan.py` — planning dispatch: roles, prompts, boundary check,
  close/archive tail
- `bin/report.py` — init/deliver/gate: the human surface and two gates
- `bin/aidlc-shell` — systemd containment shell for the agent runtime
- `supervisor/skills/` — execution skills (ai-dlc, ai-dlc-doctor,
  ui-designer)
- `config/collapsed.config.yaml` — 5 config keys
- `openspec/specs/` — 21 process spec definitions
- `tests/collapse/` — live test suite (shell + Python)
- `docs/` — 12 PRD/design rationale documents
- `install.sh` — idempotent installer with `--doctor` health check

### What's NOT in this release

- `evidence/` — internal benchmark/test evidence (6.6 MB, 429 files)
  excluded; contains machine-specific paths and LLM session transcripts
- `openspec/changes/2026-09-01-vivo-maas-launch/` — client project
  excluded (business-sensitive)
- `.ai-dlc/` — internal state files excluded

### Install

```bash
./install.sh            # skills + openspec CLI
./install.sh --doctor   # health check
```

### Notes

- No LICENSE file included — license TBD
- README may need revision for public audience
- Some code defaults reference internal tool paths (overridable via
  environment variables)
```

---

## 5. 审查方法

- 通读 `task/design-required` 分支全部 556 个 git 跟踪文件的结构
- 用 `grep` 扫描硬编码 IP（10.x / 172.16-31.x / 192.168.x / 124.81.97.217）、机器路径（/root/DevTeam、/root/.jiuwenswarm、ecs-maas-test）、密钥模式（sk-、Bearer、MAAS_API_KEY=）
- 对 evidence/ 逐子目录抽样阅读 README、JSON、JSONL、log 文件，检查 11 个完整 LLM 对话记录文件
- 对 docs/、openspec/、supervisor/、bin/、scripts/、config/、targets/、tests/ 逐文件审查敏感内容
- 检查 openspec/changes/ 变更历史中的客户项目引用和内部代号
- 评估 README.md 作为公开项目首页的适用性

---

## 客户名 vivo → client-x 替换（2026-09-02）

将 8 个文件中作为「客户名/内部代号」使用的 `vivo`/`Vivo` 统一替换为 `client-x`/`Client-x`：

- `bin/plan.py`（第 7646、7707-7708、7736 行附近注释）
- `bin/report.py`（第 920、1648、1653 行附近注释）
- `tests/collapse/wr_work_ref.sh`（第 287、300、319 行——构造数据与断言同步替换，`vivo-ai-launch` → `client-x-ai-launch`）
- `tests/collapse/dm_measure_work.sh`（第 81、83、150 行——`<h1>Vivo</h1>` → `<h1>Client-x</h1>`、commit message `vivo page` → `client-x page`）
- `docs/prd-deliver-measures-work.md`
- `docs/prd-uidesigner-reliable-fast.md`
- `docs/prd-devteam-workflow-hardening.md`
- `docs/prd-agent-onboarding.md`

补充：`docs/prd-uidesigner-reliable-fast.md` 中路径变体 `/tmp$ivo-ai-launch/`（`$` 吞掉了 `/v`，不含 `vivo` 子串，首轮替换漏掉）也已统一替换为 `/tmp$client-x-ai-launch/`。

自检：`grep -rliE 'vivo' /root/ai-dlc/` 仅剩 `PUBLISH_NOTES.md`（本文件记录替换事实的元描述，以及 §3/§3.6 中描述被排除的 `openspec/changes/2026-09-01-vivo-maas-launch/` 的商业敏感说明——后者是对真实客户交付产物的排除记录，保留原客户名以保持事实准确性）。

### 二次扫描（2026-09-02）

上一轮敏感词扫描只覆盖 IP/路径/密钥模式，未覆盖「客户名/内部代号/人名」维度。本次在全仓库范围内做了补充扫描，逐条结论如下：

**已处理（替换）：**

| 项 | 位置 | 处理 |
|---|---|---|
| `1-3-Cloud-Adoption-Skills` | `docs/plane-runtime.md:284`（内部项目代号，出现在 config 条目描述中） | → `<internal-project>` |
| `devteam-design-select-widget-scope-prd-20260902.md` | `tests/test_design_v2.py:1042`（注释中引用内部 PRD 文件名） | → `the widget-scope PRD` |

**已记录待人工确认（不替换，替换会破坏功能或丢失技术准确性）：**

| 项 | 位置 | 说明 |
|---|---|---|
| `@fission-ai/openspec` | `install.sh`（3 处）、`docs/prd-openspec-containment.md`（2 处）、`tests/collapse/l7_target_safety.sh`（3 处） | npm scoped package，揭示 GitHub org `fission-ai`。与 §3.8 `nexu-io/open-design` 同类——若是公开包则 org 名已公开，若是私有则需确认。替换会破坏安装逻辑，未动。 |
| `open.bigmodel.cn` | `docs/prd-openspec-containment.md:102` | 智谱 AI（Zhipu）公开 API 端点，揭示 LLM 供应商。该 PRD 描述实际 containment 设置，替换会丢失技术准确性。保留，待人工确认。 |

**判定为良性（不替换）：**

| 项 | 位置 | 说明 |
|---|---|---|
| `peru`/`argentina`/`brazil`/`panama`/`colombia`/`rio` | 约 25 个文件（CHANGELOG、tests/、docs/、bin/、openspec/） | 通用国家/城市名，作为案例代号和测试夹具使用，被多处断言依赖。`rio` 首轮未记录，本次补录。未替换——待人工确认是否需要进一步匿名化。 |
| `csvmini` | CHANGELOG、docs/、supervisor/skills/ | 内部测试项目代号。已泛化改写为 "a CSV-parsing benchmark project" / "the benchmark project"（首次全称、后续简称），保留全部数字和论证逻辑，仅替换专有名词。详见 §5.6。 |
| `hello-site`/`landing`/`brazil-tourism`/`peru-tourism` | docs/、tests/、openspec/ | 通用测试夹具名。`hello-site` 已删除具体举例内容（详见 §5.3/§5.4），其余保留。 |

**未发现：** 其他真实客户名、其他真实人名（`Robin` 已在 §3.7 处理）、其他真实公司名（华为云作为技术栈提及，保留）。

---

## §4 二次处理记录（2026-09-02 续）

### §4.1 第一件事：内部工具名对外统一用 openjiuwen

将 `jiuwenswarm`/`delegate-router`/`delegate` 在 A 类（纯文字/文档引用）位置替换为 `openjiuwen`，B 类（代码依赖的真实字面值）保持不变。

**A 类改了以下文件：**

| 文件 | 改了什么 |
|---|---|
| `bin/plan.py` | 2 处注释（`jiuwenswarm session history` → `openjiuwen session history`） |
| `targets/claude-glm.json` | role 字段 `delegate/workflow` → `openjiuwen/workflow` |
| `targets/claude-maas.json` | role 字段 `delegate 默认客户端` → `openjiuwen 默认客户端` |
| `supervisor/skills/claude/ai-dlc/SKILL.md` | 2 处叙述性提及（`through jiuwenswarm` → `through openjiuwen`） |
| `scripts/setup-maas-key.sh` | 3 处注释/帮助文本（`jiuwenswarm gateway` → `openjiuwen gateway`） |
| `scripts/configure-gateway-model.sh` | 1 处注释（`jiuwenswarm turns every...` → `openjiuwen turns every...`） |
| `tests/collapse/glue_surface.sh` | 2 处注释（`shipped jiuwenswarm client` → `shipped openjiuwen client`、`names jiuwenswarm as the sole` → `names openjiuwen as the sole`） |
| `tests/collapse/d2_legacy_surface.sh` | 2 处注释（`delegate/sdd-proposed` → `openjiuwen/sdd-proposed`、`delegate_dispatch` → `openjiuwen_dispatch`） |
| `CHANGELOG.md` | 约 20 处叙述性文字中的工具名引用（`delegate`/`delegate-router`/`jiuwenswarm` → `openjiuwen`） |
| `docs/prd-openspec-containment.md` | 6 处叙述性提及 |
| `docs/prd-gateway-open-sandbox.md` | 2 处叙述性提及（不含 systemctl 命令） |
| `docs/prd-uidesigner-reliable-fast.md` | 3 处叙述性提及 |
| `docs/prd-design-autodispatch.md` | 2 处叙述性提及 |
| `docs/prd-design-required.md` | 1 处叙述性提及 |
| `docs/prd-deliver-measures-work.md` | 1 处叙述性提及 |
| `docs/prd-install-targets.md` | 5 处叙述性提及及 role 字段 |
| `docs/prd-uidesigner-opendesign.md` | 10 处叙述性提及（不含 `~/.jiuwenswarm/` 路径） |
| `docs/plane-runtime.md` | 1 处叙述性提及（不含 systemctl 命令/路径） |
| `docs/team-mode-record.md` | 2 处叙述性提及（不含 `<workspace-root>/reference/jiuwenswarm` 路径） |

**B 类跳过（保持原样）的具体位置：**

| 文件 | 行 | 内容 | 为什么是 B 类 |
|---|---|---|---|
| `bin/plan.py` | 267 | `os.environ.get("AI_DLC_CLIENT", "...jiuwenswarm")` | 真实二进制路径 |
| `bin/plan.py` | 275 | `"...jiuwenswarm/agent/workspace/skills"` | 真实文件系统路径 |
| `bin/plan.py` | 1450 | `"/etc/systemd/system/jiuwenswarm-gateway.service"` | 真实 systemd 服务路径 |
| `bin/plan.py` | 2118 | `FORBIDDEN_DIR_MARKERS = ("delegate-router", "jiuwenswarm", "openjiuwen")` | 真实代码字面值，检查目录名 |
| `bin/plan.py` | 2126 | `claude-code-oauth-delegate-router source` | 真实外部包名 |
| `bin/plan.py` | 2492-2493 | `"never-modify rule names delegate-router / jiuwenswarm / openjiuwen / openspec"` | 用户可见错误消息，与 FORBIDDEN_DIR_MARKERS 对应 |
| `bin/plan.py` | 2748 | `f"...jiuwenswarm/agent/sessions/"` | 真实文件系统路径 |
| `install.sh` | 38,45,46,48,50,120,124,126,128,131,167,315,374,410 | 各处 `${HOME}/.jiuwenswarm`、`jiuwenswarm-gateway` | 真实路径/服务名/systemctl 操作 |
| `install.sh` | 929-938 | `command -v jiuwenswarm`、`uv tool install jiuwenswarm==0.2.3` | 真实命令/包名 |
| `scripts/setup-maas-key.sh` | 20,37,155,162,163,165 | `$HOME/.jiuwenswarm/config/.env`、`systemctl restart jiuwenswarm-gateway` | 真实路径/服务名 |
| `scripts/install-opendesign.sh` | 38,40 | `$HOME/.jiuwenswarm/...` | 真实路径 |
| `scripts/configure-gateway-model.sh` | 36,37,38,184 | `${HOME}/.jiuwenswarm/...`、`jiuwenswarm-gateway` | 真实路径/服务名 |
| `tests/collapse/l4_doctor.sh` | 26,38,49,50,64 | `jiuwenswarm-gateway` 断言 | 测试断言真实服务名 |
| `tests/collapse/l7_target_safety.sh` | 71,72,82 | `claude-code-oauth-delegate-router` | 真实外部包名 |
| `tests/collapse/open_plane.sh` | 237,272 | `ReadWritePaths=/root/.jiuwenswarm`、`AI_DLC_GW_SERVICE=jiuwenswarm-gateway` | 真实路径/服务名 |
| `tests/collapse/doctor_opendesign_check.sh` | 13,14,24,46 | `$T/fakehome/.jiuwenswarm/config` | 测试构造真实路径结构 |
| `tests/collapse/glue_surface.sh` | 80,98 | `grep ... "jiuwenswarm"` | 真实 grep 模式 |
| `tests/collapse/d2_legacy_surface.sh` | 17,26,27,76,77 | `grep ... delegate_dispatch`、`grep ... 'via `delegate`'` | 真实 grep 模式 |
| `openspec/specs/glue-boundary/spec.md` | 44 | `grep for ... jiuwenswarm` | 规范要求 grep 真实名 |
| `config/collapsed.config.yaml` | 4 | `v0.5.1-delegated-final` | 真实 git tag |
| `docs/plane-runtime.md` | 73,106,218,221,264,275,304,368 | systemctl 命令/路径 | 真实命令/路径 |
| `docs/team-mode-record.md` | 9,34,70,73 | `<workspace-root>/reference/jiuwenswarm`、`~/.jiuwenswarm/...` | 真实路径 |
| `docs/prd-uidesigner-opendesign.md` | 282,283,289,369,370 | `~/.jiuwenswarm/...` 路径 | 真实路径 |
| `docs/prd-install-targets.md` | 42 | `~/.jiuwenswarm/agent/workspace/skills/` | 真实路径 |
| `CHANGELOG.md` | 763,813,830 | `v0.5.1-delegated-final` | 真实 git tag |
| `CHANGELOG.md` | 1648,1650 | `jiuwenswarm-start` | 真实命令名 |
| `CHANGELOG.md` | 1657 | `~/.jiuwenswarm/config/.env` | 真实路径 |

**拿不准跳过的位置（交给你判断）：**

| 文件 | 行 | 内容 | 为什么拿不准 |
|---|---|---|---|
| `install.sh` | 898 | `echo "  2. jiuwenswarm gateway    (uv tool install, ...)"` | 用户可见的安装进度消息。改成 openjiuwen 不影响执行，但下方实际命令仍安装 `jiuwenswarm==0.2.3`，可能造成用户困惑 |
| `install.sh` | 925 | `# ── Step 2/5: jiuwenswarm ──` | 安装步骤标题注释。同上理由 |
| `install.sh` | 934 | `fail "jiuwenswarm install failed — check network or PyPI access"` | 错误消息。用户看到后需要去 PyPI 查 `jiuwenswarm` 包，改成 openjiuwen 会误导 |
| `install.sh` | 936 | `warn "uv not found — jiuwenswarm install command needs..."` | 同上 |
| `install.sh` | 1016 | `--bootstrap ... (openspec → jiuwenswarm → MaaS key → ...)` | 帮助文本描述安装流程。同 line 898 理由 |
| `config/collapsed.config.yaml` | 2 | `The delegated pipeline's` | "delegated" 是形容词不是工具名，但暗示了内部名 |
| `CHANGELOG.md` | 808,810,838 | `delegated orchestrator`、`delegated test suite`、`delegated run's` | "delegated" 是形容词，不是工具名 `delegate` |
| `CHANGELOG.md` | 1135 | `delegated: v0.5.1` | git tag 引用 |
| `openspec/specs/glue-boundary/spec.md` | 27 | `SHALL delegate to an external` | "delegate" 是动词，不是工具名 |
| `openspec/specs/legacy-removal/spec.md` | 4,11,17,24 | `delegated design`、`delegated worker` | "delegated" 是形容词 |
| `supervisor/skills/claude/ai-dlc/SKILL.md` | 102 | `delegate-router / jiuwenswarm / openjiuwen / openspec source` | 列举 FORBIDDEN_DIR_MARKERS 的真实目录名 |
| `supervisor/skills/claude/ai-dlc/SKILL.md` | 283 | `Delegated orchestrator: v0.5.1-delegated-final` | git tag |
| `docs/prd-install-targets.md` | 67 | `delegate:78` | 代码行号引用（真实源码位置） |

### §4.2 第二件事：硬编码 /root/ 默认值改为通用默认值

| 文件 | 原内容 | 改为 |
|---|---|---|
| `bin/plan.py:267` | `os.environ.get("AI_DLC_CLIENT", "/root/.local/bin/jiuwenswarm")` | `os.environ.get("AI_DLC_CLIENT", os.path.expanduser("~/.local/bin/jiuwenswarm"))` |
| `bin/plan.py:275` | `"/root/.jiuwenswarm/agent/workspace/skills"` | `os.path.expanduser("~/.jiuwenswarm/agent/workspace/skills")` |
| `bin/plan.py:2748` | `f"/root/.jiuwenswarm/agent/sessions/"` | `f"{os.path.expanduser('~/.jiuwenswarm/agent/sessions/')}"` |
| `install.sh:21` | `--target-dir /root/.claude-x` | `--target-dir ~/.claude-x` |
| `install.sh:972,1114` | `echo "/root/.claude"` | `echo "${HOME}/.claude"` |

`bin/plan.py` 语法检查通过（`py_compile`）。未找到针对这些默认值逻辑的单元测试（`pytest -k 'client or workspace or path'` 无匹配）。

### §4.3 第三件事：国家名匿名化

**替换方案：** 按国家名字母序编号——`argentina` → `country-a`、`brazil` → `country-b`、`colombia` → `country-c`、`panama` → `country-d`、`peru` → `country-e`。大写形式（`Brazil`、`Peru` 等）和形容词形式（`Brazilian`）统一映射到对应小写代号。`rio` 是城市名不在本次范围内，保留。

**理由：** 编号方式保留了"是不同的国家/项目"这一语义区分，但不透出具体是哪国。字母序对应（a=argentina, b=brazil, ...）简单可追溯。

**涉及 20 个文件 + 1 个文件重命名：**

| 文件 | 类型 |
|---|---|
| `CHANGELOG.md` | 叙述性案例代号 |
| `bin/plan.py` | 注释中的案例代号 |
| `bin/report.py` | 注释中的案例代号 |
| `docs/plane-runtime.md` | 叙述性提及 |
| `docs/prd-agent-onboarding.md` | 叙述性提及 |
| `docs/prd-deliver-measures-work.md` | 叙述性提及 |
| `docs/prd-design-autodispatch.md` | 叙述性提及 |
| `docs/prd-design-required.md` | 叙述性提及 |
| `docs/prd-devteam-workflow-hardening.md` | 叙述性提及 |
| `docs/prd-gateway-open-sandbox.md` | 叙述性提及 |
| `docs/prd-openspec-containment.md` | 叙述性提及 |
| `docs/prd-uidesigner-opendesign.md` | 叙述性提及 |
| `docs/prd-uidesigner-reliable-fast.md` | 叙述性提及 |
| `openspec/changes/archive/2026-09-01-uidesigner-opendesign/proposal.md` | 叙述性提及 |
| `tests/collapse/wr_work_ref.sh` | 注释 + 测试数据（`<body>brazil</body>` → `<body>country-b</body>`） |
| `tests/fixtures/design-select/brazil-restaurant.json` → **重命名为** `country-b-restaurant.json` | 夹具 change ID + proposal 文本 |
| `tests/fixtures/design-select/tourism-landing.json` | 夹具 change ID + proposal 文本 |
| `tests/fixtures/design-select/hwc-maas-soft-wrap.json` | proposal 文本（`Brazilian Portuguese` → `country-b Portuguese`） |
| `tests/test_design_select_fixtures.py` | 注释引用夹具名 |
| `tests/test_design_v2.py` | 测试数据 proposal 文本 |

**测试数据 + 断言配对检查：** 检查了所有涉及国家名的测试文件，未发现构造数据与断言分别在不同位置且依赖具体国家名字符串的配对（`wr_work_ref.sh` 中的 `brazil` 出现在测试数据 `<body>brazil</body>` 但不被断言——断言检查的是分支结构，不是文件内容；`test_design_v2.py` 中的 `Brazilian restaurant` 是 proposal 文本但断言检查的是 `dashboard` 不在 query_tokens 中，与国家名无关）。

**自检：** `grep -rliE 'peru|argentina|brazil|panama|colombia' /root/ai-dlc/` 仅返回 `PUBLISH_NOTES.md`（本文件中的元描述）。

**测试运行结果：**

| 测试文件 | 结果 |
|---|---|
| `tests/collapse/wr_work_ref.sh` | ✅ PASS（Y1-Y12 全绿） |
| `tests/collapse/d2_legacy_surface.sh` | ✅ PASS |
| `tests/collapse/glue_surface.sh` | ❌ FAIL（**预先存在的失败**，非本次修改引入） |

`glue_surface.sh` 失败原因：该测试 grep 查找 `jiuwenswarm` 在非排除文件中的残留，发现 `PUBLISH_NOTES.md`（用户手写、要求不动）、`scripts/setup-maas-key.sh` 和 `tests/collapse/doctor_opendesign_check.sh` 中有 B 类真实路径/服务名。这些文件在本次修改前就包含 `jiuwenswarm`，且不在 `glue_surface.sh` 的排除列表中。本次 A 类修改实际上**减少**了 `jiuwenswarm` 的出现次数，未引入任何新的。如需修复此测试，可将上述文件加入排除列表，或确认 `PUBLISH_NOTES.md` 在公开发布时不随仓库分发。

---

## §5 脱敏收尾（2026-09-03）

三件事，对之前几轮脱敏工作的收尾。

### §5.1 bigmodel.cn 引用脱敏

`docs/prd-openspec-containment.md` 第 102 行 E4 条目原文点名了具体模型供应商端点 `https://open.bigmodel.cn/api/anthropic` 和模型名 `glm-5.3`。替换为通用占位 `<vendor-endpoint>` 和 `<vendor-model>`，技术论述逻辑不变（「CC 出口是一个外部 HTTPS 端点，不是本地代理，所以基于 127.0.0.1 的白名单策略不适用」）。同文件第 106 行的 `<cc-glm-config>` 也替换为 `<cc-vendor-config>`。第 99 行的 `api.anthropic.com` 保留——那是 Anthropic 自身的公开 API 端点，用于连通性测试，不是第三方供应商选择。

此前 §4 二次扫描中第 227 行标注 `open.bigmodel.cn`「保留，待人工确认」，本次已处理。

### §5.2 rio/Rio 匿名化

`rio`/`Rio` 是真实历史事件/项目代号，处理方式与此前 `vivo→client-x`、国家名→`country-x` 一致，统一替换为 `demo`：

| 文件 | 改了什么 |
|---|---|
| `CHANGELOG.md`（第 189-192 行） | `Rio incident` → `demo incident`、`rio-site` → `demo-site`、`g10-rio-m1-report.json` → `g10-demo-m1-report.json` |
| `tests/collapse/g10_discrimination.sh` | 全文 `rio`→`demo`、`Rio`→`demo`：注释、task_id（`rio-m1`→`demo-m1` 等）、change_id（`rio-site`→`demo-site`、`rio-ok`→`demo-ok`、`rio-forged`→`demo-forged`）、grep 断言、fixture 路径引用、最终 echo 消息 |
| `tests/collapse/fixtures/g10-rio-m1-report.json` → **重命名为** `g10-demo-m1-report.json` | fixture 内 `task_id`、`files` 路径、`command` 字段全部 `rio`→`demo` |
| `tests/collapse/fixtures/README.md` | `/tmp/Rio/` → `/tmp/demo/`、`Rio run` → `demo run`、`rio-site` → `demo-site`、`rio-m1` → `demo-m1` |

**三者一致性：** 测试脚本构造的 task_id/change_id、grep 断言模式、fixture JSON 字段值三方互引，已确认全部同步替换为 `demo` 系列。

**测试结果：** `bash tests/collapse/g10_discrimination.sh` → ✅ PASS。

### §5.3 hello-site 匿名化

`hello-site` 出现在 5 个文件中，敏感度低于 rio/vivo/国家名（类似 hello-world 风格的示例名），但按要求统一处理。**选择 `sample-site` 而非 `demo-site`** 作为替代词，原因是 `demo-site` 已被 §5.2 中 `rio-site` 的替换结果占用，两者引用不同的事件，使用同一字符串会造成语义歧义。`sample-site` 与 `demo` 系列无冲突。

| 文件 | 改了什么 |
|---|---|
| `tests/collapse/d3_plan_judge.sh`（第 70 行注释） | `hello-site sessions` → `sample-site sessions`（仅注释，无断言依赖） |
| `docs/plane-runtime.md`（第 236 行） | `<workspace-root>/hello-site` → `<workspace-root>/sample-site` |
| `openspec/changes/archive/2026-09-01-uidesigner-opendesign/proposal.md`（第 5 行） | `hello-site and landing` → `sample-site and landing` |
| `bin/plan.py`（第 718 行注释） | `hello-site sessions` → `sample-site sessions` |
| `docs/prd-uidesigner-opendesign.md`（第 14、317 行） | 两处 `hello-site` → `sample-site` |

**测试结果：** `bash tests/collapse/d3_plan_judge.sh` → ✅ PASS。

**后续（§5.4 追加处理）：** 改名只是中间步骤，用户随后要求删掉这些具体举例内容本身，详见 §5.4。

### §5.4 追加决定（2026-09-03）：Rio 整个测试删除，而不是改名保留

用户明确决定 §5.2/§5.3 的处理方式不够——rio 和 hello-site 相关内容"不应该是发布的内容"，直接删除而不是改名后保留。逐项处理：

- **Rio → 整个删除。** `tests/collapse/g10_discrimination.sh` 和
  `tests/collapse/fixtures/`（`g10-demo-m1-report.json` + `README.md`）
  已删除。理由：这两个文件的**全部内容**就是这一次真实历史事件的回放
  测试和它的 fixture 数据——改名成 `demo` 之后除了测试逻辑本身，文件
  已经没有别的存在理由了，直接删比留一个"改了名的空壳"更干净。
  `CHANGELOG.md`/`docs/prd-devteam-workflow-hardening.md` 里还有几处
  提到 `g10_discrimination`/`g10-demo-m1-report.json` 这两个文件名——
  这些是**历史记录性质的文字提及**（changelog 记着"这个测试是什么时候
  加的"，PRD 记着"诊断时夹具跟哪几个测试脚本有关"），不是指向真实文件
  的可执行链接，删除测试文件本身不会让这些文字失效或者产生死链接，
  参照本项目自己的原则（退役代码用 git rm + 历史记录锚定，不做静默
  删除）保留不动。
  删除后重跑了 `pytest tests/test_design_v2.py`（36 passed）和
  `test_design_select_fixtures.py`（13/13），确认没有其他文件引用这两
  个被删的路径。

- **hello-site → 删除具体举例内容（不只是改名）。**
  跟 Rio 不一样：`hello-site` 只是散落在 `bin/plan.py`、
  `docs/plane-runtime.md`、`docs/prd-uidesigner-opendesign.md`、
  `openspec/changes/archive/.../proposal.md`、
  `tests/collapse/d3_plan_judge.sh` 里的**一处举例/一行提及**，这几个
  文件本身的主题分别是"设计角色调度逻辑""网关运行时授权记录""设计
  流程 PRD""D3 判定逻辑测试"——都不是"关于 hello-site 这件事"的文件，
  删掉整份文件会丢掉这些文件里其他大量不相关、正常应该发布的技术内容。
  因此逐处删除 `sample-site` 这一个举例本身，保留各自文件里其余内容：
  `docs/prd-uidesigner-opendesign.md` 两处并列列举各删掉 `sample-site`
  一项、保留其余例子并调整连词；`proposal.md` 从四项并列删成三项；
  `docs/plane-runtime.md` 删掉 YAML 配置示例中 `<workspace-root>/sample-site`
  那一行；`bin/plan.py` 和 `tests/collapse/d3_plan_judge.sh` 的注释里
  `sample-site sessions` 改成抽象的 `these sessions`。

**核实时额外发现并修复**：`bin/plan.py` 那处删除举例后留了一个悬空的 "the user's"（"the user's these sessions carry zero processing_status frames"，语法不通），已改成 "measured sessions carry zero processing_status frames"，语义不变、语法通顺。

### §5.5 自检（更新）

`grep -rliE 'bigmodel|rio-site|rio-m1|rio-m2|rio-m3|rio-ok|rio-forged|Rio incident|hello-site|csvmini|sample-site' /root/ai-dlc/` 仅返回 `PUBLISH_NOTES.md`（本文件中的元描述，包括此前 §4 二次扫描记录和本节）。搜索使用复合词模式，未搜裸 `rio` 三字母以避免误伤无关英文单词。

### §5.6 csvmini 泛化改写（2026-09-03）

`csvmini` 是作者内部的 CSV 解析测试/基准项目代号，出现在 3 个文件共 16 处。问题性质是"外部读者看不懂这是什么"，不是"这个信息不该被外部看到"——那些数字（4,963,611 input tokens、0/4 correct deliveries、12× wall / 11× input、−1 correctness 等）是真实技术证据，在论证具体架构决策，删掉会降低内容质量。因此**只换专有名词，保留数字、论证逻辑和因果关系**。

统一替代说法：首次出现写全称 "a CSV-parsing benchmark project"，后续简称 "the benchmark project"；历史代码路径引用（`probes/oracle_csvmini.py` 等）和内部标识符（`csvmini-e1`、`oracle.csvmini-o1b`、`csvmini-accept` 等）按纯文字提及处理，将 `csvmini` 部分替换为 `benchmark`。

| 文件 | 改了什么 |
|---|---|
| `CHANGELOG.md`（11 处） | 文件名 `oracle_csvmini.py` → `oracle_benchmark.py`、`csvmini_inline_reference.py` → `benchmark_inline_reference.py`；标识符 `csvmini-e1` → `benchmark-e1`、`oracle.csvmini-o1b`/`o2a` → `oracle.benchmark-o1b`/`o2a`；散文提及 `csvmini` → "a CSV-parsing benchmark project"（首次）/ "the benchmark project"（后续）/ "benchmark-project"（作复合形容词） |
| `supervisor/skills/claude/ai-dlc/SKILL.md`（1 处，第 276 行） | `Measured on csvmini` → `Measured on a CSV-parsing benchmark project`——保留 "12× wall / 11× input and bought −1 correctness" 这条硬性规则的实证依据 |
| `docs/plane-runtime.md`（4 处） | 配置项 `csvmini-accept` → `benchmark-accept`；散文 `csvmini-inline` → "a CSV-parsing benchmark project (inline form)" |

---

## §6 增量同步：phase-chain-automation（2026-09-04）

从 `<workspace-root>`（本次同步源分支：`master`，已合并 commit
`3577447`，归档 commit `af75f5e`）带来 `plan.py initiative`
（register/advance/status）这一个新功能，Phase A 范围（不含
`plan.py close` 尾部挂钩，那是单独一个未来 change）。

### 带过来的文件

| 文件 | 处理 |
|---|---|
| `bin/initiative.py` | ✅ 原样带入（新文件，扫描无机器路径/IP/内部工具名） |
| `bin/plan.py` | ✅ 手工应用同一段 diff（导入 + `initiative` 子命令 + 三行 dispatch），未整体覆盖——release 版 `plan.py` 已有独立于源仓库的脱敏历史（shebang、jiuwenswarm A/B 类替换等），整体覆盖会丢失那些改动 |
| `tests/test_initiative.py` | ✅ 原样带入（`created_by="robin"`/`decided_by="robin"` 是测试夹具数据，非真实指代；按 §3.7 已有先例保留，不匿名化） |
| `docs/prd-phase-chain-automation.md` | ✅ 已脱敏（见下） |
| `openspec/changes/archive/2026-09-03-phase-chain-automation/`（proposal/design/tasks/spec） | ✅ 原样带入——四个文件本身是英文技术内容，扫描无机器路径/IP/内部工具名。`design.md` 数据契约示例里的 `"created_by": "robin"` 同上，保留 |
| `openspec/specs/phase-chain-automation/spec.md` | ✅ 原样带入（archive 派发写回主 spec 树的那份，与 changes/archive/ 下的副本逐字节一致） |

### PRD 里的脱敏

`docs/prd-phase-chain-automation.md` 记录了一次针对某客户项目的 ai-dlc
使用情况复盘，原文包含：

- 工作区路径 `/root/DevTeam/ai-dlc` → `<workspace-root>`（沿用 §1 既有规则）
- 主机 IP `192.168.0.212` → `<host-ip>`（沿用 §1 既有规则，端口号
  `:8443` 本身通用，保留）
- 主机名 `ecs-auto-scaling` → 直接删除（不引入新占位符，叙述不依赖具体
  主机名）
- 客户项目路径 `/mnt/hcsa-production-closure` → `<client-project>`
  （新占位符——该路径名本身透出客户代号，与 §3.6 vivo 同类问题，但这里
  只是"曾经调查过"的引用，不是完整项目产物，用占位符替换即可，不需要
  像 vivo-maas-launch 那样整体排除）
- 正文一处提到 `vivo-maas-launch` 作为"单阶段任务"的例子——按 §1 已有的
  vivo→client-x 替换惯例，改为 `client-x-maas-launch`，避免在这份新文档
  里重新引入已经处理过一次的客户代号
- INV-7 一段原文使用内部工具名 `jiuwenswarm` 描述派发机制（纯叙述性提及，
  非真实路径/服务名）→ 按 §4.1 A 类规则替换为 `openjiuwen`

### 自检

```
grep -rnE '/root/|192\.168\.|110\.238\.|ecs-auto-scaling|hcsa-production-closure' \
  docs/prd-phase-chain-automation.md \
  openspec/changes/archive/2026-09-03-phase-chain-automation/ \
  openspec/specs/phase-chain-automation/ \
  bin/initiative.py tests/test_initiative.py
```

仅剩 PRD 里已脱敏的 `<host-ip>:8443` 占位符字符串本身（`8443` 三字符
被粗正则误命中，非真实 IP 泄露）。

### 测试

`pytest tests/test_initiative.py`：11 passed。全量回归
`pytest tests/ --ignore=tests/collapse`：47 passed，无破坏。

## §7 增量同步：codegraph role + Understand-Anything backend（2026-09-04）

从 `<workspace-root>`（本次同步源分支：`master`，范围
`3577447..b0a8276`，19 个 commit）带来完整的 codegraph 角色功能：
Phase A（确定性 codegraph_surface/codegraph-scope）、Phase B
（会话派发的 codegraph brief）、C1/C2（pin 住 Understand-Anything、
把 build/brief 从"调二进制"改写为"派发会话"）、jiuwenswarm 子 agent
注册、author 派发前自动触发、以及三个在真实 planned 任务验证过程中
发现并修复的 bug（worktree 可见性盲区、build 派发的非交互纪律、pin
摘要误把运行时产物算进去）。openspec/ 部分（vivo-maas-launch 删除、
phase-chain-automation 归档+spec）跟本目录当前状态逐字节一致，
无需同步（前者本来就没带过来，见 §2；后者已经在 §6 那次同步里带过）。

### 带过来的文件

| 文件 | 处理 |
|---|---|
| `bin/plan.py` | ✅ 手工应用同一段 diff（新增 `UNDERSTAND_ANYTHING_ROOT`/`_PATHS` 常量、`cmd_codegraph_scope`/`_build_core`/`build`/`brief`、pin 校验、非交互纪律 preamble、`_maybe_auto_codegraph` 挂钩等），未整体覆盖——理由同 §6：release 版已有独立于源仓库的脱敏历史（shebang、`jiuwenswarm`→`openjiuwen`、`Brazil`/`argentina`/`colombia`/`vivo`→`country-*`/`client-x` 等 A/B 类替换），整体覆盖会丢失那些改动。两处新增紧邻已脱敏行（`CLIENT` 常量后、`vivo round` 注释前），手工定位插入点后逐字节比对确认新增内容与源仓库一致、周边脱敏内容未被扰动 |
| `bin/report.py` | ✅ 同上手法（新增 `codegraph_surface`/`codegraph_auto_due`/`codegraph_auto_dispatch`/`_change_files_for_codegraph`），diff 干净应用，无需手工介入 |
| `docs/prd-codegraph-role.md`、`prd-codegraph-understand-anything-backend.md`、`prd-jiuwenswarm-understand-anything-subagents.md`、`prd-codegraph-docs-cleanup.md`、`prd-codegraph-author-autodispatch.md`、`prd-codegraph-autodispatch-worktree-blindspot.md`、`prd-codegraph-build-noninteractive-incremental.md`、`prd-codegraph-pin-digest-runtime-artifacts.md` | ✅ 8 个新 PRD，原样带入，仅 1 处脱敏（见下） |
| `scripts/install-understand-anything.sh` | ✅ 原样带入（新文件，照抄 `install-opendesign.sh` 的既有模式：sparse clone 到 `/opt/understand-anything`、`.aidlc-pin.json`、`chmod -R a-w`；扫描无机器路径/IP/内部代号） |
| `supervisor/skills/workspace/codegraph/SKILL.md` | ✅ 原样带入（新文件，workspace 技能定义） |
| `install.sh` | ✅ 原样带入 diff（`--doctor`/`--bootstrap`/`--understand-anything` 三处接入 Understand-Anything 安装步骤，扫描无机器路径） |
| `config/collapsed.config.yaml` | ✅ 原样带入 diff（`product_excludes` 加 `codegraph/**`、`.ua/**`） |
| `tests/collapse/dt1_gates.sh` | ✅ 原样带入 diff（子命令黄金列表加 `codegraph`/`codegraph-scope`/`codegraph-pin`） |
| `tests/test_codegraph_autodispatch.py`、`test_codegraph_brief.py`、`test_codegraph_build_prompt.py`、`test_codegraph_role.py`、`test_codegraph_subagent_prompt.py`、`test_understand_anything_pin.py`、`test_understand_anything_subagents.sh` | ✅ 7 个新测试文件，原样带入，扫描无机器路径/IP/内部代号 |

### PRD 里的脱敏

`docs/prd-jiuwenswarm-understand-anything-subagents.md` 一处引用了
研究时读源码用的本机路径：

- `/root/DevTeam/reference/jiuwenswarm` → `<workspace-root>/reference/jiuwenswarm`
  （沿用 §1 既有规则）

其余 7 个新 PRD 和全部新增代码扫描无 `/root/`、无 IP、无
`Robin`/`argentina`/`brazil`/`colombia`/`panama`/`vivo` 等既有代号——
这批工作是纯工具链功能开发（codegraph 角色本身），不涉及任何具体
客户项目复盘，天然干净。

### 自检

```
grep -rnE '(/root/DevTeam|/root/\.jiuwenswarm|/root/\.claude-|Robin\b|\
124\.81\.97\.217|110\.238\.103\.247|192\.168\.0\.212|binrogithub|\
panama|argentina|peru\b|brazil|colombia|vivo\b)' \
  bin/plan.py bin/report.py docs/prd-codegraph-*.md \
  docs/prd-jiuwenswarm-understand-anything-subagents.md \
  scripts/install-understand-anything.sh \
  supervisor/skills/workspace/codegraph/ install.sh config/ \
  tests/test_codegraph_*.py tests/test_understand_anything_*.* \
  tests/collapse/dt1_gates.sh
```

无匹配（`bin/plan.py`/`bin/report.py` 里既有的 `country-*`/`client-x`
替换词本身不含这些原词，不会误报）。

### 测试

`pytest tests/test_codegraph_autodispatch.py tests/test_codegraph_brief.py
tests/test_codegraph_build_prompt.py tests/test_codegraph_role.py
tests/test_codegraph_subagent_prompt.py tests/test_understand_anything_pin.py`：
全部 passed。全量回归 `pytest tests/ --ignore=tests/collapse`：
91 passed，无破坏（对照同步前的源仓库，也是 91 passed，一致）。

`tests/collapse/dt1_gates.sh` 在本目录跑会失败——但这是本目录截断版
git 历史（只有 2 个 commit，没有源仓库里 `v0.8.0` 等历史 tag）导致的
既有限制，同步前（缺 codegraph 子命令）和同步后（缺 tag 锚点）都会
失败，只是失败在脚本的不同检查点，跟本次同步内容本身的正确性无关。
