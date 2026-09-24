# PRD · 安装器整备（install-targets）

> 让安装器知道自己在往哪装、装了什么、还在不在——
> 三件今天一件都做不到。

- 目标仓库：`<repo-path>`
- 相关：`docs/prd-uidesigner-opendesign.md`（workspace 线的来源）、`scripts/install-opendesign.sh`（读回断言的现成写法）
- 测量日期：2026-09-01 · <host-ip>
- 回滚锚点：开工前打 `v0.18.0-pre-installtargets`（**先打 tag 再动手**）

---

## 01 问题

`install.sh` 是按「`supervisor/skills/` 里有什么就往一个地方倒什么」写的。
这个形状在只有一个客户端、只有一类 skill 的时候是对的。
今天两个前提都不成立了，于是它同时装错了地方、装错了东西、还查不出来。

### 一 · 装到哪取决于当前目录

`targets/claude.json` 写的是相对路径：

```json
{ "name": "claude-code", "skills_dir": ".claude/skills", … }
```

`install_skills_to_target()`（`install.sh:449`）拿它直接当路径用。
从仓库根跑落在 `./.claude/skills`；从别处跑就落在别处。
**现场铁证**：仓库里躺着一个 `.claude/.claude/skills/`（08-30 建，
08-31 15:31 还被写过），就是某次 cwd 落在 `.claude/` 时跑出来的。
里面还有 6 个 `openspec-*` 陈旧 skill——`supervisor/skills/` 里早就没有它们了。

### 二 · 把只该给角色的 skill 装给了编排壳

`for skill_dir in "${SUPERVISOR_DIR}"/*/` 是无条件循环。
**今天 08:41 有人跑了一次 `install.sh`**，`.claude/skills/` 里于是有了三个，
包括 `ui-designer`。

但 `ui-designer` 不属于 Claude Code 侧：

- 按 uidesigner PRD 的 N2/N4，它属于 **gateway workspace**
  （`~/.jiuwenswarm/agent/workspace/skills/` + `skills_state.json` 登记）；
- CC 壳被 `aidlc-shell` 的 N5 掩码挡着，**根本读不到 `/opt/open-design`**。
  给 CC 一块指向它看不见的树的指路牌，是纯噪音；
- 而 install.sh **既不装 workspace、也不登记 `skills_state.json`**——
  真正该装的那一侧它一个字都没碰。

### 三 · 装完之后没人知道装的还在不在

doctor 的 skill 检查是这样的（`install.sh:161`）：

```bash
for skill in ai-dlc ai-dlc-doctor; do
  [[ -f "${SUPERVISOR_DIR}/${skill}/SKILL.md" ]] && ok "skill source: ${skill}"
```

**只断言源文件存在**——漏了 `ui-designer`，更要命的是它**从不比对已安装的副本**。
今天实测：`<cc-glm-config>/skills/ai-dlc-doctor/SKILL.md` 是 `e957ca7e`（624 B），
源是 `6f8bf7af`（729 B）——**已经分叉了，doctor 全绿**。

### 四 · CC 真正读的那个目录，脚本压根不认识

| config dir | skills | 谁在用 |
|---|---|---|
| `<cc-config>` | 无 | `claude`（订阅直连） |
| `<cc-glm-config>` | `ai-dlc`、`ai-dlc-doctor`、`feature-development` | `claude-glm`（`bin/claude-glm:22`，`export CLAUDE_CONFIG_DIR` 在 :110） |
| `<cc-maas-config>` | **空**（两个孤儿今天已删） | `claude-maas`（`:29` / `:229`），`openjiuwen` 的默认客户端（`delegate:78`） |
| `<cc-config>-hybrid` | 无，无 settings | — |

`.claude-glm` 里那三份**是手放的**，没有任何脚本在维护它们与源的一致性；
`targets/` 里也没有任何一条认识这个目录。install.sh 只会生成项目级 `.claude/skills/`。

**结论**：安装器的模型是「一个目标、一类 skill、一次拷贝」，
现实是「N 个客户端、两类去向、需要长期保持一致」。差距不是 bug，是形状不对。

---

## 02 目标与非目标

### 目标

| ID | 目标 |
|---|---|
| **G-A** | **任意客户端可装**：`claude-glm`、`claude-maas` 是一等目标；任何 `CLAUDE_CONFIG_DIR` 都能作为目标，**不需要事先造一个 JSON** |
| **G-B** | **去向由归属决定**：CC 侧的 skill 与 workspace 侧的 skill 分开，新增 skill 不必改安装器 |
| **G-C** | **workspace 线完整**：装文件 + 登记 `skills_state.json` + 读回断言，一步不缺 |
| **G-D** | **装了什么可核对**：安装即记账；doctor 按账比对 sha256，分叉即红 |
| **G-E** | **与 cwd 无关**：路径绝对化，`.claude/.claude/` 这种产物不可能再出现 |
| **G-F** | **只动自己装的**：安装器绝不删它没装过的东西 |

### 非目标

- 不改任何一个 skill 的内容。本轮只搬运与记账。
- 不动客户端包装器（`claude-glm` / `claude-maas` / `openjiuwen`）——它们工作正常，
  安装器**读**它们的 `CLAUDE_CONFIG_DIR` 约定，不改写它们。
- 不引入包管理器、版本号、marketplace。skill 仍是目录加文件。
- 不做跨机器分发。本轮只解决单机多客户端。
- 不改 `/opt/open-design` 的部署方式（`install-opendesign.sh` 保持独立，只是被纳入统一入口与 doctor）。

---

## 03 不变式

| ID | 不变式 |
|---|---|
| **K1** | 安装路径**全部绝对**，结果与调用时的 cwd 无关。 |
| **K2** | 安装器**只删它自己装过的**（以 manifest 为准）。`feature-development` 这类不由 ai-dlc 提供的 skill，任何路径下都不得被移除。 |
| **K3** | skill 的去向由**目录归属**决定，不由名单决定。`workspace/` 类**永不**进任何 CC 客户端的 skills 目录。 |
| **K4** | 每次安装写 manifest：装到哪、sha256、时间、来源。**没有 manifest 的安装视为未完成。** |
| **K5** | doctor 按 manifest 逐条比对 sha256；任一条不一致即**失败**，并指名是哪个目标的哪个 skill。 |
| **K6** | 一切写入**读回才算数**：文件写完读回比 sha，注册写完读回数条目。「写过了」不算。 |
| **K7** | 未知目标、不存在或不可写的 config dir → **拒绝并说明**，不静默降级、不自动创建到一个猜出来的位置。 |
| **K8** | 幂等：同样的输入连跑两次，第二次不产生任何差异（manifest 的时间戳除外）。 |

---

## 04 实测约束

**E1 · 客户端选择是 `CLAUDE_CONFIG_DIR`，约定已经存在。**
`claude-glm:22` `claude_config_dir="$HOME/.claude-glm"`、`:110` `export CLAUDE_CONFIG_DIR`；
`claude-maas:29` / `:229` 同构。**安装器不需要发明机制，只需要读同一个约定**：
一个目标 ≡ 一个 config dir，其 skills 目录 ≡ `<config_dir>/skills`。

**E2 · 目标目录里有不属于 ai-dlc 的东西。**
`<cc-glm-config>/skills/feature-development` 是 openjiuwen 的运行态 swarm-skill，
不由本仓库提供。**任何「镜像同步」式实现都会误删它**——K2 就是为它写的。

**E3 · 分叉今天就在。**
`.claude-glm/skills/ai-dlc-doctor` = `e957ca7e`（624 B）vs 源 `6f8bf7af`（729 B）。
`ai-dlc` 与 `ui-designer` 目前一致（`19b5c3ba` / `7808171193`）。
**K5 上线当天就会红一条**，这正是它有鉴别力的证据。

**E4 · 相对路径的产物已经在仓库里。**
`.claude/.claude/skills/` 含 `ai-dlc`、`ai-dlc-doctor` 与 6 个 `openspec-*`。
`.gitignore` 有 `.claude/`，所以它没进 git——**也因此从来没人看见它**。

**E5 · 登记的形状已经定好了。**
`skills_state.json` 的 `installed_plugins` 条目：

```json
{"name": "ui-designer", "marketplace": "builtin", "version": "", "commit": "",
 "source": "ai-dlc supervisor/skills/ui-designer",
 "installed_at": "2026-08-31T21:25:45.572803+00:00"}
```

`source` 字段已经在承担「谁装的」这个职责，manifest 应与之一致，不另造一套词汇。

**E6 · 读回断言的写法已经有现成的。**
`scripts/install-opendesign.sh:144-146`（config 键读回）与 `:171-172`
（注册条目数读回，`!= 1` 即 die）。**照抄，不要重写第二套。**

**E7 · `PY` 可用。**
`python3.12` → uv 的 3.12.14，符号链接在位。
（注意 `/usr/bin/python3` 是 3.6，跑不了 `plan.py`——安装器已经用对了。）

**E8 · `.claude-maas/skills/` 今天清空过。**
两个孤儿（`ai-dlc-tdd` / `ai-dlc-audit`，一个已被移除的 vendor+overlay 子系统的残留）
已删，备份在 `<cc-maas-config>/skills-removed-20260901-084936.tar.gz`。
**这个目录现在是干净的空目标**，正好当 B 组反向门的白纸。

---

## 05 目标架构

### 一个目标 = 一个 config dir

```
targets/
  claude.json        config_dir: <cc-config>
  claude-glm.json    config_dir: <cc-glm-config>
  claude-maas.json   config_dir: <cc-maas-config>
```

目标文件的形状（`skills_dir` 不再手写，由 `config_dir` 推导）：

```json
{
  "name": "claude-glm",
  "display_name": "Claude Code (GLM direct)",
  "config_dir": "<cc-glm-config>",
  "launcher": "<local-dir>/bin/claude-glm",
  "role": "执行壳 — openjiuwen/workflow 的下游"
}
```

而**任意客户端不需要 JSON**：

```bash
./install.sh --target-dir <cc-config>-hybrid     # 任意 CLAUDE_CONFIG_DIR
./install.sh --target claude-glm                   # 注册表里的
./install.sh --all-targets                         # targets/ 下全部
```

`--target-dir` 是 G-A 的主路径：**新客户端不需要先在仓库里登记**，
给一个目录就能装；想长期维护再补一个 JSON 进 `targets/`。

### 两条去向，由目录归属决定

```
supervisor/skills/
  claude/                 → 装进每个 CC 目标的 <config_dir>/skills/
    ai-dlc/
    ai-dlc-doctor/
  workspace/              → 装进 gateway workspace + 登记 skills_state.json
    ui-designer/
```

**K3 的机器形式**：`workspace/` 下的东西没有任何代码路径能把它送进 CC 目标。
新增一个 skill 时，作者放进哪个子目录就决定了它去哪——安装器不需要认识它的名字。

### 三条线，一个入口

```
./install.sh                     线1 CC 目标（默认 claude）+ 线2 workspace + openspec
./install.sh --all-targets       线1 扩展到 targets/ 下全部
./install.sh --opendesign        线3：转调 scripts/install-opendesign.sh（宿主步骤）
./install.sh --doctor            三条线各自的状态 + K5 一致性
./install.sh --uninstall --target <n>   按 manifest 精确移除
```

线 3 单独留一个开关，因为它要 root、要拉 138 M、要改 systemd unit——
不该混进默认路径。

### 记账

`.ai-dlc/install-manifest.json`（不进 git，`.gitignore` 已忽略 `.ai-dlc/tasks/`，
需为 manifest 另加一行）：

```json
{
  "version": 1,
  "installs": [
    {"target": "claude-glm", "kind": "claude",
     "config_dir": "<cc-glm-config>",
     "skill": "ai-dlc",
     "path": "<cc-glm-config>/skills/ai-dlc/SKILL.md",
     "sha256": "19b5c3ba…", "source": "supervisor/skills/claude/ai-dlc",
     "installed_at": "2026-09-01T09:10:00Z"},
    {"target": "workspace", "kind": "workspace",
     "config_dir": "<gateway-home>/agent/workspace",
     "skill": "ui-designer",
     "path": "<gateway-home>/agent/workspace/skills/ui-designer/SKILL.md",
     "sha256": "78081711…", "registered": true,
     "source": "supervisor/skills/workspace/ui-designer",
     "installed_at": "2026-09-01T09:10:00Z"}
  ]
}
```

manifest 同时是 **K2 的执行依据**（只删记过的）与 **K5 的比对基准**。

---

## 06 新增

| ID | 内容 |
|---|---|
| **N1** | **目标注册表泛化**：`targets/*.json` 增加 `config_dir`（绝对）与 `launcher`；新增 `claude-glm.json`、`claude-maas.json`。`skills_dir` 由 `config_dir` 推导，**不再手写、不再相对**（K1）。 |
| **N2** | **`--target-dir <path>`**：任意 `CLAUDE_CONFIG_DIR` 直接作为目标，无需 JSON（G-A）。目录不存在或不可写 → 拒绝（K7）。 |
| **N3** | **`--all-targets`**：对 `targets/` 下每个 JSON 各装一遍，逐个报结果，一个失败不静默吞掉其余。 |
| **N4** | **目录归属**：`supervisor/skills/` 重排为 `claude/` 与 `workspace/` 两个子目录；`install_skills_to_target()` 只遍历 `claude/`（K3）。 |
| **N5** | **workspace 线并入**：装 `workspace/` 下的 skill 到 gateway workspace，并按 E5 的形状登记 `skills_state.json`，写完**读回断言**（E6 的写法，K6）。 |
| **N6** | **manifest**：`.ai-dlc/install-manifest.json`，每次安装重写自己那部分（K4）。 |
| **N7** | **doctor 升级**：从「查源存在」改为**三段**——① 源齐全（含 `workspace/`）；② manifest 每条的 sha256 与现场一致（K5）；③ workspace 注册条目数为 1、`/opt/open-design` pin 校验通过。 |
| **N8** | **`--uninstall --target <n>`**：按 manifest 精确移除，**只删记过的路径**（K2），并从 `skills_state.json` 摘掉对应登记。 |
| **N9** | **清理**：删 `.claude/.claude/`（E4 的陈旧产物）；`.gitignore` 加 `.ai-dlc/install-manifest.json`。 |
| **N10** | **文案同步**：`install.sh` 文件头与结尾的 `skills → …` 一行按新布局重写（今天漏 `ui-designer`，且把 workspace 侧说成 CC skill）。 |

---

## 07 反向门

每条标注今天判什么，**不装红**。

| ID | 尝试 | 期望 | 今天 |
|---|---|---|---|
| **B1** | 从 `/tmp` 跑 `./install.sh --target claude-glm` | 装进 `<cc-glm-config>/skills/`，**不在 `/tmp` 下产生任何目录** | **RED**（今天相对路径，会在 cwd 下造 `.claude/skills`） |
| **B2** | `--target-dir <cc-config>-hybrid` | 装进该目录的 `skills/`，manifest 记一条 | **RED**（今天没有这个开关） |
| **B3** | `--target-dir /nonexistent/xyz` | **拒绝**并说明，不创建、不降级 | **RED** |
| **B4** | 任意目标安装后检查其 `skills/` | **没有 `ui-designer`** | **RED** — **K3 的核心判别力**（今天 08:41 那次就装进去了） |
| **B5** | 安装后检查 gateway workspace | `ui-designer` 在位**且** `skills_state.json` 里恰好 1 条登记 | **RED**（今天 install.sh 完全不碰这一侧） |
| **B6** | 装完把 `.claude-glm/skills/ai-dlc/SKILL.md` 改一个字节，跑 `--doctor` | **失败**，指名 `claude-glm` / `ai-dlc` | **RED** — K5，今天 doctor 全绿 |
| **B7** | **判别力现况**：直接对现状跑 `--doctor` | `.claude-glm/ai-dlc-doctor` 判红（`e957ca7e` ≠ `6f8bf7af`） | **RED**，且**改完当天就该红**（E3）——绿了说明门没接上 |
| **B8** | `--uninstall --target claude-glm` | `ai-dlc`/`ai-dlc-doctor` 移除，**`feature-development` 原样保留** | **RED** — **K2 的核心判别力** |
| **B9** | 连跑两次 `./install.sh --all-targets` | 第二次除 manifest 时间戳外零差异 | **RED**（K8 今天无从谈起） |
| **B10** | `skills_state.json` 登记写入后被外部改坏 | 读回断言失败并 die，**不报成功** | **RED**（K6） |
| **B11** | 在 `supervisor/skills/workspace/` 下新增一个假 skill | 它进 workspace、**不进任何 CC 目标**，且安装器**没有被改过** | **RED** — 证明 G-B（归属而非名单） |
| **B12** | `--all-targets` 中一个目标不可写 | 其余目标照常装完，失败项被明确报出 | **RED** |
| **B13** | 装完检查 `.claude/.claude/` | 不存在 | **RED**（今天存在，含 6 个陈旧 `openspec-*`） |

**B4 与 B11 缺一不可**：B4 判「今天装错的那一个有没有被挡住」，
B11 判「以后新增的会不会重蹈覆辙」。
**B7 与 B6 缺一不可**：B6 是构造出来的红，B7 是**现状本来就该红**——
一道对现状无差别的一致性门等于没有。
**B8 是本轮最危险的一条**：`--uninstall` 写错就会删掉 `feature-development`。

---

## 08 分期

| 期 | 内容 | 门 |
|---|---|---|
| **Q0 · 探针** | 已完成：四个 config dir 与包装器约定实测（E1）、`feature-development` 的存在（E2）、现存分叉（E3）、`.claude/.claude/` 与 08:41 那次误装（E4/§01 二） | 四个事实进记录 |
| **Q1 · 路径与归属** | N1 + N2 + N4 + N9：绝对路径、`--target-dir`、两个子目录、清陈旧 | B1 B2 B3 **B4** **B11** B13 |
| **Q2 · 记账与一致性** | N6 + N7：manifest、doctor 三段 | B6 **B7** B9 |
| **Q3 · workspace 线** | N5：装 + 登记 + 读回 | B5 B10 |
| **Q4 · 多目标与卸载** | N3 + N8 + N10：`--all-targets`、`--uninstall`、文案 | **B8** B12 |

Q1 让「装到哪、装什么」变对；Q2 让「装了还在不在」可查；
Q3 补上从来没接过的那一侧；Q4 才谈多目标批量与移除。

**Q2 之前不要跑 `--all-targets`**——没有 manifest 就没有 K2 的依据，
一次批量安装等于在三个目录里留下无法追溯的拷贝。

---

## 09 风险与残余

| ID | 风险 | 消化方式 |
|---|---|---|
| **R1** | **`--uninstall` 误删他人资产**（`feature-development` 是活的） | K2 写死：只删 manifest 记过的**具体路径**，不按目录名匹配、不做镜像同步。B8 是它的门。**残余**：manifest 丢失后 `--uninstall` 应当拒绝执行，而不是「猜」。 |
| **R2** | **重排 `supervisor/skills/` 会打断现有引用** | `plan.py` 的 `authoring_skill_state()` / `design_skill_state()` 与 `install-opendesign.sh` 都按路径找 skill，重排前必须全量 grep 一遍并同改。列为 Q1 的前置动作，不是可选清理。 |
| **R3** | **K5 上线即红**（E3 的分叉） | 这是**预期行为，不是事故**。修法是重装一次让它们一致，不是放宽门。**不许**为了「让 doctor 变绿」去改比对逻辑。 |
| **R4** | **`--target-dir` 允许任意目录 = 允许装错地方** | K7 只做最小校验（存在、可写、看起来是个 config dir——有 `settings.json` 或 `skills/`）。**残余**：给一个合法但无关的目录，安装器会照装。这是「任意客户端」的必然代价，接受。 |
| **R5** | **manifest 与现实脱节**（有人手改了目标目录） | 这正是 K5 要暴露的，不是要防的。doctor 报出来，人来决定重装还是接受。 |
| **R6** | **`.claude` 与项目级 `.claude/skills` 语义混淆** | 项目级 `.claude/skills/` 是 CC 的合法机制（cwd 在项目时可见），不废除；但它由 `--target claude` 显式产生，**不再是相对路径的副作用**。文档里把两者说清楚。 |
| **R7** | 客户端包装器将来改了 config dir 约定 | 目标 JSON 里存 `launcher` 路径，doctor 可核对 `launcher` 里的 `claude_config_dir` 与 JSON 的 `config_dir` 是否一致。**本轮只存不校**，列为后续。 |

---

## 10 回滚

1. `git reset --hard v0.18.0-pre-installtargets`
2. 各目标目录按 manifest 还原（Q2 之后才有 manifest；Q1 期间靠 git 与手工）
3. `.claude-maas` 的两个孤儿如需恢复：
   `tar -xzf <cc-maas-config>/skills-removed-20260901-084936.tar.gz -C <cc-maas-config>`
4. `/opt/open-design`、gateway unit、openjiuwen `config.yaml` 全程未动

---

## 附注 · 与另一份 PRD 的接缝

`docs/prd-design-autodispatch.md` 的 **A8**（两份 playbook sha 相同）
与本 PRD 的 **K5/B6/B7** 是同一件事的两种写法。
**应当合并到本 PRD 的 doctor 里**——那是运行态检查，
住在 `install.sh --doctor` 比住在 `tests/collapse/` 更对：
测试要有人跑才咬人，doctor 是安装动作的一部分。
autodispatch PRD 的 A8 届时改为「引用本 PRD 的 K5」。

另：那份 PRD 的 E5 记的分叉（仓库 `e6002a99` vs `.claude-glm` `735caedb`）
**已于 09-01 07:54–07:55 被外部同步掉**，两份现在都是 `19b5c3ba`。
E5 的数字需要回写；结论（会分叉、需要门）不变——`ai-dlc-doctor` 那条今天还分着。

---

*`docs/prd-install-targets.md` · 测量日期 2026-09-01 · <host-ip>*
