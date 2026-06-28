---
name: hbase-migration
description: HBase 数据迁移技能，用于华为云。适用于：(1) 将 HBase 数据迁移到华为云表格存储服务，(2) 配置 HBase 集群间的数据同步，(3) 验证迁移完整性和数据一致性，(4) 排查 HBase 迁移问题。 HBase data migration skill for Huawei Cloud. Use when (1) Migrating HBase data to Huawei Cloud Table Store service, (2) Configuring data sync between HBase clusters, (3) Verifying migration completeness and data consistency, (4) Troubleshooting HBase migration issues.
---

# HBase Migration / HBase 迁移

## Overview / 概述

This skill provides guidance for migrating HBase data to Huawei Cloud. It covers the complete migration workflow including pre-migration assessment, data export/import, synchronization, and verification.

本技能提供将 HBase 数据迁移到华为云的指导。涵盖完整的迁移工作流程，包括迁移前评估、数据导出/导入、同步和验证。

## Migration Prerequisites / 迁移前置条件

- Source HBase cluster accessible and healthy / 源端 HBase 集群可访问且健康
- Target Huawei Cloud MRS or Table Store provisioned / 目标华为云 MRS 或表格存储已创建
- Network connectivity between source and target / 源与目标之间网络连通
- Migration tool readiness (Export/Import, DistCP, or DRS) / 迁移工具就绪（Export/Import、DistCP 或 DRS）
- Sufficient capacity at target / 目标有足够容量

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory HBase tables**: List all tables to be migrated
   **清点 HBase 表**：列出所有待迁移表

```bash
# List all tables in HBase Shell
list
describe 'table_name'
```

2. **Assess data size**: Calculate total data volume
   **评估数据大小**：计算总数据量

```bash
# Check table size
du 'table_name'
```

3. **Analyze schema**: Document column families and versions
   **分析 schema**：记录列族和版本

4. **Identify regions**: Understand region distribution
   **识别 region**：了解 region 分布

### 2. Migration Methods / 迁移方法

#### Method A: Export/Import / 方法一：导出/导入

1. **Export table to HDFS**: Use HBase Export utility
   **导出表到 HDFS**：使用 HBase Export 工具

```bash
hbase org.apache.hadoop.hbase.mapreduce.Export table_name /hdfs/path/export
```

2. **Transfer to target HDFS**: Copy data files
   **传输到目标 HDFS**：复制数据文件

```bash
hadoop distcp /source/path /target/path
```

3. **Import table**: Use HBase Import utility
   **导入表**：使用 HBase Import 工具

```bash
hbase org.apache.hadoop.hbase.mapreduce.Import table_name /hdfs/path/export
```

#### Method B: Copy Table / 方法二：复制表

1. **Enable snapshot**: Create table snapshot
   **启用快照**：创建表快照

```bash
snapshot 'table_name', 'snapshot_name'
```

2. **Export snapshot**: Export snapshot to target
   **导出快照**：导出快照到目标

```bash
hbase org.apache.hadoop.hbase.snapshot.ExportSnapshot -snapshot snapshot_name -copy-to hdfs://target:8020/hbase
```

3. **Restore snapshot**: Restore on target cluster
   **恢复快照**：在目标集群恢复

```bash
restore_snapshot 'snapshot_name'
```

#### Method C: DRS for HBase / 方法三：DRS 用于 HBase

1. **Create DRS task**: Set up replication
   **创建 DRS 任务**：设置复制

2. **Configure source and target**: Specify endpoints
   **配置源和目标**：指定端点

3. **Start replication**: Begin data sync
   **启动复制**：开始数据同步

### 3. Schema Migration / Schema 迁移

1. **Export schema**: Capture table definition
   **导出 schema**：捕获表定义

```bash
hbase org.apache.hadoop.hbase.mapreduce.Export table_name /hdfs/path/schema -schemaOnly
```

2. **Create table on target**: Recreate table structure
   **在目标创建表**：重建表结构

```bash
create 'new_table', 'cf1', 'cf2'
```

3. **Verify schema**: Ensure column families match
   **验证 schema**：确保列族匹配

### 4. Data Verification / 数据验证

1. **Count rows**: Compare row counts
   **统计行数**：比对行数

```bash
count 'table_name', INTERVAL => 1000000
```

2. **Scan sample data**: Verify data content
   **扫描抽样数据**：验证数据内容

```bash
scan 'table_name', LIMIT => 100
```

3. **Check data integrity**: Validate key-value pairs
   **检查数据完整性**：验证键值对

### 5. Cutover / 切换

1. **Stop applications**: Prevent new writes
   **停止应用**：阻止新写入

2. **Final sync**: Capture remaining changes
   **最终同步**：捕获剩余变更

3. **Update application config**: Point to target
   **更新应用配置**：指向目标

4. **Start applications**: Bring up services
   **启动应用**：启动服务

### 6. Post-Migration Verification / 迁移后验证

1. **Verify row counts**: Ensure all data migrated
   **验证行数**：确保所有数据已迁移

2. **Validate data integrity**: Spot check records
   **验证数据完整性**：抽样检查记录

3. **Test application functionality**: Verify operations
   **测试应用功能**：验证操作

4. **Monitor performance**: Check latency and throughput
   **监控性能**：检查延迟和吞吐量

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Region split issues / Region 拆分问题 | Different cluster configs / 不同集群配置 | Pre-split table before import / 导入前预拆分表 |
| WAL (Write-Ahead Log) issues / WAL 问题 | Unfinished transactions / 未完成事务 | Disable and re-enable WAL / 禁用并重新启用 WAL |
| Compression mismatch / 压缩不匹配 | Different codecs / 不同编解码器 | Re-create table with matching compression / 使用匹配的压缩重新创建表 |
| HFile version mismatch / HFile 版本不匹配 | HBase version difference / HBase 版本差异 | Upgrade HBase or convert HFiles / 升级 HBase 或转换 HFile |
| Timeout during export / 导出超时 | Large table / 大表 | Increase timeout values / 增加超时值 |

## Huawei Cloud MRS HBase Specifics / 华为云 MRS HBase 详情

### Supported Versions / 支持的版本
- **HBase 1.x**, **2.x** depending on MRS version / 根据 MRS 版本支持 HBase 1.x、2.x

### Storage Backend / 存储后端
- **HDFS**: Default HDFS storage / 默认 HDFS 存储
- **Apache Phoenix**: SQL layer for HBase / HBase 的 SQL 层

### Migration Tools / 迁移工具
- **Snapshot/Export/Import**: Native HBase tools / 原生 HBase 工具
- **DistCP**: HDFS data copy / HDFS 数据复制
- **DRS**: Managed migration service / 托管迁移服务

## Best Practices / 最佳实践

1. **Pre-split tables** before migration for large datasets / 大数据集迁移前预拆分表
2. **Use snapshots** for point-in-time consistency / 使用快照保证时间点一致性
3. **Disable WAL** during bulk import for performance / 批量导入时禁用 WAL 以提高性能
4. **Verify data during migration**, not after / 迁移期间验证数据，而非之后
5. **Plan for rollback** in case of issues / 准备回滚方案以防问题
