# JiuwenSwarm AutoOps 安装

安装器只发布 AutoOps 胶水代码的配置和生命周期单元，不修改 JiuwenSwarm、TUI、Loki、Prometheus、OpenSearch、Rundeck 或 Ansible 源码，也不会写入 MaaS 密钥。

在项目目录执行：

```bash
cd /root/Jiuwenswarm_AutoOps
python3 scripts/install-autoops-runtime.py
python3 scripts/install-jiuwenswarm-autoops-skills.py
```

也可以使用统一入口：

```bash
scripts/jiuwenswarm-autoops-tui.sh --install-only
```

Skill 注册默认使用 `preserve-existing`，只更新 AutoOps 路由和 TUI/SwarmFlow 设置，不改客户已有权限。隔离测试主机若明确需要项目既有的全权限测试策略，显式指定：

```bash
python3 scripts/install-jiuwenswarm-autoops-skills.py \
  --deployment-mode full-access-test
```

部署模式定义见 [`config/release/deployment-modes.json`](../config/release/deployment-modes.json)；重复安装不会隐式切换模式。

默认发布位置如下：

| 内容 | 位置 |
|---|---|
| 受管运行时（脚本、配置、角色和工作流） | `/opt/Jiuwenswarm_AutoOps` |
| 客户配置模板 | `/etc/jiuwenswarm-autoops` |
| watcher、事件和任务状态 | `/var/lib/jiuwenswarm-autoops` |
| systemd 单元 | `/etc/systemd/system` |
| 安装清单 | `/opt/Jiuwenswarm_AutoOps/autoops-install-manifest.json` |

安装清单使用 v2：包含实例 ID、四类根目录、源配置位置、受管文件 SHA-256、文件 mode/uid/gid 和迁移来源。清单只保存元数据和摘要，不保存 MaaS、Loki、OpenSearch 或其他凭据；`preserved` 仅表示文件被保留，不代表服务健康。旧 v1 清单会在重装时迁移，未知清单或运行时配置版本会明确失败。

安装器具备以下约束：

- 首次安装创建角色、ServiceProfile、MonitoringPolicy、能力目录、验证配置、客户配置模板、状态目录和 systemd 单元。
- 重复安装会刷新 `/opt/Jiuwenswarm_AutoOps` 内项目管理的脚本、工作流和默认配置；客户配置模板、事件文件和非托管 systemd 单元不会覆盖。
- 由 `# Managed by JiuwenSwarm AutoOps installer` 标记的单元可在项目模板变化后更新。
- 默认只落盘配置，不自动 `systemctl enable`、`start` 或执行任何运维动作。
- Skill 安装器按实际 checkout 路径渲染项目命令；将项目安装到 `/opt` 或其他目录时，Skill/bootstrap 不再残留 `/root/Jiuwenswarm_AutoOps` 路径。
- 默认服务身份是 `jiuwenswarm-autoops:jiuwenswarm-autoops`。在 root 主机且 systemd 单元发布到 `/etc/systemd/system` 时，安装器会创建这个低权限系统账号，并把仅限 AutoOps 的状态目录交给它；使用 `--no-create-service-account` 可关闭此行为。非默认 systemd 目录常用于镜像构建和测试，安装器不会修改宿主机账号。
- 默认服务账号会加入 `systemd-journal` 组，使 E05 可只读访问本机 journal；安装器会在缺少该系统组或无法配置成员资格时明确失败。
- 安装器会探测 `components.env` 声明的本机 Loki、Prometheus 和 OpenSearch 健康端点，并仅在对应 `/etc/jiuwenswarm-autoops/*.env` 缺失时生成无凭据配置。已有客户配置不会覆盖；可用 `--no-auto-configure-local-observability` 关闭探测。`Jiuwen_autoops_tui` 的默认启动流程会执行此安装步骤。
- 安装器保留 `/etc/jiuwenswarm-autoops` 的管理员所有权，并将已声明的观测、MaaS 和预授权配置文件授予服务组只读权限；目录对该组仅开放遍历权限。其他客户文件不会变更。
- 安装器会选择服务账号可访问的 Python 3.9+ 解释器并写入 systemd 单元。若宿主机的 `python3` 指向 `/root` 下的用户环境，可用 `--python-executable` 指定系统解释器。

非默认目录可用于预发布或容器镜像构建：

```bash
python3 scripts/install-autoops-runtime.py \
  --install-root /opt/Jiuwenswarm_AutoOps \
  --config-root /etc/jiuwenswarm-autoops \
  --state-root /var/lib/jiuwenswarm-autoops \
  --systemd-root /etc/systemd/system
```

安装后仍需按客户环境填写 MaaS、Loki、Prometheus、OpenSearch 和 Rundeck 的环境变量，并单独完成连通性检查。运行时默认从 `/etc/jiuwenswarm-autoops/{prometheus,opensearch,loki}.env` 读取已安装的观测配置；开发或预发布环境可以设置 `JIUWENSWARM_AUTOOPS_CONFIG_DIR` 指向另一目录。进程环境变量优先级最高，适合临时覆盖端点或凭据。预授权策略默认是禁用状态；没有明确发布的策略时，ProjectManager 只调查、等待授权或升级，不执行写操作。

E2E 预检会把组件状态分为下载、部署、接入和有数据。用 `AUTOOPS_PREFLIGHT_REQUIRED_SOURCES` 声明本次必须可用的 Loki、Prometheus 或 OpenSearch，用 `AUTOOPS_PREFLIGHT_OPTIONAL_SOURCES` 声明允许降级的源；身份探测 READY 不等同于指定应用已有数据，完整流程仍需执行原生查询并记录 coverage。详细隔离环境和 fixture 流程见 [release-environment.md](release-environment.md)。

升级前可为单个实例创建一致备份。该工具使用 SQLite backup API 保存已提交的任务、事件和外部 execution ID，不直接复制活跃数据库的 `-wal`/`-shm` 文件；恢复前必须停止 AutoOps 写入者，并且恢复不会重放外部动作：

```bash
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-runtime-backup.py create \
  --output /var/backups/jiuwenswarm-autoops/$(date +%Y%m%d-%H%M%S) \
  --install-root /opt/Jiuwenswarm_AutoOps \
  --config-root /etc/jiuwenswarm-autoops \
  --state-root /var/lib/jiuwenswarm-autoops \
  --systemd-root /etc/systemd/system

# 停止 watcher/dispatch/Alertmanager 后再恢复
python3 /opt/Jiuwenswarm_AutoOps/scripts/autoops-runtime-backup.py restore \
  --backup /var/backups/jiuwenswarm-autoops/<备份目录> --assume-stopped
```

备份目录包含 `backup-manifest.json`，其中记录摘要、权限和恢复策略；恢复会校验清单及每个文件 hash。账号创建、第三方业务动作和已提交的外部任务不会被自动撤销或再次提交。

如果客户使用 E03，先运行只读 Kubernetes 依赖检查：

```bash
python3 scripts/k8s-environment-check.py --cluster autoops-development
```

只有检查返回 `status=READY`，才继续审核 `config/kubernetes/workloads.json` 中的 context、namespace、工作负载和固定恢复 Job。安装器不会自动启用集群，也不会生成或复制 kubeconfig。

需要验证恢复链路时使用：

```bash
python3 scripts/k8s-environment-check.py \
  --cluster autoops-development --require-recovery
```

Rundeck Job 模板由安装器发布到 `config/rundeck/e03-k8s-restore-order-api-job.json`，需按客户 context、kubeconfig 路径和 workload 审核后手动导入；安装器不会自动导入或启用写 Job。

如果本机已经运行项目安装的 Loki，可执行下面的命令将实际监听地址写入 AutoOps 配置。脚本会先检查 `/ready`，配置文件权限为 `0600`，不会生成凭据：

```bash
scripts/configure-local-loki.sh
```

Loki 的本机主机和端口由项目 `components.env` 中的 `LOKI_HTTP_HOST`/`LOKI_HTTP_PORT` 决定；当前配置解析为 `127.0.0.1:3101`，`3100` 是 MaaS/Claude Code 代理端口。Loki 服务健康不代表已有日志，仍需配置 Alloy、Promtail 或其他现有采集管道向 Loki 写入带 `service` 标签的日志。

## 长稳验收

用加速夹具先验证多个 watcher 周期的状态和水位连续性：

```bash
python3 scripts/autoops-long-stability.py \
  --policy config/monitoring/autoops-demo-watch.json \
  --events-file /var/lib/jiuwenswarm-autoops/events.jsonl \
  --state-dir /var/lib/jiuwenswarm-autoops/watch \
  --state-db /var/lib/jiuwenswarm-autoops/autoops-state.db \
  --cycles 3 --interval-seconds 0 \
  --evidence /var/lib/jiuwenswarm-autoops/stability-evidence.json
```

`--cycles` 只用于快速夹具验证，输出会标记 `mode=accelerated`。正式 24 小时验收省略 `--cycles`，保留默认 `--duration-seconds 86400` 和现场的 MaaS、数据源故障、重复告警、TUI 离线及后端重启证据；加速测试不会计入 24 小时通过结论。运行中的每轮 checkpoint 写入 `<state-dir>/stability-progress.jsonl`，最终结果才写入 `--evidence` 指定文件。
