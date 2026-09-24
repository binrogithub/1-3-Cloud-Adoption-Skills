# E05 Log Investigator Runbook

E05 通过 Loki 的只读 `query_range` API 获取一个服务在限定时间窗口内的错误线索，并将已脱敏的证据交给 JiuwenSwarm。它不部署 Loki、不配置采集器、不修改上游项目，也不能修复服务。

## 配置

优先使用项目脚本探测 Loki 并生成受控配置。脚本从项目 `components.env` 的 `LOKI_HTTP_HOST`/`LOKI_HTTP_PORT` 读取本机地址，不把端口写死在代码中；也可以用 `LOKI_LOCAL_BASE_URL` 或 `--url` 覆盖。脚本不会写入任何凭据：

```bash
./scripts/configure-local-loki.sh
```

远程 Loki 或其他端口可显式指定：

```bash
./scripts/configure-local-loki.sh --url https://loki.example.internal
```

脚本只有在 `/ready` 返回 `ready` 后才写入 `config/local/loki.env`，文件权限为 `0600`，并采用原子替换。多租户 Loki 使用 `LOKI_TENANT_ID`，认证 Loki 使用 `LOKI_BEARER_TOKEN`；这些值不得进入 Git、任务描述、模型提示词或日志。

```bash
set -a
source config/local/loki.env
set +a
```

服务名称只允许字母、数字、点、下划线和连字符。查询窗口为 1–1440 分钟，结果上限为 1–200；调用者不能传入任意 LogQL。根因或溯源任务通过 E05→E04→E05 前置回溯→E06 条件联动入口执行，24 小时无异常时停止，不调用 OpenSearch。

## 查询证据

```bash
./scripts/loki-query.sh --service order-api --since-minutes 15 --limit 100
```

返回 JSON 中的 `query_ref`、`start_ns`、`end_ns` 和 `entries` 是诊断证据。`status: empty` 表示该范围内没有匹配条目，不表示服务健康。凭据类键值会以 `[REDACTED]` 返回。

## TUI 诊断

在已配置 E00 MaaS dotenv 的受控终端执行：

```bash
./scripts/log-investigate.sh --service order-api --since-minutes 15 --limit 100
```

包装器在 Loki 查询成功后才调用 JiuwenSwarm；它固定为只读诊断提示，日志中的文本不会成为工具指令。任何修复建议均需在后续 Rundeck/Ansible Epic 中由人工审批后执行。

每次成功查询会将**已脱敏**的证据保存为 `.runtime/log-investigator/<UTC 时间>-<query_ref>.json`，目录为 `0700`、文件为 `0600`。通过 `LOG_INVESTIGATION_EVIDENCE_DIR` 可指定受控的替代目录。原始 Loki HTTP 响应只存在于临时目录并会清理。

如果 MaaS 调用失败，或需要基于同一证据再次生成诊断，请重用已保存文件而不要重新查询移动时间窗口：

```bash
./scripts/log-investigate.sh --evidence-file .runtime/log-investigator/<file>.json
```

## 验证与故障处理

- Loki 返回空结果：检查服务标签、采集状态与时间窗口；输出必须保留 `empty` 状态。
- 本机端口由 `components.env` 的 `LOKI_HTTP_PORT` 决定；`3100` 若被 MaaS/Claude Code 代理占用，不能当作 Loki 地址。
- Loki 请求失败：检查网络、认证、租户 ID 和 Loki 可用性，不向 MaaS 发送失败响应体。
- 不要使用本脚本分析未获授权的跨租户或敏感日志。
