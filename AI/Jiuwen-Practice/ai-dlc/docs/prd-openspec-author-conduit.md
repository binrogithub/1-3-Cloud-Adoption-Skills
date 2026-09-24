# PRD · openspec-author 通道补齐 + doctor 的网关技能盲区

> containment N1 禁止编排会话直接调用 openspec CLI，plane 侧则通过
> `openspec-author` 技能获得授权去调用它。但这个技能**在本仓库从未存在
> 过**——于是编排侧被规则禁止、plane 侧没有通道，实际发生的唯一事情就是
> 编排会话凭记忆手写 artifact。规则被违反不是因为它存在，而是因为通道缺失。

- 目标仓库：`<workspace-root>`（`supervisor/skills/workspace/`、`install.sh`）
- 关联：`docs/prd-phase-chain-automation.md`（INV-7 自陈曾亲手违反 containment）、
  `docs/prd-route-selfcheck-and-intent-menu.md`（G2 的健康自检，本 PRD 的 G2 是
  它在网关侧的对应物）、`SKILL.md` 的 containment N1
- 触发来源：一次针对 ai-dlc 自身的端到端评估（跑全量 48 个 collapse 门禁 +
  通读 dispatch 路径）
- 文档日期：2026-09-05 · 优先级：P0 · 目标版本：v0.23.0

---

## 01 问题

`plan.py` 的 planned route 撰写路径把 `openspec-author` 技能当作**派发的
前置条件**——`cmd_dispatch`（2483）和 `cmd_phase`（5024）在客户端存在之前
就检查 `authoring_skill_state()`，不通过则以 `EXIT_SKILL_MISSING` 拒绝。

这个技能在本仓库不存在，任何地方都不存在：

| 查证 | 结果 |
|---|---|
| `grep openspec-author install.sh` | 无——安装器从不部署它 |
| `supervisor/skills/workspace/` | 只有 `codegraph`、`ui-designer` |
| 全盘 `find / -name 'openspec-author*'` | 无 |
| 网关 workspace 的 `skills_state.json` | 注册了 skill-creator、swarmskill-creator、codegraph、ui-designer——没有它 |

**直接后果**：planned route 里"由角色撰写 change artifact"这半条流程在任何
机器上都无法派发。实测 48 个 collapse 门禁中 18 个红，其中约 7 个
（`d4_reverse_cases`、`rs3_concurrency`、`l3_resume`、`dr_review_round`、
`rs2_timing`、`rs4_decide`、`dm_measure_work`）报的是同一句
`"stopped": "before dispatch — the client was never invoked"`。在补齐工作
开始前的 commit 上复跑，同样全红——是既有状态，不是新引入的回归。

**二次后果，更严重**：containment N1 禁止编排会话直接跑 openspec CLI；
plane 侧又没有通道；于是真实发生的唯一事情是编排会话凭记忆手写 artifact。
`docs/prd-phase-chain-automation.md` 的 INV-7 已经自陈过一次
（"本轮工作亲手违反过一次……结果发现仓库本地的 openspec 树和 plane 内部
权威副本早已分叉"），本 PRD 的撰写会话同样是手写的。**这条规则正在被系统性
违反，根因是通道缺失而非纪律松懈。**

**为什么潜伏这么久**：`install.sh --doctor` 的 workspace 校验硬编码只统计
`ui-designer` 一个技能（install.sh:259 `x.get('name')=='ui-designer'`），
所以 `openspec-author` 缺失时 doctor 依然输出 `All checks passed`、退出码
0。健康检查看不见的缺失，等于不存在的缺失。

## 02 调研结论

- **设计前提成立**：`openspec instructions [artifact] --change <id> --json`
  在 openspec 1.10.0 中真实存在（命令表：`Output enriched instructions for
  artifacts, apply, or archive`）。role prompt 依赖的契约没有落空。
- **名字对得上**：默认 schema `spec-driven` 的 artifact 为
  `proposal → specs → design → tasks`；ai-dlc 侧 `ARTIFACT_BASENAMES`
  覆盖 proposal/design/tasks，`specs` 由 `plan.py:5305-5313` 的路径映射
  处理（`specs/**` 与 `spec.md` → `art="specs"`）。四个 artifact 全部对齐，
  通道可做成通用的，不需要按 artifact 分支。
- **角色集合的唯一来源是 plane 侧签名 graph**（`cmd_roles`:438-442：
  "The ONLY source of the role set… the schema is never queried
  caller-side"）——这条既有姿态决定了本 PRD 的 schema 处理方式（见 §03 非目标）。
- **判据很轻**：`authoring_skill_state()`（1213）只检查两件事——
  `<workspace>/openspec-author/SKILL.md` 存在，且 `skills_state.json` 的
  `installed_plugins` 里有同名条目。
- **install.sh 不需要改部署逻辑**：`install_workspace_skills()`（941）已经
  遍历 `supervisor/skills/workspace/*/` 全量部署 + 注册 + read-back 断言。
  新增一个目录即被自动接管——这是本 PRD 改动面能这么小的原因。
- **纪律已有单一承担者**：role prompt（552-572）已写明"只写自己的
  artifact""不许自己跑 validate""拿不到 CLI 就打 `CLI_UNAVAILABLE_MARKER`
  停手，不许凭记忆编造"，并明确 *"That guidance is deliberately NOT copied
  into this prompt"*——指南必须来自 CLI，不来自 prompt，也不来自模型记忆。

## 03 目标与非目标

**目标**

- **G1**：新增 `supervisor/skills/workspace/openspec-author/SKILL.md`，
  一个**极薄的纯通道**：告诉会话去跑
  `openspec instructions <artifact> --change <id> --json`，并照它返回的
  instruction、template、output path 执行。不承担纪律。
- **G2**：`install.sh --doctor` 的 workspace 校验改为**以
  `supervisor/skills/workspace/` 的实际内容为准**逐个校验注册状态，
  取代当前硬编码的单一 `ui-designer` 判断。

**非目标**

- 不在 skill 里复述任何纪律条款（决策：极薄纯通道）。纪律的唯一真相源是
  role prompt——两处写同一件事必然长期漂移，这个代码库在 INV 里反复强调过
  单一真相源。
- 不传 `--schema`（决策：靠 openspec 自 `config.yaml` 自动探测），保持
  `cmd_roles` 既有的"从不在 caller 侧查询 schema"姿态。
- 不修改 `authoring_skill_state()` 的判据、不修改
  `install_workspace_skills()` 的部署机制、不修改 role prompt。
- 不碰 `validate` / `archive` 路径——实测证明它们不依赖这个技能（本次评估
  中两者在技能缺失的情况下均正常完成，含一次真实的签名 verdict 和一次完整
  的归档 dispatch）。
- **不自我安装、不自我注册**——沿用既有的 E6/N4 立场：nothing installs
  itself, nothing edits the gateway's configuration。技能由安装器部署，
  不由运行期的会话部署。
- 不承诺角色产出的 artifact 质量。本 PRD 只负责打通通道。

## 04 不变式

延续既有编号（最近一次落地于 `docs/prd-route-selfcheck-and-intent-menu.md`
的 INV-20～25），从 INV-26 继续：

- **INV-26**：conduit 只做一件事——让会话取得 openspec CLI 的指令并照做。
  skill 正文中出现与 role prompt 重复的纪律条款，视为回归而非加固。
- **INV-27**：conduit 不传 `--schema`。若 artifact 名与当前 schema 错位，
  角色按既有的 `CLI_UNAVAILABLE_MARKER` 协议停手并如实说明，**绝不允许
  降级为"换个名字再试"或凭记忆编造**——fail-closed 是这条路径既有的、
  且被 role prompt 明文要求的行为。
- **INV-28**：doctor 的 workspace 校验以交付内容为准（`supervisor/skills/
  workspace/` 里有什么就校验什么），不得再出现硬编码的技能名单。
- **INV-29**：doctor 发现某个已交付的 workspace 技能未安装或未注册时，
  报为**失败**（`--doctor` 退出码 1），而不是 advisory。理由：这与
  `plan.py next` 的 G2 advisory 不同——那条不阻塞是因为工具链缺失只影响
  单次任务的建议质量；而网关技能缺失会让**一整条路线静默不可用**，正是
  本 PRD 要消除的失效模式，不能再让它以"通过"的面目出现。
- **INV-30**：注册读回断言沿用 install 侧既有标准——同名技能的条目数必须
  恰好为 1，多于一条报失败，不静默去重。

## 05 目标架构

**G1 — `supervisor/skills/workspace/openspec-author/SKILL.md`**

结构对齐既有的 `codegraph`/`ui-designer`（YAML frontmatter `name` +
`description`，正文 markdown）：

- `name: openspec-author`
- `description`：说明这是角色获取 artifact 撰写指令的通道，由
  `plan.py dispatch`/`phase` 派发的角色调用。
- 正文只讲三件事：
  1. **你是谁**——你正在撰写某一个 change artifact，指令不在 prompt 里。
  2. **跑什么**——`openspec instructions <artifact> --change <id> --json`
     （artifact 与 change id 由派发的 prompt 给出），照返回的
     instruction / template / output path 执行，输出写到它报告的路径。
  3. **拿不到怎么办**——不改写、不猜测、不凭记忆编造；按派发 prompt 里
     既有的停手协议执行（此处只**指向**该协议，不复述其内容，见 INV-26）。

部署与注册**零改动**：`install_workspace_skills()` 的既有循环会自动
部署、注册、read-back 断言、写进安装清单。

**G2 — `install.sh` 的 doctor workspace 校验**

把现有的单一硬编码判断（256-267 附近）改为：遍历 `${WS_SKILLS_DIR}/*/`
得到"本次交付应当装好的技能"列表，逐个在网关的 `skills_state.json` 里
校验注册条目数恰好为 1，并校验目标目录下 `SKILL.md` 存在。任一不满足
即 `fail` 并点名技能与路径（INV-28/29/30）。

## 06 反向门

- `supervisor/skills/workspace/` 下有目录但缺 `SKILL.md` → doctor 报失败
  并点名（与 install 侧既有 read-back 断言同一标准）。
- 网关 `skills_state.json` 不存在 → 保持既有 `warn` 行为，不改为失败
  （这是"网关尚未初始化"，与"技能漏装"是不同的情况）。
- 同名技能注册了多条 → 报失败，不静默去重（INV-30）。
- 用户自己在网关里另装了 ai-dlc 不交付的技能 → 不管、不报、不删；本 PRD
  只校验 ai-dlc 自己交付的那些。
- openspec CLI 在会话内不可用（网络、版本、change 不存在）→ 不属于本 PRD
  的路径；角色按 role prompt 既有协议停手。

## 07 验收

- **单元**：`authoring_skill_state()` 在技能装好后返回 `ok: true`；
  反注册（从 `skills_state.json` 删条目但保留文件）后返回
  `installed: true, registered: false, ok: false`。
- **doctor**：故意反注册 `openspec-author`，确认 `--doctor` 退出码为 1
  且输出点名了该技能；恢复后退出码回到 0。
- **端到端（关键，依赖真实网关）**：装好后跑一次真实的 planned route 角色
  派发，确认：① 不再是 `"stopped": "before dispatch"`；② evidence frames
  的 `commands_seen` 里确实出现 `openspec instructions <artifact> …`——
  即角色真的是从 CLI 取的指令，而不是凭记忆写的。**这一条是本 PRD 成立与否
  的判据**，仅靠 `ok: true` 不足以证明通道真的通了。
- **门禁回归**：跑全量 48 个 collapse 门禁，记录补齐前后对比。预期那 ~7 个
  同根因门禁转绿；其余红项属另外两个独立根因（见 §08），不在本 PRD 范围。

## 08 风险与残余

- **门禁不会全绿**。18 个红门禁有三个独立根因，本 PRD 只解决其中一个：
  另外两个是 plane 根目录的 git `dubious ownership`（`swarm:swarm 0750`
  与调用方身份不符，影响 `d3_plan_boundary`、`l7_sweep`、
  `l7_target_safety`、`open_plane`——其中 `open_plane` 会静默降级为
  `"boundary": "unknown"`，安全相关）、以及回滚锚点 tag 在本仓库根本不存在
  （`dt1_gates`，本库是重新发布的，pre-history 与 tag 留在原库）。各自单独
  立项。
- 通道打通后，角色能否产出合格 artifact 取决于 `openspec instructions`
  的模板质量与模型能力——本 PRD 不对产出质量做承诺，只对"指令来自 CLI
  而非模型记忆"这一属性负责。
- 若某仓库的 `config.yaml` 换掉了 schema，artifact 名可能与 graph 给的
  角色名错位。按 INV-27，这会表现为角色 fail-closed 停手（可诊断），
  而不是产出错误的 artifact（不可诊断）。这是有意的取舍。

## 09 回滚

纯新增：一个技能目录 + doctor 里一段循环替换掉一处硬编码判断。删除该目录、
把 doctor 那段改回原样即回到今天；`install.sh --uninstall` 的既有逻辑已经
覆盖 workspace 技能的反注册，无需额外回滚路径。
