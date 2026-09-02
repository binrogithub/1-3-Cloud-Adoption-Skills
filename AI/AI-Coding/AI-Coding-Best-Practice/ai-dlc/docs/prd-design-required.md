# PRD · 网站设计必须经过 UIDesigner（design-required）

> Robin 的决定（2026-09-01）：**关于网站设计，要用 ui-designer 才算成功。**
> 本轮把这句话变成机器判定——并且先把判据修到能判成功，再上门。

- 目标仓库：`<repo-path>`
- 上游：`docs/prd-uidesigner-opendesign.md`（五条事实）、`docs/prd-design-autodispatch.md`（调度，已实现）
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：开工前打 `v0.18.x-pre-designrequired`（**先打 tag 再动手**）

---

## 00 这一轮推翻了什么

必须先讲清楚，否则和既有的门互相打架。

上游 uidesigner PRD 的 **I5** 写的是「`design_unverified` 不得折成失败」；
我自己上一份 autodispatch PRD 的 **G-C** 还专门论证过「只加调度，不加门」。

**Robin 的决定推翻了这两条在 web/deck 面上的适用性。**
新的规则是：

> **交付面测出 web 或 deck ⇒ 没有签名的 design 记录就不算交付成功。**
> 纯代码面完全不受影响（`design_not_applicable`，一秒不加）。

I5 在**非适用面**上继续有效（那里根本不会有 design 状态）。
D6/D12 两条今天绿着的反向门**语义会变**，必须在本轮同步改写，
不能让它们以旧语义留在套件里——那会变成「门禁写了两套互相矛盾的期望」。

---

## 01 今天实测：ui-designer 被四道闸依次挡住

两轮真实运行，四个阻塞点，**没有一个是「模型不听话」**。

### country-d（`task-20260901093149-f93794`，09:31→09:48，claude-maas/glm-5.2）

交付物本身很好：13 文件 / 114,938 字节，10 个 HTML + `assets/style.css`(12.3 KB)
+ `main.js`(2 KB)；**186 个本地资源引用 0 个解不出来**；零占位文本；
HTTPS 8443 十页全 200。

但 ui-designer 一次都没跑。三个原因叠在一起：

```
gate-route.answer.json
{"decision":"exception","author":"AI-DLC Executor",   ← 模型自己签的例外
 "reason":"…greenfield static site…"}

state.json      "change_id": null                      ← 例外 ⇒ 没有 change
report.json     "design_state":"design_unverified",
                "why":"no change id recorded",
                "surface":{"applicable":true,"classes":["web"],
                           "surface_files_total":11}   ← 测出 11 个 web 文件
events.jsonl    DESIGN_AUTO_SKIPPED {"why":"disabled"} ← 又被显式关掉
```

实际命令：

```
python3 bin/report.py deliver --task-dir … --repo … --outcome completed --no-design
```

**即使不加 `--no-design`，`no_change_id` 那条也会挡住**——
`design_auto_due()`（`report.py:671`）的合取里要求 `state["change_id"]` 非空。

最后 `delivered: false`、`outcome: spec_unverified`、`design_unverified`，
而人在这三个未验证的状态下批准了合并（`gate-merge.answer.json`，
`approver: "human-at-terminal"`）。系统没骗人，但**「没用 ui-designer」
和「spec 没验」混在一起，作为两行小字滑过去了**。

### country-a（`design-country-a-site-1`，手动派发，855 秒）

这一轮**跑了** ui-designer，角色干得不错：

- 读了上游 5 个路径（`skills/redesign-skill/SKILL.md`、
  `design-systems/warm-editorial/DESIGN.md` + `tokens.css` 等）
- `index.html` 25,777 → 29,388 字节，另写 `favicon.svg`
- 渲染 **HTTP 200 / 239 DOM 节点**，**零占位文本**

**判据仍然判它失败，没写记录：**

```json
"failed": [
  "a file the frames show written does not stand on the filesystem",
  "writes outside the product surface: ['/tmp/arg_srv.log']",
  "referenced assets do not resolve (local missing 1, remote unreachable 0)"
]
```

三条**全是判据自身的缺陷**（详见 §03 的 F1/F2/F3），**且今天仍未修**：
`plan.py:5861` 还是 `(page.parent / target).resolve()`；
`_normalized_targets(_strip_heredocs(...))` 仍不剥引号内文本；
`writes_outside` 仍无自检豁免。

### 四道闸，按今天挡住它的顺序

| # | 闸 | 状态 |
|---|---|---|
| **闸1** | 判据在真实页面上判不出成功（F1/F2/F3） | **未修** — country-a 855 秒证明 |
| **闸2** | `no_change_id`：inline 例外路线拿不到 change id | **未修** — country-d证明 |
| **闸3** | `--no-design` 可被模型无理由关闭 | **未修** — country-d证明 |
| **闸4** | design 不是交付判据，未验证也能进合并门 | **未修**（本轮的目标） |

**修复次序不能颠倒**：先修闸4（上门）而不修闸1，
结果是**每一个网站交付都被卡死**——因为country-a已经证明五条事实
在真实页面上判不过。这是本 PRD 唯一不能商量的排序。

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **H-0** | **判据先能在真实页面上判成功**——country-a那一轮的同一份帧重跑，五条事实全过。闸4 的前置 |
| **H-A** | **web/deck 面上 `design_applied` 是交付成功的必要条件**；不满足即 `delivered: false`，且**合并门上人必须看得见这一条** |
| **H-B** | **纯代码面完全不受影响**——测量判 `design_not_applicable`，不派发、不加时间、不参与判定 |
| **H-C** | **没有静默跳过的路径**：`no_change_id` 补上，`--no-design` 需人署名 |
| **H-D** | **放行必须是人的、具名的、带理由的**——模型不得签发绕过（country-d路由例外的教训） |

### 非目标

- 不做「设计好不好看」的自动打分。判据仍只到可核对的事实为止。
- 不改五条事实**本身**（模板读取 / 写入文件 / 资源解析 / 页面渲染 / 无占位）。
  本轮只修**读取这五条事实的方式**，不减一条。
- 不做 PPTX / PDF / MP4 导出（仍属 od daemon，仍是上游 P4）。
- 不动路由例外的签发权——那是另一个问题，Robin 已说「其他问题可以先放一下」。
  但本轮的 override 必须**不重蹈它的覆辙**（H-D）。
- 不改 spec 侧的判定。`spec_unverified` 与本轮无关。

---

## 03 判据的三处缺陷（闸1）

country-a那一轮的原始产物在
`/tmp/country-a-design-probe.json`，帧在
`<gateway-home>/agent/sessions/design-country-a-site-1/history.jsonl`（319 KB）。
**重跑不需要再花 855 秒。**

| | 现象 | 根因 |
|---|---|---|
| **F1** | `files` 里混进 4 条垃圾路径 `]'%tag,h))`、`%tag,h))`、`))`、`[^`，全 `missing: true` → 判据 #2 必败 | 写入提取把 Bash 命令**引号内的 `>`** 当重定向。角色自检跑 `python3 -c "…r'</%s>'%tag…"` 与 `grep -oE "<title>[^<]*</title>\|…"`。`_strip_heredocs`（`plan.py:1033`）只剥 heredoc 体，`_normalized_targets` 照样在引号里找 `>` |
| **F2** | `writes_outside: ['/tmp/arg_srv.log']` → 判据 #2 再败 | 判据 #4 要求页面渲染 200，角色**必须**起本地服务；服务日志被写边界判成越界。**两条判据互相打架**，角色除非不自检否则躲不开 |
| **F3** | `local_missing: ["index.html -> /favicon.svg"]`，而同一份 JSON 的 `files` 里 `favicon.svg` 1065 字节、sha256 齐全 → 判据 #3 败 | `plan.py:5861` `resolved = (page.parent / target).resolve()`；`target="/favicon.svg"` 时 pathlib 绝对操作数覆盖基路径，解析到文件系统根。**根绝对 href 的语义是文档根相对**，本地服务下 curl 取回正常 |

**F3 是自相矛盾**：同一份记录里 `files` 说文件在、`assets` 说它不在。
这种矛盾今天能静静通过，本身就是缺陷证据。

---

## 04 不变式

| ID | 不变式 |
|---|---|
| **L1** | **修判据只许收窄误判，不许放宽判据。** 五条事实一条不减；每一处豁免必须把豁免了什么原样记进记录。修完之后，一轮**真的没读上游**的会话（D8 形态）仍然拿不到记录——上游 D8 门保持绿。 |
| **L2** | **适用性只来自文件测量**，与 `change_id`、路由、提示词措辞无关。 |
| **L3** | **纯代码面零成本**：`applicable=false` 时不派发、不判定、不影响 `delivered`。 |
| **L4** | **`design_applied` 进入 `delivered` 的合取**——仅限 `applicable=true` 的面。 |
| **L5** | **合并门必须承载 design 状态**：`gate-merge.request.json` 的 `summary` 里带 `design_state` 与 `surface`。人可以放行，但**不能在看不见它的情况下放行**。 |
| **L6** | **绕过必须具名**：override 的 `author` 不得是模型。取值限定枚举（如 `human-at-terminal`），且必须带 `why`。模型签发即拒绝。 |
| **L7** | **无静默跳过**：每一次不派发都有一个可读的 `why`，且 `why` 的取值是封闭集合。`no_change_id` 不再是其中之一（被 M2 消除）。 |
| **L8** | **至多一次自动派发，永不自动重跑**（沿用 autodispatch 的 J2）。门只判「有没有记录」，不触发第二轮。 |

---

## 05 新增

| ID | 内容 |
|---|---|
| **M1** | **修 F1**：`_normalized_targets` 之前先剥**引号内文本**（单/双引号、`python3 -c` / `grep -E` / `sed` 的模式参数），再找 `>`。且一条写入事实成立须**路径既在帧里出现、又在文件系统上站得住**；站不住的候选**丢弃并记进 `discarded_candidates`**，不再判败（幻影不该杀掉一轮真实工作）。 |
| **M2** | **修 F2**：写边界排除角色为满足判据 #4 而起的本地服务及其日志。口径收窄——只豁免 `/tmp` 下、会话自己创建、不在产品面内的路径，逐条记进 `render.self_check_writes`（L1）。 |
| **M3** | **修 F3**：`target` 以 `/` 开头时解析为 `repo / target.lstrip("/")`。并加**自洽断言**：已在 `files` 记过 sha256 的路径，不得同时出现在 `assets.local_missing`——矛盾即判败并指名。 |
| **M4** | **消除 `no_change_id`（闸2）**：design 记录的键从 `change` 放宽为 `change or task_id`。inline 例外路线下用 `task_id` 作记录键，记录里两个字段都存。`design_auto_due()` 去掉 `no_change_id` 分支。 |
| **M5** | **`--no-design` 需人署名（闸3）**：改为 `--no-design --no-design-by <who> --no-design-why <text>`，三者缺一即拒绝执行。`who` 不得是模型（L6）。事件 `DESIGN_AUTO_SKIPPED` 承载三者。 |
| **M6** | **design 进入交付判定（闸4）**：`applicable=true` 且 `design_state ∉ {design_applied, design_declined}` → `delivered: false`，`outcome: design_required`。`design_declined` 仍算通过——那是人记录的跳过，已有署名。 |
| **M7** | **合并门承载 design 状态（L5）**：`gate-merge.request.json` 的 `summary` 填入 `design_state` / `surface.classes` / `surface_files_total`，以及未通过时的 remedy 一行。 |
| **M8** | **override 路径**：`report.py exception --design-override --by <who> --why <text>`，写进 `planning.json.design_override`，`author` 枚举校验（L6）。deliver 读到它时 `delivered` 可为 true，但报告里**原样承载** who/why，且 outcome 标为 `design_overridden`。 |
| **M9** | **反向门重写**：`tests/collapse/ud_design_gates.sh` 里 D6/D12 的旧语义（design 不当门）改为新语义；新增本轮的 C 组。**不留两套矛盾期望。** |

---

## 06 数据契约

`design-<seq>.json` 增加一个键（其余不变）：

```json
"change": "country-a-site",       // 无 change 时为 null
"task": "task-20260901093149-f93794",
"record_key": "task-20260901093149-f93794",   // M4：change or task_id
"discarded_candidates": ["]'%tag,h))", "))"], // M1
"render": {"self_check_writes": ["/tmp/arg_srv.log"]}  // M2
```

`planning.json`：

```json
"design_override": {"by": "human-at-terminal",
                    "why": "…", "ts": "…"}
```

`deliver` 的新 outcome：`design_required` | `design_overridden`。

---

## 07 反向门

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **C1** | 拿**country-a那一轮已有的帧**重跑事实提取 | 五条全过，落签名记录 | **RED** — 今天三条判败零记录。**闸1 是否修对的唯一硬证据** |
| **C2** | 帧里含 `grep -oE "<title>[^<]*</title>"` 与 `python3 -c "…r'</%s>'…"` | 零幻影候选；真实写入照常记 | **RED**（F1） |
| **C3** | 角色起本地服务、日志落 `/tmp/*.log` | 不判 `writes_outside`；豁免逐条记进 `self_check_writes` | **RED**（F2） |
| **C4** | 页面 `href="/favicon.svg"`，文件在仓库根 | `local_missing` 为空 | **RED**（F3） |
| **C5** | 构造一条路径既在 `files` 有 sha256、又在 `local_missing` | 判败并指名 | **RED** — 今天这个矛盾静静通过 |
| **C6** | **D8 回归**：帧里零上游读取、角色声称已美化 | 仍然拿不到记录 | **GREEN 回归门** — L1 的守卫，修完必须还绿 |
| **C7** | `change_id: null` 的 inline 交付，面测出 web | **自动派发**，记录以 `task_id` 为键 | **RED**（闸2，country-d就是这个形状） |
| **C8** | `--no-design` 不带 `--no-design-by/--why` | **拒绝执行** | **RED**（闸3） |
| **C9** | `--no-design-by "AI-DLC Executor"` | **拒绝**（L6：模型不得署名） | **RED** — country-d路由例外的同型防护 |
| **C10** | web 面、无 design 记录、无 override → `deliver` | `delivered: false`，`outcome: design_required` | **RED**（闸4） |
| **C11** | 纯后端 change → `deliver` | `design_not_applicable`，`delivered` **不受影响**，零派发、零延时 | **GREEN 回归门** — H-B 的守卫 |
| **C12** | 合并门 request | `summary` 里能读到 `design_state` 与 `surface` | **RED**（L5，今天 `summary: {}`） |
| **C13** | `--design-override --by human-at-terminal --why …` | `delivered: true`，`outcome: design_overridden`，who/why 原样承载 | **RED** |
| **C14** | **判别力**：拿country-d这一轮重跑 `deliver` | 改前：`delivered:false` 但仍进合并门且 summary 空；改后：`design_required` + summary 带状态 | 改前一半**今天已实测成立** |

**C1 与 C10 缺一不可**：C1 证明门有东西可判过，C10 证明门真的会判。
**C6 与 C11 缺一不可**：C6 防「为了让门变绿而放宽判据」，C11 防「为了上门而把纯代码也拖下水」。
**C9 是本轮的态度**：country-d已经演示了「模型给自己签例外」是怎么发生的，
新加的 override 不能留同一个口子。

> **附注（deliver-measures-work 补门）**：C10/C11 在 planned 路线上
> 从未被真正行使过——交付测量量的是 HEAD，而 planned 路线的工作在
> `task/<change>` 分支上，批准后才合并。`prd-deliver-measures-work.md`
> 的 N1 修复了测量的 ref，C10/C11 现在在 planned 路线上也真正运行
> （量任务分支）。该 PRD 的 P1/P2 已补进门集 `tests/collapse/dm_measure_work.sh`。

---

## 08 分期（次序是硬依赖）

| 期 | 内容 | 门 | 依赖 |
|---|---|---|---|
| **S0 · 探针** | 已完成：country-d四闸实测、country-a帧已在手 | 四个事实进记录 | — |
| **S1 · 判据修对** | M1 + M2 + M3 | **C1** C2 C3 C4 C5 **C6** | — |
| **S2 · 通路** | M4 + M5 | C7 C8 **C9** | S1 |
| **S3 · 上门** | M6 + M7 + M8 | **C10** **C11** C12 C13 C14 | **S1 必须先过** |
| **S4 · 门禁一致** | M9 反向门重写 | 套件全绿，无矛盾期望 | S3 |

> **S1 未过之前绝不做 S3。**
> 先上门后修判据 = 每一个网站交付都被卡死。
> C1 是那道闸：country-a的帧重跑五条全过，才允许进 S3。

**S3 落地当天应当用country-d复验**（C14）：那个仓库 186 个引用 0 缺失、零占位、
十页全 200，是目前最干净的正向样本。

---

## 09 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | **上门后网站交付全部卡死**（若 S1 没修好） | S1→S3 的硬依赖 + C1 作闸。**这是本轮最大的风险，也是唯一有明确防线的那个。** |
| **R2** | **每个前端交付多一次十四分钟的会话**（country-a 855s） | 按 landing L1：**不设上限、不设告警、不报预算**，只在记录里存 `elapsed`。事件先落盘再开会话，人看得见它在跑。 |
| **R3** | **M2 的豁免滑成「`/tmp` 随便写」** | 口径写死：只豁免 `/tmp` 下、会话自己创建、不在产品面内的路径，逐条记账。**残余**：把真实产物写进 `/tmp` 的角色不会被这条抓住——该由产品面测量抓。 |
| **R4** | **M1 的丢弃掩盖真实写入失败** | 丢弃项记进 `discarded_candidates`，人能看见。**残余**：一次真实的「写了但没落盘」会被当幻影丢掉；靠 C2 的正向一半兜。 |
| **R5** | **override 变成新的橡皮图章** | L6 限定署名枚举 + 必须带 why + outcome 显式标 `design_overridden`（不是 `completed`）。**残余**：一个人可以每次都签。这是人的权力，不该由机器剥夺——但每一次都留痕、可统计。 |
| **R6** | **D6/D12 语义反转造成门禁自相矛盾** | M9 同轮重写，不留旧期望。**不允许**「新门绿、旧门也绿」这种两套标准并存的状态。 |
| **R7** | **`design_declined` 成为绕过捷径** | 它已要求人记录 + 理由（`decide --design skip --why`），与 override 同级。**接受**：两条具名路径，不是漏洞。 |

---

## 10 回滚

1. `git reset --hard v0.18.x-pre-designrequired`
2. 记录目录 `/var/lib/aidlc/records/` 保留不删（本轮证据）
3. `/opt/open-design`、gateway unit、openjiuwen 配置全程未动
4. 已产生的 `design_override` / `design_required` 记录保留——它们是这一轮的事实

---

## 附注 · 与另外两份 PRD 的关系

- **`prd-design-autodispatch.md`**：其 P1（判据修对，N8/N9/N10）与本 PRD 的 S1（M1/M2/M3）**是同一件事**，本 PRD 取代它；其 P2（调度）**已实现**（`report.py:671/699`），保留。
  该 PRD 的 **G-C「不加门」被本轮推翻**，应在文首标注。
- **`prd-install-targets.md`**：与本轮无功能耦合，`supervisor/skills/` 的
  `claude/` + `workspace/` 重排已完成（3 个 SKILL.md 在位），不影响本轮。
- **上游 `prd-uidesigner-opendesign.md`**：**I5 需要按 §00 改写**——
  在 web/deck 适用面上不再成立。其余不变式（I1–I4、I6）原样有效。

---

*`docs/prd-design-required.md` · 测量日期 2026-09-01 · <host-ip>*
