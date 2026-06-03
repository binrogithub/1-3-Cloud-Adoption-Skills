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

## Cleanup

Use v1 DeleteCluster API or console to delete debug clusters. Transient `delete_when_no_steps=true` clusters should self-terminate, but always verify final state.
