# PRD — UIDesigner 角色：把 OpenDesign 接到 plane 上，只给前端与 PPT 用

状态：待评审 · 目标机器 <host-ip> · 仓库 `<repo-path>`
（master `540c4b2`）· 现行技能 v0.11 · 上游 `nexu-io/open-design`
（Apache-2.0，pin `open-design-v0.21.1`，2026-08-31）

回滚锚点：落地前在 master 打 `v0.13.0-pre-uidesigner`。

---

## 1. 问题

pipeline 现在能把一个网站从需求做到能跑，但**做不到能看**。
`country-b-tourism` / `country-e-tourism` / `landing` 这几轮交付的页面
都是模型凭记忆手写的 CSS：能过 `--strict`、能返回 200、能通过交付面测量，
但没有任何一条判据说过它长什么样。设计是当前 pipeline 唯一**完全没有工件、
没有判据、没有记录**的产出维度。

OpenDesign（`nexu-io/open-design`）恰好是这一维度的现成资产：
`skills/` 下 139 个功能技能、`design-templates/` 下 115 套渲染模板、
`design-systems/` 下 154 套品牌设计系统，全部是**文件系统上的 markdown +
side files**，不是一个需要调用的服务。它天然适合被派发进一个会话里读。

但直接把它塞给 Claude Code 会同时踩两个已经付过代价的坑：

1. **判据与被判对象同源**（`ai-dlc-self-certifying-loop`）。CC 自己挑模板、
   自己写页面、自己说"已美化"，和 openspec 收容前的形态一模一样。
2. **技能全局暴露**。openjiuwen 的 `react.skill_mode: all` 让 workspace 下
   的技能对**每一次派发**可见——把 139 个设计技能链进去，author、validate、
   implement 全都会在提示里看到它们。这不是"可选角色"，这是全局污染。

所以本 PRD 要解决的不是"能不能用 OpenDesign"，是**在哪一侧用、由谁判、
怎么只在该用的时候出现**。

---

## 2. 目标与非目标

**目标**

- G-A 新增可选角色 **UIDesigner**，产出物是仓库产品面里的真实文件
  （HTML/CSS/资源、deck 页面），不是一段"建议"。
- G-B 该角色**只在前端/网页/PPT 类交付面上可用**，由**测量**决定适用性，
  不由模型自述、也不由提示词里的形容词决定。
- G-C Claude Code **不能直接调用 OpenDesign**：唯一出站仍是 CLIENT
  （`<gateway-client>`），CC 壳内看不见 OpenDesign 树。
- G-D **不改 openjiuwen 源码，不改 open-design 源码**。openjiuwen 侧的
  全部改动是 `config/config.yaml` 与 workspace 技能目录；open-design 侧
  只读引用。
- G-E **不打入代码包**：ai-dlc 仓库里不出现任何 open-design 内容，只出现
  一个 pin（tag + sha）和一个指路技能。部署时从 GitHub 拉。
- G-F 设计结论进签名记录，`deliver` 读记录，缺记录报 `design_unverified`。

**非目标**

- 不承诺 PPTX / PDF / MP4 **导出**保真。上游导出走 `od` daemon
  （Node 24 + pnpm 10.33.2 或 Docker :7456），P1 不引入；见 §10 P4。
- 不引入任何成本门、token 上限、耗时告警（landing L1 的禁令继续有效）。
- 不做"设计好不好看"的自动打分。判据只到**可核对的事实**为止：
  用了哪套模板、写了哪些文件、资源解不解析、页面渲不渲染。
- 不改 `review` 轮的 axes 机制，UIDesigner 不是第四个 reviewer——它写文件，
  reviewer 不写文件。

---

## 3. 不变式（验收逐条判定）

- **I1** `grep -rE "\bod\b|open-design"` 在 `bin/` 下匹配不到任何
  `subprocess` / argv 参数；ai-dlc 对 OpenDesign 零进程调用。
- **I2** CC 壳（`aidlc-shell`）内 `/opt/open-design` 不可读；PATH 上若存在
  `od` 则不可执行。掩码缺失时壳**拒绝启动**，不静默降级。
- **I3** 角色对 `/opt/open-design` 只读（root:root 0555）；上游树被改动即
  在下一次 preflight 被 sha 核对判出。
- **I4** workspace 里新增的技能条目**只有一个**（`ui-designer`），139 个上游
  技能不进 `skills_state.json`、不进 workspace。
- **I5** `report.py deliver` 的设计结论四态：`design_applied` /
  `design_declined` / `design_unverified` / `design_not_applicable`，
  `design_unverified` **不得**折成失败、**不得**触发自动重跑。
- **I6** 适用性判定来自产品面文件测量，`plan.py design` 对不适用的交付面
  **拒绝派发**（exit 24），不留"反正跑一下也不亏"的口子。

---

## 4. 实测约束（2026-08-31 在 217 上测的，决定了方案边界）

**E1 — 上游是文件，不是服务。** `skills/<name>/SKILL.md` 是带 frontmatter
的 markdown（`name` / `description` / `category` / `od.mode` / `od.preview` /
`example_prompt`）加 side files（`example.html` 等）。
`skills/AGENTS.md` 明说：daemon 只是把这个目录"列出来"，
"lazy scanner picks the entry up on the next `/api/skills` request — no
rebuild required"。**读目录就能用，不需要 daemon。**

**E2 — 但导出需要 daemon。** `.claude-plugin/marketplace.json` 里只有一个
插件，就是 MCP server，描述写明 "Requires `od` on PATH"。
`QUICKSTART.md` 的两条路径都重：Node `~24` + pnpm `10.33.2`，或 Docker
compose 起在 `:7456` 并需要 `OD_API_TOKEN`。**HTML/PDF/PPTX/MP4 导出属于
daemon 能力，P1 拿不到。**

**E3 — 仓库 1.8 GB。** `repos/nexu-io/open-design` → `size: 1882056` KB。
217 的 `/` 只剩 16 G（40 G 用了 22 G，59%）。**必须 sparse checkout**：
`--filter=blob:none` + `sparse-checkout set skills design-templates
design-systems`，实测占用写进验收，不接受"clone 完再说"。

**E4 — `skill_mode: all` 是全局的。** `config.yaml` 的
`react.skill_mode: all`，`modes.code.tools` 含 `skill_toolkit` /
`skill_retrieval`；`openjiuwen chat` 的参数表里**没有 `--skill` 之类的
按会话过滤开关**（只有 `--mode` / `--session` / `--cwd` / `--project-dir` /
`--trusted-dir` / `--name` / `--dotenv`）。
**结论：链进 workspace 的技能对所有派发可见。** 这一条直接否掉"把上游 139
个技能链进 workspace"的方案，见 §5。

**E5 — openjiuwen 侧的配置面是够的，且当前是空的。**
`mcp.servers: []`（存在但空）；`rules:` 只有一条 `allow_openspec`
（pattern `openspec *`，tools `bash` + `mcp_exec_command`）；
`permissions.external_directory` 是一张显式 allow 表；
workspace 技能在 `<gateway-home>/agent/workspace/skills/` +
`skills_state.json`。**全部是配置，改它不算改代码。**

**E6 — `authoring_skill_state()` 是现成的先例。** `plan.py:1099` 检查
`SKILL.md` 在位 + 在 `skills_state.json` 注册，不在位就带 remedy 硬失败，
**从不自动安装**。UIDesigner 照抄这个契约。

**E7 — `aidlc-shell` 已有算子扩展位。** `AI_DLC_INACCESSIBLE`（冒号分隔）
可以把额外路径加进掩码，且掩码构建器在"PATH 上的 openspec 没进掩码"时
**拒绝运行**。把 `od` 与 clone 路径纳入同一条拒绝规则即可，无需新机制。

**E8 — 上游技能自带反占位约束。** 例如
`skills/deck-swiss-international/SKILL.md` 的 `example_prompt` 写死
"use real content and data, and avoid lorem ipsum or placeholder images"，
主题色 hex 也写死"不许改"。**这给了可核对的判据**：产出的页面里出现
lorem ipsum 或解不出的占位图，就是没照模板做——不需要审美判断。

---

## 5. 目标架构

```
┌─ CC 运行壳 aidlc-shell ────────────────────────────────────────────┐
│  Claude Code：读代码、写代码、跑测试、做 git                        │
│  看不见：/opt/open-design、PATH 上的 od                             │
└──────────────────────────── bin/plan.py ───────────────────────────┘
                         │  唯一出站：CLIENT（openjiuwen）
                         ▼
     openjiuwen Gateway（信任根，配置层改动，源码只读）
       ├─ author / validate / graph / archive 派发        （已有）
       └─ design 派发（新增 N1）
             会话里唯一新增的技能是 ui-designer（一个 SKILL.md）
             它把角色指向只读的上游目录：
                 /opt/open-design/skills            139 个功能技能
                 /opt/open-design/design-templates  115 套渲染模板
                 /opt/open-design/design-systems    154 套设计系统
                         │
                         ▼
     产品面文件写进仓库（write boundary = 本任务的前端面）
                         │
     /var/lib/aidlc/records/<change>/design-<seq>.json  （HMAC 签名，CC 只读）
```

**为什么是"一个指路技能"而不是"链 139 个技能"。** E4 说清楚了：workspace
技能是全局可见的。链 139 个 = 每一次 author/validate/implement 派发都要在
上下文里背 139 条 description，且模型可能在一个后端 change 里去挑配色。
一个 `ui-designer` 技能只增加**一条** description，它的 body 告诉角色
"目录在哪、怎么挑、挑完读哪个文件"——这正是 `openspec-author` 对
openspec CLI 做的事（E6）：**技能是指路牌，不是内容副本**。
副产品是 G-E 自动成立：ai-dlc 仓库里只有指路牌，没有一行上游内容。

**判据可信性落在哪里。** 与 openspec 收容同构，取自帧里 `tool_result` 的
原文而非模型的结论句：

1. **用了哪套模板** — 帧里必须有对 `/opt/open-design/**` 下某个
   `SKILL.md` 的读取，记录里存该路径与其 sha256；零读取 = 角色没用上游，
   判 `design_unverified`。
2. **写了哪些文件** — 从写入类 `tool_result` 取路径与字节数，**派发后与
   文件系统逐条核对**（N2 已有的做法），对不上判 tampering。
3. **资源解不解析** — 产出 HTML 里引用的每个本地资源必须存在；远程资源
   必须可达或不存在。这条抓的是 E8 说的占位图。
4. **页面渲不渲染** — 起本地静态服务取回，HTTP 200 且 DOM 非空。
5. **没有占位文本** — `lorem ipsum` / `placeholder` / `TODO` 在产出面上
   出现即判 RED（E8 的模板约束本身就这么要求）。

以上五条没有一条需要"审美"。**看不看得出好看不在判据里，能不能证明确实
按模板做了才在。**

---

## 6. 适用性：谁决定 UIDesigner 出不出现

不由模型判，不由提示词里有没有"网站"两个字判。由**产品面文件测量**判。

`plan.py design-scope --task <id> --repo <repo>` 复用 `report.py` 的交付面
（`delivery.product_excludes` 原样生效），按扩展名分类：

| 类 | 扩展名 |
|----|--------|
| `web`  | `.html` `.htm` `.css` `.scss` `.jsx` `.tsx` `.vue` `.svelte` `.astro` |
| `deck` | `.pptx`；`slides/` 或 `deck/` 下的 `.html`；带 deck frontmatter 的 `.md` |

`web + deck ≥ 1` → **适用**。否则**不适用**，`plan.py design` 拒绝派发
（exit 24，把测到的面原样列出）。后端 change 买不到美化。

适用 ≠ 必须。四态由此定义，与 `spec_*` 三态同构：

| 状态 | 条件 |
|------|------|
| `design_not_applicable` | 测量判不适用 |
| `design_unverified`     | 适用、无签名记录（**不失败、不自动跑**） |
| `design_declined`       | 适用、有人记录了跳过（`plan.py decide --design skip --why …`），理由原样承载 |
| `design_applied`        | 适用、有签名记录且 §5 五条判据全过 |

---

## 7. 新增

- **N1 design 派发** `plan.py design --task <id> --repo <repo>
  [--surface web|deck] [--system <name>] [--template <name>]`：
  开独立会话（独立 session、独立帧文件、独立 boundary baseline，与
  artifact 角色完全同构），write boundary = §6 测出的前端面，
  从帧提取 §5 的五条事实，写签名记录。
- **N2 `ui-designer` 技能**（ai-dlc 作者，随 `supervisor/skills/` 发布，
  install.sh 装进 gateway workspace，与 `openspec-author` 同路径同做法）。
  body 只讲三件事：目录在哪、怎么按 `od.mode` / `category` / `scenario`
  frontmatter 挑一个、挑定后必须完整读那个 `SKILL.md` 再动手。
  **不复制上游任何正文。**
- **N3 pin 与校验** `/opt/open-design/.aidlc-pin.json`：
  `{tag, sha, sparse_paths, installed_at, size_bytes, tree_sha256}`。
  preflight 核对 sha 与 `tree_sha256`；对不上 exit 26 并给 remedy。
- **N4 `design_skill_state()`** 照抄 `authoring_skill_state()`
  （plan.py:1099）：验 `SKILL.md` 在位 + 在 `skills_state.json` 注册；
  不在位 exit 25 带 remedy，**从不自动安装、从不自动改 openjiuwen 配置**。
- **N5 壳掩码扩展** `aidlc-shell` 的掩码集合加入 `/opt/open-design` 与
  PATH 上的 `od`，纳入"没掩到就拒绝启动"的同一条规则（E7）。
- **N6 部署脚本** `scripts/install-opendesign.sh`（幂等）：
  见 §9。

---

## 8. 数据契约

- 记录路径 `/var/lib/aidlc/records/<change>/design-<seq>.json`，
  HMAC-SHA256，密钥沿用 `/etc/aidlc/verdict.key`。
- 字段：
  ```json
  {"verb":"design","change":"…","task":"…","surface":"web",
   "template":{"path":"/opt/open-design/design-templates/…/SKILL.md",
               "sha256":"…"},
   "design_system":"…|null",
   "files":[{"path":"…","bytes":1234,"sha256":"…"}],
   "assets":{"local_missing":[],"remote_unreachable":[]},
   "render":{"status":200,"dom_nodes":812},
   "placeholders":[],
   "session":"…","ts":"…","hmac":"…"}
  ```
- 新增退出码：`24` 交付面不适用；`25` `ui-designer` 未安装/未注册；
  `26` OpenDesign pin 缺失或 sha 不符。
- 失败一律硬失败并原文承载，沿用现有约定。
  **降级即静默中断**（`ccdr-degradation-kills-loop` 的教训）。

---

## 9. 部署（不打入代码包）

一次性，`scripts/install-opendesign.sh`，幂等，全部在 ai-dlc 之外落地：

```bash
# 1. 稀疏拉取（E3：全量 1.8 GB，只要三个目录）
git clone --filter=blob:none --sparse --depth 1 \
    --branch open-design-v0.21.1 \
    https://github.com/nexu-io/open-design /opt/open-design
git -C /opt/open-design sparse-checkout set \
    skills design-templates design-systems

# 2. 只读给角色，写权限一律不给（I3）
chown -R root:root /opt/open-design
find /opt/open-design -type d -exec chmod 0555 {} +
find /opt/open-design -type f -exec chmod 0444 {} +

# 3. 记 pin（N3）
scripts/install-opendesign.sh --write-pin

# 4. openjiuwen 侧：只动配置，先备份（config.yaml 是手改过的，
#    任何"重新生成"都会 clobber——litellm 那边已经付过这个代价）
cp ~/.jiuwenswarm/config/config.yaml \
   ~/.jiuwenswarm/config/config.yaml.bak.$(date +%s)
#    加一行 allow：permissions.external_directory["/opt/open-design"]: allow
#    改完必须重新读回 config.yaml 断言该键在位，不接受"写过了"

# 5. 装指路技能（与 openspec-author 同做法）
install -D supervisor/skills/ui-designer/SKILL.md \
    ~/.jiuwenswarm/agent/workspace/skills/ui-designer/SKILL.md
#    并在 skills_state.json 的 installed_plugins 里登记 ui-designer
```

`git` 里 ai-dlc 只多出：`supervisor/skills/ui-designer/SKILL.md`、
`scripts/install-opendesign.sh`、`docs/` 本文、`bin/` 的胶水与测试。
**`/opt/open-design` 不进任何 ai-dlc 的提交、打包或镜像。**

升级 = 改 pin 里的 tag 重跑脚本；上游被本地改动过则 `tree_sha256` 对不上，
先报 exit 26 再谈升级。

---

## 10. 反向门（每条标注今天判什么，不装红）

| ID | 尝试 | 期望 | 今天 |
|----|------|------|------|
| D1 | `bin/` 里 grep `od` / `open-design` 进程调用 | 0 处 | **GREEN（回归门，不是红先门）**——今天本来就没有，它防的是以后被加进来 |
| D2 | CC 壳内读 `/opt/open-design` | Permission denied | 装完前**空转**；正向对照：壳外可读、壳内不可读，两侧同一次测量 |
| D3 | CC 壳内 `od --version`（若 PATH 上有） | 127 / EACCES | 同 D2 |
| D4 | 角色写 `/opt/open-design/**` | Permission denied | RED（目录不存在→装完立刻测） |
| D5 | 后端 change 上 `plan.py design` | exit 24，列出测到的面 | RED |
| D6 | 前端 change 有产出、无签名记录 → `deliver` | `design_unverified` | RED（今天连字段都没有） |
| D7 | 篡改 `design-*.json` | HMAC 不符 → `design_unverified` | RED |
| D8 | 帧里零上游读取，角色声称"已美化" | `design_unverified` | RED——**这条是本 PRD 的核心判别力** |
| D9 | 产出页含 `lorem ipsum` / 解不出的本地图 | RED | RED |
| D10 | `ui-designer` 未注册时 `plan.py design` | exit 25 + remedy，**不自动装** | RED |
| D11 | **正向控制**：角色读模板 → 写文件 → 页面 200 → 资源全解析 | 全 GREEN | 未测 |
| D12 | **判别力**：拿已交付的 `country-b-tourism` 重跑 deliver | 判 `design_unverified` | 今天判"已交付"，即新门对现状**有**区分 |
| D13 | workspace 技能条目数 | 装前 +1，且 `skills_state.json` 里只多 `ui-designer` | 可测 |

D11 与 D12 缺一不可：D11 防"把功能关死了当成关住了"，D12 防新门对现状
无差别放行。D2–D4 必须在**真实的 `aidlc-shell` 里**跑，不能用夹具模拟
（`gate-blindspots-seam-determinism-state` 的第三种盲区：反向用例用全新实例）。

---

## 11. 分期

| 期 | 内容 | 完成判据 |
|----|------|----------|
| P0 | 探针：sparse clone 实测体积；壳内外可见性两侧对照；workspace 加一个技能后对**非设计派发**的上下文影响实测 | 三个数字进记录；若 P0 测出 E4 之外的泄漏，方案回到 §5 讨论 |
| P1 | N3/N6 部署 + N2 指路技能 + N4 状态校验；`design-scope` 测量 | D4/D5/D10/D13 GREEN |
| P2 | N1 design 派发 + 签名记录 + `deliver` 四态 | D6/D7/D8/D11 GREEN |
| P3 | N5 壳掩码 + 反向门入 `tests/collapse/` | D2/D3 GREEN；D12 GREEN |
| P4 | 可选：`od` daemon（Docker :7456 或 Node 24 + pnpm 10.33.2），换取 PDF/PPTX/MP4 导出；openjiuwen 侧加 `mcp.servers` 一项 + `rules` 一条 `allow_od` | 导出产物可打开、非零、页数对得上；**未达成则 P4 不合入，P1–P3 独立可用** |

P1+P2 让"用了什么、写了什么"可核对；P3 让"CC 拿不到"成真；
P4 才让"导得出 PPTX"成真。**P4 之前不要在任何地方写"支持 PPT 导出"。**

---

## 12. 风险与残余

- **R1 CC 自己去 clone（旁路，与收容 PRD 的 R1 同形）。** open-design 是
  公开仓库，壳内出网就能拿回副本。消化方式同 openspec：它拿到的副本产不出
  被承认的记录（I5/D8），`deliver` 照样报 `design_unverified`。
  **代价是必须承认"看不见"是尽力而为，不能在验收里写成已强制。**
- **R2 模型凭记忆仿模板。** 上游模板风格是公开的，藏不住书写。D8 挡的是
  "没读就说读了"，挡不住"读了别处仿得像"。可接受：判据只声称"确实读了
  这个文件并写了这些文件"，不声称"这是唯一可能的来源"。
- **R3 上游漂移。** 139/115/154 三个目录随上游演进，pin 到 tag 可控，但
  升级时技能 id 可能消失，导致历史记录里的 `template.path` 失效。
  记录已存 sha256，失效可判、可解释，不追求可复现渲染。
- **R4 `skill_mode: all` 的残余暴露。** 即便只加一条 description，它对所有
  派发仍然可见。P0 要测它是否影响非设计派发的行为；若影响可观测，
  升级方案是 `openjiuwen chat --name/--dotenv` 的实例隔离（仍是配置，
  不改源码），列为 P5。
- **R5 成本。** 每个前端 change 多一次派发。设计类会话通常长
  （any-directory 那次 read-in-place 实测 792.7 s）。按 landing L1，
  **不设上限、不设告警、不报预算**，只在记录里存 elapsed。
- **R6 磁盘。** 217 只剩 16 G。sparse checkout 的实测体积是 P0 的门槛数字，
  超出预期就缩 `sparse-checkout` 到 `design-templates` + `design-systems`。

---

## 13. 回滚

`git reset --hard v0.13.0-pre-uidesigner` 恢复 ai-dlc；
`rm -rf /opt/open-design`；
`~/.jiuwenswarm/config/config.yaml` 从 `.bak.<ts>` 还原；
删 `~/.jiuwenswarm/agent/workspace/skills/ui-designer/` 并从
`skills_state.json` 的 `installed_plugins` 摘掉该条。
记录目录保留不删，作为本轮的证据。
openjiuwen 与 open-design 两边源码全程未动，回滚不涉及它们。
