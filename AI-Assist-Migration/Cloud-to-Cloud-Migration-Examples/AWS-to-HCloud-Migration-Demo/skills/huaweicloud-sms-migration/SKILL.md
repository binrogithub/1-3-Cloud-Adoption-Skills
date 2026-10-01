---
name: huaweicloud-sms-migration
description: Migrate servers to Huawei Cloud ECS using SMS (Server Migration Service), with an image-export fallback (AMI -> S3 -> OBS -> IMS -> ECS) for sources SMS cannot handle. Handles cross-cloud (AWS, Azure, GCP, on-prem) Linux/Windows server migration with agent installation, network connectivity, firmware compatibility, and Terraform automation. Use when the user wants to migrate or replicate a physical or virtual server to Huawei Cloud.
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
3. **VERIFY FIRMWARE COMPATIBILITY** — source and target must use the same firmware type (UEFI or BIOS). Most cloud providers use UEFI for modern Linux images; HuaweiCloud public images may use BIOS. The template approach handles this automatically.
4. **SMS API REGION ≠ TARGET REGION** — the SMS service API is only available in specific regions (e.g. `ap-southeast-3`). The target ECS can be in any HuaweiCloud region (e.g. `sa-brazil-1`, `la-north-2`). Always use `--cli-region=<sms-region>` for SMS API calls. In Terraform, set the provider `region = <sms-region>` and add `region = <target-region>` + `project_id = <target-project-id>` on each resource if the target region differs from the SMS region.
5. **NEVER GUESS CREDENTIALS** — always ask the user for HuaweiCloud AK/SK and source server SSH credentials. Never extract them from state files, logs, or environment variables.
6. **VERIFY AGENT CONNECTION** — after installing the SMS Agent, always check that the source server shows `connected: true` and all pre-migration checks pass before creating a migration task.
7. **CHOOSE MIGRATION TYPE WISELY** — `MIGRATE_FILE` (file-level): better compatibility, slower, works for all Linux. `MIGRATE_BLOCK` (block-level): faster, but Windows-only and may have compatibility issues on Linux. For Amazon Linux 2, use `MIGRATE_FILE` — `MIGRATE_BLOCK` fails with `SMS.6617` (kernel version does not support Linux block migration).
8. **MONITOR SUBTASK PROGRESSION** — SMS tasks have ordered subtasks. Each must reach 100% before the next starts. Monitor via `ShowTask` API.
9. **PLAN FOR DISK SIZE DIFFERENCES** — target disk must be ≥ source disk. HuaweiCloud images may have minimum disk requirements (e.g. 10GB) that exceed the source disk size (e.g. 8GB). The template approach handles this automatically. In Terraform, `target_server_disks` `size` is in **MB**, not bytes (the provider multiplies by 2^20 internally).
10. **CLEAN UP AFTER MIGRATION** — delete the SMS task and template after successful migration and verification. The migrated ECS persists; only SMS metadata is cleaned up.
11. **RUN THE PREFLIGHT FIRST** — always execute Phase 0 (Preflight Compatibility Check) before installing the agent or creating any resource. It is read-only and fast, and it catches every known blocker while the fix is still cheap.
12. **SELECT THE MIGRATION PATH FROM THE PREFLIGHT RESULT** — `path: auto` uses the SMS path when the source is compatible and falls back to the image-based path (Phase 8) when it is not. **However**, the preflight's OS list is incomplete — Amazon Linux 2 (`AMZN_2_2_64BIT`) is not listed but SMS **does** support it (verified end-to-end). If the only blocking check is `OS_VERSION` for Amazon Linux 2, override to the SMS path.
13. **FIX THE FOUR KNOWN PITFALLS PROACTIVELY** — (a) unsupported OS version (`SMS.6504`), (b) `fstab`/`/dev/root` device-name mapping, (c) missing HuaweiCloud VPC/subnet/SG permissions, (d) agent restart that hangs on the interactive `startup.sh` (`EOFError`). Phase 0 checks all four.
14. **DELIVER THE TARGET PASSWORD AT MIGRATION TIME** — file-level migration copies the source `/etc/shadow` verbatim, so the target inherits the source's accounts. Set the password on the SMS server template or in the SMS console destination step. `ResetServerPassword` API does not work on migrated images (returns empty body, no effect).
15. **CHECK THE TARGET `sshd` AUTH MODE BEFORE SSH VERIFY** — migrated Linux images often allow `publickey` only. To enable password auth, write `/etc/ssh/sshd_config.d/00-enable-pw.conf` with both `PasswordAuthentication yes` and `PermitRootLogin yes` — the `00-` prefix is mandatory (lexicographic order, first-match-wins).
16. **VERIFY THE FILE SET WITH A SOURCE/TARGET TREE DIFF** — file-level migration is a single `tar` of the root filesystem with no incremental sync. Diff the two `find / -xdev` trees before trusting the result.
17. **IMAGE PATH (Phase 8): FIX THE FIVE PITFALLS PROACTIVELY** — (a) the AWS `vmimport` role must carry `sts:ExternalId: vmimport`; (b) IMS import of a VMDK must be normal import (`is_quick_import=False`); (c) use **obsutil** for S3→OBS transfer (not the script's `s3_to_obs.py` which is too slow, and not boto3 which has `XAmzContentSHA256Mismatch` with OBS); (d) `SATA` may not exist in the target region — use `GPSSD`; (e) when the keypair API returns 500, inject the public key via cloud-init `user_data`.
18. **IMAGE PATH: THE ECS WILL BE UNREACHABLE WITHOUT NETWORK DRIVER FIX** — the imported image has source-cloud network drivers (AWS: `ena`/`ixgbevf`, Huawei Cloud: `virtio`). The ECS boots but the network interface never comes up. **Before attempting the image path**, verify that `virtio_net` is loaded on the source (`lsmod | grep virtio_net`). If not, install it and rebuild the AMI. After migration, use the VNC console to manually configure the network if the ECS is unreachable. This is the **critical gap** in the image path.
19. **S3 BUCKET CREATION IN us-east-1** — AWS S3 bucket creation in `us-east-1` must NOT include `CreateBucketConfiguration.LocationConstraint` (it's the default region). The `aws_image_path.py prep` script must be patched to skip this for `us-east-1`.
20. **CLOUD-INIT USER NAME VARIES BY OS** — Amazon Linux 2 uses `ec2-user`, Ubuntu uses `ubuntu`, CentOS uses `centos`. The cloud-init `user_data` must write SSH keys to the correct user's `~/.ssh/authorized_keys`. Hardcoding `/home/ubuntu/` fails for Amazon Linux 2.
21. **TERRAFORM PROVIDER QUIRKS FOR sa-brazil-1** — `sa-brazil-1` is not in the supported SMS CLI regions list. Use provider `region = "ap-southeast-3"` with `region = "sa-brazil-1"` and `project_id` overrides on each resource. Available volume types: ESSD2, ESSD, GPSSD2, SAS, GPSSD, SSD, SATA (no GP3). Flavor `c2.large` is sold out — use `s6.large.2` (2 vCPU, 4GB).

## Workflow Overview

```
Phase 0          Phase 1          Phase 2          Phase 3
PREFLIGHT   →    DISCOVER    →    AGENT       →    NETWORK
(compat check)   (source+target)  (install)       (connectivity)

Phase 4          Phase 5          Phase 6          Phase 7
TERRAFORM   →    APPLY&MONITOR →  VERIFY     →    CLEANUP
(template+task)  (run migration)  (SSH check)      (delete SMS res)

Path selection: Phase 0 decides SMS vs image (image path = Phase 8).
```

## Phase 0: PREFLIGHT (COMPATIBILITY CHECK)

Run this **before** installing the agent or creating any resource.

### The blocking pitfalls (all automated here)

| # | Pitfall | Symptom | Check |
|---|---------|---------|-------|
| 1 | Unsupported OS version | Agent installs, source stays `unavailable`, task returns `SMS.6504` | `OS_VERSION` |
| 2 | `fstab` device mapping (`/dev/root`) | `ShowServer` pre-check `FSTAB` fails | `FSTAB` |
| 3 | Missing HuaweiCloud VPC/subnet/SG permissions | Template/task creation fails with `SMS.0101` / `VPC.xxxx` | `VPC_PERMISSION` |
| 4 | Agent restart hangs on interactive installer | `./linuxmain 0` dies with `EOFError` | `AGENT_RESTART` |

Non-blocking checks (warn only): `RSYNC`, `ROUTE`, `FIRMWARE`, `DISK_INFO`.

### Known false positive: Amazon Linux 2

The preflight script derives the OS identifier as `AMZN_2_2_64BIT` from `/etc/os-release`, which is NOT in the SMS supported list. However, SMS **does** support Amazon Linux 2 — the agent detects it as `Amazon_2_0_64BIT` and migration succeeds end-to-end (verified with `MIGRATE_FILE`). If the only blocking check is `OS_VERSION` for Amazon Linux 2, **override to the SMS path**.

### Run it

**Source-side**:

```bash
scp scripts/preflight.sh <user>@<source-ip>:/tmp/preflight.sh
ssh <user>@<source-ip> "sudo bash /tmp/preflight.sh" | tee preflight-source.json
```

Exit code: `0` = SMS-compatible, `2` = at least one blocking issue.

**HuaweiCloud-side**:

```bash
hcloud SMS ListServers    --cli-region=<sms-region>   --cli-output=json
hcloud VPC ListVpcs       --cli-region=<target-region> --cli-output=json
hcloud VPC ListSubnets    --cli-region=<target-region> --vpc_id=<vpc-id>
hcloud VPC ListSecurityGroups --cli-region=<target-region>
hcloud ECS ListFlavors    --cli-region=<target-region>
```

### Path selection

```
                     Phase 0 preflight
                            |
            +---------------+---------------+
            |                               |
     all blocking checks OK          a blocking check failed
            |                               |
     SMS path (Phases 1-7)          Image path (Phase 8)
```

**Exception**: If the only blocking check is `OS_VERSION` for Amazon Linux 2, use the SMS path (known false positive).

### Path comparison (SMS vs image)

| Aspect | SMS path | Image path |
|--------|----------|------------|
| Agent required | Yes | No |
| Time | ~10-30 min | ~2+ hours |
| OS support | Broad (but list incomplete) | Any (disk copy) |
| Network drivers | Handled by SMS | **Must match source** (critical gap) |
| Post-migration access | SSH with source key | May be unreachable (network drivers) |
| Data fidelity | File-level (tar) | Block-level (exact disk copy) |

## Phase 1: DISCOVER

### Source server

```bash
ssh <user>@<source-ip> "uname -a; cat /etc/os-release; df -h; lsblk; free -h; ip addr"
```

### Target environment

```bash
hcloud VPC ShowVpc --vpc_id=<vpc-id> --cli-region=<target-region>
hcloud VPC ShowSubnet --subnet_id=<subnet-id> --cli-region=<target-region>
hcloud VPC ShowSecurityGroup --security_group_id=<sg-id> --cli-region=<target-region>
hcloud ECS ListFlavors --cli-region=<target-region> | grep -E "s6|t6|c1"
```

## Phase 2: AGENT INSTALLATION

```bash
# Download and install SMS Agent on the source server
ssh <user>@<source-ip> "sudo bash -c '
  cd /tmp
  wget -q https://sms-resource-intl-ap-southeast-3.obs.ap-southeast-3.myhuaweicloud.com/SMS-Agent.tar.gz
  tar xzf SMS-Agent.tar.gz
  cd SMS-Agent
  ./setup.sh
'"
```

**Known issue**: `setup.sh` is interactive (prompts for AK/SK). Use `pexpect` or pipe input:

```python
import pexpect
child = pexpect.spawn('ssh ... "sudo bash /tmp/SMS-Agent/setup.sh"')
child.expect('AK:')
child.sendline('<AK>')
child.expect('SK:')
child.sendline('<SK>')
child.expect(pexpect.EOF)
```

## Phase 3: NETWORK CONNECTIVITY

Ensure the source server can reach the SMS service endpoint:

```bash
ssh <user>@<source-ip> "curl -s https://sms.ap-southeast-3.myhuaweicloud.com/ | head -1"
```

## Phase 4: TERRAFORM (TEMPLATE + TASK)

### Working Terraform config (verified end-to-end)

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.60"
    }
  }
}

# Provider region = SMS API region (not target region)
provider "huaweicloud" {
  region     = "ap-southeast-3"
  access_key = "<AK>"
  secret_key = "<SK>"
}

# Data sources for target environment
data "huaweicloud_vpc_vpc" "target" {
  id    = "<vpc-id>"
  region    = "sa-brazil-1"
  project_id = "<project-id>"
}

data "huaweicloud_vpc_subnet" "target" {
  id        = "<subnet-id>"
  region    = "sa-brazil-1"
  project_id = "<project-id>"
}

# SMS Server Template
resource "huaweicloud_sms_server_template" "template" {
  name        = "migration-template"
  region      = "sa-brazil-1"
  project_id  = "<project-id>"
  flavor_id   = "s6.large.2"
  vpc_id      = data.huaweicloud_vpc_vpc.target.id
  subnet_id   = data.huaweicloud_vpc_subnet.target.id
  security_group_id = "<sg-id>"
  volume_type = "GPSSD"
  bandwidth_size = 5
}

# SMS Migration Task
resource "huaweicloud_sms_task" "task" {
  name           = "migration-task"
  region         = "sa-brazil-1"
  project_id     = "<project-id>"
  source_server_id = "<source-server-id>"
  vm_template_id = huaweicloud_sms_server_template.template.id
  type           = "MIGRATE_FILE"
  action         = "start"

  lifecycle {
    ignore_changes = [state, migration_ip]
  }
}
```

### Key Terraform notes

- **Provider region**: Must be `ap-southeast-3` (SMS API region), NOT the target region
- **Resource region/project_id**: Add `region` and `project_id` overrides for `sa-brazil-1`
- **Volume type**: Use `GPSSD` (not `GP3` — not available in `sa-brazil-1`)
- **Flavor**: `s6.large.2` (2 vCPU, 4GB) — `c2.large` is sold out
- **Bandwidth**: `bandwidth_size = 5` is required (without it, `SMS.6562` "Failed to obtain target server IP address")
- **Migration type**: `MIGRATE_FILE` for Amazon Linux 2 (`MIGRATE_BLOCK` fails with `SMS.6617`)
- **lifecycle ignore_changes**: Prevents Terraform from trying to manage `state` and `migration_ip`

## Phase 5: APPLY & MONITOR

```bash
terraform init
terraform plan
terraform apply
```

Monitor the task:

```bash
hcloud SMS ShowTask --cli-region=ap-southeast-3 --task_id=<task-id>
```

Subtask sequence: `start` → `attach_volume` → `create_snapshot` → `copy_data` → `detach_volume` → `delete_snapshot` → `stop`

## Phase 6: VERIFY

```bash
# Get the migrated ECS ID from the task
hcloud SMS ShowTask --cli-region=ap-southeast-3 --task_id=<task-id> | grep target_server_id

# SSH to the migrated ECS
ssh -i <source-key> ec2-user@<ecs-public-ip> "hostname; uname -r; df -h; ls /var/www/html/"
```

## Phase 7: CLEANUP

```bash
# Delete SMS task and template
hcloud SMS DeleteTask --cli-region=ap-southeast-3 --task_id=<task-id>
hcloud SMS DeleteTemplate --cli-region=ap-southeast-3 --template_id=<template-id>

# Delete source server from SMS
hcloud SMS DeleteServer --cli-region=ap-southeast-3 --server_id=<source-server-id>

# Terraform destroy (if needed)
terraform destroy
```

## Phase 8: IMAGE MIGRATION PATH (FALLBACK)

Used when Phase 0 finds a blocking incompatibility that SMS cannot handle.

### When this path applies

| Trigger | Why SMS cannot be used |
|---------|------------------------|
| `OS_VERSION` = BLOCK (truly unsupported OS) | Source OS is not in SMS supported list |
| `FSTAB` = BLOCK, unfixable | Root device cannot be remapped |
| `FIRMWARE` mismatch | Boot mode cannot be matched |
| Source stays `unavailable` after correct agent install | Product-level limitation |

**Note**: Amazon Linux 2 is NOT a valid trigger — see the false positive note in Phase 0.

### End-to-end flow

```
AWS EC2 → create-image (AMI) → export-image (VMDK to S3) → S3 → OBS → IMS import → ECS → verify
```

### Phase 8a: AWS AMI + Export

```bash
# Patch: skip LocationConstraint for us-east-1
python scripts/aws_image_path.py prep --instance-id <id> --region us-east-1 --bucket <bucket>
python scripts/aws_image_path.py export --instance-id <id> --region us-east-1 --bucket <bucket>
python scripts/export_wait.py 3600
```

**Bug**: `aws_image_path.py prep` fails in `us-east-1` with `InvalidLocationConstraint`. Fix: skip `CreateBucketConfiguration` for `us-east-1`.

### Phase 8b: Transfer S3 → OBS

**Do NOT use `s3_to_obs.py`** — it's too slow (16 MiB chunks at ~1 MB/s = ~2 hours for 7 GB).

**Do NOT use boto3** — `XAmzContentSHA256Mismatch` incompatibility with OBS.

**Use obsutil** (Huawei Cloud's dedicated OBS CLI):

```bash
# Install obsutil
wget https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz
tar xzf obsutil_linux_amd64.tar.gz

# Configure
./obsutil config -i=<HW-AK> -k=<HW-SK> -e=obs.<target-region>.myhuaweicloud.com

# Download from S3 (use screen for long transfers)
screen -dmS s3dl aws s3 cp s3://<bucket>/export/<file>.vmdk /home/user/disk.vmdk --region us-east-1

# Upload to OBS (multipart, resumable)
./obsutil cp /home/user/disk.vmdk obs://<obs-bucket>/export/<file>.vmdk -f -r -u -j 5
```

**Known issue**: obsutil may timeout on the final part (`RequestTimeout` 408). Retry with `-r` (resume from checkpoint).

### Phase 8c: IMS Import

```bash
python scripts/hw_image_path.py import --region <target-region> \
  --obs-bucket <bucket> --object export/<file>.vmdk \
  --image-name <name> --os-version "CentOS 7.9 64bit" \
  --min-disk 40 --firmware bios
python scripts/hw_image_path.py status --region <target-region> --image-name <name>
```

For Amazon Linux 2, use `--os-version "CentOS 7.9 64bit"` (closest match) and `--firmware bios`.

### Phase 8d: Create ECS

```bash
python scripts/hw_image_path.py ecs --region <target-region> \
  --image-name <name> --vpc-id <vpc> --subnet-id <subnet> --secgroup-id <sg> \
  --flavor s6.large.2 --ecs-name <name> --disk-gb 40 --disk-type GPSSD \
  --pub-key ~/.ssh/id_rsa.pub
```

**Bug**: The script's cloud-init `user_data` hardcodes `/home/ubuntu/.ssh/authorized_keys`. For Amazon Linux 2, change to `/home/ec2-user/.ssh/authorized_keys`.

### Phase 8e: Verify

```bash
ssh -i <key> ec2-user@<ecs-ip> "hostname; uname -r; df -h"
```

**CRITICAL ISSUE**: The ECS will likely be **unreachable** because the imported image has AWS network drivers (`ena`/`ixgbevf`) that don't work on Huawei Cloud (`virtio`). Symptoms:
- ECS shows `ACTIVE` with no fault
- No ping response
- No SSH response
- No ports open
- `ResetServerPassword` fails with `Ecs.0613` (no plugin)

**Workarounds** (none fully tested):
1. Use VNC console to manually load `virtio_net` driver and configure DHCP
2. Pre-install `virtio_net` on the source EC2 before creating the AMI
3. Use a custom startup script that loads the driver on first boot

**This is the critical gap in the image path.** The SMS path does not have this issue because SMS handles driver injection during migration.

## Troubleshooting

### SMS path issues

| Error | Cause | Fix |
|-------|-------|-----|
| `SMS.6617` | Block migration not supported for this kernel | Use `MIGRATE_FILE` instead of `MIGRATE_BLOCK` |
| `SMS.0519` | Used space exceeds destination partition | Increase `min_disk` or use `xfs` filesystem |
| `SMS.0601` | Flavor sold out | Use `s6.large.2` instead of `c2.large` |
| `SMS.0601` | Volume type not available | Use `GPSSD` instead of `GP3` in `sa-brazil-1` |
| `SMS.6562` | No bandwidth configured | Add `bandwidth_size = 5` to template |
| `SMS.6504` | OS not supported | Check if Amazon Linux 2 (false positive) or use image path |
| `EOFError` on agent install | Interactive `setup.sh` | Use `pexpect` to automate input |

### Image path issues

| Error | Cause | Fix |
|-------|-------|-----|
| `InvalidLocationConstraint` | S3 bucket creation in `us-east-1` | Skip `LocationConstraint` for `us-east-1` |
| `XAmzContentSHA256Mismatch` | boto3 ↔ OBS incompatibility | Use `obsutil` instead of boto3 |
| `RequestTimeout` (408) | obsutil final part timeout | Retry with `-r` (resume) |
| `Ecs.0613` (no plugin) | Password reset on imported image | Use VNC console or SSH key |
| ECS unreachable | Network driver mismatch | See Phase 8e workarounds |
| `IMG.0158` | Quick import with VMDK | Use `is_quick_import=False` |

### Terraform issues

| Error | Cause | Fix |
|-------|-------|-----|
| Provider region error | `sa-brazil-1` not in SMS CLI regions | Use `region = "ap-southeast-3"` on provider, override on resources |
| `size` unit mismatch | `target_server_disks` size is in MB | Specify in MB (e.g. `8192` for 8 GB) |

## References

- [Preflight checks](references/preflight-checks.md)
- [Post-migration access](references/post-migration-access.md)
- [File-level migration semantics](references/file-level-migration-semantics.md)
- [Image migration path](references/image-migration-path.md)
- [Troubleshooting](references/troubleshooting.md)
- [Firmware compatibility](references/firmware-compatibility.md)

## Verified configurations

| Source | Target | Path | Status | Notes |
|--------|--------|------|--------|-------|
| AWS EC2 Amazon Linux 2 (us-east-1) | HuaweiCloud ECS (sa-brazil-1) | SMS (MIGRATE_FILE) | ✅ Verified | s6.large.2, GPSSD, bandwidth_size=5 |
| AWS EC2 Amazon Linux 2 (us-east-1) | HuaweiCloud ECS (sa-brazil-1) | Image (Phase 8) | ❌ ECS unreachable | Network driver mismatch (ena vs virtio) |
