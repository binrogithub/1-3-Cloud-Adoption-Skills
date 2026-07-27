---
name: databricks-to-huawei-mrs-hudi-demo
description: Use when analyzing or migrating Databricks CDC/Delta workflow scripts into a Huawei Cloud Chile MRS + OBS + Apache Hudi demo, including synthetic CDC data generation, notebook-triggered automation, Delta-to-Hudi replacement, deployment troubleshooting, and smoke validation. Also use when continuing the dockone ExampleApp demo package under the Codex outputs folder.
---

# Databricks to Huawei MRS Hudi Demo

Use this skill to reproduce or continue the Databricks CDC workflow replacement demo built from `databricks-workflows-script.7z`.

Core target:

- Region: `la-south-2` (Chile).
- Storage: OBS bucket `docktest`.
- Compute default: MRS transient or existing MRS Spark, not DLI.
- Table format: Apache Hudi replacing Delta table behavior.
- Notebook role: an automated trigger/orchestrator that submits platform jobs, not only documentation.
- Secrets: never write AK/SK, IAM password, token, or temporary credentials into repo or skill files.

## Quick Workflow

1. Locate the demo package:
   - Preferred path: `C:\Users\Matebook\Documents\Codex\2026-06-02\files-mentioned-by-the-user-databricks\outputs\huawei-dli-hudi-demo`
   - Raw synthetic CDC data: sibling `outputs\synthetic-cdc-data`
2. Use existing credential selectors:
   - `scripts\14_select_huawei_auth.ps1`
   - Use `-ForceFallback` when the user explicitly chooses the fallback token/IAM credential.
3. For MRS notebook smoke:
   - Run `scripts\15_run_notebook_auto.ps1 -Engine mrs -Bucket docktest -TransientMrsCluster -SmokeTables 1`
   - This invokes `notebooks\run_notebook_auto.py`, which executes the notebook cells and calls `scripts\19_resume_mrs_notebook_workflow.ps1`.
4. For controlled existing-cluster execution:
   - Run auth, package, upload, then:
   - `python scripts\18_run_mrs_dataflow_workflow.py --execute --cluster-id <MRS_CLUSTER_ID> --limit 1`
5. Verify:
   - `runtime\mrs-dataflow-run-summary.json` for existing-cluster runs.
   - MRS job list for transient runs.
   - OBS paths under `obs://docktest/lake/bronze/...` and `obs://docktest/lake/silver/...`.

## Chile Stable Path

Use this path when the user asks to continue or reproduce the known-good Chile environment.

1. Use fallback IAM auth unless the user explicitly asks otherwise:
   - `. .\scripts\14_select_huawei_auth.ps1 -ForceFallback`
2. Validate and package:
   - `python scripts\06_validate_demo_package.py`
   - `powershell -ExecutionPolicy Bypass -File scripts\01_package_jobs.ps1`
3. Ensure OBS and upload assets:
   - `python scripts\07_create_minimal_chile_resources.py --execute --skip-dli`
   - `python scripts\02_upload_assets_to_obs.py --execute`
   - `python scripts\17_prepare_mrs_assets.py --execute`
4. Run smoke with one table first:
   - Existing MRS: `python -u scripts\18_run_mrs_dataflow_workflow.py --execute --cluster-id <cluster-id> --limit 1`
   - Notebook trigger against existing MRS: `powershell -ExecutionPolicy Bypass -File scripts\15_run_notebook_auto.ps1 -Engine mrs -Bucket docktest -MrsClusterId <cluster-id> -SmokeTables 1`
   - Transient MRS: `powershell -ExecutionPolicy Bypass -File scripts\15_run_notebook_auto.ps1 -Engine mrs -Bucket docktest -TransientMrsCluster -SmokeTables 1`
5. Always verify:
   - MRS bronze and silver jobs are `FINISHED` / `SUCCEEDED`.
   - `obs://docktest/lake/bronze/payment/outbox/` exists.
   - `obs://docktest/lake/silver/payment/outbox/` exists.
   - Any debug/transient MRS cluster reaches `terminated`.

## Process Map

- Analyze Databricks source: `task.py`, `frame_dockone/process.py`, project YAML, task table list.
- Generate synthetic CDC data because the archive has no real customer schema or raw samples.
- Build Huawei demo package with PySpark jobs, notebook automation, OBS upload scripts, and MRS orchestration.
- Replace Databricks Delta writes/merge semantics with Hudi copy-on-write upsert/delete writes.
- Deploy minimally on Huawei Cloud:
  - OBS bucket and objects are persistent.
  - MRS transient clusters are preferred for smoke runs and should terminate after steps.
  - Existing MRS clusters may be used for debugging and sequential bronze->silver control.

## Important Rules

- Always preserve the original Databricks flow shape: raw CDC -> bronze -> silver. SQL is validation/inspection, not a replacement for the pipeline.
- Keep MRS resources minimal but realistic. The tested Chile spec used 2 master + 3 core nodes with `c6.4xlarge.4.linux.bigdata` because smaller DLI alternatives were unavailable and MRS needs multi-node topology.
- For smoke, run one table first: `dockone_exampleapp_payment_outbox`.
- Do not enable Hive sync in the first minimal PoC. It caused MRS job failure after Hudi write stages completed. Keep `hoodie.datasource.hive_sync.enable=false` until Hive metastore sync is explicitly configured.
- When using MRS `run-job-flow`, do not set log dump/log URI for `MRS 3.5.0-LTS`; that version returned `MRS.00005063: not support log dump`.
- MRS job list `offset` starts at `1`, not `0`.
- If a debug MRS cluster is created with `--keep-cluster`, delete it after inspection.
- MRS `running` does not always mean JobGateway is ready. `scripts\18_run_mrs_dataflow_workflow.py` must keep the retry/adopt-existing-job logic for Chile transient clusters.
- In manual transient mode, do not blindly resubmit the first bronze step. If run-job-flow already created a same-name bronze job, wait for or adopt that job, then submit silver.
- Cloud notebook files can be synchronized through Jupyter Contents API, but never print or store the Jupyter token in repo/skill files. The local token is DPAPI-protected under `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\cloud-notebook-credentials.xml`.

## References

Read only what is needed:

- `references/execution-record.md`: full chronological execution record and final status.
- `references/synthetic-cdc-data.md`: synthetic schema/data generation rules.
- `references/delta-to-hudi.md`: Delta table to Hudi replacement mapping.
- `references/notebook-automation.md`: notebook trigger design and commands.
- `references/mrs-deployment-notes.md`: Huawei Cloud deployment issues, fixes, and validation.

## Helper Scripts

- `scripts/run-mrs-notebook-smoke.ps1`: runs the notebook MRS smoke path from a demo package.
- `scripts/check-mrs-run.ps1`: checks MRS cluster and job list status for a cluster id.
