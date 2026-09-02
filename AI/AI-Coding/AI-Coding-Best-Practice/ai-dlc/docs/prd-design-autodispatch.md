# PRD · design 自动派发（design-autodispatch）

> 把「测出来适用」和「真的跑了」之间那段空白补上——
> 补的方式是加调度，不是加门。
> 而在加调度之前，得先让判据认得出一轮真做了活的会话。

- 目标仓库：`<repo-path>`
- 上游 PRD：`docs/prd-uidesigner-opendesign.md`（v0.18.0，已实现）
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：本轮开工前打 `v0.18.0-pre-autodispatch`（**先打 tag 再动手**）

---

## 01 问题

2026-09-01 在 217 上跑了一轮阿根廷网站（change `country-a-site`，repo
`/tmp/Argentia`）。产出是一个 25,777 字节的 `index.html`。**ui-designer
一次都没被调用。**

不是判据失效，也不是测量错了。三条现场记录说明它坏在哪：

`/tmp/Argentia/.ai-dlc/tasks/country-a-m1/report.json` —— 测量是对的：

```json
"design": {
  "design_state": "design_unverified",
  "why": "no signed design record exists; the design dispatch produces the record from its session's frames …",
  "remedy": "plan.py design --change <id> --repo <repo>",
  "surface": {"applicable": true, "classes": ["web"],
              "surface_files": ["index.html"], "surface_files_total": 1,
              "measured_files": 8}
}
```

同目录 `planning.json` —— 这一轮真正派发过的角色：

```json
"plane_dispatches": { "validate": {…}, "archive": {…} }
```

`events.jsonl` —— 整条任务流：

```
TASK_STARTED → DELIVERY_REPORT → NEED_HUMAN(gate-merge) → GATE_APPROVED → DELIVERY_REPORT
```

**`design` 从未出现。** 系统正确地测出「这是网页面、适用」，正确地写下
「没有签名记录，所以 design_unverified」，正确地把 remedy 印在报告里——
然后没有任何一段代码或指令去执行那条 remedy。

v0.18.0 交付了四样东西里的三样：**能力**（`plan.py design` 这个 verb）、
**判据**（五条事实 + HMAC 签名记录）、**诚实报告**（四态，且不当门）。
唯独没交付第四样：**调度**。

### 第二层：就算派发了，今天也交不出记录

开工前我在 country-a 上**手动派了一整轮**（会话 `design-country-a-site-1`，
855 秒，`client_rc: 0`，`round_complete: true`）。角色干得不错：

- 读了上游 5 个路径（`skills/` 目录、`skills/redesign-skill/SKILL.md`、
  `design-systems/warm-editorial/DESIGN.md` + `tokens.css`）
- 把 `index.html` 从 25,777 改写到 29,388 字节，另写了 `favicon.svg`
- 页面渲染 **HTTP 200 / 239 个 DOM 节点**
- **零占位文本**

**然后判据判它失败，没有写记录：**

```json
"failed": [
  "a file the frames show written does not stand on the filesystem",
  "writes outside the product surface: ['/tmp/arg_srv.log']",
  "referenced assets do not resolve (local missing 1, remote unreachable 0)"
]
```

三条全部是**判据自身的缺陷**，没有一条是角色没做好活：

| | 现象 | 根因 |
|---|---|---|
| **F1** | `files` 里混进四条垃圾路径：`]'%tag,h))`、`%tag,h))`、`))`、`[^`，全部 `missing: true` | 写入事实提取把 **Bash 命令里引号内的 `>`** 当成重定向。角色跑自检 `python3 -c "… re.findall(r'</%s>'%tag,h) …"` 和 `grep -oE "<title>[^<]*</title>\|…"`，正则里的 `>` 被解析成写目标。`_strip_heredocs`（`plan.py:1033`）只剥了 heredoc 体，**没处理引号内的 `>`** |
| **F2** | `writes_outside: ['/tmp/arg_srv.log']` | 判据 #4 要求「页面渲染 200」，角色就得起本地服务；服务日志写到 `/tmp`。**判据要求的动作的副产品，被判成越界写** |
| **F3** | `assets.local_missing: ["index.html -> /favicon.svg"]`，可同一份 JSON 的 `files` 里 `favicon.svg` 1065 字节、sha256 齐全 | `plan.py:5861` 是 `resolved = (page.parent / target).resolve()`。`target = "/favicon.svg"` 时 pathlib 的绝对操作数覆盖基路径 → 解析成文件系统根的 `/favicon.svg`。**根绝对 href 是文档根相对，不是文件系统绝对**；页面在本地服务下取回 200，文件就在仓库根 |

F3 尤其刺眼：**同一份 JSON 里 `files` 说这个文件在、`assets` 说它不在。**

这一层决定了本轮的次序。**光加自动派发是有害的**：加完之后每个前端 change
都会自动跑一个十四分钟的会话，然后可靠地报 `design_unverified`——
比今天更慢，结果一样。**必须先把判据修对，再让它自动跑。**

---

调度本来应该落在编排 playbook 里。`supervisor/skills/claude/ai-dlc/SKILL.md`
的任务流是五步：

```
1 · WORK   →  1b · REVIEW  →  2 · CHECK  →  3 · REPORT  →  4 · MERGE_GATE
```

五步里没有 design 这一步。两份已部署副本——仓库里的
`supervisor/skills/claude/ai-dlc/SKILL.md`（sha `19b5c3ba`，2026-09-01 07:55）
与实际被读的 `<cc-glm-config>/skills/ai-dlc/SKILL.md`（同 `19b5c3ba`，
07:54 外部同步）——**都不含 `plan.py design` 这三个字**。

所以 country-a 的行为是系统当前设计的**正确行为**。要修的不是一个
分支写错了，是一段从来没有被建造过的接线。

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **G-0** | **判据先认得出真实页面上的真实工作**——一轮读了上游、写了页面、渲染 200、零占位的会话，必须能拿到记录。今天拿不到（§01 第二层），这是 G-A 的前置 |
| **G-A** | 网页 / 前端 / PPT 类交付面上，design 轮**自动派发一次**，不依赖任何人记得敲命令 |
| **G-B** | 纯代码变更**永不派发**——由产品面文件测量决定，不由提示词里的形容词决定（这一半 v0.18.0 已实现，本轮只是不许弄坏） |
| **G-C** | **不把 design 变成门**：design 轮失败、或产出仍是 `design_unverified`，交付照常完成。上游 I5 不破 |
| **G-D** | **至多两次完成的自动派发**（deliver-measures-work Q4 收窄）——半截不算一次，`attempts` 上限 2 |
| **G-E** | 调度点落在**机器上**，不落在模型的服从性上：能不能跳过这一步，不取决于编排会话有没有读到那句话 |
| **G-F** | 「派没派、为什么没派」是**可核对事实**——写进 `planning.json` 与 `events.jsonl`，不是模型的自述句 |

### 非目标

- 不做「设计好不好看」的自动打分。判据仍然只到可核对的事实为止。
- 不改五条事实判据（模板读取 / 写入文件 / 资源解析 / 页面渲染 / 无占位）。
- 不引入成本门、token 上限、耗时告警——landing L1 的禁令继续有效。
- **不做 PPTX / PDF / MP4 导出。** 那仍然属于 od daemon，仍然是上游 PRD 的 P4，
  本轮之后仍然不许在任何地方写「支持 PPT 导出」。本轮只让 `.pptx`
  这类**交付面**触发 design 轮，不让它导出任何东西。
- 不改 review 轮的 axes 机制，不改合并门。

### 一个必须先说清楚的紧张关系

用户的要求是「**自动调用**」；上游 PRD 的 I5 写的是「`design_unverified`
**不得折成失败、不得触发自动重跑**」。这两条**不矛盾**，但只在一种读法下不矛盾：

> **调度（scheduling）** 与 **门禁（gating）** 是两件事。
> 「适用就自动跑一次」是调度。「没跑就不许交付」是门禁。
> 本轮只加前者，明确拒绝后者。

而 I5 禁止的是**重跑**（re-run）——第一次跑不是重跑。所以本轮的形态是：
**适用 → 自动跑一次 → 跑成什么样都如实报告 → 失败绝不自动再来一次。**
三条同时成立，与既有的 D6 / D12 反向门不冲突（那两条今天是绿的，本轮之后必须还是绿的）。

---

## 03 不变式

验收逐条判定，不接受「大致做到了」。

| ID | 不变式 |
|---|---|
| **J1** | `applicable=false` 时**零派发**——不开会话、不写记录。沿用现有 exit 24 的同一处测量，纯后端 change 买不到美化。 |
| **J2** | 每个 change **至多两次完成的**自动派发（deliver-measures-work Q4 收窄）。半截尝试（`rc: null`，进程被杀）**不算一次**——`design_auto_due()` 对 incomplete 返回 due，允许再派。`attempts` 计数器只数完成的（`rc is not None`）；`attempts >= 2` 才返回 `already_attempted`。尝试事实记在 `planning.json.design_auto`。 |
| **J3** | 自动轮的成败**不改变 `delivered`**。四态语义原样不变，`design_unverified` 仍不进 delivered 的合取。 |
| **J4** | 存在 `planning.json.design_decision.skip` 时**不派发**，报 `design_declined` 并原样承载理由。 |
| **J5** | 调度发生在**产品文件落地之后、交付报告定稿之前**——design 轮读的是已落地的前端面，不是空目录。 |
| **J6** | 「派了 / 没派 / 为什么没派」是**帧与文件之外的第三方记录**：`events.jsonl` 事件 + `planning.json` 字段，任何一次调度都能事后重建。 |
| **J7** | 关掉自动调度必须是**显式的**（`--no-design`），且报告里写明是被显式关掉的，不静默省略。 |
| **J8** | **判据的修补只许收窄误判，不许放宽判据。** 五条事实一条不减；N8/N9/N10 每一处豁免都必须把豁免了什么原样记进记录，可事后核对。判据修完之后，一轮**真的没读上游**的会话（D8 形态）仍然必须拿不到记录——上游 D8 门保持绿。 |

---

## 04 实测约束

2026-09-01 在 217 上测的，每一条都决定了方案边界。

**E1 · 坏在调度，不在链路。**
country-a 的三份记录（§01）证明测量、报告、remedy 全部正确，缺的只有执行。

**E2 · 会话链路可用，但判据在真实页面上判不出记录。**
`/var/lib/aidlc/records/ud1-web/design-001.json` 证明五条事实**能**全过
（模板 sha 已存、`index.html` 25,216 字节、`status 200 / dom_nodes 191`、
零占位、`local_missing: []`）——但那是一个自制的最小页面。
country-a 这个真实页面上，同一套判据 855 秒后**三条判失败、零记录**（§01 第二层）。
**结论：`plan.py design` 的内部必须动，而且要先于调度动。**

**E9 · 写入事实把引号内的 `>` 当重定向（F1）。**
`_strip_heredocs`（`plan.py:1033`）只剥 heredoc 体。角色自检时跑的
`python3 -c "… r'</%s>'%tag …"` 与 `grep -oE "<title>[^<]*</title>|…"`，
正则里的 `>` 被 `_normalized_targets` 解析成写目标，产出四条不存在的路径，
判据 #2「写了哪些文件」因此**必然**失败。v0.18.0 的 CHANGELOG 声称修过这一类
（「truncated arguments blob read as shell text」），**修得不完整**。

**E10 · 判据要求的动作，被另一条判据判成违规（F2）。**
判据 #4 要求页面渲染 200，角色就得起本地静态服务；服务日志 `/tmp/arg_srv.log`
被写边界判成 `writes_outside`。**两条判据互相打架**，且这不是角色能规避的
——除非它不自检。

**E11 · 根绝对资源引用解错（F3）。**
`plan.py:5861` `resolved = (page.parent / target).resolve()`；
`target="/favicon.svg"` 时 pathlib 的绝对操作数覆盖基路径，解析到文件系统根。
根绝对 href 的语义是**文档根相对**（本地服务下 curl 取回正常）。
同一份 JSON 里 `files` 记着 `favicon.svg` 1065 字节而 `assets` 说它缺失
——**自相矛盾即缺陷证据**。

**E3 · 「不是门」这一半已经成立，别弄坏它。**
`report.py deliver` 重跑 country-e-m1：`delivered: True` / `outcome: completed`
与 `design_state: design_unverified` 同时成立。D12 的鉴别力就靠这个。

**E4 · import 方向是单向的。**
`bin/plan.py:257` 有 `from report import (…)`；`bin/report.py` **不 import plan**。
所以调度若落在 report 侧，**必须 subprocess 调 `bin/plan.py design`，不能 import**——
反向 import 会造成循环。

**E5 · playbook 有两份副本且曾经分叉。**
仓库 `supervisor/skills/claude/ai-dlc/SKILL.md` 与
实际被读的 `<cc-glm-config>/skills/ai-dlc/SKILL.md`
于 2026-09-01 07:54–07:55 被外部同步，两份现在都是 `19b5c3ba`。
但 `ai-dlc-doctor` 那条今天还分着（`e957ca7e` vs `6f8bf7af`），
结论不变：会分叉、需要门。
**只改仓库那份等于没改。** 这与「前端从未发布」是同型的坑，本轮必须带一条新鲜度门。
该门已合并到 `install.sh --doctor` 的 manifest 一致性检查（K5），
见 `docs/prd-install-targets.md` N7 segment ②。

**E6 · design 轮很慢。**
`--timeout` 的帮助文本自己写着「design rounds run long — any-directory's
read-in-place measured 792s」。自动派发会把 `report.py deliver`
从秒级变成十分钟级。**这是本轮最大的真实代价，必须正面承认，不许藏。**

**E7 · 适用性扩展名表的现状与缺口。**
`report.py:555` 起：
`DESIGN_WEB_EXTS = (.html .htm .css .scss .jsx .tsx .vue .svelte .astro)`；
deck = `.pptx` ∪（`slides/` 或 `deck/` 下的 `.html`）∪（带 `deck:` /
`od.mode: deck` frontmatter 的 `.md`）。
**缺 `.less` `.styl` `.sass`。** 一个只有 `.less` 的前端 change 今天测不出来。

**E8 · `deliver` 是合并门的唯一入口。**
`G-DELIVER-1` 与 `MERGE_GATE` 都由 `report.py deliver` 产出。
编排会话想拿到合并门就必须经过它——**这正是 G-E 要的那个「跳不过去的点」。**

---

## 05 目标架构

调度点放在 **`report.py deliver`**，理由是 E8：它是唯一产出 `G-DELIVER-1`
与合并门的路径，编排会话绕不过去。而它**本来就已经在算** `design_validation()`
（`report.py:603`）——「适用吗、有记录吗、有人记录跳过吗」这三个判断今天就在那儿跑，
本轮只是把第四个判断（「试过了吗」）接在同一处，并在结论为 due 时**执行一次** remedy。

```
report.py deliver
  │
  ├─ 测量产品面 ──────────────► design_surface()        （已有，不动）
  │
  ├─ due? = applicable
  │         ∧ 无签名 design 记录
  │         ∧ 无 design_decision.skip
  │         ∧ planning.json.design_auto 未记录过尝试
  │         ∧ 未传 --no-design
  │
  ├─ due  → subprocess: bin/plan.py design --change … --repo … --task-dir …
  │            │                                （E4：subprocess，不 import）
  │            ├─ 写 planning.json.design_auto  （J2：尝试即记录，先记后跑）
  │            └─ 写 events.jsonl DESIGN_AUTO_DISPATCHED
  │
  ├─ 重读 design_validation()  ─► 四态照旧（J3：成败都不改 delivered）
  │
  └─ G-DELIVER-1 / MERGE_GATE  （不变）
```

**为什么不放在 playbook 里（方案 A，已否决）**
「在 SKILL.md 里加一步 1c·DESIGN」是最便宜的做法，但 country-a 恰好证明了
它的失效模式：一条没有工件的指令，被跳过时**不留任何痕迹**——你只能从
「记录里没有」反推「大概没跑」，无法区分「跳过了」和「跑了但失败了」。
这正是这个项目一直在收容的东西：**判据不能只落在模型的服从性上。**
playbook 那一步照样要加（N4），但它是**叙述**，不是执行依赖。

**为什么不做成门（方案 B，已否决）**
「applicable 且无记录 → deliver 拒绝出报告」违反上游 I5，并且会把
D6 / D12 两条今天绿着的反向门直接判红。用户要的是「自动跑」，不是「跑不了就别交付」。

**代价（正面承认）**
`deliver` 从**纯读**变成**可能开一个长会话**。这是真实的架构让步，用三件事限界：
`--no-design` 显式关闭（J7）、至多一次（J2）、以及所有夹具测试一律走 `--no-design`
（否则测试套件会被十分钟一次的真实会话拖垮）。

---

## 06 适用性：谁决定它出不出现

**沿用 v0.18.0 已实现且已测的那一套，本轮只补三个扩展名。**
不由模型判，不由提示词里有没有「网站」两个字判，由产品面文件测量判。

| 类 | 扩展名 |
|---|---|
| web | `.html` `.htm` `.css` `.scss` **`.less`** **`.styl`** **`.sass`** `.jsx` `.tsx` `.vue` `.svelte` `.astro` |
| deck | `.pptx`；`slides/` 或 `deck/` 下的 `.html`；带 `deck:` / `od.mode: deck` frontmatter 的 `.md` |

粗体是本轮新增（E7）。`web + deck ≥ 1` 判**适用**，否则不适用。
`delivery.product_excludes` 原样先生效——被排除的文件不进测量。

**纯代码开发就是「不适用」这一支**：一个只改 `.py` / `.go` / `.ts`（非 `.tsx`）
/ `.sql` 的 change，测量结果 `applicable: false`，
`deliver` 报 `design_not_applicable`，**不开会话、不写记录、不加一秒钟**。
这一支今天就已经工作（`plan.py design` 对它 exit 24），本轮的新增
只是让「适用」那一支也自己动起来。

### 四态（不变）

| 状态 | 含义 |
|---|---|
| `design_not_applicable` | 测量判不适用（纯代码开发落在这里） |
| `design_declined` | 适用、有人记录了跳过，理由原样承载 |
| `design_unverified` | 适用、无签名记录——**不失败**，本轮之后也**不自动再跑** |
| `design_applied` | 适用、有签名记录且五条判据全过 |

---

## 07 新增

| ID | 内容 |
|---|---|
| **N1** | **due 判定与一次性自动派发**：`report.py deliver` 按 §05 判 due，due 时 subprocess 调 `bin/plan.py design` 一次（E4），回来重读 `design_validation()` 再定稿报告。新增 `--no-design` 显式关闭（J7）。 |
| **N2** | **`planning.json.design_auto`**：`{attempted_at, rc, session, outcome, elapsed_seconds}`。**先写后跑**——进程被杀也留下「试过」的事实，否则 J2 会被一次崩溃绕过。 |
| **N3** | **事件**：`DESIGN_AUTO_DISPATCHED`（带 change / rc / outcome / elapsed）与 `DESIGN_AUTO_SKIPPED`（带 `why` ∈ `not_applicable` / `record_exists` / `declined` / `already_attempted` / `disabled`）写入 `events.jsonl`（J6）。 |
| **N4** | **playbook 加 `1c · DESIGN` 一步**，位置在 `1 · WORK` 与 `2 · CHECK` 之间，说明「前端面会由 deliver 自动派发一次，你不需要手敲；要跳过就 `decide --design skip --why …`」。**两份副本同步**（E5）。 |
| **N5** | **扩展名表补 `.less` `.styl` `.sass`**（E7）。 |
| **N6** | **反向门** `tests/collapse/ud_autodispatch_gates.sh`（新文件，与既有 `ud_design_gates.sh` 并列，避免把慢路径混进已绿的套件）。 |
| **N7** | **部署新鲜度门**：已合并到 `install.sh --doctor` 的 manifest 一致性检查（K5），见 `prd-install-targets.md` N7 segment ②。 |
| **N8** | **写入事实只认真正的重定向（修 F1／E9）**：`_strip_heredocs` 之外再剥**引号内文本**——单引号、双引号、`python3 -c` / `grep -E` / `sed` 的模式参数——再找 `>`。判据：一条写入事实要成立，路径必须**既在帧里出现、又在文件系统上站得住**；站不住的候选**不再判失败，而是丢弃并记进 `discarded_candidates`**（幻影不该杀掉一轮真实工作）。 |
| **N9** | **自检副产品不算越界写（修 F2／E10）**：写边界判定排除角色为满足判据 #4 而起的本地服务及其日志。收窄口径，不是开洞——只豁免 `/tmp` 下、会话自己创建、且不在产品面内的路径，并把豁免了什么原样记进 `render.self_check_writes`，可核对。 |
| **N10** | **根绝对引用按文档根解析（修 F3／E11）**：`target` 以 `/` 开头时解析为 `repo / target.lstrip("/")`，而非 `page.parent / target`。同时加一条自洽断言：**一个已在 `files` 里记过 sha256 的路径，不得同时出现在 `assets.local_missing`**——自相矛盾即缺陷，直接失败并指出是哪一条。 |

---

## 08 数据契约

`planning.json` 新增一个顶层键：

```json
"design_auto": {
  "attempted_at": "2026-09-01T08:12:44Z",
  "change": "country-a-site",
  "rc": 0,
  "outcome": "design_applied",
  "session": "design-country-a-site-1",
  "elapsed_seconds": 512.3,
  "trigger": "deliver"
}
```

- `outcome` ∈ `design_applied` | `design_unverified`（自动轮跑了但五条事实没全过）
- **键存在即视为「已尝试过」**，与 `rc` 无关（J2）。

`events.jsonl` 两个新事件：

```json
{"event":"DESIGN_AUTO_DISPATCHED","change":"…","rc":0,
 "outcome":"design_applied","elapsed_seconds":512.3,"ts":"…"}

{"event":"DESIGN_AUTO_SKIPPED","change":"…",
 "why":"not_applicable|record_exists|declined|already_attempted|disabled",
 "surface":{"applicable":false,"classes":[]},"ts":"…"}
```

**退出码不新增。** 自动轮失败**不改变** `deliver` 的退出码——这是 J3 的机器形式。

---

## 09 部署

一次性，幂等。改动全部在 `ai-dlc` 仓库内，加一次 playbook 同步。

```bash
# 0. 先打回滚锚点（不许省）
git -C <repo-path> tag v0.18.0-pre-autodispatch

# 1. 代码：bin/report.py（N1/N2/N3/N5）
#    plan.py 内部不动——E2 已证明链路可用

# 2. playbook：仓库改完，同步到实际被读的那一份，先备份
cp <cc-glm-config>/skills/ai-dlc/SKILL.md \
   <cc-glm-config>/skills/ai-dlc/SKILL.md.bak.$(date +%s)
install -m 0644 <repo-path>/supervisor/skills/claude/ai-dlc/SKILL.md \
   <cc-glm-config>/skills/ai-dlc/SKILL.md

# 3. 读回断言（不接受「写过了」）
sha256sum <repo-path>/supervisor/skills/claude/ai-dlc/SKILL.md \
          <cc-glm-config>/skills/ai-dlc/SKILL.md
#    两行前 64 位必须相同 —— 这就是 N7 的门
```

**不需要动的**：`/opt/open-design`（pin 未变）、openjiuwen `config.yaml`、
`skills_state.json`、gateway unit、`ui-designer/SKILL.md`。上游 PRD 的
收容边界（I1–I4、N5 壳掩码）本轮全程不动，其反向门必须保持绿。

---

## 10 反向门

每条标注今天判什么，**不装红**。

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **A1** | 纯后端 change 上 `deliver` | 零派发，`design_not_applicable`，stub client 从未被调用 | **GREEN 回归门**——今天本来就不派发，它防的是新调度把纯代码 change 也拖进会话 |
| **A2** | 前端 change、无记录、无 skip → `deliver` | 自动派发一次，落签名记录，`design_applied` | **RED**（今天零派发） |
| **A3** | 同一 change 第二次 `deliver` | **不再派发**（读到 `design_auto`），状态原样 | **RED**（今天连字段都没有） |
| **A4** | 自动轮以 D8 形态失败（帧里零上游读取） | 无记录、`design_unverified`、**`delivered` 仍为 true**、退出码不变 | **RED** — **J3 的核心判别力** |
| **A5** | 已 `decide --design skip --why …` | 不派发，`design_declined`，理由原样 | **RED** |
| **A6** | `deliver --no-design` | 不派发，且报告写明 `why: disabled` | **RED** |
| **A7** | **判别力**：拿 `country-a-site` 重跑 `deliver` | 改前：`design_unverified` 且零派发；改后：自动派发并落记录 | 改前一半**今天已实测成立**（§01），改后一半 **RED** |
| **A8** | 两份 playbook 副本 sha256 | 相同 | **RED** → **合并到 `install.sh --doctor`**（K5，见 `prd-install-targets.md` N7②）；`ai-dlc` 已同步（`19b5c3ba`），`ai-dlc-doctor` 仍分叉 |
| **A9** | 上游 `ud_design_gates.sh` 全套 | 原样 PASS | **GREEN 回归门**（今天实测 EXIT=0，本轮之后必须还是） |
| **A10** | 自动派发进程被杀（跑到一半 SIGKILL） | `design_auto` 已存在 → 下一次 `deliver` 不重跑 | **RED** — 防 J2 被一次崩溃绕过 |
| **A11** | 帧里含 `grep -oE "<title>[^<]*</title>"` 与 `python3 -c "…r'</%s>'…"` | 零幻影写入候选；真实写入照常记 | **RED**（今天产出 4 条垃圾路径，直接判败） |
| **A12** | 角色起本地服务自检、日志落 `/tmp/*.log` | 不判 `writes_outside`；豁免项原样记进 `render.self_check_writes` | **RED** |
| **A13** | 页面用 `href="/favicon.svg"`，文件在仓库根 | `local_missing` 为空 | **RED** |
| **A14** | **自洽断言**：构造一条路径既在 `files` 有 sha256、又在 `local_missing` | 判败并指名这条路径 | **RED** — 今天这个矛盾状态能静静通过 |
| **A15** | **端到端判别力**：拿 country-a 这一轮的**同一份帧**重跑事实提取 | 五条事实全过，落签名记录 | **RED** — 今天三条判败零记录；这是「判据修对了没有」的唯一硬证据 |

**A4 与 A7 缺一不可**：A4 防「把调度做成了门」，A7 防「新调度对现状无差别」。
**A1 与 A9 缺一不可**：A1 防「为了自动而把所有 change 都拖进会话」，
A9 防「新路径把已收容的边界撞开」。

夹具里 A1–A6、A10 全部用 **stub client**，不开真实会话；
A2 的正向控制**必须**另跑一次真实会话（不能只有夹具），否则等于没测。

---

## 11 分期

**次序是本轮唯一不能商量的东西：先把判据修对，再让它自动跑。**
倒过来做，等于给每个前端 change 加十四分钟，换一个和今天一样的
`design_unverified`。

| 期 | 内容 | 门 |
|---|---|---|
| **P0 · 探针** | 已完成：country-a 三份记录定位调度缺失（§01 第一层）；**手动派发一整轮（855s）暴露三条判据缺陷**（§01 第二层 / E9–E11）；playbook 分叉实测（E5） | 五个事实进记录 |
| **P1 · 判据修对** | N8 + N9 + N10：幻影写入、自检副产品、根绝对引用，加自洽断言 | A11 A12 A13 A14 **A15** |
| **P2 · 调度** | N1 + N2 + N3：due 判定、一次性自动派发、记录与事件 | A1 A3 A4 A5 A6 A10 |
| **P3 · 正向** | 真实会话的正向控制 + N5 扩展名 | **A2** A7 |
| **P4 · 部署面** | N4 playbook 两份同步 + N7 新鲜度门 | **A8** |
| **P5 · 回归** | N6 入 `tests/collapse/`，上游套件复跑 | **A9** |

P1 让判据认得出真实页面上的真实工作；P2 让「适用就会跑」成真；
P3 证明它跑出来的东西是被承认的；P4 让改动真的到达运行态（E5 的教训）；
P5 证明没撞坏已有的收容。

**P1 未过之前不要接 P2**——A15 是那道闸：拿 country-a 这一轮**已经存在的帧**
重跑事实提取，五条全过才算判据修对了。帧已经在
`<gateway-home>/agent/sessions/design-country-a-site-1/history.jsonl`（319 KB），
**不需要再花 855 秒**。
**P3 之前不要在任何地方写「已自动接入 ui-designer」。**

---

## 12 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | `deliver` 从秒级变十分钟级（E6） | 正面接受。记 `elapsed_seconds` 进 `design_auto`，**不设上限、不设告警、不报预算**（landing L1 禁令继续有效）。人看得见它在跑（`DESIGN_AUTO_DISPATCHED` 事件先落盘再开会话）。 |
| **R2** | `deliver` 从纯读变成会派发会话——真实的架构让步 | 三重限界：`--no-design`（J7）、至多一次（J2）、夹具一律 `--no-design`。**不假装这不是代价。** |
| **R3** | 自动轮会**覆盖人已手改的页面** | 写边界仍是测出的前端面，且每个 change 只跑一次。记录里存改动前后的文件 sha256，覆盖了什么可核对。**残余风险接受**：一个人手改过又没记 skip 的页面，会被自动轮改写。 |
| **R4** | 编排会话绕过 `deliver` 直接合并 | 绕过即没有 `G-DELIVER-1`，事后可检出。与上游 R1 同形：**承认「跳不过去」是尽力而为，不在验收里写成已强制。** |
| **R5** | playbook 副本再次分叉 | N7 的新鲜度门每次跑；但门只在跑的时候咬人。**残余**：两次运行之间被人手改仍然可能。 |
| **R6** | 自动轮把一个本该 `design_declined` 的 change 跑了 | 顺序保证：skip 决定先于派发被读（J4）。但**决定必须在 `deliver` 之前记**，事后再记只能靠下一轮。 |
| **R7** | 上游 PRD 的 §08 契约、回滚锚点、E1/E3 数字已与现场脱节 | 与本轮无功能耦合，但同一份 `docs/` 下的两份 PRD 互相矛盾会误导下一轮。**建议本轮顺手回写**（见附注）。 |
| **R8** | **N9 的豁免被当成开洞**——「自检副产品不算越界」很容易滑成「`/tmp` 下随便写」 | 口径写死：只豁免 `/tmp` 下、会话自己创建、不在产品面内的路径，且**逐条记进 `render.self_check_writes`**。J8 管着它：豁免了什么必须能被读出来。**残余**：一个把真实产物写进 `/tmp` 的角色不会被这条抓住——该由产品面测量抓，不由这条抓。 |
| **R9** | **N8 把幻影候选从「判败」改成「丢弃」，可能掩盖真实的写入失败** | 丢弃的候选逐条记进 `discarded_candidates`，人能看见丢了什么。**残余**：一次真实的「写了但文件没落盘」会被当成幻影丢掉。用 A11 的正向一半兜——真实写入必须照常出现在 `files` 里。 |

---

## 13 回滚

1. `git reset --hard v0.18.0-pre-autodispatch` 恢复 `ai-dlc`
2. `<cc-glm-config>/skills/ai-dlc/SKILL.md` 从 `.bak.<ts>` 还原
3. 记录目录 `/var/lib/aidlc/records/` **保留不删**，作为本轮的证据
4. `/opt/open-design`、openjiuwen 配置、gateway unit 全程未动，回滚不涉及

---

## 附注 · 上游 PRD 的四处脱节（建议同轮回写）

`docs/prd-uidesigner-opendesign.md` 实现得比它自己写的更严，但文本没同步。
本轮不改它会留下两份互相矛盾的 PRD：

1. **§03 I3**：写「`root:root 0555` 即只读」。实测 **root 的 DAC 不受权限位约束**
   （宿主上 `touch /opt/open-design/ZZZ` 成功，rc=0）。实际强制点是 gateway unit 的
   `ReadOnlyPaths=/opt/open-design`（命名空间内实测 `Read-only file system`）。
   **按 PRD 字面验收会通过但实际不成立。**
2. **§13 回滚锚点**：写 `v0.13.0-pre-uidesigner`，仓库里没有这个 tag；
   实际是 `v0.17.0-pre-uidesigner`。照 PRD 回滚会直接失败。
3. **§08 契约字段形状**：`surface` 字符串 → 数组 `["web"]`；`render` 单对象 → 按页数组；
   `assets` 多出 `refs_checked`；`files[].path` 是仓库相对路径而非绝对路径。
4. **§04 数字**：PRD 说 139 skills / 115 templates / 154 systems，
   实测 **162 / 114 / 153**；sparse 实测 **138M**（全量 1.8 GB），R6 磁盘风险不触发。

---

*`docs/prd-design-autodispatch.md` · 测量日期 2026-09-01 · <host-ip>*
