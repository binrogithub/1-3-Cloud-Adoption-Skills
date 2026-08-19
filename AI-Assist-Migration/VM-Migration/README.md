# VM Migration

Complete toolkit for migrating virtual machines from AWS, Azure, GCP, or on-premises to Huawei Cloud ECS using the Server Migration Service (SMS) with Terraform automation.

Includes 1 skill for AI agents (OpenCode, Hermes, Claude Code), Terraform templates, and a step-by-step migration workflow covering source discovery, agent installation, network preparation, migration execution, verification, and cleanup.

---

## What This Skill Does and Why It Is Useful

### The Problem

When migrating a VM to Huawei Cloud ECS, you need to:

- Know the exact OS, firmware type (UEFI/BIOS), disk layout, and network topology of both source and target
- Install the SMS Agent on the source server and verify it connects to the SMS service
- Ensure firmware compatibility between source and target (UEFI vs BIOS mismatches cause failures)
- Choose the right migration type (file-level vs block-level) based on OS and compatibility
- Monitor the migration through ordered subtasks, each reaching 100% before the next starts
- Verify the migrated ECS is reachable and functional before cleaning up SMS resources

### The Solution: SMS Server Template + Terraform

```
  DISCOVER           AGENT           NETWORK          TERRAFORM
  (source+target)    (install)       (connectivity)   (template+task)
      |                  |                |                |
      v                  v                v                v
  Phase 1            Phase 2          Phase 3          Phase 4

  APPLY&MONITOR      VERIFY          CLEANUP
  (run migration)    (SSH check)     (delete SMS res)
      |                  |                |
      v                  v                v
  Phase 5            Phase 6          Phase 7
```

#### Skill: huaweicloud-sms-migration

**What it does:** Migrates servers from AWS, Azure, GCP, on-prem, or other clouds to Huawei Cloud ECS using SMS. Covers the complete end-to-end workflow: source discovery, target environment discovery, SMS Agent installation, network preparation, Terraform automation, migration execution, verification, and cleanup.

**Why the SMS Server Template approach is better:**
- The `huaweicloud_sms_server_template` + `vm_template_id` approach lets SMS auto-create the target ECS with matching firmware, image, and disk layout
- Pre-creating an ECS (`target_server_id`) requires manual firmware matching, explicit disk configuration, and `migration_ip` -- it fails on UEFI/BIOS mismatches
- The template approach handles disk size differences automatically (HuaweiCloud images may have minimum disk requirements that exceed the source disk size)

**What it produces:** A migrated ECS instance accessible via SSH, with all source data intact, plus Terraform state for cleanup.

---

## What This Package Includes

```
VM-Migration/
|
|-- huaweicloud-sms-migration/       The migration skill
|   |-- SKILL.md                     Metadata + step-by-step instructions
|   |-- scripts/                     Executable migration scripts
|   |-- references/                  Documentation (firmware compat, agent install, etc.)
|   |-- assets/                      Terraform templates
|   +-- tools/                       Helper utilities
|
+-- README.md                        (this file)
```

---

## Installation

The skill is a markdown document (SKILL.md) with YAML frontmatter + instructions. Each AI agent loads it from its own path.

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r huaweicloud-sms-migration ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r huaweicloud-sms-migration ~/.hermes/skills/infrastructure/
```

### Option C: Claude Code

```bash
mkdir -p ~/.claude/skills
cp huaweicloud-sms-migration/SKILL.md ~/.claude/skills/huaweicloud-sms-migration.md
```

---

## How to Use the Skill with an AI Agent

### Natural Triggers

```
"Migrate this AWS EC2 instance to Huawei Cloud ECS"
"Move my on-prem VM to Huawei Cloud"
"Set up SMS migration for this server"
"Discover the source server and target environment for migration"
```

### Workflow Summary

```
Phase 1: DISCOVER       Inventory source + target           -> source_info.json
         |               OS, firmware, disks, network, flavor
         v
Phase 2: AGENT          Install SMS Agent on source         -> agent registered
         |               Verify connected: true, checks: OK
         v
Phase 3: NETWORK        Decide connectivity mode            -> use_public_ip / VPN
         |               Check CIDR overlap, EIP requirements
         v
Phase 4: TERRAFORM      Create SMS template + task          -> main.tf, variables.tf
         |               Use SMS Server Template approach
         v
Phase 5: APPLY&MONITOR  terraform init && terraform apply   -> migration task running
         |               Monitor subtask progression via ShowTask
         v
Phase 6: VERIFY         SSH to migrated ECS                 -> connectivity confirmed
         |               Compare source vs target disk/data
         v
Phase 7: CLEANUP        Delete SMS task + template          -> only ECS persists
```

---

## Quick Reference

### Source Discovery (AWS example)

```bash
aws ec2 describe-instances --region <region> --instance-ids <id> \
  --query 'Reservations[0].Instances[0].{OS:ImageId,Type:InstanceType,
    PrivateIP:PrivateIpAddress,PublicIP:PublicIpAddress}' --output json

# Check firmware type
ssh <user>@<source-ip> "ls /sys/firmware/efi 2>/dev/null && echo UEFI || echo BIOS"
```

### Target Discovery (Huawei Cloud)

```bash
hcloud VPC ListVpcs --cli-region=<target-region> --cli-output=json
hcloud ECS ListFlavors --cli-region=<target-region> --cli-output=json
hcloud IMS ListImages --cli-region=<target-region> --imagetype=gold --os_type=Linux --cli-output=json
```

### SMS Agent Verification

```bash
hcloud SMS ListServers --cli-region=<sms-region> --cli-output=json
# Verify: state="waiting", connected=true, all checks OK
```

### Terraform Execution

```bash
terraform init
terraform plan
terraform apply -auto-approve
```

---

## Requirements

| Component | Requirement |
|------------|-----------|
| Source server | AWS EC2 / Azure VM / GCP GCE / on-prem VM, SSH access, root/sudo |
| Target | Huawei Cloud ECS (any region) |
| SMS API | Available in specific regions (e.g. `ap-southeast-3`) -- target ECS can be in any region |
| Firmware | Source and target must use same type (UEFI or BIOS) -- template handles automatically |
| Credentials | Huawei Cloud AK/SK with IAM, SMS, ECS, VPC permissions |
| AI Agent | OpenCode / Hermes / Claude Code (optional -- scripts can run standalone) |

---

## Key Rules

1. **DISCOVER before ACT** -- always inventory source and target before creating SMS resources
2. **PREFER SMS SERVER TEMPLATE** over pre-created ECS -- auto-handles firmware, image, disk matching
3. **VERIFY FIRMWARE COMPATIBILITY** -- UEFI/BIOS mismatch causes migration failure
4. **SMS API REGION != TARGET REGION** -- SMS API in specific regions, target ECS in any region
5. **CHOOSE MIGRATION TYPE WISELY** -- `MIGRATE_FILE`: better compat, slower; `MIGRATE_BLOCK`: faster, Windows-only
6. **CLEAN UP AFTER MIGRATION** -- delete SMS task and template; migrated ECS persists

---

*Skills: huaweicloud-sms-migration*
*Strategy: SMS Server Template + Terraform automation*
*Target: Huawei Cloud ECS*
