# AWS to Huawei Cloud Migration with AI Assistance

## Overview

This scenario demonstrates migrating AWS infrastructure to Huawei Cloud using AI-assisted tools. The migration covers three paths — database replication (DRS), object storage migration (OMS), and server migration (SMS) — with the AI agent discovering AWS resources, querying Huawei Cloud Terraform provider schemas, and generating migration Terraform code.

## Migration Paths

```
AWS (Source)                    Huawei Cloud (Destination)
+-----------+                   +-----------+
| RDS MySQL | --[DRS]---------> | RDS MySQL |
| S3 Bucket | --[OMS]---------> | OBS Bucket|
| EC2 + VPC | --[SMS]---------> | ECS + VPC |
+-----------+                   +-----------+
```

### 1. DRS — Database Replication Service
Migrates AWS RDS MySQL to Huawei Cloud RDS using Data Replication Service. The AI discovers the AWS RDS instance, gets Huawei Cloud RDS schemas from Terraform MCP, and generates Terraform for the DRS migration task.

### 2. OMS — Object Storage Migration Service
Migrates AWS S3 buckets to Huawei Cloud OBS using Object Storage Migration Service. The AI lists S3 objects, discovers OMS Terraform resources, and generates migration task Terraform with source/destination credentials.

### 3. SMS — Server Migration Service
Migrates AWS EC2 instances to Huawei Cloud ECS using Server Migration Service. The AI discovers EC2 instances and VPCs, then generates Terraform for the SMS migration and target Huawei Cloud network.

## What's Included

| Path | Description |
|------|-------------|
| `DemoMigracion.html` | HTML presentation of the migration demo |
| `demo-migration/aws/` | AWS source infrastructure as Terraform (EC2, RDS, S3, VPC, Security Groups) |
| `demo-migration/huaweicloud/drs/` | DRS migration Terraform (drs.tf, rds.tf, variables.tf, versions.tf, terraform.tfvars) |
| `demo-migration/huaweicloud/oms/` | OMS migration Terraform (main.tf, variables.tf, terraform.tfvars) |
| `demo-migration/huaweicloud/sms/` | SMS migration Terraform (migration/main.tf, network/main.tf) |
| `demo-migration/huaweicloud/websites/` | HTML documentation for each migration type with phase breakdowns |
| `demo-migration/hcloud-vs-terraform.md` | Full AI conversation transcript showing the migration workflow |
| `demo-migration/website/index.html` | Main demo website |
| `skills/huaweicloud-oms-migration/SKILL.md` | OMS migration skill |
| `skills/huaweicloud-sms-migration/SKILL.md` | SMS migration skill |
| `skills/huaweicloud-terraform-planner/SKILL.md` | Terraform planner skill for code generation |

## AWS Source Infrastructure

The `demo-migration/aws/` directory contains the complete AWS source infrastructure defined in Terraform:

| File | Resources |
|------|-----------|
| `vpc.tf` | VPC + subnets for the AWS source environment |
| `security_groups.tf` | Security groups for web and database tiers |
| `ec2.tf` | EC2 instance running WordPress |
| `rds.tf` | RDS MySQL database instance |
| `s3.tf` | S3 bucket with versioning and encryption |
| `main.tf` | Provider configuration |
| `outputs.tf` | Output values for cross-reference |
| `wordpress-post.png` | Screenshot of the WordPress deployment |

## Huawei Cloud Migration Terraform

### DRS (Database Replication)
- `drs.tf` — DRS migration task resource
- `rds.tf` — Target RDS instance on Huawei Cloud
- `variables.tf` / `terraform.tfvars` — Migration parameters

### OMS (Object Storage)
- `main.tf` — OMS migration task resource (S3 → OBS)
- `variables.tf` / `terraform.tfvars` — Source and destination credentials

### SMS (Server Migration)
- `migration/main.tf` — SMS migration task
- `network/main.tf` — Target VPC and network on Huawei Cloud

## AI Conversation Transcript

The `hcloud-vs-terraform.md` file contains the full conversation between the user and the AI agent (GLM-5.2) during the migration demo. It shows:

1. User requests S3 to OBS migration via OMS
2. AI discovers AWS S3 bucket and objects using AWS MCP
3. AI queries Terraform MCP for Huawei Cloud OMS provider schema
4. AI reads AWS credentials and gets bucket details (location, versioning, encryption, tagging)
5. AI gets full provider documentation for `huaweicloud_oms_migration_task`, `huaweicloud_oms_migration_sync_task`, and `huaweicloud_oms_migration_task_group`
6. AI generates Terraform code for the migration

## HTML Documentation

The `demo-migration/huaweicloud/websites/` directory contains HTML documentation for each migration type:

| Path | Content |
|------|---------|
| `drs/index.html` + `drs/fases.html` | DRS migration overview and phases |
| `oms/index.html` + `oms/fases.html` | OMS migration overview and phases |
| `sms/index.html` + `sms/fases.html` | SMS migration overview and phases |
| `session-drs.md` | DRS session notes |
| `session-oms.md` | OMS session notes |
| `sms-session.md` | SMS session notes |

## Related Skills

- [huaweicloud-oms-migration](../huaweicloud-oms-migration/SKILL.md) — OMS migration skill (also available in the parent directory)
- [huaweicloud-sms-migration](../huaweicloud-sms-migration/SKILL.md) — SMS migration skill (also available in the parent directory)
- [ai_assist_rds_migration](../ai_assist_rds_migration/) — AI-assisted RDS migration with configs and scripts
- [ai_assist_rehost](../ai_assist_rehost/) — AI-assisted rehost migration
- [huaweicloud-terraform-planner](../../../Cloud-Foundation/Automation-and-IaC/huaweicloud-terraform-planner/SKILL.md) — Terraform planner skill

## Video Reference

This scenario corresponds to the training video `Migration with AI Assistance.mp4` and the presentation `Demo Migracion.pptx` (neither included in the repository).
