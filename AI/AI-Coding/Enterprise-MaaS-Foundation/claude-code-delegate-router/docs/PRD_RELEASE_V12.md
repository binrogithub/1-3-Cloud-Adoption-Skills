# PRD — Release V12（v1.2 收口）

状态: 实施中（N2 ✅ / N4 ✅ 已部署 / N1 决策=A 已拍板待执行 / N5 窗口待开 / N3 待打标）
作者: Claude（独立复核，非采信实施方自述）
日期: 2026-08-24
被复核构建: `30902523d6d1012846c4…`（`f33df3d` SECURITY_HARDENING_V1）
前序: PRD_SECURITY_HARDENING_V1 / PRD_LOOP_CONTINUITY_V2 / PRD_RELEASE_V11

---

## 0. 结论

**代码本身达到发布标准，但项目不能关闭。** 剩下 5 项收口，其中 2 项是
主机上**正在运行的安全暴露**，1 项是「线上跑的代码没有版本号」。

---

## 1. 我独立验证通过的部分

以下均为我自己执行，不是转述：

| 项 | 我的验证方式 | 结果 |
|---|---|---|
| 离线全量 | 自跑 `make verify-offline` 480s | **739 passed / 0 failed** |
| 生产发布门 | 自跑 `scripts/verify.sh`（key 由 env 文件经管道注入，不进 argv） | **全门 PASS**（含新增 auth-enforcement 门） |
| S1 崩溃防护 | 连发 5 个 `Host: [::1:bad` 畸形请求 | `NRestarts` 0 → **0**，进程存活 |
| S2 鉴权 | 匿名 / 错误 key / 正确 client key 三组实打 | **401 / 401 / 200** |
| S2 鉴别力 | 反向门禁：删掉 `getAuthKey` 的 enforcement 块后重跑 | **3 条安全门 FAILED** — 有鉴别力 |
| S6 systemd 加固 | `systemctl show` 逐项读取 | NoNewPrivileges / ProtectSystem=strict / ProtectHome / PrivateDevices / RestrictSUIDSGID / 空 CapabilityBoundingSet **均已生效** |
| S9 工件纳管 | `git ls-files client/` | `client/claude-glm` **已跟踪** |
| 部署一致性 | `/opt` 与 repo 的 server.js SHA | **一致**（`30902523d6d1012846c4…`） |

`RELEASE_NOTES_v1.2.md` 把两个未纳管监听、`PrivateTmp`/`MemoryDenyWriteExecute`
未启用、服务仍以 root 运行等偏差都写进了「已知限制」——**披露是诚实的**，
本 PRD 不重复指摘，只处理仍需动作的部分。

---

## 2. 阻塞项

### N1 (P0) — `127.0.0.1:3100` 跑着加固前的构建，S2 漏洞在同机活着

```
/opt/claude-glm-proxy/server.js       b8c7069b5a2c1ee5…   ← 加固前
/opt/claude-code-maas-proxy/server.js 30902523d6d10128…   ← 已加固
```

实测：向 3100 出示哑元 `maas-local-proxy` 返回 **200**（同样的请求打 3000 是 401）。
即**同机任意本地进程可匿名调用它消耗智谱配额** —— 正是 S2 描述的漏洞，
在 S2 被判定「已修复」的同一台主机上仍然可利用。

此外它违反 `PRD_SECURITY_HARDENING_V1 §8` 明列的产品不变量
「不引入第二个监听（维持单回环适配器）」，也违反「单模型 glm-5.2」不变量。

**这不是一个纯技术修复，是一次口径决策，必须由维护者拍板：**

- **选项 A —— 下线**：停用并禁用 `claude-glm-proxy.service`，删除
  `/opt/claude-glm-proxy/`，保留 `client/claude-glm` 但在文档标注为未支持配置。
  维持现有不变量不变。
- **选项 B —— 纳管**：显式修订不变量为「每个 profile 一个回环监听、
  每个 profile 一个模型」，然后把 glm profile 补齐到与 maas 同等安全水位：
  部署 `30902523…` 构建、生成独立 `client.key`、同步更新
  `~/.config/claude-glm/api-key`、加同款 systemd 加固指令、纳入 `verify.sh`。

**在 A/B 之一完成前不得打 v1.2 标。** 选 B 的额外门禁见 §3 的 N1-G。

### N2 (P0) — `127.0.0.1:3001` root 运行的适配器克隆仍在监听

```
pid 772474  node server_capture.js   （/root/argrepro/，目录创建于 2026-08-24 01:23）
```

时间戳落在 LOOP_CONTINUITY_V1 那轮排查窗口内（01:25 部署），
特征是当时用于抓 tool-args 报文的调试脚本，**排查结束后没有下线**。
root 权限、回环监听、不受任何门禁与架构契约约束。

处置：确认来源后停止进程、删除或移出 PATH 与自启，并在 release notes
的「已知限制」中把该条从「待维护者处置」改为「已处置」。

### N3 (P1) — 线上跑的代码没有 tag

```
v1.1  →  5a5dc28
线上  →  f33df3d (30902523…)
```

两者之间隔着 4 个 commit：`c7a5a43`(L1-A/L1-B 修复静默 end_turn 的 P0)、
`9f7b331`、`158925b`(L2/L4)、`1251e7a`、`f33df3d`(全部安全修复)。

后果是**已发布的 v1.1 带着 loop-continuity 的 P0**（release notes 已注明
「Fixed post-v1.1」），而修好这个 P0 的代码和全部安全修复**没有任何版本号**。
「已发布的东西」与「正在跑的东西」不是同一份代码，回滚与追溯都没有锚点。

处置：完成 N1/N2/N4 后打 `v1.2`，tag 说明必须写明它同时包含
LOOP_CONTINUITY_V1/V2 与 SECURITY_HARDENING_V1 两批修复。

### N4 (P1) — 非流式路径计入 /status 却不写 `request_end`，journald 门禁系统性少计

`adapter/server.js:690`（在 `proxyNonStreaming` 内，函数起于 `:640`）递增
`stopReasonCounts`，但全文件唯一的 `request_end` 结构化日志在 `:1301`，
只在流式路径上。

本窗口实测对照：

```
/status.stop_reasons 合计   59   (end_turn 38 + tool_use 19 + max_tokens 2)
journald 内 request_end     44   (其中带 stop_reason 的 42)
差            17 个请求（29%）在 journald 中完全不可见
```

已排除 journald 限流：`RateLimitBurst` 为默认 10000，窗口内无 `Suppressed` 记录。

后果：项目所有基于 journald 计数的发布判据 ——
`窗口内 request_end ≥ 200`、降级率、`protocol error 自愈率 ≥ 32%` ——
**都在少计，且对非流式路径的失败完全盲视**。D3 把非流式路径纳入了生命周期
控制，却没有同步补上它的结构化日志。

修复：在非流式路径的终止处发出与流式同构的 `request_end`
（至少含 `request_id` / `state` / `error_code` / `duration_ms` /
`stop_reason` / `outcome`），并加门禁 N4-G。

### N5 (P2) — 当前构建没有浸泡窗口

```
进程启动    2026-08-24 09:27:47      已跑 10.0h
窗口内请求  59（/status 口径）
```

历史发布判据（V11 §3.7/§3.8）要求 24h + `request_end ≥ 200`。
本次改动包含 **D2 鉴权**这一高爆炸半径路径，PRD 自己也标注了
「旧客户端 dummy 失效」的兼容风险并保留了 `--legacy-auth` 退路。
59 个请求不足以证明兼容性。生产已出现 1 次 `MAAS_AUTH_REJECTED`
（我实测确认该拒绝是正确行为，非误伤），但样本量太小。

处置：N1/N2/N4 修复完成后重开 24h 窗口，判据用
`request_end ≥ 200`（以修好后的口径计） + `MAAS_AUTH_REJECTED` 全部可解释。

---

## 3. 验收门禁

沿用项目既有规矩：**每条门禁必须附「回退修复后该门禁 FAIL」的证据**。

| 门 | 断言 | 反向用例 |
|---|---|---|
| N1-G（选 B 时） | glm 实例：哑元 key → 401；正确 client key → 200；`sha256(/opt/claude-glm-proxy/server.js)` == repo | 部署回旧构建后必须 FAIL |
| N1-G（选 A 时） | 主机上除 `:3000` 外无本项目派生的监听 | 重新启用 glm 服务后必须 FAIL |
| N2-G | `ss -tlnp` 中不存在 `:3001`；`/root/argrepro` 无自启项 | 重新拉起该进程后必须 FAIL |
| N4-G | 非流式请求（`stream:false`）后，journald 出现对应 `request_end`；且 `/status.stop_reasons` 合计 == journald 内 `request_end` 计数 | 回退非流式日志后必须 FAIL（当前差 17，天然为红） |
| N5-G | 新窗口 24h 届满、`request_end ≥ 200`、`MAAS_AUTH_REJECTED` 每条可解释 | — （纯时间门） |

N4-G 当前值为「59 vs 44」，**修复前即为红，无需另造反向用例**。

已由我独立验证具备鉴别力、无需重做的：**S2 鉴权门**（回退后 3 条 FAILED）。

---

## 4. 实施记录（2026-08-24 晚）

| 项 | 状态 | 证据 |
|---|---|---|
| N2 | ✅ 已处置 | pid 772474 已终止；`:3001` CLOSED；cron/systemd 自启 0 项；`/root/argrepro` 移至 `argrepro.quarantined-20260824`（证据保留） |
| N1 | 决策 **A**（维护者 2026-08-24 拍板） | 执行顺序刻意放在最后：本会话（复核与实施所在的 Claude 进程）自身依赖 3100（`ANTHROPIC_BASE_URL=127.0.0.1:3100`），先完成全部 3000 通道上的工作再下线 |
| N4 | ✅ 已修复并部署 | `proxyNonStreaming` 的 finally 补齐 `request_end`（`path:"nonstream"`，含 request_id/state/error_code/stop_reason/duration_ms/outcome）；/status 计数移入同一 finally 并与流式同规则（null 不计）——单一事实源；garbage-200-body 由无日志 catch 改为 `MAAS_STREAM_PROTOCOL` 记录。部署后实测：发 4 非流式 + 1 流式 → `stop_reasons=5 == journald=5`，path 分布 `{'nonstream':4,'stream':1}` 精确对应 |
| N5 | 窗口待开 | `make window-open` 写 `/etc/claude-code-proxy/window-v12.json`；`make window-check` 评 N1-G/N2-G/N4-G 并报告窗口进度 |
| N3 | 待打标 | 上述全绿 + 窗口届满后 `git tag -a v1.2`，说明须包含 LOOP_CONTINUITY_V1/V2 + SECURITY_HARDENING_V1 两批 |

**N4 实施中的额外发现**：`stopReasonCounts` 原实现用 `ctrl.finishReason`
直接作键，`finishReason === null` 时会在 `/status` JSON 里造出 `"null": N`
脏键。已随本修复改为与流式一致的 null 守卫，并有回归测试钉死。

**门禁鉴别力验证**（PRD §3 要求的反向证据）：

- N4-G 修复前天然为红（复测口径 **69 vs 23**，67% 不可见，比 §2 记录的
  29% 更严重——非流式占比在窗口后半段上升）；
- N1-G 在 3100 仍在线时实测 FAIL（`project-derived listeners still up:
  :3100(/usr/bin/node /opt/claude-glm-proxy/server.js)`），`tests/
  test_window_check_v12.py` 用真实 loopback node 监听复现该反向用例；
- N2-G 在 3001 下线后 PASS（下线前该端口即 §2 实测暴露源）。

## 5. 建议顺序（原案，保留）

1. **N2**（几分钟，纯下线动作，风险最低）
2. **N1** 维护者先在 A/B 之间拍板，再执行
3. **N4**（一处日志补齐 + 一条门禁）
4. 重开 24h 窗口（**N5**）
5. 窗口届满全绿 → 打 **v1.2**（**N3**）

N1 与 N2 是主机上正在生效的安全暴露，优先级高于任何文档或版本号工作。
