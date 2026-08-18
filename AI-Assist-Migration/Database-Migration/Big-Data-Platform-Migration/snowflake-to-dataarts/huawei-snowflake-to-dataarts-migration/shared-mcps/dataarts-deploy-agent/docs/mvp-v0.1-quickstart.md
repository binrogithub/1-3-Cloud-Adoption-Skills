# Migration Framework MVP v0.1 — Quickstart

## Prerequisites

- Node.js installed
- `.env.dataarts` configured with Huawei Cloud credentials
- Migration package at `cases/golden/orders_pipeline_simple`

## Step 1: Validate Package

```bash
npm run migration:doctor -- --package-dir cases/golden/orders_pipeline_simple
```

## Step 2: Prepare Runtime

```bash
npm run migration:prepare-runtime -- --package-dir cases/golden/orders_pipeline_simple
```

## Step 3: Dry-Run

```bash
npm run migration:execute -- \
  --dry-run \
  --adapter legacy-demo \
  --package-dir cases/golden/orders_pipeline_simple \
  --job-name <unique_job_name> \
  --dli-queue default
```

## Step 4: Real Controlled Execution

```bash
npm run migration:execute -- \
  --confirm \
  --adapter legacy-demo \
  --package-dir cases/golden/orders_pipeline_simple \
  --job-name <unique_job_name> \
  --dli-queue default
```

## Step 5: MVP Evidence Report

```bash
npm run migration:mvp-report -- \
  --migration-run-id <migration_run_id> \
  --runtime-run-id <runtime_run_id> \
  --job-name <job_name>
```

## Warnings

- **Always use a unique job name.** Reusing a job name will abort if the job already exists.
- **Do not reuse failed job names.** A failed job remains in DataArts Factory. Choose a new unique name.
- **Do not run `--confirm` unless `--dry-run` and `migration:doctor` are clean.** Confirm creates real DataArts resources and triggers run-immediate.
- **If failure occurs after create-job, do not blindly retry.** The job already exists. Diagnose first, then use a new job name if needed.
