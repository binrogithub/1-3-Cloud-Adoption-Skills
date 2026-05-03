# 后续迁移到华为云 DWS 的 Demo 路径

## 当前阶段

当前本机 demo 已覆盖源端分析负载：

1. 金融客户、账户、产品、机构、日期维表。
2. 交易流水、日终余额、贷款快照事实表。
3. 分行 KPI、客户贡献、贷款风险、可疑交易、流动性敞口报表。
4. MPP 分布键：事实表按 `customer_id` 分布，维表作为 reference table。

## 替换为真实 Teradata 源端

真实 Teradata Vantage Express 可以作为 VM 运行。替换路径：

1. 在 VM 中创建同名 `finance_dw` 表。
2. 将 `sql/02_data/load_finance_sample.sql` 改写为 Teradata 语法，或用 CSV 装载。
3. 使用 BTEQ、TPT、JDBC 或 ODBC 导出源端对象 DDL、统计信息、样例数据和报表结果。
4. 将导出结果与本 demo 的报表 CSV 做口径校验。

## 到 DWS 的迁移验证项

建议后续新增以下脚本：

1. Teradata DDL 到 DWS DDL 映射：数据类型、主索引、分区、统计信息。
2. 数据导出到 OBS：按表生成 CSV/Parquet。
3. DWS 建表和导入：选择 `DISTRIBUTE BY HASH(customer_id)` 或业务主键。
4. 报表 SQL 兼容性改造：日期函数、QUALIFY、TOP、递归语法、临时表语义。
5. 结果校验：行数、金额汇总、按月指标、风险敞口。
6. 性能对比：关键报表执行时间、执行计划、数据倾斜。

