# Notebook Automation

The notebook is an automated trigger/orchestrator, not a static demo document.

## Files

- Notebook: `outputs/huawei-dli-hudi-demo/notebooks/dli_hudi_demo.ipynb`.
- Runner: `outputs/huawei-dli-hudi-demo/notebooks/run_notebook_auto.py`.
- PowerShell wrapper: `outputs/huawei-dli-hudi-demo/scripts/15_run_notebook_auto.ps1`.
- MRS workflow wrapper: `outputs/huawei-dli-hudi-demo/scripts/19_resume_mrs_notebook_workflow.ps1`.

## Parameters

Important runner parameters:

- `--engine mrs`
- `--bucket docktest`
- `--transient-mrs-cluster`
- `--smoke-tables 1`
- `--execute`

PowerShell equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\15_run_notebook_auto.ps1 `
  -Engine mrs `
  -Bucket docktest `
  -TransientMrsCluster `
  -SmokeTables 1
```

## What It Does

The notebook runner executes the local notebook cells and calls the MRS platform wrapper. The MRS wrapper:

1. Selects Huawei Cloud auth, with `-ForceFallbackAuth` when needed.
2. Validates the demo package.
3. Packages PySpark jobs.
4. Ensures OBS bucket exists.
5. Uploads Python, SQL, schema, and synthetic CDC objects.
6. Uploads the Hudi Spark bundle.
7. Starts MRS dataflow execution.
8. Waits for bronze and silver Spark jobs to finish.
9. For transient clusters, requests cluster deletion and verifies cleanup separately.

## Cloud Notebook Deployment

The cloud notebook used in the Chile demo is an ECS-hosted JupyterLab trigger, not DataArts Studio.

- ECS name: `dockone-notebook-scheduler`.
- JupyterLab port: `8888`.
- Demo package path on ECS: `/opt/dockone-demo/huawei-dli-hudi-demo`.
- Jupyter systemd service: `dockone-jupyter.service`.
- Run-on-boot services: `dockone-run-onboot.service` and `dockone-run-onboot.timer`.
- ECS agency: `dockone_mrs_ecs_agency`.

Use cloud-side agency metadata where possible. Local Jupyter token and admin password are DPAPI-protected on the user's Windows machine; never copy them into skill files, repo files, or logs.

When synchronizing repaired scripts to the cloud notebook, use Jupyter Contents API with the local DPAPI token and upload as base64 if text mode returns an encoding error.

Files synchronized in the stable Chile repair:

- `scripts/18_run_mrs_dataflow_workflow.py`
- `scripts/19_resume_mrs_notebook_workflow.ps1`
- `config/mrs-config.json`
- `config/mrs-config-sa-brazil-1.json`

## Validation

A successful notebook run reports:

- cells executed without failures.
- a transient MRS cluster id or an existing MRS cluster id.
- MRS job list shows successful jobs for one smoke table:
  - `bronze-dockone_exampleapp_payment_outbox`
  - `silver-dockone_exampleapp_payment_outbox`

Latest validated local notebook-triggered existing-cluster run:

- Cells executed: `2, 3, 4, 5, 7, 9`.
- Failures: none.
- Bronze job: `8595bac3-7ce7-49db-b253-2cdb23adfec3`, `SUCCEEDED`.
- Silver job: `e5e1f2fd-6877-4f61-b084-612a75e3ccc7`, `SUCCEEDED`.

For transient notebook runs, keep `scripts\19_resume_mrs_notebook_workflow.ps1` passing `--wait-transient --transient-submit-mode manual` so the notebook waits for actual results.

## Windows Note

The notebook contains Linux/JupyterHub direct Python cells. The local Windows runner intentionally skips those and uses the PowerShell orchestration path.
