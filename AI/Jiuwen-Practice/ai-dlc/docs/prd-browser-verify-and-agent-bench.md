# PRD · browser-verify 与 agent-bench 两个新角色——都走 jiuwenswarm 派发，不直接调用，不改动上游

> 两周前那次"搜索开源社区"的评估里排了 5 条，这次先做第 3（Playwright MCP）
> 和第 5（Harbor/Terminal-Bench）。约束很明确：**胶水代码，不改社区**——
> 只装官方发布的包、不 fork、不打补丁；**用 jiuwenswarm 创建角色调用，
> 编排层（`plan.py`）不能直接调用**——不允许 `plan.py` 自己 import
> playwright、自己 shell 出 `npx playwright-mcp`、自己 shell 出
> `harbor run`。唯一允许的调用形状是 `[CLIENT, "chat", prompt, ...]`
> 派发一个会话，会话里的角色去用这些工具——跟 `codegraph`/`ui-designer`/
> `openspec-author` 完全同一个架构，不发明新模式。

- 目标仓库：`<workspace-root>`（`bin/plan.py`、
  `supervisor/skills/workspace/`、`scripts/`）
- 关联：`bin/plan.py` 里 `codegraph` 角色的完整实现（`understand_anything_pin_state`、
  `.aidlc-pin.json`、`run_codegraph_session`、`cmd_codegraph_build/brief`）——
  本 PRD 的两个新角色逐一照抄这套架构，不新发明机制。
- 文档日期：2026-09-06 · 优先级：P2 · 目标版本：v0.25.0

---

## 01 调研结论

**现状 1——页面渲染检查是编排层自己手搓的，从没走过派发**：`bin/plan.py`
第 6315 行 `render_check(pages, repo)` 自己起一个
`http.server.ThreadingHTTPServer`、用 `html.parser.HTMLParser` 数
DOM 节点数，来回答"页面渲染了没、DOM 是不是空的"。它被内嵌调用在
design 派发的"事实核验"路径里（判断角色是否真的产出了能渲染的页面），
是编排层自己的 Python 代码直接执行，**从未经过 jiuwenswarm 派发**——
跟 `codegraph`/`design`/`openspec-author` 那套"外部能力必须经派发角色
使用"的架构不是同一路数，是历史遗留的例外。Playwright MCP
（`microsoft/playwright-mcp`，Apache-2.0，230K+ 安装量，GitHub Copilot
自己的 coding agent 拿它做同一件事）已经把这件事做得更准（基于
accessibility tree，不是数 DOM 节点）、更全（能点击、填表、走完整用户
旅程,不止"渲染了没"）,没有理由继续手搓。

**现状 2——没有任何东西持续度量"这套流水线本身产出质量是涨是跌"**：
`plan.py review` 是针对单次改动的 LLM 对抗评审（发表关于这次改动的意见），
`plan.py validate` 是单次改动的 spec 结构合法性验证——两者都是**逐次改动**
判断,没有一个**跨改动、跨模型/prompt 版本**的能力曲线追踪。Harbor
（`harbor-framework/harbor`，Terminal-Bench 2.0 的官方评测框架，
`pip install harbor`）就是干这个的标准开源方案。

**现状 3——外部能力接入的架构已经有完整先例，照抄即可**：`codegraph` 角色
的实现给出了精确的模板，六个组成部分缺一不可：
1. `AI_DLC_<NAME>_ROOT` 环境变量可覆盖、默认指向 `/opt/<name>` 的 pin 目录常量
   （如 `UNDERSTAND_ANYTHING_ROOT`）。
2. pin 目录旁边的 `.aidlc-pin.json`（`tag`/`sha`/`tree_sha256`/`sparse_paths`/
   `installed_at`/`size_bytes`）——**这正是"不改社区"在技术上被强制的地方**：
   如果谁事后改了 pin 住的树，`tree_sha256` 就对不上，派发在开会话之前
   直接拒绝（`understand_anything_pin_state()` 的最后一步）。
3. 一个 `<name>_pin_state()` 检查函数——ok/not-ok 结构化返回，从不崩溃，
   总是带 remedy；不可用时降级为"跳过、不阻塞任务"，绝不硬失败。
4. 一个 `scripts/install-<name>.sh` 宿主一次性安装脚本——**调用方从不在
   运行期 clone/安装**，这条边界本 PRD 原样继承。
5. 一个 workspace 技能 `supervisor/skills/workspace/<name>/SKILL.md`——
   给角色看的"怎么用这棵 pin 树"的指南，跟 `openspec-author` 一样只是
   通道,不夹带纪律。
6. 一个 `run_<name>_session()` 派发函数——固定调用形状
   `[CLIENT, "chat", prompt, "--jsonl", "--cwd", str(repo), "--mode", mode,
   "--timeout", ..., "--session", session_name]`，evidence 落盘 jsonl，
   `judge_frames()` 判定，从不读会话的"结论句"当真相。

本 PRD 的 G1、G2 分别把 Playwright MCP 和 Harbor 套进这六件套，一件不多、
一件不少。

## 02 目标与非目标

**目标**

- **G1**：新增 `browser-verify` 角色。宿主一次性安装 Playwright MCP
  （`@playwright/mcp` 官方 npm 包 + 浏览器二进制）到 pin 目录；新增
  `browser_verify_pin_state()`；新增 workspace 技能
  `supervisor/skills/workspace/browser-verify/SKILL.md`；新增
  `run_browser_verify_session()` 与 `plan.py browser-verify` 子命令，
  经派发会话驱动 Playwright MCP 检查一组页面，产出结构化报告。
  `render_check()` 原地保留但标记 deprecated,新派发路径可用时优先用它,
  详见 §04。
- **G2**：新增 `agent-bench` 角色。宿主一次性安装 Harbor
  （`pip install harbor` 到独立 venv）到 pin 目录；新增
  `agent_bench_pin_state()`；新增 workspace 技能
  `supervisor/skills/workspace/agent-bench/SKILL.md`；新增
  `run_agent_bench_session()` 与 `plan.py bench` 子命令，经派发会话跑
  Harbor 的评测数据集（初版直接用 Harbor 自带的 `terminal-bench@2.0`
  数据集，不是本项目自建的数据集——自建数据集是明确的非目标,见下），
  产出一条签名的评测结果记录，写进独立的历史文件供人事后查阅。

**非目标**

- **不改动 Playwright MCP 或 Harbor 的任何源码**——胶水代码，只装官方
  发布的包/release，不 fork、不打补丁、不夹带本地патch。
- **编排层（`plan.py` 自身进程）绝不直接调用这两个工具**——不
  `import playwright`、不直接 `subprocess.run(["npx", "playwright-mcp", ...])`、
  不直接 `subprocess.run(["harbor", "run", ...])`。唯一允许的调用形状是
  `run_<name>_session()` 里那行 `[CLIENT, "chat", prompt, ...]`——由
  jiuwenswarm 开一个真会话，会话里的角色自己决定怎么用这些工具。
- **`agent-bench` 不进 MERGE_GATE，不卡任何单次改动的交付判定**——它是
  独立于 `--change <id>` 生命周期之外的诊断命令,产出写进独立的历史
  文件,不写进任何一次 change 的 `delivered` 判据。这条对齐上次评估时
  已经定下的立场（"不进 MERGE_GATE、不卡任何单次改动"）。
- **本版不自建评测任务集**——直接用 Harbor/Terminal-Bench 自带的公开
  数据集（`terminal-bench@2.0`）。"拿 ai-dlc 自己已合并的 168 个 PR 当
  回归任务集"是有价值的后续方向,但需要单独设计任务定义格式,不在本次
  范围内,记在 §08。
- **不删除、不立刻迁移 `render_check()` 的现有调用点**——`design_facts`
  今天调用 `render_check()` 的路径原样保留、继续工作；本 PRD 只新增
  `browser-verify` 这条**新**路径,新旧并存,迁移时机是分期决定,见 §07。
- **不新增任何 cost/budget 相关字段**（继续遵守 `SKILL.md` 硬性禁令 #2）。

## 03 不变式

延续既有编号（`docs/prd-plane-git-boundary-and-rollback-anchor.md` 用到
INV-35），从 INV-36 继续：

- **INV-36**：`browser-verify`/`agent-bench` 的 pin 校验必须包含
  `tree_sha256` 摘要比对——pin 住的树被事后修改，派发在会话开始前拒绝，
  不静默继续（原样照抄 `understand_anything_pin_state` 的第五步）。
- **INV-37**：两个角色的宿主安装脚本（`scripts/install-browser-verify.sh`、
  `scripts/install-agent-bench.sh`）只做"下载官方发布版本 + 写 pin"，
  绝不修改下载下来的文件内容——安装后的树与上游发布物字节级一致，除了
  `.aidlc-pin.json` 本身。
- **INV-38**：`plan.py`/`report.py` 源码中，除 `run_browser_verify_session`/
  `run_agent_bench_session`（以及既有的 `run_codegraph_session` 等同类
  函数）之外，不得出现直接执行 Playwright/Harbor 可执行文件的代码路径——
  这是"不能直接调用"的静态可核查版本，门禁可以直接 grep 检查。
- **INV-39**：pin 不可用（未安装/摘要不匹配）时，`browser-verify` 与
  `agent-bench` 都必须降级为"跳过、记录原因、不阻塞任务"，不得让缺失的
  外部工具变成任务的硬失败（对齐 codegraph INV-12 同一立场）。
- **INV-40**：`agent-bench` 的产出记录必须包含 Harbor/Playwright 的**版本号
  与 pin 的 sha256**，不能只留一个"跑过了"的布尔值——没有版本信息的评测
  结果无法跟未来的结果比较，等于没测。

## 04 目标架构

### G1 — `browser-verify`

**Pin**（照抄 codegraph 的六件套）：
- `AI_DLC_PLAYWRIGHT_MCP_ROOT`，默认 `/opt/playwright-mcp`。
- `scripts/install-browser-verify.sh`：`npm install @playwright/mcp@<pinned-version>`
  到该目录（本地安装，不装全局，避免跟宿主机其他 npm 项目打架）+
  `npx playwright install chromium`（Playwright 官方给的浏览器二进制
  安装命令，同样是纯下载官方产物）；安装完写 `.aidlc-pin.json`
  （`tag` = npm 包版本号，`tree_sha256` = 对整个安装目录的摘要）。
- `browser_verify_pin_state(root=None) -> dict`：结构和
  `understand_anything_pin_state` 一致（ok/root/pin/why/remedy/exit_code），
  校验目录存在、pin 文件存在、`tree_sha256` 摘要吻合。

**Workspace 技能** `supervisor/skills/workspace/browser-verify/SKILL.md`：
薄通道，三段式（跟 `openspec-author` 一样不夹带纪律）：
1. 你是谁——你正在核验派发 prompt 给出的这组页面是否真的渲染、关键
   元素是否存在。
2. 怎么做——通过本机已装好的 Playwright MCP（pin 目录下的
   `@playwright/mcp`）打开每个页面，读 accessibility snapshot，检查
   HTTP 状态、标题、prompt 里点名要核对的选择器/文案是否存在；把结果
   写成结构化 markdown（`browser-verify/report.md`）：每页一行,
   通过/失败 + 失败原因。
3. 拿不到工具/页面不可达怎么办——按既有的 `CLI_UNAVAILABLE_MARKER`
   协议停手、如实说明，不编造"看起来是对的"。

**派发**：`run_browser_verify_session(change, prompt, repo, task_dir, mode,
timeout) -> tuple[dict, list]`，函数体与 `run_codegraph_session` 同构
（`session_name = f"browser-verify-{change}-{seq}"`，`[CLIENT, "chat", ...]`，
evidence 落盘，`judge_frames()`）。`plan.py browser-verify --change <id>
--repo <repo> --pages <相对路径,逗号分隔>` 组合 prompt（把 pages 列表和
本次要核对的断言塞进 prompt）、检查 pin、派发、把结果记进
`state.json.browser_verify` 与 `events.jsonl`（`BROWSER_VERIFY_PASSED`/
`BROWSER_VERIFY_FAILED`/`BROWSER_VERIFY_UNAVAILABLE`）。

**与 `render_check()` 的关系**：不改、不删既有调用——`design_facts` 继续
用它做同步、免会话的快速核验（它本来就是"六个机械检查之一"的角色，
拆下来单独跑一次会话反而增加延迟）。`browser-verify` 是给**需要真实
交互（点击、填表、走完整旅程）**的场景用的新增能力，`render_check` 覆盖
不了这一段——两条路径场景不同、并存，见 §07 的分期建议何时考虑收敛。

### G2 — `agent-bench`

**Pin**：
- `AI_DLC_AGENT_BENCH_ROOT`，默认 `/opt/agent-bench`。
- `scripts/install-agent-bench.sh`：在该目录下建一个独立 Python venv，
  `pip install harbor`（官方 PyPI 包，不装到宿主机全局 site-packages，
  避免跟其他 Python 项目的依赖冲突）；写 `.aidlc-pin.json`
  （`tag` = Harbor 版本号）。
- `agent_bench_pin_state()`：结构同上，额外校验 venv 内
  `bin/harbor`（或等价入口）可执行。

**Workspace 技能** `supervisor/skills/workspace/agent-bench/SKILL.md`：
薄通道：
1. 你是谁——你在跑一次 ai-dlc 流水线自身的能力评测,不是在改任何用户
   项目。
2. 怎么做——用 pin 目录下的 Harbor（`harbor run --dataset
   terminal-bench@2.0 --agent claude-code --model <派发 prompt 给出的
   model 参数> --n-concurrent <派发 prompt 给出的并发数>`），等它跑完，
   读它自己产出的结果文件，把摘要（总任务数、通过数、每类失败原因）写成
   `agent-bench/result.md` + 原始 Harbor 输出路径的指针。
3. 跑失败/pin 不可用怎么办——同 G1 的停手协议。

**派发**：`run_agent_bench_session(prompt, repo, task_dir, mode, timeout)`，
结构同构（`session_name = f"agent-bench-{seq}"`，不挂 `change`——这是
独立诊断,不是任何一次 change 的一部分）。`plan.py bench [--dataset
terminal-bench@2.0] [--model <name>] [--n-concurrent N]` 子命令：检查
pin → 派发 → 把签名结果写进
`/var/lib/aidlc/bench-history/<started_at>.json`（版本号+摘要+通过率，
INV-40）→ `emit` 一份摘要给调用的人看。**不接受 `--change`、不读写任何
`.ai-dlc/tasks/` 下的状态、不出现在任何 `report.py deliver` 的判据里**——
这是它"不卡任何单次改动"的技术落实方式,不是靠自觉。

## 05 反向门

- **两者共同**：pin 目录存在但 `.aidlc-pin.json` 缺失或摘要不匹配 →
  拒绝派发,报 remedy（重跑安装脚本或人工确认后手动重新写 pin），不静默
  用一棵可能被改过的树。
- **G1**：`--pages` 给出的路径一个都不存在于当前 `--repo` 的工作树里 →
  不派发,直接返回 `browser_verify_state: "not_applicable"`（没有可核对
  的页面，派发一次会话没有意义）。
- **G1**：Playwright MCP 会话打不开浏览器（宿主环境缺依赖，比如缺
  `libnss3` 之类系统库）→ 角色按停手协议报告，`plan.py browser-verify`
  记 `browser_verify_state: "unavailable"`,不阻塞调用方的任务。
- **G2**：Harbor 数据集下载失败（离线环境）→ 角色停手报告，
  `plan.py bench` 记 `agent_bench_state: "unavailable"`,退出码 0（诊断
  命令本身不应该让调用它的脚本/CI 因为"这次测不了"而失败）。
- **G2**：`--n-concurrent` 缺省时不假设一个数字——读派发 prompt 给出的
  值，没给就用 Harbor 自己的默认值，`plan.py bench` 不在这一层发明
  自己的默认并发策略。

## 06 验收

- 单元：`browser_verify_pin_state`/`agent_bench_pin_state` 分别覆盖
  "全部就绪"、"目录不存在"、"pin 文件缺失"、"摘要不匹配" 四种分支，
  返回结构与 `understand_anything_pin_state` 同构。
- 静态门禁（对应 INV-38）：新增一条 `grep` 型 collapse 门禁，确认
  `bin/plan.py`/`bin/report.py` 里除
  `run_browser_verify_session`/`run_agent_bench_session`/既有的
  `run_codegraph_session`/`run_design_session` 等函数体之外,不出现
  `playwright`/`harbor` 可执行文件名的直接 `subprocess`/`os.exec` 调用。
- 端到端（依赖真实宿主环境，记录在实施报告里留给有权限的人跑）：
  ① 跑一次 `scripts/install-browser-verify.sh`，确认 pin 写入、
  `browser_verify_pin_state().ok == true`；对一个真实的多页面项目跑
  `plan.py browser-verify`，核对 evidence frames 里出现的是 Playwright
  MCP 的工具调用（而不是角色自己写了一个简易 curl/requests 脚本糊弄过去——
  跟 `openspec-author` 那次"必须在 evidence 里看到真实调用"是同一验收
  哲学）。
  ② 跑一次 `scripts/install-agent-bench.sh`，`plan.py bench --n-concurrent
  1` 跑一个最小任务子集，核对 `/var/lib/aidlc/bench-history/` 下出现
  带版本号的签名记录。

## 07 分期

| Phase | 内容 | 风险 |
|---|---|---|
| A（本 PRD 覆盖） | G1 + G2 的完整六件套（pin/安装脚本/技能/派发函数/子命令），`render_check()` 原样保留、新旧并存 | 低——纯新增，不改动任何既有调用路径 |
| B（未来，视 A 落地后的实测情况决定） | 是否把 `design_facts` 里 `render_check()` 的调用逐步替换成 `browser-verify` 派发（好处是更准确,代价是从"同步免会话"变成"需要开一次会话",延迟和成本都会上升,需要实测权衡后再决定，不在本次预判） | 中——涉及既有 D8 事实核验路径的行为变更 |
| C（未来） | `agent-bench` 自建基于 ai-dlc 自身历史 PR 的回归任务集，取代/补充 Harbor 自带的通用数据集 | 中——需要单独设计任务定义格式与"什么算通过" |

## 08 风险与残余

- G1 的浏览器依赖（Chromium + 系统库）比 Harbor 的 Python venv 更重，
  在受限的宿主环境里更容易触发"pin 不可用"的降级路径——这是可接受的
  已知取舍，不是本 PRD 要解决的问题。
- G2 首版直接用 Harbor 公开数据集，跑分不能直接说明"ai-dlc 这套流水线
  具体哪里变差了"，只能看到"整体分数变化"——归因到具体阶段（WORK/
  DESIGN/CHECK 哪个环节）需要 Phase C 的自建任务集才有意义。
- 两个新角色都会给宿主机新增外部下载依赖（npm 包+浏览器二进制、
  PyPI 包）——安装脚本失败模式（网络受限环境）已经在 §05 反向门里
  显式处理为不阻塞，但首次安装本身仍然需要一次性联网。

## 09 回滚

两个角色各自独立、互不依赖，可以单独回滚：删除对应的
`run_<name>_session`/`<name>_pin_state`/`plan.py <name>` 子命令代码、
删除 `supervisor/skills/workspace/<name>/`、删除 pin 目录，行为回到今天。
`render_check()`、`design_facts` 及既有 D8 路径完全不受影响——这是
本 PRD 特意保持"新旧并存、互不牵连"架构的直接好处。
