# PRD：统一安装脚本收口（bootstrap v2）

状态：已交付
前置：`docs/PRD_UNIFIED_INSTALL_V1.md`（已交付 `scripts/bootstrap.sh`、
`tests/test_bootstrap.py`、README/OPERATIONS/SECURITY 更新）

## 0. 产品摘要

v1 交付的 `bootstrap.sh` 主干是对的：真实 Key 只进 root 拥有的 env 文件，
客户端只拿 dummy key + loopback URL，适配器产物复用 `adapter/deploy.sh`。
一次真实全路径安装（隔离 service/port/dest/HOME、systemd 实跑）已验证通过。

但它**报告成功的条件太弱**：一把完全无效的 Key 也能让脚本 exit 0 并打印
`bootstrap: complete`，而装出来的东西第一次请求就 401。同时 PRD v1 的验收
第 5 条（`claude-maas --version` 可用）在全新用户环境下不成立。

v2 的目标只有一个：**让"bootstrap 说成功"等价于"这台机器上 claude-maas
真的能干活"**，并补上三个已证实的功能缺陷。不新增安装能力。

## 1. 证据与缺口

以下每条都是在 119.8.83.10 上实测得到的，不是代码审查推论。

### G1 — verify 没有鉴别力（P0）

用 `dummy-key-for-bootstrap-test` 走完整安装（真实 systemd、无 --skip-*）：

    bootstrap: adapter /status ok
    bootstrap: complete
    BOOTSTRAP_EXIT=0

随后第一次真实请求：

    {"error_code":"ModelArts.81003","error_msg":"Invalid authorization header."}

根因：唯一的验收动作是 `curl 127.0.0.1:$PORT/status`。`/status` 是适配器
自身的健康端点，**与 Key 是否有效、上游 URL 是否可达、模型是否有后端实例
全部无关**——上游整体下线（`ModelArts.81010`，见 2026-08-03 事件）时它同样
返回 200。仓库里已有能真正判活的 `scripts/verify.sh`（live MaaS canary +
Claude Code E2E），bootstrap 不调用它。

### G2 — 验收第 5 条不成立：launcher 不在 PATH（P0）

脚本把 launcher 装到 `$TARGET_HOME/.local/bin/`，然后提示
`Next: claude-maas --version`。模拟全新用户环境：

    env -i HOME=<home> PATH=/usr/bin:/bin bash -c 'command -v claude-maas'
    -> claude-maas: NOT ON PATH
    显式路径调用则正常：2.1.237 (Claude Code)

在 119 上看起来"可用"，是因为更早的手工安装在 `/usr/local/bin` 留了软链
——**这是掩盖缺陷的假绿灯，全新机器上不存在**。脚本既不检查 PATH，也不
在总结里告诉用户怎么补。

### G3 — `--user` 在文档主路径上恒被忽略（P1）

优先级写反了：`SUDO_USER` 高于显式 `--user`。而文档给出的调用方式就是
`sudo bash scripts/bootstrap.sh`，此时 `SUDO_USER` 必然有值。实测：

    --user root + SUDO_USER=nobody  ->  client user: nobody (home: /nonexistent)

显式 flag 必须压过继承来的环境变量，否则该 flag 在主路径上等于不存在。

### G4 — verify 的 curl 紧跟 restart，无重试（P2）

`systemctl restart` 之后立刻 `curl /status`。本次生产部署时实测撞到过
`Failed to connect ... after 0 ms`（服务几百毫秒后才 listen）。当前后果只是
一条假 WARNING；G1 修复后 verify 会变成硬门禁，这个竞态就会变成假失败。

### G5 — URL 校验的错误提示是死代码（P2）

`scripts/bootstrap.sh:174-194`：python 校验作为独立命令在 `set -e` 下失败
即退出，其后的 `if [[ $? -ne 0 ]]; then die "invalid --maas-url: ..."` 永远
不会执行。用户看到的是 python 的裸 stderr，退出码也不是 PRD §4.4 约定的值。

### G6 — 真实安装路径没有门禁（P1）

`tests/test_bootstrap.py` 20 个用例全部带 `--skip-systemd --skip-verify`，
即 unit 写入、`daemon-reload`、`enable`、`restart`、`is-active`、verify 六个
步骤**从未被任何自动化执行过**。这次是人工跑通的，一次性证据不沉淀为门禁，
下次改动照样会静默退化——与 `adapter/deploy.sh` 那三个缺陷（全绿 590 测试
下带着 message_delta 缺失、漏拷 lifecycle.js、pipefail 导致从不重启）同一类。

### G7 — 客户端配置目录无隔离开关（P2）

`--env-file/--dest/--service/--port` 都能覆盖，唯独 user phase 恒写
`$TARGET_HOME/.config/claude-maas/`。测试靠设 `HOME` 绕开。后果：在真机上做
一次带 `--port 3011` 的试装，会把**线上** claude-maas 的 base-url 改到试验
端口且无提示。本次核对时是靠手工 `HOME=/tmp/...` 才没打到生产。

## 2. 决策

### 2.1 采用

- **verify 升级为默认硬门禁**：本地 `/status` + 上游真实 canary +
  `claude-maas` 可执行性三段，任一失败 → 非零退出码 + 明确的修复指引。
- **复用 `scripts/verify.sh`**，不新写一套判活逻辑。
- **PATH 主动检查**：装完检测 `$TARGET_HOME/.local/bin` 是否在目标用户的
  PATH 上；不在则在总结里给出精确的一行修复命令，并让 verify 判失败
  （因为 PRD v1 验收第 5 条就是它）。
- **显式 flag 优先**：`--user` > `SUDO_USER` > 当前用户。
- **真实路径门禁**：新增 systemd 全路径测试，用隔离的 service/port/dest/HOME
  实跑一次，断言 unit active + `/status` 版本正确，收尾必须清理。

### 2.2 不采用

- 不为 verify 造新的健康检查协议（`/status` + verify.sh 已够）。
- 不自动改用户的 shell profile（只提示，不写 `.bashrc`——v1 的
  "never writes shell profiles" 不变量保留）。
- 不引入重试框架，只在 verify 的 `/status` 上做有界轮询。
- 不改凭证拓扑。

## 3. 接口变更

| flag | 变更 |
|---|---|
| `--skip-verify` | 保留；语义从"跳过一个提示"变成"跳过硬门禁"，帮助文本需说明风险 |
| `--user` | 优先级提到 `SUDO_USER` 之上 |
| `--config-dir PATH` | **新增**，覆盖客户端配置目录（默认 `$TARGET_HOME/.config/claude-maas`），供试装/多 profile 使用 |
| `--verify-live` / `--no-verify-live` | **新增**，控制是否打上游 canary（默认开；离线安装可关，关闭时明确打印"未验证上游"） |

退出码（沿用 PRD v1 §4.4 的分段）：

- `4` = 安装完成但 verify 失败（区别于 `3` = 安装步骤本身失败），
  且必须打印已完成的部分和回滚指引。

## 4. 验收标准

每一条都要求**先证明它在修复前失败**（反向门），再证明修复后通过。

1. **G1 反向门**：用一把无效 Key 完整安装 → 脚本必须非零退出（码 4）、
   stderr 指出上游认证失败；修复前同一场景 exit 0 + `complete`。
2. **G2 反向门**：`env -i HOME=<tmp> PATH=/usr/bin:/bin` 下安装 →
   必须报出 PATH 缺失并给出修复命令；把 `~/.local/bin` 加入 PATH 后同一
   流程通过。
3. **G3**：`--user X` 在 `SUDO_USER=Y` 存在时解析为 X；测试同时覆盖
   `--user` 缺省时仍回落到 `SUDO_USER`。
4. **G4**：verify 的 `/status` 轮询上限 ≥10s；用一个延迟 listen 的桩服务
   证明轮询有效，且超时后是失败而不是 WARNING。
5. **G5**：非法 URL 的退出码与错误文案符合 §4.4，且 `die` 分支可达。
6. **G6**：新增 systemd 全路径测试，隔离 service/port/dest/HOME 实跑，
   断言 `systemctl is-active` + `/status` 的 `version` 字段；无 systemd 的
   环境用 skip 标记但**必须在 CI 摘要里显式列出被 skip 的项**
   （不允许"永远 skip 的测试算通过"）。
7. **G7**：`--config-dir` 生效；并新增一条断言——未传 `--config-dir` 且
   目标目录已存在指向**不同端口**的 config 时，必须提示将被覆盖。
8. 幂等性、Key 不入 stdout/argv/用户 home、`--dry-run` 无副作用：
   沿用 v1 的既有断言，不得回退。
9. `make verify-offline` 全绿，且**新增测试数 ≥ 上述条目数**；
   `git status` 干净（v1 的产物与本次修改一并提交）。

## 5. 非目标

- 不支持多主机 / k8s / 非 systemd init。
- 不自动写用户 shell profile。
- 不改 `adapter/` 的协议行为。
- 不把真实 Key 放进用户 home（v1 不变量，保留）。
- 不做 Key 轮换的独立子命令（重跑 bootstrap 即轮换，v1 已定）。

## 6. 实施顺序

1. G5、G3（纯逻辑，最小改动，先把死代码和优先级修掉）
2. G7（`--config-dir`，后续测试要用它做隔离）
3. G4 → G1（先把轮询做对，再把 verify 升成硬门禁）
4. G2（PATH 检查并入 verify）
5. G6（systemd 全路径门禁，最后加，因为它依赖前面的隔离开关）
6. 一并提交 v1 未提交的产物
