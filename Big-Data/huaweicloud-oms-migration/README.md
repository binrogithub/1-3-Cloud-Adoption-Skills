# Object Storage Migration to Huawei Cloud OBS via OMS

Migrate object storage data from AWS S3, Azure Blob, Aliyun OSS, Tencent COS, GCP GCS, or HTTP/HTTPS sources to Huawei Cloud OBS using the Object Migration Service (OMS).

---

## Overview

```
Source Cloud                          Huawei Cloud
+------------------+                 +------------------+
|  AWS S3          |                 |  OBS Bucket      |
|  Azure Blob      |   --- OMS -->   |  (destination)   |
|  Aliyun OSS      |                 |                  |
|  Tencent COS     |                 |  Consistency     |
|  GCP GCS         |                 |  check (ETags)   |
|  HTTP/HTTPS      |                 |                  |
+------------------+                 +------------------+
```

OMS (Object Migration Service) is a Huawei Cloud data service that handles cross-cloud object storage migration with bandwidth control, consistency checks, and continuous sync options. This skill is oriented towards **data migration** use cases — moving data assets between cloud providers or from on-premises storage to Huawei Cloud OBS.

---

## When to Use This Skill

- Migrating data lakes or object storage from another cloud to Huawei Cloud OBS
- Replicating S3 buckets to OBS for multi-cloud data redundancy
- Moving training datasets, model artifacts, or backups to OBS
- Continuous sync of object storage between clouds (OMS sync task)
- Data consolidation from multiple cloud sources into a single OBS region

---

## Skill Contents

| File | Description |
|------|-------------|
| `SKILL.md` | Complete skill with rules, workflow phases, and Terraform examples |
| `references/source-clouds.md` | Source cloud configuration (AWS, Azure, Aliyun, Tencent, GCP, HTTP) |
| `references/terraform-oms-resources.md` | Terraform resource definitions for OMS tasks |
| `references/troubleshooting.md` | Common errors and solutions |
| `references/verification.md` | Post-migration verification procedures |

---

## Workflow

```
Phase 1: DISCOVER     Inventory source bucket (region, object count, size, storage classes)
Phase 2: PREPARE      Create destination OBS bucket if needed
Phase 3: TERRAFORM    Write main.tf with OMS migration task
Phase 4: APPLY        terraform init && terraform apply
Phase 5: VERIFY       Compare ETags and object counts between source and destination
Phase 6: CLEANUP      Remove temporary resources (optional)
```

---

## How to Use with an AI Agent

```
"Migrate object storage from AWS S3 bucket <bucket-name> in <region>
 to Huawei Cloud OBS using OMS. Use the huaweicloud-oms-migration skill.
 Set up Terraform with the OMS migration task and verify the migration
 with ETag comparison."
```

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Terraform | 1.5+ with huaweicloud provider |
| Source cloud credentials | AK/SK for the source cloud (AWS, Azure, etc.) |
| Huawei Cloud credentials | AK/SK with OBS and OMS permissions |
| Terraform MCP | For provider schema discovery (optional) |

---

*Version: 1.0 -- July 2026*
*Skill: huaweicloud-oms-migration*
*Service: Huawei Cloud OMS (Object Migration Service)*
*Orientation: Data migration*
