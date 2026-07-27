# Teradata to Huawei Cloud DWS Migration Demo

本 demo 用于在本机快速模拟一个金融行业 Teradata 源端分析与报表工作负载，并为后续迁移到华为云 DWS 做准备。

## 重要说明

Teradata 没有开源数据库集群发行版。Teradata Vantage Express 是免费的、可完整运行的 Vantage VM 镜像，但不是开源软件，也不是 Docker 原生集群。本项目因此采用开源 Citus/PostgreSQL 搭建最小 MPP SQL 集群来模拟源端 Teradata 分析负载：

- `tdsim-coordinator`: SQL 入口，映射 Teradata 源端访问入口。
- `tdsim-worker1`、`tdsim-worker2`: 两个 worker 节点，模拟 MPP 数据分布。
- `finance_dw`: 金融数仓 schema。
- `reports`: 报表视图 schema。

后续如果需要接入真实 Teradata Vantage Express，只需要替换连接与导出层，保留金融模型、报表口径和迁移评估脚本。

## 快速启动

```bash
./scripts/start_source_cluster.sh
./scripts/init_finance_demo.sh
./scripts/run_reports.sh
```

默认连接信息：

- Host: `127.0.0.1`
- Port: `15432`
- Database: `tdsim`
- User: `tdadmin`
- Password: `tdadmin`

连接示例：

```bash
docker exec -it tdsim-coordinator psql -U tdadmin -d tdsim
```

## 报表输出

`./scripts/run_reports.sh` 会生成 CSV 文件到 `reports/output/`：

- `branch_kpi.csv`: 分行经营指标。
- `customer_profitability.csv`: 客户月度贡献。
- `liquidity_gap.csv`: 产品与币种流动性敞口。
- `loan_risk_snapshot.csv`: 贷款风险与预期损失。
- `suspicious_activity.csv`: 可疑交易监控。

## 停止与清理

停止容器但保留数据：

```bash
./scripts/stop_source_cluster.sh
```

删除容器、网络和数据卷：

```bash
./scripts/destroy_source_cluster.sh
```

## 创建华为云 DWS 最小集群

创建真实云上资源会产生费用。脚本默认在 `la-south-2`、project `89a76cc1484440b38810ecb9e3b5c0d7` 创建 3 节点 DWS 集群：

```bash
export CLOUD_SDK_AK="$AK"
export CLOUD_SDK_SK="$SK"
./scripts/create_huawei_dws_min_cluster.sh
```

默认集群名为 `dws-finance-demo-min3`。脚本会自动查询可用 DWS 规格和 AZ，优先复用同名 demo VPC、子网、安全组，不存在时创建。若未设置 `DWS_DB_PASSWORD`，脚本会生成数据库管理员密码并保存到本机 `.secrets/dws-finance-demo-min3.env`，权限为 `0600`。

常用覆盖参数：

```bash
./scripts/create_huawei_dws_min_cluster.sh \
  --cluster-name dws-finance-demo-min3 \
  --node-count 3 \
  --num-cn 2
```

## 迁移 Teradata 数据和分析过程到 DWS

配置目标 DWS 连接：

```bash
./scripts/configure_dws_env.sh
vi config/dws.env
```

执行端到端迁移：

```bash
./scripts/migrate_td_to_dws.sh
```

迁移流程包括：

- 从源端导出金融数仓表到 `data/export/`。
- 在 DWS 创建 `finance_dw` 和 `reports` schema。
- 将 CSV 装载到 DWS。
- 在 DWS 创建并运行分行 KPI、客户贡献、流动性敞口、贷款风险、可疑交易报表。
- 校验源端和 DWS 的行数与报表结果。

详细说明见 [docs/teradata_to_dws_migration_scripts.md](/root/Teradata-migration/docs/teradata_to_dws_migration_scripts.md)。

扫描 Teradata SQL/BTEQ/TPT 兼容性风险：

```bash
./scripts/scan_teradata_compatibility.py /path/to/teradata/sql
```

输出：

- `reports/teradata_compatibility_scan.csv`
- `reports/teradata_compatibility_scan.md`

生产装载建议使用 OBS 并行路径：

```bash
cp config/obs.env.example config/obs.env
vi config/obs.env
./scripts/prepare_obs_parallel_load.sh
```

这会上传 `data/export/*.csv` 到 OBS，并生成 `sql/dws/08_load_from_obs.generated.sql` 装载模板。执行前按 DWS 版本和安全策略复核。详见 [docs/obs_parallel_load.md](/root/Teradata-migration/docs/obs_parallel_load.md)。

## DWS 报表优化

迁移完成后可以创建列存汇总 mart，减少高频报表每次扫描事实表的成本：

```bash
./scripts/optimize_dws.sh
./scripts/run_dws_reports_optimized.sh
./scripts/validate_dws_optimized_reports.sh
```

可选执行基准对比：

```bash
./scripts/benchmark_dws_reports.sh base
./scripts/benchmark_dws_reports.sh optimized
```

继续深化优化：

```bash
./scripts/create_partitioned_facts.sh
./scripts/check_dws_skew.sh
./scripts/refresh_dws_marts_incremental.sh 202506 2025-06-30
```

这些脚本分别用于创建分区事实表副本、检查哈希分布倾斜、按月份/快照日增量刷新报表 mart。

优化记录见 [docs/dws_optimization_notes.md](/root/Teradata-migration/docs/dws_optimization_notes.md)。

## 迁移报告和资源管理

生成交付报告：

```bash
./scripts/generate_migration_report.sh
```

报告输出到 `reports/migration_report.md`。

管理 DWS 集群：

```bash
./scripts/manage_dws_cluster.sh status
./scripts/manage_dws_cluster.sh stop
./scripts/manage_dws_cluster.sh start
```

删除集群需要显式确认：

```bash
./scripts/manage_dws_cluster.sh delete --yes --confirm-name dws-finance-demo-min3
```

## 项目结构

```text
scripts/              集群生命周期、初始化、报表导出脚本
sql/01_schema/        金融数仓表结构和 Citus 分布定义
sql/02_data/          样例金融数据生成
sql/03_reports/       报表视图与查询
sql/dws/              DWS 建表、报表视图和 CSV 装载 SQL
data/control/         迁移表顺序控制文件
docs/                 迁移说明和 Teradata 到 DWS 后续步骤
reports/output/       报表 CSV 输出目录
```
