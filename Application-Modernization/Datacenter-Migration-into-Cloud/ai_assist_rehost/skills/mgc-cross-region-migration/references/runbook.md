# Migration Runbook

## Quick Checklist

1. Confirm source server is visible in SMS source list and status is connected.
2. Confirm destination image ID exists in target region.
3. Confirm AK/SK permissions for IAM, ECS, VPC, SMS.
4. Confirm target-region VPC quota has free slot if target VPC may be auto-created.
5. Check and clean obsolete source-bound SMS tasks before starting a new migration.
6. Confirm rsync SSH parameters are present in `terraform.tfvars` for fallback (`rsync_source_host/port/user/password`).
7. When source can only reach Codex VPN, prefer bridge mode (`enable_vpn_bridge=true`). Keep target VPN client bootstrap (`enable_target_vpn_client`) only as an optional fallback mode.
8. Confirm target ECS overwrite risk is accepted.
9. Run Terraform and verify `out/migration_result.json`.
10. For rsync runs, validate target boot/SSH health after sync; if SSH fails, inspect ECS console output before changing network policies.
11. For SMS runs, still validate SSH/TCP-22 and target console output; SMS `MIGRATE_SUCCESS` does not guarantee login readiness.
12. If execution was interrupted, resume from the latest checkpoint JSONs before starting a fresh run.

## Canonical Commands

```bash
cd /root/ai_assit_migration/ai_assist_vm_migration
terraform init
terraform apply -auto-approve
terraform apply -replace=terraform_data.sms_existing_target_batch -auto-approve
cat out/migration_result.json
```

Use `-replace=terraform_data.sms_existing_target_batch` only when a rerun is required but normal apply reports `No changes`.

## tfvars -> Runtime Env Mapping

`main.tf` passes these variables to `scripts/mgc_sms_existing_target_batch.py`:

- `source_access_key` -> `SOURCE_ACCESS_KEY`
- `source_secret_key` -> `SOURCE_SECRET_KEY`
- `source_region` -> `SOURCE_REGION`
- `source_project_id` -> `SOURCE_PROJECT_ID`
- `destination_access_key` -> `DESTINATION_ACCESS_KEY`
- `destination_secret_key` -> `DESTINATION_SECRET_KEY`
- `destination_region` -> `DESTINATION_REGION`
- `destination_region_name` -> `DESTINATION_REGION_NAME`
- `destination_project_id` -> `DESTINATION_PROJECT_ID`
- `source_server_ids` -> `SOURCE_SERVER_IDS` (comma-separated)
- `eip_bandwidth_mbps` -> `EIP_BANDWIDTH_MBPS`
- `security_group_rule_description` -> `SG_RULE_DESCRIPTION`
- `sms_endpoint` -> `SMS_ENDPOINT`
- fixed output path -> `RESULT_PATH=out/migration_result.json`

For single-source migration or rsync fallback, `scripts/mgc_migrate.py` can still be invoked directly with its own env mapping.

## What Success Looks Like

`out/migration_result.json` includes non-empty values for:

- top-level `mode`
- top-level `migration_project_id` (or explicit project-create error)
- per-item `source_sms_server_id`
- per-item `target_vm_id`
- per-item `task_id`
- per-item `task_state`

## Error Handling Matrix

- `SMS.1404`
  - Meaning: task creation hits disk-attachment state mismatch (`available` vs `IN-USE`) during `ATTACH_AGENT_IMAGE`.
  - Action: retry CreateTask without `target_server.disks` mapping and ensure target boot-disk baseline is consistent before recreating task.
  - Evidence pattern: `subtask_info=ATTACH_AGENT_IMAGE-90` + `error_param` containing disk UUID and `available/IN-USE`.

- `SMS.0515`
  - Meaning: source disk metadata changed since last check (`Source disk info changed`).
  - Action: restart source SMS-Agent, refresh source metadata, then recreate/start tasks from the latest checkpoint summary.
  - Prevention: when paused for hours and resumed later, run source precheck and baseline checks before reusing old task context.

- `SMS.6504`
  - Meaning: source OS precheck incompatible with SMS.
  - Action: script switches to rsync fallback (`full_sync -> incremental_sync -> cutover_sync`).

- `SMS.6603`
  - Meaning: source server is not connected to SMS.
  - Action: install/start SMS-Agent on source server, then rerun.

- `SMS.6602`
  - Meaning: task creation cannot use current public IP mode.
  - Action: let script retry with `use_public_ip=false`.

- `SMS.6617`
  - Meaning: source kernel does not support block migration.
  - Action: let script fallback to `MIGRATE_FILE`.

- `SMS.7605`
  - Meaning: duplicate/failed task residue affects task creation.
  - Action: let script cleanup failed task and retry; if still `SMS.7605`, delete historical tasks bound to the same source (including old successful tasks), then retry with a fresh target ECS.

- `SMS.8115`
  - Meaning: migration-project quota reached (max 50).
  - Action: delete old migration projects (prefer auto-generated `mgc*` projects), then rerun `terraform apply -auto-approve`.

- `VPC.0114`
  - Meaning: target-region VPC/router quota exceeded when creating target VPC.
  - Action: release one unused VPC or increase quota, then rerun `terraform apply -auto-approve`.

- `SMS.7703`
  - Meaning: queried `task_id` does not exist (often from stale historical output file).
  - Action: do not use old `task_id`; get latest task from current run output or list tasks by source server and pick the active one.

- `RUNNING` with progress greater than 100
  - Meaning: SMS migrate speed/progress fields are not strict completion indicators.
  - Action: keep monitoring by task `state` and subtask stage until terminal status.
  - Prevention: do not declare success before `all_terminal=true` in monitor summary.

- `SSH reset/closed/timed out after rsync`
  - Meaning: target ECS may not have reached normal boot state even when cloud status is `ACTIVE`.
  - Action: fetch ECS console output and check for emergency mode/systemd dependency failures (commonly stale `/etc/fstab` UUID entries), repair `/etc/fstab` via VNC/serial shell, reboot, then re-test SSH.
  - Prevention: keep `/etc/fstab` in rsync exclude list unless explicit disk-mount migration remap is prepared.

- `SSH closed_or_timeout after SMS success`
  - Meaning: SMS task can be terminal-success while target SSH is not reachable.
  - Action: check `out/postcheck_network.json` for EIP/SG/peer evidence, then inspect `out/target_console_output*.txt`.
  - If console output contains cloud-init `Failed loading yaml blob` or `unknown escape character 's'` near `PasswordAuthentication\s`, fix target user-data generation (`build_linux_ssh_user_data_b64`) or repair sshd/firewall/root auth from console, then recreate/reboot and retest.
  - Prevention: validate generated cloud-init YAML before target ECS creation, and archive console output whenever TCP/22 postcheck fails.

## If Terraform Apply Fails

1. Read stderr from local-exec (`scripts/run_migration.sh`).
2. Confirm required env vars are not empty.
3. Check VPC quota in target region (common blocker for `vpc-migration` creation).
4. Re-check region names and image ID.
5. Check SMS migration-project quota; if `SMS.8115`, clean old migration projects first.
6. Re-run `terraform apply -auto-approve` after fixing input.
7. Keep previous failure output for comparison; do not delete diagnostics blindly.

## If Task Starts But Progress Is Unclear

1. Use `task_id` from `out/migration_result.json`.
2. Query SMS task detail through API or existing script helper path.
3. Check source connectivity and target ECS status in parallel.
4. Report both current task state and latest blocking signal.
5. If `progress` is null or greater than 100 while `state` is `RUNNING`, continue polling until terminal state.

## If Run Was Paused/Interrupted

1. Read `out/resume_checkpoint_latest.json` to confirm whether original target VM/disk context is still valid.
2. If checkpoint shows deleted targets or missing original volumes (`HTTP 404 itemNotFound`), do not reuse old target IDs.
3. Read `out/rebuild_diagnosis_latest.json`; if blocker is `SMS.0515`, restart source SMS-Agent first.
4. Recreate/restart tasks and write `out/resume_noagent_restart_summary_latest.json`.
5. Continue monitor loop and keep writing `out/task_poll_latest.json` and `out/monitor_checkpoint_latest.json`.

## Output Packaging Checklist

After each migration run, archive these files together:

1. `out/migration_result.json`
2. `out/precheck_source_checks.json`
3. `out/rsync_execution.json` (if fallback happened)
4. `out/precheck_task_cleanup.json`
5. `out/postcheck_network.json`
6. `out/task_poll_latest.json`
7. `out/target_console_output*.txt` when SSH/TCP-22 postcheck fails
8. `skills/mgc-cross-region-migration/references/runbook.md`
9. `skills/mgc-cross-region-migration/references/lessons-learned.md`

Store bundle under:

- `skills/mgc-cross-region-migration/bundles/<date>-<scenario>/`

## Field Case Snapshot (2026-04-17)

- Initial `terraform apply` failed with `VPC.0114` because VPC quota in `la-south-2` was full (`used=5`, `quota=5`).
- After deleting one unused VPC (`used=4`, `quota=5`), rerun succeeded and migration task started.
- A historical `task_id` from older `out/migration_result.json` returned `SMS.7703`; latest task reached `MIGRATE_SUCCESS`.

## Field Case Snapshot (2026-04-21)

- Repeated task creation failures returned `SMS.7605` because historical source-bound task residue still occupied migration binding.
- Migration project creation later returned `SMS.8115` because migration-project count hit the platform cap (`count=50`).
- Corrective actions:
  - deleted old source-bound task residue for this source server.
  - cleaned old `mgc*` migration projects to release project quota.
  - reran `terraform apply -auto-approve`.
- Latest run output task:
  - `task_id = f239ef24-7f6d-4ae4-ac5b-8d82cbf184df`
  - `task_started_at_cn = 2026-04-21 00:25:58 +08:00`
  - `task_finished_at_cn = 2026-04-21 00:44:19 +08:00`
  - `task_state_latest = MIGRATE_SUCCESS`

## Field Case Snapshot (2026-04-22)

- Source VM ID: `4fb3d857-aa08-4b79-8810-760cab680418`
- Before migration, one historical source-bound task was found and deleted:
  - `task_id = 073f5212-6175-4f65-9497-cdaeac0f4666`
  - `state = MIGRATE_SUCCESS`
- Normal `terraform apply -auto-approve` returned `No changes`; rerun with:
  - `terraform apply -replace=terraform_data.mgc_region_migration -auto-approve` (historical resource name in that run)
- New migration run result:
  - `migproject_id = 7a545883-187a-458d-aea0-6e665d295e2e`
  - `task_id = 5f044a0b-cf65-44b0-a816-9914c2b30c96`
  - `target_server_id = 7f110bb2-3332-4ef8-a19b-9013746b76a8`
  - `task_state_latest = MIGRATE_SUCCESS`
  - `task_finished_at_cn = 2026-04-22 07:28:21 +08:00`
- Postcheck evidence:
  - target VPC name = `vpc-migration`
  - target EIP exists (`119.8.149.199`)
  - source/target security-group connectivity check passed
  - task polling showed `progress=null` throughout RUNNING, then terminal success

## Field Case Snapshot (2026-05-01)

- Source VMware ID: `3574494d-5e3d-40c1-9170-13075d7ac3dc` in `la-north-2`.
- Precheck result: `OS_VERSION:SMS.6504` so migration used rsync over VPN bridge.
- Target ECS:
  - `target_server_id = fdef023a-4a00-4d4d-b0fe-771498061653`
  - `target_fixed_ip = 10.250.1.107`
  - `target_floating_ip = 46.250.163.126`
- Rsync full phase completed:
  - `started_at_cn = 2026-05-01 03:35:17 +08:00`
  - `finished_at_cn = 2026-05-01 04:48:28 +08:00`
  - `state = FULL_SYNCED`
- Post-sync SSH from source failed with reset/closed/timeout.
- ECS console output confirmed emergency mode due missing `/etc/fstab` UUID mounts; repair via console restored recovery path.

## Field Case Snapshot (2026-05-19)

- Source SMS server ID: `66d564f2-5991-4f42-97cd-66d1da6feb39`.
- Region: `la-north-2` to `la-north-2`.
- Source precheck generated at `2026-05-19 03:53:24 +08:00` had no issues.
- Pre-migration cleanup found no existing source-bound tasks (`matched_count=0`, `deleted_count=0`).
- SMS run result:
  - `migration_method = sms`
  - `task_id = 90d9ce09-76cf-47f4-bf50-3996bd680266`
  - `task_state_latest = MIGRATE_SUCCESS`
  - `target_server_id = 96712f18-4298-4f38-a187-caaa1e67a143`
  - latest poll artifact generated at `2026-05-19 04:08:03 +08:00`
- Network postcheck generated at `2026-05-19 04:19:12 +08:00` confirmed target ECS `ACTIVE`, EIP `101.44.185.135`, `100 Mbps` bandwidth, and target peer SG rules.
- SSH postcheck still failed:
  - `source_to_target_eip_22 = closed_or_timeout`
  - `direct_to_target_eip_22 = closed_or_timeout`
- Console output showed invalid cloud-init user-data (`unknown escape character 's'` near `PasswordAuthentication\s`), no authorized root SSH keys, and no clear `Started OpenSSH server daemon` line.
- Rule: after SMS success, treat SSH/login readiness as a separate acceptance gate; inspect console output before assuming SG/VPC is the only blocker.

## Field Case Snapshot (2026-06-12)

- Scenario: batch SMS existing-target migration for 4 source servers in `ap-southeast-3`, resumed after pause.
- First retry round (`out/task_poll_retry_latest.json`, UTC `2026-06-11T16:26:59Z`) reached all terminal states, but all 4 tasks failed:
  - state `MIGRATE_FAIL`
  - subtask `ATTACH_AGENT_IMAGE-90`
  - error code `SMS.1404`
- Resume checkpoint (`out/resume_checkpoint_latest.json`, local `2026-06-12 01:18:19 +0800`) showed old targets were `DELETED` and original boot volumes returned `HTTP 404`.
- Rebuild diagnosis reported blocker `SMS.0515` and advised source-side agent restart before recreating tasks.
- Recreate/restart summary (`out/resume_noagent_restart_summary_latest.json`, local `2026-06-12 04:13:29 +0800`) showed all 4 recreated tasks started successfully:
  - `620e1bb6-d455-4c9e-88f8-10a2f5fa940b`
  - `2316f170-60af-4431-b4d3-6a4d34942ca6`
  - `9b87dd1c-41fb-4630-9a7d-a4922112ed77`
  - `a0ae68ba-2057-402f-b608-87b4d22263a5`
- Monitor snapshot (`out/task_poll_latest.json`, local `2026-06-12 04:24:26 +0800`) confirmed all 4 tasks were `RUNNING` in `MIGRATE_LINUX_FILE-*` stage.

## Related Reference

- For reusable problem/experience summaries, load [lessons-learned.md](lessons-learned.md).
- For packaged migration assets and manifest, load [reuse-bundle.md](reuse-bundle.md).
