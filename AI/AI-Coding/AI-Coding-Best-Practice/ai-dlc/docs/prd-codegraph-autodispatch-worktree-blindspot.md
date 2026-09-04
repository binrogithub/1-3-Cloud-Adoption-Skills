# PRD · codegraph 自动触发的 surface 检测漏扫 linked worktree

> 自动派发的判定链本身是对的——先记尝试、再派发、失败不阻塞，全部按
> `docs/prd-codegraph-author-autodispatch.md` 的设计跑通了。漏的是判
> 定链最前面那一步：它看的是错的目录。

- 目标仓库：`<workspace-root>`（`bin/report.py`）
- 关联：`docs/prd-codegraph-author-autodispatch.md`（本 PRD 修复其实
  施中的一个缺口，不改动其调度纪律/挂钩点设计）
- 文档日期：2026-09-04
- 优先级：P1（功能性 bug——标准流程下自动触发大概率永远不 due）

---

## 01 真实复现（这次在本机跑通的一次 live 验证发现的）

`docs/prd-codegraph-author-autodispatch.md` 合入后，第一次用真实的
`planned` 任务跑通全链路验证：`report.py init --route planned` 建了
一个任务，按 ai-dlc 标准流程 `git worktree add ../wt/<id> -b
task/<id>` 建了工作树，开发者的改动全部发生在这个 worktree 里
（`state.json.branch` 记的也是这个任务分支）。跑 `plan.py phase` 后，
`_maybe_auto_codegraph` 触发了 `codegraph_auto_due`，判定结果是
`(False, "surface_unmeasured")`——即使 worktree 里已经有真实的
未提交改动。

**只有当我把改动直接放到 `--repo` 传的那个主仓库路径本身（不是任务
worktree）时，`codegraph_auto_due` 才正确判定为 `due`。** 这证明：
问题不是"改动太小测不出来"，是 `codegraph_auto_due` 依赖的文件列表
函数根本没在看开发者实际工作的地方。

## 02 根因

`bin/report.py` 的 `_change_files_for_codegraph()`（`codegraph_auto_due`
唯一的输入来源）自己的 docstring 就写明了这是"kept minimal"版本：

```python
def _change_files_for_codegraph(repo, task_dir):
    """... This is the report.py-side equivalent of plan.py's
    change_surface — kept minimal because the full resolve_work_ref
    logic lives in plan.py (E4: report does not import plan). Reads
    base_sha from state.json, diffs base..HEAD, and adds uncommitted
    paths, applying excluded()."""
```

它只做了两件事：
1. `git diff base_sha..HEAD`（在 `repo` 自己身上）
2. `git status --porcelain -uall`（同样在 `repo` 自己身上）

对照 `bin/plan.py` 的 `change_surface()`（`cmd_codegraph_scope` 等既有
命令用的、已验证过的版本），后者在这两步之外还有一段 **W8：worktree
visibility**——`git worktree list --porcelain` 找出跟 `resolve_work_ref`
解出的分支绑定的 linked worktree，对那个 worktree 单独跑一次
`git_status_paths()`，把里面的未提交路径也并进 `files`。

`_change_files_for_codegraph` 没有这一段。ai-dlc 的标准任务流程
（`docs/prd-*` 和 L1 全流程文档里反复强调的"Worktree first"）就是
`git worktree add ../wt/<id> -b task/<id>`——开发者改动**默认就发生在
一个 linked worktree 里，不在 `--repo` 直接指向的主仓库路径**。所以：

- `git diff base_sha..HEAD`（在主仓库路径上）：主仓库的 HEAD 从建
  worktree 起就没动过（工作分支的提交在 worktree 那边），`base ==
  head`，这段查不到任何东西。
- `git status --porcelain -uall`（在主仓库路径上）：主仓库本身没有
  未提交改动（改动都在 worktree 里），这段也查不到任何东西。

两段都查不到 → `files` 是空列表 → `codegraph_surface` 的
`measured_files` 是 0 → `codegraph_auto_due` 返回
`(False, "surface_unmeasured")`——**不是"这个 change 确实没碰到已有
文件"，是"这个函数压根没看开发者实际改动的地方"**。

**已确认不是巧合**：`resolve_work_ref()` 已经有两份文本一致的拷贝
（`bin/plan.py` 一份、`bin/report.py` 一份，Z5 约定，`gate Y7`
——`tests/collapse/wr_work_ref.sh`——断言两份字段级一致）。`report.py`
里已经有正确解析任务分支的能力，`_change_files_for_codegraph` 只是没
调用它、也没做 W8 那段 worktree 扫描。

## 03 影响面

`codegraph_auto_due` 是 `codegraph_auto_dispatch` 唯一的判定入口，
挂在 `cmd_phase`/`cmd_dispatch` 最前面（`docs/prd-codegraph-author-
autodispatch.md` §03）。这个缺口意味着：**在 ai-dlc 标准的
worktree-first 流程下，codegraph brief 的自动触发实际上永远不会
due**——因为 `--repo` 传的几乎总是主仓库路径，改动几乎总是在 worktree
里。auto-dispatch 这个特性合入后在真实流程里是死代码，只有当
`--repo` 碰巧直接指向工作树本身（不是标准用法）时才会正常工作。

不影响：Phase B 手动触发（`plan.py codegraph brief` 单独跑，如果调用
者自己把 `--repo` 指向正确的工作树）；`cmd_codegraph_scope` 等既有
命令（它们用的是 `plan.py` 自己的 `change_surface`，本来就有 W8）。

## 04 目标架构

**只改一个函数**：`bin/report.py` 的 `_change_files_for_codegraph()`，
补上 W8 worktree 扫描这一段，跟 `bin/plan.py` 的 `change_surface()`
同构（复用已有的 `resolve_work_ref` report.py 拷贝，不新增第三份
逻辑）：

1. `head = resolve_work_ref(repo, state)` 拿到 `sha`（当前用的是直接
   `git rev-parse HEAD`，改成走 `resolve_work_ref` 解析出的真实工作
   ref——跟 `change_surface` 一致，任务分支存在时用任务分支的 HEAD，
   不是主仓库自己的 HEAD）。
2. diff 段：`base_sha..<resolve_work_ref 解出的 sha>`（而不是主仓库
   自己的 HEAD）——这一步顺带修另一个连带问题：即使 worktree 已经把
   改动**提交**到任务分支上了（还没合并），主仓库自己的 HEAD 也看
   不到那些提交，现在的 diff 段一样会漏。
3. status 段：保留现在对 `repo` 自己跑 `git status` 那段（覆盖"就是
   直接在主仓库路径工作"的场景，一直存在，不删）。
4. 新增 W8 段：解析 `resolve_work_ref` 返回的 ref 对应的分支名，
   `git -C repo worktree list --porcelain` 找到绑定这个分支的 linked
   worktree（排除 `repo` 自己），对它跑一次
   `git status --porcelain -uall`，把未提交路径（`excluded()` 过滤后、
   去重）并入 `files`。跟 `change_surface` 的 W8 段逻辑一致，只是
   用 subprocess 直接调用（`_change_files_for_codegraph` 现有风格），
   不引入新的共享 helper、不 import plan.py（继续遵守 E4）。

**读什么**：实施前完整读一遍 `bin/plan.py` 的 `change_surface()`
（`bin/plan.py:6030`）和 `resolve_work_ref()`（`bin/plan.py:5979`，
以及它在 `bin/report.py:331` 的文本一致拷贝），逐段对照着改，不要
重新发明。

## 05 不变式

- **INV-17**：`_change_files_for_codegraph` 找到的文件集合，在
  "改动全部发生在标准任务 worktree 里"这个 ai-dlc 主路径下，必须
  跟 `plan.py change_surface` 在同一个 change 上找到的文件集合一致
  （允许 `change_surface` 因为它自己更完整的 `excluded()` 逻辑等
  原因产生的既有既知差异，但 W8 worktree 可见性这一条必须对齐）。
- 延续 `docs/prd-codegraph-author-autodispatch.md` 的 INV-14/15/16——
  本 PRD 不改动调度纪律本身，只修它的输入。

## 06 反向门

延续既有三条（inline 不触发、纯新文件不触发、pin 不可用降级不阻塞），
不新增。

## 07 验收

- 单元测试：`tests/test_codegraph_autodispatch.py` 新增用例——用
  `git worktree add` 建一个真实的 linked worktree，在 worktree 里
  （不是主仓库路径）产生未提交改动，断言 `_change_files_for_codegraph`
  /`codegraph_auto_due` 现在能看到它（之前的行为是看不到，这条用例
  在修复前必须失败，修复后必须通过——写成回归测试，不是新增覆盖率）。
- 再加一条：任务分支已经有提交（不只是未提交改动）但还没合并回主
  仓库，断言现在也能通过 diff 段看到（§04 第 2 点那个连带修复）。
- 回归：全量 `pytest` + `tests/collapse/dt1_gates.sh` +
  `tests/collapse/wr_work_ref.sh`（改动跟 `resolve_work_ref`
  相关，这个 gate 必须跑一遍确认 Y7 仍然成立——虽然本 PRD 没有改
  `resolve_work_ref` 本身）。
- 手动复现验证：照 §01 的复现步骤，在一个真实 worktree 里改一个已有
  文件，跑 `plan.py phase`，确认 `codegraph_auto_due` 现在返回
  `(True, "due")`（而不是 `surface_unmeasured`）。

## 08 风险与残余

- `resolve_work_ref` 依赖 `state.json.branch`——如果某个任务的
  `state.json` 从未记过 `branch`（老任务、或者手工建的 task_dir），
  会退回 `task/{change}` 约定分支，找不到时再退回 HEAD——这条链路
  `resolve_work_ref` 自己已经处理好了，本 PRD 不需要再处理。
- 不改动 Phase B 的 `cmd_codegraph_brief`/`codegraph_surface` 本身，
  只改它们的调用方 `codegraph_auto_due` 的输入来源。

## 09 回滚

只改了 `_change_files_for_codegraph` 一个函数体，回滚即恢复到"kept
minimal"版本——`codegraph_auto_due` 在 worktree-first 流程下重新变回
`surface_unmeasured`（回到本 PRD 发现问题之前的现状，Phase A/B/C1/C2
以及 auto-dispatch 挂钩点本身都不受影响）。
