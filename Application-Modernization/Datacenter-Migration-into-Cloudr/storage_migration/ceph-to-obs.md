---
name: ceph-to-obs
description: Ceph 到 OBS（对象存储服务）数据迁移技能，用于华为云。适用于：(1) 从 Ceph 存储迁移数据到华为云 OBS，(2) 配置数据同步和传输策略，(3) 验证迁移完整性和数据一致性，(4) 排查迁移过程中的问题。 Ceph to OBS (Object Storage Service) data migration skill for Huawei Cloud. Use when (1) Migrating data from Ceph storage to Huawei Cloud OBS, (2) Configuring data synchronization and transfer strategies, (3) Verifying migration completeness and data consistency, (4) Troubleshooting migration issues.
---

# Ceph to OBS Migration / Ceph 到 OBS 迁移

## Overview / 概述

This skill provides guidance for migrating data from Ceph storage to Huawei Cloud OBS (Object Storage Service). It covers the complete migration workflow including pre-migration planning, data transfer, synchronization, and verification.

本技能提供将数据从 Ceph 存储迁移到华为云 OBS（对象存储服务）的指导。涵盖完整的迁移工作流程，包括迁移前规划、数据传输、同步和验证。

## Migration Prerequisites / 迁移前置条件

- Source Ceph cluster accessible and healthy / 源端 Ceph 集群可访问且健康
- Target Huawei Cloud OBS bucket provisioned / 目标华为云 OBS 桶已创建
- Network connectivity between Ceph and OBS / Ceph 与 OBS 之间网络连通
- Migration tool readiness (rclone, obsutil, or custom scripts) / 迁移工具就绪（rclone、obsutil 或自定义脚本）
- Sufficient OBS capacity for migration / 足够的 OBS 容量用于迁移

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Planning / 迁移前规划

1. **Inventory Ceph data**: Analyze Ceph bucket/container structure and total size
   **清点 Ceph 数据**：分析 Ceph bucket/container 结构和总大小

```bash
# List Ceph buckets
radosgw-admin bucket list

# Get bucket stats
radosgw-admin bucket stats --bucket=<bucket-name>
```

2. **Plan OBS structure**: Design OBS bucket structure (flat vs hierarchical)
   **规划 OBS 结构**：设计 OBS 桶结构（扁平或层级）

3. **Select migration method**: Choose based on data size and downtime tolerance
   **选择迁移方法**：根据数据大小和停机容忍度选择

4. **Estimate migration time**: Calculate based on data volume and bandwidth
   **估算迁移时间**：根据数据量和带宽计算

### 2. Initial Data Transfer / 初始数据传输

#### Option A: Using rclone / 使用 rclone

```bash
# Configure Ceph source
rclone config
# Enter: name = ceph-source, type = s3, endpoint = http://ceph-rgw:8080

# Configure OBS destination
rclone config
# Enter: name = obs-dest, type = s3, endpoint = https://obs.myhuaweicloud.com

# Sync data
rclone sync ceph-source:/source-bucket obs-dest:/dest-bucket --progress
```

#### Option B: Using obsutil / 使用 obsutil

```bash
# Configure OBS destination
obsutil config -access-key=your-ak -secret-key=your-sk -endpoint=obs.myhuaweicloud.com

# Copy data
obsutil cp s3://ceph-bucket/source-path obs://bucket/target-path -r -f
```

### 3. Incremental Synchronization / 增量同步

For live data migration with minimal downtime: / 最小化停机时间的实时数据迁移：

1. **Schedule sync cycles**: Run periodic sync before cutover
   **安排同步周期**：在切换前运行周期性同步

```bash
# Cron job for incremental sync every 6 hours
0 */6 * * * rclone sync ceph-source:/source-bucket obs-dest:/dest-bucket --verbose
```

2. **Monitor sync progress**: Track sync status and any errors
   **监控同步进度**：跟踪同步状态和任何错误

3. **Verify delta size**: Ensure incremental changes are decreasing
   **验证增量大小**：确保增量变更在减少

### 4. Cutover Procedure / 切换流程

1. **Notify stakeholders**: Inform users of impending cutover
   **通知相关方**：通知用户即将到来的切换

2. **Stop writes to Ceph**: Prevent new data from being written
   **停止写入 Ceph**：阻止新数据写入

3. **Final sync**: Capture any remaining changes
   **最终同步**：捕获任何剩余变更

4. **Update applications**: Point applications to OBS endpoints
   **更新应用**：将应用指向 OBS 端点

5. **Verify access**: Test application functionality with OBS
   **验证访问**：测试应用使用 OBS 的功能

### 5. Post-Migration Verification / 迁移后验证

1. **Compare object counts**: Verify all objects transferred
   **比对对象数量**：验证所有对象已传输

```bash
# Ceph object count
radosgw-admin bucket stats --bucket=<bucket>

# OBS object count
obsutil ls obs://bucket/ -du -r | grep "Objects:"
```

2. **Validate data integrity**: Compare checksums for critical data
   **验证数据完整性**：对关键数据比对校验和

3. **Test object access**: Verify GET/PUT operations work correctly
   **测试对象访问**：验证 GET/PUT 操作正常

4. **Monitor for 48 hours**: Watch for any access errors
   **监控 48 小时**：关注任何访问错误

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Connection timeout / 连接超时 | Network issues / 网络问题 | Increase timeout values / 增加超时值 |
| Object listing slow / 对象列表慢 | Large bucket / 大桶 | Use parallel listing / 使用并行列表 |
| Checksum mismatch / 校验和不匹配 | Transfer corruption / 传输损坏 | Re-copy affected objects / 重新复制受影响对象 |
| Permission denied / 权限拒绝 | IAM policy issues / IAM 策略问题 | Review OBS bucket policies / 审查 OBS 桶策略 |
| Metadata lost / 元数据丢失 | Different metadata handling / 元数据处理不同 | Manually copy critical metadata / 手动复制关键元数据 |

## Huawei Cloud OBS Specifics / 华为云 OBS 详情

### Storage Classes / 存储类别
- **Standard**: Hot data, frequent access / 热数据，频繁访问
- **Warm**: Infrequent access, >30 days / 低频访问，>30 天
- **Cold**: Rarely accessed, >90 days / 很少访问，>90 天

### Data Formats / 数据格式
- **Object**: Single file entity with metadata / 带元数据的单个文件实体
- **Folder**: Logical grouping (not actual) / 逻辑分组（非实际）
- **Multipart**: For large files >5GB / 用于大于 5GB 的大文件

### Migration Tools / 迁移工具
- **obsutil**: CLI tool for OBS management / OBS 管理 CLI 工具
- **rclone**: Multi-cloud sync tool / 多云同步工具
- **Data Migration Service (DMS)**: Managed migration service / 托管迁移服务

## Best Practices / 最佳实践

1. **Always validate** before deleting source data / 在删除源数据前务必验证
2. **Use parallel transfers** for large datasets / 大数据集使用并行传输
3. **Set appropriate expiration** on pre-signed URLs / 预签名 URL 设置适当的过期时间
4. **Test with subset** before full migration / 完整迁移前用子集测试
5. **Document bucket policies** and ACLs for reference / 记录桶策略和 ACL 以供参考
