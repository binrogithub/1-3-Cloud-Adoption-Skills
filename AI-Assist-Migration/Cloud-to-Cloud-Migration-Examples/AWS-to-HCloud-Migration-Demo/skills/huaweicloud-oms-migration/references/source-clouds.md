# Source Cloud Inventory

How to inventory buckets in each cloud provider that OMS supports as a source. The `src_cloud_type` / `data_source` value must match exactly what OMS expects.

## src_cloud_type Mapping

| Cloud | OMS `src_cloud_type` value | Notes |
|-------|---------------------------|-------|
| AWS S3 | `AWS` | Most common cross-cloud source |
| Azure Blob Storage | `Azure` | |
| Alibaba Cloud OSS | `Aliyun` | Default if not specified |
| Tencent Cloud COS | `Tencent` | Requires `app_id` parameter |
| Huawei Cloud OBS | `HuaweiCloud` | For inter-region or inter-account HC migration |
| QingCloud | `QingCloud` | |
| Kingsoft Cloud | `KingsoftCloud` | |
| Baidu Cloud | `Baidu` | |
| Qiniu Cloud | `Qiniu` | |
| UCloud | `UCloud` | |
| HTTP/HTTPS URL | `URLSource` | For migrating from public URLs; use `type = url_list` |

---

## AWS S3

### Inventory commands

```bash
# List all buckets
aws s3api list-buckets --query 'Buckets[].Name' --output table

# Get bucket region
aws s3api get-bucket-location --bucket <bucket>
# Note: returns {"LocationConstraint": ""} for us-east-1 (no constraint)

# List objects with size and storage class
aws s3api list-objects-v2 --bucket <bucket> \
  --query 'Contents[].{Key:Key,Size:Size,StorageClass:StorageClass,LastModified:LastModified}' \
  --output table

# Count objects and total size
aws s3api list-objects-v2 --bucket <bucket> --query 'KeyCount' --output text

# Check bucket encryption
aws s3api get-bucket-encryption --bucket <bucket> 2>/dev/null

# Check storage classes present (to decide enable_restore)
aws s3api list-objects-v2 --bucket <bucket> \
  --query 'Contents[].StorageClass' --output text | sort | uniq -c
```

### Required source permissions

The source AK/SK needs at minimum:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:ListBucket", "s3:GetObject"],
    "Resource": [
      "arn:aws:s3:::<bucket>",
      "arn:aws:s3:::<bucket>/*"
    ]
  }]
}
```

If the bucket has Requester Pays enabled, also add `s3:GetObject` with `"Condition": {"StringEquals": {"aws:ResourceAccount": "<owner-account>"}}` and set `enable_requester_pays = true` in the OMS task.

### Region format

AWS regions use the standard format (`us-east-2`, `ap-southeast-1`, etc.). Pass directly as `src_region`.

---

## Azure Blob Storage

### Inventory commands

```bash
# List containers
az storage container list --account-name <account> --query '[].name' --output table

# List blobs
az storage blob list --account-name <account> --container-name <container> \
  --query '[].{name:name,size:properties.contentLength,tier:properties.blobTier}' \
  --output table
```

### Credentials

Use the Azure storage account name and key. OMS maps these to `src_ak` (account name) and `src_sk` (account key). The `src_region` should be the Azure region (e.g. `eastus`, `westeurope`).

---

## Alibaba Cloud OSS (Aliyun)

### Inventory commands

```bash
# List buckets
ossutil ls

# List objects
ossutil ls oss://<bucket>/ --recursive

# Get bucket location
ossutil bucket-loc oss://<bucket>/
```

### Credentials

Use Aliyun AccessKey ID and Secret. `src_region` uses Aliyun format (`oss-cn-hangzhou`, `oss-us-west-1`, etc.).

OMS supports `crc64` consistency check for Aliyun sources — use it for stronger integrity verification.

---

## Tencent Cloud COS

### Inventory commands

```bash
# List buckets
coscli ls

# List objects
coscli ls cos://<bucket>/ --recursive
```

### Credentials

Tencent COS requires an **APP ID** in addition to AK/SK. Pass it as the `app_id` parameter in the OMS task. The `src_region` uses Tencent format (`ap-guangzhou`, `ap-beijing`, etc.).

OMS supports `crc64` consistency check for Tencent sources.

---

## Google Cloud Storage (GCS)

GCS is not in the standard `src_cloud_type` list. To migrate from GCS:

1. **Option A**: Use `URLSource` with `type = url_list` — generate a URL list of signed GCS URLs and store it in an OBS helper bucket.
2. **Option B**: Use the `json_auth_file` parameter in `source_object` (if supported in your provider version) with a GCS service account JSON key file.

### Generate signed URL list

```bash
# Generate signed URLs for all objects in a GCS bucket
gsutil ls gs://<bucket>/** | while read url; do
  gsutil signurl -d 24h key.json "$url"
done > url-list.txt
```

Upload `url-list.txt` to an OBS helper bucket and use `type = url_list` with `list_file_bucket` and `list_file_key`.

---

## HTTP/HTTPS URL Source

For migrating from arbitrary HTTP/HTTPS endpoints (on-prem file servers, CDN, etc.):

1. Create a URL list file (one URL per line, or in the OMS URL list format).
2. Upload it to an OBS helper bucket in the destination region.
3. Use `type = "url_list"` with `data_source = "URLSource"`.

```hcl
resource "huaweicloud_oms_migration_task" "url" {
  source_object {
    data_source      = "URLSource"
    list_file_bucket = "helper-bucket"
    list_file_key    = "url-list.txt"
  }
  type = "url_list"
  # ...
}
```

Use `consistency_check = "no_check"` for HTTP sources where content-length is unavailable.

---

## Huawei Cloud OBS (inter-region/inter-account)

For migrating between Huawei Cloud OBS buckets (different regions or accounts):

```hcl
source_object {
  data_source = "HuaweiCloud"
  region      = "cn-north-1"  # source HC region
  bucket      = "source-bucket"
  access_key  = var.src_ak
  secret_key  = var.src_sk
  object      = [""]
}
```

OMS supports `crc64` consistency check for HC-to-HC migration.

---

## Decision Guide: Which Source Cloud?

| Scenario | src_cloud_type | Consistency check |
|----------|---------------|-------------------|
| AWS S3 → HC OBS | `AWS` | `size_last_modified` |
| Azure Blob → HC OBS | `Azure` | `size_last_modified` |
| Aliyun OSS → HC OBS | `Aliyun` | `crc64` (preferred) |
| Tencent COS → HC OBS | `Tencent` (+ `app_id`) | `crc64` (preferred) |
| HC OBS → HC OBS | `HuaweiCloud` | `crc64` (preferred) |
| HTTP URLs → HC OBS | `URLSource` | `no_check` |
| GCS → HC OBS | `URLSource` (via signed URLs) | `no_check` |
