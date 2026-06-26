# Reuse Bundle for Similar Migration Scenarios

## Purpose

Package migration method, process, commands, and output artifacts in one place so future cross-region migrations can reuse a proven path with minimal rework.

## Recommended Execution Sequence

1. Precheck input and source registration in SMS.
2. Pre-migration cleanup: remove obsolete source-bound SMS tasks.
3. Run Terraform migration workflow.
4. If Terraform shows `No changes`, rerun with resource replace.
5. Postcheck target VPC/EIP/security groups.
6. Poll task state until terminal status (`*_SUCCESS` or `*_FAIL`).
7. Archive all run artifacts into `skills/.../bundles/`.

## Canonical Commands

```bash
cd /root/mgc-cross-region-migration
terraform init
terraform apply -auto-approve
terraform apply -replace=terraform_data.mgc_region_migration -auto-approve
cat out/migration_result.json
cat out/precheck_task_cleanup.json
cat out/postcheck_network.json
cat out/task_poll_latest.json
```

## Artifact Manifest

Keep these files after every run:

- `out/migration_result.json`: core migration IDs and network result.
- `out/precheck_task_cleanup.json`: historical task cleanup evidence.
- `out/postcheck_network.json`: target VPC/EIP/SG connectivity verification.
- `out/task_poll_latest.json`: terminal task state timeline.

Optional supporting files:

- `main.tf`
- `variables.tf`
- `scripts/mgc_migrate.py`
- `skills/mgc-cross-region-migration/SKILL.md`
- `skills/mgc-cross-region-migration/references/runbook.md`
- `skills/mgc-cross-region-migration/references/lessons-learned.md`

## Packaging Rule

Store each completed migration under:

- `skills/mgc-cross-region-migration/bundles/<date>-<source>-to-<target>/`

Each bundle should include:

1. A `README.md` with source/target region, source VM ID, task ID, final state, and key timestamps.
2. The 4 core `out/*.json` artifacts.
3. Any extra evidence needed for postmortem (only non-secret information).

## One-Command Bundle Generation

Use the bundled script:

```bash
cd /root/mgc-cross-region-migration
bash skills/mgc-cross-region-migration/tools/build_bundle_from_latest_out.sh <bundle-name>
```

Example:

```bash
bash skills/mgc-cross-region-migration/tools/build_bundle_from_latest_out.sh 2026-04-22-mx2-to-santiago
```
