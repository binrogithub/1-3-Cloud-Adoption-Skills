# PRD · install.sh 接入 browser-verify / agent-bench，并为存量用户补增量更新路径

## 01 调研结论

`browser-verify`、`agent-bench` 两个角色（PR #169）已经落地：`bin/plan.py`
的调度函数、`scripts/install-browser-verify.sh`、
`scripts/install-agent-bench.sh`、`supervisor/skills/workspace/<name>/`
均已存在并通过实测（真实安装 + 真实 jiuwenswarm 派发验证）。但 `install.sh`
本身**完全没有引用**这两个新脚本——

```
grep -n 'browser-verify\|agent-bench\|install-browser-verify\|install-agent-bench' install.sh
# (空)
```

对照同类型、已落地的两个前例 `--opendesign` / `--understand-anything`，
它们在 `install.sh` 里各接入了五个位置，`browser-verify` / `agent-bench`
一个都没有：

| 接入点 | opendesign/understand-anything 现状 | browser-verify/agent-bench 现状 |
|---|---|---|
| usage 注释（~L24） | 有 | 无 |
| doctor 缺失告警（run_doctor 内） | 有：`warn "... tree missing ... Run: ./install.sh --opendesign"` | 无 |
| `--bootstrap` 流程（步骤 4/6、5/6） | 有 | 无 |
| 顶层 flag 解析（`--opendesign`/`--understand-anything`） | 有 | 无 |
| `--help` 文本 | 有 | 无 |
| mode dispatch（`exec .../install-*.sh "$@"`） | 有 | 无 |

这两个 sub-task 在各自的 `IMPLEMENTATION_REPORT.md` 里已经如实标注了这一
缺口（"I did NOT edit install.sh ... since install.sh is a shared file the
browser-verify session may also be editing and the brief's enumerated file
list did not include it"）——不是遗漏，是当时的委托边界特意排除了共享文件
的并发编辑风险，遗留到现在才补。

**已有的存量用户感知机制**：`install.sh --check-sync`（`run_check_sync()`，
~L294-330）比较仓库根 `VERSION` 与每个已安装 target 的 `VERSION`，报告版本
漂移，但这只覆盖"完整工具集拷贝"这条路径（`cp -r` 时把 VERSION 一起带过
去的 target），**不覆盖**这两个"host 一次性 pin 安装"的外部工具（
OpenDesign / Understand-Anything / 未来的 browser-verify / agent-bench）
——这四者的"新不新"完全靠 `run_doctor()` 里对应目录是否存在来判断，与
`VERSION`/`--check-sync` 机制无关，两套机制并行、互不覆盖，这是既有设计，
不是本 PRD 要统一的对象。

## 02 目标与非目标

**目标**

- G1：`install.sh` 为 `browser-verify`、`agent-bench` 补齐与
  `opendesign`/`understand-anything` **完全对称**的五个接入点（usage 注释、
  doctor 告警、bootstrap 步骤、顶层 flag、help 文本、mode dispatch——共六项，
  上表五行里 bootstrap 单独占两步）。
- G2：存量用户（已经装过旧版 ai-dlc、仓库已 `git pull` 到含这两个新角色
  的版本，但从未跑过安装动作）能够**在不重新执行完整安装的前提下**，
  发现并单独装上这两个新组件——机制与 opendesign/understand-anything
  当年提供给存量用户的路径完全一致：`--doctor` 输出对应 warn 行 + 明确
  的 remedy 命令（`./install.sh --browser-verify` / `--agent-bench`）。
- G3：`--bootstrap`（面向全新环境的一次性建环）把这两步一并纳入，步骤计数
  从"6 步"改为"8 步"，与新增的两步保持一致的 `步骤 N/8 开始/完成` 输出格式。

**非目标**

- 不新增独立于 `--check-sync` 之外的"版本号"机制给这两个 pin 式外部工具
  ——它们本来就没有语义版本号意义下的"VERSION 文件漂移"概念，`ok`/`not
  ok` 只看目录是否存在、pin 摘要是否吻合（`browser_verify_pin_state()` /
  `agent_bench_pin_state()` 已经是权威判断源），不重复造轮子。
- 不修改 `bin/plan.py`、两个 pin-state 函数、两个 dispatch 函数、两个
  `SKILL.md`——PR #169 的核心实现已验证完毕，本 PRD 只动 `install.sh`。
- 不强制现有安装立刻升级；两个新组件在 `--bootstrap` 之外仍是可选、
  显式 opt-in（与 opendesign/understand-anything 现状一致——它们也不在
  `(no flags)` 的默认安装路径里，只在 `--bootstrap` 或显式 flag 下才装）。

## 03 不变式

延续仓库全局 INV 编号，从 INV-41 起：

- **INV-41**：`install.sh` 里任何"host 一次性 pin 安装"外部工具（现有
  OpenDesign、Understand-Anything，新增 browser-verify、agent-bench）
  必须同时具备：usage 注释、doctor 缺失告警（含可直接复制执行的 remedy
  命令）、独立的顶层 flag、help 文本条目、mode dispatch 的 `exec` 交接——
  五项任一缺失即视为该工具未完成接入，`tests/collapse/dt1_gates.sh` 或
  等价门禁必须能检测到新增工具漏接任一项。
- **INV-42**：`--doctor` 对这两个新工具的告警文案必须准确指出后果
  （"plan.py browser-verify 会派发失败" / "plan.py bench 会报
  unavailable"），不得使用与 OpenDesign/Understand-Anything 告警重复的
  笼统文案，避免存量用户看错该装哪一个。
- **INV-43**：`--bootstrap` 纳入这两步后，任一步失败（`rc=1`）不得中断
  后续步骤——与现有 opendesign/understand-anything 步骤的"失败只标记
  rc、继续跑完全部步骤，最后由整体 rc 反映"行为完全一致，不引入新的
  中止语义。

## 04 目标架构

对 `install.sh` 做六处镜像式追加，逐一对齐现有 opendesign/
understand-anything 的写法（不引入新抽象、不重构现有函数）：

1. **usage 注释**（~L24 附近）追加两行：
   ```
   ./install.sh --browser-verify      # deploy the Playwright MCP tree (host step)
   ./install.sh --agent-bench         # deploy the Harbor/Terminal-Bench venv (host step)
   ```

2. **`run_doctor()` 缺失告警**（紧跟 understand-anything 告警块之后）：
   ```bash
   local bv_root="${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}"
   if [[ -d "${bv_root}" ]]; then
     ok "Playwright MCP tree present: ${bv_root}"
   else
     warn "Playwright MCP tree missing — plan.py browser-verify will fail to dispatch. Run: ./install.sh --browser-verify"
   fi

   local ab_root="${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}"
   if [[ -d "${ab_root}" ]]; then
     ok "Harbor/Terminal-Bench venv present: ${ab_root}"
   else
     warn "Harbor/Terminal-Bench venv missing — plan.py bench will report unavailable. Run: ./install.sh --agent-bench"
   fi
   ```
   根目录环境变量名必须与 `bin/plan.py` 里实际使用的
   `AI_DLC_PLAYWRIGHT_MCP_ROOT` / `AI_DLC_AGENT_BENCH_ROOT` 逐字一致
   ——这是最容易出现"看起来装了、其实没对上"的地方，实现时必须回读
   `bin/plan.py` 里的常量定义确认，不能凭记忆猜。

3. **`--bootstrap` 流程**：在既有"步骤 5/6 Understand-Anything"之后追加
   两步，并把全部步骤计数器从 `N/6` 改为 `N/8`（含之前的 1-5 步文案）：
   ```bash
   # ── Step 6/8: Playwright MCP (browser-verify) ──
   echo ""
   echo "步骤 6/8 开始 — Playwright MCP tree (npm install, ~几十 MB, ~1-3min)"
   t0=$(date +%s)
   if [[ -d "${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}" ]]; then
     ok "Playwright MCP tree already present: ${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}"
   else
     "${SCRIPT_DIR}/scripts/install-browser-verify.sh" --write-pin || rc=1
   fi
   echo "步骤 6/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

   # ── Step 7/8: Harbor/Terminal-Bench (agent-bench) ──
   echo ""
   echo "步骤 7/8 开始 — Harbor venv (pip install, ~几十个包, ~1-3min)"
   t0=$(date +%s)
   if [[ -d "${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}" ]]; then
     ok "Harbor venv already present: ${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}"
   else
     "${SCRIPT_DIR}/scripts/install-agent-bench.sh" --write-pin || rc=1
   fi
   echo "步骤 7/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"
   ```
   原"步骤 6/6: AI-DLC skills"改为"步骤 8/8"。两个新安装脚本是否接受
   `--write-pin` 参数、参数名是否一致，实现时必须回读
   `scripts/install-browser-verify.sh` / `install-agent-bench.sh` 的
   实际 `getopts`/`case` 分支确认。

4. **顶层 flag 解析**（`main()` 的 `case "$1" in` 块）：
   ```bash
   --browser-verify) mode="browser-verify"; shift ;;
   --agent-bench) mode="agent-bench"; shift ;;
   ```

5. **`--help` 文本**：在 `--understand-anything` 行之后追加：
   ```
     --browser-verify           deploy the Playwright MCP tree (host step)
     --agent-bench              deploy the Harbor/Terminal-Bench venv (host step)
   ```

6. **mode dispatch**（跟在 `--understand-anything` 的 `exec` 块之后）：
   ```bash
   if [[ "${mode}" == "browser-verify" ]]; then
     exec "${SCRIPT_DIR}/scripts/install-browser-verify.sh" "$@"
   fi
   if [[ "${mode}" == "agent-bench" ]]; then
     exec "${SCRIPT_DIR}/scripts/install-agent-bench.sh" "$@"
   fi
   ```

**存量用户的增量更新路径（G2 的具体机制）**：不新增任何专门的"升级
向导"。用户 `git pull`（拿到含新角色代码的 ai-dlc 仓库）后，只要跑一次
`./install.sh --doctor`，第 2 条里新增的两行 warn 就会原样提示缺什么、
该敲哪条命令——这与今天 OpenDesign/Understand-Anything 对存量用户的
提示方式完全相同，是"复用已验证过的存量用户路径"而不是"发明新路径"。

## 05 反向门

**核实结论（写 PRD 时已用 `grep -n 'install.sh\|opendesign\|understand-anything'
tests/collapse/dt1_gates.sh` 确认）：`dt1_gates.sh` 与 `install.sh` 的
opendesign/understand-anything 接入完全无关**（它审计的是 oracle 删除、
checker registry 消失、gate id 集合等 L1 落地承诺），不存在"扩展现有
断言"这回事——此前的假设是错的，新增一个独立脚本。

- 新建 `tests/collapse/install_sh_tool_wiring.sh`：对
  `opendesign`/`understand-anything`/`browser-verify`/`agent-bench`
  四个工具名跑同一条参数化断言循环（用一个 bash 数组存四个工具名，
  循环体一次写好，不给新工具复制四段断言），每个工具名断言
  `install.sh` 源码里都能 grep 到：
  1. usage 注释里出现 `--<name>`
  2. `run_doctor()` 里出现对应的 `warn "...--<name>"` 告警行
  3. `--help` here-doc 里出现 `--<name>`
  4. mode dispatch 里出现 `exec "${SCRIPT_DIR}/scripts/install-<name>.sh"`
  四项任一缺失即整条脚本失败并报出具体工具名 + 缺失的是哪一项
  （不是笼统的 "FAIL"）。
- 这个新脚本本身要能在两种方向上验证有效：对当前已接好的
  opendesign/understand-anything 跑通过；临时把 browser-verify/agent-bench
  的接入删掉一处（比如注释掉 mode dispatch 那一行）应该让脚本明确报错
  指出具体哪一项、哪个工具——照抄 PR #169 里 `no_direct_tool_exec.sh`
  已经验证过的"两个方向都要证明"的标准，不能只证明"正常情况下通过"。

## 06 验收

- `bash -n install.sh` 语法检查通过。
- `./install.sh --help` 输出包含 `--browser-verify`、`--agent-bench` 两行。
- 在两个 pin 目录都不存在的环境下 `./install.sh --doctor`：退出码保持
  健康路径不受影响（这两条新增 warn 不应导致 doctor 整体判定失败——
  与 opendesign/understand-anything 现状一致，warn 不是 fail），且 stdout
  里能看到两条新的 warn 文案与 remedy 命令。
- 真实执行 `./install.sh --browser-verify` 与 `./install.sh --agent-bench`
  各一次（复用已经验证过的两个安装脚本，本 PRD 不重新装，只验证
  `install.sh` 能正确 `exec` 交接、参数透传正常），随后 `--doctor` 里对应
  的两条 warn 消失、变成 `ok`。
- `./install.sh --bootstrap` 在一个两个 pin 目录都已存在的环境下试跑一次
  （模拟"重复跑 bootstrap 不该重装"），确认新增的步骤 6/8、7/8 都走
  `already present` 分支且不报错；步骤计数文案确认已从 `N/6` 全部改为
  `N/8`。
- 全量 `pytest -q` 与既有 `tests/collapse/*.sh` 门禁不因本次改动回归
  （本次不动 `bin/plan.py`，回归面很小，但仍需真跑一遍确认）。
- 新建的 `tests/collapse/install_sh_tool_wiring.sh` 通过，且经过双向验证
  （正常代码下通过；临时注入一处缺失接入能被正确检出并点名具体工具/项）。

## 07 分期

单期交付，不拆多个 change：六处改动全部集中在 `install.sh` 一个文件，
互相之间没有独立可交付的中间态，拆分期反而增加协调成本。

## 08 风险与残余

- **环境变量名拼写不一致的风险**最高——`AI_DLC_PLAYWRIGHT_MCP_ROOT` /
  `AI_DLC_AGENT_BENCH_ROOT` 必须与 `bin/plan.py` 里的真实常量名逐字对上，
  否则 doctor 告警会在工具明明已装的情况下持续误报。验收清单里的真实
  `--doctor` 前后对比就是为了兜住这个风险，不能只做 grep 层面的静态检查。
- **`--bootstrap` 步骤计数器改动是纯文本改动，容易漏改**（1-5 步的
  `N/6` 文案与新增的 6-8 步不一致）——验收清单里专门有一条核对全部步骤
  文案。
- **残余**：这两个新组件目前仍不在 `(no flags)` 默认安装路径与
  `--all-targets` 路径里（与 opendesign/understand-anything 现状一致）
  ——如果将来希望默认安装就带上它们，需要新的 PRD 单独评估默认安装体积
  膨胀（Chromium + Docker/Harbor 依赖都不小），本 PRD 不做这个决定。

## 09 回滚

六处改动全部是纯追加（新增 flag 分支、新增 warn 块、新增 bootstrap
步骤、新增 help 行、新增 mode dispatch），删除对应新增的代码块即可完全
回到今天的行为，不影响 opendesign/understand-anything 现有路径，不涉及
`bin/plan.py`。
