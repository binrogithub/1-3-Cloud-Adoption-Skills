---
name: huaweicloud-oms-migration
description: Migrate object storage to Huawei Cloud OBS using OMS (Object Migration Service). Handles cross-cloud (AWS, Azure, Aliyun, Tencent, GCP, on-prem HTTP) S3/bucket migration with Terraform automation, consistency checks, and post-migration verification. Use when the user wants to migrate or replicate objects/buckets to Huawei Cloud OBS.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: object-storage-migration-huaweicloud
---

# Huawei Cloud OMS Object Storage Migration

Migrate objects from AWS S3, Azure Blob, Aliyun OSS, Tencent COS, GCP GCS, or HTTP/HTTPS sources to Huawei Cloud OBS using the Object Migration Service (OMS). This skill covers the complete end-to-end workflow: source discovery, target discovery, destination bucket creation, Terraform automation, migration execution, verification, and cleanup.

## Rules

1. **DISCOVER before ACT** — always inventory the source bucket (region, object count, total size, storage classes) and the target OBS environment before creating any OMS task. Never assume the source bucket is empty or small.
2. **NEVER HARDCODE CREDENTIALS** — declare source and destination AK/SK as `sensitive` Terraform variables. Pass them via `-var` or `TF_VAR_*` environment variables at apply time. Never commit them to `.tfvars` or state. Add `terraform.tfvars` and `*.tfstate*` to `.gitignore`.
3. **CHOOSE TASK TYPE WISELY** — `huaweicloud_oms_migration_task` for one-time migration of a finite object set. `huaweicloud_oms_migration_sync_task` for continuous replication (keeps destination in sync with future source changes). `huaweicloud_oms_migration_task_group` to batch many tasks with shared bandwidth limits. Default to one-time unless the user explicitly asks for ongoing sync.
4. **CREATE DESTINATION BUCKET VIA TERRAFORM** — if the destination OBS bucket does not exist, create it with `huaweicloud_obs_bucket` in the same Terraform configuration. Reference it as `huaweicloud_obs_bucket.dest.bucket` in the OMS task, never hardcode the name. Verify the bucket name is globally unique (OBS namespace is global per region).
5. **USE `type = "prefix"` + `object = [""]` FOR FULL BUCKET** — to migrate an entire source bucket, set `type = "prefix"` and `object = [""]`. For a subset, use `type = "object"` with explicit keys (trailing `/` = folder). For very large buckets, use `type = "list"` with an object list file in an OBS bucket.
6. **SET CONSISTENCY CHECK AND OVERWRITE MODE** — `consistency_check = "size_last_modified"` and `object_overwrite_mode = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"` make re-runs idempotent (skip objects already migrated with same size+mtime). Use `crc64` only when migrating from Aliyun/Tencent/HuaweiCloud. Use `FULL_OVERWRITE` only when you want to force re-copy.
7. **AVOID INVALID DESCRIPTION CHARACTERS** — OMS rejects `->`, `<>`, `<=`, `>=` and other non-plain-ASCII in the `description` field with error `OMS.0064 Invalid request parameters [description] invalid.` Use plain ASCII: `"AWS S3 to Huawei OBS migration"`, not `"AWS S3 -> Huawei OBS"`.
8. **PROVIDER NEEDS EXPLICIT AK/SK** — the `huaweicloud` Terraform provider does not fall back to ECS metadata service (IMDS) like the AWS provider does. Always set `access_key` and `secret_key` in the `provider "huaweicloud"` block (from sensitive variables), or export `HW_ACCESS_KEY`/`HW_SECRET_KEY` environment variables.
9. **REFRESH STATE TO CHECK REAL STATUS** — `terraform output oms_task_status` reads from the local state file, which is a snapshot at apply time. To see the live task status, run `terraform refresh` first (or `terraform apply -refresh-only`). Status codes: `1`=waiting, `2`=migrating, `3`=paused, `4`=failed, `5`=succeeded.
10. **VERIFY WITH ETAGS, NOT JUST COUNTS** — after migration, compare object counts AND ETags between source and destination. Matching ETags guarantee byte-level integrity. Also inspect the `oms/` folder that OMS creates in the destination bucket — it contains the failed-object list (empty on success).

## Workflow Overview

```
Phase 1          Phase 2          Phase 3          Phase 4
DISCOVER    →    PREPARE     →    TERRAFORM   →    APPLY
(source+dest)    (dest bucket)    (main.tf)        (init/plan/apply)

Phase 5          Phase 6
VERIFY     →    CLEANUP
(ETags+count)    (optional)
```

## Phase 1: DISCOVER

Gather complete information about the source bucket and target environment.

### Source inventory

Use the source cloud's CLI to collect:

| Item | Why needed | Example |
|------|-----------|---------|
| Bucket name | OMS `src_bucket` | `demo-bucket-17b5e8a2` |
| Region | OMS `src_region` | `us-east-2` (AWS), `oss-cn-hangzhou` (Aliyun) |
| Cloud provider | OMS `src_cloud_type` / `data_source` | `AWS`, `Azure`, `Aliyun`, `Tencent` |
| Object count + total size | Estimate migration duration/cost | 15 objects, ~1.1 MB |
| Storage classes present | Decide `enable_restore` | STANDARD, GLACIER/ARCHIVE |
| AK/SK with read access | OMS `src_ak` / `src_sk` | `s3:GetObject` + `s3:ListBucket` |

See [references/source-clouds.md](references/source-clouds.md) for per-cloud inventory commands and `src_cloud_type` value mapping.

```bash
# AWS S3 example
aws s3api get-bucket-location --bucket <bucket>
aws s3api list-objects-v2 --bucket <bucket> --query 'Contents[].{Key:Key,Size:Size,StorageClass:StorageClass}' --output table
```

### Target inventory (Huawei Cloud OBS)

```bash
# List existing OBS buckets
hcloud obs ls -s

# Check if destination name is already taken
hcloud obs ls obs://<dest-bucket>/ -s 2>&1  # error = available, list = exists
```

If the destination bucket does not exist, it will be created in Phase 3 via Terraform.

### Target credentials

Ask the user for Huawei Cloud AK/SK with OBS permissions (`obs:bucket:*` or equivalent). Verify with:

```bash
hcloud configure test
```

## Phase 2: PREPARE

Decide configuration values:

| Decision | Default | Options |
|----------|---------|---------|
| Destination region | `la-north-2` (or user's default) | Any Huawei Cloud region with OBS |
| Destination bucket name | Same as source, or `<source>-oms` | Globally unique, lowercase, 3-63 chars |
| Task type | `oms_migration_task` (one-time) | `oms_migration_sync_task` (continuous) |
| Migration scope | Full bucket (`prefix` + `[""]`) | Subset (`object` + keys), list file (`list`) |
| Consistency check | `size_last_modified` | `crc64` (Aliyun/Tencent/HC only), `no_check` (HTTP) |
| Overwrite mode | `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` | `NO_OVERWRITE`, `FULL_OVERWRITE`, `CRC64_COMPARISON_OVERWRITE` |
| Metadata migration | `true` | `false` (ContentType always migrated) |
| Restore archive | `false` | `true` if source has ARCHIVE/GLACIER objects |
| KMS encryption | `false` | `true` if destination should be encrypted |

Ask the user only about decisions not implied by their request. Batch questions.

## Phase 3: TERRAFORM

Write the Terraform configuration. See [references/terraform-oms-resources.md](references/terraform-oms-resources.md) for full schema.

### File structure

```
<project>/
├── main.tf                  # provider + obs_bucket + oms_migration_task + outputs
├── variables.tf             # all inputs, sensitive flagged
├── terraform.tfvars.example # non-sensitive defaults, sensitive as <REEMPLAZAR>
└── .gitignore               # terraform.tfvars, *.tfstate*, .terraform/
```

### main.tf (one-time migration, full bucket)

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.93.0"  # check latest with terraform_get_latest_provider_version
    }
  }
}

provider "huaweicloud" {
  region     = var.hc_region
  access_key = var.hc_ak
  secret_key = var.hc_sk
}

resource "huaweicloud_obs_bucket" "dest" {
  bucket = var.hc_bucket
  acl    = "private"
}

resource "huaweicloud_oms_migration_task" "migration" {
  region = var.hc_region

  source_object {
    data_source = var.src_cloud_type
    region      = var.src_region
    bucket      = var.src_bucket
    access_key  = var.src_ak
    secret_key  = var.src_sk
    object      = [""]  # entire bucket
  }

  destination_object {
    region     = var.hc_region
    bucket     = huaweicloud_obs_bucket.dest.bucket
    access_key = var.hc_ak
    secret_key = var.hc_sk
  }

  type                           = "prefix"
  start_task                     = true
  description                    = "AWS S3 to Huawei OBS migration"
  enable_metadata_migration      = true
  consistency_check              = "size_last_modified"
  object_overwrite_mode          = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"
  enable_failed_object_recording = true
}

output "obs_bucket_name" { value = huaweicloud_obs_bucket.dest.bucket }
output "oms_task_id"     { value = huaweicloud_oms_migration_task.migration.id }
output "oms_task_status" { value = huaweicloud_oms_migration_task.migration.status }
```

### variables.tf

```hcl
variable "src_cloud_type" { type = string }  # AWS, Azure, Aliyun, Tencent, etc.
variable "src_region"     { type = string }
variable "src_bucket"     { type = string }
variable "src_ak"         { type = string; sensitive = true }
variable "src_sk"         { type = string; sensitive = true }

variable "hc_region" { type = string }  # e.g. la-north-2
variable "hc_bucket" { type = string }
variable "hc_ak"     { type = string; sensitive = true }
variable "hc_sk"     { type = string; sensitive = true }
```

### .gitignore

```
terraform.tfvars
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
tfplan
```

### Continuous sync variant

If the user wants ongoing replication, replace `huaweicloud_oms_migration_task` with `huaweicloud_oms_migration_sync_task`:

```hcl
resource "huaweicloud_oms_migration_sync_task" "sync" {
  region         = var.hc_region
  src_cloud_type = var.src_cloud_type
  src_region     = var.src_region
  src_bucket     = var.src_bucket
  src_ak         = var.src_ak
  src_sk         = var.src_sk
  dst_bucket     = huaweicloud_obs_bucket.dest.bucket
  dst_ak         = var.hc_ak
  dst_sk         = var.hc_sk

  enable_metadata_migration = true
  consistency_check         = "size_last_modified"
  description               = "AWS S3 to Huawei OBS sync"
  action                    = "start"
}
```

## Phase 4: APPLY

```bash
# 1. Initialize and validate
terraform init
terraform validate

# 2. Plan (pass sensitive vars via -var or TF_VAR_*)
terraform plan -out=tfplan \
  -var="src_cloud_type=AWS" \
  -var="src_region=us-east-2" \
  -var="src_bucket=demo-bucket-17b5e8a2" \
  -var="src_ak=AKIA..." \
  -var="src_sk=..." \
  -var="hc_region=la-north-2" \
  -var="hc_bucket=demo-bucket-17b5e8a2" \
  -var="hc_ak=HPUA..." \
  -var="hc_sk=..."

# 3. Review the plan — confirm 2 resources to add (obs_bucket + oms_task)

# 4. Get EXPLICIT user confirmation before applying

# 5. Apply
terraform apply -auto-approve tfplan
```

**Always get explicit yes/no confirmation before `terraform apply`.** The apply creates real infrastructure (OBS bucket + OMS task) and starts the migration immediately if `start_task = true`.

## Phase 5: VERIFY

See [references/verification.md](references/verification.md) for full procedures.

```bash
# 1. Refresh state to get live task status
terraform refresh -var=...  # (same vars as apply)
terraform output oms_task_status
# 5 = succeeded, 4 = failed, 2 = still migrating

# 2. Compare object counts
aws s3api list-objects-v2 --bucket <src> --query 'KeyCount' --output text
hcloud obs ls obs://<dest>/ -d -s  # look at "File number: N"

# 3. Compare ETags (byte-level integrity)
aws s3api list-objects-v2 --bucket <src> --query 'Contents[].{Key:Key,ETag:ETag,Size:Size}' --output table
hcloud obs ls obs://<dest>/ -d  # ETag column

# 4. Inspect the oms/ folder for failed objects
hcloud obs ls obs://<dest>/oms/ -d -s
```

## Phase 6: CLEANUP (optional)

The OBS bucket and migrated objects persist. Only OMS task metadata can be cleaned:

```bash
# Remove the OMS task from Terraform state + cloud
terraform destroy -var=...  # destroys oms_migration_task AND obs_bucket
# OR selectively:
terraform destroy -target=huaweicloud_oms_migration_task.migration -var=...
```

Warn the user: `terraform destroy` removes the OBS bucket and all migrated objects if the bucket is managed by this config. To keep the bucket, use `-target` on only the OMS task.

## Worked Example

The following example was executed successfully:

| | Source (AWS S3) | Destination (Huawei Cloud OBS) |
|---|---|---|
| Bucket | `demo-bucket-17b5e8a2` | `demo-bucket-17b5e8a2` |
| Region | `us-east-2` | `la-north-2` |
| Objects | 15 (~75 KB each) | 15 (ETags matched) |
| Task ID | — | `260661304820157` |
| Final status | — | `5` (succeeded) |

Provider version: `huaweicloud` v1.93.0. Migration completed in ~2 minutes for 15 small objects.

## References

* **Terraform OMS resources schema** [references/terraform-oms-resources.md](references/terraform-oms-resources.md)
* **Source cloud inventory commands** [references/source-clouds.md](references/source-clouds.md)
* **Post-migration verification** [references/verification.md](references/verification.md)
* **Troubleshooting common errors** [references/troubleshooting.md](references/troubleshooting.md)
