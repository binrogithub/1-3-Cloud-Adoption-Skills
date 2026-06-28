---
name: windows-server-migration
description: Windows 服务器迁移技能，用于华为云。适用于：(1) 将 Windows 服务器迁移到华为云 ECS，(2) 配置 Windows 工作负载迁移，(3) 验证迁移后系统可用性和数据完整性，(4) 排查 Windows 迁移问题。 Windows server migration skill for Huawei Cloud. Use when (1) Migrating Windows servers to Huawei Cloud ECS, (2) Configuring Windows workload migration, (3) Verifying post-migration system availability and data integrity, (4) Troubleshooting Windows migration issues.
---

# Windows Server Migration / Windows 服务器迁移

## Overview / 概述

This skill provides guidance for migrating Windows servers to Huawei Cloud ECS. It covers the complete migration workflow including pre-migration assessment, migration execution, and post-migration verification.

本技能提供将 Windows 服务器迁移到华为云 ECS 的指导。涵盖完整的迁移工作流程，包括迁移前评估、迁移执行和迁移后验证。

## Migration Prerequisites / 迁移前置条件

- Source Windows server accessible / 源端 Windows 服务器可访问
- Target Huawei Cloud ECS with Windows image provisioned / 目标华为云 ECS（Windows 镜像）已创建
- Network connectivity between source and Huawei Cloud / 源与华为云之间网络连通
- Migration tool readiness (SMS, or manual migration) / 迁移工具就绪（SMS 或手动迁移）
- Backup of source server completed / 源服务器备份已完成

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory Windows servers**: List all servers to be migrated
   **清点 Windows 服务器**：列出所有待迁移服务器

2. **Document system info**: Capture OS version, hardware specs
   **记录系统信息**：捕获 OS 版本、硬件规格

```powershell
# Get system information
Get-ComputerInfo | Select-Object WindowsProductName, OsHardwareAbstractionLayer, CsProcessors, CsTotalPhysicalMemory

# Get installed roles and features
Get-WindowsFeature
```

3. **Identify applications**: List all installed applications
   **识别应用**：列出所有已安装应用

```powershell
# List installed programs
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* | Select DisplayName, DisplayVersion, Publisher
```

4. **Check dependencies**: Identify network and storage dependencies
   **检查依赖**：识别网络和存储依赖

### 2. Preparation / 准备工作

1. **Create target ECS**: Provision Windows instance on Huawei Cloud
   **创建目标 ECS**：在华为云上配置 Windows 实例

2. **Configure networking**: Set up VPC, security groups
   **配置网络**：设置 VPC、安全组

3. **Prepare migration tool**: Set up SMS agent or alternative
   **准备迁移工具**：设置 SMS agent 或替代工具

4. **Create backup**: Take snapshot of source server
   **创建备份**：拍摄源服务器快照

### 3. Migration Methods / 迁移方法

#### Method A: Using SMS (Server Migration Service) / 方法一：使用 SMS（服务器迁移服务）

1. **Install SMS agent**: Deploy agent on source server
   **安装 SMS agent**：在源服务器部署 agent

2. **Create migration task**: Configure migration in console
   **创建迁移任务**：在控制台配置迁移

3. **Start migration**: Initiate the migration
   **开始迁移**：启动迁移

4. **Monitor progress**: Track migration status
   **监控进度**：跟踪迁移状态

#### Method B: Manual Migration / 方法二：手动迁移

1. **Sysprep source**: Generalize source system
   **Sysprep 源端**：通用化源系统

```powershell
C:\Windows\System32\Sysprep\sysprep.exe /generalize /shutdown
```

2. **Create image**: Capture generalized VM
   **创建镜像**：捕获通用化 VM

3. **Deploy to ECS**: Launch instance from image
   **部署到 ECS**：从镜像启动实例

4. **Configure new instance**: Set up hostname, IP, etc.
   **配置新实例**：设置主机名、IP 等

### 4. Application Migration / 应用迁移

1. **Reinstall applications**: Install required software on target
   **重新安装应用**：在目标安装所需软件

2. **Migrate configurations**: Copy config files and settings
   **迁移配置**：复制配置文件和设置

3. **Migrate data**: Copy application data
   **迁移数据**：复制应用数据

4. **Update connections**: Point apps to new infrastructure
   **更新连接**：将应用指向新基础设施

### 5. Data Migration / 数据迁移

1. **Identify data locations**: Find all data to migrate
   **识别数据位置**：找出所有要迁移的数据

2. **Choose transfer method**: Use appropriate tool
   **选择传输方法**：使用适当的工具

```powershell
# Robocopy for file migration
robocopy \\source-server\share D:\Data /E /R:3 /W:5
```

3. **Verify data integrity**: Ensure all data transferred
   **验证数据完整性**：确保所有数据已传输

### 6. Cutover / 切换

1. **Schedule maintenance window**: Notify users
   **安排维护窗口**：通知用户

2. **Stop services**: Stop applications on source
   **停止服务**：停止源端应用

3. **Final data sync**: Capture remaining changes
   **最终数据同步**：捕获剩余变更

4. **Update DNS**: Point to new ECS
   **更新 DNS**：指向新 ECS

5. **Start services**: Bring up services on target
   **启动服务**：在目标启动服务

### 7. Post-Migration Verification / 迁移后验证

1. **Verify system functionality**: Check Windows features
   **验证系统功能**：检查 Windows 功能

2. **Test applications**: Verify installed apps work
   **测试应用**：验证已安装应用工作

3. **Check networking**: Ensure connectivity
   **检查网络**：确保连接

4. **Validate data**: Confirm all data present
   **验证数据**：确认所有数据存在

5. **Monitor for issues**: Watch for 48 hours
   **监控问题**：观察 48 小时

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Boot failure / 启动失败 | Incorrect driver / 错误驱动 | Install Huawei Cloud VirtIO drivers / 安装华为云 VirtIO 驱动 |
| SID conflicts / SID 冲突 | Duplicate SID / 重复 SID | Run Sysprep to generate new SID / 运行 Sysprep 生成新 SID |
| Activation issues / 激活问题 | License not transferred / 许可证未转移 | Transfer license or use KMS / 转移许可证或使用 KMS |
| Application compatibility / 应用兼容性 | Missing dependencies / 缺失依赖 | Reinstall or update applications / 重新安装或更新应用 |
| Network config issues / 网络配置问题 | Static IP not updated / 静态 IP 未更新 | Update IP configuration / 更新 IP 配置 |

## Huawei Cloud Windows on ECS / 华为云 ECS 上的 Windows

### Supported Versions / 支持的版本
- **Windows Server 2012 R2**, **2016**, **2019**, **2022**

### Required Drivers / 所需驱动
- **VirtIO drivers**: For network and storage / 用于网络和存储
- **Huawei Cloud guest drivers**: For enhanced functionality / 用于增强功能

### Instance Types / 实例类型
- **General purpose (S)**: Standard workloads / 标准工作负载
- **Memory optimized (M)**: Database and memory-intensive / 数据库和内存密集型
- **GPU optimized (G)**: Graphics and compute intensive / 图形和计算密集型

### Migration Tools / 迁移工具
- **SMS (Server Migration Service)**: Automated migration / 自动化迁移
- **手动迁移**: Using custom images / 使用自定义镜像
- **Cloud Connect**: For large-scale migrations / 用于大规模迁移

## Best Practices / 最佳实践

1. **Always test** migration in non-production first / 先在非生产环境测试迁移
2. **Document everything** before starting migration / 开始迁移前记录一切
3. **Keep source available** for rollback / 保持源可用以便回滚
4. **Test applications thoroughly** after migration / 迁移后彻底测试应用
5. **Plan for activation issues** with Windows licensing / 规划 Windows 许可激活问题
