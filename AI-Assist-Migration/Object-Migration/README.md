# Object Migration

Complete toolkit for migrating object storage data from AWS S3, Azure Blob, Aliyun OSS, Tencent COS, GCP GCS, or HTTP/HTTPS sources to Huawei Cloud OBS (Object Storage Service) using the Object Migration Service (OMS) with Terraform automation.

Includes 1 skill for AI agents (OpenCode, Hermes, Claude Code), Terraform templates, and a step-by-step workflow covering source discovery, destination bucket creation, migration execution, consistency verification, and cleanup.

---

## What This Skill Does and Why It Is Useful

### The Problem

When migrating object storage to Huawei Cloud OBS, you need to:

- Inventory the source bucket: region, object count, total size, storage classes (including ARCHIVE/GLACIER)
- Create the destination OBS bucket if it does not exist (globally unique name)
- Choose the right task type: one-time migration vs continuous sync
- Select the right consistency check and overwrite mode for idempotent re-runs
- Avoid invalid characters in task descriptions (OMS rejects `->`, `<>`, `<=`, `>=`)
- Verify migration integrity with ETags, not just object counts

### The Solution: OMS + Terraform

```
  DISCOVER           PREPARE          TERRAFORM        APPLY
  (source+dest)      (dest bucket)    (main.tf)        (init/plan/apply)
      |                  |                |                |
      v                  v                v                v
  Phase 1            Phase 2          Phase 3          Phase 4

  VERIFY             CLEANUP
  (ETags+count)      (optional)
      |                  |
      v                  v
  Phase 5            Phase 6
```

#### Skill: huaweicloud-oms-migration

**What it does:** Migrates objects from AWS S3, Azure Blob, Aliyun OSS, Tencent COS, GCP GCS, or HTTP/HTTPS sources to Huawei Cloud OBS using OMS. Covers the complete end-to-end workflow: source discovery, target discovery, destination bucket creation, Terraform automation, migration execution, verification, and cleanup.

**Key design decisions:**
- `huaweicloud_oms_migration_task` for one-time migration of a finite object set
- `huaweicloud_oms_migration_sync_task` for continuous replication (keeps destination in sync)
- `huaweicloud_oms_migration_task_group` to batch many tasks with shared bandwidth limits
- `consistency_check = "size_last_modified"` + `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` for idempotent re-runs

**What it produces:** A destination OBS bucket with all source objects migrated, plus Terraform state for cleanup.

---

## What This Package Includes

```
Object-Migration/
|
|-- huaweicloud-oms-migration/       The migration skill
|   |-- SKILL.md                     Metadata + step-by-step instructions
|   |-- references/                  Per-cloud inventory commands, Terraform schema
|   |-- assets/                      Terraform templates
|   +-- scripts/                     Helper utilities
|
+-- README.md                        (this file)
```

---

## Installation

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r huaweicloud-oms-migration ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r huaweicloud-oms-migration ~/.hermes/skills/infrastructure/
```

### Option C: Claude Code

```bash
mkdir -p ~/.claude/skills
cp huaweicloud-oms-migration/SKILL.md ~/.claude/skills/huaweicloud-oms-migration.md
```

---

## How to Use the Skill with an AI Agent

### Natural Triggers

```
"Migrate this S3 bucket to Huawei Cloud OBS"
"Move my Azure Blob storage to OBS"
"Set up OMS migration for this bucket"
"Sync objects from Aliyun OSS to Huawei OBS"
```

### Workflow Summary

```
Phase 1: DISCOVER       Inventory source bucket + target     -> source_info.json
         |               Region, object count, size, storage classes
         v
Phase 2: PREPARE        Decide configuration                  -> config decisions
         |               Task type, scope, consistency check, overwrite mode
         v
Phase 3: TERRAFORM      Write main.tf + variables.tf          -> terraform config
         |               Create dest bucket + OMS task
         v
Phase 4: APPLY          terraform init && terraform apply     -> migration running
         |               Monitor task status (1=waiting, 2=migrating, 5=succeeded)
         v
Phase 5: VERIFY         Compare object counts + ETags         -> integrity confirmed
         |               Check oms/ folder for failed objects
         v
Phase 6: CLEANUP        Optional: destroy OMS task             -> bucket persists
```

---

## Quick Reference

### Source Discovery (AWS S3)

```bash
aws s3api get-bucket-location --bucket <bucket>
aws s3api list-objects-v2 --bucket <bucket> \
  --query 'Contents[].{Key:Key,Size:Size,StorageClass:StorageClass}' --output table
```

### Target Discovery (Huawei Cloud OBS)

```bash
hcloud obs ls -s
hcloud obs ls obs://<dest-bucket>/ -s 2>&1  # error = available, list = exists
```

### Terraform (one-time full bucket migration)

```hcl
resource "huaweicloud_obs_bucket" "dest" {
  bucket = var.hc_bucket
  acl    = "private"
}

resource "huaweicloud_oms_migration_task" "migration" {
  source_object {
    data_source = var.src_cloud_type  # AWS, Azure, Aliyun, Tencent, etc.
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
  type                  = "prefix"
  start_task            = true
  consistency_check     = "size_last_modified"
  object_overwrite_mode = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"
}
```

---

## Supported Source Clouds

| Cloud | `data_source` value | Consistency check options |
|-------|-------------------|--------------------------|
| AWS S3 | `AWS` | `size_last_modified` |
| Azure Blob | `Azure` | `size_last_modified` |
| Aliyun OSS | `Aliyun` | `size_last_modified`, `crc64` |
| Tencent COS | `Tencent` | `size_last_modified`, `crc64` |
| GCP GCS | `GCP` | `size_last_modified` |
| HTTP/HTTPS | `HTTP` | `no_check` |

---

## Requirements

| Component | Requirement |
|------------|-----------|
| Source | AWS S3 / Azure Blob / Aliyun OSS / Tencent COS / GCP GCS / HTTP endpoint |
| Target | Huawei Cloud OBS bucket (created automatically if missing) |
| Credentials | Source AK/SK with read access; Huawei Cloud AK/SK with OBS permissions |
| Terraform | huaweicloud provider >= 1.93.0 |
| AI Agent | OpenCode / Hermes / Claude Code (optional) |

---

## Key Rules

1. **DISCOVER before ACT** -- never assume the source bucket is empty or small
2. **NEVER HARDCODE CREDENTIALS** -- use sensitive Terraform variables, pass via TF_VAR_*
3. **CHOOSE TASK TYPE WISELY** -- one-time vs continuous sync vs task group
4. **SET CONSISTENCY CHECK** -- `size_last_modified` + `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` for idempotent re-runs
5. **AVOID INVALID DESCRIPTION CHARACTERS** -- OMS rejects `->`, `<>`, `<=`, `>=` in description
6. **VERIFY WITH ETAGS** -- matching ETags guarantee byte-level integrity, not just counts

---

*Skills: huaweicloud-oms-migration*
*Strategy: OMS + Terraform automation*
*Target: Huawei Cloud OBS*
