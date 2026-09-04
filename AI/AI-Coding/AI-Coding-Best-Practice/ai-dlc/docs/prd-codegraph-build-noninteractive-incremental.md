# PRD · codegraph build 派发的非交互纪律 + 复用既有增量图

> 官方工具自己说"后续运行默认是增量的"。我们的派发 prompt 从没告诉过
> 它"这是后续运行"，也没告诉过它"这里没有人能回答你的问题"。

- 目标仓库：`<workspace-root>`（`bin/plan.py`）
- 关联：`docs/prd-codegraph-understand-anything-backend.md`（C1/C2，
  `_codegraph_build_core` 的原始实现）、`docs/prd-codegraph-role.md`
  （Phase A/B）
- 文档日期：2026-09-04
- 优先级：P2（不是阻塞性 bug——现状能跑通，只是每次都比该付的贵得多）

---

## 01 调研：官方工具自己的"协同"设计，以及我们没接上的那部分

搜了一遍本机已经 pin 住的 Understand-Anything 技能树源码（
`/opt/understand-anything`，跟实际调用的版本完全一致，最权威），加一次
外部检索验证。结论：官方从设计上就不是"每次都全量重建"：

**`skills/understand/SKILL.md` 自带新鲜度判定表**（该文件 §7 决策逻辑，
读取 `.ua/meta.json` 的 `gitCommitHash` 跟当前 HEAD 比对）：

| 情况 | 官方设计的动作 |
|---|---|
| 无既有图 | 全量分析 |
| 有图 + commit hash 没变 | **向用户提问**："已是最新，要 (a) 全量重建 (b) 跑图审查 (c) 什么都不做？" |
| 有图 + 有文件变了 | **增量更新**——只重新分析变了的文件，走 `hooks/auto-update-prompt.md` 那套零 token 结构指纹判定 |

README 原话："The initial `/understand` ... can consume a significant
number of tokens ... **Subsequent runs are incremental by default —
only changed files are re-analyzed.**"

**我们已经具备触发增量路径的前提条件，只是没告诉角色去用它**：验证过
（这次 live 测试的 `bugfind-live-test` 仓库）`.ua/knowledge-graph.json`
/`.ua/meta.json`/`.ua/fingerprints.json` 是写在 `--repo` 传的**主仓库
checkout 路径**下的，不是任务 worktree 里——worktree 会在任务合并后被
`plan.py close` 删掉，但主仓库路径不会。也就是说，**同一个仓库上的
后续 `codegraph brief`/`codegraph build` 派发，图天然已经在磁盘上等着
被复用**，不需要额外的持久化机制、不需要改 `INV-9`（`.ua/**` 不计入
`landed_files` 这条不受影响，本 PRD 不碰它）。

**真正的缺口在 `_codegraph_build_core` 的 build prompt**
（`bin/plan.py:7898`）：现在的 prompt 只是把 `understand/SKILL.md`
全文糊进去、加一句"照着做"，完全没告诉被派发的角色：

1. 这是一次**无人值守的自动化派发**（jiuwenswarm session dispatch，
   不是本地交互式 Claude Code 会话）——SKILL.md §7 决策表里"有图+
   commit hash 没变 → 向用户提问"这一分支，在这里没有人能回答。角色
   会怎么处理这个没人应答的多选题是未定义行为：可能瞎猜一个选项、
   可能卡住等一个不会来的输入、也可能默认选了最贵的"全量重建"——
   跟 `hooks/hooks.json` 那条官方自己的自动化路径明确写的原则
   （"Do not ask the user for confirmation — just do it"）正好相反。
2. 磁盘上**可能已经有一份可复用的图**——prompt 里从没提过这件事，
   角色是靠自己读 SKILL.md 里"检查 `.ua/knowledge-graph.json` 是否
   存在"这一步才发现的，不是我们主动告知的，容易在长 prompt 里被
   淹没或误判。

这次实测（`verify-ab` 那次 live 验证，见 PART A/B 验证记录）耗时
669 秒建一个 4 文件玩具仓库的图——这次是**第一次**建图（仓库里原本
没有 `.ua/`），走全量分析是正确、预期的行为，不是本 PRD 要修的问题。
本 PRD 要修的是：**第二次、第三次……在同一个仓库上的派发**，理论上
应该命中增量路径（便宜、快），但没人明确告诉角色"这就是你要走的
路径，别停下来问问题"。

## 02 目标架构

**只改一处**：`bin/plan.py` 的 `_codegraph_build_core()`
（`bin/plan.py:7898`）里构造 `build_prompt` 的那一段。在现有的
"Follow the skill instructions below in full" 之前，加一段明确的
非交互运行上下文说明，原则直接对齐 `hooks/auto-update-prompt.md`
和 `hooks/hooks.json` 里官方自己用的措辞（"Do not ask the user for
confirmation — just do it"），具体要求：

1. **声明运行上下文**：这是一次自动化、无人值守的会话派发——运行
   过程中不存在可以回答问题的人。
2. **SKILL.md §7 决策表里任何"向用户提问/等待用户选择"的分支**：
   不等待、不停下——按"用户选了 (c) 什么都不做"处理（即：图已是最新
   就直接复用，不重建），除非该分支本身已经明确说明了非交互回退
   行为（比如语言检测那一步 SKILL.md 自己已经写了"如果无法交互就
   跳过等待，用检测到的语言，打印一行提示"——那种已有回退的分支不用
   我们额外说明，只针对"完全没有非交互回退"的那个新鲜度确认分支）。
3. **明确提示磁盘状态**：告诉角色 `{repo}/.ua/knowledge-graph.json`
   如果已存在，大概率是同一仓库更早一次派发留下的、可复用的图——
   请按 SKILL.md 自己的新鲜度判定表决定是复用、增量更新还是全量
   重建，不要预设"这次一定要全量重建"。
4. **不新增任何 `--full`/`--review` 之类的参数传递机制**——不在我们
   这边模拟 `$ARGUMENTS`，交给 SKILL.md 自己的决策表按磁盘状态判断；
   本 PRD 只是把"这是自动化环境、别问问题"说清楚，不替角色做判断。

`cmd_codegraph_brief`（`bin/plan.py:7970`）调用 `_codegraph_build_core`
的方式不变——它已经是"先 build 再 brief"的既有流程，本 PRD 不改这个
顺序、不改 `cmd_codegraph_brief` 本身的任何逻辑。

## 03 不变式

- **INV-18**：`_codegraph_build_core` 的 prompt 变化不改变它的返回值
  形状（仍是 `(exit_code, result_dict)`，`result_dict` 仍带
  `graph_file`/`graph_written`）——调用方 `cmd_codegraph_build`/
  `cmd_codegraph_brief` 不需要跟着改。
- 延续既有的 INV-8~INV-10（安装免交互、`.ua/**`/`codegraph/**` 不计入
  `landed_files`、pin 只读校验）——本 PRD 不改动这几条，也不改动
  `INV-9` 的排除范围本身（讨论过是否要把图纳入版本控制，结论是**不
  需要**——图已经天然持久化在主仓库 checkout 路径上，见 §01，不需要
  靠 git 提交来解决"重复建图"的问题）。

## 04 反向门

延续既有几条不阻塞任务的立场——本 PRD 不新增反向门，只是让既有的
"pin 不可用→unavailable"路径之外，多一条"图已存在且新鲜→角色应该
识别到并跳过重建"的预期路径更容易被角色正确命中。

## 05 验收

- 单元测试（`tests/test_codegraph_*` 里挑合适的文件扩展，或新建
  `tests/test_codegraph_build_prompt.py`）：断言 `_codegraph_build_core`
  构造出的 prompt 字符串里包含（a）非交互运行上下文的说明文字（b）
  "don't ask/wait for a human" 一类措辞（c）提到检查
  `.ua/knowledge-graph.json` 是否已存在这件事——不需要真的派发会话，
  只测 prompt 字符串本身的内容（mock/monkeypatch
  `run_codegraph_session`，只检查它被调用时传入的 prompt 参数）。
- 手动复现验证（实施者跑一次，不用写进自动化测试）：在一个**已经有
  `.ua/knowledge-graph.json` 且 commit hash 未变**的仓库上，再跑一次
  `plan.py codegraph brief`，确认这次派发明显比首次建图快得多（用
  `state.json.codegraph_brief`/`planning.json.codegraph_auto` 里的
  `elapsed_seconds` 对比），且没有卡在等待输入上。
- 回归：全量 `pytest` + `tests/collapse/dt1_gates.sh`。

## 06 风险与残余

- SKILL.md 自身的决策逻辑（§7 那张表）不受我们控制——它是 pin 住的
  第三方技能树，如果未来升级 pin 版本时这张表的分支结构变了（比如
  又加了一种新的交互式确认），本 PRD 加的说明文字可能需要跟着调整。
  这是选型时就接受的代价（pin 第三方 prompt/skill 驱动型工具的固有
  风险），不是本 PRD 引入的新风险。
- 复用既有图不是这次要验证的对象——本 PRD 的验收只要求"不再无谓地
  卡在交互确认上"，至于 SKILL.md 自己的增量更新流水线本身是否精确
  可靠（`hooks/auto-update-prompt.md` 那套指纹判定），是第三方工具
  自己的实现细节，我们不重新验证、不重复实现（延续 Phase B/C2 一直
  以来的立场：复用已验证过的方法论，不自己发明一套）。

## 07 回滚

只改了 `_codegraph_build_core` 一个函数体里 prompt 拼接的那一段——
回滚即恢复到"prompt 里不提非交互纪律、不提复用既有图"的现状，行为
退回本 PRD 发现问题之前——每次派发都可能撞上未定义的交互式分支，但
不影响任何已落地的功能（Phase A/B/C1/C2、auto-dispatch 挂钩点、
worktree 盲区修复都不依赖这段 prompt 的具体措辞）。
