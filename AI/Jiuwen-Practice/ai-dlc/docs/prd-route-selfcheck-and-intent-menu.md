# PRD · ROUTE 自检广播 + 阶段链自动衔接落地 + 场景/意图建议菜单

> 复盘两次 claude-maas 上的 `/ai-dlc` 实测会话之后发现：四条最初设想的
> "自动化建议"里，两条其实**已经实现**（jiuwenswarm 子 agent 注册、
> codegraph brief autodispatch），只是没有可靠地传播到下游安装目标；
> 一条**已经立项但只做了一半**（phase-chain-automation 的 Phase A 落地
> 了，Phase B——自动衔接——原 PRD §08 明确留给以后）；只有一条是真正
> 从未被记录过的缺口（会话侧从不自检安装是否完整）。本 PRD 认领"以后"
> 那一半，补上真正的缺口，并新增一条委托方追加的需求：把"该走哪条自动化
> 路线"从会话的隐式判断变成一份摆在人面前的候选清单。

- 目标仓库：`<workspace-root>`（`bin/plan.py`、`bin/report.py`、
  `install.sh`）
- 关联：`docs/prd-phase-chain-automation.md`（本 PRD 的 G1 认领其 §08
  "Phase B"）、`docs/prd-codegraph-author-autodispatch.md`（G2/G3 沿用
  同一套"调度不是门禁"范式）、`docs/prd-jiuwenswarm-understand-anything-subagents.md`
  （证实 G4 描述的下游分发问题真实存在过）、`install.sh --doctor`
  （G2 复用其核心检查项，不重新发明）
- 触发来源：一次围绕 `<client-project>` 上 claude-maas + `/ai-dlc` 两次
  实测会话（2026-09-02～2026-09-04）的复盘，以及复盘后委托方（人类）
  当场追加的第二条需求
- 文档日期：2026-09-05 · 优先级：P1 · 目标版本：v0.22.0

---

## 01 调研结论

对着 `<workspace-root>` 的既有代码和文档逐条核对最初的四条建议，结果
跟最初设想有出入，如实记录：

| 原建议 | 现状 | 结论 |
|---|---|---|
| jiuwenswarm 子 agent 注册做成持续对账 | `install.sh` 第 1b 段已经在装/卸载时同步 `understand-anything-plugin/agents/*.md` 到 `~/.jiuwenswarm/agents/`（幂等、`--uninstall` 对称删除） | **已实现**，不是缺口 |
| codegraph brief 自动调度 | `report.py.codegraph_auto_due/codegraph_auto_dispatch` 已存在，`plan.py.cmd_phase`/`cmd_dispatch` 已经接线调用 | **已实现**，不是缺口 |
| 多阶段任务用 initiative 自动衔接 | `plan.py initiative register/advance/status` 已合入（PR #158，Phase A）；但 `cmd_close` 尾部**没有**调用 `advance`——`grep cmd_close` 找不到任何 `initiative` 引用 | **一半实现**：数据契约和命令都在，唯独"close 之后自动触发"这一步原 PRD §08 明确写着"留待以后的 change" |
| ROUTE 阶段自动跑 doctor 自愈 | `install.sh --doctor`/`run_doctor` 只在 `install.sh`（含 bootstrap 结尾的 `run_doctor \|\| true`）里跑；`SKILL.md` 的 L0 首屏和 `plan.py next` 都不在**每次任务调用**时做任何自检 | **真缺口**：两次实测会话都是任务进行到一半、撞见 `plan.py`/`report.py`/`config.yaml` 缺失才发现，`~/.claude-maas/skills/ai-dlc/` 一度只有 `SKILL.md` |

额外发现一个**分发**问题，不是能力缺口：claude-maas 环境里技能装得不
完整这件事，本身说明"canonical 仓库有能力"和"某台机器上真的能用"之间
没有任何对账机制——`targets/*.json`（`targets/claude-maas.json` 等）
登记了安装目标，但没有版本戳、没有任何东西检查"这个目标现在是不是落后
于仓库"。这条本 PRD 用 G4 收尾。

委托方复盘后追加的第二条需求（原话："基于客户的输入，识别任务目标，
基于场景/现状给出不同的流程自动化，或者流程建议让用户选择"）在现有
代码里也有对应先例可抄——`design-pick`（D0 SELECT）已经证明"检索出
候选清单、写清楚每条的取舍、让人/小会话挑"这套模式站得住，只是从未被
用在"任务本身该走哪条路"这一层：今天这个判断完全靠会话读 `SKILL.md`
自己拿主意，拿完主意也只停留在聊天文本里（"路由已初始化，stage=WORK"
这类自我叙述），不落地成任何人能核对的记录。

## 02 目标与非目标

**目标**

- **G1**：认领 `docs/prd-phase-chain-automation.md` §08 的 Phase B——
  `plan.py close` 归档成功之后，若该 change 出现在某个 initiative
  manifest 里，自动调用已经存在的 `initiative advance` 逻辑（复用
  Phase A 的函数，不新写一份）。
- **G2**：`plan.py next`（已经是"问系统下一步做什么"的既有只读入口）
  在给出 `do`/`blocked_on` 之前，先跑一遍 `install.sh --doctor` 核心
  检查的一个子集（`bin/plan.py`/`bin/report.py`/`config/` 是否存在且
  可执行、jiuwenswarm 网关是否可达），不健康时在返回里追加一条
  `advisory`（一句话诊断 + 一条可直接复制执行的修复命令），但绝不拦
  `next` 本身的返回。
- **G3**（委托方追加）：新增 `plan.py suggest --repo <repo> [--change
  <id>] "<自由文本>"`——只读查询，输入用户这句话和仓库当前状态，输出
  一份有序候选路线清单（每条：路线名字、一句取舍理由、选它对应的第一条
  可执行命令），从不替人选，只列清楚。跟 `next`（"这个 change 现在该跑
  什么"）互补而不是重叠：`suggest` 面向"这句话/这个仓库现状，值得考虑
  哪几条不同的路"，可以在**还没有 change id**的时候就用。
- **G4**：`install.sh` 新增 `--check-sync`：比较仓库自己的版本戳（新增
  一个 `VERSION` 文件）跟 `targets/*.json` 登记的每个已安装目标各自的
  `VERSION` 副本，不一致就在 `--doctor` 输出里点名，供人决定要不要在
  那台机器上重跑安装。

**非目标**

- **不在本 PRD 实现"拦截绕开状态机的直接 git 操作"**——两次实测会话里
  代码改完之后都是直接 `git commit`（其中一次紧接着 `vercel --prod`），
  没有经过 `plan.py close` 的合并门。这是真实存在的问题，但方案（给
  用户仓库装 git hook）影响面和风险都明显大于本 PRD 其余四条，需要单独
  评审"拦下 vs 只警告""对哪些仓库生效""如何跟已有的 sandbox/boundary
  机制协同"，本 PRD 只在 §08 记下来，正式设计留给下一个 change。
- `plan.py suggest` 不执行、不写任何 `state.json`/`events.jsonl` 字段、
  不打开任何会话——纯函数式只读查询，这是它和 `design-pick`（会写
  `state.json.design_selection`）的关键区别。
- 不新增、不复活任何 cost/budget 字段（继续遵守 `SKILL.md` 硬性禁令
  #2："Never reintroduce a cost gate..."）。
- 不修改 `report.py deliver`、`plan.py design`、
  `config/collapsed.config.yaml` 的 `planning_threshold_files`（对齐
  `docs/prd-phase-chain-automation.md` §05 的边界声明）。
- G2 的自检**只报告，不自愈**——不自动从 canonical 源复制文件修复目标
  环境；"看见 advisory 之后手动跑 `install.sh`"是人的动作，不是本 PRD
  要交付的能力（收窄范围，避免一个只读检查意外具备写权限）。
- G4 只点名不一致，不做跨主机自动同步安装——那是运维动作。

## 03 不变式

延续仓库现有的 INV-1～INV-19（最近一次落地于
`docs/prd-codegraph-author-autodispatch.md` 的 INV-14～16），从
INV-20 继续编号：

- **INV-20**（对齐 Phase A 的 INV-2）：G1 的触发前提跟 Phase A 原样
  一致——只有 `plan.py close` 成功合并+归档之后才触发 `advance`；
  `close` 因未获批准而未执行、或 archive 命令非零退出，一律不触发。
  本 PRD 不改判据本身，只是把 Phase A 已经写好的函数接上调用点。
- **INV-21**（对齐 INV-12/INV-14）：G2 的自检失败绝不阻塞
  `plan.py next` 或任何其他子命令的返回——降级成一条 `advisory`
  字段，跟"注册失败不阻塞 codegraph build""codegraph 派发失败角色照常
  派发"同一立场。
- **INV-22**：G2 的自检本身只读，不做任何自愈/自动复制文件的动作——
  这是范围收窄后的结果（评审中曾设想"自动从 canonical 源同步"，收窄为
  只报告，理由见 §02 非目标）。
- **INV-23**：`plan.py suggest` 不修改任何文件、不写任何状态字段、不
  触发任何会话或 dispatch；可以在离线/网关不可达的环境下运行（网关不
  可达本身也是它可能给出的一条候选理由，而不是它自己的前提条件）。
- **INV-24**：`suggest` 的候选列表最多 4 条（参照 `review.max_axes: 3`
  再放宽一档，避免选项本身变成新的认知负担）；候选数量的上限是配置项，
  超过时按分数截断，从不静默调整这个上限本身。
- **INV-25**：G4 的版本对账只读——`--check-sync` 发现不一致时只在
  `--doctor` 输出里点名，从不自动改动任何已安装目标的文件。

## 04 目标架构

**G1（`bin/plan.py` · `cmd_close`）**
在其现有的"merge → archive → cleanup"尾部之后，新增一步：复用
`docs/prd-phase-chain-automation.md` 已经定义、Phase A 已经实现的
initiative 查找+`advance`调用（`plan.py initiative` 内部函数，非
subprocess 二次调用自己）。严格在归档成功**之后**执行，失败不影响已
写盘的归档结果。这一步的代码量应该很小——Phase A 已经把 `advance` 的
全部逻辑写好，G1 只是把它接到 `close` 的尾部，是原 PRD 自己规划好的
下一步。

**G2（`bin/report.py` 新函数 + `plan.py.cmd_next`）**
新函数 `route_doctor_advisory(repo) -> str | None`，直接调用
`install.sh --doctor` 现有检查逻辑的一个子集（文件存在性 + 可执行位 +
网关连通性三项，不含"验证器能否判别"那类需要真实跑一次 dispatch 的
重检查——`next` 是高频只读调用，不能背上一次网络往返的延迟）。
`cmd_next` 组装返回值时，若 `route_doctor_advisory` 非空，追加进
返回的 `advisory` 字段（新字段，纯增量，不改变现有 `stage`/
`blocked_on`/`do`/`then`/`not_yet` 的语义）。

**G3（`bin/plan.py` 新子命令 `suggest`）**
```
plan.py suggest --repo <repo> [--change <id>] "<free text>"
```
内部一个 `score_candidates(text, repo, state)` 函数，复用
`_extract_change_keywords` 已有的 IDF/CJK-bigram 检索机制（不新造一套
分词逻辑）对一组预置候选路线打分：

| 候选路线 | 触发信号（示例） |
|---|---|
| `inline_quick_fix` | 文本暗示单文件/机械改动；`classify_target` 判定小 |
| `planned_full_pipeline` | 文本提到多个模块/"梳理架构"；`codegraph-scope` 适用 |
| `prd_spec_only` | 文本明确要求"先出 PRD/spec，人补完再实施" |
| `design_first` | `design-scope` 判定 surface 是 web/deck |
| `deploy_extra_gate` | 文本或最近改动带"部署/上线/production/prod" |

每条候选输出 `{name, why, first_command}`，按分数降序、最多 4 条
（INV-24）。**不选**——只列；`--change <id>` 可选，带上时候选理由里会
引用该 change 已有的 `state.json`（比如已经做过 `design-pick`，
`design_first` 的理由就变成"已经选过模板，继续 D1"而不是"考虑先选模板"）。

**G4（`install.sh`）**
新增顶层文件 `VERSION`（单行 semver，本 change 落地时写 `0.22.0`）。
`--check-sync`：遍历 `targets/*.json` 登记的每个安装目标路径，读取该
目标目录下同名的 `VERSION` 副本（安装时随其他文件一起复制），跟仓库
自己的 `VERSION` 比较，不一致就在 `--doctor` 的输出里追加一行点名
（目标路径 + 两边版本号），退出码不因此变化（点名不是失败）。

## 05 反向门

- G1：沿用 Phase A 已有的三条（`close` 未获批准不触发 / archive 非零
  退出不触发 / initiative 为 `blocked` 不触发）——本 PRD 不新增判据。
- G2：网关不可达、`--frames-file` 离线测试模式下，`route_doctor_advisory`
  直接返回其中一条固定 advisory 文案，不重试、不阻塞、不计入任何重试
  预算（跟 codegraph INV-16 的"不设重试计数器"同一立场）。
- G3：候选打分全部为 0（自由文本太短或无法识别）时返回空列表 + 一句
  "看不出偏向，按 `plan.py next` 的默认判断走"，不是报错，也不硬凑一条
  候选。
- G4：目标路径在 `targets/*.json` 里登记但本地已不存在（比如那台机器
  被下线）——跳过，不报错、不要求先清理登记。

## 06 验收

- 单元测试：`route_doctor_advisory` 覆盖"三项检查全过→None"、"任一项
  缺失→非空 advisory 字符串含具体缺失项和修复命令"两类；`score_candidates`
  覆盖 §04 表格每一行的触发信号，以及"全零分→空列表"的反向门。
- 集成测试（沿用 `monkeypatch.setattr(plan, ...)` 既有套路）：`cmd_close`
  在 change 已注册 initiative 时确实调用了一次 `advance`，未注册时
  字节级不变（对齐 Phase A INV-6 的既有断言方式）；`cmd_next` 返回体
  在两种健康状态下分别带/不带 `advisory` 字段。
- 回归：全量 `pytest` + `tests/collapse/dt1_gates.sh`（G1/G3 各新增一个
  顶层子命令分支，`dt1_gates.sh` 预期需要更新一条门禁清单，需要确认）。
- 人工验收（依赖真实环境，记录在此留给有权限的人执行）：在 claude-maas
  上重新走一遍本次复盘用的两个真实场景（"opencode 多模型可复用项目"、
  "openjiuwen 效率优化三阶段"），确认 `plan.py next` 在技能装不全时
  给出 advisory 而不是让会话自己中途发现；确认三阶段场景下 Phase 1
  的 `close` 之后 Phase 2 任务骨架被自动创建。

## 07 分期

| Phase | 内容 | 风险 |
|---|---|---|
| A（本 PRD + SPEC 覆盖） | G1（认领已有设计）+ G2（只读 advisory）+ G3（`suggest` 只读查询）+ G4（`--check-sync` 只读点名） | 低——全部只读或复用既有函数，无新的写路径、无新的自动合并/自动执行 |
| B（未来，单独立项） | §02 非目标里记录的"拦截绕开状态机的直接 git 操作"；G2 从"只报告"升级为"人确认后一键自愈";G4 从"点名"升级为"一键同步" | 中～高——涉及给用户仓库装 hook、涉及写权限，需要单独的安全/边界评审 |

## 08 风险与残余

- G3 的候选打分是启发式的，不是模型判断——复杂/模糊的自由文本可能落进
  "全零分"反向门，交回 `plan.py next` 兜底；这是有意的保守设计，不是
  待修的 bug。
- G1 依赖的前提是 initiative manifest 已经存在（`register` 仍是手动
  调用）——本 PRD 不处理"从 PRD/proposal.md 里自动识别多阶段结构并自动
  `register`"，那是比 G1 大得多的另一个判断，留给 Phase B 或更后面。

## 09 回滚

四条都是纯增量：`cmd_close` 尾部一次函数调用（G1）、`report.py` 一个
新函数 + `cmd_next` 一个新字段（G2）、`plan.py` 一个新子命令（G3）、
`install.sh` 一个新标志位 + 一个新增的 `VERSION` 文件（G4）。删除对应
代码、删掉 `VERSION` 文件，行为回到今天；不改动任何既有任务的历史记录，
不影响 Phase A（initiative register/advance/status）已经落地的行为。
