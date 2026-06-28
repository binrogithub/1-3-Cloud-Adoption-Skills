# Migration Runbook

## Quick Checklist

1. Confirm source server is visible in SMS source list and status is connected.
2. Confirm destination image ID exists in target region.
3. Confirm AK/SK permissions for IAM, ECS, VPC, SMS.
4. Confirm target-region VPC quota has free slot if target VPC may be auto-created.
5. Check and clean obsolete source-bound SMS tasks before starting a new migration.
6. Confirm target ECS overwrite risk is accepted.
7. Run Terraform and verify `out/migration_result.json`.

## Canonical Commands

```bash
cd /root/mgc-cross-region-migration
terraform init
terraform apply -auto-approve
terraform apply -replace=terraform_data.mgc_region_migration -auto-approve
cat out/migration_result.json
```

Use `-replace=terraform_data.mgc_region_migration` only when a rerun is required but normal apply reports `No changes`.

## tfvars -> Runtime Env Mapping

`main.tf` passes these variables to `scripts/mgc_migrate.py`:

- `access_key` -> `HC_AK`
- `secret_key` -> `HC_SK`
- `source_server_id` -> `SOURCE_SERVER_ID`
- `source_region` -> `SOURCE_REGION`
- `target_region` -> `TARGET_REGION`
- `target_region_name` -> `TARGET_REGION_NAME`
- `target_vpc_name` -> `TARGET_VPC_NAME`
- `target_image_id` -> `TARGET_IMAGE_ID`
- `target_server_name` -> `TARGET_SERVER_NAME`
- `eip_bandwidth_mbps` -> `EIP_BANDWIDTH_MBPS`
- `root_volume_type` -> `ROOT_VOLUME_TYPE`
- `data_volume_type` -> `DATA_VOLUME_TYPE`
- `sms_endpoint` -> `SMS_ENDPOINT`
- fixed output path -> `RESULT_PATH=out/migration_result.json`

## What Success Looks Like

`out/migration_result.json` includes non-empty values for:

- `source_project_id`
- `target_project_id`
- `source_sms_server_id`
- `target_server_id`
- `migproject_id`
- `task_id`
- `task_state`

## Error Handling Matrix

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
5. If `progress` is null but `state` is `RUNNING`, continue polling until terminal state.

## Output Packaging Checklist

After each migration run, archive these files together:

1. `out/migration_result.json`
2. `out/precheck_task_cleanup.json`
3. `out/postcheck_network.json`
4. `out/task_poll_latest.json`
5. `skills/mgc-cross-region-migration/references/runbook.md`
6. `skills/mgc-cross-region-migration/references/lessons-learned.md`

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
  - `terraform apply -replace=terraform_data.mgc_region_migration -auto-approve`
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

## Related Reference

- For reusable problem/experience summaries, load [lessons-learned.md](lessons-learned.md).
- For packaged migration assets and manifest, load [reuse-bundle.md](reuse-bundle.md).
