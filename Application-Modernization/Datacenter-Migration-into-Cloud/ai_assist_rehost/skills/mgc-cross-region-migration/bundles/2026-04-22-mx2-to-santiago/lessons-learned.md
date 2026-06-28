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
- Root cause: `terraform_data.mgc_region_migration` trigger fingerprint did not change from previous successful run.
- Corrective action: run `terraform apply -replace=terraform_data.mgc_region_migration -auto-approve`.
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
