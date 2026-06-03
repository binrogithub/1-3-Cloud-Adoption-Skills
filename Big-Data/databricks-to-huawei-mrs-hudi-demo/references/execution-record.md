# Execution Record

This reference records the completed Databricks-to-Huawei MRS/Hudi demo run.

## Source Analysis

- Input archive: `C:/Users/Matebook/Downloads/databricks-workflows-script.7z`.
- Extracted Databricks project contained:
  - `task.py` entrypoint with `--job_id` and `--step bronze|silver`.
  - `frame_dockone/process.py` CDC processing logic.
  - project YAML for `job_dockone_dockone_exampleapp_silver`.
  - one concrete pipeline config for `billing_contracts`.
  - 21 task table names.
- No real customer database schema, DDL, field list, or raw CDC sample was present.

## Deliverables Created

- Architecture:
  - `outputs/databricks-to-huaweicloud-architecture-v2.drawio`
  - `outputs/databricks-to-huaweicloud-architecture-v2.json`
  - `outputs/databricks-to-huaweicloud-resources-v2.csv`
- Synthetic CDC data:
  - `outputs/synthetic-cdc-data/raw/.../*.json`
  - `outputs/synthetic-cdc-data/schema/inferred-table-schemas.json`
  - `outputs/synthetic-cdc-data/schema/inferred-table-ddl.sql`
  - `outputs/synthetic-cdc-data/manifest.json`
- Demo package:
  - `outputs/huawei-dli-hudi-demo`
  - despite the historical folder name, the active path now supports MRS as the execution engine.

## Cloud Resources Used

- Region: `la-south-2`.
- OBS bucket: `docktest`.
- Hudi bundle uploaded to `obs://docktest/jobs/jars/hudi-spark3.3-bundle_2.12-0.15.0.jar`.
- Spark jobs uploaded under `obs://docktest/jobs/dli/`.
- Synthetic raw data uploaded under `obs://docktest/raw/...`.
- Hudi outputs written under:
  - `obs://docktest/lake/bronze/payment/outbox`
  - `obs://docktest/lake/silver/payment/outbox`

## Successful Smoke Result

Test table: `dockone_exampleapp_payment_outbox`.

Existing-cluster controlled run on MRS cluster `aa80ee9e-e55b-42c3-a7e1-9c5f652c182f`:

- Bronze job `3661c28d-fbe7-4b5b-b340-28dc8ef29e99`: `SUCCEEDED`.
- Silver job `b1b7be9b-d92b-472c-b615-1ac9599efb83`: `SUCCEEDED`.
- Runtime summary: `outputs/huawei-dli-hudi-demo/runtime/mrs-dataflow-run-summary.json`.

Notebook-triggered transient MRS run:

- Transient cluster: `748983a3-fde4-4c35-b83c-350c5728ee8a`.
- Final cluster state: `terminated`.
- Bronze job `794cf9c5-9622-43d2-b4a5-fa4572a8f9cd`: `SUCCEEDED`.
- Silver job `0d2f6ab6-307e-4a58-9aaf-fd0766879901`: `SUCCEEDED`.
- Notebook execution reported no local failures.

## Latest Chile Stable Repair Result

Date: 2026-06-03.

Purpose:

- Stabilize the Chile MRS + OBS + Hudi workflow after transient cluster timing issues.
- Verify notebook as an automated trigger that waits for results.

Script repairs:

- `scripts/18_run_mrs_dataflow_workflow.py`
  - Uses manual transient mode by default.
  - Adopts same-name jobs created by run-job-flow.
  - Retries explicit job submission while JobGateway warms up.
  - Waits for the first bronze step when it already exists.
- `scripts/19_resume_mrs_notebook_workflow.ps1`
  - Adds `--wait-transient --transient-submit-mode manual` for transient notebook runs.

Validated existing-cluster smoke on debug cluster `6edebdbe-62b1-44db-aafd-8e15e16cda79`:

- Bronze job `d960ad3c-d19b-485e-8abf-9eaf8796ed98`: `SUCCEEDED`.
- Silver job `97d7dbfe-9049-47eb-97c1-218956a32756`: `SUCCEEDED`.

Validated notebook-triggered existing-cluster smoke on the same cluster:

- Cells executed: `2, 3, 4, 5, 7, 9`.
- Failures: none.
- Bronze job `8595bac3-7ce7-49db-b253-2cdb23adfec3`: `SUCCEEDED`.
- Silver job `e5e1f2fd-6877-4f61-b084-612a75e3ccc7`: `SUCCEEDED`.

Cleanup:

- Debug cluster `6edebdbe-62b1-44db-aafd-8e15e16cda79` was deleted and reached `terminated`.
- Latest repaired files were synced to the ECS cloud notebook through Jupyter Contents API.

## Cleanup Status

- Debug MRS cluster `aa80ee9e-e55b-42c3-a7e1-9c5f652c182f` was deleted and reached `terminated`.
- Notebook transient cluster `748983a3-fde4-4c35-b83c-350c5728ee8a` self-terminated.
- OBS bucket `docktest` and uploaded objects remain.
- Earlier DLI pool/queue may still exist from pre-MRS testing and should be reviewed if cost cleanup is requested.
