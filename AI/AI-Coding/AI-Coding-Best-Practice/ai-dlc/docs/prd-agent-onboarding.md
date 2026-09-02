# PRD · 让 agent 快速学会用 ai-dlc（agent-onboarding）

> 今天一个 agent 要用 ai-dlc，得在 283 KB 的入口面里自己找路，
> 然后在任务中途靠 `--help` 摸索命令。
> 本轮把「读文档才会用」换成「问系统下一步」。

- 目标仓库：`<repo-path>`
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：开工前打 `v0.19.x-pre-onboarding`（**先打 tag 再动手**）

---

## 01 问题

### 入口面 283 KB，其中 92% 是 agent 不该读的

```
supervisor/skills/claude/ai-dlc/SKILL.md       11,859 B   ← 唯一的 playbook
supervisor/skills/claude/ai-dlc-doctor/SKILL.md    729 B
supervisor/skills/workspace/ui-designer/SKILL.md 1,852 B
README.md                                       6,144 B
CHANGELOG.md                                  103,526 B   ← 给人看的
docs/*.md（8 份 PRD + 2 份记录）              158,811 B   ← 给人看的
                                              ─────────
                                              282,921 B
```

`CHANGELOG.md` + `docs/` = 262 KB = **92.6%**，是历史与设计论证，
agent 读了只会被淹没。但**没有任何一处告诉它「别读这些」**。

### 命令面 26 个子命令，playbook 只讲 6 步

```
plan.py    21 个：roles validate graph status prompt dispatch phase decide
                  review boundary accept close sweep classify stage snapshot
                  untouched migrate sandbox design design-scope design-pin
report.py   5 个：init deliver gate exception correct
```

playbook 的任务流是 `1·WORK → 1b·REVIEW → 1c·DESIGN → 2·CHECK → 3·REPORT → 4·MERGE_GATE`
——**六步，对 26 个子命令**。差额靠 agent 自己补。

### agent 确实在任务中途摸索（实测）

| 会话 | 总命令数 | 其中 `--help` | 摸索的对象 |
|---|---|---|---|
| 巴拿马编排（claude-maas） | 104 | **5** | `report.py init/exception/gate --help`、`plan.py close --help` |
| client-x 编排（claude-maas） | 14 | **3** | `report.py --help`、`report.py init --help`、`plan.py dispatch --help` |

外加 2 条 grep 文档的命令（`grep -n 'design\|ui-designer' …SKILL.md`）——
**agent 在跑任务的过程中，回头去读自己的说明书。**

### 走错的都是「说明书没说」，不是「模型不听话」

- **巴拿马自签路由例外**：`gate-route.answer.json` 的 `author: "AI-DLC Executor"`。
  playbook 里**从没写过「例外必须由人签」**——直到 `c58e9f2` 才在代码里加了
  `stated_actor()` 校验，playbook 至今没说。
- **巴拿马 `REPO` 路径写错**：命令里是 `<workspace-root>/country-d-tourism-8443`，
  真实仓库在 `/tmp/country-d-tourism-8443`。没有任何一步校验它。
- **design 一度不在流程里**：`1c · DESIGN` 是后来补的；在此之前 playbook 六步里没有它，
  于是没有任何一轮跑过 ui-designer。

### `description` 写成了设计说明，不是「何时用」

```yaml
name: ai-dlc
description: |
  The collapsed AI-DLC execution skill (v0.11.0): Claude Code IS the
  executor. It reads, writes, and runs tests itself, inside a per-task
  worktree. No machine judges the artifact: strict spec validation is
  the plan criterion, read as the plane's SIGNED verdict and never as
  a tool this executor runs — openspec is invisible to Claude Code
  (containment) — the human reading the deliverable is the correctness
  judge, and a human holds the merge gate. …
```

十二行架构论述。而 `description` 是**决定要不要用这个技能时读的那一句**。
对照同仓库的 `ui-designer`——一句话，说清了「是什么」和「何时用」。

### 结论

问题不是文档写得不好，是**入口的形状不对**：
它假设读者会从头读到尾，而 agent 是**按需查、边跑边查**的。
今天没有「按需查」的接口，所以它退化成了 `--help` 摸索。

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **U-A** | **冷启动 60 秒可用**：一个从未见过 ai-dlc 的 agent，只读 SKILL.md 的第一屏就能正确跑完一个最小任务 |
| **U-B** | **不必记命令**：任何时刻都能问系统「现在该做什么」，得到一条**可直接执行**的命令 |
| **U-C** | **每一次拒绝都自带出路**：非零退出必须携带一条可复制执行的补救命令 |
| **U-D** | **明确划出「别读什么」**：`CHANGELOG.md` 与 `docs/` 是给人的，agent 的读取路径里不出现 |
| **U-E** | **非 Claude 的 agent 也能用**：提供机器可读的能力契约，不依赖自然语言 playbook |
| **U-F** | **把已经踩过的坑写进说明书**：署名规则、仓库路径校验、design 那一步 |

### 非目标

- 不改任何 verb 的行为、退出码语义、判据。**本轮只改「怎么被理解」，不改「做什么」。**
- 不删 `CHANGELOG.md` 与 `docs/`——它们对人有价值，只是不该在 agent 的路径上。
- 不做交互式向导、不做 TUI。
- 不改合并门的人工判官地位。
- 不替 agent 做决定：`next` 只回答「下一步是什么」，不自动执行。

---

## 03 不变式

| ID | 不变式 |
|---|---|
| **V1** | **单一事实来源**：`next` 与 `--describe` 的内容**从代码推导**（argparse 与退出码常量），不是手写的第二份文档。手写的会漂移——`1c · DESIGN` 缺席那次就是漂移。 |
| **V2** | **`next` 只读不写**：不派发、不改状态、不建目录。它是一个查询。 |
| **V3** | **每个非零退出都带 `remedy`**，且 `remedy` 是一条**可直接执行的命令行**，不是一句描述。 |
| **V4** | **L0 层（第一屏）是自足的**：只靠它能跑通最小任务；不足之处必须由 `next` 补齐，而不是要求读者往下翻。 |
| **V5** | **不新增行为**：本轮不引入任何改变交付判定的代码路径。回归门守住。 |
| **V6** | **`next` 的建议必须与真实前置一致**：它说「可以跑 X」，跑 X 就不该因为前置不满足而被拒绝。**建议与拒绝同源。** |

---

## 04 实测约束

**E1 · `remedy` 已有先例，但覆盖不均。**
`grep -c remedy`：`bin/plan.py` **48 处**，`bin/report.py` **3 处**。
`design_skill_state()` / exit 24 / 25 / 26 的 remedy 是好范本
（"install the ui-designer skill into …, shipped as supervisor/skills/workspace/…"）。
**report 侧是缺口。**

**E2 · 退出码已经是结构化的。**
`plan.py` 有 20+ 个 `EXIT_*` 常量带行内注释（`EXIT_DESIGN_SURFACE = 24  # the measured
product surface carries no…`）。**`--describe` 的语料已经在代码里**，不需要新写。

**E3 · 没有 `next` / `describe` / `contract` 子命令。**
`plan.py --help` 里搜不到。`status` 是派发一个会话去问状态（要 `--change --repo --timeout`），
不是本地查询——**不能拿它冒充 `next`**。

**E4 · 任务状态已经是机器可读的。**
`state.json` 有 `stage` / `human_state` / `route` / `change_id`；
`planning.json` 有 `dispatches` / `design_auto` / `design_decision`；
`gates/*.json` 有门的请求与答复。**`next` 的输入齐备，不需要新增记账。**

**E5 · `install.sh --doctor` 讲的是环境健康，不是「怎么开始」。**
它检查 git/openspec/python/网关/技能源，**不回答「我现在该跑哪条命令」**。
两者互补，不要合并。

**E6 · 摸索基线可测。**
巴拿马 5/104、client-x 3/14。**这是本轮唯一有鉴别力的效果指标**——
不是「文档变好了」这种自评，而是**下一轮真实任务的 `--help` 次数**。

---

## 05 方案

### 一句话：把「读说明书」换成「问系统」

```
今天：  agent → 读 11.8 KB playbook → 记不住 26 个子命令 → 中途 --help 摸索
本轮：  agent → 读第一屏（~40 行）→ 任何时刻 `plan.py next` → 一条可执行的命令
```

### 三层入口

```
L0 · 第一屏（~40 行）      能跑通最小任务的最小集：
                           四步流程 + `next` 的用法 + 三条硬禁令
L1 · 完整任务流            现有的六步，保留
L2 · 边界与禁令            收容、署名规则、路径约定
```

**L0 必须自足（V4）**：读完它 + 会用 `next`，就能跑完一个任务。
L1/L2 是「想知道为什么」时才读的。

### `next` 是本轮的核心

```bash
$ plan.py next --task-dir <td> --repo <repo>
{
  "stage": "MERGE_GATE",
  "human_state": "Needs your decision",
  "blocked_on": "a person",
  "why": "the delivery report stands; the merge gate is unanswered",
  "do": "python3 bin/report.py gate --request --task-dir <td> --repo <repo>",
  "then": ["a person answers with --decision approve|request_changes --approver <name> --rationale <text>"],
  "not_yet": [
    {"verb": "close", "why": "no approval recorded", "exit_if_run": 11}
  ]
}
```

- `do` 是**一条可直接执行的命令**（U-B）
- `not_yet` 说明现在**不能**跑什么、跑了会得到哪个退出码——
  这直接消灭「试一下看看报什么错」这类摸索
- **只读（V2）**，且与真实前置同源（V6）

### `--describe`：给非 Claude 的 agent

```bash
$ plan.py --describe          # 或 report.py --describe
{"verbs": [{"name": "design", "purpose": "…", "requires": ["--change","--repo"],
            "preconditions": ["ui-designer installed", "pin verified",
                              "measured surface applicable"],
            "exits": {"24": "surface not applicable", "25": "skill missing",
                      "26": "pin mismatch"}}], …}
```

**从 argparse 与 `EXIT_*` 常量推导（V1/E2）**，不手写。

### 划出「别读什么」

L0 里一行显式声明：

> `CHANGELOG.md` 与 `docs/` 是给人读的历史与设计论证。
> 执行任务时不要读它们——你需要的一切在本文件和 `plan.py next` 里。

---

## 06 新增

| ID | 内容 |
|---|---|
| **N1** | **`plan.py next --task-dir --repo`**：读 `state.json` / `planning.json` / `gates/`，输出 `stage` / `blocked_on` / `why` / `do` / `then` / `not_yet`。只读（V2），前置判定复用各 verb 已有的前置函数（V6），不复制逻辑。 |
| **N2** | **`report.py next`**：同一形状，覆盖 `init/deliver/gate/exception/correct` 这一侧。两侧的 `next` 结果**互相不矛盾**（同一 task 状态只有一个「下一步」）。 |
| **N3** | **`--describe`（两个 executable）**：从 argparse 与 `EXIT_*` 常量推导的 JSON 能力契约（V1/U-E）。 |
| **N4** | **SKILL.md 重排为 L0/L1/L2**，L0 ≤ 40 行且自足（V4）；`description` 改为一句「是什么 + 何时用」，架构论述移入 L2。 |
| **N5** | **`remedy` 契约补齐**：`report.py` 的每个非零退出都带一条可执行 `remedy`（E1 的缺口）；已有的 48 处按「必须是命令行」校验一遍（V3）。 |
| **N6** | **把踩过的坑写进 L0/L2**：① 门的答复必须由人署名，模型不得签（`stated_actor()` 已在代码里，说明书里没有）；② `--repo` 必须是**存在的 git 仓库**，`next` 与 `deliver` 先校验后执行（巴拿马路径写错那次）；③ design 那一步及其「自动派发一次」的语义。 |
| **N7** | **「别读什么」声明**（U-D）：L0 一行，`README.md` 一行。 |
| **N8** | **`install.sh --quickstart`**：打印一段可复制的最小任务序列（init → work → deliver → gate → close），与 L0 同源，不是第二份文档。 |

---

## 07 反向门

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **W1** | **冷启动**：只把 L0（第一屏）交给一个不知道 ai-dlc 的 agent，让它跑一个最小任务 | 跑通，且 `--help` 次数 = 0 | **RED** — 今天 L0 不存在 |
| **W2** | **摸索基线**（U-B 的效果指标，E6）：下一轮真实任务的编排会话 | `--help` 次数 ≤ 1 | **RED** — 基线 5/104 与 3/14 |
| **W3** | 任务处于 6 个不同 stage，各跑 `next` | 每次都给出**一条可直接执行**的 `do` | **RED** |
| **W4** | **建议与拒绝同源（V6）**：对每个 stage，把 `next.do` 原样执行 | 不因前置不满足被拒 | **RED** — 这是 `next` 最容易腐烂的地方 |
| **W5** | 把 `not_yet` 里的 verb 原样执行 | 得到它预告的那个退出码 | **RED** |
| **W6** | `plan.py --describe` 与 `plan.py --help` 的子命令集合 | 完全一致（V1：同源，不会漂移） | **RED** |
| **W7** | 每个非零退出路径 | 都带 `remedy`，且 `remedy` 可直接执行 | **RED** — report.py 只有 3 处 |
| **W8** | `--repo` 指向不存在的路径（巴拿马那次的形状） | 立即拒绝并指出路径不存在 | **RED** — 今天静默继续 |
| **W9** | L0 行数 | ≤ 40 行 | **RED** |
| **W10** | **回归**：三套现有门禁 | 全绿，真实退出码 | **GREEN 回归门** — V5 的守卫 |

**W1 与 W2 缺一不可**：W1 是构造出来的冷启动，W2 是**真实任务上的效果**——
只有 W1 会让人误以为「文档写好了」。
**W4 是本轮最容易腐烂的一条**：`next` 一旦和真实前置分叉，就成了新的错误来源，
比没有 `next` 更糟。它必须复用前置函数，不能复制判断。

---

## 08 分期

| 期 | 内容 | 门 |
|---|---|---|
| **X0 · 探针** | 已完成：入口面 283 KB / 92.6% 非 agent 用；26 子命令 vs 6 步；摸索基线 5/104 与 3/14；三处走错的实证 | 四个事实进记录 |
| **X1 · next** | N1 + N2 | **W3** **W4** W5 |
| **X2 · 契约** | N3 + N5 + N6② | W6 **W7** **W8** |
| **X3 · 入口重排** | N4 + N6①③ + N7 + N8 | **W1** W9 |
| **X4 · 效果** | 不写代码：观察下一轮真实任务 | **W2** W10 |

X1 先做，因为它让 X3 可以变短——**有了 `next`，L0 才可能压到 40 行**。
反过来先写文档再做 `next`，文档会写成第二份说明书。

**X4 不是走过场**：W2 才是这轮有没有用的唯一证据。
X3 之后的第一轮真实任务，把编排会话的 `--help` 次数记进记录。

---

## 09 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | **`next` 与真实前置分叉**，成为新的错误来源 | V6 + W4：复用前置函数，不复制判断。**这是本轮唯一能把事情变得更糟的改动**，W4 必须逐 stage 跑。 |
| **R2** | **L0 压到 40 行导致丢失必要约束** | V4 要求 L0 自足，W1 用真实冷启动验；丢失的部分由 `next` 在运行时补，而不是靠读者往下翻。 |
| **R3** | **`--describe` 与 argparse 漂移** | V1 要求从 argparse 推导；W6 断言两者子命令集合一致。**残余**：`purpose`/`preconditions` 的文字仍是手写的，会漂移——只保证结构不漂移。 |
| **R4** | **W2 不可控**：真实任务的 `--help` 次数受任务复杂度影响 | 不做单点判定，看趋势；并记录任务规模一起对比。**接受这是软指标**，但它是唯一贴近目的的那个。 |
| **R5** | **「别读 docs/」被当成「docs/ 不重要」** | 措辞写清：**给人读的**，不是没用的。人做设计决策仍然要读。 |
| **R6** | **N6② 的路径校验误伤**：某些合法流程用尚不存在的路径 | 只校验 `--repo`（必须是存在的 git 仓库），不校验输出路径。**残余**：非 git 目录的合法用法会被拒——若真有，降级为告警。 |
| **R7** | 本轮不改行为，但改 SKILL.md 会改变模型的实际动作 | W10 回归门 + X4 观察。**残余**：playbook 的措辞变化对模型行为的影响无法用单元测试覆盖，只能靠真实轮次观察。 |

---

## 10 回滚

1. `git reset --hard v0.19.x-pre-onboarding`
2. `supervisor/skills/claude/ai-dlc/SKILL.md` 回滚后需**重新同步到部署位置**
   （`<cc-glm-config>/skills/`、`<cc-maas-config>/skills/`——见
   `docs/prd-install-targets.md` 的 K5：两份副本会分叉）
3. 无运行时状态变更，无记录变更，无配置变更

---

## 附注 · 与既有 PRD 的关系

- **`prd-install-targets.md`**：本轮改 SKILL.md，**必须走它的安装/一致性路径**，
  否则会重演「改了仓库那份，运行时读的是另一份」。
  N4 落地后应立刻跑 `--doctor` 的 K5 一致性检查。
- **`prd-design-required.md`**：N6③ 把设计门的语义写进 L0——
  代码里已经强制，说明书里至今没有。
- **`prd-deliver-measures-work.md`**：其 N2 的 `measured_ref` 应进入 `next` 的输出，
  让 agent 在合并门之前就看得见量的是哪个 ref。

---

*`docs/prd-agent-onboarding.md` · 测量日期 2026-09-01 · <host-ip>*
