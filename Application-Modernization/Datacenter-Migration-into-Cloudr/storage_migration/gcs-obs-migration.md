---
name: gcs-obs-migration
description: 这是一份GCS 到 OBS 迁移skill，涵盖 gsutil、Rclone 及华为云 OMS 三大主流方案。文档提供从权限配置、工具选型、执行命令到数据校验的全流程步骤，助您高效、安全地实现跨云对象存储迁移，避免数据丢失与权限陷阱。
---

# GCS 到 OBS 数据迁移技能文档

## 1. 概述
本文档旨在指导用户将数据从 Google Cloud Storage (GCS) 迁移至华为云对象存储服务 (OBS)。迁移过程主要涉及身份认证配置、工具选择、数据同步执行及校验。

> **注意**：作为 AI 助手，我无法直接执行迁移操作或生成可执行的二进制文件。以下内容均为**操作指南、脚本示例及配置结构**，请根据您的实际环境复制并执行。

---

## 2. 前置准备

### 2.1 权限配置
在开始之前，请确保您拥有足够的权限：
- **源端 (GCS)**: 拥有 `Storage Object Admin` 或 `Storage Object Viewer` 权限。
- **目标端 (OBS)**: 拥有 `OBS Administrator` 或 `OBS Operator` 权限，且目标桶（Bucket）已创建。

### 2.2 获取凭证
1. **GCS 凭证**:
   - 在 Google Cloud Console 创建 Service Account (SA)。
   - 下载 JSON 格式的密钥文件 (`gcs-sa-key.json`)。
   - 或者使用 `gcloud auth application-default login` 获取临时凭证。

2. **OBS 凭证**:
   - 在华为云控制台获取 Access Key ID 和 Secret Access Key。
   - 或者配置 `HUAWEI_CLOUD_SDK` 环境变量。

---

## 3. 迁移方案选择

根据您的数据量和网络环境，推荐以下三种方案：

| 方案 | 适用场景 | 工具/方法 | 优点 | 缺点 |
| :--- | :--- | :--- | :--- :--- |
| **方案 A** | 全量迁移，数据量 < 10TB | **gsutil** (Google 官方) | 稳定，支持断点续传 | 需安装 Google Cloud SDK |
| **方案 B** | 全量 + 增量，大数据量 | **华为云 OMS (对象存储迁移服务)** | 可视化界面，支持断点续传，自动校验 | 需开通 OMS 服务，可能有费用 |
| **方案 C** | 极客/自动化脚本 | **Python (boto3 + obs-python-sdk)** | 灵活，可定制逻辑 | 需自行编写代码，维护成本高 |

---

## 4. 详细操作步骤

### 方案 A：使用 gsutil 迁移 (推荐中小规模)

#### 4.1 安装与配置
```bash
# 安装 Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL # 刷新环境变量

# 配置 GCS 本地认证
gcloud auth activate-service-account --key-file=/path/to/gcs-sa-key.json

# 配置 OBS 远程存储 (需先安装华为云 CLI 或配置 gsutil 端点)
# 注意：gsutil 原生支持 GCS，对 OBS 支持需通过 S3 协议别名配置
gcloud config set project <Your-GCP-Project-ID>
```

#### 4.2 配置 gsutil 以连接 OBS
编辑 `~/.config/gsutil/config` (或运行 `gsutil config -o` 交互配置)，添加 OBS 端点：
```ini
[Credentials]
gs_access_key_id = <Your-OBS-AK>
gs_access_key_secret = <Your-OBS-SK>

[GSUtil]
# 关键：将 OBS 视为 S3 兼容存储
# 注意：gsutil 原生对非 S3 协议支持有限，通常建议配合 rclone 或转为 S3 协议配置
# 如果 OBS 开启了 S3 兼容性，可配置如下：
[GSUtil]
default_project_id = <Your-OBS-Project-ID>

# 更推荐的方式：将 OBS 配置为 S3 端点，然后使用 s3cp 或 rclone
# 这里演示使用 rclone 作为通用替代方案（见方案 B 补充）
```
*注：由于 `gsutil` 对华为云 OBS 原生支持不如 AWS S3 完善，**强烈建议**对于 GCS -> OBS 跨云厂商迁移，使用 **Rclone** 或 **OMS** 更稳妥。*

#### 4.3 执行迁移 (使用 Rclone 替代方案)
如果您安装了 `rclone` (跨云迁移神器)：

1. **配置源 (GCS)**:
   ```bash
   rclone config
   # 选择 new remote -> GCS -> Service Account Key File -> 输入 JSON 路径
   # 命名为：gcs_remote
   ```

2. **配置目标 (OBS)**:
   ```bash
   rclone config
   # 选择 new remote -> Huawei Cloud OBS -> AK/SK -> 输入凭证
   # 命名为：obs_remote
   ```

3. **执行迁移**:
   ```bash
   # 同步数据 (--dry-run 先预览)
   rclone sync gcs_remote:my-bucket-name obs_remote:my-bucket-name --dry-run
   
   # 正式执行
   rclone sync gcs_remote:my-bucket-name obs_remote:my-bucket-name --progress --transfers 4 --checkers 32
   ```

---

### 方案 B：使用华为云 OMS (推荐企业级/可视化)

1. **登录华为云控制台**，搜索并进入“对象存储迁移服务 (OMS)"。
2. **创建迁移任务**：
   - **源端**: 选择 "Google Cloud GCS"。
   - **目标端**: 选择 "OBS"。
   - **配置认证**: 输入 GCS 的 SA 密钥和 OBS 的 AK/SK。
   - **配置规则**: 选择要迁移的 Bucket 或特定前缀 (Prefix)。
3. **启动任务**:
   - OMS 会自行建立通道，进行全量迁移。
   - 迁移过程中，OMS 会实时显示进度条、错误日志。
   - 支持**增量迁移**：全量完成后，开启增量模式，实时同步 GCS 的新增/修改对象。
4. **校验**: 任务结束后，OMS 会自动进行校验（MD5 比对），并生成校验报告。

---

### 方案 C：Python 脚本示例 (自定义逻辑)

如果您需要完全控制迁移过程，可以使用以下 Python 代码结构。

```python
import os
import time
from google.cloud import storage as gcs_client
from obs import ObsClient

# 1. 初始化 GCS 客户端
gcs_credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'gcs-sa-key.json')
gcs_client = gcs_client.Client.from_service_account_json(gcs_credentials_path)

# 2. 初始化 OBS 客户端
obs_client = ObsClient(
    access_key_id="YOUR_OBS_AK",
    secret_access_key="YOUR_OBS_SK",
    server="obs.cn-north-4.myhuaweicloud.com" # 根据实际区域调整
)

# 3. 迁移函数
def migrate_bucket(source_bucket_name, target_bucket_name):
    # 获取 GCS 所有对象列表
    source_bucket = gcs_client.bucket(source_bucket_name)
    blobs = source_bucket.list_blobs()
    
    for blob in blobs:
        print(f"正在处理：{blob.name}")
        try:
            # 下载 GCS 对象内容到内存
            content = blob.download_as_bytes()
            
            # 上传到 OBS
            # 注意：ObsClient.putObject 需要流或文件路径，这里简化为字节流处理
            # 实际大规模传输建议分块上传 (chunk upload)
            obs_client.putObject(target_bucket_name, blob.name, content)
            
            print(f"成功迁移：{blob.name}")
        except Exception as e:
            print(f"迁移失败 {blob.name}: {str(e)}")
            # 记录失败日志，稍后重试

# 4. 执行
if __name__ == "__main__":
    migrate_bucket("source-gcs-bucket", "target-obs-bucket")
```

> **代码说明**: 上述脚本为简化版。实际生产中，GCS 对象可能很大，**不建议**直接 `download_as_bytes()` 加载到内存，应使用流式读写 (`blob.open('rb')` 和 `OBSClient.putObject` 的文件/流模式) 以避免内存溢出。

---

## 5. 迁移后校验

无论使用哪种工具，迁移完成后必须执行校验：

1. **数量核对**:
   - GCS: `gsutil ls -s gs://bucket-name | wc -l`
   - OBS: 通过控制台查看对象数量或编写脚本遍历。
2. **大小核对**:
   - 对比源端和目标端的 Bucket 总存储大小。
3. **完整性校验**:
   - 重点检查随机抽样文件的 MD5 值是否一致。
   - 如果是使用 OMS，直接查看“校验报告”。
   - 如果是使用 Rclone，`--dry-run` 已包含校验逻辑，正式运行后检查日志中的 `OK` 和 `ERROR` 计数。

---

## 6. 常见问题与避坑指南

- **网络延迟**: GCS 到 OBS 是跨云跨地域传输，速度受限于公网带宽。建议使用 OMS 的**专线通道**（如果企业有云专线）或选择**同区域**（如 GCS 美东 -> OBS 美东）以减少延迟。
- **权限错误**: 确保 GCS Service Account 有 `Storage Object Admin`，且 OBS 的 AK/SK 有 `OBS Administrator` 权限。
- **元数据丢失**: 某些自定义元数据（Metadata）在迁移过程中可能会丢失。Rclone 和 OMS 通常支持保留元数据，但脚本迁移需显式处理 `blob.metadata`。
- **小文件性能**: 数千万个小文件迁移会非常慢。建议先进行小文件聚合测试，或调整并发线程数 (`--transfers`, `--threads`)。

## 7. 附录：迁移检查清单 (Checklist)

- [ ] 确认源 Bucket 和目标 Bucket 已创建。
- [ ] 确认网络连通性（GCP 到华为云公网/专线）。
- [ ] 准备好 GCS SA 密钥和 OBS AK/SK。
- [ ] 选择迁移工具 (Rclone / OMS / 脚本)。
- [ ] 执行预演 (Dry Run) 并确认文件数量。
- [ ] 执行正式迁移。
- [ ] 执行数据校验 (校验报告/脚本比对)。
- [ ] 更新应用配置，将访问入口指向新 OBS Bucket。
- [ ] 保留旧数据一段时间作为备份，确认无误后归档。

---
*文档生成时间：2026-05-21*
*提示：迁移涉及数据核心安全，建议在非业务高峰期进行，并做好回滚预案。*