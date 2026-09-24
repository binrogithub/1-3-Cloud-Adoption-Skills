# PRD · codegraph 后端选型：pin Understand-Anything，安装免选择

> 编译产物型工具带着操作系统层面的二进制兼容风险——
> 这次选的东西没有这堵墙：它不是二进制，是一份技能树。

- 目标仓库：`<workspace-root>`（本仓库自身，`bin/plan.py`）
- 关联：`docs/prd-codegraph-role.md`（Phase A/B 已合入 master，本 PRD 是选型 + 接线）
- 文档日期：2026-09-04
- 优先级：P1

---

## 01 选型过程

prompt/skill 驱动的工具优先于编译产物型工具。前者是一份技能说明（markdown
指令 + sub-agent 定义），由 LLM 会话读取并执行，不产生任何原生二进制绑定，
因此不依赖特定 glibc 版本、不需要本地编译工具链，没有操作系统层面的二进制
兼容风险。这台机器是 CentOS 8 / glibc 2.28，编译产物型工具的原生绑定通常
针对 glibc 2.29+（Ubuntu 20.04+ 一类现代发行版）编译，在这台机器上跑不起来；
升级系统 glibc 风险极高（可能拖垮整台机器上跑着的其它服务），不在考虑范围。
因此选定 prompt/skill 驱动型工具（Understand-Anything，见 §02）。

## 02 最终选型：Understand-Anything

`Egonex-AI/Understand-Anything`（MIT，Claude Code 官方插件市场格式
`.claude-plugin/`）。核实过的关键事实：

- **没有编译产物，没有 glibc 依赖**——是一份 `SKILL.md` + sub-agent
  markdown 组成的技能树（`understand-anything-plugin/skills/`、
  `understand-anything-plugin/agents/`），靠一个 LLM 会话读这些指令、
  自己去扫代码、自己写 JSON——这正是 jiuwenswarm 派发会话的既有工作
  方式，不是"调用一个外部工具"，是"派发一个角色去读一份技能说明"。
- 建图技能 `understand`/`understand-knowledge`：多个子 agent
  （`project-scanner.md`、`file-analyzer.md`、`architecture-analyzer.md`
  等）协作扫描，产出 `.ua/knowledge-graph.json`（节点：file/function/
  class/module/...；边：imports/calls/depends_on/...）。
- 影响分析技能 `understand-diff`：给定改动文件列表，在已有图谱里查
  1-hop 关联节点和边，产出影响面——**跟我们 `codegraph brief` 要做的事
  几乎一模一样**，直接复用它的方法论，不用自己再发明一套查询逻辑。
- 图谱新鲜度：`understand-diff` 自己会比对 `knowledge-graph.json` 里记的
  `gitCommitHash` 和当前 HEAD，判断图是否过期——这部分不需要我们自己
  实现。

## 03 需要修正的架构假设（对齐 `docs/prd-codegraph-role.md`）

Phase A 把 `codegraph build` 设计成"确定性、无会话派发的步骤（像 D0
SELECT）"——这个假设是针对"本地二进制工具，跑一下就出索引"设的，**不
成立了**。Understand-Anything 的建图本身就是一整个多 agent LLM 流水线，
跟 D1 SPECIFY（ui-designer 读 SKILL.md 产出 design/ 五个文件）是同一
类操作，不是 D0 SELECT 那一类。

修正：`cmd_codegraph_build` 从"shell 出去调二进制"改成"会话派发"，
复用 `run_codegraph_session` 那套机制（Phase B 已经写好，直接复用，不
重新发明）。

## 04 目标架构

**安装**：`scripts/install-understand-anything.sh`，照抄
`scripts/install-opendesign.sh` 的既有模式（一次性 pin，`.aidlc-pin.json`
记 tag + 整棵树的摘要，装到固定路径 `/opt/understand-anything`，CC 侧
只读挂载）：

1. `git clone --branch <pinned-tag> --depth 1 https://github.com/Egonex-AI/Understand-Anything.git /opt/understand-anything`
   （pin 到写这份 PRD 时的最新 tag——实施时查一次当前最新 release/tag
   固定下来，不跟 `main` 分支走）。
2. 写 `.aidlc-pin.json`（tag、commit sha、整棵 `understand-anything-plugin/`
   目录的 tree_sha256），跟 open-design 的格式一致。
3. `chmod -R a-w /opt/understand-anything`（只读，同 open-design 的
   `ReadOnlyPaths` 思路——这里先做文件权限层面的只读，systemd 层面的
   `ReadOnlyPaths=` 是网关侧配置，不在这个仓库改动范围内）。
4. **不问用户选择任何东西**——固定装这一个工具、固定这个路径、固定这个
   pin 版本，跟 open-design 的安装方式对齐（同样是"operator 一次性
   host step"，不是每次任务都重新决定）。
5. 接入 `install.sh`（照 `install-opendesign.sh` 在 `install.sh:1126`/
   `1224` 被调用的方式，同样接一处），使其成为默认安装流程的一部分,
   不需要额外手动步骤。

**`cmd_codegraph_build`（改写，替代 Phase A 的确定性版本）**：
- 读取 `/opt/understand-anything/understand-anything-plugin/skills/understand/SKILL.md`
  （或 `understand-knowledge`，实施时确认哪个是入口技能）全文构造
  prompt，dispatch `run_codegraph_session`，cwd 设为目标 repo，让角色
  按技能说明扫描并写出 `.ua/knowledge-graph.json`。
- 若 `.ua/knowledge-graph.json` 已存在且 `gitCommitHash` 与当前 HEAD
  一致（技能自己的新鲜度判断逻辑），可以让角色自己判断跳过重建——这部分
  行为交给技能本身的既有逻辑，我们不重复实现。
- pin 路径不存在（没装）→ 跟现有反向门一致：`codegraph_state:
  unavailable`，不阻塞任务。

**`cmd_codegraph_brief`（沿用 Phase B 框架，改查询方法论）**：
- prompt 改为引用 `/opt/understand-anything/understand-anything-plugin/skills/understand-diff/SKILL.md`
  的方法论：读 `.ua/knowledge-graph.json`、按改动文件 grep 匹配节点、
  查 1-hop 边——不是让角色自己发明查询方式，是让它照抄这份已经验证过
  的方法论。
- 产出仍然是我们自己的 `codegraph/impact-brief.md`（格式沿用
  `prd-codegraph-role.md` §06），不是直接照搬 `.ua/knowledge-graph.json`
  的原始结构——那个文件是给机器查的，`impact-brief.md` 是给 author
  角色读的摘要。

## 05 不变式（新增，延续 `prd-codegraph-role.md` 的既有几条）

- **INV-8** 安装脚本不产生任何交互式提示——固定工具、固定版本、固定
  路径，运行即完成，不需要人在场回答问题。
- **INV-9** `.ua/knowledge-graph.json`、`codegraph/impact-brief.md` 都
  不计入 `landed_files`（延续 `prd-codegraph-role.md` INV-2 的立场，
  `.ua/**` 也要加进 `product_excludes`）。
- **INV-10** pin 的技能树只读——CC 侧不得写入
  `/opt/understand-anything`，任何"角色觉得技能说明有问题"都是人工
  升级 pin 版本的事，不是运行时自己改说明文件。

## 06 反向门

- 未安装（pin 路径不存在）→ `codegraph_state: unavailable`，不阻塞，
  沿用 Phase B 已有逻辑。
- pin 校验失败（`.aidlc-pin.json` 摘要跟磁盘内容对不上——比如被意外
  改动）→ 拒绝派发，报错说明 pin 不匹配，不静默用一份可能被篡改的
  技能说明。
- git clone 失败（网络问题）→ 安装脚本本身报错退出，不留半装状态。

## 07 分期

| Phase | 内容 | 风险 |
|---|---|---|
| C1 | `scripts/install-understand-anything.sh` + 接入 `install.sh`，纯安装，不改 `cmd_codegraph_build`/`brief` | 低 |
| C2 | `cmd_codegraph_build` 改写为会话派发；`cmd_codegraph_brief` 的 prompt 引用 `understand-diff` 方法论 | 中——改动已合入 master 的 Phase A/B 代码，需要回归验证 |

本 PRD 覆盖 C1 + C2；两者可以在同一轮委托里一起做，因为 C2 直接依赖
C1 装好的东西才能测。

## 08 风险与残余

- Understand-Anything 的建图流水线（多个子 agent 协作）比原来设想的
  "跑个二进制"重得多，一次完整扫描的耗时/token 成本没有实测数据——
  实施时用一个小仓库先测一次，把耗时记进交付报告，不要假设它跟
  Phase A 原来设想的"轻量确定性操作"一样便宜。
- pin 到哪个具体 tag，实施时才能查到当时的最新版本号——本 PRD 不点名
  版本号，交给实施时锁定并记录。

## 09 回滚

`scripts/install-understand-anything.sh` 未运行过 → `/opt/understand-anything`
不存在 → `codegraph build`/`brief` 走既有的 `unavailable` 反向门，行为
回到 Phase A/B 刚合入时的状态。删除安装脚本、`install.sh` 里那一行调用、
以及 `cmd_codegraph_build` 里指向该路径的读取逻辑，即可完全回退到
Phase A 的确定性设计（虽然那个设计本身也没有实际可用的二进制可指向）。
