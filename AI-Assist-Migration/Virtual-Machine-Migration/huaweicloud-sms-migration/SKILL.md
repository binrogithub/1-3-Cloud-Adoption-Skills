---
name: huaweicloud-sms-migration
description: Migrate servers to Huawei Cloud ECS using SMS (Server Migration Service). Handles cross-cloud (AWS, Azure, GCP, on-prem) Linux/Windows server migration with agent installation, network connectivity, firmware compatibility, and Terraform automation. Use when the user wants to migrate or replicate a physical or virtual server to Huawei Cloud.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: server-migration-huaweicloud
---

# Huawei Cloud SMS Server Migration

Migrate servers from AWS, Azure, GCP, on-prem, or other clouds to Huawei Cloud ECS using the Server Migration Service (SMS). This skill covers the complete end-to-end workflow: source discovery, target environment discovery, SMS Agent installation, network preparation, Terraform automation, migration execution, verification, and cleanup.

## Rules

1. **DISCOVER before ACT** — always inventory the source server and target environment before creating any SMS resources. Know the exact OS, version, firmware type, disk layout, network topology, and flavor of both sides.
2. **PREFER SMS SERVER TEMPLATE over pre-created ECS** — the `huaweicloud_sms_server_template` + `vm_template_id` approach lets SMS auto-create the target ECS with matching firmware, image, and disk layout. Pre-creating an ECS (`target_server_id`) requires manual firmware matching, explicit disk configuration, and `migration_ip` — it fails on UEFI/BIOS mismatches and is only recommended when you need exact control over the target server.
3. **VERIFY FIRMWARE COMPATIBILITY** — source and target must use the same firmware type (UEFI or BIOS). Most cloud providers use UEFI for modern Linux images; HuaweiCloud public images may use BIOS. The template approach handles this automatically. See [references/firmware-compatibility.md](references/firmware-compatibility.md).
4. **SMS API REGION ≠ TARGET REGION** — the SMS service API is only available in specific regions (e.g. `ap-southeast-3`). The target ECS can be in any HuaweiCloud region (e.g. `la-north-2`). Always use `--cli-region=<sms-region>` for SMS API calls, but set the provider `region = <target-region>` in Terraform.
5. **NEVER GUESS CREDENTIALS** — always ask the user for HuaweiCloud AK/SK and source server SSH credentials. Never extract them from state files, logs, or environment variables.
6. **VERIFY AGENT CONNECTION** — after installing the SMS Agent, always check that the source server shows `connected: true` and all pre-migration checks pass before creating a migration task.
7. **CHOOSE MIGRATION TYPE WISELY** — `MIGRATE_FILE` (file-level): better compatibility, slower, works for all Linux. `MIGRATE_BLOCK` (block-level): faster, but Windows-only and may have compatibility issues on Linux.
8. **MONITOR SUBTASK PROGRESSION** — SMS tasks have ordered subtasks. Each must reach 100% before the next starts. Monitor via `ShowTask` API. See the subtask sequence in Phase 5.
9. **PLAN FOR DISK SIZE DIFFERENCES** — target disk must be ≥ source disk. HuaweiCloud images may have minimum disk requirements (e.g. 10GB) that exceed the source disk size (e.g. 8GB). The template approach handles this automatically.
10. **CLEAN UP AFTER MIGRATION** — delete the SMS task and template after successful migration and verification. The migrated ECS persists; only SMS metadata is cleaned up.

## Workflow Overview

```
Phase 1          Phase 2          Phase 3          Phase 4
DISCOVER    →    AGENT       →    NETWORK    →    TERRAFORM
(source+target)  (install)       (connectivity)   (template+task)

Phase 5          Phase 6          Phase 7
APPLY&MONITOR →  VERIFY     →    CLEANUP
(run migration)  (SSH check)      (delete SMS res)
```

## Phase 1: DISCOVER

Gather complete information about the source server and target environment.

### Source inventory

Use the source cloud's CLI or API to collect:

| Item | Why needed | Example |
|------|-----------|---------|
| Instance ID / name | Reference | `i-059a39bdab9198a58` |
| OS type + version | SMS task config | Ubuntu 22.04, Windows 2019 |
| Firmware type (UEFI/BIOS) | Firmware compatibility | UEFI (check via `ls /sys/firmware/efi`) |
| vCPU / RAM | Flavor matching | 2 vCPU / 8 GB |
| Disk layout (device, size, partitions) | Disk config | `/dev/nvme0n1` 8GB, GPT, 2 partitions |
| Network (VPC, subnet, SG, IP) | Target network mapping | 10.0.1.156, SG allows 22+80 |
| Public/private IP | Migration network | 18.119.129.93 |
| SSH key or password | Agent install + verification | Ed25519 key |

```bash
# AWS example
aws ec2 describe-instances --region <region> \
  --instance-ids <id> \
  --query 'Reservations[0].Instances[0].{OS:ImageId,Type:InstanceType,
    PrivateIP:PrivateIpAddress,PublicIP:PublicIpAddress,
    VPC:VpcId,Subnet:SubnetId,SGs:SecurityGroups[*].GroupId,
    Key:KeyName,AZ:Placement.AvailabilityZone}' --output json

# Check firmware type (run on source server)
ssh <user>@<source-ip> "ls /sys/firmware/efi 2>/dev/null && echo UEFI || echo BIOS"

# Get disk layout
ssh <user>@<source-ip> "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,PARTTYPE && df -h"
```

### Target inventory (Huawei Cloud)

```bash
# List existing VPCs
hcloud VPC ListVpcs --cli-region=<target-region> --cli-output=json

# List subnets in a VPC
hcloud VPC ListSubnets --cli-region=<target-region> --vpc_id=<vpc-id> --cli-output=json

# List security groups
hcloud VPC ListSecurityGroups --cli-region=<target-region> --cli-output=json

# List availability zones
hcloud ECS NovaListAvailabilityZones --cli-region=<target-region> --cli-output=json

# List flavors (match source vCPU/RAM)
hcloud ECS ListFlavors --cli-region=<target-region> --cli-output=json

# List public images (match source OS)
hcloud IMS ListImages --cli-region=<target-region> \
  --imagetype=gold --os_type=Linux --cli-output=json

# Check existing ECS instances
hcloud ECS ListServersDetails --cli-region=<target-region> --cli-output=json

# Check SMS source servers (already registered)
hcloud SMS ListServers --cli-region=<sms-region> --cli-output=json
```

### What to collect

| Item | Source | Target |
|------|--------|--------|
| OS + version | e.g. Ubuntu 22.04 | Match or compatible |
| Firmware | UEFI or BIOS | Must match (template handles auto) |
| vCPU / RAM | e.g. 2 vCPU / 8 GB | Match via flavor |
| Disk size | e.g. 8 GB | ≥ source (min 10 GB for some images) |
| VPC CIDR | e.g. 10.0.0.0/16 | Existing or create new |
| Subnet | e.g. 10.0.1.0/24 | Existing in target VPC |
| Security group | e.g. allow 22, 80 | Existing or create new |
| Public IP | Yes/No | Needed for Internet migration |

## Phase 2: SMS AGENT INSTALL

Install the SMS Agent on the source server to register it with the SMS service.

### Prerequisites

- HuaweiCloud AK/SK (ask the user — never guess)
- SMS endpoint region (e.g. `sms.ap-southeast-3.myhuaweicloud.com`)
- SSH access to the source server
- Root or sudo privileges on the source server

### Installation

The SMS Agent installer is interactive with 6 prompts. For automation, use a Python `pexpect` script or similar.

See [references/sms-agent-install.md](references/sms-agent-install.md) for the complete installation procedure, including the pexpect script template and all 6 prompts.

### Verification

```bash
# Check source server registered with SMS
hcloud SMS ListServers --cli-region=<sms-region> --cli-output=json

# Verify: state should be "waiting", connected should be true
# Check all pre-migration checks passed
hcloud SMS ShowServer --source_id=<source-id> --cli-region=<sms-region> --cli-output=json
```

The source server must show:
- `state: "waiting"`
- `connected: true`
- All `checks` with `result: "OK"`

## Phase 3: NETWORK

Decide how SMS will connect the source agent to the target ECS.

### Decision tree

```
Source and target in same HuaweiCloud VPC?
├── YES → use_public_ip = false (private network)
└── NO (cross-cloud or on-prem)
    ├── VPN available with non-overlapping CIDRs?
    │   ├── YES → use_public_ip = false, migration_ip = <target private IP>
    │   └── NO → use_public_ip = true (Internet, requires target EIP)
```

### CIDR overlap check

If both source and target VPCs use the same CIDR (e.g. both 10.0.0.0/16), VPN is impossible without re-IP or NAT. Use public IP migration instead.

### Public IP migration (most common for cross-cloud)

1. Target ECS gets an EIP (handled by `bandwidth_size` in SMS template or inline in compute_instance)
2. SMS Agent connects to target via public IP
3. `use_public_ip = true` in the SMS task

### VPN migration (not yet tested, but supported)

1. Establish VPN between source and target VPCs (non-overlapping CIDRs)
2. `use_public_ip = false` in the SMS task
3. `migration_ip = <target private IP>` in the SMS task

## Phase 4: TERRAFORM

Create SMS resources via Terraform. Always use the **SMS Server Template** approach.

### Provider configuration

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "1.93.0"  # or latest
    }
  }
}

provider "huaweicloud" {
  region = var.target_region  # e.g. la-north-2
}
```

### Data sources (reference existing infrastructure)

```hcl
data "huaweicloud_availability_zones" "demo" {}

data "huaweicloud_vpc" "demo" {
  name = var.vpc_name
}

data "huaweicloud_vpc_subnet" "demo" {
  name = var.subnet_name
}

data "huaweicloud_networking_secgroup" "demo" {
  name = var.secgroup_name
}

data "huaweicloud_sms_source_servers" "demo" {
  id = var.source_server_id
}
```

### Resources (RECOMMENDED: SMS Server Template)

```hcl
resource "huaweicloud_sms_server_template" "demo" {
  name               = "${var.target_server_name}-template"
  availability_zone  = data.huaweicloud_availability_zones.demo.names[0]
  vpc_id             = data.huaweicloud_vpc.demo.id
  subnet_ids         = [data.huaweicloud_vpc_subnet.demo.id]
  security_group_ids = [data.huaweicloud_networking_secgroup.demo.id]
  flavor             = var.flavor_id
  volume_type        = "SAS"
  target_server_name = var.target_server_name
  bandwidth_size     = 10  # Mbit/s for migration EIP
}

resource "huaweicloud_sms_task" "migration" {
  type               = "MIGRATE_FILE"
  os_type            = "LINUX"
  source_server_id   = data.huaweicloud_sms_source_servers.demo.servers[0].id
  vm_template_id     = huaweicloud_sms_server_template.demo.id
  action             = "start"
  start_target_server = true
  use_public_ip      = true

  lifecycle {
    ignore_changes = [
      syncing, action, auto_start, start_network_check,
      over_speed_threshold, is_need_consistency_check,
    ]
  }
}
```

### Alternative: Pre-create ECS (use with caution)

Only use this approach if you need exact control over the target ECS. Requires:
- Matching firmware (UEFI source → UEFI image on target)
- Explicit `target_server_disks` with `disk_id` and `physical_volumes`
- `migration_ip` set to target's public IP
- Target ECS running for SSL_CONFIG step

See [references/terraform-sms-resources.md](references/terraform-sms-resources.md) for the full pre-create ECS template and all resource schemas.

### Key configuration decisions

| Decision | Options | Recommendation |
|----------|---------|---------------|
| Migration approach | Template, Pre-create ECS | **Template** (handles firmware auto) |
| `type` | MIGRATE_FILE, MIGRATE_BLOCK | MIGRATE_FILE (compatibility) |
| `os_type` | LINUX, WINDOWS | Match source |
| `volume_type` | SAS, SSD, GPSSD | SAS (cost-effective) |
| `use_public_ip` | true, false | true for cross-cloud |
| `start_target_server` | true, false | true (auto-start after migration) |

## Phase 5: APPLY & MONITOR

### Apply

```bash
HW_ACCESS_KEY=<ak> HW_SECRET_KEY=<sk> terraform init
HW_ACCESS_KEY=<ak> HW_SECRET_KEY=<sk> terraform plan
HW_ACCESS_KEY=<ak> HW_SECRET_KEY=<sk> terraform apply -auto-approve
```

### Monitor

```bash
hcloud SMS ShowTask --task_id=<task-id> --cli-region=<sms-region> --cli-output=json
```

### Subtask progression

```
CREATE_CLOUD_SERVER  → SMS creates target ECS from template
SSL_CONFIG           → Establish secure channel (source agent ↔ target)
ATTACH_AGENT_IMAGE   → Attach SMS agent image to target
FORMAT_DISK_LINUX    → Format target disk(s)
MIGRATE_LINUX_FILE   → Actual file/data replication
CONFIGURE_LINUX_FILE → Configure migrated OS (network, fstab, etc.)
DETTACH_AGENT_IMAGE  → Detach SMS agent image
```

For Windows servers, the subtasks differ slightly (block-level migration).

### Status values

| State | Meaning |
|-------|---------|
| `RUNNING` | Migration in progress |
| `MIGRATE_SUCCESS` | Migration completed successfully |
| `MIGRATE_FAIL` | Migration failed — check `error_json` |
| `PAUSED` | Migration paused (can be resumed) |

### Monitoring script

```bash
# Poll until task completes
TASK_ID="<task-id>"
SMS_REGION="<sms-region>"
while true; do
  STATE=$(hcloud SMS ShowTask --task_id=$TASK_ID --cli-region=$SMS_REGION 2>&1 | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['state'])")
  echo "$(date +%H:%M:%S) State: $STATE"
  if [ "$STATE" = "MIGRATE_SUCCESS" ] || [ "$STATE" = "MIGRATE_FAIL" ]; then break; fi
  sleep 30
done
```

## Phase 6: VERIFY

After migration completes (`MIGRATE_SUCCESS`), verify the migrated ECS.

### Get target ECS details

```bash
# From the SMS task response
TARGET_VM_ID=$(hcloud SMS ShowTask --task_id=<task-id> --cli-region=<sms-region> 2>&1 | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['target_server']['vm_id'])")

# Show ECS details
hcloud ECS ShowServer --server_id=$TARGET_VM_ID --cli-output=json
```

### SSH verification

```bash
# SSH into migrated server using source SSH key
ssh -i <source-key.pem> <user>@<target-public-ip> "
  hostname &&
  uname -a &&
  cat /etc/os-release | head -5 &&
  df -h / &&
  whoami
"
```

### What to verify

| Check | Expected | Notes |
|-------|----------|-------|
| Hostname | Same as source | May need updating for new env |
| OS version | Same as source | Exact match |
| Kernel | Same as source | May need updating for HuaweiCloud |
| Disk size | ≥ source | SMS may resize to fit min image req |
| Users | Same as source | SSH keys preserved |
| Application data | Present and intact | Check app-specific files/services |
| Network | Target VPC/subnet | IP will differ from source |

## Phase 7: CLEANUP

After successful migration and verification:

```bash
# Option A: Terraform destroy (removes SMS task + template, keeps migrated ECS)
HW_ACCESS_KEY=<ak> HW_SECRET_KEY=<sk> terraform destroy -auto-approve

# Option B: Manual cleanup via API
hcloud SMS DeleteTask --task_id=<task-id> --cli-region=<sms-region>
hcloud SMS DeleteTemplate --template_id=<template-id> --cli-region=<sms-region>
```

The migrated ECS persists — only SMS metadata (task, template) is cleaned up.

### Post-migration tasks

1. **Update hostname** — `hostnamectl set-hostname <new-name>` (source hostname is preserved)
2. **Update kernel** (optional) — install HuaweiCloud kernel for better driver support
3. **Configure monitoring** — CES, HSS agents
4. **Update DNS** — point to new public IP
5. **Revert source changes** — any temp SG rules, public IP, etc.

## Quick Reference: SMS API Flow

```
1. ListServers              → verify source server registered
2. ShowServer               → check pre-migration checks
3. Create template (TF)     → huaweicloud_sms_server_template
4. Create task (TF)         → huaweicloud_sms_task with vm_template_id
5. ShowTask                 → monitor subtask progression
6. ShowServer (ECS)         → verify migrated ECS
7. SSH                      → verify OS, data, users
8. DeleteTask + DeleteTemplate → cleanup
```

## Quick Reference: Terraform Resources

| Resource | Purpose |
|----------|---------|
| `huaweicloud_sms_server_template` | Target server config (VPC, subnet, SG, flavor, AZ) |
| `huaweicloud_sms_task` | Migration task (links source + template, starts migration) |
| `huaweicloud_compute_instance` | Pre-create ECS (alternative, use with caution) |
| `data.huaweicloud_sms_source_servers` | Look up registered source server |

## References

- [SMS Agent Installation](references/sms-agent-install.md) — download, interactive prompts, pexpect automation, verification
- [Terraform SMS Resources](references/terraform-sms-resources.md) — full resource schemas, both approaches, data sources
- [Firmware Compatibility](references/firmware-compatibility.md) — UEFI/BIOS, NVMe/VBD, GPT/MBR, how to handle mismatches
- [Troubleshooting](references/troubleshooting.md) — error codes, common failures, fixes, hcloud CLI limitations
