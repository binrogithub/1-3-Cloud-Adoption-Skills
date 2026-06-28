---
name: mysql-to-rds
description: MySQL 到 RDS（关系数据库服务）数据迁移技能，用于华为云。适用于：(1) 从 MySQL 迁移到华为云 RDS for MySQL，(2) 配置数据同步和全量迁移，(3) 验证迁移完整性和数据一致性，(4) 排查 MySQL 迁移问题。 MySQL to RDS (Relational Database Service) data migration skill for Huawei Cloud. Use when (1) Migrating from MySQL to Huawei Cloud RDS for MySQL, (2) Configuring data sync and full migration, (3) Verifying migration completeness and data consistency, (4) Troubleshooting MySQL migration issues.
---

# MySQL to RDS Migration / MySQL 到 RDS 迁移

## Overview / 概述

This skill provides guidance for migrating data from MySQL to Huawei Cloud RDS for MySQL. It covers the complete migration workflow including pre-migration assessment, data migration, synchronization, and verification.

本技能提供将数据从 MySQL 迁移到华为云 RDS for MySQL 的指导。涵盖完整的迁移工作流程，包括迁移前评估、数据迁移、同步和验证。

## Migration Prerequisites / 迁移前置条件

- Source MySQL accessible (on-premise or cloud) / 源端 MySQL 可访问（本地或云上）
- Target Huawei Cloud RDS for MySQL instance provisioned / 目标华为云 RDS for MySQL 实例已创建
- Network connectivity between MySQL and RDS / MySQL 与 RDS 之间网络连通
- Migration tool readiness (mysqldump, DRS, or Data Transport Service) / 迁移工具就绪（mysqldump、DRS 或数据传输服务）
- Source database backup completed / 源数据库备份已完成

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory databases**: List all databases to be migrated
   **清点数据库**：列出所有待迁移数据库

```sql
SHOW DATABASES;
```

2. **Check MySQL version**: Ensure compatibility with RDS
   **检查 MySQL 版本**：确保与 RDS 兼容

```sql
SELECT VERSION();
```

3. **Assess data size**: Calculate total data volume
   **评估数据大小**：计算总数据量

```sql
SELECT 
    table_schema AS 'Database',
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)'
FROM information_schema.tables
GROUP BY table_schema;
```

4. **Identify large tables**: Flag tables requiring special handling
   **识别大表**：标记需要特殊处理的表

5. **Review privileges**: Document required user permissions
   **审查权限**：记录需要的用户权限

### 2. Full Data Migration / 全量数据迁移

#### Option A: Using mysqldump / 使用 mysqldump

1. **Export schema**: Create schema dump
   **导出 schema**：创建 schema 转储

```bash
mysqldump -h <source-host> -P <source-port> -u <user> -p --single-transaction --no-data <database> > schema.sql
```

2. **Export data**: Create data dump
   **导出数据**：创建数据转储

```bash
mysqldump -h <source-host> -P <source-port> -u <user> -p --single-transaction --quick <database> > data.sql
```

3. **Transfer to RDS**: Import into target
   **传输到 RDS**：导入到目标

```bash
mysql -h <rds-host> -P <rds-port> -u <user> -p <database> < schema.sql
mysql -h <rds-host> -P <rds-port> -u <user> -p <database> < data.sql
```

#### Option B: Using DRS / 使用 DRS

1. **Create DRS instance**: Set up migration task
   **创建 DRS 实例**：设置迁移任务

2. **Configure source and target**: Specify connection details
   **配置源和目标**：指定连接详情

3. **Select databases/tables**: Choose what to migrate
   **选择数据库/表**：选择要迁移的内容

4. **Start migration**: Begin the replication
   **开始迁移**：启动复制

### 3. Schema Migration / Schema 迁移

1. **Export stored procedures, functions, triggers**: Capture DB objects
   **导出存储过程、函数、触发器**：捕获数据库对象

```bash
mysqldump -h <source-host> -P <source-port> -u <user> -p --no-data --routines --triggers <database> > objects.sql
```

2. **Review and adjust** for any RDS incompatibilities
   **审查并调整** 以解决 RDS 不兼容问题

3. **Import to RDS**: Load DB objects
   **导入到 RDS**：加载数据库对象

### 4. User Migration / 用户迁移

1. **Export users and privileges**: Capture user accounts
   **导出用户和权限**：捕获用户账户

```sql
SELECT user, host, authentication_string FROM mysql.user;
```

2. **Create users on RDS**: Recreate user accounts
   **在 RDS 上创建用户**：重建用户账户

3. **Grant privileges**: Apply appropriate permissions
   **授予权限**：应用适当的权限

### 5. Incremental Synchronization / 增量同步

For live data migration with minimal downtime: / 最小化停机时间的实时数据迁移：

1. **Enable binlog**: Ensure source has binary logging
   **启用 binlog**：确保源端有二进制日志

```sql
SHOW VARIABLES LIKE 'log_bin';
```

2. **Configure DRS for CDC**: Set up change data capture
   **配置 DRS CDC**：设置变更数据捕获

3. **Monitor replication**: Track sync status
   **监控复制**：跟踪同步状态

### 6. Cutover / 切换

1. **Notify stakeholders**: Inform users of cutover window
   **通知相关方**：通知用户切换窗口

2. **Stop applications**: Prevent new writes to source
   **停止应用**：阻止向源端写入

3. **Final sync**: Wait for DRS to catch up
   **最终同步**：等待 DRS 追上

4. **Update connection strings**: Point to RDS
   **更新连接字符串**：指向 RDS

5. **Start applications**: Bring up services with RDS
   **启动应用**：使用 RDS 启动服务

### 7. Post-Migration Verification / 迁移后验证

1. **Compare row counts**: Verify all data migrated
   **比对行数**：验证所有数据已迁移

```sql
SELECT COUNT(*) FROM source_table;
-- Compare with target after connection string update
SELECT COUNT(*) FROM target_table;
```

2. **Validate data integrity**: Spot check records
   **验证数据完整性**：抽样检查记录

3. **Test application queries**: Verify functionality
   **测试应用查询**：验证功能

4. **Monitor performance**: Check RDS metrics
   **监控性能**：检查 RDS 指标

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Character set issues / 字符集问题 | Different default charset / 不同默认字符集 | Explicitly specify UTF-8 during export / 导出时明确指定 UTF-8 |
| Key conflicts / 主键冲突 | Duplicate data / 重复数据 | Truncate target before import / 导入前清空目标 |
| Foreign key errors / 外键错误 | Table order issues / 表顺序问题 | Disable foreign key checks during import / 导入时禁用外键检查 |
| Grant errors / 权限错误 | Different privilege model / 不同权限模型 | Use RDS managed accounts / 使用 RDS 管理账户 |
| Large table timeout / 大表超时 | Long import time / 导入时间长 | Use mysqldump with --quick flag / 使用带 --quick 标志的 mysqldump |

## Huawei Cloud RDS Specifics / 华为云 RDS 详情

### Supported Versions / 支持的版本
- **MySQL 5.7**, **8.0** compatible / 兼容 MySQL 5.7、8.0

### Instance Types / 实例类型
- **Basic**: Single instance for development / 开发用单实例
- **Ha**: Primary-replica for high availability / 高可用主从
- **Enterprise**: Multi-replica for enterprise use / 企业用多副本

### Storage Types / 存储类型
- **SSD**: Standard storage / 标准存储
- **Ultra-fast SSD**: High performance / 高性能

### Migration Tools / 迁移工具
- **DRS (Data Replication Service)**: Real-time migration with CDC / 带 CDC 的实时迁移
- **mysqldump**: Manual full migration / 手动全量迁移
- **Data Transport Service**: Large dataset migration / 大数据集迁移

## Best Practices / 最佳实践

1. **Always backup** source before migration / 迁移前务必备份源
2. **Use DRS for zero-downtime** migration when possible / 尽可能使用 DRS 实现零停机迁移
3. **Test in staging** before production migration / 生产迁移前在预发环境测试
4. **Keep source available** for at least 48 hours post-migration / 迁移后至少保持源可用 48 小时
5. **Monitor RDS performance** closely during initial period / 初期密切监控 RDS 性能
