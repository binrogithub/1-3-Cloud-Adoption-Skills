# PRD — openspec 收容：ai-dlc 的唯一出站是 openjiuwen

状态：待评审 · 目标机器 <host-ip> · 仓库 `<repo-path>`
（master `1e7b57a`）· 现行技能 v0.11 · 决策：**A 方案（spec 树迁出
Claude Code 的工作树）**

回滚锚点：落地前在 master 打 `v0.12.1-openspec-caller-side`。

---

## 1. 问题

今天 openspec 在 **caller 侧**执行——caller 就是 Claude Code 本人。它
自己跑校验、自己读规格、自己写规格树，判据与被判对象同源。这是
`ai-dlc-self-certifying-loop` 记录过的失真形态在规格面上的复现：不是门禁
没鉴别力，是验证依据握在被验证者手里。

实测的 caller 侧触点（2026-08-31 盘点，共 19 处，其中 argv 形态的进程调用 4 处）：

| # | 位置 | 形态 |
|---|------|------|
| 1 | `bin/plan.py:270-289` `openspec()` / `openspec_soft()` | 进程内调用 CLI |
| 2 | `bin/plan.py:324` `cmd_roles` | `openspec status --json --change` |
| 3 | `bin/plan.py:513` preflight | `openspec status --json --change` |
| 4 | `bin/plan.py` `cmd_close` | `openspec archive <id> --yes --json` |
| 5 | `bin/plan.py:3828` `cmd_accept` | `openspec validate <id> --strict`——**接受回路的判据本体** |
| 6 | `bin/report.py:334` | `openspec validate <id> --strict` |
| 7 | `.claude/skills/ai-dlc/SKILL.md` 第 2 步 CHECK | 指示 CC 亲自跑 validate |
| 8 | `bin/plan.py:432-440` 角色 prompt | 「你不要调 validator，acceptor 来判」 |
| 9 | `bin/plan.py:648` `VALIDATOR_RE` | 角色跑了 validate 就判 dispatch 失败 |
| 10-15 | `.claude/skills/openspec-{propose,explore,apply-change,update-change,archive-change,sync-specs}` | 6 个 CC 技能直接调 CLI |
| 16 | `.claude/commands/opsx/*` | 6 个 CC 命令 |
| 17 | `plan.py:528` / `1164-1172` / `1280-1283` | CC 侧构造并镜像 spec 树（preflight、分片暂存、隔离拷贝） |
| 18 | `openspec/` 树在 CC 工作树内 | CC 可读可写 specs / changes / project.md |
| 19 | 任务提示词惯例 | 「Read … `openspec/project.md` first」 |

注意 7 与 8：现行契约是「**caller 判、角色禁**」。本 PRD 把它整个反转成
「**plane 判、caller 禁**」。这不是加一层壳，是判据归属的搬迁。

---

## 2. 目标与非目标

**目标**

- G-A ai-dlc 代码库中不再存在任何 openspec 进程调用；唯一外部可执行依赖
  是 `CLIENT`（`<gateway-client>`）。
- G-B Claude Code 的运行壳内，openspec 不可执行、spec 树不可读。
- G-C Claude Code 不能写 spec 树。
- G-D 规格判据只来自 plane 产出的签名记录，CC 无法伪造。
- G-E 正向能力不退化：角色仍能 author / validate / archive。

**非目标**

- 不修改 openjiuwen 源码（只读引用 `<workspace-root>/reference/jiuwenswarm`）。
- 不引入任何成本门、token 上限或告警（landing L1 的禁令继续有效）。
- 不承诺「隐藏 = 模型不知道 openspec 格式」。openspec 是公开 npm 包，
  知识面封不住；本 PRD 封的是**效果面**，见 §4-E2 与 §11-R1。

---

## 3. 不变式（验收逐条判定）

- **I1** `grep -rE "\bopenspec\b" bin/ .claude/` 只匹配到注释与文档引用，
  匹配不到任何 `subprocess`/`run()` 参数中的 `openspec`。
- **I2** CC 壳内 `openspec` 不可执行（PATH、绝对路径、node 直调三条全断），
  `/var/lib/aidlc/specs/**` 不可读。
- **I3** CC 对 spec 树无写权限（属主 `swarm`，0750）。
- **I4** `report.py deliver` 的 `spec_valid` 只能来自带有效 HMAC 的
  `verdict-*.json`；缺记录或签名不符一律报 `spec_unverified`。
- **I5** 角色派发仍能取到 `openspec instructions`、产出通过 `--strict` 的
  工件、完成 archive。

---

## 4. 实测约束（2026-08-31 在 217 上跑的，决定了方案边界）

**E1 — 命名空间隐藏对 uid 0 也成立。** 瞬时单元里
`NoNewPrivileges=yes` + `CapabilityBoundingSet=` + `InaccessiblePaths=`：

```
uid=0  CapBnd: 0000000000000000
openspec:     command not found
node 直调:    node:internal/modules/cjs/loader:1433
ls 树:        Permission denied
umount 旁路:  umount: must be sucountry-eser to unmount
```

能力位清零后 CC 没有 CAP_SYS_ADMIN，卸不掉遮挡；`NoNewPrivileges` 堵死
提权。**不需要 uid 拆分就能拿到 I2 的路径级部分。**

**E2 — npx 能把 openspec 拿回来。** 同一个壳里
`npx -y @fission-ai/openspec --version` → `rc=0, 1.11.0`；藏掉 `<npm-cache>`
后改 `npm_config_cache=/tmp/xx` 依旧成功。**只要 CC 出网，I2 就是尽力而为，
不是强制。** 这条不阻断本方案，因为 I3/I4 让拿回来的副本无处施力
（见 §11-R1）。

**E3 — 这台机器不能用 systemd 断网。** `/sys/fs/cgroup` 是 tmpfs
（cgroup v1），`IPAddressDeny=any` 不生效——壳内 `curl https://api.anthropic.com`
返回 404（说明连通）。要封出口只能走 uid 拆分 + `iptables -m owner`，列为 P5。

**E4 — CC 出口是一个外部 HTTPS 端点 `<vendor-endpoint>`**（`ANTHROPIC_MODEL=<vendor-model>`），
不是本地代理，所以没有「只放行 127.0.0.1」这种廉价白名单。

**E5 — 当前权限层强制力为零。** CC 以 root 运行且带
`--allow-dangerously-skip-permissions`，`<cc-vendor-config>/settings.json` 是
`Bash(*) / Write(*) / Edit(*) / Read(*)`。任何写在 settings 或 hook 里的
「禁止调用 openspec」都是装饰，不计入本 PRD 的强制手段。

---

## 5. 目标架构

```
┌─ CC 运行壳 aidlc-shell（CapBnd=0，NoNewPrivileges，InaccessiblePaths） ─┐
│  Claude Code：读代码、写代码、跑测试、做 git                            │
│  看得见：plane 投递的行为要求（tasks 条目）、签名裁决记录（只读）        │
│  看不见：openspec 二进制 / node 模块 / spec 树 / instructions / schema   │
└──────────────────────────── bin/plan.py ────────────────────────────────┘
                                   │  唯一出站：CLIENT（openjiuwen）
                                   ▼
     openjiuwen Gateway（信任根，systemd 硬化，源码只读）
       ├─ author 派发   ：写 proposal / specs / design / tasks   （已有）
       ├─ validate 派发 ：规范化命令跑 --strict                  （新增 N1）
       └─ archive 派发  ：archive + 回写仓库 + 提交              （新增 N2）
                                   │
              /var/lib/aidlc/specs/<repo-id>/openspec   (swarm:swarm 0750)
              /var/lib/aidlc/records/<change>/          (swarm:swarm 0755，CC 只读)
                  graph.json · artifact-status.json · verdict-*.json
```

**判据可信性落在哪里。** validate 由 LLM 角色的会话执行，但裁决不取自模型
的自述，而取自事件帧里 `tool_result` 的原文，且要求：

1. 命令是规范化字面量 `/usr/local/bin/openspec validate <id> --strict --json`
   ——绝对路径，无管道、无重定向、无 shell 元字符；
2. 该二进制属主 root、角色对 `/usr/local` 无写权限，**角色无法预先植入同名
   假二进制**（现有 pre-dispatch baseline 与命令审计已能看见任何写入尝试）；
3. plan.py 从帧里读 `rc` 与 stdout，不读模型的结论句。

因此伪造需要 gateway 本身共谋。**gateway 是本设计的唯一信任根**，这一点必须
明写（风险 R3）。

`cmd_accept` 的现行语义保留、来源更换：帧违规（作者自判、破坏基线路径）
仍然先于一切判定；随后的 `--strict` 结论不再由 caller 现场跑出，而是取自
validate 派发的裁决记录，`revision_pending.validator_output` 承载裁决里的
原文。**「作者不得自判」这条约束因此变得可强制**——作者会话与验证会话是
两次独立派发，而不是同一侧的两段代码。

---

## 6. 删除清单

| ID | 删除对象 | 替代物 |
|----|----------|--------|
| D1 | `plan.py:270-289` `openspec()` / `openspec_soft()` | 无——进程内调用 openspec 一律禁止 |
| D2 | `plan.py:324` `cmd_roles` 的 status | 读 `records/<change>/graph.json` |
| D3 | `plan.py:513` preflight 的 status | 同上 |
| D4 | `plan.py` `cmd_close` 的 `openspec archive` | archive 派发（N2） |
| D5 | `report.py:334` 的 `openspec validate --strict` | 读 `verdict-*.json`；无记录 → `spec_unverified` |
| D5b | `plan.py:3828` `cmd_accept` 的 `openspec validate --strict` | 读 validate 派发的裁决；`revision_pending` 的 `validator_output` 改填裁决记录里的原文 |
| D6 | `.claude/skills/openspec-*`（6 个） | 能力移入 gateway workspace skills |
| D7 | `.claude/commands/opsx/*`（6 个） | 删除，不重建 |
| D8 | `SKILL.md` 第 2 步 CHECK 的自跑 validate | 「向 plane 请求裁决，原文承载」 |
| D9 | `plan.py:432-440` 角色 prompt 的「你不要调 validator」 | 反转为 validate 派发的规范化指令 |
| D10 | `plan.py:648` `VALIDATOR_RE` 的失败语义 | 反转：帧里**没有**规范化 validator 调用才失败 |
| D11 | CC 任务提示词/CLAUDE.md 里的 `openspec/project.md` 阅读指示 | plane 投递的行为要求（N7） |
| D12 | `plan.py:528` / `1164-1172` / `1280-1283` 的 spec 树构造与镜像 | 路径基准改为 plane 树；分片暂存与隔离拷贝的 openspec 面由派发在 plane 侧建立，CC 侧不再 mkdir/复制 `openspec/**` |

`report.py:109` 的 `product_excludes` 保留 `openspec/**`：迁树后仓库工作期内
没有该目录，归档回写会重新产生它，交付面测量语义不变。

---

## 7. 新增

- **N1 validate 派发** `plan.py validate --change <id> --repo <repo>`：
  开一个新会话，唯一被允许的工具调用是 §5 的规范化命令；从帧提取
  `rc` / stdout 原文，写签名裁决。
- **N2 archive 派发** `plan.py close` 的尾段改为一次派发：`openspec archive
  <id> --yes --json` → 把 `openspec/specs` 与 `changes/archive/<date>-<id>`
  回写到仓库 → `git add` + `git commit`（gateway 已有 `ReadWritePaths=<workspace-root>`）。
  合入仍由 CC 的 `git merge` 完成，且仍必须先有带理由的人类批准。
- **N3 graph 记录** change 创建时一次性派发产出 `graph.json`（工件清单 +
  依赖），change 生命周期内不再重算——避免每次 `roles`/preflight 都烧一次派发。
- **N4 裁决签名** HMAC-SHA256，密钥 `/etc/aidlc/verdict.key`（0400 swarm）。
  字段：`{verb, argv, rc, stdout, sha256, change, ts, session, hmac}`。
- **N5 CC 运行壳** `aidlc-shell`（systemd 瞬时单元包装 claude 启动）：
  `NoNewPrivileges=yes`、`CapabilityBoundingSet=`、
  `InaccessiblePaths=` 覆盖 openspec 模块目录、`/usr/local/bin/openspec`、
  `/var/lib/aidlc/specs`。
- **N6 spec 树迁移** `openspec/` → `/var/lib/aidlc/specs/<repo-id>/openspec`；
  角色的 write boundary 与 trusted-dir 同步改到新路径。
- **N7 行为要求投递** 角色写完 tasks 后，plane 把可执行条目投递到
  `records/<change>/handoff.md`（CC 只读）。**信息面切割：行为可见，规格工具
  与格式不可见。** 不做这一刀，CC 会凭记忆手写 spec，届时只剩 I3 挡得住。

---

## 8. 数据契约

- 裁决记录路径 `/var/lib/aidlc/records/<change>/verdict-<seq>.json`。
- `report.py deliver` 的结论三态：`spec_valid` / `spec_invalid`（有裁决且 rc≠0）
  / `spec_unverified`（无裁决或签名不符）。**`spec_unverified` 不得被当作
  `spec_invalid` 处理，也不得触发任何自动重跑。**
- 新增退出码：`22` 裁决缺失或签名不符；`23` validate 派发的帧里没有规范化
  validator 调用。
- 失败一律硬失败并原文承载 CLI 输出，沿用现有约定。

---

## 9. 反向门（每条都必须对今天的代码判 RED）

| ID | 尝试 | 期望 | 今天 |
|----|------|------|------|
| G1 | 源码里 grep openspec 进程调用 | 0 处 | RED（4 处 argv 调用 + 3 处树构造） |
| G2 | CC 壳内 `openspec --version` | 127 / EACCES | RED（返回版本号） |
| G3 | `node …/@fission-ai/openspec/bin/openspec.js` | 失败 | RED |
| G4 | CC 读 `/var/lib/aidlc/specs/**` | Permission denied | — |
| G5 | CC 写 spec 树 | Permission denied | RED |
| G6 | CC 手写 change 目录后请求 archive | 派发拒绝（路径/属主不符） | RED |
| G7 | CC 篡改 `verdict-*.json` | HMAC 不符 → `spec_unverified` | RED |
| G8 | 无裁决时 `report.py deliver` | 报 `spec_unverified`，不得自调 validate | RED |
| G9 | **正向控制**：角色 `openspec instructions` / validate / archive | 全部 GREEN | GREEN |
| G10 | **判别力**：今天那次 CC 自跑 validate 的交付记录 | 新门下判 RED | 现为 GREEN |

G9 与 G10 缺一不可：G9 防止「把系统关死了当成关住了」，G10 防止新门对现状
无差别放行。落地为 `tests/collapse/` 下的脚本，G2–G5 必须在真实的
`aidlc-shell` 里跑，不能用夹具模拟。

---

## 10. 分期

| 期 | 内容 | 完成判据 |
|----|------|----------|
| P1 | 删除 D1–D11；`plan.py`/`report.py` 改为读记录 | G1 GREEN；套件仍绿 |
| P2 | N1/N3/N4：validate 派发 + graph 记录 + 签名 | G7/G8 GREEN；G9 GREEN |
| P3 | N6/N2/N7：迁树 + archive 派发 + 行为投递 | G4/G5/G6 GREEN；一次 live 全流程 |
| P4 | N5：`aidlc-shell` + 反向门入套件 | G2/G3 GREEN；G10 GREEN |
| P5 | 可选：uid 拆分 + `iptables -m owner` 出口白名单 | E2 的 npx 通道关闭 |

P1+P2 让 I3/I4 成立（自写自判在结构上不可能）；P3 让「看不见」成真；
P5 才让「拿不到」成真。

---

## 11. 风险与残余

- **R1 npx 旁路（E2 实测成立）。** CC 可从公网重新取得 openspec 副本。
  消化方式：它只能校验自己在临时目录里写的文件——写不进 plane 树（I3），
  产不出被承认的裁决（I4）。**代价是必须承认「不可见」在 P5 之前是尽力而为，
  不能在验收里写成已强制。**
- **R2 模型凭记忆手写 spec。** openspec 格式是公开的，隐藏挡不住书写，
  只有 I3 挡得住落地。G6 就是为这条设的。
- **R3 gateway 成为唯一信任根。** 判据全部经由 openjiuwen 的帧。gateway
  被改则全线失守。缓解：openjiuwen 源码只读引用，unit 受现有 sandbox guard
  保护（widening 判 exit 21），unit 文件变更纳入门禁。
- **R4 成本。** 每个 change 多两次派发（validate、archive），graph 一次；
  author 派发数不变。按 217 已测的单角色派发量级，增量以分钟计，不以小时计。
- **R5 迁树摩擦。** 工作期内仓库没有 `openspec/` 目录，仓库内的 openspec 类
  工具全部不可用——这是目的，不是缺陷；但 `sweep` / `close` / worktree 相关
  路径需要逐条复核。

---

## 12. 回滚

`git reset --hard v0.12.1-openspec-caller-side` 恢复代码；
`/var/lib/aidlc/specs/<repo-id>/openspec` 拷回仓库 `openspec/`；
停用 `aidlc-shell` 包装即可让 CC 恢复直连 openspec。记录目录保留不删，
作为收容期的证据。
