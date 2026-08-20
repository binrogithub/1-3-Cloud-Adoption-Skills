# PRD：统一安装脚本（bootstrap）

**版本：** 1.0
**日期：** 2026-08-20
**状态：** Approved for implementation
**依赖：** `docs/PRD.md`、`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`
**适用分支：** `feat/direct-maas-router`

## 0. 产品摘要

提供一个统一安装脚本 `scripts/bootstrap.sh`，在全新机器上一步完成
Claude Code Direct MaaS Delegate Router 的完整安装：

- root 侧：写入 MaaS 凭证环境文件、安装 systemd unit、部署适配器产物、
  启动服务；
- 用户侧：安装 `claude-maas` 启动器、客户端配置（指向 loopback 适配器）和
  launcher 软链接；
- 可选：安装 Exa 网络搜索。

MaaS API Key 通过 stdin 传入（必选，永不进入 argv）。MaaS 上游 chat URL 通过
`--maas-url` 传入（必选）。Exa 通过 `--with-exa` 可选启用。

```text
全新机器：
  printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
    | sudo bash scripts/bootstrap.sh \
        --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions

  -> /etc/claude-code-proxy/maas.env        (root:root 0600, 真实 Key)
  -> /etc/systemd/system/claude-code-maas-proxy.service
  -> /opt/claude-code-maas-proxy/{server.js,lifecycle.js}
  -> systemctl enable --now + restart
  -> ~/.config/claude-maas/{api-key(=maas-local-proxy),config.json(->127.0.0.1:3000)}
  -> ~/.local/bin/{claude-maas,claude-select,delegate,workflow}
```

## 1. 背景与现状缺口

项目当前有两个互不衔接的安装入口，都无法在全新机器上独立完成安装：

| 入口 | 做什么 | 缺什么 |
| --- | --- | --- |
| `scripts/install.sh` → `client/claude-maas-setup.sh` | 安装用户侧 `claude-maas` 启动器 + 客户端配置（`~/.config/claude-maas/`），`anthropic_base_url` 指向 `http://127.0.0.1:3000` | 不安装适配器、systemd unit、env 文件 |
| `adapter/deploy.sh` | 把 `server.js` + `lifecycle.js` 交换到 `/opt/claude-code-maas-proxy/` 并重启 systemd unit | 假设 unit 和 `/etc/claude-code-proxy/maas.env` 已存在（8-04 legacy 残留）；全新机器上不存在 |

线上主机（2026-08-20 复核）的实际拓扑：

| 项 | 值 |
| --- | --- |
| systemd unit | `/etc/systemd/system/claude-code-maas-proxy.service`（Type=simple, ExecStart=/usr/bin/node …/server.js, EnvironmentFile=/etc/claude-code-proxy/maas.env, Restart=always） |
| env 文件 | `/etc/claude-code-proxy/maas.env`（root:root, 0600, 241 字节） |
| `ANTHROPIC_PROXY_BASE_URL` | `https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions` |
| server.js 默认 chat URL | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions`（`adapter/server.js:30`） |
| **路径不一致** | 线上用 `/v2/`，代码默认用 `/openai/v1/` |
| 客户端 api-key | `maas-local-proxy`（dummy，17 字节） |
| 客户端 config | `anthropic_base_url=http://127.0.0.1:3000`, `model=glm-5.2` |

**关键结论：** `--maas-url` 必须是用户提供的完整 chat-completions URL，不得从
代码默认值推导——线上 `/v2/` 与默认 `/openai/v1/` 的分歧证明推导不安全。

## 2. 决策

### 2.1 采用

- 单一 `scripts/bootstrap.sh` 安装完整 stack。
- 凭证拓扑：真实 Key 存放在 root 拥有的 `/etc/claude-code-proxy/maas.env`
  （0600）；客户端持有 dummy `maas-local-proxy`；适配器通过 `getAuthKey()`
  fallthrough 注入真实 Key。真实 Key 永不进入用户 home。
- `--maas-url` 为完整 chat URL，必选，用户提供，不做推导。
- MaaS Key 通过 stdin 第 1 行传入，必选，永不进入 argv。
- 复用现有脚本：`adapter/deploy.sh`（产物部署 + 重启）、
  `client/claude-maas-setup.sh`（用户侧配置）、`scripts/configure-exa.sh`
  （Exa，仅 `--with-exa` 时调用）。
- 幂等：重复运行安全（env 原子覆写、unit 覆写、`daemon-reload` + `restart`、
  deploy.sh 保存 rollback）。
- `--dry-run` 字节级无副作用。

### 2.2 不采用

- 不把 Key 放进 argv、环境变量、用户 home、Git 或日志。
- 不从代码默认值推导 MaaS chat URL。
- 不自动安装 OAuth 编排策略（`configure-policy.sh` 保持独立，Mode A 用户单独
  运行）。
- 不使用 pm2 / docker / 第二个 listener。
- 不在 v1 支持多主机、k8s 或非 systemd init。

## 3. 凭证拓扑与权限模型

```text
用户 home（~/.config/claude-maas/，用户拥有）：
  config.json:  anthropic_base_url = http://127.0.0.1:<port>
                model              = glm-5.2
  api-key:      maas-local-proxy   (dummy)

root 拥有（/etc/claude-code-proxy/maas.env，0600 root:root）：
  CLAUDE_CODE_PROXY_API_KEY = <真实 Key>
  ANTHROPIC_PROXY_BASE_URL  = <完整 MaaS chat URL>
  COMPLETION_MODEL          = glm-5.2
  PROXY_HOST                = 127.0.0.1
  PROXY_PORT                = 3000
  DEBUG                     = false

请求流：
  claude-maas --(dummy Bearer)--> adapter:127.0.0.1:3000 --(真实 Key)--> MaaS
```

| 文件 | 属主 | 模式 | 内容 |
| --- | --- | --- | --- |
| `/etc/claude-code-proxy/maas.env` | root:root | 0600 | 真实 Key + URL + model |
| `/etc/systemd/system/<service>` | root:root | 0644 | unit 定义 |
| `/opt/claude-code-maas-proxy/server.js` | root:root | 0644 | 适配器 |
| `/opt/claude-code-maas-proxy/lifecycle.js` | root:root | 0644 | 生命周期控制器 |
| `~/.config/claude-maas/api-key` | 用户 | 0600 | `maas-local-proxy` |
| `~/.config/claude-maas/config.json` | 用户 | 0600 | loopback URL + model |

### sudo 流程

1. 用户以非 root 身份运行 `printf '%s\n' "$KEY" | sudo bash scripts/bootstrap.sh …`。
2. 脚本检测 EUID != 0，通过 `sudo` 重新执行自身（stdin 管道保留，Key 随 stdin
   传入）。
3. root 阶段：写 env 文件、写 unit、部署产物、启动服务。
4. 用户阶段：以 `$SUDO_USER` 身份（`sudo -u`，HOME 设为该用户 home）运行
   `claude-maas-setup.sh`，使 `~/.config/claude-maas/` 落在真实用户 home 而非
   `/root`。
5. 直接以 root 运行（无 sudo）时，要求显式 `--user`/`--home`，否则报错（避免
   `$HOME=/root` 误装）。

## 4. 接口契约

### 4.1 CLI

```bash
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions \
      [--model glm-5.2] \
      [--port 3000] \
      [--with-exa] \
      [--env-file /etc/claude-code-proxy/maas.env] \
      [--dest /opt/claude-code-maas-proxy] \
      [--service claude-code-maas-proxy.service] \
      [--skip-systemd] \
      [--skip-verify] \
      [--dry-run] \
      [--user <username>] \
      [--help]
```

### 4.2 stdin

- 第 1 行：MaaS API Key（必选，非空，单行）。
- 第 2 行（仅 `--with-exa` 时）：Exa API Key（必选，非空，单行）。

### 4.3 flags

| flag | 必选 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--maas-url` | 是 | — | 完整 MaaS chat-completions URL，必须 HTTPS（或 localhost），路径含 `chat/completions` |
| `--model` | 否 | `glm-5.2` | 模型 id |
| `--port` | 否 | `3000` | 适配器 loopback 端口 |
| `--with-exa` | 否 | — | 启用 Exa 安装（读 stdin 第 2 行） |
| `--env-file` | 否 | `/etc/claude-code-proxy/maas.env` | env 文件路径（测试覆盖） |
| `--dest` | 否 | `/opt/claude-code-maas-proxy` | 适配器产物目录（测试覆盖） |
| `--service` | 否 | `claude-code-maas-proxy.service` | systemd unit 名（测试覆盖） |
| `--skip-systemd` | 否 | — | 跳过 daemon-reload/enable/start（非 systemd CI） |
| `--skip-verify` | 否 | — | 跳过安装后 verify.sh |
| `--dry-run` | 否 | — | 打印将要执行的操作，不写任何文件 |
| `--user` | 否 | `$SUDO_USER` | 直接以 root 运行时的目标用户 |

### 4.4 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 安装成功 |
| 1 | 参数/验证错误（缺 `--maas-url`、空 Key、非 HTTPS URL 等） |
| 2 | 依赖缺失（node / systemctl 不在 PATH） |
| 3 | root 阶段失败（写 env/unit、部署、启动） |
| 4 | verify 失败 |

### 4.5 安全

- Key 永不出现在 argv、stdout、stderr、日志、进程标题。
- `die()` 只打印安全（无 Key）的错误消息。
- `--dry-run` 不写任何文件。

## 5. 安装步骤

按顺序执行：

1. **解析 flags + 验证**：`--maas-url` HTTPS 且路径含 `chat/completions`；
   `--model` 非空；node 在 PATH（否则 exit 2）；systemctl 在 PATH（除非
   `--skip-systemd`）。
2. **读 Key**：stdin 第 1 行（`IFS= read -r`，拒绝空/多行）；`--with-exa` 时
   读第 2 行。
3. **root 阶段**：
   a. 原子写 env 文件（mktemp + chmod 600 + chown root:root + mv）。
   b. `mkdir -p` 产物目录。
   c. 原子写 systemd unit（heredoc，ExecStart 指向产物目录）。
   d. `systemctl daemon-reload`。
   e. 调用 `adapter/deploy.sh`（`ADAPTER_DEST_DIR`/`ADAPTER_SERVICE` 覆盖）。
   f. `systemctl enable --now` + `restart` + `is-active` 检查。
4. **用户阶段**（以目标用户身份）：
   a. `printf 'maas-local-proxy\n' | client/claude-maas-setup.sh --base-url http://127.0.0.1:<port> --model <model>`
   b. `--with-exa` 时：`printf '%s\n' "$EXA_KEY" | scripts/configure-exa.sh`
5. **验证**（除非 `--skip-verify`）：`curl -sf http://127.0.0.1:<port>/status`。

## 6. 幂等性与回滚

- 重复运行 `bootstrap.sh` 安全：env 原子覆写、unit 覆写、`daemon-reload` +
  `restart`、`deploy.sh` 保存 `.rollback` 副本。
- 适配器回滚：`bash adapter/rollback.sh`（恢复上一版产物 + 重启）。
- 客户端卸载：`scripts/uninstall.sh`（默认保留 Key/审计，`--purge` 显式清除）。
- `--dry-run` 打印每步将执行的操作，不产生任何副作用。

## 7. 测试契约

`tests/test_bootstrap.py` 验证：

- `bash -n` 语法通过。
- 缺 `--maas-url` → exit 1。
- 空 Key / 多行 Key → exit 1。
- 非 HTTPS `--maas-url`（非 localhost）→ exit 1。
- `--dry-run` 不写任何文件。
- env 文件创建于覆盖路径，模式 0600，含 4 个预期 key。
- env 文件含真实 Key，不含 `maas-local-proxy`。
- 客户端 `api-key` 含 `maas-local-proxy`（dummy）。
- 客户端 `config.json` 的 `anthropic_base_url` = `http://127.0.0.1:<port>`。
- 适配器产物（server.js + lifecycle.js）复制到 dest，SHA-256 匹配仓库。
- systemd unit 写入，ExecStart/EnvironmentFile 正确。
- Key 不出现在 stdout/stderr。
- 重复运行成功，文件稳定。
- `--with-exa` 创建 `exa-api-key`；不带 flag 则不创建。

测试以 `HOME=tmp_path` 运行，stub `systemctl`（复用
`test_adapter_deploy.py` 的 STUB_SYSTEMCTL 模式），用 `--skip-systemd` +
路径覆盖指向 tmp_path。

## 8. 验收标准

1. `bash -n scripts/bootstrap.sh` 通过。
2. `pytest -q tests/test_bootstrap.py` 全部通过。
3. `make verify-offline` 通过（现有 600 测试 + 新 bootstrap 测试 +
   prohibited-dependency 扫描）。
4. 全新机器上 `bootstrap.sh` 一步完成安装；`curl 127.0.0.1:3000/status`
   返回 `stream-reliability-v2`。
5. `claude-maas --version` 可用。
6. 重复运行幂等。
7. Key 不出现在 stdout/stderr/argv。
8. `--dry-run` 无副作用。

## 9. 非目标

- 不支持多主机、k8s 或非 systemd init（v1）。
- 不把真实 Key 放入用户 home。
- 不自动安装 OAuth 编排策略。
- 不安装 pm2 / docker / 第二个 listener。
- 不推导 MaaS chat URL。
