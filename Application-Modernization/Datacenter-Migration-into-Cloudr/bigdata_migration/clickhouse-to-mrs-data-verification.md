---
name: clickhouse-to-mrs-data-verification
description: ClickHouse 到 MRS（MapReduce Service）数据验证技能，用于华为云。适用于：(1) 验证 ClickHouse 到 MRS 的数据迁移完整性，(2) 比对源端与目标端数据一致性，(3) 校验数据文件和目录结构，(4) 排查数据差异问题。ClickHouse to MRS data verification skill for Huawei Cloud. Use when (1) Verifying data migration completeness from ClickHouse to MRS, (2) Comparing source and target data consistency, (3) Validating data files and directory structures, (4) Troubleshooting data discrepancies.
---

# ClickHouse to MRS Data Verification / ClickHouse 到 MRS 数据验证

## Overview / 概述

This skill provides guidance for verifying data integrity and completeness when migrating from ClickHouse to Huawei Cloud MRS (MapReduce Service). It covers verification methodologies, comparison methods, and discrepancy resolution.

本技能提供从 ClickHouse 迁移数据到华为云 MRS（MapReduce Service）时的数据完整性和一致性验证指导，涵盖验证方法论、比对方法和差异排查。

## Verification Prerequisites / 验证前置条件

- Source ClickHouse database accessible / 源端 ClickHouse 数据库可访问
- Target MRS cluster provisioned and running / 目标 MRS 集群已创建并运行
- Network connectivity between ClickHouse and MRS / ClickHouse 与 MRS 之间网络连通
- Verification tools installed (clickhouse-client, beeline, hdfs dfs) / 验证工具已安装（clickhouse-client、beeline、hdfs dfs）
- Migration data manifest or migration plan available / 迁移数据清单或迁移计划可用

## Verification Workflow / 验证工作流程

### 1. Table Structure Verification / 表结构验证

1. **Export source table schemas**: Retrieve ClickHouse table definitions
   **导出源端表结构**：获取 ClickHouse 表定义

```sql
SHOW CREATE TABLE source_table;
```

2. **Compare with target**: Verify MRS Hive/MR table schemas match
   **比对目标端**：验证 MRS Hive/MR 表结构是否匹配

```sql
DESCRIBE FORMATTED mrs_database.target_table;
```

3. **Check indexing and partitioning**: Ensure partitioning strategies align
   **检查索引和分区**：确保分区策略一致

### 2. Data Count Verification / 数据量验证

1. **Count source records**: Get total row count from ClickHouse
   **统计源端记录数**：从 ClickHouse 获取总行数

```sql
SELECT count() FROM source_table;
```

2. **Count target records**: Get total row count from MRS
   **统计目标端记录数**：从 MRS 获取总行数

```bash
beeline -e "SELECT COUNT(*) FROM mrs_database.target_table;"
```

3. **Compare counts**: Verify source and target counts match
   **比对数量**：验证源端和目标端数量一致

### 3. Data Content Verification / 数据内容验证

1. **Sample data comparison**: Compare random samples from both sides
   **抽样数据比对**：比对两端的随机抽样数据

```sql
-- ClickHouse
SELECT * FROM source_table ORDER BY rand() LIMIT 100;
```

2. **Checksum verification**: Calculate checksums for verification
   **校验和验证**：计算校验和进行验证

```bash
# HDFS level checksum
hdfs dfs -checksum /mrs/data/path/
```

3. **Column-by-column validation**: For critical tables, validate each column
   **逐列验证**：对关键表逐列验证

### 4. File and Directory Verification / 文件和目录验证

1. **Check HDFS directory structure**: Verify source paths match target
   **检查 HDFS 目录结构**：验证源路径与目标路径一致

```bash
hdfs dfs -ls -R /mrs/data/path/
```

2. **Compare file sizes**: Ensure all files transferred completely
   **比对文件大小**：确保所有文件完整传输

```bash
hdfs dfs -du -h /mrs/data/path/
```

3. **Verify file permissions**: Check read/write permissions are correct
   **验证文件权限**：检查读写权限是否正确

### 5. Query Functionality Verification / 查询功能验证

1. **Run test queries**: Execute sample queries on target
   **运行测试查询**：在目标端执行示例查询

2. **Compare query results**: Ensure results match between source and target
   **比对查询结果**：确保两端查询结果一致

3. **Test aggregation queries**: Verify GROUP BY, JOIN operations work correctly
   **测试聚合查询**：验证 GROUP BY、JOIN 操作正确性

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Count mismatch / 数量不匹配 | Data type conversion issues / 数据类型转换问题 | Check implicit type conversions / 检查隐式类型转换 |
| Null value differences / 空值差异 | NULL handling differs / NULL 处理方式不同 | Normalize NULL handling / 规范化 NULL 处理 |
| Precision loss / 精度丢失 | Float/double conversion / 浮点数转换 | Use DECIMAL type or tolerate minor differences / 使用 DECIMAL 类型或接受细微差异 |
| Encoding issues / 编码问题 | Character set mismatch / 字符集不匹配 | Ensure UTF-8 encoding throughout / 确保全程 UTF-8 编码 |
| Missing partitions / 分区丢失 | Partition syntax differences / 分区语法差异 | Re-create partitions on target / 在目标端重建分区 |

## Huawei Cloud MRS Specifics / 华为云 MRS 详情

### Supported Components / 支持的组件
- **Hive**: For SQL-like queries on MRS data / 用于 MRS 数据的 SQL 查询
- **Spark**: For large-scale data processing / 用于大规模数据处理
- **HBase**: For NoSQL-style access / 用于 NoSQL 方式访问

### Data Formats / 数据格式
- **ORC**: Optimized Row Columnar format / 优化行列式格式
- **Parquet**: Columnar storage format / 列式存储格式
- **RCFile**: Record Columnar File / 记录列式文件
- **TextFile**: Plain text format / 纯文本格式

### Verification Tools / 验证工具
- **beeline**: Hive query tool / Hive 查询工具
- **hdfs dfs**: HDFS file operations / HDFS 文件操作
- **clickhouse-client**: ClickHouse client / ClickHouse 客户端
- **Data Studio**: GUI-based query and verification / 基于 GUI 的查询和验证

## Best Practices / 最佳实践

1. **Automate verification** with scripts for repeatability / 使用脚本自动化验证以保证可重复性
2. **Sample first, full verification later** for large datasets / 大数据集先抽样后全量验证
3. **Document all discrepancies** found during verification / 记录验证中发现的所有差异
4. **Re-verify after fixes** to ensure issues resolved / 修复后重新验证确保问题解决
5. **Keep verification logs** for audit and troubleshooting / 保留验证日志用于审计和排查
