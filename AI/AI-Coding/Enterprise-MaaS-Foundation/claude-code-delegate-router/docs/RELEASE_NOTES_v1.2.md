# Release Notes — v1.2 (Security Hardening V1)

日期: 2026-08-24
PRD: docs/PRD_SECURITY_HARDENING_V1.md
范围: 安全修复与加固。无新功能，产品不变量（每个适配器实例单模型
单上游、无路由、无 fallback）不变——该不变量约束的是**实例基数**，
不是 `glm-5.2` 字面量，也不是全局单实例（PRD UPSTREAM_PROFILE_V1
D4 澄清；多 profile 由 window-check N1-G 逐实例把关）。

## 高危修复

### S1 — 畸形 Host 头导致适配器进程崩溃（DoS）

`new URL(req.url, \`http://${req.headers.host}\`)` 不在任何 try/catch
内，`Host: [::1:bad` 一个请求即可让进程退出、杀死全部在途流。修复后
Host 头不再反射进 URL 解析，畸形请求返回 400，进程零重启。
生产实测：畸形 Host 轰炸后 NRestarts=0。

### S2 — /v1/messages 实际无鉴权（真实 key 被代理给任意本地进程）

此前无凭据/dummy key 一律回落到 env 文件里的真实 MaaS key — 同机任
意进程可匿名消耗配额。现在：

- bootstrap 生成 32 字节随机 client key（`/etc/claude-code-proxy/client.key`，
  root:root 0600）并下发到客户端 `api-key`；
- 适配器 enforced 模式：匿名、错误 key、legacy dummy 一律
  `401 authentication_error`；正确 client key（恒定时间比较）→ 注入
  真实上游 key；
- `--legacy-auth` 保留旧行为作为迁移退路（不推荐）；
- client key 轮换 = 删除该文件后重跑 bootstrap。

## 中危修复

- **S3** 非流式路径纳入 ConcurrencyGuard + connect/idle/total 看门狗
  + finally 槽位释放（与流式路径同构）。满载返回 503 OVER_CAPACITY。
- **S4** 非流式路径不再透传上游错误正文，统一 ERROR_TEMPLATES 脱敏输出。
- **S5** workflow `run_id`/`item_id` 限定
  `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`（schema + 代码 + 写入层三重），
  路径穿越写被结构性拒绝。
- **S6** systemd unit 加固：NoNewPrivileges、ProtectSystem=strict、
  ProtectHome、PrivateDevices、内核/cgroup 保护、
  RestrictAddressFamilies、RestrictSUIDSGID、LockPersonality、空
  CapabilityBoundingSet。

## 低危修复

- **S7** `x-fake-scenario` 测试头仅在 `MAAS_TEST_UPSTREAM=1` 时转发上游。
- **S8** delegate 的 goal 文本经 stdin 传给 `claude -p`（argv 不再含任务
  文本，/proc/*/cmdline 不可见）。
- **S9** `client/claude-glm` 纳入 git 跟踪（进扫描与测试门）；
  `~/.local/bin/claude-glm.bak-*` 可执行备份已删除。
- **S10** verify.sh 证据生成改为环境变量传参，不再把不可信字符串内插
  进 Python 源。

## 已知限制与实施偏差

- `PrivateTmp` 与 `MemoryDenyWriteExecute` 未启用：前者破坏 /tmp 下的
  artifact 目录（exit 226/NAMESPACE，实测），后者使 Node V8 JIT 启动
  即崩（实测）。详见 PRD §6。
- 服务仍以 root 运行（专用服务用户 + 0640 env 属 D6 目标态，下版本）。

## v1.2 收口更新（PRD_RELEASE_V12，2026-08-24 晚）

- **N2 已处置**：`:3001` 的 root capture 进程已终止，端口关闭，无自启
  项；`/root/argrepro` 隔离为 `argrepro.quarantined-20260824`（证据保留）。
- **N1 决策为 A（下线）**（后被推翻：维护者于 UPSTREAM_PROFILE_V1 改判
  B——保留多 profile、逐监听合规校验；N1-G 已按 D10 改写）：当时执行了下线。
  `claude-glm-proxy.service` 停用并 disable，`/opt/claude-glm-proxy/` 删除；
  `client/claude-glm` 源码保留但标注为未支持配置。`make window-check`
  的 N1-G 门禁防止其（或同类克隆）再现。
- **N4 已修复**：非流式路径此前只更新 /status 不写 journald
  `request_end`（生产窗口实测 67% 请求对日志门禁不可见）。现于
  `proxyNonStreaming` 的 finally 发出与流式同构的 `request_end`
  （`path:"nonstream"`），/status 计数移入同一处（null 不计，顺带修掉
  `"null"` 脏键）。部署后实测等式恢复：`stop_reasons=5 == journald=5`，
  path 分布精确对应发压请求。
- **N5 窗口**：`make window-open` 打开 24h 浸泡窗（≥200 request_end），
  `make window-check` 随时评估；窗口届满且 N1-G/N2-G/N4-G 全绿后打
  `v1.2` 标（tag 说明含 LOOP_CONTINUITY_V1/V2 + SECURITY_HARDENING_V1）。

## 验证

- 离线全量：`make verify-offline` — 739 passed, 0 failed
- 生产发布门：`scripts/verify.sh` — 8/8 门 PASS（新增 auth-enforcement 门）
- 生产实测：匿名/dummy/错误 key → 401；正确 client key → 200；
  畸形 Host 轰炸零重启；launcher 真实回合 + 工具往返 PASS

## 升级指引

```bash
# 幂等重跑 bootstrap：生成 client.key、更新 env、下发客户端 key、
# 写入加固 unit、重启服务并过 verify 硬门（含新的 401 检查）
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

如需临时保留旧的开放行为（例如另有未迁移的本地客户端依赖匿名访问）：
加 `--legacy-auth`。迁移完成后请去掉该旗标。

## v1.2 收口更新（PRD_RELEASE_V13，2026-08-25）

- **S1**：N4-G 的旧断言建立在「两侧计数同步重置」的错误前提上，含失败请求
  的窗口恒红（实测 124 vs 125，差值恰为失败数）。已改为恒等式
  `sum(stop_reasons) + null-stop == request_end`——零失败与任意失败数均成立，
  漏记请求仍会 FAIL。
- **S3-a**：工具参数重试从 1 次加到 2 次（`MAAS_TOOL_ARG_RETRIES`，默认 2）。
  第 1 次成功率 ~92%（29/31），第二次独立尝试把残余 ~8% 压到 ~0.7%。
- **S3a-G2**：重试挂起期触发 total watchdog 时，槽位归零、reaper 静默、进程
  存活；为此给 SSE 写路径加了 write-after-end 守卫（否则会崩溃进程）。
- **S3-b**：重试提示词增加「字符串内双引号必须转义」——对准 13/13 观测指纹
  （括号平衡、引号奇数、反斜杠恒 0）。提示词只教规则，绝不回放畸形载荷。
- **S3-c**：交互式会话的残余错误需人工 `continue`（已知且有意的边界，见
  OPERATIONS）。
- **S4**：`request_end.repair.tool_name` 上线，服务端可直接回答归因问题。
