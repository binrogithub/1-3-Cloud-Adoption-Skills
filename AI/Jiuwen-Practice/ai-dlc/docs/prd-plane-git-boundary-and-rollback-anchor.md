# PRD · plane 根目录的 git 边界失灵 + 无法兑现的回滚锚点

> 两个不相关的失效凑在同一次评估里被发现，但根因完全独立——一个是
> 「调用方身份和 plane 目录所有权对不上」，一个是「这个仓库的历史根本
> 装不下它承诺的锚点」。合并成一份 PRD 只是因为都小、都不阻塞任何人，
> 分开做反而增加流程开销。

- 目标仓库：`<workspace-root>`（`bin/plan.py`、`SKILL.md`、
  `tests/collapse/dt1_gates.sh`）
- 关联：上一份评估（48 个 collapse 门禁全量复跑，18 红）、
  `docs/prd-openspec-author-conduit.md`（同一轮评估发现的第三个根因，
  已单独立项）
- 文档日期：2026-09-05 · 优先级：P1 · 目标版本：v0.24.0

---

## Part A · plane 根目录的 git dubious-ownership

### 01 问题

`cmd_migrate`（N6）把 `openspec/` 搬到 `/var/lib/aidlc/specs/<repo-id>`
后，把这棵树 `chown` 给 `swarm:swarm`、`mode 0750`（`docs/plane-runtime.md`
既有设计，本 PRD 不改）。但调用 `plan.py` 的进程（这台机器上是 root，
其他环境可能是别的账号）不是 `swarm`，git 2.36+ 的 CVE-2022-24765
防护会拒绝对"不属于当前用户"的仓库做任何操作：

```
fatal: detected dubious ownership in repository at '<plane_root>'
```

**实测确认的影响面**：4 个 collapse 门禁（`d3_plan_boundary`、`l7_sweep`、
`l7_target_safety`、`open_plane`）在补齐 openspec-author 之前和之后
复跑结果一致——独立根因，不受那份 PRD 影响。

**其中一个是静默降级，比单纯报错更麻烦**：`_run_role`（2665-2685）里
的 boundary baseline 快照失败时，返回的不是拒绝，而是
`{"boundary": "unknown"}`（`EXIT_INCONCLUSIVE`）——这是一条安全相关的
判定，静默变成"不知道"，而不是"失败并停下"。

### 02 调研结论

实际会调用 git 且目标路径可能是 plane_root（或其派生路径）的地方，只有
两类，一共 3 个函数，而不是全文件 29 处 git 调用都相关（那 29 处大多
数是对目标仓库 `--repo` 或 `/opt/open-design`、`/opt/understand-anything`
这类只读 pin 树操作，所有者是调用方自己或世界可读，不受影响）：

| 函数 | 行号 | 操作的路径 |
|---|---|---|
| `cmd_sweep` | 2272、2299 | `root = plane_root(repo)` |
| `_run_role`（boundary baseline） | 2681 附近 | `tree`，split-workspace 时是 plane 内的工作副本 |
| `boundary_scan` | 1317 附近 | 经 `git_status_paths(repo)` |

三处底层都收敛到同一个函数：`git_status_paths(repo)`（1285），以及
`cmd_sweep` 里两处直接 `run(["git", "-C", str(root), ...])`。**修复面
比最初估计的小得多——不需要碰全部 29 个 git 调用点，只需要碰这一个
共享函数 + `cmd_sweep` 的两处直接调用。**

git 自己对这个场景的标准答案是 `-c safe.directory=<path>`——单次进程
内的临时配置覆盖，不写入任何文件、不影响该进程之外的任何 git 调用、
不影响机器上其他用户或进程。这正是决策记录里选定的方向（②，拒绝
全局 `git config --global`）。

### 03 目标与非目标

**目标**

- **G1**：新增 `git_run(args: list[str], repo: Path, ...) ->
  subprocess.CompletedProcess`，行为等价于现有 `run(["git", "-C",
  str(repo)] + args)`，但总是带上 `-c safe.directory=<repo>`（作为
  `git` 的第一个参数，在子命令之前）。
- **G2**：`git_status_paths()` 改为内部调用 `git_run`，不再自己拼
  `run(["git", "-C", ...])`。
- **G3**：`cmd_sweep` 里 2272、2299 两处直接调用同样换成 `git_run`。
- **G4**：boundary baseline 快照失败时（`_run_role` 2681 附近）区分
  两种原因——"目标目录不存在/不可读"（维持现有 `EXIT_INCONCLUSIVE`
  + `"boundary": "unknown"`，这确实是无法判定）与"git 因所有权拒绝"
  （用 G1/G2 修完之后，这一支路径理论上不应再触发；若仍触发，说明
  `safe.directory` 覆盖本身失败，应报为明确的错误而不是"unknown"）。

**非目标**

- 不改 `cmd_migrate` 的 chown/mode 逻辑——所有权隔离本身是设计意图
  （对齐 `axis.security.refuses`），本 PRD 只解决"调用方合法读取
  plane 侧内容时被 git 自己的保护机制误伤"，不解决/不触碰真正的权限
  边界。
- 不改任何**目标仓库**（`--repo`）自身的 git 调用——那些路径的所有者
  就是调用方，从不触发这个问题，混进 `-c safe.directory` 没有意义。
- 不写全局 `~/.gitconfig`，不新增环境变量，不新增配置项。
- 不处理"调用方本身就该被拒绝"的场景（比如误把别人的 plane 目录当
  自己的）——`safe.directory` 只解决"确实是同一条流水线内、自己
  chown 出来的目录，git 认错人"这一种情况，不放宽任何真正的越权。

### 04 不变式

延续既有编号（`docs/prd-openspec-author-conduit.md` 用到 INV-30），
从 INV-31 继续：

- **INV-31**：`-c safe.directory=X` 只在目标路径 X 恰好是本次调用
  操作的那个 plane 路径时使用，且只作为该次子进程调用的参数，从不
  写入任何配置文件、从不设置环境变量、从不影响调用它的这一次
  `git_run` 之外的任何进程。
- **INV-32**：`git_run` 是这个仓库里唯一允许构造"针对 plane 路径的
  git 调用"的入口——新增的、需要在 plane 路径上跑 git 的代码，必须
  经过它，不得再手写 `run(["git", "-C", ...])`。
- **INV-33**：G4 的"unknown"与"明确错误"两种失败必须在返回结构里
  用不同字段/不同文案区分，人或后续代码不能靠猜测分辨——沿用这个
  仓库对"降级状态必须可诊断"的一贯要求。

### 05 反向门

- 目标路径不是 plane_root 也不是其派生路径（比如普通的 `--repo`）→
  不应该、也不需要用 `git_run`，维持现有 `run()` 直接调用。
- `safe.directory` 覆盖后 git 仍然失败（真的损坏、真的不是 git 仓库）
  → 照旧报错，不因为加了这个 flag 就把真实错误也吞掉。

### 06 验收

- 单元：`git_run` 构造出的 argv 里 `-c safe.directory=<repo>` 出现在
  `-C` 之前；对一个所有者不同的临时目录跑 `git_run(["status"], ...)`
  能成功（对照：直接 `run(["git","-C",...])` 在同样目录上失败）。
- 门禁回归：`d3_plan_boundary`、`l7_sweep`、`l7_target_safety`、
  `open_plane` 四个从 FAIL 转 PASS；其余门禁不受影响。

### 07 回滚

新增一个函数 + 两处调用点替换，删除即回到今天。不改变任何已有行为
在"同所有者"场景下的输出（`safe.directory` 覆盖对同所有者的仓库是
no-op）。

---

## Part B · dt1_gates.sh 的回滚锚点在本仓库结构性不可达

### 08 问题

```
git cat-file -e v0.8.0:bin/oracle.py
  || FAIL: v0.8.0:bin/oracle.py missing — deletion has no rollback anchor
```

`git tag`（本地）、`git ls-remote --tags origin`（远程）都是空，
`git log --oneline --all -- '*oracle.py'` 在本仓库整条历史里找不到
一次提交碰过这个文件。这不是"标签被误删"，是**这份仓库本身没有携带
它自称携带的历史**——`SKILL.md` 的 "Retired (rollback anchors)" 一节
承诺 `v0.8.0` 能找回 `bin/oracle.py`，但这份承诺属于这份代码更早、
未随重新发布带过来的谱系。

### 09 目标与非目标

**目标**

- **G5**：`dt1_gates.sh` 的第 6 项检查前先探测锚点**在当前仓库历史内
  是否可达**（`git cat-file -e <tag>` 本身失败于"tag 不存在"时，
  与"tag 存在但内容对不上"要分开报）：
  - tag 不存在于 `git tag` 列表 → 记为
    `SKIP: v0.8.0 anchor not carried by this repo's history (republished copy) — see SKILL.md`，
    不计入失败，不计入通过，单独一行,门禁整体判定不受影响。
  - tag 存在但 `git cat-file -e v0.8.0:bin/oracle.py` 失败 → 维持
    现状，判为 `FAIL`（这才是"锚点真的坏了"，必须拦下）。
- **G6**：更正 `SKILL.md` 第 296-301 行"Retired (rollback anchors)"
  一节，给 `v0.8.0` 一行说明：这份具体的仓库副本不携带该提交，锚点
  仅在原始谱系中成立；不删除这条历史记录本身（它仍然是真实发生过的
  设计事件），只是不再对**这份**代码许下兑现不了的承诺。

**非目标**

- 不伪造或移植一个 `v0.8.0:bin/oracle.py` blob 来让检查"通过"——那会
  让"已验证的回滚锚点"这句话本身变成谎言，比检查失败更糟。
- 不删除这条检查——删除会抹掉"`bin/oracle.py` 曾经存在过、曾经有真实
  回滚路径"这段历史动机，而 SKIP 状态保留了这个事实,只是如实标注
  "这份副本够不到它"。
- 不处理 `v0.5.1-delegated-final` 这另一个锚点——若它在本仓库历史内
  可达就不用动；若同样不可达，按同一模式处理，但不在本 PRD 未经核实
  的情况下预判，需要单独确认后再决定是否顺带修。

### 10 不变式

- **INV-34**：锚点不可达时的 SKIP 状态必须点名具体是哪个锚点、哪个
  文件、以及"republished copy"这个原因，不能是一句笼统的"skipped"。
- **INV-35**：SKIP 与 PASS 在门禁的最终输出文案里必须可区分（沿用
  INV-33 的"降级状态必须可诊断"要求）——不能让 SKIP 看起来像是
  "全部正常"。

### 11 反向门

- 若某天这份仓库真的被推上携带完整历史的位置（比如原库合并回来），
  `git tag` 里出现了 `v0.8.0` → 自动回到正常检查路径，不需要改代码。

### 12 验收

- 在当前仓库状态下跑 `dt1_gates.sh`：整体退出码从 1 变为 0，输出中
  出现一行明确的 SKIP 说明，而不是静默通过或者继续 FAIL。
- 人工核对 `v0.5.1-delegated-final` 锚点是否可达（`git tag` 或
  `git cat-file -e` 验证），把结论记录进本 PRD 的实施报告，决定是否
  顺带按同一模式处理。

### 13 回滚

`dt1_gates.sh` 一段判断逻辑 + `SKILL.md` 六行文字。删除/改回原样即
回到今天（门禁重新变为永久 FAIL）。
