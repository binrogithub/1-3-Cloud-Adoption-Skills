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

## Validation

A successful notebook run reports:

- cells executed without failures.
- a transient MRS cluster id.
- later MRS job list should show two successful jobs for one smoke table:
  - `bronze-dockone_exampleapp_payment_outbox`
  - `silver-dockone_exampleapp_payment_outbox`

## Windows Note

The notebook contains Linux/JupyterHub direct Python cells. The local Windows runner intentionally skips those and uses the PowerShell orchestration path.
