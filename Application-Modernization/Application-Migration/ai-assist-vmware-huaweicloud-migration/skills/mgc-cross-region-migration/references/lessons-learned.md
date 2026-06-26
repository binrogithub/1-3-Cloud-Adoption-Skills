# Migration Issues and Lessons Learned

Use this file to summarize migration incidents in a stable structure:

1. Symptom and error code
2. Root cause
3. Corrective action
4. Prevention rule for next run

## Problem Pattern Matrix

### `VPC.0114` (target VPC creation failed)

- Symptom: `terraform apply` fails while creating target VPC (`vpc-migration`) in `la-south-2`.
- Root cause: target-region VPC quota is full (`used == quota`).
- Corrective action: delete one unused VPC or increase VPC quota, then rerun `terraform apply -auto-approve`.
- Prevention: check VPC quota before every apply when VPC may be auto-created.

### `SMS.7703` (task does not exist)

- Symptom: querying a task by ID returns `Task doesn't exist`.
- Root cause: stale `task_id` from historical `out/migration_result.json`.
- Corrective action: use `task_id` from the latest run output, or query current task list by source server.
- Prevention: treat `out/migration_result.json` as historical unless it was generated in the current run.

### `RUNNING` with `progress = null`

- Symptom: task state is `RUNNING`, but progress field is empty.
- Root cause: SMS may omit numeric progress even when migration is active.
- Corrective action: continue polling task `state` and verify target ECS status in parallel.
- Prevention: do not use `progress` as the only health indicator.

### Terraform `No changes` on rerun

- Symptom: `terraform apply -auto-approve` returns `No changes` and does not trigger migration again.
- Root cause: `terraform_data` trigger fingerprint did not change from previous successful run (`sms_existing_target_batch` in current repo).
- Corrective action: run `terraform apply -replace=terraform_data.sms_existing_target_batch -auto-approve`.
- Prevention: for deliberate reruns with same tfvars, use `-replace` explicitly.

### `SMS.6603` (source not connected)

- Symptom: task creation/start fails with source connectivity error.
- Root cause: SMS-Agent is not installed, not running, or source not connected in SMS.
- Corrective action: install/start SMS-Agent on source host, verify source is connected, rerun.
- Prevention: perform source connectivity precheck before Terraform apply.

### `SMS.6617` (block migration unsupported)

- Symptom: task creation fails for block migration mode.
- Root cause: source kernel does not support block migration.
- Corrective action: fallback to `MIGRATE_FILE` (already implemented in script retry path).
- Prevention: keep block->file fallback enabled; do not hard-force block mode.

### `SMS.6504` (source OS incompatible with SMS)

- Symptom: SMS source precheck (`OS_VERSION`) returns `ERROR` with `SMS.6504`.
- Root cause: source OS/kernel combination is outside SMS supported range.
- Corrective action: switch to rsync staged migration (`full_sync -> incremental_sync -> cutover_sync`) while keeping target ECS/VPC/EIP provisioning unchanged.
- Prevention: read source check result from API before creating SMS task, and fallback automatically when `SMS.6504` appears.

### `SMS.6602` (public IP mode mismatch)

- Symptom: task creation fails when using public IP mode.
- Root cause: environment/task constraints conflict with current public IP option.
- Corrective action: retry with `use_public_ip=false` (already implemented).
- Prevention: keep adaptive retry logic and report selected mode in execution logs.

### `SMS.7605` (failed/duplicate task residue)

- Symptom: new task creation blocked by existing failed residue task.
- Root cause: historical task residue (including prior successful tasks bound to the same source/target context) still occupied migration binding.
- Corrective action: cleanup old source-bound tasks first, then retry task creation; if still blocked, switch to a fresh target ECS and retry.
- Prevention: precheck existing tasks by source server before task creation, and purge obsolete historical tasks.

### `SMS.8115` (migration project quota exceeded)

- Symptom: creating migration project fails with `The quantity of MigProject must be lower than or equal to 50`.
- Root cause: accumulated historical migration projects reached platform quota (`count=50`).
- Corrective action: delete old migration projects (prefer auto-generated `mgc*` items), then rerun `terraform apply -auto-approve`.
- Prevention: add migration-project quota check/cleanup before each large rerun batch.

### `SMS.1404` (target disk state mismatch)

- Symptom: batch SMS tasks fail at `ATTACH_AGENT_IMAGE-90` with `MIGRATE_FAIL` and `error_param` containing `available` vs `IN-USE`.
- Root cause: target boot-disk mapping state is inconsistent at task creation/start (expected available by SMS validation, but disk is attached/in-use at runtime).
- Corrective action:
  - retry task creation without strict `target_server.disks` mapping when supported by script fallback.
  - repair/rebuild target baseline so expected boot volume attachment state is consistent, then recreate/start task.
- Prevention:
  - when resuming old runs, verify target VM/disk baseline before reusing historical task context.
  - avoid using stale target IDs and stale disk mapping after long pauses/restarts.

### `SMS.0515` (source disk info changed)

- Symptom: rebuild diagnosis reports `current_blocker=source_side_sms_0515`.
- Root cause: source-side disk metadata changed after pause/restart window, and SMS source state no longer matches previous task context.
- Corrective action: restart source SMS-Agent, refresh source metadata/precheck, then recreate and restart migration tasks from the latest checkpoint.
- Prevention: for paused runs (hours), always run source-side health/precheck again before resume.

### SSH `connection reset/closed/timed out` after rsync cutover

- Symptom: source VM cannot SSH target private IP; errors include `kex_exchange_identification`, `Connection closed`, or timeout.
- Root cause: target ECS booted into emergency mode because migrated `/etc/fstab` contains stale source-disk UUID mounts.
- Corrective action:
  - read ECS console output (`os-getConsoleOutput`) and confirm missing UUID dependency failure.
  - enter VNC/serial emergency shell and repair `/etc/fstab` (remove/fix invalid UUID entries or mark `nofail`).
  - reboot target and re-validate source->target SSH.
- Prevention:
  - exclude `/etc/fstab` in rsync excludes by default.
  - add post-rsync boot-health check before declaring migration complete.

### SSH `closed_or_timeout` after SMS success

- Symptom: SMS task reaches `MIGRATE_SUCCESS` and target ECS is `ACTIVE`, but `out/postcheck_network.json` reports `source_to_target_eip_22` and/or `direct_to_target_eip_22` as `closed_or_timeout`.
- Root cause: do not assume this is only a VPC/SG problem. In the 2026-05-19 local run, ECS console output showed cloud-init rejected target user-data with `Failed loading yaml blob` and `unknown escape character 's'` near `PasswordAuthentication\s`, so SSH password/root-login/firewall bootstrap commands could be skipped.
- Corrective action:
  - archive `out/target_console_output*.txt` with the JSON artifacts.
  - fix target user-data generation (`build_linux_ssh_user_data_b64`) to emit valid cloud-init YAML, or repair sshd/firewall/root auth from VNC/serial console.
  - recreate/reboot the target and rerun SSH/TCP-22 postcheck.
- Prevention:
  - validate generated cloud-init YAML before target ECS creation.
  - after SMS success, treat login readiness as a separate postcheck from task state and ECS `ACTIVE`.
  - once EIP and expected peer SG rules are present, inspect console output before repeatedly adding network rules.

## Confirmed Field Case (2026-04-18)

- First `terraform apply` attempt failed with `VPC.0114` because VPC quota in `la-south-2` was full (`used=5`, `quota=5`).
- After deleting one unused VPC (`used=4`, `quota=5`), rerun succeeded and migration task started.
- Latest run output task:
  - `task_id = 78ab987b-b602-4c20-858b-da55fa530122`
  - `task_started_at_cn = 2026-04-18 02:30:10 +08:00`
  - `task_finished_at_cn = 2026-04-18 02:46:16 +08:00`
  - `task_state_latest = MIGRATE_SUCCESS`

## Confirmed Field Case (2026-04-21)

- This run repeatedly hit `SMS.7605` during task creation because source-bound historical task residue was not fully cleared.
- After task cleanup, migration project creation hit `SMS.8115` due to project quota saturation (`count=50`).
- After deleting obsolete task/project residue and rerunning, migration completed successfully.
- Latest run output task:
  - `task_id = f239ef24-7f6d-4ae4-ac5b-8d82cbf184df`
  - `task_started_at_cn = 2026-04-21 00:25:58 +08:00`
  - `task_finished_at_cn = 2026-04-21 00:44:19 +08:00`
  - `task_state_latest = MIGRATE_SUCCESS`

## Confirmed Field Case (2026-04-22)

- Input source VM ID: `4fb3d857-aa08-4b79-8810-760cab680418`.
- Precheck found one historical source-bound task in `MIGRATE_SUCCESS`; task was deleted before rerun:
  - `task_id = 073f5212-6175-4f65-9497-cdaeac0f4666`
- First apply returned `No changes`; rerun used `terraform_data` replace to force execution.
- Migration task reached success:
  - `task_id = 5f044a0b-cf65-44b0-a816-9914c2b30c96`
  - `task_finished_at_cn = 2026-04-22 07:28:21 +08:00`
  - `task_state_latest = MIGRATE_SUCCESS`
- Network postcheck confirmed:
  - target VPC = `vpc-migration`
  - target EIP allocated and bound
  - source/target security-group connectivity passed
- During execution, `progress` remained null while state stayed `RUNNING`; terminal state is the reliable completion indicator.

## Confirmed Field Case (2026-04-29)

- Source SMS precheck showed `OS_VERSION` error `SMS.6504`, but `RSYNC` check was `OK`.
- Migration kept the same target provisioning policy:
  - target VPC = `vpc-migration`
  - EIP bandwidth = `100 Mbps`
  - charging mode = `postPaid`
- Corrective action moved from SMS task creation to rsync staged migration:
  - full sync
  - incremental sync
  - cutover sync

## Confirmed Field Case (2026-05-01)

- Source VM ID: `3574494d-5e3d-40c1-9170-13075d7ac3dc` (on-prem VMware over VPN).
- SMS source precheck returned `OS_VERSION:SMS.6504`; method switched to rsync.
- Target ECS created in Mexico City2:
  - `target_server_id = fdef023a-4a00-4d4d-b0fe-771498061653`
  - `target_fixed_ip = 10.250.1.107`
  - `target_floating_ip = 46.250.163.126`
- rsync full phase completed:
  - `started_at_cn = 2026-05-01 03:35:17 +08:00`
  - `finished_at_cn = 2026-05-01 04:48:28 +08:00`
  - `state = FULL_SYNCED`
  - `rsync code 23` treated as non-fatal warning.
- After cutover validation, SSH to target failed (`reset/closed/timed out`).
- Console output showed emergency mode from missing `/etc/fstab` UUID devices:
  - `7c37581b-bc60-4c6c-8552-1517b33413c9`
  - `87a3ba70-e0f3-4f1c-842d-1691208ba04c`
- Preventive updates:
  - default excludes now include `/etc/fstab` in migration settings.
  - skill runbook now requires boot-health validation when SSH errors appear post-rsync.

## Confirmed Field Case (2026-05-19)

- Source SMS server ID: `66d564f2-5991-4f42-97cd-66d1da6feb39`.
- Source and target region: `la-north-2` (Mexico City2).
- Source precheck generated at `2026-05-19 03:53:24 +08:00` showed no SMS incompatibility issues.
- Pre-migration task cleanup found no source-bound task residue:
  - `matched_count = 0`
  - `deleted_count = 0`
- SMS migration ran with `migration_method = sms` and task type `MIGRATE_FILE`:
  - `task_id = 90d9ce09-76cf-47f4-bf50-3996bd680266`
  - `target_server_id = 96712f18-4298-4f38-a187-caaa1e67a143`
  - `task_started_at_cn = 2026-05-19 03:54:07 +08:00`
  - `task_state_latest = MIGRATE_SUCCESS`
  - latest poll artifact generated at `2026-05-19 04:08:03 +08:00`
- Network postcheck generated at `2026-05-19 04:19:12 +08:00` confirmed:
  - target VPC = `vpc-migration`
  - target fixed IP = `10.250.1.99`
  - target EIP = `101.44.185.135`
  - target ECS status = `ACTIVE`
  - EIP bandwidth = `100 Mbps`
  - target SG peer rules were present for source/extra peers
- Remaining issue:
  - `source_to_target_eip_22 = closed_or_timeout`
  - `direct_to_target_eip_22 = closed_or_timeout`
  - console output showed cloud-init YAML parsing failure near `PasswordAuthentication\s`, no authorized root SSH keys, and only `Starting OpenSSH server daemon...` without a clear started line.
- Lesson: SMS `MIGRATE_SUCCESS` validates migration task completion, not necessarily SSH login readiness. Always run and archive SSH/TCP-22 plus console-output postchecks before declaring the migrated server operational.

## Confirmed Field Case (2026-06-12)

- Scenario: batch SMS existing-target migration in `ap-southeast-3` for 4 source servers.
- Retry polling snapshot (`out/task_poll_retry_latest.json`, UTC `2026-06-11T16:26:59Z`) showed all 4 tasks ended in `MIGRATE_FAIL`:
  - common subtask: `ATTACH_AGENT_IMAGE-90`
  - common code: `SMS.1404`
- Resume checkpoint (`out/resume_checkpoint_latest.json`, local `2026-06-12 01:18:19 +0800`) showed all prior targets were deleted and original boot volumes returned `HTTP 404 itemNotFound`, so direct task resume was invalid.
- Rebuild diagnosis (`out/rebuild_diagnosis_latest.json`) reported blocker `SMS.0515` and recommended source-side SMS-Agent restart before rebuild.
- Recreate/restart summary (`out/resume_noagent_restart_summary_latest.json`, local `2026-06-12 04:13:29 +0800`) showed `ok_count=4`, `failed_count=0` with new tasks:
  - `620e1bb6-d455-4c9e-88f8-10a2f5fa940b`
  - `2316f170-60af-4431-b4d3-6a4d34942ca6`
  - `9b87dd1c-41fb-4630-9a7d-a4922112ed77`
  - `a0ae68ba-2057-402f-b608-87b4d22263a5`
- Monitor snapshot (`out/task_poll_latest.json`, local `2026-06-12 04:24:26 +0800`) showed all recreated tasks in `RUNNING` (`MIGRATE_LINUX_FILE-1/2`) rather than terminal fail.
- Lesson:
  - For batch resume, do not only retry task creation.
  - Validate checkpoint baseline first, restart source agent when `SMS.0515` appears, then rebuild targets/tasks and continue monitor loop.

## Reusable Postmortem Template

Use this compact template in user-facing summaries:

```text
[Issue]
Symptom:
Root cause:
Action taken:
Prevention:
Evidence (file/log/timestamp):
```
