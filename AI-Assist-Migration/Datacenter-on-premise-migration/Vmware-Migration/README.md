# VMware Migration to Huawei Cloud

Complete toolkit for migrating VMware virtual machines (on-premises or cloud) to Huawei Cloud ECS using MGC (Migration Center) / SMS (Server Migration Service) with Terraform automation and rsync fallback.

Includes 1 skill for AI agents (OpenCode, Hermes, Claude Code), Terraform templates, migration scripts, runbooks, and reusable migration bundles with architecture diagrams.

---

## What This Skill Does and Why It Is Useful

### The Problem

When migrating VMware VMs to Huawei Cloud ECS across regions:

- The source VM may be SMS-incompatible (e.g., `SMS.6504`), requiring a fallback path
- Migration tasks can fail with various error codes (`SMS.6617`, `SMS.6602`, `SMS.7605`, `SMS.8115`) that need specific handling
- VPC quota limits (`VPC.0114`) can block target environment creation
- Stale tasks and migration projects from previous runs can interfere with new migrations
- You need to verify not just the migration result but also network connectivity (EIP binding, security group rules)

### The Solution: SMS First + rsync Fallback

```
  VALIDATE          PREPARE          EXECUTE          VALIDATE
  (prerequisites)   (tfvars)         (terraform)      (outputs)
      |                  |                |                |
      v                  v                v                v
  Step 1             Step 2           Step 3           Step 4

  TROUBLESHOOT
  (error codes)
      |
      v
  Step 5
```

#### Skill: mgc-cross-region-migration

**What it does:** Executes and troubleshoots Huawei Cloud server migration with Terraform. Default policy is SMS first (block-level disk copy); when precheck indicates incompatible source (`SMS.6504`), it switches to rsync staged migration (`full_sync -> incremental_sync -> cutover_sync`).

**Two migration paths:**

1. **Primary path (default): SMS** -- block-level disk copy via Server Migration Service
2. **Fallback path: rsync** -- when source is SMS-incompatible (e.g., `SMS.6504`, `SMS.6617`)

**What it produces:** A migrated ECS instance in the target region, with migration result JSON, network verification, and optional reusable migration bundle.

---

## What This Package Includes

```
Vmware-Migration/
|
|-- mgc-cross-region-migration/       The migration skill
|   |-- SKILL.md                      Metadata + step-by-step instructions
|   |-- scripts/
|   |   |-- mgc_migrate.py            Main migration script (precheck -> migrate -> postcheck)
|   |   +-- run_migration.sh          Shell wrapper for Terraform + Python
|   |-- references/
|   |   |-- runbook.md                Error codes and troubleshooting
|   |   |-- lessons-learned.md        Post-mortem insights from real migrations
|   |   |-- reuse-bundle.md           Bundle reuse guide
|   |   +-- migration-skill-summary.md  End-to-end summary
|   |-- assets/
|   |   |-- main.tf                   Terraform configuration
|   |   |-- variables.tf              Input variables
|   |   |-- terraform.tfvars          Default values
|   |   +-- bundles/                  Reusable migration bundles with diagrams
|   +-- tools/
|       +-- build_bundle_from_latest_out.sh  Bundle builder
|
+-- README.md                         (this file)
```

---

## Installation

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r mgc-cross-region-migration ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r mgc-cross-region-migration ~/.hermes/skills/infrastructure/
```

### Option C: Claude Code

```bash
mkdir -p ~/.claude/skills
cp mgc-cross-region-migration/SKILL.md ~/.claude/skills/mgc-cross-region-migration.md
```

---

## How to Use the Skill with an AI Agent

### Natural Triggers

```
"Migrate this VMware VM to Huawei Cloud ECS"
"Run cross-region migration from la-north-2 to la-south-2"
"Set up MGC migration with Terraform"
"Troubleshoot SMS error SMS.6504"
```

### Workflow Summary

```
Step 1: VALIDATE       Check prerequisites                    -> precheck
        |               Source registered in SMS, AK/SK perms
        |               target_image_id exists, VPC quota
        v
Step 2: PREPARE        Edit terraform.tfvars                  -> config ready
        |               source_server_id, target_image_id
        |               source_region, target_region
        v
Step 3: EXECUTE        terraform init && terraform apply      -> migration running
        |               Terraform calls run_migration.sh
        |               Which calls mgc_migrate.py
        |               SMS task created + started
        v
Step 4: VALIDATE       Check out/migration_result.json        -> success/failure
        |               Verify: migproject_id, task_id
        |               task_state, target_server_id
        |               Postcheck: VPC, EIP, security groups
        v
Step 5: TROUBLESHOOT   Match error codes to runbook           -> resolution
        |               SMS.6504 -> rsync fallback
        |               SMS.6617 -> MIGRATE_FILE fallback
        |               SMS.7605 -> cleanup + retry
        |               VPC.0114 -> free quota
```

---

## Quick Reference

### Execute Migration

```bash
cd mgc-cross-region-migration
# Edit assets/terraform.tfvars with your source/target details
terraform init
terraform apply -auto-approve
```

### Force Re-run (No Changes)

```bash
terraform apply -replace=terraform_data.mgc_region_migration -auto-approve
```

### Validate Outputs

```bash
cat out/migration_result.json
# Ensure: migproject_id, task_id, source_sms_server_id,
#          target_server_id, task_state
```

### Core API Chain

```
1. POST /v3/privacy-agreements       (accept privacy)
2. POST /v3/migprojects              (create migration project)
3. GET  /v3/sources                  (list source servers)
4. POST /v1.1/{project_id}/cloudservers  (create target ECS)
5. POST /v3/tasks                    (create migration task)
6. POST /v3/tasks/{task_id}/action   (start task)
```

---

## Troubleshooting Reference

| Error Code | Meaning | Action |
|------------|---------|--------|
| `SMS.6504` | Source incompatible | Switch to rsync staged migration |
| `SMS.6617` | Block migration failed | Fallback to `MIGRATE_FILE` |
| `SMS.6602` | Network issue | Retry with `use_public_ip=false` |
| `SMS.6603` | Agent not running | Install/start SMS Agent on source |
| `SMS.7605` | Task creation failed | Cleanup failed task + retry; check historical tasks |
| `SMS.7703` | Task doesn't exist | Query live task list by source |
| `SMS.8115` | Too many projects | Clean old migration projects (< 50) |
| `VPC.0114` | VPC quota exceeded | Free quota (delete unused VPC or increase) |

---

## Requirements

| Component | Requirement |
|------------|-----------|
| Source server | Registered in SMS/MGC, reachable/connected |
| Target | Huawei Cloud ECS in target region (e.g. `la-south-2`) |
| Credentials | AK/SK with IAM, SMS, ECS, VPC permissions |
| Target image | `target_image_id` exists in target region |
| Terraform | Installed locally |
| rsync | Available on source and target (for fallback path) |
| AI Agent | OpenCode / Hermes / Claude Code (optional) |

---

*Skills: mgc-cross-region-migration*
*Strategy: SMS first + rsync fallback + Terraform automation*
*Target: Huawei Cloud ECS (cross-region)*
