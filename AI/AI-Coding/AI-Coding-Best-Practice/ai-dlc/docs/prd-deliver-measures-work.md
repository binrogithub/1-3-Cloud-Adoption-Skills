# PRD · 交付测量必须量到工作所在的 ref（deliver-measures-work）

> client-x 实测：一个三页网站的交付报告量到「2 个文件 / 0 字节」，
> 设计面判成「不适用」，刚上线的设计门被静默绕过，人在这份报告上批准了合并。
> 不是判据错了——是判据被喂了一棵还没有工作的树。

- 目标仓库：`<repo-path>`
- 相关：`docs/prd-design-required.md`（设计门，已实现 `c58e9f2`）
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：开工前打 `v0.19.x-pre-measurework`（**先打 tag 再动手**）

---

## 01 问题

### 实测时间线（`/tmp/client-x-ai-launch`，change `2026-09-01-client-x-ai-launch`）

```
19:16:54  24daa54  seed                              ← base_sha
19:18:07  ce150f2  openspec change 提交到 main
19:51:00  77f44ff  网站落地：site/{index,features,about}.html
                   + site/css/style.css + serve.py + tests  （940 行）
                   ↑ 提交在 task/2026-09-01-client-x-ai-launch 上，不在 main
19:51:21  183fb1b  .gitignore
19:55:53  DELIVERY_REPORT   landed_files=2  landed_bytes=0
19:56:08  DELIVERY_REPORT   landed_files=2  landed_bytes=0
19:56:17  DELIVERY_REPORT   landed_files=2  landed_bytes=0
19:56:41  NEED_HUMAN（合并门）
19:57:46  GATE_APPROVED
19:58:08  main reflog: "merge task/2026-09-01-client-x-ai-launch: Fast-forward"
                   ↑ 工作到这一刻才进 main —— 在批准之后
19:59:06  799ff6c  openspec archive
```

`report.json` 实测：

```json
"repo_head": "ce150f2…",  "head_advanced": true,
"landed_files": 2,  "landed_bytes": 0,
"files": ["openspec/changes/…/proposal.md",
          "openspec/changes/…/specs/client-x-ai-site/spec.md"],
"design": {"design_state": "design_not_applicable",
           "surface": {"applicable": false, "classes": [],
                       "surface_files": [], "surface_files_total": 0,
                       "measured_files": 2}}
```

事件流三次都是 `DESIGN_AUTO_SKIPPED {"why": "not_applicable"}`。

### 根因

`bin/plan.py` 的 `change_surface()`：

```python
base = state.get("base_sha")
head = run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
if base and head and base != head:
    diff = run(["git", "-C", str(repo), "diff", "--name-only", base, head])
```

它量的是 **`--repo` 那棵树的 HEAD**，也就是 `main`。
而 chain-completion 的规定是「**合并跟在批准之后**」——所以在 planned 路线上，
**批准之前，工作根本不在 `main` 上**。

于是：量到的是 `24daa54..ce150f2`，只有两个 openspec 文件，
其中还都是被 openspec 暂存（R5）挪走的、字节数为 0 的路径。

### 这是结构性的，不是偶发

| 路线 | 工作在哪 | deliver 量到 | 结果 |
|---|---|---|---|
| **inline** | 直接提交到 `main` | HEAD 已前进 → 量到真实文件 | 正常（巴拿马 13 个文件、阿根廷 1 个） |
| **planned** | `task/<change>` 分支，批准后才合并 | HEAD 还没动 → 量到空 | **必然失效** |

**刚上线的设计门（`prd-design-required.md`）在 planned 路线上被 100% 静默绕过**——
而且绕过的方式是四态里最无害的那个：`design_not_applicable`。
报告上看不出任何异常，人也看不出。

我用副本重跑同一段代码，合并之后测量立刻正确：

```
applicable: True   classes: ['web']
surface_files: ['site/about.html', 'site/css/style.css',
                'site/features.html', 'site/index.html']
```

**判据是对的，喂给它的 ref 是错的。**

### 三个附带问题（同一轮暴露）

**F-A · 自相矛盾的测量通过了 G-DELIVER-1。**
`head_advanced: true` + `landed_files: 2` + `landed_bytes: 0` 同时成立。
「头前进了、有文件、零字节」这个组合本身就不自洽，却一路放行。

**F-B · `DELIVERY_REPORT` 连发三次，结果完全相同。**
19:55:53 / 19:56:08 / 19:56:17。编排在重试，但每次都量同一棵没有工作的树，
**重试不可能自愈**，只是把同一个错误记了三遍。

**F-C · `__pycache__/*.pyc` 进了 `77f44ff` 的历史。**
22 KB 二进制。`183fb1b` 事后加了 `.gitignore` 补救，但 blob 已在历史里。

### 一个同类问题（巴拿马，同一失败家族）

`design_auto` 留下半截记录后被永久锁死：

```json
"design_auto": {"attempted_at": "…02:29:58Z", "trigger": "deliver",
                "rc": null, "outcome": null, "session": null,
                "elapsed_seconds": null}
```

会话 `design-task-20260901093149-f93794-1` 实际跑了 **1337 秒 / 187 帧 / 48 次工具调用**，
调用了 `skill_tool {"skill_name": "ui-designer"}`，我拿它的帧重跑事实提取
**五条全过**（11 个文件、108 个引用 0 缺失、10 页全 200、零占位）。
但结果没回写，而 `design_auto_due()` 现在返回 `(False, 'already_attempted')`
——**一条本该签发的记录永久丢失，且补救路径被自己的规则挡死**。

client-x 与巴拿马是同一件事的两个面：
**一次「量不到所以不适用」，一次「跑了但没回写」，两次都以 ui-designer 没参与收场，
而两份报告看上去都不像出错。**

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **P-A** | **交付测量量到工作实际所在的 ref**，与路线无关。planned 与 inline 得到同样正确的测量 |
| **P-B** | **自相矛盾的测量判失败**，不得放行（F-A） |
| **P-C** | **半截的 `design_auto` 不得永久锁死重试**（巴拿马） |
| **P-D** | **量的是哪个 ref，人在合并门上看得见** |

### 非目标

- **不改 chain-completion 的「合并跟在批准之后」**。那条是对的，问题不在它。
- 不改路由、不改阈值、不改路由例外的签发权。
- 不改设计门的判定逻辑（`c58e9f2` 的 M6 是对的）。
- 不改五条事实判据。
- 不清理 `77f44ff` 的历史（F-C 只记录，不做 rewrite——改写已合并历史的代价大于收益）。

---

## 03 不变式

| ID | 不变式 |
|---|---|
| **Q1** | **测量的 ref 是工作所在的 ref**：任务分支存在就量任务分支，不存在就量 HEAD。合并之后任务分支被删，回退到 HEAD 时工作已在其中——**两个方向都正确**。 |
| **Q2** | **量了哪个 ref 必须写进报告**，并进合并门的 `summary`（P-D）。不留「不知道量的是什么」的状态。 |
| **Q3** | **自相矛盾即失败**：`head_advanced` 为真且 `landed_files > 0` 且 `landed_bytes == 0` → 判失败并指出矛盾（沿用 M3 自洽断言的同一形态）。 |
| **Q4** | **半截尝试不是尝试过**：`design_auto` 的 `rc` 为 null 视为未完成，允许再派一次，并把次数记进 `attempts`。**上限仍然存在**（默认 2），不是无限重试。 |
| **Q5** | **不改变人的最终判官地位**：本轮只让报告说真话，不替人做决定。 |
| **Q6** | **inline 路线的行为一字不变**——今天它是对的，回归门守住。 |

---

## 04 实测约束

**E1 · 分支名有现成约定。**
`cmd_close`（`plan.py:5482`）已经在用 `br = branch or f"task/{change}"`。
`change_surface` 复用同一条约定即可，**不要发明第二套**。

**E2 · 分支名也在证据里。**
`evidence/plan-*.project-manifest.json` 里都写着 `task/2026-09-01-client-x-ai-launch`。
可作为交叉核对，但不应作为主来源（证据文件不保证存在）。

**E3 · 合并后分支会被删。**
client-x 现在 `git branch -a` 只剩 `main`，`.git/logs/refs/heads/` 也只有 `main`。
所以「分支不存在则回退 HEAD」是必需的，且此时 HEAD 已含工作——Q1 的两个方向都成立。

**E4 · `git status` 那一半今天就在工作。**
`change_surface` 已经把未提交文件并入测量。本轮只修 committed 那一半。

**E5 · 巴拿马的帧还在。**
`design-task-20260901093149-f93794-1/history.jsonl`（472 KB，187 帧）
与 `design-country-a-site-1/history.jsonl`（319 KB）都在，
**P-C 的回归门不需要再花 22 分钟跑会话。**

---

## 05 修复方案

| ID | 内容 |
|---|---|
| **N1** | **`change_surface` 量工作 ref**：先按 `f"task/{change}"`（E1 同约定）`rev-parse --verify -q refs/heads/<br>`；存在则用它做 diff 的 head，不存在回退 `rev-parse HEAD`。change id 从 `state.json` 的 `change_id` 取；无 change id（inline 例外路线）直接走 HEAD——**inline 行为不变**（Q6）。 |
| **N2** | **测量出处进 detail 与报告**：`{"measured_ref": "refs/heads/task/…"\|"HEAD", "ref_kind": "task_branch"\|"head", "head": "<sha>"}`，`report.json` 承载，合并门 `summary` 承载（Q2/P-D）。 |
| **N3** | **自洽断言（F-A）**：`head_advanced ∧ landed_files>0 ∧ landed_bytes==0` → `outcome: "measurement_inconsistent"`，`delivered: false`，报告里指出矛盾三元组。 |
| **N4** | **半截 `design_auto` 可重试（P-C）**：`rc is None` 视为 `incomplete`；`design_auto_due()` 对 incomplete 返回 due，并把 `attempts` 加一；`attempts >= 2` 才返回 `already_attempted`。记录形状加 `attempts` 与 `state: "incomplete"\|"complete"`。 |
| **N5** | **deliver 重试去抖（F-B）**：同一 `(measured_ref, base_sha, files_sha)` 的连续报告，事件只记第一条，其后记 `DELIVERY_REPORT_REPEAT` 带次数。**不阻止重试，只不再假装是新结果。** |
| **N6** | **巴拿马的补救**：清掉那条 `rc: null` 的 `design_auto`（N4 上线后它会被判 incomplete 自动可重试），并清掉那条 `"why": "C13 test: human overrides design gate"` 的伪造 `design_override`——**没有人做过那个决定**，它现在让巴拿马的报告在说谎。 |

### N1 的形状（要点）

```python
change = (load_json(task_dir / "state.json", {}) or {}).get("change_id")
head, ref_kind, measured_ref = None, "head", "HEAD"
if change:
    br = f"task/{change}"
    r = run(["git","-C",str(repo),"rev-parse","--verify","-q","refs/heads/"+br])
    if r.returncode == 0:
        head, ref_kind, measured_ref = r.stdout.strip(), "task_branch", "refs/heads/"+br
if head is None:
    head = run(["git","-C",str(repo),"rev-parse","HEAD"]).stdout.strip()
```

其余（`diff base..head`、`git status` 并入、`excluded()` 过滤）**一字不动**。

---

## 06 反向门

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **P1** | **判别力**：拿 client-x 在**合并前**的形状（base=24daa54，任务分支 = 183fb1b，main = ce150f2）跑 `deliver` | 量到 11 个文件，`applicable: true`，`classes: ['web']`，`surface_files` 含四个 `site/*` | **RED** — 今天量到 2 个文件 / 0 字节 |
| **P2** | 同上形状，且无 design 记录 | `outcome: design_required`，`delivered: false` | **RED** — 今天 `design_not_applicable` 放行 |
| **P3** | **inline 回归**：巴拿马形状（无任务分支，工作在 HEAD） | 与今天完全一致（13 个文件） | **GREEN 回归门** — Q6 的守卫 |
| **P4** | 合并**之后**再跑 `deliver`（分支已删） | 回退 HEAD，量到同样 11 个文件 | **RED**（今天恰好也对，但不是因为 N1；上线后须由 N1 保证） |
| **P5** | `head_advanced ∧ files>0 ∧ bytes==0` | `measurement_inconsistent`，`delivered: false` | **RED** — 今天静静通过 |
| **P6** | 报告与合并门 `summary` | 含 `measured_ref` / `ref_kind` | **RED** |
| **P7** | `design_auto` 为 `rc: null` | 判 `incomplete`，允许再派一次 | **RED** — 今天 `already_attempted` 永久锁死 |
| **P8** | 同上，`attempts` 已达 2 | `already_attempted`，不再派 | **RED** — 防 N4 变成无限重试 |
| **P9** | 连续三次相同 deliver | 第一条 `DELIVERY_REPORT`，其后 `DELIVERY_REPORT_REPEAT` 带次数 | **RED** — 今天记了三条一样的 |
| **P10** | **端到端**：拿巴拿马 design 会话**已有的帧**重跑事实提取 | 五条全过、记录签发 | 事实提取**今天已实测全过**；记录签发这一半 **RED** |

**P1 与 P3 缺一不可**：P1 证明 planned 路线被修好，P3 证明 inline 没被弄坏。
**P7 与 P8 缺一不可**：P7 解开死锁，P8 防止解成无限重试。
**P5 是最便宜的一道**：它本可以在 client-x 当天就把这个 bug 拦下来。

---

## 07 分期

| 期 | 内容 | 门 |
|---|---|---|
| **T0 · 探针** | 已完成：client-x 时间线与 reflog 定性（结构性，非偶发）；巴拿马帧重跑五条全过 | 两个事实进记录 |
| **T1 · 测量对 ref** | N1 + N2 | **P1** **P3** P4 P6 |
| **T2 · 自洽与去抖** | N3 + N5 | **P5** P9 |
| **T3 · 解死锁** | N4 + N6 | **P7** P8 P10 |

T1 是主修；T2 是「本可以早点发现」的那道便宜保险；
T3 把两个已经卡住的真实交付（巴拿马）解开。

**T1 落地当天用 client-x 复验**（P1）：它的合并前形状可以从 git 完整重建
（`base=24daa54`、`task 分支尖=183fb1b`、`main=ce150f2`），**不需要重跑任何会话**。

---

## 08 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | **`task/<change>` 只是约定**，有人用别的分支名就落空 | 回退 HEAD 时行为与今天一致（不会更糟）；`measured_ref` 写进报告，落空时人看得见量的是 `HEAD`。**残余**：约定之外的分支名仍量不到，需要显式 `--branch`（`cmd_close` 已有同名参数，可复用）。 |
| **R2** | **量任务分支 = 量了还没被人批准的东西** | 这正是想要的：**报告要在批准之前告诉人「将要合并进来的是什么」**。合并本身仍然跟在批准之后（chain-completion 不变）。 |
| **R3** | **N4 让 design 轮被重跑，多花一次十几到二十分钟** | `attempts` 上限 2（P8）。**残余**：一次真实失败会被再试一次——这是解死锁的代价，可接受。 |
| **R4** | **N3 误判**：某些合法交付确实是 0 字节（纯删除） | 断言限定在 `landed_files > 0 ∧ landed_bytes == 0`；纯删除交付应当 `landed_files > 0` 且字节为 0——**这条要在 T2 用真实的纯删除 change 验一次**，不能只靠夹具。**若确有合法形态，改为告警而非失败。** |
| **R5** | **N6 修改线上任务记录** | 只删两条：半截 `design_auto` 与伪造的 `design_override`。**不静默删事件**——在 `events.jsonl` 追加一条更正事件，写明删了什么、为什么。 |
| **R6** | 修好之后，**存量已交付的 planned 任务回头看都可能是「未验设计」** | 不追溯、不自动重跑。**残余**：历史交付的设计状态不可信，需要时人工按需补跑。 |

---

## 09 回滚

1. `git reset --hard v0.19.x-pre-measurework`
2. `/var/lib/aidlc/records/` 保留不删
3. N6 动过的任务记录：更正事件保留（它本身是事实），被删的两条从
   `git`/备份恢复（巴拿马仓库在 `/tmp/country-d-tourism-8443`，`.ai-dlc/` 未入 git，
   **执行 N6 前先 tar 一份该任务目录**）
4. `/opt/open-design`、gateway unit、openjiuwen 配置全程未动

---

## 附注 · 与既有 PRD 的关系

- **`prd-design-required.md`**：其判定逻辑（M6）**是对的，本轮不动**。
  本轮修的是喂给它的输入。该 PRD 的 C10/C11 在 planned 路线上从未被真正行使过——
  **建议把本 PRD 的 P1/P2 补进它的门集**，否则「设计门已上线」这句话
  在 planned 路线上不成立。
- **`prd-design-autodispatch.md`**：其 J2「至多一次、永不自动重跑」
  需按 Q4 收窄为「至多两次**完成的**尝试」——半截不算一次。
- **`prd-install-targets.md`**：无耦合。

---

*`docs/prd-deliver-measures-work.md` · 测量日期 2026-09-01 · <host-ip>*
