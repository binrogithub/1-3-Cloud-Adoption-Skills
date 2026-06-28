# Migration Skill Summary

## Scope

- Skill path: `skills/mgc-cross-region-migration`
- Objective: migrate workloads to Huawei Cloud with Terraform + repository migration scripts.
- Current Terraform entrypoint: `scripts/mgc_sms_existing_target_batch.py` (batch existing-target SMS flow).
- Secondary path: `scripts/mgc_migrate.py` (single-source SMS/rsync flow).
- Proven path 1: SMS migration when source precheck is clean.
- Proven path 2: automatic rsync fallback over VPN bridge when SMS source precheck returns `SMS.6504`.
- Always separate migration-task success from operational acceptance: validate target ECS status, EIP, SG peer rules, SSH/TCP-22, and console output.

## Canonical Process

1. Validate source registration/permissions/target image/quota.
2. Populate `terraform.tfvars` with migration, network, and optional VPN/rsync parameters.
3. Run `terraform init` then `terraform apply -auto-approve`.
4. If apply reports `No changes`, force rerun with:
   - `terraform apply -replace=terraform_data.sms_existing_target_batch -auto-approve`
5. Confirm run output from:
   - `out/migration_result.json`
   - `out/precheck_source_checks.json`
   - `out/precheck_task_cleanup.json`
   - `out/task_poll_latest.json`
   - `out/rsync_execution.json` when fallback is used
6. Validate postcheck:
   - VPC name is `vpc-migration`
   - target ECS is `ACTIVE`
   - EIP exists with expected bandwidth
   - security-group connectivity rules are present for expected peers
   - SSH/TCP-22 is reachable, or console output explains why it is not

## Proven Automation Behaviors

- Auto creates/reuses target VPC/subnet and target ECS (single-source flow).
- Supports batch mapping from source ECS IDs to existing destination ECS by fixed IP (existing-target batch flow).
- Auto binds a dedicated EIP, normally `100 Mbps`.
- Auto adds source/target SG reachability rules for source and configured extra peers.
- Auto switches from SMS to rsync when source precheck returns `SMS.6504`.
- Retries CreateTask without strict disks mapping on `SMS.1404` in single-source flow.
- Supports VPN bridge routing through OpenVPN + VPC peering for rsync fallback.
- Treats rsync return code `23/24` as non-fatal partial/vanished-file warnings.
- Polls task `state`; do not require non-null `progress` or `end_date` to recognize terminal success.

## Latest Local Batch Resume Run (2026-06-12)

- Region/project: `ap-southeast-3`
- Batch size: 4 source servers
- Failure round evidence (`out/task_poll_retry_latest.json`, UTC `2026-06-11T16:26:59Z`):
  - all 4 tasks ended `MIGRATE_FAIL`
  - shared stage `ATTACH_AGENT_IMAGE-90`
  - shared code `SMS.1404`
- Checkpoint evidence (`out/resume_checkpoint_latest.json`, local `2026-06-12 01:18:19 +0800`):
  - all prior targets were `DELETED`
  - original boot volumes returned `HTTP 404 itemNotFound`
- Rebuild diagnosis (`out/rebuild_diagnosis_latest.json`):
  - blocker `SMS.0515`
  - action hint: restart source SMS-Agent and refresh disk metadata
- Recreate/restart summary (`out/resume_noagent_restart_summary_latest.json`, local `2026-06-12 04:13:29 +0800`):
  - `ok_count = 4`
  - `failed_count = 0`
  - new task IDs:
    - `620e1bb6-d455-4c9e-88f8-10a2f5fa940b`
    - `2316f170-60af-4431-b4d3-6a4d34942ca6`
    - `9b87dd1c-41fb-4630-9a7d-a4922112ed77`
    - `a0ae68ba-2057-402f-b608-87b4d22263a5`
- Monitor snapshot (`out/task_poll_latest.json`, local `2026-06-12 04:24:26 +0800`):
  - all 4 tasks `RUNNING`
  - subtasks in `MIGRATE_LINUX_FILE-1/2`
  - `all_terminal = false` (must continue polling)

## Latest Local SMS Run (2026-05-19)

- Source SMS ID: `66d564f2-5991-4f42-97cd-66d1da6feb39`
- Region: `la-north-2` to `la-north-2`
- Source precheck: no issues, generated at `2026-05-19 03:53:24 +08:00`
- Pre-migration cleanup: no historical source-bound tasks found
- Migration method: `sms`
- Task:
  - `task_id = 90d9ce09-76cf-47f4-bf50-3996bd680266`
  - `task_state_latest = MIGRATE_SUCCESS`
  - latest poll generated at `2026-05-19 04:08:03 +08:00`
- Target:
  - `target_server_id = 96712f18-4298-4f38-a187-caaa1e67a143`
  - fixed IP `10.250.1.99`
  - EIP `101.44.185.135`
  - ECS status `ACTIVE`
  - EIP bandwidth `100 Mbps`
- Remaining postcheck issue:
  - `source_to_target_eip_22 = closed_or_timeout`
  - `direct_to_target_eip_22 = closed_or_timeout`
  - console output showed invalid cloud-init YAML near `PasswordAuthentication\s`, no authorized root SSH keys, and no clear `Started OpenSSH server daemon` line.
- Lesson: after SMS `MIGRATE_SUCCESS`, SSH/login readiness must be validated separately. Inspect console output before repeatedly changing SG/VPC settings.

## Latest Local Rsync/VPN Run (2026-05-01)

- Source SMS/VM ID: `3574494d-5e3d-40c1-9170-13075d7ac3dc`
- Source host used for rsync: `192.168.229.128`
- Target region: `la-north-2`
- Target ECS ID: `fdef023a-4a00-4d4d-b0fe-771498061653`
- Target fixed IP: `10.250.1.107`
- Target EIP: `46.250.163.126`
- Target VPC: `vpc-migration` (`52e6bbac-6ff9-4c90-ba95-4ff6f9660b62`)
- SMS precheck reason: `OS_VERSION:SMS.6504`
- Migration method: `rsync`
- rsync state: `FULL_SYNCED`
- full_sync started: `2026-05-01 03:35:17 +08:00`
- full_sync finished: `2026-05-01 04:48:28 +08:00`
- full_sync duration: `4391s`
- Post-sync SSH issue:
  - target boot entered emergency mode because rsync copied stale `/etc/fstab` UUIDs.
  - recovery path was console repair of `/etc/fstab`, then reboot and SSH retest.

## Latest Local External-Source SMS Run (2026-06-28)

- Source input: `instance-20260627-200301` (external GCP host).
- Target: `la-north-2` (`project_id=3b1dbd8270424257930b2e95bc150916`).
- Source recovery note:
  - prior source ID `56966be1-0724-4397-8115-148ce5c1a0d6` became invalid (`SMS.7602 SourceServer does not exist`) while source agent still held stale task bindings.
  - fixed by stopping old agent, clearing source-side stale files (`taskInfo`, `rollback.cfg`, `disk_mapping.record`), and re-running `startup.sh` registration.
  - final source registration in this run:
    - `source_sms_server_id = 815e8300-29ab-4099-986f-8e32d445aebe`
    - `connected = true`
- Migration task terminal state:
  - `task_id = 7bcc6370-b6ce-4d1e-9495-fb36e35dfcd5`
  - `task_type = MIGRATE_FILE`
  - `task_state = MIGRATE_SUCCESS` (`out/task_poll_latest.json`, `generated_at_local = 2026-06-28 09:35:59 +08:00`)
  - target ECS:
    - `target_server_id = 679f64ef-0c4a-4f11-8a7b-059d841c9f4e`
    - `target_fixed_ip = 10.250.1.242`
    - `target_eip = 110.238.84.80`
    - `target_image_id = b1eecdf6-a943-43f3-9d47-a538231d1442`
- Post-migration blocker and root cause evidence:
  - `out/postcheck_network.json` (`2026-06-28 09:36:32 +08:00`) reported `direct_to_target_eip_22 = closed_or_error` (`connect_ex=11`).
  - console output in `out/target_boot_repair_latest.json` showed `Cannot open root device "/dev/vdb1"` and `Kernel panic`, while actual attached boot device was `/dev/vda`.
- Recovery sequence (confirmed):
  - `out/target_boot_repair_latest.json`
  - `out/target_root_param_fix_latest.json`
  - `out/target_grubcfg_fix_latest.json`
  - `out/target_rootdev_fix_latest.json`
  - `out/target_sshpass_fix_latest.json`
- Final acceptance:
  - target remained healthy and attached with `/dev/vda` (`out/target_boot_diagnosis_latest.json`, `out/target_access_recovery_latest.json`).
  - SSH login recheck passed:
    - timestamp: `2026-06-28 10:58:31 +08:00`
    - command result: `LOGIN_OK` on `root@110.238.84.80`.

## Operational Rules Distilled

- Clean old source-bound SMS tasks before creating a new migration task.
- Clean old auto-generated migration projects when `SMS.8115` reports the 50-project quota.
- Use `-replace` with the actual `terraform_data` resource for deliberate reruns with unchanged inputs.
- In this repo's current batch flow, use `-replace=terraform_data.sms_existing_target_batch`.
- Treat `progress=null` and `end_date=null` as acceptable if task `state` is terminal success.
- Treat `SMS.1404` as a target-disk baseline issue first, not only as transient API failure.
- When diagnosis reports `SMS.0515`, restart source SMS-Agent and refresh source metadata before recreating tasks.
- When a paused run is resumed, verify checkpoint baseline (`target exists`, `orig disk exists`) before reusing historical task IDs.
- Keep `/etc/fstab` excluded from rsync fallback unless a disk-mount remap is explicitly prepared.
- Validate generated cloud-init YAML before target creation; bad user-data can leave SSH unreachable even after SMS success.
- If SMS is `MIGRATE_SUCCESS` but SSH still fails and console shows `root=/dev/vdb1`/kernel panic, repair grub/root device mapping (`/dev/vda` or correct root UUID) via helper attach workflow before changing SG/VPC rules.

## Evidence Files

- `out/migration_result.json`
- `out/precheck_source_checks.json`
- `out/precheck_task_cleanup.json`
- `out/task_poll_latest.json`
- `out/task_poll_retry_latest.json` (when failed round exists)
- `out/resume_checkpoint_latest.json` (when resumed after interruption)
- `out/resume_noagent_restart_summary_latest.json` (when recreated targets/tasks)
- `out/monitor_checkpoint_latest.json`
- `out/rebuild_diagnosis_latest.json`
- `out/postcheck_network.json`
- `out/rsync_execution.json` when fallback is used
- `out/target_console_output*.txt` when SSH/TCP-22 postcheck fails
- `out/target_boot_diagnosis_latest.json` when task is successful but boot behavior is suspect
- `out/target_access_recovery_latest.json` after password reset/reboot recovery
- `out/target_boot_repair_latest.json`
- `out/target_root_param_fix_latest.json`
- `out/target_grubcfg_fix_latest.json`
- `out/target_rootdev_fix_latest.json`
- `out/target_sshpass_fix_latest.json`
