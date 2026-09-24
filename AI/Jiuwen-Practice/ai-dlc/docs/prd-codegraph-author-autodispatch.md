# PRD · codegraph brief 自动调度接入 author 派发

> design 的自动派发是"补救"——代码写完了，deliver 时才想起来配一份设计。
> codegraph brief 不能这样晚：它是给 author 动笔之前用的输入，等
> deliver 阶段再触发就没意义了。同一套调度模式，不同的挂钩点。

- 目标仓库：`<workspace-root>`（`bin/plan.py`、`bin/report.py`）
- 关联：`docs/prd-codegraph-role.md`（Phase A/B）、
  `docs/prd-codegraph-understand-anything-backend.md`（C1/C2）、
  `docs/prd-jiuwenswarm-understand-anything-subagents.md`（子 agent 注册）
- 文档日期：2026-09-04
- 优先级：P1

---

## 01 调研：既有的"自动触发"先例，以及为什么不能照抄挂钩点

`report.py` 里已经有一套现成的自动调度模式——`design_auto_dispatch`/
`design_auto_due`（`design-autodispatch` 那份 PRD 的产物）。读了一遍，
这套模式本身值得抄，但挂钩点不能照抄：

**调度模式**（值得抄）：
- `design_auto_due()`：一条判定链——surface 是否 applicable、有没有签名
  记录、有没有人工记录跳过、有没有已完成的先前尝试（上限 2 次）——
  返回 `(due: bool, why_not: str)`，不是"要不要跑"简单布尔，是带理由的
  判定。
- `design_auto_dispatch()`：**先在 `planning.json` 写下"尝试中"记录，
  再真正开会话**——即使进程被杀（这个环境这学期天天在发生），也留得下
  "试过"这个事实，不会无限重试。
- 调用处（`cmd_deliver` 里那段"the design auto-dispatch (N1):
  scheduling, not gating"注释）：派发结果**从不改变 `delivered`**——
  这是调度，不是门禁，跟 codegraph 一直以来的立场（PRD §07 反向门：
  "不阻塞任务"）完全一致。

**挂钩点不能照抄**：design 的自动派发挂在 **`report.py deliver`**——
在 REPORT 阶段，代码已经写完之后，是"漏了就补"的补救路径（design v2
架构本身也说了这是"A2 retrofit 路径"，主路径是 WORK 阶段主会话直接
写）。codegraph brief 的存在理由是"author 写 proposal 之前先给它看
影响面"——如果挂在 deliver 阶段触发，author 早就已经凭自己读代码写完
proposal 了，简报送到时黄花菜都凉了。**必须挂在 author 派发开始之前**，
即 WORK 阶段最前面，`docs/prd-codegraph-role.md` §04 从一开始就是这么
写的（"CODEGRAPH 挂在 WORK 最前面"）——只是 Phase B 实施时把"接入
author 派发"这一步显式推迟了（发现 `prepare()` 走的是网关注册的
authoring skill，不是 `plan.py` 自己拼的 prompt 字符串，一度以为要动
不在改动范围内的东西）。这次把这一步做完，但避开那个深坑——见 §03。

**角色名不是写死的常量**：查过 `bin/plan.py`，没有任何地方硬编码
`"author"` 这个角色名字符串——角色名是数据，从 artifact 图（N3 graph
派发的产物）里读出来，按"一个角色一份产物"的惯例，很可能是
`proposal`/`spec`/`design`/`tasks` 这类按产物命名的角色，而不是一个
笼统的 "author"。因此本 PRD **不按角色名过滤**"只在派发 proposal 角色
时触发"——按"这个 change 是第一次进入角色派发池"来触发，跟具体是哪个
角色名无关，更稳，不依赖一个可能不稳定的角色名字符串。

## 02 场景调研：哪些情况该自动触发

对齐 `docs/prd-codegraph-role.md` 已经定下的判据（§07 反向门 + §02
适用性），本 PRD 把"该不该自动触发"收拢成一条判定链（跟
`design_auto_due` 同构）：

| 条件 | 触发？ | 理由 |
|---|---|---|
| `route == "planned"` 且 `codegraph-scope` 适用（有已存在文件） | ✅ 触发 | 唯一的主场景——`docs/prd-codegraph-role.md` 从第一版就是这么定的 |
| `route == "inline"` | ❌ 不触发 | 已有反向门：任务量小，查图收益低于开销 |
| `codegraph-scope` 不适用（纯新文件） | ❌ 不触发 | 没有已存在的图可查 |
| 已经为这个 change 尝试过（`planning.json` 有 `codegraph_brief` 记录，不论成功失败） | ❌ 不触发 | 幂等——`cmd_phase`/`cmd_dispatch` 可能被多次调用（resume 场景），不重复派发 |
| understand-anything pin 不可用 | ❌ 不触发（走已有 `unavailable` 反向门） | Phase B 已有逻辑，不新增 |
| 人工已经用 `plan.py codegraph brief` 手动跑过 | ❌ 不重复触发 | 跟"已经尝试过"是同一条件——手动跑的结果同样写 `planning.json.codegraph_brief`，自动调度识别到就跳过 |

**不新增场景**：没有发现"设计角色不同、需要不同触发条件"的情况——
`docs/prd-codegraph-role.md` 原来那条"仅 planned 且适用"的判据已经是
完整答案，本 PRD 的调研结论是**确认既有判据够用，不用加新条件**，
真正要做的是把"谁来触发、什么时候触发"从"没人触发"变成"自动触发"。

## 03 目标架构

**避开的坑**：不修改、不依赖 `prepare()` 内部逻辑或它读取的网关注册
authoring skill——那部分继续保持"黑盒"，本 PRD 的改动全部落在
`plan.py` 自己的编排层（`cmd_phase`、`cmd_dispatch`、`_run_role`）。

**新函数**（`bin/report.py`，紧挨着 `design_auto_due`/
`design_auto_dispatch` 写，命名对称）：

- `codegraph_auto_due(task_dir, repo, state) -> tuple[bool, str]`：
  判定链见 §02 表格。读 `planning.json.codegraph_brief` 判断"是否已
  尝试过"（Phase B 的 `cmd_codegraph_brief` 已经把结果写在这个键下，
  直接复用，不新增字段）。
- `codegraph_auto_dispatch(task_dir, repo, state, change) -> dict`：
  跟 `design_auto_dispatch` 同一套"先记尝试、再派发"纪律，内部通过
  subprocess 调 `plan.py codegraph brief`（同 E4：report 不 import
  plan），不是直接调用 Phase B 的 Python 函数——工具（`plan.py`）编排
  会话，`report.py` 不越界直接开会话。

**挂钩点**（`bin/plan.py`）：
- `cmd_phase()` 开头（角色派发池启动前）：调 `codegraph_auto_due` +
  `codegraph_auto_dispatch`（若 due）——覆盖"一次性派发一批角色"的
  主路径。
- `cmd_dispatch()` 开头（单角色派发前，跳过 offline judge 模式那条
  测试专用分支）：同样调一次——覆盖单角色手动/脚本化派发的路径。
- `_run_role()`（`prepare()` 拿到 `prompt` 之后、`dispatch_role()` 之前）：
  若 `repo/codegraph/impact-brief.md` 存在，把
  `docs/prd-codegraph-role.md` §04 定的那句"先读
  codegraph/impact-brief.md（如果存在）"追加进 `prompt`——不管有没有
  刚触发自动派发，这一步都做（文件是之前哪次派发写的、这次自动触发写
  的、还是人工手动跑的，一视同仁，只看文件在不在）。

## 04 不变式

- **INV-14**（对齐 design 的 J3）：codegraph 自动派发的结果**不影响**
  `cmd_phase`/`cmd_dispatch` 的返回码或角色派发本身是否继续——纯调度，
  不是门禁，派发失败只是没有简报可读，角色照常派发。
- **INV-15**（对齐 design 的 J2/N4）：派发前先写"尝试中"记录到
  `planning.json.codegraph_brief`，即使进程被杀（`_plain_run`/
  `_supervised_run` 的静默杀死探测已经证明这个环境常发生）也留得下
  "试过"的事实，不会每次 `cmd_phase` 重入都重新派发一次。
- **INV-16**：自动触发只发生一次（幂等），不设"最多 N 次重试"计数器
  ——跟 design 的"最多 2 次"不同，因为 codegraph brief 失败的后果只是
  "author 拿不到简报，自己读代码"，不像 design 缺失会影响交付判定，
  不需要重试预算。
- 延续既有的 INV-8~INV-13（安装免交互、`.ua/**`/`codegraph/**` 不计入
  `landed_files`、pin 只读校验）——本 PRD 不改动那部分。

## 05 反向门

- 沿用 `docs/prd-codegraph-role.md` §07 的三条（inline 不触发、纯新
  文件不触发、build 失败降级不阻塞）——本 PRD 新增的是"已尝试过不重复
  触发"这一条（§02 表格倒数第二行）。
- `cmd_phase`/`cmd_dispatch` 在离线测试模式（`--frames-file`，
  `cmd_dispatch` 已有的 test hook）下**不触发**自动调度——那条路径
  本来就不真的开会话，不该在测试夹具上意外触发真实派发。

## 06 验收

- 单元测试：`codegraph_auto_due` 覆盖 §02 表格每一行（applicable+
  planned+从未尝试 → due；inline → 不 due；不 applicable → 不 due；
  已有 `codegraph_brief` 记录（无论 written true/false）→ 不 due）。
- 集成测试（mock `codegraph_auto_dispatch`，同 Phase A/B 测试用
  `monkeypatch.setattr(plan, ...)` 的既有套路）：`cmd_phase`/
  `cmd_dispatch` 在 due 时确实调用了一次派发，在角色派发本身失败/成功
  两种情况下都不受影响；`_run_role` 在 `codegraph/impact-brief.md`
  存在时确实把指针句子追加进了传给 `dispatch_role` 的 prompt。
- 回归：全量 `pytest` + `tests/collapse/dt1_gates.sh`（这次没有新增
  顶层 `plan.py` 子命令，`dt1_gates.sh` 预期不受影响，但仍要跑一遍
  确认）。

## 07 风险与残余

- `cmd_phase`/`cmd_dispatch` 都要加同一段判定+派发逻辑，有轻微重复——
  可以抽成一个共享的小函数（如 `_maybe_auto_codegraph(change, repo,
  task_dir)`）供两处调用，避免两份判定逻辑长期漂移不一致；实施时决定
  是否值得这层抽象。
- codegraph brief 的耗时（Understand-Anything 建图流水线，PRD
  §08 风险已经记过"比设想的重"）会直接叠加进 author 派发前的等待——
  这是设计本身的取舍（PRD 一直以来的立场：先有输入再动笔），不是本
  PRD 要解决的性能问题，需要时留给以后的缓存优化（`docs/prd-
  codegraph-role.md` §08 Phase C）。

## 08 回滚

纯新增：两个 `report.py` 函数、`cmd_phase`/`cmd_dispatch` 里各一段
调用、`_run_role` 里一段 prompt 追加。删除这几处，行为回到"codegraph
brief 只能人工用 `plan.py codegraph brief` 手动触发"的现状，不影响
已经落地的 Phase A/B/C1/C2 骨架。
