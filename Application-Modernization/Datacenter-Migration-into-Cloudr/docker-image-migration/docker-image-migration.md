---
name: docker-image-migration
description: Docker 镜像迁移技能，用于华为云。适用于：(1) 将 Docker 镜像从其他平台迁移到华为云 SWR，(2) 打包和传输容器镜像，(3) 在华为云重新部署镜像，(4) 排查镜像迁移问题。 Docker image migration skill for Huawei Cloud. Use when (1) Migrating Docker images from other platforms to Huawei Cloud SWR, (2) Packaging and transferring container images, (3) Redeploying images on Huawei Cloud, (4) Troubleshooting image migration issues.
---

# Docker Image Migration / Docker 镜像迁移

## Overview / 概述

This skill provides guidance for migrating Docker container images to Huawei Cloud SWR (Software Repository for Containers). It covers the complete migration workflow including image preparation, transfer, and redeployment.

本技能提供将 Docker 容器镜像迁移到华为云 SWR（容器镜像服务）的指导。涵盖完整的迁移工作流程，包括镜像准备、传输和重新部署。

## Migration Prerequisites / 迁移前置条件

- Docker CLI installed on migration machine / 迁移机器上已安装 Docker CLI
- Source registry accessible (Docker Hub, ACR, GCR, private registry) / 源镜像仓库可访问（Docker Hub、ACR、GCR、私有仓库）
- Target Huawei Cloud SWR instance created / 目标华为云 SWR 实例已创建
- Network connectivity for image transfer / 用于镜像传输的网络连接
- Appropriate SWR permissions / 适当的 SWR 权限

## Migration Workflow / 迁移工作流程

### 1. Pre-Migration Assessment / 迁移前评估

1. **Inventory images**: List all images to be migrated
   **清点镜像**：列出所有待迁移镜像

```bash
# List local images
docker images

# List images in source registry (example for ACR)
az acr repository list --name <registry-name>
```

2. **Document image details**: Capture tags, sizes, digests
   **记录镜像详情**：捕获标签、大小、摘要

3. **Identify dependencies**: Note base images and layers
   **识别依赖**：注意基础镜像和层

4. **Plan image namespace**: Design SWR organization
   **规划镜像命名空间**：设计 SWR 组织结构

### 2. Preparation / 准备工作

1. **Create SWR organization**: Set up organization/namespace
   **创建 SWR 组织**：设置组织/命名空间

2. **Configure authentication**: Set up SWR login credentials
   **配置认证**：设置 SWR 登录凭证

```bash
# Login to SWR
docker login -u <username> -p <password> swr.<region>.myhuaweicloud.com
```

3. **Install tools**: Ensure docker, crane, or skopeo available
   **安装工具**：确保 docker、crane 或 skopeo 可用

### 3. Image Transfer Methods / 镜像传输方法

#### Method A: Direct Push / 方法一：直接推送

1. **Pull image from source**: Download to local
   **从源拉取镜像**：下载到本地

```bash
# Pull from Docker Hub
docker pull source-image:tag

# Pull from other registries
docker pull registry.example.com/source-image:tag
```

2. **Tag for SWR**: Retag for target repository
   **为 SWR 打标签**：为目标仓库重新打标签

```bash
docker tag source-image:tag swr.<region>.myhuaweicloud.com/<namespace>/image:tag
```

3. **Push to SWR**: Upload image
   **推送到 SWR**：上传镜像

```bash
docker push swr.<region>.myhuaweicloud.com/<namespace>/image:tag
```

#### Method B: Using crane / 方法二：使用 crane

1. **Install crane**: Get tool for image transfer
   **安装 crane**：获取镜像传输工具

```bash
# Download crane
wget https://github.com/google/go-containerregistry/releases/latest/download/crane-linux-amd64
chmod +x crane
mv crane /usr/local/bin/
```

2. **Copy image**: Direct transfer between registries
   **复制镜像**：镜像仓库间直接传输

```bash
crane copy source-registry/image:tag swr.<region>.myhuaweicloud.com/<namespace>/image:tag
```

#### Method C: Using skopeo / 方法三：使用 skopeo

1. **Install skopeo**: Get tool for image inspection and copy
   **安装 skopeo**：获取镜像检查和复制工具

```bash
# Install skopeo
yum install -y skopeo  # RHEL/CentOS
# or
apt-get install -y skopeo  # Debian/Ubuntu
```

2. **Copy image**: Transfer between registries
   **复制镜像**：在镜像仓库间传输

```bash
skopeo copy docker://source-registry/image:tag docker://swr.<region>.myhuaweicloud.com/<namespace>/image:tag
```

### 4. Batch Migration / 批量迁移

For migrating multiple images: / 迁移多个镜像：

1. **Create migration script**: Automate the process
   **创建迁移脚本**：自动化处理

```bash
#!/bin/bash
# migrate_images.sh

SOURCE_REGISTRY="source.example.com"
TARGET_REGISTRY="swr.<region>.myhuaweicloud.com"
NAMESPACE="my-namespace"
IMAGES=("image1:v1" "image2:v2" "image3:latest")

for image in "${IMAGES[@]}"; do
    echo "Migrating $image..."
    crane copy "${SOURCE_REGISTRY}/${image}" "${TARGET_REGISTRY}/${NAMESPACE}/${image}"
done
```

2. **Execute script**: Run batch migration
   **执行脚本**：运行批量迁移

3. **Verify transfers**: Check all images in SWR
   **验证传输**：检查 SWR 中的所有镜像

### 5. Helm Chart Migration / Helm 图表迁移

For chart-based deployments: / 基于图表的部署：

1. **Pull Helm chart**: Download chart package
   **拉取 Helm 图表**：下载图表包

```bash
helm pull <chart-repo>/<chart-name>
```

2. **Update image references**: Modify image tags if needed
   **更新镜像引用**：如需要修改镜像标签

3. **Push to SWR**: Upload chart to SWR
   **推送到 SWR**：上传图表到 SWR

### 6. Post-Migration Verification / 迁移后验证

1. **List SWR repositories**: Verify all images present
   **列出 SWR 仓库**：验证所有镜像存在

```bash
# List repositories in namespace
az acr repository list --name <swr-name> --namespace <namespace>
```

2. **Pull test image**: Verify image integrity
   **拉取测试镜像**：验证镜像完整性

```bash
docker pull swr.<region>.myhuaweicloud.com/<namespace>/image:tag
docker run --rm swr.<region>.myhuaweicloud.com/<namespace>/image:tag --version
```

3. **Check image layers**: Verify layer integrity
   **检查镜像层**：验证层完整性

4. **Test deployment**: Deploy to CCE cluster
   **测试部署**：部署到 CCE 集群

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Authentication failed / 认证失败 | Invalid credentials / 凭证无效 | Regenerate SWR login token / 重新生成 SWR 登录令牌 |
| Image size too large / 镜像太大 | Large image layers / 大镜像层 | Use multi-stage builds to reduce size / 使用多阶段构建减小大小 |
| Network timeout / 网络超时 | Slow transfer / 传输慢 | Use smaller batch sizes or faster connection / 使用更小批次或更快连接 |
| Layer already exists / 层已存在 | Duplicate layer / 重复层 | This is normal, transfer should continue / 这是正常的，传输应继续 |
| Architecture mismatch / 架构不匹配 | Cross-architecture image / 跨架构镜像 | Build platform-specific images or use manifest lists / 构建平台特定镜像或使用 manifest 列表 |

## Huawei Cloud SWR Specifics / 华为云 SWR 详情

### Features / 功能
- **Organization management**: Namespace isolation / 组织管理：命名空间隔离
- **Image versioning**: Tag-based versioning / 镜像版本控制：基于标签的版本控制
- **Vulnerability scanning**: Security scanning for images / 漏洞扫描：镜像安全扫描
- **Access control**: IAM-based permissions / 访问控制：基于 IAM 的权限

### Supported Registries / 支持的镜像仓库
- **Docker Hub**: Public images / 公共镜像
- **ACR (Azure Container Registry)**: Azure registries / Azure 镜像仓库
- **GCR (Google Container Registry)**: Google registries / Google 镜像仓库
- **ECR (Amazon ECR)**: AWS registries / AWS 镜像仓库
- **Private registries**: Other private registries / 私有镜像仓库

### Integration / 集成
- **CCE (Cloud Container Engine)**: Direct deployment to clusters / 直接部署到集群
- **IEF (Intelligent Edge Fabric)**: Edge deployment / 边缘部署
- **AppStage**: Application lifecycle management / 应用生命周期管理

## Best Practices / 最佳实践

1. **Use multi-stage builds** to reduce image size / 使用多阶段构建减小镜像大小
2. **Clean up unused images** before migration / 迁移前清理未使用的镜像
3. **Tag with versioning** for easy rollback / 使用版本控制标签以便回滚
4. **Scan images for vulnerabilities** after migration / 迁移后扫描镜像漏洞
5. **Document image sources** for future reference / 记录镜像源以供将来参考
