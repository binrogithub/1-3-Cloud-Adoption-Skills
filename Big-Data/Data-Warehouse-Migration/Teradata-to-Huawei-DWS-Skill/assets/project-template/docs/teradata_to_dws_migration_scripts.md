# Teradata 数据和分析过程迁移脚本

本项目提供两种源端模式：

1. `tdsim`：当前本机 demo 源端，使用 Citus/PostgreSQL 模拟 Teradata MPP 金融分析负载。
2. `real-teradata`：真实 Teradata 源端预留模式，使用 `scripts/export_real_teradata_jdbc.py` 通过 JDBC 导出同名表。

## 端到端迁移

准备 DWS 连接配置：

```bash
cp config/dws.env.example config/dws.env
vi config/dws.env
```

执行迁移：

```bash
./scripts/migrate_td_to_dws.sh
```

该命令会依次执行：

1. `scripts/export_td_data.sh`：从源端导出 8 张金融表 CSV。
2. `scripts/load_dws_data.sh`：在 DWS 创建 `finance_dw` 和 `reports` schema，装载 CSV。
3. `scripts/run_dws_reports.sh`：在 DWS 运行报表视图并导出报表 CSV。
4. `scripts/validate_dws_migration.sh`：校验源端和 DWS 的行数、报表结果。

## 分析过程迁移

当前金融分析过程已迁移为 DWS 视图：

- `reports.branch_kpi`
- `reports.customer_profitability`
- `reports.liquidity_gap`
- `reports.loan_risk_snapshot`
- `reports.suspicious_activity`

DWS SQL 位于：

- `sql/dws/01_create_finance_dw.sql`
- `sql/dws/02_report_views.sql`
- `sql/dws/03_load_data.sql`

## 真实 Teradata 导出

真实 Teradata 环境需要提供 JDBC 驱动：

```bash
cp config/teradata.env.example config/teradata.env
source config/teradata.env
python3 -m pip install --user jaydebeapi
./scripts/export_real_teradata_jdbc.py
```

导出的 CSV 与 `tdsim` 模式一致，后续仍使用：

```bash
./scripts/load_dws_data.sh
./scripts/run_dws_reports.sh
./scripts/validate_dws_migration.sh
```

## SQL 转换辅助

迁移前先扫描 Teradata SQL/BTEQ/TPT 高风险语法：

```bash
./scripts/scan_teradata_compatibility.py /path/to/teradata/sql
```

输出：

- `reports/teradata_compatibility_scan.csv`
- `reports/teradata_compatibility_scan.md`

简单报表 SQL 可先用辅助脚本转换：

```bash
./scripts/convert_teradata_sql_to_dws.py source_sql_dir converted_sql_dir
```

该脚本只处理常见类型和 `SELECT TOP` 等简单语法。`QUALIFY`、volatile table、macro、存储过程、Teradata 专有 UDF、复杂时间函数仍需人工复核。
