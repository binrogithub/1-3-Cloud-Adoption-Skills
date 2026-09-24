# PRD · 安装时强制 MaaS key + 交互式定义 review 角色人设

> 两处独立缺口，合并成一个 change：装完却没有可用凭据的安装不该报
> "success"；能让人写自己心目中角色人设的地方，不该是一份已经被记录
> 证明"配了也没用"的死配置。

- 目标仓库：`<workspace-root>`（本仓库自身，`install.sh` +
  `scripts/setup-maas-key.sh` + 新增 `scripts/setup-review-axes.sh`）
- 关联：`docs/team-mode-record.md`（openjiuwen team 模式/`predefined_members`
  已被实测证伪，本 PRD §01-B 引用其结论作为设计依据，不重跑实验）
- 文档日期：2026-09-07
- 优先级：P1

---

## 01 问题

### A · MaaS key 缺失时，安装仍然报成功

`ensure_maas_key()`（`install.sh:1034-1050`）已经做对了一半：key 已存在
时会跳过重新询问（`ok "MaaS API_KEY already configured … shared by every
installed agent"`），这一点不用改。缺口在失败路径：

- 交互式环境里，`ensure_maas_key()` 调用
  `scripts/setup-maas-key.sh --force`，但**不检查它的返回码**——用户在
  `read -rs` 提示前直接回车/中断，`setup-maas-key.sh` 会因为空 key 校验
  （`api key must not be empty or whitespace-only`）以 `exit 1` 退出，
  但这个 1 在 `ensure_maas_key()` 里被直接丢弃。
- 非交互式环境（CI、管道）里，`ensure_maas_key()` 只 `warn`，同样不置
  `rc=1`。
- `main()` 里唯一调用点（`install.sh:1349`）是裸调用
  `ensure_maas_key`，没有 `|| rc=1`——即使上面两条路径真的改成返回 1，
  这里也接不住。
- `run_bootstrap()` 的"步骤 3/5"（`install.sh:1115-1123`）是另一条独立
  路径：**无条件**调用 `setup-maas-key.sh --force`，不先检查 key 是否
  已配置——跟 `ensure_maas_key()` 已有的"配过就跳过"语义不一致，每次跑
  `--bootstrap` 都会被重新问一遍。

结果：`./install.sh` 或 `./install.sh --bootstrap` 在 key 缺失/输入为空
的情况下，仍然打印 `ok "Install complete."` / `ok "Bootstrap complete."`
并以 0 退出——直到用户真正跑一次 planned 任务、`bin/plan.py` 派发到
openjiuwen 网关失败，才会发现装的时候就没配对。

### B · "角色定义"最初想接的挂钩点是一段已被证伪的死配置

最初的方向是把"角色人设"接到 openjiuwen 网关自己的团队花名册
`~/.jiuwenswarm/config/config.yaml` 下的
`team.jiuwen_team.predefined_members`（leader/developer/tester/reviewer，
各带一条中文 `persona` + `prompt_hint`）。核对 `docs/team-mode-record.md`
后确认这条路是死的，原文（finding 2）：

> A configured roster for the wildcard team is not read on the
> command-line path. … three adversarial personas … were written into
> `~/.jiuwenswarm/config/config.yaml` under
> `modes.team.jiuwen_team.predefined_members`, the gateway was
> restarted, and a team round ran for 2,672 frames. The roster names
> appeared nowhere in the run.

即：这份花名册只被 openjiuwen 的 Web channel handler 读取，
`bin/plan.py` 走的命令行路径完全不读它——不管这次往里面填什么中文还是
英文人设，实际派发时都不会生效，装出来的是一个"看起来配置了、实际上
不做任何事"的功能。`docs/team-mode-record.md` 已经明确记录"这份花名册
2026-08-31 被移除过一次"，本 PRD 不重开这个已有定论的讨论。

真正被 `bin/plan.py` 读取并用于会话派发的、唯一可命名多个"角色人设"的
现成机制，是 `review_axes()`（`bin/plan.py:4050` 起）从
`config/collapsed.config.yaml` 的 `review:` 段读出的审查轴——设计-审查
（design-review）环节按这里的
`axis.<name>.{stance,accepts,refuses}` 逐条构造 `reviewer_prompt()`
（`bin/plan.py:4153`），真实派发成独立会话。约束也已经在代码里写死：
`max_axes`（当前 3）、每个 persona 的 `stance/accepts/refuses` 三项必填
（`roster_check()`），以及"任意两个 persona 不能共享同一个 stance"。
这是本 PRD 实际要接的挂钩点。

## 02 目标与非目标

**目标**

- A：`ensure_maas_key()` 在 key 最终仍为空时返回 `1`；`main()` 用
  `ensure_maas_key || rc=1` 接住，使 `install.sh` 整体以非零码退出并走
  `fail "Install completed with errors."` 分支。`run_bootstrap()` 的
  "步骤 3/5"改为先做与 `ensure_maas_key()` 相同的"已配置就跳过"检查，
  只有缺失时才提示；缺失且非交互式（无法提示、stdin 也没有被喂 key）
  时同样置 `rc=1`，不再只 `warn`。已配置时两条路径都保持零提示——这是
  用户已确认的"所有场景一律硬失败"决策的落地。
- B：新增 `scripts/setup-review-axes.sh` + `install.sh --configure-roles`
  入口，在 `ensure_maas_key` 之后（`main()` 收尾处）对**每一个本次实际
  安装到的 target**（跟 `install_skills_to_target()` 复制 `config/` 的
  范围一致，逐 target 各自的 `<config_dir>/skills/ai-dlc/config/
  collapsed.config.yaml`）跑一次交互：
  - 全英文提示与菜单文案（不影响文件里已有的中文 `review.axis.*`
    默认值——用户不选就原样不动）。
  - 列出候选轴的预设名字+人设文本（如 `security` / `operability` /
    `performance` 沿用现有默认三条，另外补 `correctness`、
    `spec-completeness`、`maintainability` 等新预设），多选（最多
    `max_axes` 条，超选时提示重选而不是静默截断——对齐
    `SKILL.md`"更多是拒绝，从不静默截断"的既有措辞）；每条允许直接用
    预设的 `stance/accepts/refuses`，或选完预设后再追加自定义文本，或
    完全跳过预设直接三项都手打。
  - 已经不是出厂默认三条（`security`/`operability`/`performance` 且
    文本与仓库出厂值逐字相同）时，视为"已配置过"，跳过交互（对齐 A 的
    "配过不再问"语义）；显式 `--configure-roles` 总是强制重新问一遍
    （对齐 `--setup-maas-key` 已有的 `--force` 语义）。
  - 写回时用与 `setup-maas-key.sh` 相同的纪律：mktemp 同目录 +
    `chmod 600`/一致权限 + `mv` 原子替换，只改 `review:` 段下
    `axis.*` 与 `max_axes`（如用户选择的轴数改变了上限判断的分母，本
    PRD 不改 `max_axes` 本身的值，只在选择数超过既有 `max_axes` 时拒绝
    ——修改 `max_axes` 数值是另一个 change 的事），其余 9 个顶层 key
    原样保留。

**非目标**

- 不碰 `~/.jiuwenswarm/config/config.yaml` 或
  `team.jiuwen_team.predefined_members`——`docs/team-mode-record.md` 的
  结论不重新评估。
- 不新增 spec/design/verify 这三个字面角色名——它们是最初需求里的
  示例说法，落地后对应的是"三条可命名、真实生效的 review 轴"，不是
  ROUTE/WORK/DESIGN/CHECK 这些生命周期阶段本身的人设（那些阶段的
  角色 prompt 是 `bin/plan.py` 里按阶段硬编码构造的，不在本 PRD 范围）。
- 不修改 `max_axes` 的出厂值，也不做"自动把用户选的轴数写回
  `max_axes`"这类联动。
- `--all-targets` / `--target` 之外，不新增遍历未安装 target 的逻辑——
  只处理本次 `install.sh` 调用实际会写入的 target 集合。

## 03 设计草图

**A（`install.sh`）**

```bash
ensure_maas_key() {
  local env_file="${AI_DLC_ENV_FILE:-$HOME/.jiuwenswarm/config/.env}"
  local maas_key=""
  [[ -f "${env_file}" ]] && maas_key="$(grep '^API_KEY=' "${env_file}" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [[ -n "${maas_key}" ]]; then
    ok "MaaS API_KEY already configured (${env_file}) — shared by every installed agent"
    return 0
  fi
  if [[ -t 0 ]]; then
    "${SCRIPT_DIR}/scripts/setup-maas-key.sh" --force || { fail "MaaS API_KEY still not configured"; return 1; }
  else
    fail "MaaS API_KEY not configured and no key piped via stdin — install cannot proceed"
    fail "run './install.sh --setup-maas-key' interactively, or pipe a key: printf '%s\n' \"\$KEY\" | ./install.sh --setup-maas-key"
    return 1
  fi
  [[ -f "${env_file}" ]] && maas_key="$(grep '^API_KEY=' "${env_file}" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  [[ -n "${maas_key}" ]] || { fail "MaaS API_KEY still empty after setup"; return 1; }
}
...
ensure_maas_key || rc=1
```

`run_bootstrap()` 步骤 3/5 同理，前置同一段"已配置就跳过"检查（抽成
共享函数 `maas_key_present()`，`ensure_maas_key()` 和 `run_bootstrap()`
都调用它，避免两处判断逻辑各写一份而慢慢漂移）。

**B（新增 `scripts/setup-review-axes.sh`，参数对齐 `setup-maas-key.sh`
的既有形状）**

```
Usage: setup-review-axes.sh --config-file <path/to/collapsed.config.yaml> [--force]
```

- 读取目标文件里 `review.axis.*` 现状，与仓库出厂值逐字比较，决定是否
  跳过（`--force` 强制重问）。
- 交互问答全部英文：先问选几条轴（1–`max_axes`，读文件里现有
  `max_axes` 值作为上限），逐条问"pick a preset or write your own"，
  预设列表用编号菜单（`read -r -p`，纯 bash，不引入新依赖），自定义项
  依次追问 stance / accepts / refuses 三行文本。
- 校验：轴名唯一、三项均非空、任意两轴 stance 不重复（复用
  `roster_check()` 的判据描述，脚本侧做同等的字符串级校验，即使写坏了
  最终也会被 `bin/plan.py` 自己的 `roster_check()` 拦下，这里的校验是
  提前给出更友好的报错，不是唯一防线）。
- 写回用 Python（复用 `setup-maas-key.sh` 已验证的 PYEOF 内联脚本套路，
  按行替换/追加 `axis.*` 系列 key，不引入 YAML 库依赖，保持与仓库其余
  安装脚本一致的"零第三方 Python 依赖"纪律）。

`main()` 收尾处，在现有的 target 安装循环（`--all-targets` / `--target`
/ 默认 claude-code 三条路径）各自完成 `install_skills_to_target()` 之后，
对每个成功安装的 `<config_dir>/skills/ai-dlc/config/collapsed.config.yaml`
调用一次 `setup-review-axes.sh`；非交互式环境下这一步只 `warn` 并跳过
（不像 A 那样硬失败——review 轴给的是出厂默认值就能正常工作的
可选人设，MaaS key 缺失是"任务直接跑不了"的硬约束，两者严重程度不同，
不套同一条"必须配置"规则）。

## 04 反向门 / 边界情况

- 已经跑过一次 `--configure-roles` 的 target，再跑一次普通
  `./install.sh` → 检测到非出厂默认值，跳过交互，`ok` 一行提示。
- `--all-targets` 时某个 target 的 `config_dir` 无效（现有
  `validate_config_dir` 已经会 `return 1` 并整体计入 `rc=1`）→
  `setup-review-axes.sh` 不会对这个 target 被调用，不新增二次报错。
- 用户在 B 的交互中选择的轴数超过文件里的 `max_axes` → 拒绝这次选择，
  重新问，而不是静默截断到 `max_axes` 条或自动改大 `max_axes`。
- A 的非交互路径：`printf '%s\n' "$KEY" | ./install.sh` 这类既有的管道
  用法要继续可用——`setup-maas-key.sh` 自己读 stdin 一行当 key 的逻辑
  不改，只改 `ensure_maas_key()` 外层在"读到的还是空"时的返回码。

## 05 验收

- `bats`/shell 测试（放进现有 `tests/`，具体文件名由实施者对齐既有
  命名）：
  - 空 `HOME`（无 `.jiuwenswarm/config/.env`）+ 非交互 stdin（`</dev/null`）
    跑 `./install.sh --target-dir <tmp>` → 退出码非零，stderr 含
    "MaaS API_KEY not configured"。
  - 预先写好非空 `API_KEY=` 的 `.env`，同样非交互跑 → 退出码 0，且
    `setup-maas-key.sh` 不被调用（用一个会写文件、能检测"是否被执行过"
    的 stub 替身验证零次调用）。
  - `setup-review-axes.sh --config-file <fixture>.yaml <<< $'2\n1\n...'`
    （喂选择序列）→ 产物文件的 `review.axis.*` 按预期更新，其余 9 个
    顶层 key 字节级不变（`diff` 掉 `review:` 段后其余内容相同）。
  - 同一 fixture 文件（已改过、非出厂默认）不带 `--force` 再跑一次 →
    不产生任何写入（用 mtime 或内容 hash 判断）。
- 人工验证（依赖真实网关，记在这里，不进自动化范围）：装完之后跑一次
  真实的 `bin/plan.py review`，确认 dispatch 出的
  `review-<axis>-N` 会话数量、prompt 内容跟新写入的 `axis.*` 一致。

## 06 回滚

A、B 都只新增/修改 shell 脚本内的函数与一个新脚本文件，不改
`bin/plan.py` 的读取逻辑（`review_axes()`/`roster_check()`/
`max_axes` 校验原样不动，只是它们读到的 `config/collapsed.config.yaml`
内容可能被安装期交互改写）。回滚即 `git revert` 这一个 change 的提交；
已经被交互写坏/写乱的某个 target 的 `collapsed.config.yaml`，用仓库
里的出厂版本 `cp` 覆盖即可单独恢复，不影响其它已安装 target。
