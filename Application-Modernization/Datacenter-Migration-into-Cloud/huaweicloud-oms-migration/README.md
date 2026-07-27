# Object Storage Migration from Datacenter to Huawei Cloud OBS via OMS

Migrate object storage from on-premises HTTP/HTTPS sources or other cloud providers to Huawei Cloud OBS as part of a datacenter-to-cloud migration strategy.

---

## Overview

```
Datacenter / Source Cloud              Huawei Cloud
+------------------+                   +------------------+
|  On-prem HTTP     |                   |  OBS Bucket      |
|  AWS S3           |   --- OMS --->    |  (destination)   |
|  Azure Blob       |                   |                  |
|  NFS via HTTP     |                   |  Data now in     |
|  Legacy storage   |                   |  cloud-native    |
+------------------+                   |  object storage  |
                                       +------------------+
```

When migrating a datacenter to Huawei Cloud, object storage is often one of the first workloads to move. OMS (Object Migration Service) handles the transfer from HTTP/HTTPS sources or other cloud S3-compatible endpoints to OBS, with consistency checks and bandwidth throttling. This skill is oriented towards **datacenter migration** use cases — moving storage assets from an on-premises or legacy environment to Huawei Cloud as part of a broader migration wave.

---

## When to Use This Skill

- Migrating on-premises file storage to OBS via HTTP/HTTPS endpoint
- Moving storage from a legacy cloud provider to Huawei Cloud during datacenter exit
- Bulk transfer of archived data, backups, or media files to OBS
- First wave of datacenter migration: move storage before compute (data-first strategy)
- Decommissioning on-premises NAS/SAN by migrating data to OBS

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
Phase 1: DISCOVER     Inventory source storage (endpoint, object count, total size)
Phase 2: PREPARE      Create destination OBS bucket in target region
Phase 3: TERRAFORM    Write main.tf with OMS migration task
Phase 4: APPLY        terraform init && terraform apply
Phase 5: VERIFY       Compare ETags and object counts between source and destination
Phase 6: CLEANUP      Remove temporary resources (optional)
```

### Datacenter Migration Wave Strategy

```
Wave 1: STORAGE    (this skill)     Move object storage to OBS first
Wave 2: DATABASES  (DRS skill)      Migrate databases to RDS/GaussDB
Wave 3: COMPUTE    (SMS skill)      Migrate servers to ECS
Wave 4: APPS       (re-architect)   Re-deploy applications on cloud
```

---

## How to Use with an AI Agent

```
"Migrate object storage from our datacenter HTTP endpoint <url>
 to Huawei Cloud OBS as part of a datacenter migration.
 Use the huaweicloud-oms-migration skill with HTTP source type.
 Create the destination OBS bucket and set up the OMS migration task
 via Terraform."
```

---

## Related Skills in Datacenter Migration

| Skill | Service | What it migrates |
|-------|---------|-----------------|
| `huaweicloud-oms-migration` (this) | OMS | Object storage to OBS |
| `huaweicloud-sms-migration` | SMS | Servers to ECS |
| `huaweicloud-drs-migration` | DRS | Databases to RDS |

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Terraform | 1.5+ with huaweicloud provider |
| Source credentials | AK/SK or HTTP credentials for the source storage |
| Huawei Cloud credentials | AK/SK with OBS and OMS permissions |
| Network connectivity | Source endpoint reachable from Huawei Cloud OMS |

---

*Version: 1.0 -- July 2026*
*Skill: huaweicloud-oms-migration*
*Service: Huawei Cloud OMS (Object Migration Service)*
*Orientation: Datacenter migration (storage-first strategy)*
