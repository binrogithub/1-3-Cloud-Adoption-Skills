# AutoOps Release 环境与数据源接入

这份指南用于隔离验收环境。它只配置 JiuwenSwarm AutoOps 胶水代码，不安装或修改 JiuwenSwarm、TUI、Loki、Prometheus、OpenSearch、Rundeck 或 Ansible 源码。

## 环境边界

- runtime：`/opt/Jiuwenswarm_AutoOps`
- 客户配置：`/etc/jiuwenswarm-autoops`
- 任务、事件和 watcher 状态：`/var/lib/jiuwenswarm-autoops`
- fixture：默认位于 `/var/tmp/jiuwenswarm-autoops-fixtures/fixture-<run-id>`
- 真正的 API key、token、密码和 kubeconfig 由外部环境或客户配置提供，不写进制品和 fixture manifest。

## 支持矩阵

| 能力/平台 | 当前声明 | 必需前置 |
|---|---|---|
| Linux amd64、Python 3.9+、systemd | 支持候选验收 | 服务账号可访问的 Python、systemd-journal 组和持久状态目录 |
| 原生 JiuwenSwarm TUI | 已接入，需候选制品复验 | JiuwenSwarm backend/TUI 已由客户安装并可用；TUI 不负责安装组件 |
| 本机 Linux journal | 支持本机只读调查 | service account 可读取 journal；权限错误必须报告为 unavailable |
| Loki / Prometheus / OpenSearch | 按数据源分别声明 | URL、身份、健康和指定应用窗口数据都通过预检；缺可选源只能 DEGRADED |
| Rundeck / Ansible | 支持已登记 Job | allowlist、目标绑定、外部凭据和独立业务探针通过验收 |
| Kubernetes / 远端主机 | 仅支持已登记并单独验收的目标 | context、namespace、工作负载和零副作用/恢复证据齐全 |
| Windows、无 systemd 主机、多租户 | 未声明支持 | 需要单独产品设计和验收，不以本 Release 的 Linux 证据替代 |

## 版本与环境记录

干净主机验收时把以下命令输出写入 release evidence 的环境清单，并只记录版本和路径，不记录密钥值：

```bash
uname -srm
python3 --version
systemd --version | head -1
jiuwenswarm-tui --version || true
git -C /root/src/jiuwenswarm rev-parse HEAD 2>/dev/null || true
cat /opt/Jiuwenswarm_AutoOps/autoops-install-manifest.json
```

实际环境清单必须同时记录制品 SHA、配置 SHA、启用的数据源、服务账号和组件探测结果。开发 checkout、历史 commit 和没有制品 SHA 的运行只能作为开发证据。

安装完成不代表组件可用。按以下顺序检查：

1. **下载**：组件文件存在，版本和 SHA-256 与 `components.env` 一致。
2. **部署**：组件进程或服务正在运行，监听地址属于目标环境。
3. **接入**：AutoOps 环境文件有正确端点，身份探测能识别对应组件。
4. **有数据**：针对指定应用、标签、索引和窗口的原生查询命中数据，并记录 coverage；身份探测为 READY 不能代替有数据。

## 预检

E01/E02 的 Rundeck 与 Job 是必需项。若本轮还要求数据源，把它们列入必需清单；可选源单独列出，缺失时只降级：

```bash
export RUNDECK_BASE_URL=https://rundeck.example.internal
export RUNDECK_API_TOKEN='由外部 secret 注入'
export RUNDECK_PROJECT=autoops
export RUNDECK_HOST_BASIC_CHECK_JOB_ID=<只读 Job ID>
export RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID=<Ansible Job ID>
export AUTOOPS_PREFLIGHT_REQUIRED_SOURCES=loki
export AUTOOPS_PREFLIGHT_OPTIONAL_SOURCES=prometheus,opensearch

scripts/autoops-e2e-preflight.sh
```

返回结果会分别列出 `downloaded`、`deployed`、`configured`、`identity_valid` 和 `data_available`。`data_available=UNKNOWN` 必须继续执行针对应用和窗口的原生查询，不能判为正常。必需数据源缺失时退出码为 3；可选数据源缺失时返回 `DEGRADED` 且退出码为 0。

## 隔离观测夹具

```bash
run_id=release-001
python3 scripts/release-fixtures.py setup --run-id "$run_id"
python3 scripts/release-fixtures.py inject --run-id "$run_id" --kind anomaly
python3 scripts/release-fixtures.py inject --run-id "$run_id" --kind change
python3 scripts/release-fixtures.py check --run-id "$run_id"
python3 scripts/release-fixtures.py cleanup --run-id "$run_id"
```

夹具的 `ground-truth.json` 保存应用名、service 标签、Prometheus job、OpenSearch index、异常和变更真值。只有把它接入实际采集、scrape 和事件写入管道后，才能进行三源原生查询验收；本地 fixture 检查不替代真实证据。

## 清理与持久目录

每次运行必须使用唯一 `run_id`，只清理对应 fixture 目录。客户配置和 `/var/lib/jiuwenswarm-autoops` 状态不能作为临时资源删除。升级前使用 `autoops-runtime-backup.py` 做一致备份；恢复前停止 watcher、dispatch 和 Alertmanager 写入者。

首次日志任务的最短 walkthrough：安装 → 填客户配置 → 运行 `scripts/autoops-e2e-preflight.sh` → 启动 `Jiuwen_autoops_tui` → 输入“排查本机 Linux 日志” → 通过任务 ID 查询状态和证据。配置缺失时按命令输出补齐后重新预检，不要把 `UNAVAILABLE` 当作无异常。
