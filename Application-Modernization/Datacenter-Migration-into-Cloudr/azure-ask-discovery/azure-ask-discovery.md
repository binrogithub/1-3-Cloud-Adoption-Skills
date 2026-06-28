---
name: azure-ask-discovery
description: Azure ASK (App Service Kubernetes) 发现与评估技能。适用于：(1) 发现 Azure ASK 环境和配置，(2) 评估应用和依赖关系，(3) 规划迁移到华为云容器服务，(4) 分析容器化应用兼容性。Azure ASK (App Service Kubernetes) discovery and assessment skill. Use when (1) Discovering Azure ASK environment and configurations, (2) Assessing applications and dependencies, (3) Planning migration to Huawei Cloud container services, (4) Analyzing containerized application compatibility.
---

# Azure ASK Discovery / Azure ASK 发现与评估

## Overview / 概述

This skill provides guidance for discovering, analyzing, and assessing Azure App Service Kubernetes (ASK) environments in preparation for migration to Huawei Cloud. It covers environment scanning, dependency mapping, and compatibility assessment.

本技能提供发现、分析和评估 Azure App Service Kubernetes (ASK) 环境的指导，为迁移到华为云做准备。涵盖环境扫描、依赖关系映射和兼容性评估。

## Discovery Prerequisites / 发现前置条件

- Azure CLI access configured / Azure CLI 已配置
- Appropriate Azure subscriptions and permissions / 适当的 Azure 订阅和权限
- Network access to Azure resources / 网络可访问 Azure 资源
- Assessment tools ready (azure CLI, kubectl, discovery scripts) / 评估工具就绪（azure CLI、kubectl、发现脚本）

## Discovery Workflow / 发现工作流程

### 1. Environment Overview / 环境概览

1. **List Azure subscriptions**: Identify all relevant subscriptions
   **列出 Azure 订阅**：识别所有相关订阅

```bash
az account list --output table
```

2. **Identify ASK clusters**: Find all App Service Kubernetes environments
   **识别 ASK 集群**：查找所有 App Service Kubernetes 环境

3. **Get resource groups**: List resource groups containing ASK resources
   **获取资源组**：列出包含 ASK 资源的资源组

```bash
az resource list --resource-type Microsoft.Web/kubeEnvironments
```

### 2. Cluster Configuration Discovery / 集群配置发现

1. **Get cluster details**: Retrieve ASK cluster configuration
   **获取集群详情**：获取 ASK 集群配置

```bash
az aks show --resource-group <rg-name> --name <cluster-name>
```

2. **List node pools**: Identify node pool configurations
   **列出节点池**：识别节点池配置

3. **Check Kubernetes version**: Verify Kubernetes version and upgrade path
   **检查 Kubernetes 版本**：验证 Kubernetes 版本和升级路径

4. **Retrieve ingress and networking**: Document ingress controllers and network policies
   **获取入口和网络配置**：记录入口控制器和网络策略

### 3. Application Discovery / 应用发现

1. **List deployed applications**: Identify all web apps and their configurations
   **列出已部署应用**：识别所有 Web 应用及其配置

```bash
az webapp list --resource-group <rg-name>
```

2. **Get app settings**: Retrieve application settings and connection strings
   **获取应用设置**：获取应用设置和连接字符串

```bash
az webapp config appsettings list --resource-group <rg-name> --name <app-name>
```

3. **Document dependencies**: Map external service dependencies
   **记录依赖关系**：映射外部服务依赖

### 4. Container and Image Discovery / 容器和镜像发现

1. **List container images**: Identify all container images in use
   **列出容器镜像**：识别所有使用的容器镜像

```bash
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}'
```

2. **Check image registries**: Document used container registries
   **检查镜像仓库**：记录使用的容器仓库

3. **Analyze Dockerfile**: If available, review Dockerfile configurations
   **分析 Dockerfile**：如有 Dockerfile，审查其配置

### 5. Dependency Mapping / 依赖关系映射

1. **Map internal dependencies**: Identify service-to-service dependencies
   **映射内部依赖**：识别服务间依赖关系

2. **Document external services**: Record database, cache, and API dependencies
   **记录外部服务**：记录数据库、缓存和 API 依赖

3. **Identify persistent storage**: Note PVC and storage requirements
   **识别持久存储**：记录 PVC 和存储需求

4. **Map network flows**: Document ingress/egress traffic patterns
   **映射网络流量**：记录入口/出口流量模式

## Assessment Criteria / 评估标准

### Compatibility Assessment / 兼容性评估

| Component / 组件 | Assessment Items / 评估项 | Huawei Cloud Alternative / 华为云替代 |
|------------------|---------------------------|--------------------------------------|
| Kubernetes / Kubernetes | K8s version, API compatibility / K8s 版本、API 兼容性 |CCE (Cloud Container Engine) / CCE (云容器引擎)|
| Container Registry / 容器仓库 | ACR, image formats / ACR、镜像格式 | SWR (Software Repository for Container) / SWR (容器镜像服务) |
| Load Balancer / 负载均衡 | Azure Load Balancer, Application Gateway / Azure 负载均衡器、应用网关 | ELB, APIG / ELB、APIG |
| Persistent Storage / 持久存储 | Azure Disk, Files / Azure 云盘、文件存储 | EVS, SFS / 云硬盘、文件存储 |
| DNS / DNS | Azure DNS, Custom DNS / Azure DNS、自定义 DNS | DNS / DNS |

### Migration Complexity Rating / 迁移复杂度评级

1. **Low**: Standard containers, no persistent storage, no complex networking
   **低**：标准容器，无持久存储，无复杂网络

2. **Medium**: Some persistent storage, standard networking, few dependencies
   **中**：部分持久存储，标准网络，少量依赖

3. **High**: Complex networking, multiple dependencies, stateful applications
   **高**：复杂网络，多重依赖，有状态应用

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Image compatibility / 镜像兼容性 | Architecture differences / 架构差异 | Rebuild images for x86_64/arm64 / 为 x86_64/arm64 重建镜像 |
| Secret management / 密钥管理 | Different secrets solutions / 不同的密钥方案 | Migrate to Huawei Cloud Secret Manager / 迁移到华为云密钥管理服务 |
| Ingress differences / 入口差异 | Different ingress implementations / 不同的入口实现 | Use Huawei Cloud ingress controller / 使用华为云入口控制器 |
| Storage class mismatch / 存储类不匹配 | Different storage provisioners / 不同的存储提供程序 | Create matching storage classes / 创建匹配的存储类 |

## Best Practices / 最佳实践

1. **Perform discovery in non-production** to avoid impact / 在非生产环境执行发现以避免影响
2. **Capture all configurations** before starting migration / 开始迁移前捕获所有配置
3. **Prioritize applications** based on complexity and business value / 根据复杂度和业务价值对应用排序
4. **Create detailed assessment reports** for each application / 为每个应用创建详细评估报告
5. **Test in staging** before production migration / 生产迁移前在预发环境测试
