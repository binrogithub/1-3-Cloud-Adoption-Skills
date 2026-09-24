# PRD · jiuwenswarm 派发 Understand-Anything 子 agent——注册缺口

> SKILL.md 里写着"用 Task 工具派发 project-scanner"，
> 但 project-scanner 这个名字，jiuwenswarm 压根不认识。

- 目标仓库：`<workspace-root>`（本仓库自身，`bin/plan.py` +
  `scripts/install-understand-anything.sh`）
- 关联：`docs/prd-codegraph-understand-anything-backend.md`（C1/C2 已合入
  master）、`docs/team-mode-record.md`（jiuwenswarm team 模式的既有调研，
  跟本 PRD 是两回事，见下）
- 文档日期：2026-09-04
- 优先级：P1

---

## 01 调研结论

**jiuwenswarm 的 `code.normal` 会话内置一个跟 Claude Code 完全一致的
Task 工具。** 查了 `<workspace-root>/reference/jiuwenswarm` 源码：
`jiuwenswarm/server/runtime/agent_adapter/code_agent_rail.py` 里会话可用
工具集直接列着 `"Agent", "task", "enter_plan_mode", ...`，Task 工具的
参数 schema 是 `subagent_type` / `description` / `prompt` 三件套——跟
Claude Code 自己的 Task 工具字面一致。`debug_trace/task_tool_patch.py`
甚至专门为它做了调试追踪（"Monkeypatch the SDK's builtin
`TaskTool.invoke` to capture subagent streams"）。这不是阉割版会话，是
带完整子 agent 派发能力的真实 agent 运行时。

**这跟 `docs/team-mode-record.md` 调研过的"team"模式是两个不同机制**，
容易混——team 模式是**多个独立的 jiuwenswarm 参与者**（leader +
teammate），已经因为"给不了具名角色、慢一个数量级、进度不可见"被否决；
Task 工具是**一个会话内部**派发子任务的能力，跟 team 模式不共享同一套
限制。Understand-Anything 的 `understand/SKILL.md` 需要的正是 Task
工具，不是 team 模式——本 PRD 不重开 team 模式的讨论，那份记录仍然成立。

**真正的缺口**：`understand/SKILL.md`（已经在 C1/C2 里被读进
`cmd_codegraph_build` 的 prompt）预期会话会用 Task 工具派发
`understand-anything-plugin/agents/*.md` 里定义的具名子 agent
（`project-scanner`、`file-analyzer`、`architecture-analyzer` 等）。
但这些 `agents/*.md` 文件只是躺在只读 pin 里（`/opt/understand-
anything`），**从没被复制进 jiuwenswarm 的 `AgentConfigService` 会扫描
的目录**。查了 `agent_config_service.py`：它扫描三层——
`_get_user_agents_dir()`（`~/.jiuwenswarm/agents`，已核实
`get_user_workspace_dir()` 直接返回 `~/.jiuwenswarm`，不是
`~/.jiuwenswarm/agent/workspace/...` 那套 skills 用的路径）、
`_get_project_agents_dir()`（`<workspace>/.jiuwenswarm/agents`）、
`_get_local_agents_dir()`（`<workspace>/.jiuwenswarm/agents-local`）。
`project-scanner.md` 这个名字不在任何一层里，Task 工具的
`subagent_type: "project-scanner"` 就解析不到——会话即使读了 SKILL.md、
想照着派发，也没有这个子 agent 可派。

**格式恰好完全匹配，不需要转换**：`_parse_agent_file` 期待
`---\nname: ...\ndescription: ...\n---\n<正文>` 这个 YAML frontmatter +
markdown 正文的格式；实际下载核对过 `project-scanner.md` 的文件头，
逐字段对得上（`name`、`description`）。缺的只是"把文件放到该放的地方"
这一步。

## 02 目标与非目标

**目标**

- `scripts/install-understand-anything.sh` 新增一步：把
  `understand-anything-plugin/agents/*.md` 逐个复制进
  `~/.jiuwenswarm/agents/`（"user"层，全局可用，不是项目层——理由：
  codegraph 角色对任意仓库都该能用，不该逐仓库重新注册）。
- 复制而不是符号链接——对齐 `install-opendesign.sh` 给 `ui-designer`
  SKILL.md 用的 `install -D -m 0644` 那个既有惯例（拷贝小文件，不搞
  跨只读树的符号链接）。
- `--uninstall` 对称删除这些注册（跟既有的 skill 卸载逻辑一致）。
- `cmd_codegraph_build`/`cmd_codegraph_brief` 的 prompt 明确列出已注册
  的 `subagent_type` 名字，让会话不用自己猜、直接照抄。

**非目标**

- 不碰 `docs/team-mode-record.md` 或任何 team 模式相关代码——那是另一套
  机制，已经有定论。
- 不给 Understand-Anything 的子 agent 定义做任何内容修改——原样注册，
  不做本地化或裁剪。
- 不注册到 project/local 层——除非以后发现"这个仓库需要一份跟全局不同
  的 codegraph 子 agent 定义"，那是另一个 change 的事，本 PRD 不预判。

## 03 不变式

- **INV-11** 注册的子 agent 定义文件只读（`chmod 0444`，对齐已有
  `/opt/understand-anything` 的只读纪律，虽然这次是复制出来的独立文件，
  不是同一棵只读树，但角色不该在运行期改写自己的定义）。
- **INV-12** 注册失败（比如 `~/.jiuwenswarm/agents/` 目录不可写）不阻塞
  `codegraph build`/`brief`——降级成"会话拿不到 Task 工具可用的具名子
  agent，只能靠自己读 SKILL.md 里的说明尽力做"，跟 §07 反向门的既有
  "不可用不阻塞任务"立场一致，不新增一种阻塞路径。
- **INV-13** 注册是覆盖式幂等——重跑安装脚本用新版本覆盖旧的子 agent
  定义文件，不残留旧版本内容（对齐 open-design pin 的"tag 换了就升级"
  纪律）。

## 04 目标架构

**安装脚本改动**（`scripts/install-understand-anything.sh`，第①步之后
新增）：

```bash
AGENTS_SRC="$ROOT/understand-anything-plugin/agents"
AGENTS_DST="${AI_DLC_JIUWENSWARM_AGENTS_DIR:-$HOME/.jiuwenswarm/agents}"
if [[ -d "$AGENTS_SRC" ]]; then
  mkdir -p "$AGENTS_DST"
  for f in "$AGENTS_SRC"/*.md; do
    install -D -m 0444 "$f" "$AGENTS_DST/$(basename "$f")"
  done
  say "registered $(ls "$AGENTS_SRC"/*.md | wc -l) subagents into $AGENTS_DST"
fi
```

`--uninstall` 对称删除 `$AGENTS_DST` 下同名文件（不清空整个目录——那
里可能有别的、无关的用户自定义 agent）。

**prompt 改动**（`cmd_codegraph_build`/`cmd_codegraph_brief` 里已有的
prompt 构造处）：读一遍 `understand-anything-plugin/agents/` 目录列出
的文件名（去掉 `.md` 后缀就是 `subagent_type` 的值），在 prompt 里加一句
"以下是已注册、可以直接用 Task 工具派发的子 agent 名字：
project-scanner, file-analyzer, architecture-analyzer, ..."——不需要让
会话自己去猜或去读目录，直接告诉它。

## 05 反向门

- 已经注册过、再跑一次安装脚本 → 覆盖式幂等更新，不报错、不追加重复。
- pin 存在但 `agents/` 子目录不存在（未来 Understand-Anything 版本
  改了目录结构）→ 跳过这一步，`say` 一条提示，不 `die`——这一步的失败
  不该拖垮整个安装。
- `~/.jiuwenswarm/agents/` 目录已存在且里面有同名但内容不同的文件（用户
  自己写的 `project-scanner.md`）→ 直接覆盖（这是"user"层的既有语义——
  同名后装的赢，源码里 `_load_from_dir` 本来就是后来源覆盖前来源）；
  这不是本 PRD 引入的新行为，是 jiuwenswarm 自己的既有加载顺序。

## 06 验收

- 单元测试：安装脚本的这一步用一个假的 `agents/*.md` 目录跑一遍，断言
  目标目录下出现同名文件、内容一致、mode 0444。
- 端到端（人工/后续 change）：真的装完之后，跑一次
  `jiuwenswarm chat --mode code.normal` 让会话尝试用 Task 工具派发
  `subagent_type: "project-scanner"`，确认能解析到（这一步依赖真实
  jiuwenswarm 网关和已安装的 pin，不在这次委托的自动化测试范围内——
  记在这里，留给有真实环境的人工验证）。

## 07 回滚

只新增了安装脚本里的一段循环 + `cmd_codegraph_build`/`brief` prompt 里
一行列举——删掉这段循环、手动清掉 `~/.jiuwenswarm/agents/` 下对应的
文件即可完全回退，不影响 C1/C2 已经落地的 pin/build/brief 骨架。
