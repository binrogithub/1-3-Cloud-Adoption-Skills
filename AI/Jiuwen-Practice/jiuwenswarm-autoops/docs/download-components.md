# JiuwenSwarm 组件下载记录

记录时间：2026-09-10
目标平台：Linux x86_64 / amd64
默认安装目录：`/opt/JiuwenSwarm`

## 下载内容

| 能力 | 组件 | 版本 | 安装位置 |
| --- | --- | --- | --- |
| Observe | Prometheus | 3.14.0 | `/opt/JiuwenSwarm/components/prometheus/3.14.0/` |
| Observe | Grafana OSS | 13.1.0 | `/opt/JiuwenSwarm/components/grafana/13.1.0/` |
| Observe | Alertmanager | 0.34.0 | `/opt/JiuwenSwarm/components/alertmanager/0.34.0/` |
| Observe | Loki | 3.7.7 | `/opt/JiuwenSwarm/components/loki/3.7.7/` |
| Observe | OpenSearch | 3.8.0 | `/opt/JiuwenSwarm/components/opensearch/3.8.0/` |
| Action | Rundeck OSS RPM | 6.2.1.20260909 | `/opt/JiuwenSwarm/components/rundeck/6.2.1.20260909/` |
| Action | Ansible Core | 2.21.4 | `/opt/JiuwenSwarm/components/ansible/2.21.4/venv/` |
| Action | kubectl | v1.37.0 | `/opt/JiuwenSwarm/bin/kubectl` |

Reason / Plan / Skill 是 JiuwenSwarm 的编排层，负责观察上下文、诊断问题、制定计划并选择可执行 Skill；它不是需要单独下载的第三方组件。

## 下载方式

项目根目录的 [`download.sh`](../download.sh) 是后续安装入口。它调用 [`scripts/bootstrap-components.sh`](../scripts/bootstrap-components.sh)，从 [`components.env`](../components.env) 读取固定版本和校验值：

```bash
cd /root/Jiuwenswarm_AutoOps
./download.sh
```

自定义目标目录时：

```bash
JIUWENSWARM_ROOT=/opt/JiuwenSwarm-dev ./download.sh
```

脚本执行流程如下：

1. 检查 `curl`、`tar`、`unzip`、校验工具和 Python 3。
2. 创建目标目录、组件目录、运行时目录和 kubectl 目录。
3. 下载 Prometheus、Alertmanager、Grafana、Loki 和 OpenSearch 官方发行包。
4. 在解包前校验官方 SHA-256 或 SHA-512 值。
5. 下载 Rundeck RPM，并保留 RPM 供后续 Java 环境安装。
6. 创建独立 Python 虚拟环境，安装 `ansible-core`。
7. 下载 kubectl 及官方 `.sha256` 文件并校验。
8. 生成已解析版本文件和已安装入口文件的 SHA-256 清单。
9. 删除临时下载目录，不保留大型压缩包。

脚本可以重复执行。已经存在且可执行的同版本组件会跳过下载，但每次都会重新生成 `/opt/JiuwenSwarm/components.sha256` 和 `resolved-versions.env`。

## 校验与结果

下载完成后可以执行：

```bash
cd /opt/JiuwenSwarm
sha256sum --check components.sha256
source resolved-versions.env
components/prometheus/${PROMETHEUS_VERSION}/prometheus --version
components/alertmanager/${ALERTMANAGER_VERSION}/alertmanager --version
components/grafana/${GRAFANA_VERSION}/bin/grafana --version
components/loki/${LOKI_VERSION}/loki-linux-amd64 -version
components/ansible/${ANSIBLE_VERSION}/venv/bin/ansible --version
bin/kubectl version --client
rpm -qp components/rundeck/${RUNDECK_VERSION}/*.rpm
```

当前 Rundeck 只下载 RPM，没有写入系统。它后续需要 Java 17 或更高版本及 SSH 等运行依赖。OpenSearch 使用发行包自带的 JDK；正式启动前仍需准备数据目录、内存和 `vm.max_map_count`。脚本本身不会启动服务，也不会修改 `/etc`、systemd、Docker 或 Kubernetes 状态。

本机磁盘空间有限，因此 Ansible 使用 `ansible-core`，项目需要的额外 Collection 应按项目需求单独安装。OpenSearch 和 Grafana 解包后占用空间较大，执行前应确认目标磁盘有足够空间。

## 官方下载来源

- [Prometheus Downloads](https://prometheus.io/download/)
- [Grafana OSS Downloads](https://grafana.com/grafana/download)
- [Loki Releases](https://github.com/grafana/loki/releases)
- [OpenSearch Downloads](https://opensearch.org/downloads/)
- [Rundeck RPM Installation](https://docs.rundeck.com/docs/administration/install/linux-rpm.html)
- [Kubernetes kubectl Installation](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
