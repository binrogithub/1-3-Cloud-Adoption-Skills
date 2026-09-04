# PRD · codegraph 角色（结构先行的规划）

> 写代码之前先知道"这块代码谁在调、被谁依赖"——
> 而不是让 author 角色自己现读一圈现拼上下文。

- 目标仓库：`<workspace-root>`（本仓库自身，`bin/plan.py`）
- 关联调研：2026-09-04 外部检索（外部代码知识图谱工具的落地模式）
- 文档日期：2026-09-04
- 优先级：P1

---

## 01 问题

`SKILL.md` 路由表本身就有一条判据："reading-is-for-writing"——读一遍代码
只是为了写代码，这种读法成本高。今天系统没有为这条判据配任何工具：
author 角色要理解一段改动的影响面，只能自己 grep、自己多文件通读，读的
量随代码库增长而增长，而且每次都从零读。

外部实践已经收敛到同一套模式：本地预建一份代码结构图（函数/类/import/
调用链），维护成本低（增量更新，只有改动过的文件重新入图），查询成本
接近零；用在写代码之前的规划阶段，能显著降低之后的读文件次数和 token——
Meta 内部的类似实践测出来减少约 40% 的工具调用/token；外部开源代码图谱
工具测出来减少 47% token、58% 工具调用。这类工具现在都是
"本地预索引 + 通过某种协议查询"的形状，不依赖云端。

## 02 目标与非目标

**目标**

- 新增 `plan.py codegraph` 两个子命令：`build`（建/增量刷新本地图索引，
  确定性操作，不开会话）、`brief`（针对某个 change 的改动范围查图，产出
  一份结构化的"影响面简报"，这一步需要判断"哪些查询结果值得放进简报"，
  是真正的角色判断，走会话派发）。
- `brief` 复用 `plan.py` 现有的 jiuwenswarm 派发机制（跟 N1 validate 派发、
  N2 archive 派发、D1 SPECIFY 同一套 client 调用方式）——**不需要改
  jiuwenswarm 网关自己的代码**。核实过了：`jiuwenswarm` 是通用的多 agent
  路由/会话网关（IM、cron、routing 等），"validate 派发"「"archive 派发"
  这些名字是 `plan.py` 自己给会话喂的 prompt+规范化命令约束出来的效果，
  不是网关内置的专用 verb——所以新增一种"喂法"完全在 `plan.py` 自己的
  改动范围内。
- 产出物 `codegraph/impact-brief.md` 是给 author 角色读的输入，不是给人
  看的最终交付物——author 派发的 prompt 里追加一句"先读
  `codegraph/impact-brief.md`（如果存在）"。
- 适用性像 `design-scope` 一样机械判定：change 的目标文件里只要有一个是
  **已存在**的文件（不是纯新增文件），就算适用——纯新写的文件没有图可查。

**非目标**

- 不做可视化面板、不做跨仓库图谱、不做常驻 watcher（这版是"任务开始时
  build 一次，增量跳过没变的文件"，不是常驻进程盯着文件系统）。
- 不让 codegraph 的结论门禁合并——跟 design 状态一样，是可见信息，不是
  MERGE_GATE 的一部分。
- 不在这版做"多 change 共享同一份索引缓存"的优化——每个 change 各自
  build 一次，重复扫描未变化文件的成本由底层工具自己的增量哈希吸收
  （见 §04），不需要 `plan.py` 自己再做一层缓存管理。

## 03 不变式

- **INV-1** `codegraph build` 是确定性操作（解析文件生成图），不判断
  任何"对不对"，因此**不需要**走会话派发、不需要签名验证——这一点跟
  D0 SELECT（"millisecond, no session"）同类，区别于需要角色判断的
  `brief`。
- **INV-2** `codegraph/` 产出物不计入 `report.py deliver` 的
  `landed_files`/`landed_bytes`——它是规划期间的工作辅助材料，不是交付物
  （跟 `evidence/**` 同类，不是跟 `design/` 同类；design/ 的产出会真的
  出现在最终页面里，codegraph 的简报不会）。`config/collapsed.config.yaml`
  的 `product_excludes` 加一条 `codegraph/**`。
- **INV-3** 跟 phase-chain-automation 的 INV-3 对齐：下一阶段的
  `codegraph/impact-brief.md` 必须重新查图产出，不得从上一阶段复制——
  代码在阶段之间会变，旧简报可能已经过期。
- **INV-4** `brief` 的会话只能读图索引和该 change 记录在案的目标文件
  范围，不得读取图索引之外的任意路径——跟其他角色派发一样，边界由
  `plan.py` 传给会话的规范化参数决定，不是会话自己决定读多少。
- **INV-5** 没有调用过 `plan.py codegraph build/brief` 的既有任务，行为
  与今天完全一致——纯增量，`author` 派发的 prompt 只是"如果这个文件
  存在就读"，文件不存在时行为不变。

## 04 目标架构

**索引工具**：不自己造轮子，钉一个现成的本地代码图谱工具（同类选型均为
tree-sitter 或等价静态解析 + 本地图数据库，增量哈希更新，无需联网）。钉法参照已有先例
`scripts/install-opendesign.sh` 那一套——固定 tag/sha，`.aidlc-pin.json`
记整棵树的摘要，operator 一次性安装到固定路径（如 `/opt/codegraph`），
CC 侧只读挂载。选型和落地细节留给实施时决定，本 PRD 不点名版本号。

**`plan.py codegraph build --repo <repo>`**：调用钉好的工具对 `<repo>`
做（增量）索引，索引本身存在图工具自己的本地存储里（不进 git，跟
`.ai-dlc/**` 一样在 `product_excludes`）。纯本地操作，`plan.py` 只是
transparently 转发调用并检查退出码。

**`plan.py codegraph brief --change <id> --repo <repo>`**：
1. 读该 change 记录在案的目标文件范围（跟 `route_check` 读的是同一个
   来源——git diff 出来的改动文件列表）。
2. 对索引发起若干条查询（谁调用了这些文件里的符号、这些文件依赖谁、
   有没有跨模块的隐藏耦合）。
3. 把查询结果连同 change 的目标范围一起喂给一个新会话（复用 N1/N2 同款
   jiuwenswarm client 调用方式），让它把原始查询结果收拢成一份给人/给
   author 角色读的简报——这一步判断"哪些边值得写进去、哪些是噪音"，
   是需要角色判断的地方，产出 `codegraph/impact-brief.md`。
4. 写一条事件到该任务的 `events.jsonl`（`CODEGRAPH_BRIEF_WRITTEN`），
   人类可见。

**接入点**：`author` 派发（`plan.py` 现有的角色派发逻辑）的 prompt 模板
追加一句——若 `codegraph/impact-brief.md` 存在，先读它再动笔。这是纯
prompt 层面的追加，不改变 author 派发本身的机制。

**流程位置**：`INIT → ROUTE → CODEGRAPH（新，仅 planned 且适用时）→
WORK(author 派发 + 实现) → DESIGN → CHECK → REPORT → MERGE_GATE`。
CODEGRAPH 挂在 WORK 最前面，跟 DESIGN 的 D0 SELECT 一样是"先机械判定
适不适用，适用才跑"。

## 05 与既有流程的边界

- 跟 `report.py deliver` 的 design 自动派发是两个独立的判定，互不影响：
  design 看 surface 文件（web/deck），codegraph 看"改动是否触达已存在
  文件"，两者可能同时适用、也可能只有一个适用。
- 跟 phase-chain-automation 的 `plan.py initiative advance` 不冲突——
  `advance` 只建任务骨架（INIT 状态），不触发 WORK，自然也不触发
  CODEGRAPH；CODEGRAPH 是新阶段自己进入 WORK 时才会跑，产出天然是这个
  新阶段自己的，不会继承上一阶段（对齐 INV-3）。
- 跟 openspec 分叉的教训对齐（INV-7，phase-chain-automation PRD 里记的
  那次违反）：`brief` 会话产出的 `impact-brief.md` 是**产品文件**，直接
  写进调用者仓库的 `codegraph/` 目录（不是写进 plane 的权威副本），因为
  它不是 openspec 内容、不受 plane 迁树规则约束——这条本 PRD 需要在实施
  时明确写进代码注释，避免以后有人套用 openspec 那套"迁到 plane"的
  惯性做法。

## 06 数据契约

`codegraph/impact-brief.md`（产品辅助文件，不计入 landed_files）：

```markdown
# Codegraph impact brief — <change-id>

## Scope queried
<change 的目标文件列表>

## Callers
<谁调用了这次改动涉及的符号，按文件分组>

## Callees / dependencies
<这次改动涉及的代码依赖谁>

## Cross-module coupling flagged
<查询过程中发现的、值得 author 注意的隐藏耦合，没有就写"none found">
```

## 07 反向门（不该触发的时候）

- 目标文件全是新文件（没有一个已存在）→ `codegraph-scope` 判不适用，
  不触发 `build`/`brief`，不留空产出物。
- `codegraph build` 失败（工具不可用、索引损坏）→ `brief` 直接跳过，
  在 events.jsonl 记一条 `CODEGRAPH_UNAVAILABLE`，author 派发照常进行，
  只是拿不到简报——不阻塞任务。
- route 是 inline（不是 planned）→ 不触发，inline 任务量太小，查图收益
  低于开销。

## 08 分期

| Phase | 内容 | 风险 |
|---|---|---|
| A | 钉好本地图谱工具（安装脚本）+ `plan.py codegraph build` + `codegraph-scope` 适用性判定，纯确定性、无会话派发 | 低 |
| B | `plan.py codegraph brief` 会话派发 + 接入 author 派发 prompt + `product_excludes` 加规则 | 中——碰到 author 派发的 prompt 模板，需要回归验证 author 产出不受影响 |
| C（可选） | 跨 change 共享索引缓存优化 | 低，纯性能，不改行为 |

本 PRD 覆盖 Phase A + Phase B 的规格；C 留给用量上来之后再评估要不要做。

## 09 风险与残余

- 图谱工具本身的解析准确性依赖它对语言的支持程度（多语言项目里，某些
  语言可能没有对应的 tree-sitter 语法支持）——`codegraph build` 失败时
  的降级路径（§07 反向门）兜住这个风险，不是本 PRD 要解决的问题。
- `brief` 会话的"哪些边值得写进简报"这一步本质是摘要生成，摘要质量
  没有机器判据——这是本项目一贯的立场（design/spec 的正确性也不用机器
  判），交给读简报的 author 角色和最终读 diff 的人自己判断简报有没有
  用，用不上就当没有。

## 10 回滚

纯新增：一个 pinned 外部工具的安装脚本、`plan.py codegraph` 两个子命令、
一段 author prompt 追加、`product_excludes` 一条新规则。删除这几处、或者
干脆不装这个图谱工具，行为回到今天——`codegraph/impact-brief.md` 不存在
时 author 派发的 prompt 分支本来就是"跳过这步"，不会报错。
