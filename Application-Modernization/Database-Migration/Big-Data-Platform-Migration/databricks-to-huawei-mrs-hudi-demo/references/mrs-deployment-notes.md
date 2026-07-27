# MRS Deployment Notes

## Working Auth Pattern

Use the project scripts; do not hand-code secrets:

```powershell
. .\scripts\14_select_huawei_auth.ps1 -ForceFallback
```

This uses the locally stored fallback IAM credential and exchanges it for temporary AK/SK plus a security token for OBS where needed.

## MRS Cluster Shape Used

Region: `la-south-2`.

Cluster config:

- Version: `MRS 3.5.0-LTS`.
- Components: `Hadoop,Hive,Spark,JobGateway`.
- VPC: `vpc-cloudera-test`.
- Subnet: `subnet-cloudera-test`.
- Security group: `0e302a4d-fe1c-42e5-a3ff-31c2a99b0a19`.
- Availability zone: `la-south-2a`.
- Node shape: `c6.4xlarge.4.linux.bigdata`.
- Master nodes: 2.
- Core nodes: 3.
- Root volume: SAS 480 GB.
- Data volume: SAS 600 GB x 1.

This was not truly tiny, but it was the minimal successful MRS shape found by reusing the prior account network and historical cluster sizing.

## Chile Stable Deployment Process

Known-good sequence for the dockone ExampleApp smoke table:

```powershell
Set-Location C:\Users\Matebook\Documents\Codex\2026-06-02\files-mentioned-by-the-user-databricks\outputs\huawei-dli-hudi-demo
. .\scripts\14_select_huawei_auth.ps1 -ForceFallback
python scripts\06_validate_demo_package.py
powershell -ExecutionPolicy Bypass -File scripts\01_package_jobs.ps1
python scripts\07_create_minimal_chile_resources.py --execute --skip-dli
python scripts\02_upload_assets_to_obs.py --execute
python scripts\17_prepare_mrs_assets.py --execute
python -u scripts\18_run_mrs_dataflow_workflow.py --execute --cluster-id <MRS_CLUSTER_ID> --limit 1
```

Notebook-triggered existing-cluster smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\15_run_notebook_auto.ps1 `
  -Engine mrs `
  -Bucket docktest `
  -MrsClusterId <MRS_CLUSTER_ID> `
  -SmokeTables 1
```

Notebook-triggered transient smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\15_run_notebook_auto.ps1 `
  -Engine mrs `
  -Bucket docktest `
  -TransientMrsCluster `
  -SmokeTables 1
```

The notebook path executes `notebooks\run_notebook_auto.py`, then `scripts\19_resume_mrs_notebook_workflow.ps1`, then `scripts\18_run_mrs_dataflow_workflow.py`.

Validated latest smoke:

- Region: `la-south-2`.
- Bucket: `docktest`.
- Table: `dockone_exampleapp_payment_outbox`.
- Bronze job examples: `d960ad3c-d19b-485e-8abf-9eaf8796ed98`, `8595bac3-7ce7-49db-b253-2cdb23adfec3`.
- Silver job examples: `97d7dbfe-9049-47eb-97c1-218956a32756`, `e5e1f2fd-6877-4f61-b084-612a75e3ccc7`.
- Result: bronze and silver `FINISHED` / `SUCCEEDED`.
- Cleanup: debug cluster `6edebdbe-62b1-44db-aafd-8e15e16cda79` reached `terminated`.
- Output prefixes:
  - `obs://docktest/lake/bronze/payment/outbox/`
  - `obs://docktest/lake/silver/payment/outbox/`

## Issues Found and Fixes

### DLI Blockers

- DLI general queues 16/64/256/512 CU were sold out.
- DLI elastic resource pool and queue could be created.
- Spark 3.3.1 DLI job was blocked by custom agency requirements.
- The IAM user could not list/manage agencies.
- Decision: replace DLI with MRS.

### MRS run-job-flow Log Dump

Problem:

```text
MRS.00005063: The cluster version MRS 3.5.0-LTS is not support log dump.
```

Fix:

- Do not set `log_uri` or log dump options in `run-job-flow` body for this version.

### OBS Endpoint

Problem:

- Spark jobs need OBS endpoint properties on MRS.

Fix:

```json
{
  "fs.obs.endpoint": "obs.la-south-2.myhuaweicloud.com"
}
```

### Unexpanded Bucket Variable

Problem:

- Existing-cluster submit initially passed `obs://${DEMO_BUCKET}/...` as Hudi jar path.

Fix:

- Set `os.environ["DEMO_BUCKET"] = bucket` inside `18_run_mrs_dataflow_workflow.py`.

### Hive Sync Failure

Problem:

- Hudi write stages completed but job finished as failed.
- Failure was consistent with Hive sync/metastore integration in a minimal cluster.

Fix:

- Set `hoodie.datasource.hive_sync.enable=false` for bronze and silver scripts.

### Query Offset

Problem:

- MRS v2 job list with `offset=0` failed.

Fix:

- Use `offset=1`.

### JobGateway Warm-Up and Duplicate Bronze

Problem:

- A transient cluster can report `running` while MRS JobGateway is not ready to accept a new explicit Spark job.
- The first run-job-flow bronze step may be created asynchronously.
- The old manual transient code saw the first bronze step as "not succeeded" and attempted to submit bronze again immediately.
- MRS returned:

```text
0173 Failed to submit the job
409 Tasks are being executed in the cluster
```

Fix:

- Keep `scripts\18_run_mrs_dataflow_workflow.py` logic that:
  - Normalizes MRS job-list fields.
  - Finds same-name jobs.
  - Adopts an existing same-name job instead of duplicating it.
  - Retries job submission while JobGateway warms up.
  - Waits for the first run-job-flow bronze step when visible.
- Keep `scripts\19_resume_mrs_notebook_workflow.ps1` passing:

```powershell
--wait-transient --transient-submit-mode manual
```

This makes notebook-triggered transient runs wait for actual results, not just submission.

## Cleanup

Use v1 DeleteCluster API or console to delete debug clusters. Transient `delete_when_no_steps=true` clusters should self-terminate, but always verify final state.
