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

## Cleanup Status

- Debug MRS cluster `aa80ee9e-e55b-42c3-a7e1-9c5f652c182f` was deleted and reached `terminated`.
- Notebook transient cluster `748983a3-fde4-4c35-b83c-350c5728ee8a` self-terminated.
- OBS bucket `docktest` and uploaded objects remain.
- Earlier DLI pool/queue may still exist from pre-MRS testing and should be reviewed if cost cleanup is requested.
