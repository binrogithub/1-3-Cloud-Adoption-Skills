# PRD — 全开网关沙箱：整机即沙箱（功能优先）

状态：**决策已定** —— Robin 于 2026-09-01 会话内裁决：「授权
openjiuwen 全文件夹访问权限，把整体安装环境当作沙箱。先完整功能
可用。」运行时在讨论中给出的折中（仅授 `/tmp`、逐仓库 `BindPaths`）
与「全开」的安全代价均已于会话内陈述，被否决/接受，记录在案。
仓库 `<repo-path>`（master `540c4b2`，v0.16.0，套件 34/34）。
事故源：country-e-m1 run（2026-09-01，`/tmp/country-e`，close exit 11 裂态；
证据 `…/evidence/plan-archive-1.jsonl` 与 `close-deviation.md`）。

回滚锚点：落地前 master 打 `v0.16.1-pre-open`；单元 `.bak` 链延续
（现有两份：`.bak.1788023482`、`.bak.1788196532`）。

本 PRD 取代同日草案 `prd-tmp-close-reachability.md`（未提交，删除）：
其中的 exit-24 双出路与 `--write-back caller` 模式**随本决策作废**，
「close 与归档拆分（B 方案）」**延后**（见 §10 残余）。

---

## 1. 决策与它换来什么

**决策内容**：网关单元的挂载墙退役，会话可写面 = 整机文件系统。
这不是运行时自我扩权（章程仍禁止），是操作者的一次主机步骤。

**换来的**：任何路径下的仓库（含 `/tmp`，站点任务的自然居所）全程
走正门 —— plane 署名写回、签名归档记录，不再需要侧门或人工补完。
country-e-m1 式裂态的**成因**（会话私有 `/tmp`）消失。

**交出去的**（操作者已知悉并接受，见 §10）：会话以 root 身份运行，
墙拆掉后 ——
`/usr/local/bin/openspec`（裁判）变为可改写；`/etc/aidlc` 的
裁决签名密钥变为可读取。即：签名记录从「机械不可伪造」降级为
「信任会话本身」。系统目录（`/usr`、`/etc`、systemd 单元、cron）
对失控会话全部可写，爆炸半径从项目文件变为整机。

## 2. 全开后仍然存在的功能缺陷

| # | 位置 | 缺陷 | 全开后的变化 |
|---|------|------|--------------|
| 1 | `cmd_classify` 写探针 | mkdir -p 式**创造**被探路径 | **更严重**：私有 ns 没了，污染直接落在宿主真文件系统上 —— classify 一个不存在的路径会把它创建出来 |
| 2 | `cmd_classify` 裁决政策 | 「the probe decides」压过 unit 授权 | 保留：若单元从 `.bak` 回滚，判定必须重新诚实 |
| 3 | `cmd_close` 命令序 | `openspec archive`（plane 树变更）先于一切写回，无前置检查 | 成因消失，但**普通失败**（git 冲突、目标异常、磁盘）仍会裂态 |
| 4 | `cmd_close` 重跑 | 裂态后重跑再次 archive → 必败，恢复需手工 plane 树手术 | 同上，仍需最简续跑 |

## 3. 目标与非目标

目标：一次单元变更 + 最小运行时对齐，使任意路径仓库的完整生命周期
（migrate → work → validate → deliver → gate → close）全程 plane 侧
完成并经端到端验收；运行时在「全开」与「.bak 回滚」两种形态下都
判定诚实。

非目标：不做 uid 分离与密钥托管（恢复「不可伪造」的路径，仅记录）；
不改 aidlc-shell 与 CC 侧收容（「CC 永不调用 openspec」纪律不变，
本决策只涉网关）；不改 openjiuwen / openjiuwen / openspec 源码；
不做中断自动重派；不做 `--write-back caller`（作废）；不实现 B 方案
全量拆分（延后，只做其最简续跑子集）。

## 4. 不变式（验收逐条判定）

- **I1 探针不得创造存在**：classify 探测后，宿主上不得出现探测前
  不存在的路径组件（既有目录内即建即删的探测临时文件不算）；
  `probe_created_paths` 恒空并以断言守护。
- **I2 判定机械可查**：class 判定含对 `/proc/<MainPID>/mountinfo` 的
  机械读取；遮蔽挂载覆盖的路径前缀一律 `invisible`，探针只许更
  保守。全开形态下此检查恒空，但**必须在**——单元一旦回滚它就是
  唯一诚实的判定来源。
- **I3 close 先检后动**：`openspec archive` 之前完成仓库可达性判定；
  不可达 → plane 树未变更即停止（沿用 exit 语义，文案指向单元回滚
  状态或路径本身，不再有「双出路」）。
- **I4 裂态可续（最简）**：重跑 close 时以树形状判定「已归档」
  （`changes/<id>` 不在且 `archive/<date>-<id>` 在）→ 跳过 archive
  从写回续起；形状不明时退化为只读 status 字面量探树。续跑事实入
  签名记录。
- **I5 门禁不松**：MERGE_GATE 前置（approved + 具名 rationale）不变；
  无任何自动重派。
- **I6 双形态正确**：运行时不得假设全开永存。单元回滚到 `.bak` 后，
  classify 必须对 `/tmp` 诚实报 invisible（靠 I2，不靠探针污染），
  close 在 I3 处干净停止 —— 与全开形态同样正确。

## 5. 单元目标态（P0，主机步骤，Robin 按键）

```ini
[Service]
NoNewPrivileges=true          # 与文件面无关、零功能代价，保留
PrivateTmp=false
# 2026-09-01 operator decision: whole environment as the sandbox —
# full functionality first. ProtectSystem/ReadWritePaths retired;
# accepted residual in docs/prd-gateway-open-sandbox.md §10.
ReadOnlyPaths=<local-dir>    # 网关自身源码只读：自我完整性，零功能代价
```

即：删除 `ProtectSystem=strict` 与 `ReadWritePaths=…` 两行，
`PrivateTmp` 翻为 `false`。保留的 `ReadOnlyPaths=<local-dir>` 与
`NoNewPrivileges` 若 Robin 认为「全开」意指字面一切，可一并去除
—— P0 执行时一句话的事，PRD 默认保留。

执行序：`cp` 单元为新 `.bak` → 按目标态编辑 →
`systemctl daemon-reload && systemctl restart jiuwenswarm-gateway` →
用 classify 验证（对 `/tmp` 下现存路径应报 writable 且
`probe_created_paths` 为空）。

## 6. 运行时对齐（P1/P2）

- **classify（P1）**：写探针改非创造式（读探针 + 仅在既有目录内的
  临时文件建删）；mountinfo 遮蔽守卫（I2）；裁决政策改为
  「遮蔽一票否决，其余分歧取最保守，`decision_basis` 标明依据」。
  全开形态下几乎恒为 writable —— 判定简单，但必须是真的简单而不是
  恰好没被拆穿。
- **close（P2）**：I3 前置 + I4 最简续跑（树形状优先，status 字面量
  兜底）。帧契约（命令字面量与帧判）不变。
- **文档与版本（P3）**：`docs/plane-runtime.md` §1 类表标注「全开
  形态：单一 writable；.bak 形态：原三分类」、§2 追加本次决策与
  日期、§3 external_directory 说明对齐；CHANGELOG；tag `v0.17.0`。

## 7. 数据契约

classify JSON 增：`masked_by: "<mount>" | null`、
`probe_created_paths: []`（恒空，断言）、
`decision_basis: "mountinfo" | "probe" | "grants"`。

close JSON 增：`reachability: {class, checked_at}`、
`resumed_from: "write-back" | null`。不新增 `write_back` 字段
（caller 模式作废）。

## 8. 反向门（每条对今天的代码判 RED）

- **R-G1** 对不存在的 `/tmp/never-created` 跑 classify → 今天（全开
  后）会在宿主**创建**该路径；修后不创建且如实报判定。
- **R-G2** 全新 `/tmp` 仓库端到端（migrate → work → validate →
  deliver → gate → close）→ 今天 exit 11 裂态；修后闭环，仓库内
  出现 plane 署名的归档写回提交，无裂态。
- **R-G3** `/root` 下仓库回归 → 行为不变（不得误伤既有面）。
- **R-G4** 回滚演练：单元还原 `.bak` → classify 对 `/tmp` 报
  invisible（I2 兜住，而非探针污染）；close 在 I3 干净停止。演练后
  重新全开。

## 9. 分期

- **P0** 主机步骤（§5）：Robin 按键或明确委托执行；`.bak` 链 + 验证。
- **P1** classify 诚实（I1/I2 + 数据契约）；验收 R-G1。
- **P2** close 前置与最简续跑（I3/I4）；验收 R-G2/R-G3。
- **P3** 文档对齐 + CHANGELOG + `v0.17.0`；验收 R-G4（回滚演练）。

P0 先行（P1 的 R-G1 需要 P0 后的宿主直染形态才测得出真 RED）。

## 10. 风险与残余（操作者已接受的部分明示于此）

- **裁决可伪造（已接受）**：会话可读 `/etc/aidlc/verdict.key`、可改
  写 openspec 二进制 → 签名记录降级为「信任会话」。恢复路径（不在
  本期）：uid 分离 + 密钥托管，或单元回滚。接受理由：单操作者工作
  机、功能优先。
- **共享 `/tmp` 面开放（已接受）**：会话可写他人临时文件。
- **普通失败仍可裂态**：P2 之前，close 中途的 git 冲突等仍会裂；
  P2 落地后仅剩「拆分 close 与归档（B 方案）」可彻底消除 —— 延后，
  触发条件：P2 的最简续跑仍不够用时。
- **CC 侧收容不变**：aidlc-shell 掩蔽与「CC 永不调用 openspec」与
  本决策正交，未被触碰。

## 11. 回滚

单元：新 `.bak` 落盘后，`cp …bak.<ts> …service && daemon-reload &&
restart` 即回旧形态（I6 保证运行时在旧形态下同样正确）。代码：每期
一提交，按期 revert；tag `v0.16.1-pre-open` 为总锚点。
