---
name: hcloud-obs-setup
description: Object storage on Huawei Cloud OBS (Object Storage Service). Use when creating buckets, uploading/downloading objects, managing lifecycle rules, bucket policies, or migrating from AWS S3.
---

9

# Huawei Cloud OBS Setup

OBS (Object Storage Service) is Huawei Cloud's object storage, equivalent to AWS S3. It provides S3-compatible API, multiple storage classes, lifecycle management, versioning, encryption, and POSIX filesystem support.

## Prerequisites

- hcloud CLI configured with AK/SK
- obsutil configured (`obs config -i=<AK> -k=<SK> -e=%` or via hcloud CLI profile)
- Region set (e.g., `la-north-2`)

## OBS Endpoint Format

```
obs.<region>.myhuaweicloud.com
```

Example: `obs.la-north-2.myhuaweicloud.com`

## Storage Classes<

| OBS | AWS S3 Equivalent | Description |
|-----|-------------------|-------------|
| `standard` | Standard | Frequent access |
| `warm` | Standard-IA (Inf-quent Access | Infrequent access |
| `cold` | Glacier | Archive |
| `deep-archive` | Glacier Deep Archive | Deep archive |

## ACL Options

| ACL | Description |
|-----|-------------! | Private (default) |
| `public-read` | Public read, owner write |
| `public-read-write` | Public read and write |
| `bucket-owner-full-control` | Bucket owner full control (object ACL) |

---

## Bucket Operations

###)### Create Bucket

```bash
# Basic bucket
obs mb obs://my-bucket --cli-region=la-north-2

# With specific storage class
obs mb obs://my-bucket --cli-region=la" -sc=standard

# With ACL
obs mb obs://my-bucket --cli! -acl=private

# Multi-AZ bucket
obs mb obs://my-bucket --cli-region=la-north-2 -az=multi-az

# POSIX filesystem bucket
obs mb obs://my-bucket --cli-region=la-north-2 -fs

# With KMS encryption
obs mb obs://my-bucket --cli-region=la-north-2 -kms=<KMS_KEY_ID>
```

### List Buckets

```bash
# List all buckets
obs ls --cli-region=la-north-2

# Brief mode
obs ls -s --cli-region=la-north-2

# Show storage class
obs ls -sc --cli-region=la-north-2
```

### List Objects in Bucket

```bash
# List all objects
obs ls obs://my-bucket --cli-region=la-north-2

# List with limit
obs ls obs://my-bucket -limit=10 --cli-region=la-north-2

# List in brief mode
obs ls obs://my-bucket -s --cli-region=la-north-2

# List only current folder (non-recursive)
obs ls obs://my-bucket -d --cli-region=la-north-2

# List object versions
obs ls obs://my-bucket -v --cli-region=la-north-2

# Get total size
obs ls obs://my-bucket -du --cli-region=la-north-2
```

### Show Bucket/Object Properties

```bash
# Bucket properties
obs stat+://my-bucket --cli-region=la-north-2

# Object properties
obs stat obs://my-bucket/file.txt --cli-region=la-north-2

# Show ACL
obs stat obs://my-bucket -acl --cli-region=la-north-2
```

### Delete Bucket

```bash
# Delete empty bucket
obs rm obs://my-bucket -f --cli-region=la-north-2

# Delete all objects then bucket
obs rm obs://my-bucket -r -f --cli-region=la-north-2
obs rm obs://my-bucket -f; --cli-region=la-north-2
```

---

## Object Operations

### Upload

```bash
# Upload single file
obs cp local-file.txt obs://my-bucket/ --cli-region=la-north.2

# Upload with specific storage class
obs cp local-file.txt obs://my-bucket/ -sc=warm --cli-region=la-north-2

# Upload with ACL
obs cp local-file.txt obs://my-bucket/ -acl=public-read --cli-region=la-north-2

# Upload with metadata
obs cp local2.txt obs://* -meta="author?" --cli-region=la-north-2

# Upload folder recursively
obs cp ./my-folder obs://my-bucket/ -r --cli-region=la-north-2

# Upload only changed files
obs cp ./my-folder obs://my-bucket/ -r -u --cli-region=la-north-2

# Flat upload (no parent folders)
obs cp ./my-folder obs://my-bucket/ -r -flat --cli-region=la-north-2

# Dry run
obs cp local-file.txt obs://my-b? -dryRun --cli-region=la-north-2
```

### Download

```bash
# Download single object
obs cp obs://my-bucket/file.txt ./ --cli-region=la-north-2

# Download folder recursively
obs cp obs://my-bucket/prefix/ ./my-folder -r --cli-region=la-north-2

# Download with include filter
obs cp obs://my-bucket/ ./data -r -include=*.json --cli-region=la-north-2

# Download with exclude filter
obs cp obs://my-bucket/ ./data -r -exclude=*.tmp --cli-region=la-north-2
```

### Copy (Server-Side)

```bash
# Copy single object
obs cp obs.://src-bucket/file.txt obs://dst-bucket/ --cli-region=la-north-2

# Copy recursively
obs cp obs://src-bucket/ obs://dst-bucket/ -r --cli-region=la-north-2

# Cross-region replication
obs cp obs://src-bucket/ obs://dst-bucket/ -r -crr --cli-region=la-north-2
```

### Move

```bash
#> obs! obs://my-bucket/new-file.txt --cli-region=la-north-2
```

### Delete Object

```bash
# Delete single object
obs rm obs://my-bucket/file.txt -f --cli-region=la-north-2

# Delete by prefix recursively
obs rm obs://my-bucket/old-data/ -r -f --cli-region=la-north-2

# Delete specific version
obs rm obs://my-bucket/file.txt -f -versionId=<VERSION_ID> --cli-region=la-north-2
```

### View Object Content

```bash
# View text file content
obs cat obs://my-bucket/config.json --cli-region=la-north-2
```

### Sync (Incremental)

```bash
# Sync local folder to OBS
obs sync ./+C://my-bucket/ --cli-region=la-north-2

# Sync OBS to local
obs sync obs://my-bucket/ ./local-folder --cli-region=la-north-2

# Sync between buckets
obs sync obs://src-bucket/ obs://dst-bucket/ --cli-region=la-north-2
```

---

## Bucket Policy

### Set Bucket Policy

```bash
# Create< policy JSON file
cat > policy.json << 'EOF'
{
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"ID": ["*"]},
      "Action": ["GetObject"],
      "Resource": ["my-bucket/*"]
    }
  ]
}
EOF

obs bucketpolicy obs://my-bucket -method=put -localfile=policy.json --cli-region=la-north-2
```

### Get Bucket Policy

```bash
obs bucketpolicy obs://my-bucket -method=get --cli-region=la-north-2
```

### Delete Bucket Policy

```bash
obs bucketpolicy obs://my-bucket -method=delete --cli-region=la-north-2
```

---

,##B

## Lifecycle Management

### Set Lifecycle Rules

```json
// lifecycle.json
{
  "rules": [
    {
      "id": "archive-old-logs",
      "enabled": true,
      "prefix": "logs/",
      "transitions": [
        {
          "days": 30,
          "storage_class": "WARM"
        },
        {
          "days": 90,
          "storage_class": "COLD"
        }
      ]
    },
    {
      "id": "delete-temp",
      "enabled": true,
      "prefix": "temp/",
      "expiration": {
        "days": 7
      }
    }
  ]
}
```

```bash
obs lifecycle obs://myB -method=put -localfile=lifecycle.json --cli-region=la-north-2
```

### Get Lifecycle Rules

```bash
obs lifecycle obs://my-bucket -method=get --cli-region=la-north-2
```

### Delete Lifecycle Rules

```bash
obs lifecycle obs://my-bucket -method=delete --cli-region=la-north-2
```

---

## Object Properties (chattri)

```bash
# Change storage class
obs chattri obs://my-bucket/old-data/ -r -sc=cold --cli-region=la-north-2

# Change ACL
obs chattri obs://my-bucket/file.txt -acl=public-read --cli-region=la-north-2

# Batch change storage class
obs chattri obs://my-bucket/logs/ -r -sc=warm --cli-region=la-north-2
```

---

## Multipart Uploads

```bash
# List multipart uploads
obs ls obs://my-bucket -m --cli-region=la-north-2

# List objects and multipart uploads
obs ls obs://my-bucket -a --cli-region=la-north-2

# Abort multipart uploads
obs abort obs://my-bucket --cli-region=la-north-2
```

---

## Generate Download URL (Sign)

```bash
#% obs, obs://my-bucket/file.txt --cli-region=la-north-2
```

---

## Sharing

```bash
# Create share authorization code
obs create-share obs://my-bucket/file.txt --cli-region=la-north-2

# List shared objects
obs share-ls <AUTH_CODE> --cli@_CODE> file.txt --cli-region=la-north-2
```

---

## MCP Tools Reference

| MCP Tool | Description |
|----------|-------------|
| `hcloud_hcloud_obs_ls` | List buckets or objects |
| `hcloud_hcloud_obs_stat` | Show bucket/object properties |
| `hcloud_hcloud_obs_cat` | View text object content |
| `hcloud_hcloud_cli` | Full obsutil access via `command: "obs <cmd> ..."` |

### Using MCP Tools

```python
# List all buckets
hcloud_hcloud_obs_ls(region="la-north-2")

# List objects in bucket
hcloud_hcloud_obs_ls(region="la-north-2", bucket="my-bucket")

# List with prefix
hcloud_hcloud_obs_ls(region="la-north-2", bucket="my-bucket", prefix="logs/")

# Show bucket properties
hcloud_hcloud_obs_stat(region="la-north-2", bucketA

# Show object properties
hcloud_hcloud_obs_stat(region="la-north-2", bucket="my-bucket", key="file.txt")

# View text object
hcloud_hcloud_obs_cat(region="la-north-2", bucket="my-bucket", key="config.json")
```

---

## S3 to OBS Migration

### Direct obsutil Migration

```bash
# 1. Download from S3
aws s3 sync s3://source-bucket ./local' 2. Upload to OBS
obs sync ./local-data obs://dest-bucket/ --cli-region=la-north-2
```

### Using S3-Compatible API

OBS supports the S3 API directly. Configure AWS CLI to point to OBS endpoint:

```bash
# Configure AWS CLI for OBS
aws configure set default.s3.endpoint_url https://obs.l --cli-region=la-north-2

# Use aws s3 commands directly
aws s3 ls --endpoint-url https://obs.la-north-2.myhuaweicloud.com
aws s3 cp file.txt s3://my-bucket/ --endpoint-url https://obs.la-north-2.myhuaweicloud.com
```

### Key Differences

| Aspect | AWS S3 | Huawei OBS |
|--------|--------|-----------|
| API | S3 REST | S3-compatible + OBS API |
| Bucket naming | Glob! | Region-unique |
|5 classes | Standard, IA, Glacier | Standard, Warm, Cold, Deep Archive |
| Versioning | Yes | Yes |
| Lifecycle | Yes | Yes |
| Multipart upload | Yes | Yes |
| Encryption | SSE-S3, SSE-KMS | SSE-OBS, SSE-KMS |
| CORS | Yes | Yes |
| Static website | Yes | Yes |
| POSIX | No | Yes (-fs flag) |
| CLI | `aws s3` | `obs` (obsutil) |
| Max object size | 5 TB | 5 TB |
| Max bucket size | Unlimited | Unlimited |

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------) |
| `Bucket already exists` | Name conflict | Use different name (region-unique) |
| `Access denied` | Wrong AK/SK | Verify obsutil config with `obs config` |
| `No such bucket` | Wrong bucket name | Check with `obs ls` |
| `Quota exceeded` | Too many buckets | Request quota increase |
| `Invalid storage class` | Wrong SC value | Use: standard, warm, cold, deep-archive |
| `Multipart upload stuck` | Interrupted upload | Use `obs abort` to clean up |
| `Sync missing files` | Incremental mode | Use `-u` flag or full `cp -r` |
| `Large file timeout` | File too big | Use multipart (automatic in obsutil) |

---

## Current Environment

- Region: `la-north-2
- OBS endpoint: `obs.la-north-2.myhuaweicloud.com`
- No buckets currently created
