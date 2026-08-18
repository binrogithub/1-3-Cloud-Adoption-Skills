# Golden Migration Packages

## Overview

Golden packages are reference migration packages that validate the framework is reusable and not hardcoded to a single case.

## Packages

### orders_pipeline_simple

- **Status:** runtime-confirmed
- **Source pattern:** MERGE (upsert)
- **Flow:** RAW_ORDERS → SILVER_ORDERS → GOLD_DAILY_SALES → TASK_AUDIT
- **Validation checks:** 7
- **Doctor warnings:** 2 (full-refresh, MERGE+DLI)
- **Runtime confirmed:** Yes
- **Equivalence:** EQUIVALENT

### customer_status_pipeline_simple

- **Status:** package/dry-run validated, not runtime-confirmed yet
- **Source pattern:** INSERT INTO SELECT (non-upsert)
- **Flow:** RAW_CUSTOMERS → SILVER_CUSTOMERS → GOLD_CUSTOMER_STATUS → TASK_AUDIT
- **Validation checks:** 8
- **Doctor warnings:** 1 (full-refresh only; no MERGE warning)
- **Runtime confirmed:** No
- **Equivalence:** NOT_EXECUTED

## Key Differences

| Aspect | orders_pipeline_simple | customer_status_pipeline_simple |
|--------|----------------------|-------------------------------|
| Source operation | MERGE | INSERT INTO SELECT |
| Doctor MERGE warning | Yes | No |
| Doctor warnings | 2 | 1 |
| Validation checks | 7 | 8 |
| Runtime confirmed | Yes | No |
| Aggregate dimension | ORDER_DATE | CUSTOMER_STATUS |

## Batch Assessment

Run a consolidated assessment of all migration packages in a directory:

```bash
npm run migration:batch-assess -- --packages-dir cases/golden
```

This command scans the directory for valid migration packages, assesses each one, and generates a consolidated report. It is read-only and local: no cloud APIs, no SQL execution, no runtime execution.

### Readiness Statuses

| Status | Description |
|--------|-------------|
| RUNTIME_CONFIRMED | Package has been executed and equivalence confirmed (equivalence_confirmed=true or final_equivalence=EQUIVALENT). |
| DRY_RUN_VALIDATED | Package is locally valid and doctor-healthy; expected equivalence status is NOT_EXECUTED (dry-run passed but no runtime evidence). |
| READY_FOR_DRY_RUN | Package is locally valid and doctor-healthy with no runtime evidence and no review warnings. Ready for dry-run validation. |
| NEEDS_REVIEW | Package has MERGE+DLI or full-refresh warnings that require human review before proceeding. Warnings are not fatal. |
| BLOCKED | Package doctor found fatal findings that must be resolved before any further steps. |
| INVALID_PACKAGE | Package structure is invalid (missing required files or manifest errors). |

### Output

- `out/batch_assessment_result.json` - Full assessment result as JSON.
- `out/batch_assessment_report.md` - Human-readable markdown report.

## Batch Validation

Run a full local/dry-run validation workflow for every migration package in a directory:

```bash
npm run migration:batch-validate -- --packages-dir cases/golden --adapter legacy-demo --dli-queue default
```

This command goes beyond batch assessment. For each package it executes the full local readiness pipeline:

1. **package-load** - Load and validate package structure
2. **plan** - Build migration plan
3. **doctor** - Run package doctor health checks
4. **prepare-runtime** - Prepare runtime artifacts (copy SQL, generate DAG, pipeline YAML)
5. **execute-plan** - Build execution plan
6. **execute-dry-run** - Migration executor dry-run through legacy-demo adapter

### batch-assess vs batch-validate

| Aspect | batch-assess | batch-validate |
|--------|-------------|---------------|
| Scope | Readiness assessment only | Full local prepare + execute-plan + dry-run |
| Stages | package-load, plan, doctor | package-load, plan, doctor, prepare-runtime, execute-plan, execute-dry-run |
| Runtime artifacts | Not prepared | Prepared (SQL copied, DAG, pipeline YAML) |
| Dry-run | Not executed | Executed via legacy-demo adapter |
| Cloud APIs | No | No |
| SQL execution | No | No |
| Confirm | No | No |

### Validation Statuses

| Status | Description |
|--------|-------------|
| BATCH_DRY_RUN_VALIDATED | All stages passed: package loaded, plan built, doctor healthy, runtime prepared, execution plan ready, dry-run successful. |
| INVALID_PACKAGE | Package structure is invalid or plan could not be built. |
| DOCTOR_UNHEALTHY | Doctor found fatal findings that block the package. |
| RUNTIME_PREPARE_FAILED | Runtime artifact preparation failed. |
| EXECUTION_PLAN_FAILED | Execution plan build failed. |
| DRY_RUN_FAILED | Dry-run execution through the adapter failed. |

### Safety

- Dry-run only: no confirm mode is used.
- No cloud API calls.
- No SQL execution.
- No runtime execution.
- No jobs created, started, or published.

### Output

- `out/batch_validation_result.json` - Full validation result as JSON.
- `out/batch_validation_report.md` - Human-readable markdown report.

## Package-specific runtime artifacts

Each golden package can include package-specific runtime data and validation artifacts under a `runtime/` directory:

```
cases/golden/<migration_id>/
  runtime/
    setup/
      01_create_schema.sql
      02_create_raw_tables.sql
      03_insert_seed_data.sql
    validation/
      validation_queries.json
```

### runtime/setup/*.sql

Package-specific seed/prep SQL for setting up the source data environment before pipeline execution. Each file contains exactly one DLI-compatible SQL statement. Files are sorted by filename and executed in order. These define the raw source tables and seed data that the pipeline transforms.

### runtime/validation/validation_queries.json

Package-specific validation queries for confirming runtime results. Each query has:
- `id` - unique identifier
- `type` - TABLE_COUNT, AGGREGATE_CHECK, TASK_AUDIT_SUCCESS, or FINAL_EQUIVALENCE
- `object_name` - the object being validated
- `sql` - the DLI SQL query to execute
- `expected` - the expected result value

### Local-only artifacts

These are local artifacts and are **not executed** by `batch-validate`. They are:
- Loaded and validated by `runtime-package-loader.js` (structure, single-statement, field completeness)
- Cross-checked by `runtime-validation-plan-checker.js` (every non-PIPELINE_READY / non-FINAL_EQUIVALENCE validation plan check has a corresponding runtime query)
- Checked by `package-doctor.js` (warnings if missing, findings if present but invalid)
- Copied into prepared runtime artifacts by `runtime-preparer.js`

### Future native runtime engine

A future native runtime engine confirm will use these artifacts to avoid hardcoded demo validation. Instead of relying on the legacy one-shot runtime (which was designed around the orders demo dataset), the engine will:
1. Execute `runtime/setup/*.sql` to prepare the source environment
2. Execute the pipeline SQL nodes
3. Execute `runtime/validation/validation_queries.json` queries and compare results to expected values

This makes runtime confirmation generic per migration package rather than hardcoded to a single demo.

## Native DLI Runtime Plan

The `native-dli` adapter is a dry-run/planning-only adapter that builds a package-specific native execution plan. It does not depend on the legacy demo-one-shot path.

### Building a native runtime plan

```bash
npm run runtime:native-plan -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

This produces:
- `out/native_runtime_plan_result.json` — Full plan as JSON
- `out/native_runtime_plan_report.md` — Human-readable markdown report

### Plan phases

| Phase | Type | Description |
|-------|------|-------------|
| runtime_setup | DLI_SQL | Steps for each `runtime/setup/*.sql` file |
| target_transform | DLI_SQL | Steps for each `target/sql/*.sql` from artifact manifest dependency order |
| runtime_validation | DLI_QUERY | Steps for each runtime validation query |
| equivalence_summary | LOCAL_COMPARISON | Local comparison of DLI results vs expected |

### Using native-dli with migration:execute

```bash
npm run migration:execute -- --dry-run --adapter native-dli --package-dir cases/golden/orders_pipeline_simple --job-name native_dli_dryrun --dli-queue default
```

The `native-dli` adapter is dry-run only. Confirm mode returns `UNSUPPORTED_MODE`. The `legacy-demo` adapter remains the only confirm-capable adapter for now.

### Safety

- No cloud API calls
- No SQL execution
- No runtime execution
- No confirm
- No commands executed

### Native DLI Simulation

The `native-dli` adapter supports a **SIMULATE** mode that exercises the native runtime plan end-to-end locally without calling Huawei Cloud or executing SQL:

```bash
npm run runtime:native-simulate -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

Or via the migration executor:

```bash
npm run migration:execute -- --simulate --adapter native-dli --package-dir cases/golden/orders_pipeline_simple --job-name native_sim_orders --dli-queue default
```

Simulation produces:
- `out/native_dli_simulation_result.json` — Full simulation result as JSON
- `out/native_dli_simulation_report.md` — Human-readable markdown report
- `out/runs/<run_id>/native_dli_simulation_result.json` — Per-run result
- `out/runs/<run_id>/native_dli_simulation_report.md` — Per-run report
- `out/runs/<run_id>/current_run.json` — Current run metadata

Key properties:
- `final_equivalence` is `SIMULATED_EQUIVALENT`, not `EQUIVALENT`
- `equivalence_confirmed` is always `false`
- `simulation_only` is `true`
- Validation rows are derived from expected values in `validation_queries.json`
- No cloud APIs called, no SQL executed, no runtime execution

### Native DLI Mock Execution

The `native-dli` adapter supports a **MOCK** mode that exercises the actual executor flow using an injectable mock DLI client:

```bash
npm run runtime:native-execute:mock -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

Or via the migration executor:

```bash
npm run migration:execute -- --mock --adapter native-dli --package-dir cases/golden/orders_pipeline_simple --job-name native_mock_orders --dli-queue default
```

Mock execution produces:
- `out/native_dli_mock_execution_result.json` — Full mock execution result as JSON
- `out/native_dli_mock_execution_report.md` — Human-readable markdown report
- `out/runs/<run_id>/native_dli_mock_execution_result.json` — Per-run result
- `out/runs/<run_id>/native_dli_mock_execution_report.md` — Per-run report
- `out/runs/<run_id>/current_run.json` — Current run metadata

Key properties:
- `final_equivalence` is `MOCK_EQUIVALENT`, not `EQUIVALENT`
- `equivalence_confirmed` is always `false`
- `real_runtime_confirmed` is always `false`
- `mock_execution` is `true`
- Validation rows are derived from mock DLI client results
- No cloud APIs called, no real SQL executed, no runtime execution

### Future work

A future native DLI execution adapter will use the native runtime plan to execute setup SQL, pipeline SQL, and validation queries directly via KooCLI/API or existing DLI helpers, without the legacy demo-one-shot dependency.

## Native DLI Guarded Execution

A guarded native DLI execution path exists as a standalone runtime command. Real execution is **not run automatically** and requires explicit guardrail flags.

### Plan-only mode (safe, no SQL execution)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --plan-only
```

Returns `NATIVE_DLI_GUARDED_PLAN_READY` with:
- `planned_sql_executions`: 8 (3 setup + 5 target)
- `planned_query_executions`: 7
- `total_planned_requests`: 15

No SQL is executed. No cloud write APIs are called.

### Guarded real mode (future, requires all flags)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --allow-real-execution \
  --confirm-native-dli \
  --i-understand-this-executes-sql
```

Real execution requires **all three** explicit flags. If any flag is missing, execution is blocked. If all flags are present but implementation is not yet complete, returns `NATIVE_DLI_REAL_EXECUTION_NOT_IMPLEMENTED`.

### Safety

- Plan-only: `plan_only`, `no_sql_execution`, `no_runtime_execution`
- Real mode: `guarded_real_execution`, `sql_execution_possible`
- Both modes: `explicit_native_confirm_required`, `understand_executes_sql_required`, `preflight_required`, `no_publish`, `no_delete`, `no_update`, `no_overwrite`, `no_schedule_start`
- `migration:execute --confirm --adapter native-dli` remains **unsupported**

## Real DLI Client v0.1 (Scaffold)

A real DLI client scaffold provides plan-only DLI request planning without executing any SQL or calling any cloud APIs.

### DLI Client Plan

Each golden package produces **15 planned DLI requests** (3 setup + 5 target + 7 validation) plus 1 local equivalence comparison step:

| Package | Setup SQL | Target SQL | Validation Queries | Total DLI Requests |
|---------|-----------|------------|--------------------|--------------------|
| orders_pipeline_simple | 3 | 5 | 7 | 15 |
| customer_status_pipeline_simple | 3 | 5 | 7 | 15 |

```bash
npm run dli:client:plan -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
npm run dli:client:plan -- --package-dir cases/golden/customer_status_pipeline_simple --dli-queue default
```

### DLI Client Doctor

```bash
npm run dli:client:doctor
```

Validates config, client interface, and safety policy. No cloud APIs, no SQL execution.

### DLI Client Live Read-Only Preflight

```bash
npm run dli:client:live-preflight -- --dli-queue default --read-only
```

Validates live Huawei Cloud/DLI connectivity and queue accessibility using read-only API calls only. The `--read-only` flag is required.

- **dli:client:doctor** = local config/interface validation (no cloud calls)
- **dli:client:plan** = request planning only (no cloud calls)
- **dli:client:live-preflight** = read-only live connectivity/queue check (read-only GET only)
- No SQL execution
- No native confirm yet
- `--read-only` required

### Safety

- Plan only: no cloud APIs, no SQL execution, no runtime execution, no confirm
- Live preflight: read-only GET calls only, no SQL execution, no runtime execution, no cloud write calls, no confirm
- Secrets are never exposed in config validation or preflight results
- Runtime config loading: config override > process.env > .env.dataarts > defaults
- DLI doctor/preflight use masked config (AK/SK shown as PRESENT/NOT SET only)
- `allowRealExecution: true` requires all three guard flags or throws
- Native-dli CONFIRM remains UNSUPPORTED

### DLI HTTP Transport Layer

The real DLI client now routes through a DLI HTTP transport layer (`dli-http-transport.js`) that provides:

- Request builders for DLI SQL job submission, status polling, and result fetching
- Strict three-flag execution guard (`allowRealExecution`, `confirmNativeDli`, `understandExecutesSql`)
- Injectable `httpClient` for testing (no real cloud calls in tests)
- AK/SK signing via `huawei-signer.js` (SDK-HMAC-SHA256)
- Secret scrubbing on all output and errors

```bash
npm run dli:transport:plan -- --package-dir cases/golden/customer_status_pipeline_simple --dli-queue default
```

Shows exact transport-level HTTP requests without execution.

### DLI Submit-Job Audit

```bash
npm run dli:submit-job:audit -- --package-dir cases/golden/customer_status_pipeline_simple --dli-queue default
```

Audits every planned DLI submit-job request against the documented API shape. This is a **local-only** audit — no cloud APIs, no SQL execution.

**What it checks:**
- Request method is POST and path matches `/v1.0/{project_id}/jobs/submit-job`
- `body.sql` is present and non-empty
- `body.queue_name` is present and matches the requested queue
- `body.currentdb` is present for non-CREATE DATABASE statements (warns if missing)
- `body.currentdb` is omitted for CREATE/DROP DATABASE statements (warns if present)
- `project_id` and `region` are present (warns if null — request cannot be submitted)
- Request body does not expose secrets

**Why submit-job may fail even when preflight passes:**
- Preflight checks queue accessibility (GET /queues) but submit-job requires `dli:queue:submitJob` IAM permission
- Missing `currentdb` for non-DDL statements can cause DLI to reject the job
- Missing `queue_name` causes DLI to use the default queue which may not exist or may lack resources

**Output:**
- `out/dli_submit_job_audit_result.json` — Full audit result as JSON
- `out/dli_submit_job_audit_report.md` — Human-readable markdown report

### Real execution status

- Real DLI SQL execution has **not been run** during this sprint.
- Request planning and live preflight must pass before any real run.
- `migration:execute --confirm --adapter native-dli` remains **unsupported**.

### DLI Queue Health Check

```bash
npm run dli:queue:health -- --dli-queue default --read-only
```

Reports DLI queue health including job counts by state. The `--read-only` flag is required. Never cancels jobs, never executes SQL, never mutates cloud resources.

### Queue Congestion Gate

Before real execution, the guarded executor checks DLI queue health. If LAUNCHING jobs exceed the threshold (default: 10, override with `--max-launching-jobs`), execution is blocked with `NATIVE_DLI_QUEUE_CONGESTED`. Does not apply in plan-only mode.

### Resume Support (--resume-from)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --resume-from target_transform \
  --plan-only
```

Allowed values: `runtime_setup` (default), `target_transform`, `runtime_validation`. Skipped steps are recorded as `SKIPPED_RESUME`. Do not retry full setup after partial setup success unless setup is idempotent.

### Future work

- Run real guarded execution after manual review of transport plan and preflight results
- The real client uses Huawei Cloud DLI API v1.0 with SDK-HMAC-SHA256 signing via the transport layer
