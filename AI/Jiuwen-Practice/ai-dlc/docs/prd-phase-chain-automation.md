# PRD · 阶段自动衔接（phase-chain-automation）

> 一个 change 交付完只是一个阶段完成，不是整件事完成——
> 但今天系统里没有任何东西记得「这属于哪件事的第几阶段」。

- 目标仓库：`<workspace-root>`
- 关联讨论：一次围绕 `<client-project>` 上 ai-dlc + Claude-MaaS 使用记录的
  复盘会话
- 测量日期：2026-09-03 · `<host-ip>:8443`，项目 `<client-project>`
- 回滚锚点：本轮开工前打 tag（本仓库当前 HEAD `790d83c`）

---

## 01 问题

在 `<client-project>` 上，`openspec/changes/openjiuwen-efficiency-v1/proposal.md`
把一次运行时优化拆成三个阶段：

```
Phase 1 (Low risk):    incremental-token-counting, checkpoint-optimization
Phase 2 (Medium risk): message-queue-parallelism, task-loop-prefetch
Phase 3 (Medium risk): llm-batch-and-retrieval-cache
```

这份文档写得很清楚——**但它只是文字**。`.ai-dlc/tasks/` 里没有任何字段
记录「这个 change 是某个 initiative 的第几阶段」「上一阶段合并之后该轮到
谁」。`plan.py` 的 26 个子命令里，`phase` 指的是单个 change 内部并发派发
角色（author/reviewer 那一层），和 proposal.md 里的「Phase 1/2/3」是两个
不相关的概念，只是撞了名字。

同一台机器上另一条记录（`.ai-dlc/tasks/frontend-design-tokens`）展示了
「无人衔接」的另一种后果：一个 inline 任务因为没人跑 `plan.py validate`，
`stage` 停在 `FAILED`、`human_state: "Needs your decision"`，`report.py
deliver` 已经把 remedy 印在报告里，但没有任何东西把这条 remedy 送到人面前。
单个任务尚且如此，跨阶段的衔接就更没有着落——Phase 1 合并之后，
Phase 2 的任务连"该被创建"这件事都不会自动发生。

## 02 目标与非目标

**目标**

- Phase N 的 change 通过 MERGE_GATE（有 rationale 的批准）合并、归档之后，
  自动创建 Phase N+1 的任务骨架——**仅 INIT，不更多**。
- 人始终持有下一阶段真正开工、验收、合并的每一个闸门；自动化只负责
  "把下一张卡片摆到桌上"，不负责打开它。
- 新阶段任务从空白状态开始：不得继承上一阶段的 `planning.json`／
  `design_decision`／任何判断结果。
- 未注册 initiative 的任务（今天绝大多数任务，包括 client-x-maas-launch、
  panama-tourism 这类单阶段网站项目）行为与今天完全一致——这是纯增量，
  不改动任何现有代码路径的默认行为。

**非目标**

- 不做跨阶段的自动排期、资源调度或并发限速。
- 不做失败阶段的自动重试、自动跳过或自动降级到别的阶段。
- 这一版不做可视化面板；只做数据契约 + 一个查询命令 + 一个挂钩点。
- 不判断"这个 initiative 该不该继续"——那永远是人的判断，本 PRD 只负责
  让"继续"这件事从"没人记得"变成"骨架已经摆好，等人开工"。

## 03 不变式

这些是本功能自己的硬约束，直接对齐 `SKILL.md` L2 的既有硬性禁令
（尤其是"Never merge without approved rationale"和"Never automatically
re-dispatch a run stopped by an interrupt"两条）：

- **INV-1** 自动创建的下一阶段任务永远停在 INIT 之后、ROUTE 判断产生的
  最小状态；自动化本身绝不触发 WORK、绝不调用
  `report.py deliver`、绝不调用 `report.py gate --request`。
- **INV-2** 只有当上一阶段的 MERGE_GATE 记录着"带 rationale 的批准"
  （即 `plan.py close` 成功跑完合并+归档）时才触发；`close` 因为没有
  approval 而未执行、或 archive 命令非零退出时，一律不触发。
- **INV-3** 新阶段任务的 `planning.json`／`design_decision`／任何状态
  字段必须来自与手动 `report.py init` 完全相同的代码路径——不得复制、
  不得预填上一阶段的任何判断。
- **INV-4** 触发下一阶段失败（比如目标目录不可写、change id 冲突）
  绝不影响、绝不回滚已经成功关闭的上一阶段记录；失败是可见的、可人工
  重试的独立事件。
- **INV-5** 一个 change id 只能属于一个 initiative 的一个阶段；试图把
  同一个 change id 注册进第二个 initiative，或注册进已存在的任务 id，
  一律拒绝，不静默覆盖。
- **INV-6** 没有注册进任何 initiative 的任务，`plan.py close` 的行为
  与今天字节级一致——这条不变式是本功能能不能合入的前提，不是附带承诺。
- **INV-7** SPEC/PRD 一类 openspec 产物的产出与校验，一律经由
  `openjiuwen` 派发到 plane 侧完成；orchestrating session（含
  `plan.py initiative` 自己）绝不直接调用 `openspec` CLI 去产出或校验
  内容。这不是新原则，是 `SKILL.md` "containment N1"（"you never run
  it, and it is invisible to you"）本来就有的边界，本 PRD 把它显式列
  出来是因为**本轮工作亲手违反过一次**：为了赶产出，先在仓库本地手写
  markdown，又直接跑了一遍 `openspec validate phase-chain-automation
  --strict` 当"预检"，结果发现仓库本地的 `openspec/` 树和 plane 内部
  权威副本早已分叉——本地有 plane 没有的 change，plane 有本地没有的
  change，`plan.py validate` 两次拿到一模一样的 `unknown_item` 报错，
  因为它读的从来不是我手写的那份。这个分叉正是绕开 openjiuwen、自己
  手动碰 openspec CLI 的直接后果。`plan.py initiative
  register/advance` 只读写 `.ai-dlc/initiatives/*.json` 和调用
  `report.py init` 的既有函数，本身不涉及 openspec 内容，天然合规；
  这条不变式是防止未来有人"顺手"在这两个命令里加一行直接调 openspec
  CLI 的捷径。

## 04 目标架构

**新增数据契约**：`.ai-dlc/initiatives/<initiative-id>.json`，见 §08。
由撰写多阶段 proposal 的人（或 planning 角色）在 WORK 阶段随 proposal.md
一起创建——本质上是把 proposal.md 里"Phase 1/2/3"那张表格，多存一份
机器可读的版本。

**新增命令**：`plan.py initiative`
- `plan.py initiative register --initiative <id> --repo <repo> --phases <change_id>[,<change_id>...]`
  ——从一批已知的 change id 建立/更新 manifest，phase 顺序即参数顺序。
- `plan.py initiative advance --change <closed-change-id> --repo <repo>`
  ——在某个 change 的 `plan.py close` 成功之后调用：读 manifest，把
  `<closed-change-id>` 标记为 `delivered`；若存在状态为 `pending` 的
  下一阶段，对它调用与手动 `report.py init` 完全相同的初始化函数
  （复用，不 fork 一份新逻辑），标记为 `queued`；若没有下一阶段，把
  整个 initiative 标记为 `complete`。产生一条
  `INITIATIVE_PHASE_QUEUED` / `INITIATIVE_COMPLETE` 事件写进调用者
  仓库的 `events.jsonl`，人类可见。
- `plan.py initiative status --initiative <id> --repo <repo>`
  ——只读，打印各阶段当前状态，供人核对。

**挂钩点**：`plan.py close` 现有的"merge → archive → cleanup"尾部之后，
新增一步——查该 change_id 是否出现在某个 initiative manifest 里；如果
有，调用上面的 `advance` 逻辑；这一步严格在归档成功**之后**，且失败不
影响已经写盘的归档结果（对齐 INV-4）。

## 05 与既有流程的边界（回应"会不会影响网站开发流程"）

`report.py deliver` 的 design 自动派发（D0→D1→D3）挂在单个 change 自己的
surface 文件上触发，和 initiative 是两个不相关的层——本功能不修改
`report.py deliver`、不修改 `plan.py design`、不修改
`config/collapsed.config.yaml` 里的 `planning_threshold_files`。任何
没有调用过 `plan.py initiative register` 的 change（包括所有已存在的
网站类任务）永远查不到自己在哪个 manifest 里，`advance` 对它们是纯
no-op。

## 06 数据契约

```json
{
  "initiative_id": "openjiuwen-efficiency-v1",
  "title": "openjiuwen agent-core efficiency optimization",
  "created_by": "robin",
  "created_at": "2026-09-03T12:00:00Z",
  "phases": [
    {"seq": 1, "change_id": "openjiuwen-efficiency-v1-phase1", "status": "delivered"},
    {"seq": 2, "change_id": "openjiuwen-efficiency-v1-phase2", "status": "queued"},
    {"seq": 3, "change_id": "openjiuwen-efficiency-v1-phase3", "status": "pending"}
  ]
}
```

`status` 只有四态：`pending`（还没被创建）、`queued`（`report.py init`
已跑过，等人开工）、`delivered`（该阶段已合并归档）、`blocked`（人工标记
——比如 Phase 2 出问题，暂停整个 initiative，不再自动 advance 到
Phase 3；这是唯一允许人工写入的状态，automation 从不写 `blocked`）。

## 07 反向门（不该触发的时候）

- `close` 因为无 approval 未执行 → 不触发。
- `close` 里 archive 命令非零退出 → 不触发，阶段状态保持不变，等人重试
  `plan.py close`。
- 目标 change id 已存在同名任务 → 拒绝创建，报错给人，不覆盖、不静默
  跳到下一个阶段。
- initiative 状态为 `blocked` → 不触发，即使下一阶段是 `pending`。

## 08 分期（本功能自己的交付分期）

| Phase | 内容 | 风险 |
|---|---|---|
| A | 数据契约 + `plan.py initiative register/status`（只读/手动，无自动触发） | 低 |
| B | `plan.py close` 尾部接入 `advance` 自动触发 | 中——改动了既有 `close` 的尾部，需要 INV-6 的回归验证 |
| C（可选） | 跨 initiative 的汇总视图 | 低，纯查询 |

本 PRD + SPEC 覆盖 Phase A 的规格；B、C 留待各自的 change。

## 09 风险与残余

- 一个 change 理论上可能想属于两个 initiative（比如既是效率优化的一部分，
  又是季度路线图的一部分）——v1 用 INV-5 直接拒绝双重注册，把这个场景推
  回给人用两个不同粒度的 initiative 描述。
- 本版不处理"某阶段失败/被否决后，剩余阶段要不要继续"——`blocked` 状态
  只是让人手动摁停，是否恢复、是否跳过，都是人的判断，不在自动化范围内。

## 10 回滚

纯新增：一个数据目录（`.ai-dlc/initiatives/`）、一个新子命令
（`plan.py initiative`）、`plan.py close` 尾部一段可选调用。删除这三样、
或者干脆不注册任何 initiative，行为回到今天。不改动任何既有任务的历史
记录。
