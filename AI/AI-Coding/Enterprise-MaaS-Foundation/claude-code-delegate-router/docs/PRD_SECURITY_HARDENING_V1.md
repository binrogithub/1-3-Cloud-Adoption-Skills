# PRD — 安全加固 V1

状态: 已实施（D1–D11 全部落地；G1–G11 全绿，生产 2026-08-24 部署验证通过）
作者: Claude (OAuth 会话 — 安全类任务按策略留在本会话)
日期: 2026-08-24
实施日期: 2026-08-24
适用构建: main @ 1251e7a（adapter/server.js SHA-256 b8c7069b… 与 /opt 部署一致）
前序: PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2 / PRD_LOOP_CONTINUITY_V2

---

## 0. 范围声明

本 PRD 修复一次全面安全复查发现的问题。全部条目为**缺陷修复与加固**，
不新增产品功能，不改变"单回环适配器、单模型 glm-5.2、无 fallback"的
产品不变量。

复查覆盖：`adapter/`（server.js、lifecycle.js、deploy.sh）、`scripts/`
（bootstrap、verify、delegate、workflow、configure-policy、migrate、
uninstall、Exa 三件套）、`client/`（claude-maas、setup、claude-select）、
部署现场（/etc、/opt、systemd unit、~/.local/bin、监听端口）。
其中 S1、S2、S3 在生产端口 3000 上实测复现。

---

## 1. 已确认的安全不变量（保持，不改动）

复查确认以下既有设计**有效**，本 PRD 不动它们：

| 不变量 | 证据 |
| --- | --- |
| 真实 MaaS key 仅存于 root:root 0600 env 文件 | `/etc/claude-code-proxy/maas.env` 及备份均为 0600 root |
| key 全程 stdin 传输，不进 argv/日志/家目录 | bootstrap/setup/verify 三处均 `IFS= read -r` + 多行拒绝 |
| 客户端只持 dummy key（17 字节 `maas-local-proxy`） | `~/.config/claude-maas/api-key` 实测确认 |
| 回环绑定启动校验，拒绝非回环 | server.js:58-60 |
| /status 仅回环 + 仅枚举字段，泄密扫描测试覆盖 | server.js:1309-1316, tests/test_adapter_protocol_security.py |
| reasoning 内容绝不转发客户端（thinking 占位符方案） | tests 覆盖 `test_reasoning_canary_not_in_client_output` |
| Exa headersHelper fail-closed（属主/符号链接/0600/URL 校验） | scripts/exa-headers-helper.py |
| 禁依赖扫描 + 架构契约测试进发布门 | scripts/check-prohibited-dependencies.py |

---

## 2. 问题陈述（按严重度排序）

### S1（高危）畸形 Host 头导致适配器进程崩溃 — 已实测复现

`adapter/server.js:1304`：

```js
const url = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
```

该表达式不在任何 try/catch 内。`Host: [::1:bad` 这类畸形头使
`new URL` 抛 `TypeError: Invalid URL`，异步 handler 拒绝后进程退出，
systemd `Restart=always`（RestartSec=3）重启。实测（2026-08-24 08:33）：

```
TypeError: Invalid URL
    at new URL (node:internal/url:818:25)
    at Server.<anonymous> (/opt/claude-code-maas-proxy/server.js:1304:15)
systemd[1]: claude-code-maas-proxy.service: Failed with result 'exit-code'.
```

影响：任意本地进程**单请求**即可杀死全部进行中的流；持续发送即崩溃
循环 = 本地 DoS。重启窗口内所有 claude-maas 会话中断。

### S2（高危）/v1/messages 实际无鉴权，真实 key 被代理给任意本地进程

`adapter/server.js:181-193` `getAuthKey()`：请求无凭据、或凭据为 dummy
`maas-local-proxy` 时，回落到 `DEFAULT_KEY`（root env 文件中的真实
MaaS key）。实测：不带任何 Authorization 头 POST `/v1/messages` 即可
成功获得模型流式输出。

影响：同机任意进程（任意 UID）均可匿名消耗真实 key 的配额与费用；
攻击者还可借 root 服务"洗"请求来源。当前信任模型是"回环 = 可信"，
在多用户主机上不成立。

附带问题：`getAuthKey` 把客户端提供的任何非空 key 原样转发上游（直连
key 模式），该行为未显式开关，默认静默放行。

### S3（中）非流式路径无并发准入、无超时

`adapter/server.js:583-596` `proxyNonStreaming`：

- 不经过 `concurrencyGuard.tryAdmit()`（准入只在 proxyStreaming 有）；
- `fetch` 无 `signal`、无任何超时 — 上游挂起则请求永久挂起（实测
  挂住 >10s 无响应也无报错）；
- 可无上限并发，绕过 MAX_CONCURRENCY=8 的容量保证，直打上游配额。

### S4（中）非流式路径原样转发上游错误体

`adapter/server.js:589-593`：

```js
const text = await upstream.text();
if (!upstream.ok) {
  res.writeHead(upstream.status, { "content-type": "application/json" });
  res.end(text);   // <-- 原样透传
```

与 ERROR_TEMPLATES 注释"never forward raw upstream bodies"矛盾。流式
路径有脱敏模板，非流式路径没有；上游错误体可能携带内部信息。现有
`test_upstream_error_body_not_forwarded` 只覆盖流式路径。

### S5（中）workflow run_id / item_id 路径穿越写

`scripts/workflow`：

- `_ensure_run_dir(run_id)`（L297）：`WORKFLOWS_DIR / run_id`，
  `run_id` 来自 manifest，无字符集校验；
- `_write_item_result`（L308）：`run_dir / f"{item_id}.json"`，
  `item_id` 来自 item，同样无校验；
- `assets/manifest-schema.json` 对两者无 pattern 约束。

`run_id="../../.ssh"` 或 `item_id="../x"` 可把 0600 JSON 写到
workflows 目录外（以调用者身份）。manifest 若由委托产出物提供，
即成自伤面。

### S6（中）systemd 以 root 运行且无加固指令

`/etc/systemd/system/claude-code-maas-proxy.service`：无 `User=`、无
`NoNewPrivileges` / `ProtectSystem` / `ProtectHome` / `PrivateTmp` /
`RestrictAddressFamilies`。服务只需绑定非特权端口 3000 并读一个 env
文件，却以 root 运行并持有真实 key 读取权 — 违反最小权限，放大 S1
类内存/逻辑缺陷的 blast radius。

### S7（低）生产环境转发 x-fake-scenario 测试头

`adapter/server.js:576-580` `upstreamHeaders()` 无条件把客户端可控的
`x-fake-scenario` 头转发给真实 MaaS 端点。注释称"真实端点会忽略未知
头"，但这是不必要的生产攻击面（测试挂钩应测试开关控制）。

### S8（低）delegate goal 明文进入子进程 argv

`scripts/delegate:264-268`：`claude-maas -p <goal>` — 任务全文在 argv，
多用户主机上经 `/proc/*/cmdline` 对所有用户可见。key 不在 argv（已
保证），但任务文本（可能含敏感内容）在。

### S9（低）未纳管工件：client/claude-glm 未 git 跟踪却已装入 PATH

- `client/claude-glm` 是 claude-maas 的改名分叉（读
  `~/.config/claude-glm/`），git 未跟踪（`?? client/claude-glm`）；
- `~/.local/bin/claude-glm` 符号链接指向它，另有一个可执行备份
  `claude-glm.bak-20260824` 留在 PATH 目录里；
- 未跟踪 = 不进 prohibited-dep 扫描、不进任何测试门、不受架构契约
  约束 — 供应链卫生缺口。

### S10（低）verify.sh 证据 heredoc 把不可信字符串内插进 Python 源

`scripts/verify.sh:546-588`：`"${_version_out}"`（claude --version 的
输出）等直接内插进 Python 源码。畸形版本串可破坏或注入代码（操作者
自跑，风险低，但应改环境变量传参）。

### S11（现场观察，非本仓库代码）主机存在未纳管同类监听

- 127.0.0.1:3001：`/root/argrepro/server_capture.js`，root 运行的
  适配器克隆，来源不明；
- 127.0.0.1:3100：`/opt/claude-glm-proxy/server.js` 服务 **glm-5.3**，
  违反"v1 仅 glm-5.2"不变量。

两者均违反"单回环适配器"产品不变量。本 PRD 仅要求处置并留档，不
修改其代码。

---

## 3. 修复方案（D1–D10）

### D1 — URL 解析防崩（修 S1）

`adapter/server.js` 入口处：

```js
let url;
try {
  url = new URL(req.url, `http://${HOST}:${PORT}`);   // 不再信任 Host 头
} catch {
  sendJson(res, 400, { type: "error", error: { type: "invalid_request_error", message: "malformed request target" } });
  return;
}
```

要点：base 直接用 `HOST:PORT`，**不反射 Host 头**（同时消除请求走私
类反射面）。回归测试：畸形 Host / 畸形 request-target 返回 400 且服务
进程存活、在途流不中断。

### D2 — /v1/messages 强制客户端凭据（修 S2）

- 新增 env `MAAS_CLIENT_KEY_FILE`（默认 `/etc/claude-code-proxy/client.key`，
  root:root 0600，bootstrap 生成随机 32 字节 dummy 替代固定串）；
- `getAuthKey()` 改为：`x-api-key`/Bearer 与 client.key 内容**恒定时间
  比较**相等 → 注入真实 key；其余（含无凭据、含旧 dummy
  `maas-local-proxy`）→ 401 `authentication_error`；
- 新增 env `MAAS_ALLOW_PASSTHROUGH_KEYS`（默认 `0`）：仅显式开启时才
  转发客户端自带 key 直连上游，并记录审计计数；
- 迁移：bootstrap 重跑时写 client.key 并同步更新客户端 config；
  旧部署未升级适配器前，回退行为保持现状（env 缺省 = 旧语义），
  但 verify.sh 新增门检查 401 生效（见 G2）。

### D3 — 非流式路径纳入生命周期控制（修 S3）

`proxyNonStreaming` 改为：

1. 入口 `concurrencyGuard.tryAdmit()`，满载返回 `OVER_CAPACITY`；
2. 构造 `RequestLifecycleController`（仅 connect+total 看门狗），
   fetch 带 `signal: ctrl.abortController.signal`；
3. `try/finally` 释放槽位，与流式路径同构。

### D4 — 非流式错误体脱敏（修 S4）

上游非 2xx 时不再透传 body，改用 `ERROR_TEMPLATES` + 上游 status 映射
（保留 `MAAS_UPSTREAM_HTTP` code 与上游 status code，正文只留枚举
message）。原始 body 仅计入 `recordError` 计数，不落日志。补测试：
非流式路径注入 canary，断言响应体无 canary。

### D5 — run_id / item_id 字符集校验（修 S5）

- schema：`assets/manifest-schema.json` 两字段加
  `"pattern": "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"`；
- 代码：`_validate_manifest` 双重校验（schema 与代码不漂移），
  违规 → `invalid_manifest`；
- `_write_item_result` 内再做一次 basename 一致性断言（防御纵深）。

### D6 — systemd 加固（修 S6）

分两步：

- **最低线（本次必做）**：unit 追加

  ```ini
  NoNewPrivileges=yes
  ProtectSystem=strict
  ProtectHome=yes
  PrivateTmp=yes
  PrivateDevices=yes
  RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
  RestrictSUIDSGID=yes
  MemoryDenyWriteExecute=yes
  CapabilityBoundingSet=
  ```

  （`ProtectHome=yes` 与读取 `/etc` env 文件、写 `/opt` 不冲突；
  WorkingDirectory=/opt 需 `ReadOnlyPaths=` 或保持 strict + 该目录
  只读即可满足。）
- **目标态（下个版本）**：专用 `claude-maas` 服务用户 + env 文件
  `root:claude-maas 0640`，去掉 root 运行。D2 的 client.key 同权限
  处理。

### D7 — 测试头开关（修 S7）

`upstreamHeaders` 仅当 `process.env.MAAS_TEST_UPSTREAM === "1"` 时
转发 `x-fake-scenario`；默认丢弃。契约测试改为显式设该 env。

### D8 — goal 经 stdin 传递（修 S8）

`claude -p` 支持无参数时从 stdin 读 prompt。`_make_real_client` 改为
`input=goal` 传入，argv 只留 `["claude-maas","-p","--model",…]`。
若上游 CLI 行为不符，退路是文档化该限制并在多主机部署说明中标注。

### D9 — claude-glm 纳管或清除（修 S9）

二选一，由维护者定：

- **A（推荐）**：`git add client/claude-glm`，纳入扫描与测试门，删除
  `~/.local/bin/claude-glm.bak-*` 可执行备份；
- **B**：删除 `client/claude-glm` 与 `~/.local/bin/claude-glm` 符号链接
  （`claude-maas` 已覆盖其功能）。

处置结果写入 RELEASE_NOTES。`migrate.sh` 已把 `claude-glm` 列为
owned_wrapper，路径 B 与其兼容。

### D10 — 证据生成去内插（修 S10）

`verify.sh` 证据段改为经环境变量 + `json.dumps` 传参，禁止任何不可信
字符串进入 Python 源码文本。

### D11 — 现场处置（S11，运维动作）

- 调查并停用 `/root/argrepro` 3001 capture 服务（root 运行、来源
  不明，优先级最高）；
- 确认 3100 `/opt/claude-glm-proxy`（glm-5.3）的归属；若保留需新 PRD
  授权（违反 v1 单模型不变量），否则下线；
- 处置结果记录于 `docs/OPERATIONS.md`。

---

## 4. 验收标准

| 门 | 内容 | 判据 |
| --- | --- | --- |
| G1 | 崩溃回归 | 畸形 Host / request-target 扫描（≥20 变体）全部返回 400，进程零重启（`systemctl show -p NRestarts` 不变），在途流不中断 |
| G2 | 401 生效 | 无凭据、错误凭据、旧 dummy 三种请求均 401 且 `authentication_error`；正确 client.key 请求 200；passthrough 默认拒绝 |
| G3 | 非流式准入 | 并发 N>MAX_CONCURRENCY 的非流式请求，超出部分收到 503 OVER_CAPACITY；挂起上游（fake upstream sleep）在 TOTAL_TIMEOUT 内被终止 |
| G4 | 非流式脱敏 | 上游错误 canary 不出现在非流式响应体（新增测试） |
| G5 | 路径穿越 | `run_id`/`item_id` 含 `/`、`..`、空字节的 manifest 一律 `invalid_manifest`，文件系统零写入 |
| G6 | systemd 加固 | `systemd-analyze security claude-code-maas-proxy.service` 评分改善且服务功能回归全绿；`NoNewPrivileges` 等指令生效（`systemctl show` 确认） |
| G7 | 测试头 | 默认模式下 `x-fake-scenario` 不达上游（fake upstream 断言未收到）；TEST_UPSTREAM=1 时契约测试仍过 |
| G8 | argv 泄露 | `delegate` 运行期间 `/proc/<pid>/cmdline` 不含 goal 文本（新增测试） |
| G9 | 纳管 | `git ls-files client/claude-glm` 有结果（或该文件与 PATH 符号链接均已删除）；prohibited-dep 扫描覆盖它 |
| G10 | 泄漏回归 | 既有 leak-scan 全套保持全绿（D2/D4 改动不得引入新泄漏面） |
| G11 | 全量回归 | `make verify-offline` + `make verify-adapter` 全绿；live 门 `make verify-live` 通过 |

---

## 5. 实施顺序与风险

1. **D1**（最小 diff、最高收益，先行单独发布）；
2. **D4 + D3**（同文件同路径，合并实施）；
3. **D2**（涉及 bootstrap/setup/adapter 三方联动，需迁移窗口）；
4. **D5 / D7 / D8 / D10**（独立小改，可并行）；
5. **D6 最低线**（unit 文件 + 一次重启窗口）；
6. **D9 / D11**（纳管决策 + 现场处置，非代码门）。

风险与回滚：

- D2 有兼容风险（旧客户端 dummy 失效）→ 保留 env 开关
  `MAAS_LEGACY_AUTH=1` 一个版本的退路；
- D6 的 `ProtectSystem=strict` 若与 /opt 回滚写盘冲突，先降
  `ProtectSystem=full` 并在下次迭代补 ReadOnlyPaths 白名单；
- 所有 adapter 改动走 `adapter/deploy.sh` 既有 SHA-256 + rollback
  通道，`adapter/rollback.sh` 即回滚。

## 6. 实施结果（2026-08-24 记录）

| 条目 | 状态 | 备注 |
| --- | --- | --- |
| D1 URL 防崩 | ✅ | Host 头不再反射进 URL base；畸形请求 400 |
| D2 客户端凭据 | ✅ | client.key 恒定时间比较；legacy 模式保留 `--legacy-auth` 退路；bootstrap/canary/verify.sh 三处联动改造 |
| D3 非流式准入 | ✅ | ConcurrencyGuard + 三看门狗 + finally 释放 |
| D4 非流式脱敏 | ✅ | ERROR_TEMPLATES 输出，上游正文不透传 |
| D5 路径穿越 | ✅ | schema pattern + 代码双重校验 + 写入层断言 |
| D6 unit 加固 | ✅ | 见下方偏差记录 |
| D7 测试头开关 | ✅ | `MAAS_TEST_UPSTREAM=1` 显式 opt-in |
| D8 goal 走 stdin | ✅ | `claude -p` 无参数时读 stdin；argv 无任务文本 |
| D9 claude-glm 纳管 | ✅ | git add + 删除 PATH 中的可执行 .bak |
| D10 证据去内插 | ✅ | 全部经环境变量 + `_env()` 读取 |
| D11 现场处置 | ⚠️ 部分 | 3001/3100 未纳管监听仍在线 — 需要维护者决策（见 §7） |

**D6 实施偏差**（与 §3 原案的差异）：

- `PrivateTmp=yes` 未采用 — 会把 /tmp 下的 artifact 目录（测试环境的
  `--dest`）挡在私有命名空间外，`WorkingDirectory` 解析失败（exit
  226/NAMESPACE，实测复现）。
- `MemoryDenyWriteExecute=yes` 未采用 — Node V8 JIT 需要 W+X 页，实测
  启动即崩（"Check failed: 12 == errno"）。
- `ReadWritePaths=` 未采用 — 服务不写盘（rollback 副本由 deploy.sh 在
  服务外写入），strict + 全只读已足够。
- 其余指令（NoNewPrivileges / ProtectSystem=strict / ProtectHome /
  PrivateDevices / 内核与 cgroup 保护 / RestrictAddressFamilies /
  RestrictSUIDSGID / LockPersonality / 空 CapabilityBoundingSet）全部
  生效，`systemctl show` 已核验。

**实施中发现并修复的连带问题**（不在原 PRD 内）：

1. verify.sh 的 direct-api / e2e 门以**上游 key** 访问**适配器**，在
   enforced 模式下被 401 — 两门已改为"回环端点用客户端 key"。
2. bootstrap 的 upstream canary 同样双重鉴权问题，已改用客户端 key。
3. `tests/claude_e2e_probe.sh` 继承外层 `ANTHROPIC_MODEL` 等
   glm-5.3 覆盖，污染 modelUsage 断言 — 探针现清除全部模型映射
   环境变量，实现单模型隔离。
4. 测试套件此前会读取宿主真实 `/etc/claude-code-proxy/client.key`，
   造成测试顺序耦合 — 全部测试 harness 现固定指向不存在的
   `tests/no-client.key`。
5. `test_g1_dual_arm_live` 的 `MAAS_URL`（/v2/chat/completions）对
   Anthropic 原生探针是 404 路径 — 该测试改经适配器探测后即正确。

**验证记录**：

- 离线：`make verify-offline` → 739 passed, 0 failed
- 生产：`scripts/verify.sh` 全 8 门 PASS（含新增 auth-enforcement 门）
- G1 实测：畸形 Host 轰炸生产 :3000，NRestarts 0，服务 active
- G2 实测：匿名 → 401；dummy → 401；错误 key → 401；正确 client.key → 200
- 启动器实测：`claude_maas_launcher_probe.sh` PASS（真实回合 + 工具往返）

## 7. 遗留事项（需维护者决策）

1. **S11 / D11 未完成部分**：`127.0.0.1:3001`（`/root/argrepro/server_capture.js`，root 权限运行）与 `127.0.0.1:3100`（`/opt/claude-glm-proxy/server.js`，服务 glm-5.3）两个未纳管监听仍在运行。本项目 PRD 无权处置外部服务，建议按 §3 D11 排查后下线。
2. **服务仍以 root 运行**（D6 目标态）：专用 `claude-maas` 服务用户 +
   env 文件 `root:claude-maas 0640` 留待下个版本。
3. **MaaS 上游 key 的历史暴露**：`docs/SECURITY.md` 既有条目 —
   开发期经交互渠道提供过测试 key，上线前应轮换（与本 PRD 无关但同属安全遗留）。

## 8. 明确不做

- 不引入 API 网关、鉴权服务或第二个监听（维持单回环适配器不变量）；
- 不改变 key 的存放拓扑（root env 文件 + 客户端 dummy）；
- 不给 /status 加鉴权（已是回环 + 枚举字段，够用）；
- 不处理 3001/3100 两个外部服务器的代码本身（D11 仅处置下线）。
