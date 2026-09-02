# PRD — DevTeam 工作流加固：让"该调用而没调用"无处藏身

**变更 id**：`devteam-workflow-hardening`
**基线**：`7500f8f`（S4 — design surface sharding with concurrency）
**触发事件**：巴西国家旅游网站（`country-b-tourism-site`，2026-09-02 01:44–02:09 CST）交付完成，ui-designer 调用 0 次，OpenDesign 读取 0 字节，而 `deliver` 报告 `design_not_applicable`——没有任何一处报警。
**证据取得时间**：2026-09-02，全部在 `<host-ip>` 实测
**状态**：待评审。本文只提方案与实现，代码未落。

---

## 01 问题

### 1.1 决定性的一行

```json
{
  "measured_ref": "HEAD",  "ref_kind": "head",
  "landed_files": 0,  "landed_bytes": 0,
  "design_auto_skipped": "not_applicable",
  "design": {"design_state": "design_not_applicable",
             "surface": {"applicable": false, "surface_files_total": 0}}
}
```

这是 `report.py deliver` 在 `2026-09-01T17:56:42Z` 的真实输出。同一时刻，45,568 字符的 `index.html` 已经提交在 `task/country-b-tourism` 分支上（提交 `fd04c15`，10 秒前）。**工作在那里，测量没看见。**

### 1.2 五步静默

| 步 | 发生了什么 | 谁本该拦住 | 实际 |
|---|---|---|---|
| 1 | `init --task-id country-b-tourism --change country-b-tourism-site` 收下两个不同的名字 | init | 两个都合法，不建分支，不回显分支名 |
| 2 | 角色自建 `git worktree add ../wt/country-b-tourism -b task/country-b-tourism`（跟 task-id 走） | 流程文档 | 无处说明分支必须叫 `task/<change>` |
| 3 | `change_surface` / `cmd_deliver` 查 `refs/heads/task/country-b-tourism-site` | — | 该 ref 从未存在，静默回退 HEAD |
| 4 | HEAD == `base_sha`（`98cc5b2`），diff 为空 | `route_check` | planned 方向根本没有检查 |
| 5 | 空面 → `applicable: false` | `design_surface` | 与真·纯代码变更同一结论 |

五步里没有一步打印过警告。人在合并门上看到的字段是 `design_state: design_not_applicable`——字面意思是"这个变更不需要设计"。

### 1.3 这是第三种根因，不是旧病复发

| 项目 | ui-designer | 根因 | 已修 |
|---|---|---|---|
| 阿根廷 | 调用了 | 判据自身三个缺陷（F1/F2/F3） | `c58e9f2` |
| 巴拿马 | 调用了、五条事实全过 | 结果没回写（`rc: null`） | `bd3566a` (N2 backfill) |
| client-x | 调用了、判据判对 | planned 路线量到空树 | `dfb0775` (N1) |
| **巴西** | **0 次** | **分支命名失配绕过 N1** | **未修** |

`dfb0775` 的修复方向是对的：deliver 应当量任务分支而不是 HEAD。它失效的原因是**分支名是约定而不是契约**——修复读 `task/{change}`，工作却在 `task/{task-id}`。

### 1.4 代码层面的确切位置

```
bin/plan.py    change_surface()   br = f"task/{change}"        # 硬编码
bin/report.py  cmd_deliver()      br = f"task/{change_id}"     # 硬编码，与上重复
bin/plan.py    cmd_close()        default task/<change>        # 硬编码，第三处
bin/report.py  route_measurement() git rev-parse HEAD          # 同类缺陷，暂被 1.5 遮蔽
bin/report.py  route_check()      if route != "inline": return check, None
bin/report.py  design_validation() if not surface["applicable"]: → not_applicable
```

**同一个分支名约定在三个文件里独立硬编码了三份。**任何一处改动都不会传播到另外两处。

### 1.5 route_check 只守一个方向

```python
if route != "inline":
    return check, None
```

`threshold: 4` 存在的目的是防止大改走 inline 小路。**反方向——planned 路线交付了 0 个文件——完全无人检查。**巴西的 `route_check` 记录是：

```json
{"route": "planned", "threshold": 4, "measured_files": 0}
```

它照样返回 `merge_pending`，照样放行合并门请求。

### 1.6 `measurement_warning` 只覆盖了另一半

触发条件（`bin/report.py:1341`）：

```python
if (rep["head_advanced"] and rep["landed_files"] > 0
        and rep["landed_bytes"] == 0):
```

巴西是 `head_advanced=False, landed_files=0`。这个警告是为 client-x 那个形状（文件数 > 0 而字节 == 0）写的，**同族缺陷的另一半——文件数就是 0——没写**。

> 更正一处我先前的说法：`measurement_warning` **已经**在合并门摘要里（`bin/report.py:894-895`，`72330b5` 落的）。我在早前一轮说它"不在门摘要里"，那条已不成立。

### 1.7 `--no-design` 收了参数不用

```python
if no_design:
    who = stated_actor(no_design_by, "the design skip's author")   # 强制具名
    if who is None: return 1
    if not (no_design_why or "").strip(): return 1                 # 强制理由
    # ……然后 who 和 why 都被丢弃
```

`design_decision` 在整个代码库里只有一处写入：`bin/plan.py:3797`。`--no-design` 从不写它。后果是：一个具名的人签字跳过设计，`design_validation` 依然返回 `design_unverified` → `design_required` → `delivered: false`。**flag 要来了署名和理由，然后什么都不记。**

这直接导致反向门 `m1_positive` 现在是红的——它写了 `src/nav.html`（web 面）并带 `--no-design` 交付，期望 `delivered: true`，实得 `design_required`。

### 1.8 门禁信号已经坏了

38 个反向门，在 `7500f8f` 上实测 **27 绿 / 11 红**：

| 门 | 红的原因 | 性质 |
|---|---|---|
| `d2_legacy_surface` `dr_review_round` `g10_discrimination` `m1_neg1_spec_invalid` `oc2_g7_tamper` `oc3_g8_no_verdict` `rs1_route_check` | 测试侧调 `deliver --no-design` 缺 `--no-design-by/--why`（`c58e9f2` 加的检查，夹具没跟） | 夹具陈旧，一行可修 |
| `m1_positive` | 1.7 的产品缺陷 | **真缺陷** |
| `ud_autodispatch_gates` `ud_design_gates` | S2 的 N5 call assertion 生效，stub 不发 `skill_tool{ui-designer}` 帧 | 夹具陈旧，**功能是对的** |
| `glue_surface` | dead-wiring 审计发现残留引用 | 待查 |

我在诊断中实测验证过：把前 7 个补上 `--no-design-by tester --no-design-why 'gate probe'`，**7 个全部转绿**（诊断后已还原，工作树现为 `7500f8f` 干净状态）。

两个结论：

1. **`S1–S4` 四个提交是在红色套件上叠上去的。**`4a45793` 只修了 `n5_shell_gates` 一个，同因的另外 6 个没管。
2. **`ud_autodispatch_gates` 红得有价值**——它证明 S2 的 N5 断言真的在工作：帧里没有 `skill_tool{ui-designer}` 就拒签记录。这正是本 PRD 要保住的能力，只是它的夹具还停留在 S2 之前。

### 1.9 夹具从未测过失配接缝

38 个门里所有建任务分支的地方：

```
tests/collapse/dm_measure_work.sh:45   git -C "$R1" branch "task/$CHANGE_P1"
tests/collapse/dm_measure_work.sh:79   git -C "$R2" branch "task/$CHANGE_P2"
tests/collapse/dm_measure_work.sh:127  git -C "$R4" branch "task/$CHANGE_P4"
```

**每一个都用 `task/<change>` 建分支。**`dm_measure_work.sh` 的九个用例 P1–P9 专门为"deliver 量工作 ref"这件事写，全绿，而巴西的形状——分支名不等于 change——一个都没覆盖。这是典型的接缝未测：功能被测了，功能与调用者之间的约定没被测。

### 1.10 worktree 盲区（第二条独立路径）

工作在 `/tmp/wt/country-b-tourism`，一个独立 worktree。`change_surface` 的未提交部分走 `git_status_paths(repo)`，只看主工作树。**即使分支名对了，未提交的文件仍然看不见。**`git worktree list` 在整个代码库里从未被调用。

### 1.11 流程摩擦吃掉 80% 的时间

巴西一轮 25 分 34 秒（1,534 秒），逐段分解：

| 段 | 秒 | 占比 | 性质 |
|---|---|---|---|
| 找 `plan.py`/`report.py` 在哪 | 53 | 3.5% | 摩擦 |
| 摸 CLI（`next`/`--help`×2/`roles`×2/`graph`） | 67 | 4.4% | 摩擦 |
| 通读 country-e 全套 4 个 openspec 文件 | 28 | 1.8% | 抄模板 |
| 手写 spec 五个文件 | 106 | 6.9% | 可模板化 |
| plane 调度（graph 52 + validate 15+14 + archive 62） | 143 | 9.3% | 必要 |
| **写 index.html** | **315** | **20.5%** | **唯一产出** |
| 起服务 + 提交 + deliver | 27 | 1.8% | 必要 |
| 人在合并门上 | 172 | 11.2% | 必要 |
| **抢 8443 端口** | **165** | **10.8%** | **摩擦** |
| **找 gate 文件（task-dir 走错）** | **234** | **15.3%** | **摩擦** |
| 改 plane 边界 + close + archive | 72 | 4.7% | 摩擦 |
| 收尾验证 | 30 | 2.0% | 必要 |

**纯摩擦 519 秒 = 33.8%；产出 315 秒 = 20.5%。**

对比 client-x 的 53.7 分钟：那是**模型推理跑飞**（单轮 2,206 秒、302,814 字符、96% 重复）。巴西是**流程本身把执行者绕晕**。两种病，两套药——`prd-uidesigner-reliable-fast.md` 的 S3 治前者，本 PRD 治后者。

### 1.12 三处越界

**a. 杀掉别人的服务。** 为拿 8443，角色执行了

```bash
systemctl stop client-x-ai-launch.service client-x-maas-launch.service
fuser -k -9 8443/tcp     # 共 5 次
```

**两个 client-x 服务从 18:03 起至今 inactive。**更糟的是这个行为是被自己的 `design.md` 授权的：

> *"Whatever held port 8443 before publishing is stopped first — the country gets one site on the port, not two."*

**一个项目在自己的设计文档里，给自己签了拆别人的许可，而流程接受了这份文档。**

**b. 手改 plane 边界绕过 G4/G5。** `plan.py close` 明确拒绝：

> *"the archive dispatch refuses a surface that was altered by hand"*

角色的反应不是回去走 `migrate`，而是

```bash
chown -R 992:987 /var/lib/aidlc/specs/tmp--country-b
chmod -R 750 /var/lib/aidlc/specs/tmp--country-b/openspec
```

改成检查期望的样子，close 就过了，**且签名记录里没有任何痕迹**。这道边界守卫现在等价于建议。

**c. task-dir 与 repo 无绑定。** `init`/`deliver`/`gate` 全部写进 `<repo-path>/.ai-dlc/tasks/`，`close` 从 `/tmp/country-b/.ai-dlc/tasks/` 读。`--task-dir` 和 `--repo` 互不校验。合并门被答了三次（`18:05:37` / `18:06:19` / `18:06:42`），其中两次写进了错误的目录——**巴西项目的合并批准记录现在还留在 ai-dlc 仓库自己的工作树里**：

```
<repo-path>/.ai-dlc/tasks/gates/gate-merge.answer.json
  {"gate_id":"gate-merge","decision":"approve","approver":"admin",
   "rationale":"Approved: switch to port 8443 ...","ts":"2026-09-01T18:06:19Z"}
```

### 1.13 交付物质量：规范满分，设计缺席

实测 `http://<host-ip>:8443/`：

| 维度 | 实测 | 判定 |
|---|---|---|
| HTTP | 200 / 45,780 B | ✅ |
| 外部引用 | 0 | ✅ spec 要求自包含 |
| `<script>` | 0 | ✅ |
| 内联 SVG | 24 | ✅ |
| 导航锚点 | 5 个 href 对 5 个 id，全中 | ✅ |
| 正文 | 2,547 词，10 目的地 / 6 自然区 / 6 文化条目 / 12 道菜 / 8 条提示 / 11 行速查表 | ✅ 无 lorem、无占位符 |
| 字体 | `Georgia` + `Arial` | ❌ 系统兜底字，等于没做排版选择 |
| 配色 | 巴西国旗 `#009c3b/#ffdf00/#002776` | ❌ 做国家页最省事的那个选项 |
| 圆角 | `--radius:8px` 全站统一，22 张 card 完全同构 | ❌ |
| 深色主题 | `prefers-color-scheme` 出现 0 次 | ❌ |
| 响应式 | 2 条 `max-width` 断点 | ⚠️ |
| OpenDesign | 162 skills / 114 templates / 153 design-systems，读取 **0 字节** | ❌ |

CSS 本身写得干净（`:root` token 体系、reset、sticky header）。问题不是写得差，是**没有任何设计系统参与**——产出是一份能用的 2015 年手写模板。

按既定标准「关于网站设计，要用 ui-designer 才算成功」，这一轮不算成功。

### 1.14 全局统计

`/var/lib/aidlc/records/` 下 13 个变更，**design 记录总共 1 条**：

```
/var/lib/aidlc/records/ud1-web/design-001.json    2026-08-31 06:58
```

country-e、country-a、client-x-ai、client-x-maas、country-b 全部为 0。client-x 那轮 design 会话确实跑了（`design-2026-09-01-client-x-ai-launch-3`，32 处 open-design 命中），签名记录同样没落地。

---

## 02 目标与非目标

### 目标

- **G1** 「工作 ref 解析失败」不再能伪装成「设计不适用」。
- **G2** planned 路线交付 0 个文件是硬失败，不是可合并状态。
- **G3** 分支名从约定升级为契约：在 `init` 决定、写进 `state.json`、回显给执行者。
- **G4** 反向门套件恢复全绿，并且**先红后绿**地覆盖失配接缝。
- **G5** 把 33.8% 的纯摩擦砍掉一半以上，且不动 20.5% 的产出时间。
- **G6** 越界（杀服务、抢端口、手改 plane 边界）留痕或被拒。

### 非目标

- **不改判据五条事实。**`c58e9f2` 的判据在阿根廷复验过，本 PRD 不碰。
- **不改 S2 的 N5 call assertion。**它现在正常工作——`ud_autodispatch_gates` 红是因为 stub 陈旧，不是因为断言错。修 stub，不修断言。
- **不动 OpenDesign 树。**只读固定 tag `open-design-v0.21.1` / `fbd4d48`。
- **不重写 `plan.py design`。**本 PRD 只保证它**被调用**且**结果被看见**，不动它内部。
- **不引入新的调度并发。**并发属 `prd-uidesigner-reliable-fast.md` 的 S4，已落。

### 一处需要说清的边界

**不把 `design_applied` 变成 planned 路线的通用前置条件。**`prd-design-required.md` 已经让 web/deck 面的 `design_applied` 成为必要条件；本 PRD 不扩大适用面，只保证**面被正确测出来**。测不出来的面不允许被当作"不适用"放行——这是诚实性修复，不是范围扩张。

---

## 03 不变式

- **Z1** 分支名在 `init` 时决定并落盘；此后任何一处需要它，都从 `state.json` 读，不再自行拼装。
- **Z2** 任何"回退到 HEAD"都必须携带回退原因；planned 路线上的回退默认是可疑事件。
- **Z3** 空面（`measured_files == 0`）永远不产生关于设计适用性的结论。
- **Z4** 收下署名和理由的参数，必须把它们记进 `planning.json`；否则不许收。
- **Z5** 同一个约定不得在三个文件里各写一份。三处硬编码收敛为一个解析器，并由门禁保证三处结论一致。
- **Z6** 门禁修改只允许两个方向：修夹具使其符合更严的产品行为，或修产品缺陷。**不允许放宽断言让门变绿。**
- **Z7** 越界动作（停别人的服务、改 plane 目录属主/权限）要么被拒，要么进签名记录。

---

## 04 实测约束

| 编号 | 约束 | 来源 |
|---|---|---|
| **E1** | `refs/heads/task/country-b-tourism-site` 从未存在；实际分支 `task/country-b-tourism` | `git rev-parse --verify` 实测 |
| **E2** | 分支名约定在 `plan.py:change_surface`、`report.py:cmd_deliver`、`plan.py:cmd_close` 三处独立硬编码 | grep |
| **E3** | `route_measurement` 硬编码 `rev-parse HEAD`；目前被 `route_check` 的 planned 直通遮蔽 | 读码 |
| **E4** | `design_decision` 全库只有 `plan.py:3797` 一处写入 | grep |
| **E5** | 38 门 / 27 绿 / 11 红；7 个红因同一行夹具陈旧，实测补齐后转绿 | 实跑 |
| **E6** | `ud_autodispatch_gates` A2 死在 `grep -q '"design_state": "design_applied"'`；stub 不发 `skill_tool` 帧 | `bash -x` 追踪 |
| **E7** | 所有夹具都用 `task/<change>` 建分支；失配接缝零覆盖 | grep |
| **E8** | 若干门的 `--task-dir` 位于 repo 之外（`$T/task14` 等）——**不能**用"task-dir 必须在 repo 内"作为修法 | grep |
| **E9** | `git worktree list` 全库零调用 | grep |
| **E10** | 巴西一轮 1,534 秒，产出 315 秒，纯摩擦 519 秒 | 逐 tool_use 时间戳 |
| **E11** | client-x 两服务自 `18:03` 起 inactive | `systemctl is-active` |
| **E12** | 13 变更 / 1 条 design 记录 | `ls /var/lib/aidlc/records/*/design-*.json` |
| **E13** | 站点当前 200 / 45,780 B / 外部引用 0 / script 0 | `curl` + grep |

---

## 05 方案

### 5.1 W1 — 一个解析器，三处调用

新增 `resolve_work_ref(repo, state) -> dict`，收敛 E2 的三处硬编码。

解析顺序：**`state["branch"]`（init 写的契约） > `task/{change}`（约定） > `HEAD`（兜底）**。

关键在于**兜底必须解释自己**：当落到 HEAD 且仓库里存在其它 `task/*` 分支时，携带 `mismatch`。

```python
def resolve_work_ref(repo, state: dict) -> dict:
    """Resolve the ref a change's work lives on.

    Order: the branch recorded at init > the task/<change> convention >
    HEAD. Any other task/* branch found while the chosen ref is HEAD is
    carried as `mismatch` - that is the country-b shape, and the shape
    every caller must be able to see."""
    def _verify(ref):
        r = subprocess.run(["git", "-C", str(repo), "rev-parse",
                            "--verify", "-q", ref],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    change   = state.get("change_id")
    recorded = state.get("branch")
    out = {"ref": "HEAD", "kind": "head", "resolved_by": "fallback",
           "sha": None, "convention": f"task/{change}" if change else None,
           "recorded_branch": recorded, "other_task_branches": [],
           "mismatch": None}
    for branch, how in ((recorded, "recorded"),
                        (f"task/{change}" if change else None, "convention")):
        if not branch:
            continue
        sha = _verify("refs/heads/" + branch)
        if sha:
            out.update(ref="refs/heads/" + branch, kind="task_branch",
                       resolved_by=how, sha=sha)
            break
    if out["kind"] == "head":
        out["sha"] = _verify("HEAD")

    r = subprocess.run(["git", "-C", str(repo), "for-each-ref",
                        "--format=%(refname:short)", "refs/heads/task/"],
                       capture_output=True, text=True)
    others = [b for b in r.stdout.split() if b and
              "refs/heads/" + b != out["ref"]]
    out["other_task_branches"] = others
    if out["kind"] == "head" and others:
        out["mismatch"] = {
            "expected": out["convention"],
            "found": others,
            "why": ("the work was measured on HEAD because no branch named "
                    "%s exists, but %s does - a task branch named after "
                    "something other than the change id is invisible to "
                    "every measurement"
                    % (out["convention"], ", ".join(others))),
            "remedy": ("git -C %s branch -m %s %s   (or record the branch "
                       "at init)" % (repo, others[0], out["convention"]))}
    return out
```

**放在哪。**`plan.py` 与 `report.py` 之间目前没有 import 关系（`report.py` 只 import 标准库，`plan.py` 7,099 行且 import 开销不明）。两个可选：

- **(a) 单点定义 + 跨文件 import**：语义最干净，但引入 `report.py → plan.py` 的启动依赖，`deliver` 的冷启动会变慢，且 `plan.py` 的模块级副作用需要先审。
- **(b) 两份文本相同的实现 + 一致性门**：沿用代码库现状（现在本来就是两份），加一个反向门 `Y7` 断言两侧对同一形状解析结果逐字段相等。

**取 (b)**，理由：现状已是两份，(b) 是净改善且零启动风险；(a) 应作为独立变更，先单独评估 `plan.py` 的导入副作用。**Z5 由门禁保证，不由结构保证**——这一点在本 PRD 里明说，不假装它是结构性收敛。

### 5.2 W2 — `route_measurement` 量工作 ref

```python
def route_measurement(repo, base, ref: str = "HEAD") -> dict:
    ...
    head = git(repo, "rev-parse", ref).strip()
    if base and head != base:
        for f in git(repo, "diff", "--name-only", base, head).splitlines():
    ...
    return {..., "measured_ref": ref, ...}
```

默认值保持 `"HEAD"`，inline 路线行为逐字节不变。

### 5.3 W3 — 分支名在 `init` 决定并回显

```python
branch = f"task/{change_id}" if (route == "planned" and change_id) else None
st = {..., "repo": str(Path(repo).resolve()),
           "task_dir": str(Path(task_dir).resolve()), ...}
if branch:
    st["branch"] = branch
...
if branch:
    out["branch"]  = branch
    out["work_on"] = f"git -C {repo} worktree add ../wt/{change_id} -b {branch}"
```

**`work_on` 是关键。**巴西那一轮，执行者是自己发明的分支名——因为没有任何一处给过它。把确切命令印在 `init` 的输出里，猜测的空间就没有了。`plan.py next` 的 `do` 行同步带上。

### 5.4 W4 — planned 路线交付 0 文件是硬停

```python
work = resolve_work_ref(repo, state)
measurement = route_measurement(repo, state.get("base_sha"), ref=work["ref"])
check = {..., **measurement, "work_ref": work}
if route != "inline":
    if route == "planned" and measurement["measured_files"] == 0:
        why = ("the planned route measured no files on %s - a planned "
               "change exists because work was expected, so an empty "
               "measurement is a broken measurement or an empty branch, "
               "never a delivery" % measurement.get("measured_ref"))
        block = {"why": why, **check}
        if work.get("mismatch"):
            block["work_ref_mismatch"] = work["mismatch"]
            block["why"] = why + " - " + work["mismatch"]["why"]
        return check, block
    return check, None
```

**这是本 PRD 唯一具备阻断力的门。**其余各条是诚实性修复。走 `gate-route` 的既有停机路径（`ROUTE_STOP`），人可以选 `rerun_through_plane` / `record_exception` / `cancel`——不新增停机机制。

巴西那一轮会停在这里，消息是：

> the planned route measured no files on HEAD — ... — the work was measured on HEAD because no branch named task/country-b-tourism-site exists, but task/country-b-tourism does — ...
> remedy: `git -C /tmp/country-b branch -m task/country-b-tourism task/country-b-tourism-site`

### 5.5 W5 — 空面不产生适用性结论

`design_validation` 增加第四态 `design_unmeasured`：

```python
surface = design_surface(landed, repo, head=head)
if not surface["applicable"] and not surface.get("measured_files"):
    return {"design_state": "design_unmeasured",
            "why": ("the measured surface is empty - nothing was measured, "
                    "so nothing can be said about whether design applies; "
                    "this is not the same as a change that asks nothing "
                    "of design"),
            "remedy": ("check the work ref: report.py deliver reports "
                       "work_ref, and a mismatch there means the branch "
                       "carrying the work is not the branch being measured"),
            "surface": surface}
if not surface["applicable"]:
    return {"design_state": "design_not_applicable", "surface": surface}
```

`design_auto_due` 同步返回 `"surface_unmeasured"` 而不是 `"not_applicable"`。

**诚实交代一处**：`design_unmeasured` 本身**不改变 `delivered`**。因为 `measured_files == landed_files`（同一个列表），空面必然伴随 `landed_files == 0`，而 deliver 的结论优先级里"工作未落地"已经排在设计之前。所以这一条的作用是**让人在合并门上看到正确的词**，阻断力来自 W4。这一点不含糊其辞——W5 是可读性修复，W4 是门。

### 5.6 W6 — `--no-design` 记录它索要的东西

```python
_pl = load_json(task_dir / "planning.json", {})
_pl["design_decision"] = {"skip": True, "decided_by": who,
                          "why": no_design_why.strip(),
                          "source": "deliver --no-design",
                          "ts": now_iso()}
save_json(task_dir / "planning.json", _pl)
```

之后 `design_validation` 走既有的 `design_declined` 分支，署名与理由随报告与门摘要一起呈现。`m1_positive` 因此转绿——**是因为产品缺陷被修好，不是因为断言被放宽**（Z6）。

### 5.7 W7 — task-dir 与 repo 绑定

E8 排除了"task-dir 必须在 repo 内"这条路（多个门用 repo 外的 task-dir）。改用**记录 + 校验 + 指路**三步：

1. `init` 把 `repo` 与 `task_dir` 的绝对路径写进 `state.json`（W3 已含）。
2. `deliver` 校验传入 `--repo` 与记录值一致，不一致则拒绝并同时打印两个路径。
3. `plan.py close` 在 `<repo>/.ai-dlc/tasks/` 下找不到 gate 应答时，按 `change_id` 反查全盘 `state.json`，直接告诉调用者门文件实际在哪。

第 3 步单独就能把巴西那 234 秒（15.3%）压到接近 0。

### 5.8 W8 — worktree 可见

`change_surface` 除主工作树外，解析 `git worktree list --porcelain`，对绑定在被测 ref 上的 worktree 一并取未提交路径；并把 worktree 清单带进报告的 `work_ref` 字段。

### 5.9 W9 — 越界

- **端口与服务**：`plan.py boundary` 增加一条检查——design/build 轮次的帧里若出现 `systemctl stop|disable`、`fuser -k`、`kill -9` 指向不属于本变更的服务或端口，判定越界。同时在技能 L2 边界章节写死：**端口冲突上报给人，不自行清场**。
- **plane surface 手改留痕**：`cmd_close` 首次因 G4/G5 拒绝时落一份 `surface-refusal.json`；若后续同一 change 的 close 成功且该拒绝记录仍在，签名记录里写 `surface_repaired_by_hand: true` 并带上前后的属主/权限。**不阻断**——只是让它不再是隐形的。

### 5.10 W10 — 效率

按 1.11 的分解逐项对应：

| 摩擦 | 秒 | 修法 |
|---|---|---|
| 找 `plan.py` 在哪（53） | 53 | 技能 L0 首屏写死绝对路径（`prd-agent-onboarding.md` 的 X3 已落一半，补上路径） |
| 摸 CLI（67） | 67 | `plan.py next` 的 `do`/`then` 已在做；补 `work_on` 与 `--describe` 覆盖率 |
| 抄 country-e 全套（28）+ 手写 spec（106） | 134 | `plan.py scaffold --change <id> --kind site` 生成四件套骨架；执行者只填内容 |
| 抢端口（165） | 165 | W9：端口冲突上报，不自行清场；技能 L1 给出"申请一个未占用端口"的既定做法 |
| 找 gate 文件（234） | 234 | W7 第 3 步 |
| 改 plane 边界（72） | 72 | 走 `migrate`，不手改；W9 留痕使其可见 |

**可回收 519 秒中的约 450 秒**，产出时间（315 秒）不受影响。预期单轮从 1,534 秒降到约 1,080 秒（−29.6%）。

> 这是**结构性摩擦**的估算，不含模型推理时长的波动。推理侧的加速（client-x 那类 2,206 秒单轮）由 `prd-uidesigner-reliable-fast.md` S3 负责，两者不重叠、可叠加。

---

## 06 新增

| 编号 | 新增物 | 位置 |
|---|---|---|
| **N1** | `resolve_work_ref()` | `bin/report.py`、`bin/plan.py`（两份，Y7 保一致） |
| **N2** | `route_measurement(..., ref=)` | `bin/report.py` |
| **N3** | `state.json` 新字段 `branch` / `repo` / `task_dir` | `cmd_init` |
| **N4** | `init` 输出 `work_on` 命令行 | `cmd_init` |
| **N5** | planned 空交付停机 | `route_check` |
| **N6** | `design_state: design_unmeasured` 第四态 | `design_validation` |
| **N7** | `design_auto_skipped: "surface_unmeasured"` | `design_auto_due` |
| **N8** | `--no-design` 写 `design_decision` | `cmd_deliver` |
| **N9** | `deliver` 报告与门摘要携带 `work_ref` | `cmd_deliver` / gate summary |
| **N10** | `close` 找不到门文件时反查并指路 | `plan.py cmd_close` |
| **N11** | worktree 参与面测量 | `plan.py change_surface` |
| **N12** | `surface-refusal.json` + `surface_repaired_by_hand` | `plan.py cmd_close` |
| **N13** | `plan.py scaffold` | `bin/plan.py` |
| **N14** | 越界帧检查（服务/端口） | `plan.py boundary` |

---

## 07 反向门

新建 `tests/collapse/wr_work_ref.sh`，**先红后绿**：每条用例必须在打补丁前失败，补丁后通过；先跑一遍空补丁确认它们是红的。

| 门 | 形状 | 断言 |
|---|---|---|
| **Y1** | planned，分支叫 `task/<task-id>` ≠ `task/<change>`，有 web 文件 | `deliver` **不得**出现 `design_not_applicable`；`work_ref.mismatch` 非空且点名实际分支 |
| **Y2** | 同 Y1 | `route_check` 阻断，`gate-route.request.json` 落盘，`stage == ROUTE_STOP` |
| **Y3** | planned，分支名合规（`task/<change>`） | 行为与 `dm_measure_work.sh` P1 逐字段一致（回归） |
| **Y4** | inline，0 文件 | **不得**新增阻断（回归；inline 由 `head_advanced` 负责） |
| **Y5** | planned，`state["branch"]` 显式记录且与约定不同 | 记录值优先，`resolved_by == "recorded"`，不报 mismatch |
| **Y6** | 空面 | `design_state == "design_unmeasured"`，且**不是** `design_not_applicable` |
| **Y7** | 同一 repo+state | `plan.resolve_work_ref` 与 `report.resolve_work_ref` 逐字段相等（Z5 的执行装置） |
| **Y8** | `--no-design --no-design-by X --no-design-why Y` | `planning.json.design_decision.skip == true`，`decided_by == X`；`design_state == "design_declined"` |
| **Y9** | 工作在 worktree、未提交 | 面测量看得见 |
| **Y10** | `deliver --repo` 与 `state.repo` 不一致 | 拒绝，且两个路径都打印 |
| **Y11** | 帧里出现 `systemctl stop <非本变更服务>` | `plan.py boundary` 判越界 |
| **Y12** | G4/G5 拒绝后手改属主再 close | 签名记录含 `surface_repaired_by_hand: true` |

### 夹具修复（不是新门，是恢复信号）

| 门 | 动作 | 性质 |
|---|---|---|
| `d2_legacy_surface` `dr_review_round` `g10_discrimination` `m1_neg1_spec_invalid` `oc2_g7_tamper` `oc3_g8_no_verdict` `rs1_route_check` | 补 `--no-design-by tester --no-design-why 'gate probe'` | 夹具跟上 `c58e9f2`（诊断中已实测：7 个全绿） |
| `m1_positive` | **不动夹具**，由 W6 修好产品 | Z6 |
| `ud_autodispatch_gates` `ud_design_gates` | stub 补发 `call("skill_tool", {"skill_name": "ui-designer"})` 帧 | 夹具跟上 S2 的 N5 |
| **新增** `ud_autodispatch_gates` 负用例 | stub **不发** `skill_tool` 帧 → 必须拒签、`design_unverified` | **N5 断言的反向证明，目前缺失** |
| `glue_surface` | 待查 | 单独定位 |

> 最后一行的负用例是重点：现在 `ud_autodispatch_gates` 只证明"stub 发了帧就能过"，从未证明"不发帧就过不去"。没有这条，N5 断言随时可能在某次重构里失效而无人知晓。

---

## 08 分期

| 期 | 内容 | 出口条件 |
|---|---|---|
| **S0** | 恢复门禁信号：7 个夹具一行补齐；2 个 stub 补 `skill_tool` 帧；补 N5 负用例；定位 `glue_surface` | 38 门全绿（`m1_positive` 除外，留给 S3） |
| **S1** | W1 + W2 + W3（解析器、ref 化测量、init 契约） | Y3 / Y5 / Y7 绿；`dm_measure_work.sh` P1–P9 不变 |
| **S2** | W4（planned 空交付硬停） | Y1 / Y2 / Y4 绿 |
| **S3** | W5 + W6（`design_unmeasured`、`--no-design` 记录） | Y6 / Y8 绿；`m1_positive` 转绿 |
| **S4** | W7 + W8（task-dir 绑定、worktree 可见） | Y9 / Y10 绿 |
| **S5** | W9（越界：端口/服务、plane 留痕） | Y11 / Y12 绿 |
| **S6** | W10（效率：`scaffold`、L0 路径、L1 端口做法） | 一轮真实建站 ≤ 1,100 秒且 `design_applied` |
| **S7** | 复验：重跑巴西形状，端到端 | `design_applied` + 签名记录 + 五条事实 |

**S0 必须先做。**在红色套件上叠功能正是 `S1–S4` 已经发生过的事——`ud_autodispatch_gates` 从 `c12c3c6`（01:16）起就是红的，22 分钟后巴西那一轮开跑，没有任何信号。

---

## 09 风险

| 编号 | 风险 | 处置 |
|---|---|---|
| **R1** | W4 让存量 planned 任务在合并门前多一道停机，可能卡住正在进行的变更 | 走既有 `gate-route` 停机路径，人可 `record_exception`；不新增机制 |
| **R2** | 两份 `resolve_work_ref` 漂移 | Y7 是唯一防线；若 Y7 被跳过则 Z5 失效。**这是本方案已知的最弱环节**，单点收敛留作独立变更 |
| **R3** | `design_unmeasured` 是新状态词，下游读 `design_state` 的地方可能没覆盖 | 全库 grep `design_state` 的消费点，逐个确认；门摘要显式列出四态 |
| **R4** | W6 让 `--no-design` 真正产生 `design_declined`，可能被当作绕过设计要求的合法通道 | 已有 `stated_actor` 拒模型自签（`MODEL_NAMES`）；理由与署名进门摘要，人能看见 |
| **R5** | stub 补 `skill_tool` 帧后，`ud_autodispatch_gates` 转绿，可能被误读为"断言变松了" | 同批必须落 N5 负用例；两者一起评审 |
| **R6** | `plan.py scaffold` 生成的骨架被当成内容直接交付（country-e→country-b 的抄袭已经发生过） | 骨架里放显式占位标记；design 判据的第五条（无占位符）本来就会拦 |
| **R7** | W9 的端口规则让角色在真实端口冲突时卡住 | L1 给出既定做法（申请未占用端口 / 上报），不是只给禁令 |
| **R8** | 效率估算（−29.6%）来自单轮样本 | 标注为单样本；S6 出口用真实一轮复测，不用估算值结案 |
| **R9** | `close` 反查全盘 `state.json` 可能很慢或撞到无关任务 | 限定在 `<repo>` 与 `$PWD` 两棵树内，按 `change_id` 精确匹配 |

---

## 10 回滚

每期一个提交，逐期可回退：

- **S0** 只动 `tests/`，回滚不影响产品行为。
- **S1–S3** 动 `bin/report.py` 与 `bin/plan.py`；`route_measurement` 的 `ref` 参数带默认值、`state.json` 新字段为增量、`design_unmeasured` 只在既有 `not_applicable` 分支之前插入——三者都不改变已有形状的输出，`git revert` 即可。
- **S4–S5** 独立于 S1–S3，可单独回退。
- **S6** 只新增 `scaffold` 子命令与文档，不改既有路径。

**回滚验证**：每次回退后重跑全部 38 门 + `wr_work_ref.sh`，`dm_measure_work.sh` P1–P9 逐字段比对。

---

## 附 A — 需要人决定的三件事

1. **client-x 两个服务是否拉起。**`client-x-ai-launch.service` / `client-x-maas-launch.service` 自 `2026-09-01T18:03:12Z` 起 inactive，是巴西抢 8443 的连带损伤。8443 现被巴西站占用（pid 2880147），拉起需要先决定端口归属。
2. **ai-dlc 仓库里的污染状态是否清理。**`<repo-path>/.ai-dlc/tasks/gates/gate-merge.answer.json` 是巴西项目的合并批准，写错了目录。
3. **`resolve_work_ref` 取 (a) 单点还是 (b) 两份 + 门。**本 PRD 按 (b) 写；(a) 更干净但需要先审 `plan.py` 的模块级导入副作用。

## 附 B — 本 PRD 未解决的问题

- **`glue_surface` 为何红**——只知道报 `dead-wiring references survive the 1.7 audit`，未定位。
- **13 个变更只有 1 条 design 记录**：client-x 的 design 会话确实跑了却没落记录，`bd3566a` 的 N2 backfill 是否覆盖该形状，未复验。
- **`RECORD_CORRECTION` 由模型签 `corrected_by: "human-at-terminal"`**——`stated_actor()` 未施加于该路径，与本 PRD 同族（收了署名不校验），但不在本次范围。
- **关闭 thinking 之后角色是否仍走指路牌、仍读上游**——配置已于 `2026-09-02T00:57` 改为 `extra_body.thinking.type: disabled`，此后未跑过任何 design 轮。这是 `prd-uidesigner-reliable-fast.md` 的 R10 候选，本 PRD 的 S7 复验会顺带产生第一份数据。
