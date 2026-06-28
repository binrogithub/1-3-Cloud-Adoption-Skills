---
name: cross-az-server-migration
description: 跨可用区（AZ）服务器迁移技能，用于华为云。适用于：(1) 将服务器从一处可用区迁移到另一处，(2) 在可用区之间迁移虚拟机，(3) 规划零停机迁移策略，(4) 验证迁移后服务可用性。 Cross-AZ (Availability Zone) server migration skill for Huawei Cloud. Use when (1) Migrating servers from one AZ to another, (2) Moving virtual machines between AZs, (3) Planning zero-downtime migration strategies, (4) Verifying post-migration service availability.
---

# Cross-AZ Server Migration / 跨可用区服务器迁移

## Overview / 概述

This skill provides guidance for migrating servers (VMs) between Huawei Cloud Availability Zones (AZs). It covers the complete migration workflow including planning, execution, and verification.

本技能提供在华为云可用区（AZ）之间迁移服务器（VM）的指导。涵盖完整的迁移工作流程，包括规划、执行和验证。

## Migration Prerequisites / 迁移前置条件

- Source ECS instances running / 源端 ECS 实例运行中
- Target AZ with sufficient capacity / 目标 AZ 有足够容量
- Same VPC accessible in target AZ / 目标 AZ 可访问相同 VPC
- Proper IAM permissions / 适当的 IAM 权限
- Backup or snapshot of source instances / 源实例的备份或快照

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Planning / 迁移前规划

1. **Inventory servers**: List all servers to be migrated
   **清点服务器**：列出所有待迁移服务器

```bash
# List ECS instances
ecs-cli cs instances --cluster <cluster-name>
```

2. **Assess dependencies**: Identify application and network dependencies
   **评估依赖**：识别应用和网络依赖

3. **Select migration strategy**: Choose based on downtime tolerance
   **选择迁移策略**：根据停机容忍度选择

4. **Plan target configuration**: Design target AZ resource layout
   **规划目标配置**：设计目标 AZ 资源布局

### 2. Migration Strategies / 迁移策略

#### Strategy A: Stop and Migrate / 停止并迁移 (Higher downtime)
For non-critical workloads with acceptable downtime: / 用于可接受停机时间的非关键工作负载：

1. **Create snapshots** of source instances
   **创建源实例快照**

2. **Stop applications** gracefully
   **优雅停止应用**

3. **Create new instances** from snapshots in target AZ
   **从快照在目标 AZ 创建新实例**

4. **Reconfigure networking** as needed
   **根据需要重新配置网络**

#### Strategy B: Replica Migration / 副本迁移 (Minimal downtime)
For production workloads requiring high availability: / 用于需要高可用性的生产工作负载：

1. **Create disk replicas** in target AZ
   **在目标 AZ 创建磁盘副本**

2. **Start standby instances** in target AZ
   **在目标 AZ 启动待机实例**

3. **Configure replication** for data sync
   **配置复制实现数据同步**

4. **Perform cutover** when replica is current
   **当副本最新时执行切换**

### 3. Execution / 执行

1. **Create backup snapshots**: Safeguard source data
   **创建备份快照**：保护源数据

```bash
# Create snapshot
ecs-cli snapshot create --disk-id <disk-id> --name <snapshot-name>
```

2. **Deploy target instances**: Create instances in target AZ
   **部署目标实例**：在目标 AZ 创建实例

3. **Configure networking**: Set up networking in target AZ
   **配置网络**：在目标 AZ 设置网络

4. **Install and configure applications**: Set up application stack
   **安装和配置应用**：设置应用栈

5. **Configure monitoring**: Set up monitoring for new instances
   **配置监控**：为新实例设置监控

### 4. Data Synchronization / 数据同步

For stateful servers, synchronize data: / 对于有状态服务器，同步数据：

1. **Sync application data**: Copy databases, files, configurations
   **同步应用数据**：复制数据库、文件、配置

2. **Verify data consistency**: Ensure data matches between source and target
   **验证数据一致性**：确保源和目标数据一致

3. **Update connection strings**: Point applications to new instance
   **更新连接字符串**：将应用指向新实例

### 5. Cutover / 切换

1. **Schedule maintenance window**: Notify users of downtime
   **安排维护窗口**：通知用户停机时间

2. **Stop source applications**: Prevent new writes
   **停止源应用**：阻止新写入

3. **Final data sync**: Capture last changes
   **最终数据同步**：捕获最后变更

4. **Start target applications**: Bring up services in target AZ
   **启动目标应用**：在目标 AZ 启动服务

5. **Update DNS/Load Balancer**: Point to new instances
   **更新 DNS/负载均衡器**：指向新实例

### 6. Post-Migration Verification / 迁移后验证

1. **Verify instance health**: Check instance status and metrics
   **验证实例健康**：检查实例状态和指标

2. **Test application functionality**: Verify all services running
   **测试应用功能**：验证所有服务运行

3. **Check network connectivity**: Ensure VPC and security group rules
   **检查网络连接**：确保 VPC 和安全组规则

4. **Monitor for 24-48 hours**: Watch for issues
   **监控 24-48 小时**：关注问题

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Insufficient quota / 配额不足 | Target AZ capacity / 目标 AZ 容量 | Request quota increase or use different AZ / 申请增加配额或使用不同 AZ |
| Network connectivity lost / 网络连接丢失 | Different subnet / 不同子网 | Recreate networking or use VPC peering / 重建网络或使用 VPC 对等连接 |
| Performance degradation / 性能下降 | Different host hardware / 不同主机硬件 | Monitor and scale if needed / 监控并根据需要扩展 |
| Security group mismatch / 安全组不匹配 | Different SG configuration / 不同 SG 配置 | Recreate SG rules in target AZ / 在目标 AZ 重建 SG 规则 |

## Huawei Cloud ECS Specifics / 华为云 ECS 详情

### Instance Types / 实例类型
- **General purpose (S)**: Balance of CPU and memory / CPU 和内存平衡
- **Memory optimized (M)**: High memory for databases / 数据库高内存
- **CPU optimized (C)**: High compute for processing / 处理高计算
- **Ultra-high I/O (I)**: SSD storage for I/O intensive / SSD 存储用于 IO 密集型

### Available AZs / 可用 AZ
- Different AZs in same region provide fault isolation / 同一区域不同 AZ 提供故障隔离
- AZs are physically separated / AZ 之间物理隔离
- Network latency between AZs typically < 2ms / AZ 之间网络延迟通常 < 2ms

### Migration Tools / 迁移工具
- **IMS (Image Management Service)**: Create镜像 for consistent deployment / 创建镜像以保证一致部署
- **CRS (Server Replication Service)**: Real-time replication between AZs / AZ 间实时复制
- **BMS (Bare Metal Server)**: For physical server migration / 用于物理服务器迁移

## Best Practices / 最佳实践

1. **Always create snapshots** before migration / 迁移前务必创建快照
2. **Test migration** in non-production first / 先在非生产环境测试迁移
3. **Document all changes** during migration / 记录迁移期间的所有变更
4. **Plan for rollback** in case of issues / 准备回滚方案以防问题
5. **Schedule during low-traffic** periods for production / 生产环境安排在低流量时段
