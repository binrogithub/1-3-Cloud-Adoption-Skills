---
name: nas-migration
description: NAS（网络附加存储）数据迁移技能，用于华为云。适用于：(1) 从本地 NAS 迁移到华为云 NAS，(2) 不同 NAS 存储类型间迁移，(3) 配置数据同步，(4) 验证迁移完整性和数据完整性。NAS (Network Attached Storage) data migration skill for Huawei Cloud. Use when (1) Migrating from on-premise NAS to Huawei Cloud NAS, (2) Migrating between NAS storage types, (3) Configuring data synchronization, (4) Verifying migration completeness and data integrity.
---

# NAS Migration / NAS 迁移

## Overview / 概述

This skill provides guidance for performing NAS (Network Attached Storage) data migration to Huawei Cloud NAS. It covers the complete migration workflow including pre-migration planning, data transfer, synchronization, and verification.

本技能提供将 NAS（网络附加存储）数据迁移到华为云 NAS 的指导，涵盖完整的迁移工作流程，包括迁移前规划、数据传输、同步和验证。

## Migration Prerequisites / 迁移前置条件

- Source NAS system accessible (on-premise or cloud) / 源 NAS 系统可访问（本地或云上）
- Target Huawei Cloud NAS provisioned with appropriate capacity / 目标华为云 NAS 已配置足够容量
- Network connectivity between source and target / 源与目标之间网络连通
- Migration tool readiness (rsync, wget, or Huawei Cloud Data Migration Service) / 迁移工具就绪（rsync、wget 或华为云数据迁移服务）
- Backup of critical data completed / 关键数据已完成备份

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Planning / 迁移前规划

1. **Inventory source data**: Analyze source NAS structure, file types, total size, and access patterns
   **清点源数据**：分析源 NAS 结构、文件类型、总大小和访问模式

2. **Assess migration scope**: Identify hot data, cold data, and any data requiring special handling
   **评估迁移范围**：识别热数据、冷数据及需要特殊处理的数据

3. **Plan migration window**: Schedule migration during low-traffic periods
   **规划迁移窗口**：选择低流量时段进行迁移

4. **Configure target NAS**: Set up Huawei Cloud NAS with appropriate share permissions and access controls
   **配置目标 NAS**：设置华为云 NAS 的共享权限和访问控制

5. **Create migration plan**: Document file mapping between source and target paths
   **制定迁移计划**：记录源路径与目标路径的文件映射关系

### 2. Initial Data Transfer / 初始数据传输

For the bulk data migration: / 用于批量数据迁移：

1. **Mount source NAS** to the migration server
   **挂载源 NAS** 到迁移服务器

2. **Mount target Huawei Cloud NAS**
   **挂载目标华为云 NAS**

3. **Execute initial sync** using rsync or Data Migration Service:
   **执行初始同步**，使用 rsync 或数据迁移服务：

```bash
rsync -avz --progress --stats source_nas_path/ target_nas_path/
```

For very large datasets, use Huawei Cloud Data Migration Service (DMS) for optimized transfer.
对于超大数据集，使用华为云数据迁移服务（DMS）进行优化传输。

### 3. Incremental Synchronization / 增量同步

For live data migration with minimal downtime: / 最小化停机时间的实时数据迁移：

1. **Schedule multiple sync cycles** during pre-cutover phase
   **在切换前阶段安排多个同步周期**

2. **Use rsync with archive mode** to capture all attributes:
   **使用 rsync 的归档模式** 保留所有属性：

```bash
rsync -avz --delete source_nas_path/ target_nas_path/
```

3. **Monitor sync progress** and log any errors
   **监控同步进度** 并记录任何错误

4. **Verify delta size** decreases with each cycle
   **验证增量大小** 随每个周期递减

### 4. Cutover Procedure / 切换流程

1. **Notify users** of impending cutover window
   **通知用户** 即将到来的切换窗口

2. **Stop applications** writing to source NAS
   **停止应用** 对源 NAS 的写入

3. **Perform final sync** to capture remaining changes
   **执行最终同步** 捕获剩余变更

4. **Update mount points** to point to Huawei Cloud NAS
   **更新挂载点** 指向华为云 NAS

5. **Verify connectivity** from application servers
   **验证应用服务器** 的连接性

### 5. Post-Migration Verification / 迁移后验证

1. **Check file counts**: Compare source and target file counts match
   **检查文件数量**：对比源端和目标端的文件数量是否一致

2. **Validate data integrity**: Use checksums (MD5/SHA) for critical files
   **验证数据完整性**：对关键文件使用校验和（MD5/SHA）

3. **Test accessibility**: Verify applications can read/write to migrated data
   **测试可访问性**：验证应用能正常读写迁移后的数据

4. **Performance validation**: Confirm acceptable latency and throughput
   **性能验证**：确认延迟和吞吐量在可接受范围内

5. **Monitor for 48 hours**: Watch for any access errors or performance issues
   **监控 48 小时**：关注任何访问错误或性能问题

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Permission denied / 权限拒绝 | UID/GID mismatch / UID/GID 不匹配 | Configure ID mapping or use consistent UID/GID / 配置 ID 映射或使用一致的 UID/GID |
| Path too long / 路径过长 | Deep directory structures / 深层目录结构 | Use shorter paths or flatten structure / 使用更短路径或扁平化结构 |
| Symbolic links broken / 符号链接损坏 | Relative vs absolute links / 相对链接与绝对链接 | Convert links before migration / 迁移前转换链接 |
| Special characters / 特殊字符 | Non-UTF8 filenames / 非 UTF-8 文件名 | Normalize encoding before migration / 迁移前规范化编码 |
| Incomplete sync / 同步不完整 | Network interruption / 网络中断 | Re-run rsync with --partial flag / 使用 --partial 参数重新运行 rsync |

## Huawei Cloud NAS Specifics / 华为云 NAS 详情

### Supported Protocols / 支持的协议
- **NFS**: v3, v4.0, v4.1
- **SMB**: v2.0, v2.1, v3.0, v3.1.1

### Storage Tiers / 存储层级
- **Standard / 标准版**: High throughput, moderate IOPS / 高吞吐量，中等 IOPS
- **Performance / 性能版**: Low latency, high IOPS / 低延迟，高 IOPS
- **Infrequent Access / 低频访问**: Lower cost for cold data / 冷数据更低成本

### Migration Tools / 迁移工具
- **Huawei Cloud Data Migration Service (DMS) / 华为云数据迁移服务**：Full-featured migration / 全功能迁移
- **rsync/rclone**: Incremental sync for smaller datasets / 较小数据集的增量同步
- **obsutil**: For migration to Object Storage as intermediate step / 作为中间步骤迁移到对象存储

## Best Practices / 最佳实践

1. **Always validate** before deleting source data / 在删除源数据前务必验证
2. **Maintain rollback capability** for 48-72 hours post-migration / 迁移后保持 48-72 小时回滚能力
3. **Test with subset** of data first for large migrations / 大规模迁移前先用子集数据测试
4. **Schedule during maintenance windows** for production systems / 生产系统安排在维护窗口期
5. **Document all changes** made during migration for audit purposes / 记录迁移期间的所有变更以供审计
