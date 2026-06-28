---
name: linux-server-migration
description: Linux 服务器迁移技能，用于华为云。适用于：(1) 将 Linux 服务器迁移到华为云 ECS，(2) 配置 Linux 工作负载迁移，(3) 验证迁移后系统可用性和数据完整性，(4) 排查 Linux 迁移问题。 Linux server migration skill for Huawei Cloud. Use when (1) Migrating Linux servers to Huawei Cloud ECS, (2) Configuring Linux workload migration, (3) Verifying post-migration system availability and data integrity, (4) Troubleshooting Linux migration issues.
---

# Linux Server Migration / Linux 服务器迁移

## Overview / 概述

This skill provides guidance for migrating Linux servers to Huawei Cloud ECS. It covers the complete migration workflow including pre-migration assessment, migration execution, and post-migration verification.

本技能提供将 Linux 服务器迁移到华为云 ECS 的指导。涵盖完整的迁移工作流程，包括迁移前评估、迁移执行和迁移后验证。

## Migration Prerequisites / 迁移前置条件

- Source Linux server accessible via SSH / 源端 Linux 服务器可通过 SSH 访问
- Target Huawei Cloud ECS with Linux image provisioned / 目标华为云 ECS（Linux 镜像）已创建
- Network connectivity between source and Huawei Cloud / 源与华为云之间网络连通
- Migration tool readiness (SMS, or manual migration) / 迁移工具就绪（SMS 或手动迁移）
- Backup of source server completed / 源服务器备份已完成

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory Linux servers**: List all servers to be migrated
   **清点 Linux 服务器**：列出所有待迁移服务器

2. **Document system info**: Capture OS version, kernel, hardware specs
   **记录系统信息**：捕获 OS 版本、内核、硬件规格

```bash
# Get system information
uname -a
cat /etc/os-release
cat /etc/redhat-release  # For RHEL/CentOS

# Get hardware info
lscpu
free -h
df -h
```

3. **Identify applications**: List all installed packages and services
   **识别应用**：列出所有已安装包和服务

```bash
# List installed packages (Debian/Ubuntu)
dpkg -l

# List installed packages (RHEL/CentOS)
rpm -qa

# List running services
systemctl list-units --type=service --state=running
```

4. **Check dependencies**: Identify network and storage dependencies
   **检查依赖**：识别网络和存储依赖

### 2. Preparation / 准备工作

1. **Create target ECS**: Provision Linux instance on Huawei Cloud
   **创建目标 ECS**：在华为云上配置 Linux 实例

2. **Configure networking**: Set up VPC, security groups,弹性 IP
   **配置网络**：设置 VPC、安全组、弹性 IP

3. **Prepare migration tool**: Set up SMS agent or alternative
   **准备迁移工具**：设置 SMS agent 或替代工具

4. **Create backup**: Take snapshot of source server
   **创建备份**：拍摄源服务器快照

### 3. Migration Methods / 迁移方法

#### Method A: Using SMS (Server Migration Service) / 方法一：使用 SMS（服务器迁移服务）

1. **Install SMS agent**: Deploy agent on source server
   **安装 SMS agent**：在源服务器部署 agent

```bash
# Download and install agent
wget https://sms-agent-package-url
sudo dpkg -i sms-agent.deb  # Debian/Ubuntu
# or
sudo rpm -ivh sms-agent.rpm  # RHEL/CentOS
```

2. **Create migration task**: Configure migration in console
   **创建迁移任务**：在控制台配置迁移

3. **Start migration**: Initiate the migration
   **开始迁移**：启动迁移

4. **Monitor progress**: Track migration status
   **监控进度**：跟踪迁移状态

#### Method B: Manual Migration / 方法二：手动迁移

1. **Create custom image**: Capture source server
   **创建自定义镜像**：捕获源服务器

```bash
# For cloud-init based images
cloud-init clean -l
```

2. **Transfer data**: Copy using rsync or tar
   **传输数据**：使用 rsync 或 tar 复制

```bash
# Using rsync for data migration
rsync -avz --progress /data/ user@target:/data/
```

3. **Deploy to ECS**: Launch instance from image
   **部署到 ECS**：从镜像启动实例

4. **Configure new instance**: Set up hostname, IP, etc.
   **配置新实例**：设置主机名、IP 等

### 4. System Configuration / 系统配置

1. **Update network config**: Set up networking on target
   **更新网络配置**：在目标设置网络

```bash
# Update hostname
sudo hostnamectl set-hostname new-hostname

# Update /etc/hosts
sudo vi /etc/hosts
```

2. **Configure drives**: Set up fstab for any new volumes
   **配置存储**：为新卷设置 fstab

```bash
# Get UUID of new volume
sudo blkid

# Add to /etc/fstab
UUID=<uuid> /data ext4 defaults 0 2
```

3. **Update DNS**: Configure resolv.conf
   **更新 DNS**：配置 resolv.conf

4. **Regenerate SSH host keys**: For new server
   **重新生成 SSH 主机密钥**：为新服务器

```bash
sudo ssh-keygen -A
```

### 5. Application Migration / 应用迁移

1. **Reinstall applications**: Install required packages on target
   **重新安装应用**：在目标安装所需包

```bash
# For Debian/Ubuntu
sudo apt-get install package1 package2

# For RHEL/CentOS
sudo yum install package1 package2
```

2. **Migrate configurations**: Copy config files and settings
   **迁移配置**：复制配置文件和设置

3. **Migrate data**: Copy application data
   **迁移数据**：复制应用数据

4. **Update connections**: Point apps to new infrastructure
   **更新连接**：将应用指向新基础设施

### 6. Data Migration / 数据迁移

1. **Identify data locations**: Find all data to migrate
   **识别数据位置**：找出所有要迁移的数据

2. **Choose transfer method**: Use appropriate tool
   **选择传输方法**：使用适当的工具

```bash
# Rsync for file migration
rsync -avz --progress /data/ user@target:/data/

# Tar over SSH
tar -czf - /data/ | ssh user@target "tar -xzf - -C /data/"
```

3. **Verify data integrity**: Ensure all data transferred
   **验证数据完整性**：确保所有数据已传输

### 7. Cutover / 切换

1. **Schedule maintenance window**: Notify users
   **安排维护窗口**：通知用户

2. **Stop services**: Stop services on source
   **停止服务**：停止源端服务

3. **Final data sync**: Capture remaining changes
   **最终数据同步**：捕获剩余变更

4. **Update DNS**: Point to new ECS
   **更新 DNS**：指向新 ECS

5. **Start services**: Bring up services on target
   **启动服务**：在目标启动服务

### 8. Post-Migration Verification / 迁移后验证

1. **Verify system functionality**: Check OS and services
   **验证系统功能**：检查 OS 和服务

```bash
# Check running services
systemctl list-units --type=service --state=running

# Check disk space
df -h
```

2. **Test applications**: Verify installed apps work
   **测试应用**：验证已安装应用工作

3. **Check networking**: Ensure connectivity
   **检查网络**：确保连接

```bash
# Test connectivity
ping -c 4 8.8.8.8
curl -I https://www.huaweicloud.com
```

4. **Validate data**: Confirm all data present
   **验证数据**：确认所有数据存在

5. **Monitor for issues**: Watch for 48 hours
   **监控问题**：观察 48 小时

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| NIC naming changed / 网卡名称改变 | Different hypervisor drivers / 不同虚拟机管理程序驱动 | Rename interface or update config / 重命名接口或更新配置 |
| UUID conflicts / UUID 冲突 | Duplicate system UUID / 重复系统 UUID | Regenerate machine-id / 重新生成 machine-id |
| LVM issues / LVM 问题 | Different volume configuration / 不同卷配置 | Re-scan and activate volumes / 重新扫描并激活卷 |
| SELinux issues / SELinux 问题 | Security context not preserved / 安全上下文未保留 | Relabel or disable SELinux / 重新标记或禁用 SELinux |
| Module loading issues / 模块加载问题 | Missing kernel modules / 缺失内核模块 | Install cloud-init or hyperv drivers / 安装 cloud-init 或 hyperv 驱动 |

## Huawei Cloud Linux on ECS / 华为云 ECS 上的 Linux

### Supported Distributions / 支持的发行版
- **Ubuntu**, **CentOS**, **Debian**, **SUSE**, **Rocky Linux**, **Alibaba Cloud Linux**

### Required Agents / 所需 Agent
- **cloud-init**: For instance initialization / 用于实例初始化
- **VirtIO drivers**: For network and storage / 用于网络和存储
- **Huawei Cloud agent**: For enhanced management / 用于增强管理

### Instance Types / 实例类型
- **General purpose (S)**: Standard workloads / 标准工作负载
- **Memory optimized (M)**: Database and memory-intensive / 数据库和内存密集型
- **CPU optimized (C)**: Compute intensive / 计算密集型
- **Ultra-high I/O (I)**: SSD storage for I/O intensive / SSD 存储用于 IO 密集型

### Migration Tools / 迁移工具
- **SMS (Server Migration Service)**: Automated migration / 自动化迁移
- **手动迁移**: Using custom images / 使用自定义镜像
- **Cloud Server Migration Center**: For large-scale migrations / 用于大规模迁移

## Best Practices / 最佳实践

1. **Always test** migration in non-production first / 先在非生产环境测试迁移
2. **Document everything** before starting migration / 开始迁移前记录一切
3. **Use cloud-init** for automated configuration / 使用 cloud-init 进行自动化配置
4. **Keep source available** for rollback / 保持源可用以便回滚
5. **Test applications thoroughly** after migration / 迁移后彻底测试应用
