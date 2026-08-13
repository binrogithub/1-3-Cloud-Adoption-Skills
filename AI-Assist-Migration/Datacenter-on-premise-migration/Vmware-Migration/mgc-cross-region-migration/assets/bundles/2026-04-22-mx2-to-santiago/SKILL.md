---
name: mgc-cross-region-migration
description: Execute and troubleshoot Huawei Cloud cross-region server migration with MGC/SMS and Terraform in this repository. Use when users ask to migrate ECS across regions (especially la-north-2 to la-south-2), run the end-to-end workflow (`terraform init/apply` + `scripts/mgc_migrate.py`), validate prerequisites, map tfvars to runtime env vars, inspect migration output JSON, or diagnose SMS/MGC errors such as SMS.6602, SMS.6603, SMS.6617, SMS.7605, and SMS.8115. Also use for Chinese requests like “跨区域迁移”, “MGC/SMS 迁移流程”, or “迁移排障”.
---

# MGC Cross-Region Migration

## Overview

Run the migration flow in this repo from precheck to task startup and result validation. Keep execution deterministic by following the exact command sequence and error-handling rules already implemented in `scripts/mgc_migrate.py`.

## Workflow

1. Confirm prerequisites before running any write operation.
2. Prepare Terraform inputs in `terraform.tfvars`.
3. Before migration, precheck and cleanup old source-bound SMS tasks if they can occupy the same source VM.
4. Execute Terraform so it calls `scripts/run_migration.sh` and `scripts/mgc_migrate.py`.
5. Verify `out/migration_result.json` and poll task state to terminal status.
6. Run postcheck for `vpc-migration`, EIP binding, and source/target security-group connectivity.
7. Troubleshoot by matching error codes to the runbook.
8. Summarize recurring issues with the lessons reference when user asks for postmortem/experience capture.

## Step 1: Validate Preconditions

Verify all required conditions:

- Source server is already registered in SMS and is reachable/connected.
- AK/SK has IAM, SMS, ECS, and VPC permissions.
- `target_image_id` exists in target region (`target_region`, default `la-south-2`).
- Migration side effect is accepted: SMS will overwrite data on target ECS.
- If `target_vpc_name` may need to be created, confirm target-region VPC quota has free capacity before running `terraform apply`.

Run:

```bash
cd /root/mgc-cross-region-migration
```

Inspect key files before execution:

- `main.tf`
- `variables.tf`
- `terraform.tfvars`

## Step 2: Prepare Input Variables

Edit `terraform.tfvars` and provide:

- `access_key`
- `secret_key`
- `source_server_id`
- `target_image_id`
- region and network fields when defaults are not desired

Use these defaults unless user requests changes:

- `source_region = la-north-2`
- `target_region = la-south-2`
- `target_vpc_name = vpc-migration`
- `sms_endpoint = https://sms.ap-southeast-3.myhuaweicloud.com`

## Step 3: Execute Migration

Run in order:

```bash
terraform init
terraform apply -auto-approve
```

If apply returns `No changes` for `terraform_data.mgc_region_migration` (same run fingerprint), force one execution:

```bash
terraform apply -replace=terraform_data.mgc_region_migration -auto-approve
```

Expect Terraform local-exec to map tfvars into runtime env vars and call:

- `scripts/run_migration.sh`
- `python3 scripts/mgc_migrate.py`

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

Ensure the JSON includes at least:

- `migproject_id`
- `task_id`
- `source_sms_server_id`
- `target_server_id`
- `task_state`

If `task_state` is not terminal or the user asks for deeper diagnosis, use the troubleshooting guidance in [references/runbook.md](references/runbook.md).
Treat existing `out/migration_result.json` as historical unless it was just generated in the current run.

For a complete run package, also keep:

- `out/precheck_task_cleanup.json`
- `out/postcheck_network.json`
- `out/task_poll_latest.json`

## Troubleshooting Policy

Apply existing built-in fallbacks before manual changes:

- If task creation returns `SMS.6617`, allow fallback from `MIGRATE_BLOCK` to `MIGRATE_FILE`.
- If task creation returns `SMS.6602`, allow retry with `use_public_ip=false`.
- If task creation returns `SMS.7605`, allow cleanup of failed task and retry.
- If `SMS.7605` persists even after retry/new target ECS, check and delete historical tasks bound to the same source (including old `MIGRATE_SUCCESS` tasks), then retry.
- If `SMS.6603` appears, stop and require SMS-Agent installation/start on source host.
- If migration project creation returns `SMS.8115`, clean old migration projects (prefer auto-generated `mgc*` projects) to bring total count below 50, then rerun `terraform apply`.
- If VPC creation fails with `VPC.0114` (quota exceeded), stop and free quota first (delete unused VPC or increase quota), then rerun `terraform apply`.
- If task query returns `SMS.7703` (`Task doesn't exist`), do not trust stale `task_id`; query live task list by source and continue with the current task.
- If task is `RUNNING` but `progress` is null, keep polling by task `state` and verify target ECS status in parallel.

Do not invent alternative API sequences unless the user explicitly asks to modify migration logic.

## Migration Problem and Experience Summary

When the user asks for “迁移过程的问题总结”, “经验复盘”, “踩坑记录”, or “postmortem”, load [references/lessons-learned.md](references/lessons-learned.md) and report in this order:

1. Symptom and code (`VPC.0114`, `SMS.7703`, `SMS.6603`, etc.).
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
