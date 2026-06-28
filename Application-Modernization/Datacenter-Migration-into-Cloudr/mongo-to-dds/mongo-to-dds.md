---
name: mongo-to-dds
description: MongoDB 到 DDS（文档数据库服务）数据迁移技能，用于华为云。适用于：(1) 从 MongoDB 迁移到华为云 DDS，(2) 配置数据同步和全量迁移，(3) 验证迁移完整性和数据一致性，(4) 排查 MongoDB 迁移问题。 MongoDB to DDS (Document Database Service) data migration skill for Huawei Cloud. Use when (1) Migrating from MongoDB to Huawei Cloud DDS, (2) Configuring data sync and full migration, (3) Verifying migration completeness and data consistency, (4) Troubleshooting MongoDB migration issues.
---

# MongoDB to DDS Migration / MongoDB 到 DDS 迁移

## Overview / 概述

This skill provides guidance for migrating data from MongoDB to Huawei Cloud DDS (Document Database Service). It covers the complete migration workflow including pre-migration assessment, data migration, synchronization, and verification.

本技能提供将数据从 MongoDB 迁移到华为云 DDS（文档数据库服务）的指导。涵盖完整的迁移工作流程，包括迁移前评估、数据迁移、同步和验证。

## Migration Prerequisites / 迁移前置条件

- Source MongoDB accessible (on-premise or cloud) / 源端 MongoDB 可访问（本地或云上）
- Target Huawei Cloud DDS instance provisioned / 目标华为云 DDS 实例已创建
- Network connectivity between MongoDB and DDS / MongoDB 与 DDS 之间网络连通
- Migration tool readiness (mongodump/mongorestore, or DRS) / 迁移工具就绪（mongodump/mongorestore 或 DRS）
- Backup of source database completed / 源数据库备份已完成

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory MongoDB databases**: List all databases and collections
   **清点 MongoDB 数据库**：列出所有数据库和集合

```javascript
// List all databases
show dbs

// Switch to database and list collections
use <database>
show collections
```

2. **Assess data size**: Calculate total data volume
   **评估数据大小**：计算总数据量

```javascript
// Check collection sizes
db.collection.stats()
```

3. **Review MongoDB version**: Ensure compatibility with DDS
   **审查 MongoDB 版本**：确保与 DDS 兼容

4. **Identify indexes**: Document all indexes to be recreated
   **识别索引**：记录所有需要重建的索引

### 2. Full Data Migration / 全量数据迁移

#### Option A: Using mongodump/mongorestore / 使用 mongodump/mongorestore

1. **Export from source MongoDB**: Create dump file
   **从源 MongoDB 导出**：创建转储文件

```bash
mongodump --host <source-host> --port <source-port> --db <database> --out /backup/path
```

2. **Transfer to target**: Copy dump file if needed
   **传输到目标**：如需要，复制转储文件

3. **Import to DDS**: Restore to target
   **导入到 DDS**：恢复到目标

```bash
mongorestore --host <dds-host> --port <dds-port> --db <database> /backup/path/<database>
```

#### Option B: Using DRS (Data Replication Service) / 使用 DRS（数据复制服务）

1. **Create DRS instance**: Set up replication task
   **创建 DRS 实例**：设置复制任务

2. **Configure source and target**: Specify connection details
   **配置源和目标**：指定连接详情

3. **Select databases/collections**: Choose what to migrate
   **选择数据库/集合**：选择要迁移的内容

4. **Start migration**: Begin the replication
   **开始迁移**：启动复制

### 3. Incremental Synchronization / 增量同步

For live data migration: / 实时数据迁移：

1. **Use change streams**: Enable MongoDB change streams for real-time sync
   **使用变更流**：启用 MongoDB 变更流实现实时同步

```javascript
// Create change stream
db.collection.aggregate([ { $changeStream: { fullDocument: "updateLookup" } } ])
```

2. **Configure DRS for ongoing sync**: Set up incremental replication
   **配置 DRS 持续同步**：设置增量复制

3. **Monitor sync lag**: Track replication status
   **监控同步延迟**：跟踪复制状态

### 4. Index Migration / 索引迁移

1. **Export index definitions**: Capture all indexes from source
   **导出索引定义**：捕获源端所有索引

```javascript
// Get indexes
db.collection.getIndexes()
```

2. **Create indexes on DDS**: Recreate indexes on target
   **在 DDS 上创建索引**：在目标端重建索引

```javascript
// Create index on DDS
db.collection.createIndex({ field: 1 }, { name: "index_name" })
```

3. **Verify index creation**: Ensure indexes are active
   **验证索引创建**：确保索引已激活

### 5. Cutover / 切换

1. **Stop applications**: Prevent new writes to source
   **停止应用**：阻止向源端写入

2. **Final sync**: Capture remaining changes
   **最终同步**：捕获剩余变更

3. **Update connection strings**: Point applications to DDS
   **更新连接字符串**：将应用指向 DDS

4. **Start applications**: Bring up services with DDS
   **启动应用**：使用 DDS 启动服务

### 6. Post-Migration Verification / 迁移后验证

1. **Compare document counts**: Verify all documents migrated
   **比对文档数量**：验证所有文档已迁移

```javascript
// Source count
db.collection.countDocuments()

// Target count (after connection string update)
db.collection.countDocuments()
```

2. **Validate data integrity**: Spot check sample documents
   **验证数据完整性**：抽样检查文档

3. **Test query performance**: Verify indexes are working
   **测试查询性能**：验证索引工作正常

4. **Monitor for errors**: Watch application logs
   **监控错误**：关注应用日志

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Connection timeout / 连接超时 | Network or firewall / 网络或防火墙 | Check security group and network settings / 检查安全组和网络设置 |
| Index creation slow / 索引创建慢 | Large collection / 大集合 | Create indexes after data load / 在数据加载后创建索引 |
| Memory issues / 内存问题 | Large documents / 大文档 | Increase DDS instance规格 / 增加 DDS 实例规格 |
| Encoding issues / 编码问题 | Character set mismatch / 字符集不匹配 | Ensure UTF-8 encoding / 确保 UTF-8 编码 |
| Oplog overflow / 操作日志溢出 | High write volume / 高写入量 | Use longer sync window / 使用更长的同步窗口 |

## Huawei Cloud DDS Specifics / 华为云 DDS 详情

### Supported Versions / 支持的版本
- **MongoDB 4.0**, **4.2**, **4.4**, **5.0**, **6.0** compatible / 兼容 MongoDB 4.0、4.2、4.4、5.0、6.0

### Instance Types / 实例类型
- **Replica Set**: High availability with automatic failover / 高可用性，自动故障转移
- **Sharding**: Horizontal scaling for large datasets / 水平扩展，用于大数据集

### Storage Engine / 存储引擎
- **WiredTiger**: Default storage engine / 默认存储引擎
- **In-Memory**: For low latency requirements / 用于低延迟需求

### Migration Tools / 迁移工具
- **DRS (Data Replication Service)**: Managed real-time migration / 托管实时迁移
- **mongodump/mongorestore**: Manual full migration / 手动全量迁移
- **Data Studio**: GUI-based migration tool / 基于 GUI 的迁移工具

## Best Practices / 最佳实践

1. **Always backup** source before migration / 迁移前务必备份源
2. **Test with small dataset** first / 先用小数据集测试
3. **Create indexes after data load** for better performance / 数据加载后创建索引以获得更好性能
4. **Monitor replication lag** during incremental sync / 增量同步期间监控复制延迟
5. **Keep source available** for rollback / 保持源可用以便回滚
