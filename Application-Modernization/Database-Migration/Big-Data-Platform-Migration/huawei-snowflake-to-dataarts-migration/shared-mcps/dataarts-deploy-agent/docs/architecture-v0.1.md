# Migration Framework MVP v0.1 — Architecture

## Migration Pipeline

```
Migration Package
  │
  ▼
migration:plan
  │
  ▼
migration:doctor
  │
  ▼
migration:prepare-runtime
  │
  ▼
migration:execute-plan
  │
  ▼
  runtime adapter
    │
    ├─► runtime-engine (dry-run only)
    ├─► legacy-demo (dry-run + controlled confirm)
    ├─► koocli (diagnostic dry-run / future API adapter)
    └─► native-dli (dry-run / planning only)
    │
    ▼
one-shot runtime (legacy-demo path)
  │
  ▼
DataArts Factory
  │
  ▼
DLI
  │
  ▼
runtime validation
  │
  ▼
doctor
  │
  ▼
equivalence summary
  │
  ▼
MVP report
```

## Adapters

### runtime-engine

- **Mode:** Dry-run only
- **Purpose:** Validates the migration plan and generates a DataArts Create Job API payload without calling any cloud API
- **Confirm:** Not implemented
- **Safety:** Read-only, no API writes

### legacy-demo

- **Mode:** Dry-run + controlled confirm
- **Purpose:** Wraps the one-shot runtime to create a DataArts job, reset DLI demo data, run-immediate, and validate results
- **Confirm:** Yes (requires `--confirm` flag)
- **Safety:** Abort if job exists, no publish, no scheduled start, no overwrite, stale result protection

### koocli

- **Mode:** Diagnostic dry-run / future API adapter
- **Purpose:** Explores DataArts API surface via KooCLI for future direct API integration
- **Confirm:** Not implemented
- **Safety:** Read-only, diagnostic only

### native-dli

- **Mode:** Dry-run / planning only + Simulate (local simulation) + Mock (executor flow with mock DLI client)
- **Purpose:** Builds a package-specific native DLI runtime execution plan from `runtime/setup/*.sql`, `target/sql/*.sql`, and `runtime/validation/validation_queries.json`. Does not depend on hardcoded demo scripts.
- **Dry-run:** Plan only — no execution, no simulation
- **Simulate:** Local simulation of the native execution path — exercises the plan end-to-end without calling Huawei Cloud or executing SQL. Produces SIMULATED_EQUIVALENT (not EQUIVALENT). equivalence_confirmed is always false.
- **Mock:** Executor flow with mock DLI client — exercises the actual executor flow (submit setup SQL, submit target SQL, submit validation queries, compare results) using an injectable mock DLI client. Produces MOCK_EQUIVALENT (not EQUIVALENT). equivalence_confirmed is always false. real_runtime_confirmed is always false.
- **Confirm:** Not implemented (returns UNSUPPORTED_MODE)
- **Safety:** Read-only, no cloud APIs, no real SQL execution, no runtime execution
- **Future work:** A future native DLI execution adapter will use this plan to execute setup SQL, pipeline SQL, and validation queries directly via KooCLI/API or existing DLI helpers without the legacy demo-one-shot path.

## Real DLI Client v0.1 (Scaffold)

A real DLI client scaffold exists in `src/runtime/dli/real-dli-client.js`. This client implements the same `dli-client-interface.js` contract but operates in **plan-only** mode by default.

### Key properties

- **Default mode:** `allowRealExecution: false` — all methods return `PLANNED_NOT_EXECUTED` with a planned request object
- **Safety:** `no_real_sql_execution`, `no_cloud_write_calls`, `no_runtime_execution`, `no_confirm`, `secrets_redacted`
- **If `allowRealExecution: true`:** throws `"Real DLI execution is not enabled in this version."` — native confirm is not implemented yet
- **Config validation:** `validateRealDliClientConfig` uses the unified runtime config loader to check HUAWEI_REGION, HUAWEI_PROJECT_ID, HUAWEI_AK, HUAWEI_SK without exposing secrets

## DLI HTTP Transport Layer v0.1

The DLI HTTP transport layer (`src/runtime/dli/dli-http-transport.js`) provides low-level DLI HTTP request construction and optional execution behind strict three-flag guardrails.

### Transport interface

```js
{
  submitSqlJob({ sql, queueName, step })
  getSqlJobStatus({ jobId })
  getSqlJobResult({ jobId })
}
```

### Request builders

- `buildDliSqlJobRequest(options)` — constructs a POST request to `/v1.0/{projectId}/jobs/submit-job`
- `buildDliJobStatusRequest(options)` — constructs a GET request to `/v1.0/{projectId}/jobs?job_id={jobId}&limit=1`
- `buildDliJobResultRequest(options)` — constructs a GET request to `/v1.0/{projectId}/jobs/{jobId}`

### Three-flag execution guard

Real execution requires **all three** explicit flags:
- `allowRealExecution: true`
- `confirmNativeDli: true`
- `understandExecutesSql: true`

If any flag is missing, the transport returns `TRANSPORT_GUARDRAIL_BLOCKED` with a planned request. If all flags are present but no `httpClient` is configured, returns `NATIVE_DLI_TRANSPORT_NOT_CONFIGURED`. If the httpClient doesn't implement the required methods, returns `NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED`.

### Security

- AK/SK are never exposed in transport output or errors
- All error messages are scrubbed via `scrubSecrets`
- Request bodies include `sql` and `queue_name` but are never logged with secrets
- The transport uses `buildSignedHeaders` from `huawei-signer.js` for SDK-HMAC-SHA256 signing

### DLI Transport Plan

```bash
npm run dli:transport:plan -- --package-dir cases/golden/customer_status_pipeline_simple --dli-queue default
```

Shows the exact transport-level HTTP requests that would be made for each step, but no execution. No cloud APIs called, no SQL executed.

### DLI Submit-Job Audit

```bash
npm run dli:submit-job:audit -- --package-dir cases/golden/customer_status_pipeline_simple --dli-queue default
```

Audits every planned DLI submit-job request against the documented API shape. This is a **local-only** audit — no cloud APIs, no SQL execution.

**Checks performed:**
- `method` is POST
- `path` matches `/v1.0/{project_id}/jobs/submit-job`
- `body.sql` exists and is non-empty
- `body.queue_name` exists and matches requested queue
- `body.currentdb` is present for non-CREATE DATABASE statements (warns if missing for CREATE TABLE, INSERT, SELECT, MERGE)
- `body.currentdb` is omitted or warned for CREATE/DROP DATABASE statements
- `project_id` and `region` are present (warns if null)
- Request body does not expose secrets
- `sql_preview` is truncated

**Why submit-job may fail even when preflight passes:**
- Preflight checks queue accessibility (GET /queues) but submit-job requires `dli:queue:submitJob` IAM permission
- Missing `currentdb` for non-DDL statements can cause DLI to reject the job
- Missing `queue_name` causes DLI to use the default queue which may not exist or may lack resources
- Region/project_id must be present for URL construction

### Real execution status

- **Real DLI SQL execution has NOT been run during this sprint.**
- Request planning and live preflight must pass before any real run.
- `migration:execute --confirm --adapter native-dli` remains **unsupported**.

### Runtime Configuration Loading

The DLI client, doctor, and live preflight use a unified runtime configuration loader (`src/config/runtime-config-loader.js`) that loads credentials from multiple sources with the following precedence:

1. **Explicit config override** (options.config) — highest priority
2. **process.env** — medium priority
3. **.env.dataarts** — lower priority (parsed without mutating process.env)
4. **Defaults** — lowest priority (e.g., DLI_QUEUE_NAME defaults to "default")

The loader reports a `source_map` identifying where each value came from (`config.js`, `env`, `.env.dataarts`, or `missing`). Secrets (AK/SK) are never exposed in output — only `PRESENT`/`NOT SET` status is shown.

### DLI Client Doctor

```bash
npm run dli:client:doctor
```

Validates config, client interface, and safety policy. No cloud APIs, no SQL execution.

### DLI Client Plan

```bash
npm run dli:client:plan -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

Builds a native runtime plan and creates planned DLI requests for every step. Each golden package produces **15 planned DLI requests** (3 setup + 5 target + 7 validation) plus 1 local equivalence step. No cloud APIs, no SQL execution.

### DLI Client Live Read-Only Preflight

```bash
npm run dli:client:live-preflight -- --dli-queue default --read-only
```

Validates live Huawei Cloud/DLI connectivity and queue accessibility using **read-only API calls only**. The `--read-only` flag is required.

- Calls `GET /v1.0/{project_id}/queues` (read-only) to verify credentials and list queues
- Checks whether the specified queue exists among available queues
- No SQL execution, no job creation, no cloud write calls, no confirm
- If credentials are missing, returns `DLI_LIVE_PREFLIGHT_NOT_CONFIGURED` without attempting any cloud calls
- Secrets (AK/SK) are never exposed in output

### Command comparison

| Command | Purpose | Cloud calls | SQL execution |
|---------|---------|-------------|---------------|
| `dli:client:doctor` | Local config/interface validation | None | No |
| `dli:client:plan` | Request planning only | None | No |
| `dli:client:live-preflight` | Read-only live connectivity/queue check | Read-only GET only | No |
| `dli:transport:plan` | Transport-level HTTP request planning | None | No |
| `dli:submit-job:audit` | Local audit of submit-job request shape | None | No |

### Future work

- Real DLI execution will require explicit confirm guard and validated credentials
- Native-dli CONFIRM mode remains UNSUPPORTED until real execution is implemented

## Native Runtime Plan

The native runtime plan (`runtime:native-plan`) builds a deterministic, package-aware execution plan with four phases:

1. **runtime_setup** — DLI_SQL steps for each `runtime/setup/*.sql` file
2. **target_transform** — DLI_SQL steps for each `target/sql/*.sql` file from the artifact manifest dependency order
3. **runtime_validation** — DLI_QUERY steps for each runtime validation query
4. **equivalence_summary** — LOCAL_COMPARISON step for local result comparison

The plan is local-only. No SQL is executed. No Huawei Cloud APIs are called. The `legacy-demo` adapter remains the only confirm-capable adapter for now.

## Native DLI Simulation

The `native-dli` adapter supports a **SIMULATE** mode that exercises the native runtime plan end-to-end without calling Huawei Cloud or executing SQL:

1. **runtime_setup** — Simulated DLI_SQL steps (no SQL executed)
2. **target_transform** — Simulated DLI_SQL steps (no SQL executed)
3. **runtime_validation** — Simulated DLI_QUERY steps with expected values from `validation_queries.json`
4. **equivalence_summary** — Simulated LOCAL_COMPARISON step

Simulation produces `SIMULATED_EQUIVALENT`, not `EQUIVALENT`. `equivalence_confirmed` is always `false`. This prepares the native-dli adapter for future real DLI execution.

## Native DLI Mock Execution

The `native-dli` adapter supports a **MOCK** mode that exercises the actual executor flow using an injectable mock DLI client:

1. **runtime_setup** — Submit setup SQL via mock `executeSql`
2. **target_transform** — Submit target SQL via mock `executeSql`
3. **runtime_validation** — Submit validation queries via mock `querySql`
4. **equivalence_summary** — Compare mock query results against expected values from `validation_queries.json`

Mock execution produces `MOCK_EQUIVALENT`, not `EQUIVALENT`. `equivalence_confirmed` is always `false`. `real_runtime_confirmed` is always `false`. The DLI client is injectable so tests never touch real cloud.

```bash
npm run runtime:native-execute:mock -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

Or via the migration executor:

```bash
npm run migration:execute -- --mock --adapter native-dli --package-dir cases/golden/orders_pipeline_simple --job-name native_mock_orders --dli-queue default
```

```bash
npm run runtime:native-simulate -- --package-dir cases/golden/orders_pipeline_simple --dli-queue default
```

Or via the migration executor:

```bash
npm run migration:execute -- --simulate --adapter native-dli --package-dir cases/golden/orders_pipeline_simple --job-name native_sim_orders --dli-queue default
```

## Native DLI Guarded Execution

A guarded native DLI execution path exists as a standalone runtime command (`runtime:native-execute:guarded`). Real execution is **not run automatically** and requires explicit guardrail flags.

### Plan-only mode (safe, no SQL execution)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --plan-only
```

Returns `NATIVE_DLI_GUARDED_PLAN_READY` with planned SQL/query counts. No SQL is executed. No cloud write APIs are called.

### Guarded real mode (future, requires all flags)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --allow-real-execution \
  --confirm-native-dli \
  --i-understand-this-executes-sql
```

Real execution requires **all three** explicit flags:
- `--allow-real-execution`
- `--confirm-native-dli`
- `--i-understand-this-executes-sql`

If any flag is missing, execution is blocked before any SQL is submitted. If all flags are present but the real execution implementation is not yet complete, returns `NATIVE_DLI_REAL_EXECUTION_NOT_IMPLEMENTED` — no SQL is executed.

### Guardrail enforcement

The `assertRealDliExecutionAllowed` function in `real-dli-client.js` checks all three flags. The `createRealDliClient` constructor enforces the same guardrails on `executeSql`, `querySql`, `getJobStatus`, and `getJobResult`:
- If `allowRealExecution=true` but other flags are missing, throws a clear guardrail error
- If all flags are present, routes through the DLI HTTP transport layer
- If transport is not configured (no httpClient, no AK/SK), returns `NATIVE_DLI_TRANSPORT_NOT_CONFIGURED`
- If transport httpClient doesn't implement required methods, returns `NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED`

### Real execution flow

When all guardrails pass and transport is configured:

1. **runtime_setup** — Submit setup SQL via `transport.submitSqlJob`, poll status, confirm FINISHED
2. **target_transform** — Submit target SQL via `transport.submitSqlJob`, poll status, confirm FINISHED
3. **runtime_validation** — Submit validation queries via `transport.submitSqlJob`, poll status, fetch results via `transport.getSqlJobResult`
4. **equivalence_summary** — Compare validation results against expected values
5. **Result** — `EQUIVALENT` only if all validations pass; `real_runtime_confirmed: true` only after actual DLI execution and validation pass

### DLI Queue Health Check

```bash
npm run dli:queue:health -- --dli-queue default --read-only
```

Reports DLI queue health including job counts by state (LAUNCHING, RUNNING, FINISHED, FAILED, CANCELLED). The `--read-only` flag is required. This command never cancels jobs, never executes SQL, and never mutates cloud resources.

Safety flags: `read_only`, `no_sql_execution`, `no_job_cancel`, `no_cloud_write_calls`, `no_runtime_execution`, `no_confirm`, `secrets_redacted`.

### Queue Congestion Gate

Before real execution, the guarded executor runs a DLI queue health check. If the number of jobs in LAUNCHING state exceeds the threshold (default: 10), execution is blocked with status `NATIVE_DLI_QUEUE_CONGESTED`. This prevents submitting new SQL jobs when the queue is already congested.

Override the threshold with `--max-launching-jobs <number>`. The congestion gate does **not** apply in plan-only mode.

### Resume Support (--resume-from)

After a partial execution failure, re-running the full setup is wasteful and potentially dangerous if setup is not idempotent. The `--resume-from` option allows skipping already-completed phases.

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --resume-from target_transform \
  --plan-only
```

Allowed values:
- `runtime_setup` (default) — execute all phases
- `target_transform` — skip setup phase (setup already completed)
- `runtime_validation` — skip setup and target phases (setup and target already completed)

Skipped steps are recorded with:
- `status: SKIPPED_RESUME`
- `executed: false`
- `skipped_reason: resume_from`

**Why resume-from is required after partial execution:** If setup has already run successfully (creating databases and tables), re-running it may fail with "already exists" errors or cause data loss if it drops and recreates objects. Do not retry full setup after partial setup success unless setup is idempotent.

### Safety

- **Plan-only:** `plan_only`, `no_sql_execution`, `no_runtime_execution`, `explicit_native_confirm_required`, `understand_executes_sql_required`, `preflight_required`
- **Real mode:** `sql_execution_possible`, `guarded_real_execution`, `explicit_native_confirm_required`, `understand_executes_sql_required`, `preflight_required`
- Both modes: `no_publish`, `no_delete`, `no_update`, `no_overwrite`, `no_schedule_start`
- `migration:execute --confirm --adapter native-dli` remains **unsupported**

### Future work

- Run real guarded execution after manual review of transport plan and preflight results
- Add `--dry-run` flag to guarded real mode for request inspection without execution

## Key Components

| Component | Description |
|-----------|-------------|
| Migration Package | Directory containing `artifact_manifest.json`, pipeline YAML, SQL nodes, and migration config |
| migration:plan | Reads the migration package and produces an execution plan |
| migration:doctor | Validates the package structure, dependencies, and environment readiness |
| migration:prepare-runtime | Prepares runtime artifacts (SQL adaptation, DLI data prep) |
| migration:execute-plan | Dispatches to the selected runtime adapter |
| one-shot runtime | Orchestrates: create-job → reset-data → run-immediate → validate → doctor → equivalence |
| DataArts Factory | Huawei Cloud service that hosts and executes the migrated pipeline |
| DLI | Huawei Cloud Data Lake Insight — executes SQL queries |
| runtime validation | Compares DLI query results against Snowflake expected results |
| equivalence summary | Produces a table of per-object equivalence checks |
| MVP report | Aggregates all evidence into a single CONFIRMED/UNCONFIRMED report |
