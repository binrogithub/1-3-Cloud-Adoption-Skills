---
name: mgc-cross-region-migration
description: Execute and troubleshoot Huawei Cloud server migration in this repository. Support both current batch existing-target SMS workflow (`terraform apply` + `scripts/mgc_sms_existing_target_batch.py`) and single-source SMS/rsync workflow (`scripts/mgc_migrate.py`). Use when users ask to migrate ECS/on-prem VMware, run migration in `ap-southeast-3`/`la-*`, resume after pause from `out/resume_checkpoint_latest.json`, monitor tasks in `out/task_poll_latest.json`, or diagnose SMS/MGC errors such as SMS.1404, SMS.0515, SMS.6504, SMS.6602, SMS.6603, SMS.6617, SMS.7605, SMS.7703, and SMS.8115. Also use for Chinese requests like “跨区域迁移”, “MGC/SMS 迁移流程”, “批量迁移恢复”, or “迁移排障”.
---

# MGC Cross-Region Migration

## Overview

Run the migration flow in this repo from precheck to task startup/result validation. Keep execution deterministic by following the exact command sequence and error-handling rules already implemented in scripts.
Current Terraform entrypoint is batch existing-target SMS migration (`scripts/mgc_sms_existing_target_batch.py`). For single-source migrations, default policy is still `SMS` first; when precheck/runtime indicates incompatible source (for example `SMS.6504`), switch to rsync phases (`full_sync -> incremental_sync -> cutover_sync`).

## Workflow

1. Confirm prerequisites before running any write operation.
2. Prepare Terraform inputs in `terraform.tfvars`.
3. Before migration, precheck and cleanup old source-bound SMS tasks if they can occupy the same source VM.
4. Execute Terraform so it calls `scripts/run_migration.sh` and `scripts/mgc_sms_existing_target_batch.py`.
5. Verify `out/migration_result.json`; for batch mode verify every `results[]` item has `source_sms_server_id`, `task_id`, and `task_state`.
6. Run postcheck for `vpc-migration`, EIP binding, source/target security-group connectivity, and SSH/TCP-22 reachability.
7. If SSH/TCP-22 fails after SMS or rsync reports success, inspect ECS console output before making more network changes.
8. If run was paused/restarted, continue from `out/resume_checkpoint_latest.json`, `out/resume_noagent_restart_summary_latest.json`, and `out/task_poll_latest.json`.
9. Troubleshoot by matching error codes and postcheck symptoms to the runbook.
10. Summarize recurring issues with the lessons reference when user asks for postmortem/experience capture.

## Step 1: Validate Preconditions

Verify all required conditions:

- Source server is already registered in SMS and is reachable/connected.
- AK/SK has IAM, SMS, ECS, and VPC permissions.
- Batch existing-target mode can map source ECS to destination ECS by fixed IP in target project.
- If target ECS must be recreated in resume flow, `target_image_id` must exist in target region.
- Migration side effect is accepted: SMS will overwrite data on target ECS.
- If `target_vpc_name` may need to be created, confirm target-region VPC quota has free capacity before running `terraform apply`.

Run:

```bash
cd /root/ai_assit_migration/ai_assist_vm_migration
```

Inspect key files before execution:

- `main.tf`
- `variables.tf`
- `terraform.tfvars`

## Step 2: Prepare Input Variables

Edit `terraform.tfvars` and provide:

- `source_access_key`
- `source_secret_key`
- `destination_access_key`
- `destination_secret_key`
- `source_server_ids` (batch list)
- source/destination region and project fields when defaults are not desired

Use these defaults unless user requests changes:

- `source_region = ap-southeast-3`
- `destination_region = ap-southeast-3`
- `eip_bandwidth_mbps = 100`
- `sms_endpoint = https://sms.ap-southeast-3.myhuaweicloud.com`

## Step 3: Execute Migration

Run in order:

```bash
terraform init
terraform apply -auto-approve
```

If apply returns `No changes` for `terraform_data.sms_existing_target_batch` (same run fingerprint), force one execution:

```bash
terraform apply -replace=terraform_data.sms_existing_target_batch -auto-approve
```

Expect Terraform local-exec to map tfvars into runtime env vars and call:

- `scripts/run_migration.sh`
- `python3 scripts/mgc_sms_existing_target_batch.py`

Core API chain:

1. `POST /v3/privacy-agreements`
2. `POST /v3/migprojects`
3. `GET /v3/sources`
4. `POST /v1.1/{project_id}/cloudservers`
5. `POST /v3/tasks`
6. `POST /v3/tasks/{task_id}/action` (`start`)

## Step 4: Validate Outputs

Check result artifact:

```bash
cat out/migration_result.json
```

For batch mode, ensure the JSON includes at least:

- top-level `migration_project_id` (or creation error details)
- `results[]` with per-source `source_sms_server_id`
- per-source `task_id`
- per-source `target_vm_id`
- per-source `task_state`

If any per-source `task_state` is not terminal or the user asks for deeper diagnosis, use the troubleshooting guidance in [references/runbook.md](references/runbook.md).
Treat existing `out/migration_result.json` as historical unless it was just generated in the current run.

For a complete run package, also keep:

- `out/precheck_task_cleanup.json`
- `out/task_poll_latest.json`
- `out/precheck_source_checks.json`
- `out/task_poll_retry_latest.json` (when prior round failed and retried)
- `out/resume_checkpoint_latest.json` (when paused/resumed)
- `out/resume_noagent_restart_summary_latest.json` (when recreated target/tasks from checkpoint)
- `out/monitor_checkpoint_latest.json` (when monitoring continues after restart)
- `out/postcheck_network.json`
- `out/rsync_execution.json` (when fallback path is used)
- `out/target_console_output*.txt` (when SSH/TCP-22 postcheck fails)

## Troubleshooting Policy

Apply existing built-in fallbacks before manual changes:

- If task creation returns `SMS.6617`, allow fallback from `MIGRATE_BLOCK` to `MIGRATE_FILE`.
- If source check returns `SMS.6504`, skip SMS task creation and switch to rsync staged migration.
- If task creation returns `SMS.1404` with `error_param` containing `available` vs `IN-USE`, retry without explicit `target_server.disks` mapping and/or repair target boot-disk attachment baseline before recreating task.
- If task creation returns `SMS.6602`, allow retry with `use_public_ip=false`.
- If task creation returns `SMS.7605`, allow cleanup of failed task and retry.
- If `SMS.7605` persists even after retry/new target ECS, check and delete historical tasks bound to the same source (including old `MIGRATE_SUCCESS` tasks), then retry.
- If `SMS.6603` appears, stop and require SMS-Agent installation/start on source host.
- If diagnosis returns `SMS.0515` (`Source disk info changed`), restart source SMS-Agent, refresh source disk info, then recreate/start target task from the latest checkpoint summary.
- If migration project creation returns `SMS.8115`, clean old migration projects (prefer auto-generated `mgc*` projects) to bring total count below 50, then rerun `terraform apply`.
- If VPC creation fails with `VPC.0114` (quota exceeded), stop and free quota first (delete unused VPC or increase quota), then rerun `terraform apply`.
- If task query returns `SMS.7703` (`Task doesn't exist`), do not trust stale `task_id`; query live task list by source and continue with the current task.
- If task is `RUNNING` but `progress` is null, keep polling by task `state` and verify target ECS status in parallel.
- If task is `RUNNING` with progress over 100 in `MIGRATE_LINUX_FILE-*`, keep polling until terminal state; do not mark success before `all_terminal=true`.
- If task is `MIGRATE_SUCCESS` and target ECS is `ACTIVE` but SSH/TCP-22 is `closed_or_timeout`, inspect `out/postcheck_network.json` and ECS console output before adding more SG rules.
- If target ECS has boot panic (`VFS: Cannot open root device "/dev/vdb1"`/`unknown-block(0,0)`) or SSH auth regression after migration, use one deterministic repair path:
  - `PYTHONPATH=. python3 scripts/repair_boot_via_helper.py --target-server-id <target_id> --target-reset-password '<StrongPassword>'`
  - This script now includes fixed root-device rewrite (`root=/dev/vda1`), SSH password-login hardening (`PermitRootLogin yes`, `PasswordAuthentication yes`, `ssh_pwauth: true`), and offline root password write (`chpasswd`).
  - The script now also auto-cleans stale `boot-repair-*` helpers before/after run, and auto-deletes the current helper after success (use `--keep-helper` only when explicitly needed).
- If console output contains cloud-init `Failed loading yaml blob` or `unknown escape character 's'` near `PasswordAuthentication\s`, treat target user-data bootstrap as invalid; fix `build_linux_ssh_user_data_b64`/target creation user-data quoting, recreate or repair the target, then rerun postcheck.
- If console output shows only `Starting OpenSSH server daemon...` without a clear started service and `ci-info: no authorized ssh keys fingerprints found`, validate sshd/firewall/root auth from VNC/serial console or rebuild with valid cloud-init.

Do not invent alternative API sequences unless the user explicitly asks to modify migration logic.

## Migration Problem and Experience Summary

When the user asks for “迁移过程的问题总结”, “经验复盘”, “踩坑记录”, or “postmortem”, load [references/lessons-learned.md](references/lessons-learned.md) and report in this order:

1. Symptom and code (`VPC.0114`, `SMS.1404`, `SMS.0515`, `SMS.7703`, `SMS.6603`, `SSH closed_or_timeout`, etc.).
2. Root cause validated from logs/output.
3. Corrective action already proven in this repo.
4. Preventive rule to apply before next run.
5. Concrete timestamps from latest result JSON (for example `task_started_at_cn`, `task_finished_at_cn`) to avoid stale-history confusion.

## References

Load [references/runbook.md](references/runbook.md) when you need:

- command-level execution checklist
- tfvars-to-env mapping
- error-code-oriented diagnosis steps
- post-run verification checklist

Load [references/lessons-learned.md](references/lessons-learned.md) when you need:

- structured migration issue summary (`symptom -> root cause -> action -> prevention`)
- reusable troubleshooting experience from real runs
- concise postmortem output for users

Load [references/reuse-bundle.md](references/reuse-bundle.md) when you need:

- packaged migration assets and manifest
- reusable command sequence (precheck -> migrate -> verify -> poll)
- direct file pointers for future similar migrations

Load [references/migration-skill-summary.md](references/migration-skill-summary.md) when you need:

- a concise end-to-end summary of this migration skill
- a quick list of proven error-handling patterns
- the latest validated run facts (IDs, timestamps, and network results)
