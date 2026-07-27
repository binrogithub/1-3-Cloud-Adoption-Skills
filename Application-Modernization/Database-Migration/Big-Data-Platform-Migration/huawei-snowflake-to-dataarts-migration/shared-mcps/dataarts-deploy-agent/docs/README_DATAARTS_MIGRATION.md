# Snowflake to Huawei DataArts Migration Framework

## What This Tool Does

This framework converts **Snowflake Task Graph migration packages** into **Huawei Cloud DataArts Factory/DLI runtime artifacts**.

It supports the full migration lifecycle:

- **Package validation** — structural and manifest checks on migration packages
- **Planning** — deterministic migration plan generation from package artifacts
- **Dry-run validation** — full plan execution without touching cloud resources
- **Batch assessment** — portfolio-level readiness report across all golden packages
- **Batch validation** — full dry-run validation across all golden packages
- **DLI preflight** — read-only live queue and configuration checks
- **Native DLI planning** — deterministic native runtime plan for DLI execution
- **Simulation** — synthetic local simulation of the native DLI execution path
- **Mock execution** — executor flow using a mock DLI client
- **Guarded execution** — real DLI path behind explicit guardrails and triple-flag confirmation

The tool is designed to migrate:

- **Orchestration logic** — Snowflake task graph DAG structure to DataArts Factory job topology
- **SQL transformation flow** — Snowflake SQL to DLI-compatible SQL with single-statement adaptation
- **Runtime evidence** — execution results, equivalence summaries, and validation reports
- **Validation workflows** — setup SQL, validation queries, and expected equivalence results

---

## Current Maturity

| Aspect | Status |
|--------|--------|
| MVP tag | `mvp-v0.1-snowflake-dataarts` confirmed |
| `orders_pipeline_simple` | Runtime-confirmed through `legacy-demo` adapter (full end-to-end with DataArts job creation and DLI result validation) |
| `customer_status_pipeline_simple` | Package/dry-run/native-plan/simulate/mock validated; not yet runtime-confirmed |
| `native-dli` real execution path | Guarded but should only be run under controlled conditions |
| `migration:execute --confirm --adapter native-dli` | **Unsupported** — blocked by design |
| `legacy-demo` adapter | Currently the only real confirm-capable path |
| `native-dli` adapter | Supports `DRY_RUN`, `SIMULATE`, `MOCK`, and guarded runtime command path |
| Test suite | 508/508 passing |

---

## Architecture

```
Migration Package
  │
  ├─► migration:plan          → deterministic migration plan
  ├─► migration:doctor        → package health check
  ├─► migration:prepare-runtime → prepare runtime artifacts
  ├─► migration:execute-plan  → execute the migration plan
  │
  └─► Runtime Adapter
        │
        ├─► legacy-demo adapter
        │     └─► wraps original validated one-shot runtime
        │           └─► DataArts Factory job creation + run-immediate
        │
        ├─► native-dli adapter
        │     ├─► DRY_RUN    → deterministic native runtime plan
        │     ├─► SIMULATE   → synthetic local simulation
        │     ├─► MOCK       → executor flow using mock DLI client
        │     └─► guarded    → real DLI path behind explicit guardrails
        │
        ├─► koocli adapter
        │     └─► diagnostic / future command planning
        │
        └─► runtime-engine adapter
              └─► dry-run legacy-compatible command planning

  └─► DLI / DataArts runtime
        │
        └─► runtime validation
              ├─► equivalence summary
              └─► evidence report
```

### Native DLI Execution Modes

```
native-dli DRY_RUN
  └─► Produces a deterministic native runtime plan
      No SQL executed. No cloud calls.

native-dli SIMULATE
  └─► Produces synthetic local simulation
      No SQL executed. No cloud calls.

native-dli MOCK
  └─► Runs executor flow using mock DLI client
      No SQL executed. No cloud calls.

native-dli guarded execution
  └─► Real DLI path behind explicit guardrails
      Requires three explicit flags:
        --allow-real-execution
        --confirm-native-dli
        --i-understand-this-executes-sql
      Executes real SQL. Controlled use only.
```

---

## Repository Layout

```
dataarts-deploy-agent/
├── cases/golden/                    Golden migration packages
│   ├── orders_pipeline_simple/      Runtime-confirmed MVP package
│   │   ├── source/                  Original Snowflake artifacts
│   │   │   └── snowflake_task_graph.sql
│   │   ├── target/                  DataArts migration artifacts
│   │   │   ├── artifact_manifest.json
│   │   │   └── sql/*.sql            DLI-compatible SQL scripts
│   │   ├── validation/
│   │   │   └── validation_plan.json
│   │   ├── expected/
│   │   │   └── equivalence_summary_result.json
│   │   └── runtime/
│   │       ├── setup/*.sql          Setup SQL for demo data
│   │       └── validation/validation_queries.json
│   └── customer_status_pipeline_simple/
│       └── (same structure)
├── src/
│   ├── migration/                   Migration framework core
│   │   ├── package-loader.js        Load and validate migration packages
│   │   ├── package-doctor.js        Package health diagnostics
│   │   ├── plan-builder.js          Migration plan generation
│   │   ├── execution-plan-builder.js
│   │   ├── runtime-preparer.js      Prepare runtime artifacts
│   │   ├── executor.js              Migration execution engine
│   │   ├── batch-assessor.js        Portfolio batch assessment
│   │   ├── batch-validator.js       Portfolio batch validation
│   │   └── mvp-report.js            MVP status reporting
│   ├── runtime/                     Runtime execution layer
│   │   ├── adapters/
│   │   │   └── runtime-adapter.js   Adapter dispatch (legacy-demo, native-dli, koocli, runtime-engine)
│   │   ├── dli/                     DLI client layer
│   │   │   ├── dli-client-interface.js
│   │   │   ├── dli-http-transport.js  Guarded HTTP transport
│   │   │   ├── dli-client-doctor.js
│   │   │   ├── dli-live-preflight.js
│   │   │   ├── mock-dli-client.js
│   │   │   └── real-dli-client.js
│   │   ├── native-dli-executor.js
│   │   ├── native-dli-guarded-executor.js
│   │   ├── native-dli-simulator.js
│   │   ├── native-runtime-plan.js
│   │   ├── runtime-engine.js
│   │   └── runtime-validation-plan-checker.js
│   └── (CLI entry points for each npm script)
├── docs/                            Architecture and release docs
├── test/                            Test suite (508 tests)
├── out/                             Generated output (gitignored)
├── .env.dataarts                    Credentials (gitignored)
└── package.json
```

### Key Package Files

| Path | Purpose |
|------|---------|
| `source/snowflake_task_graph.sql` | Original Snowflake task graph definition |
| `target/artifact_manifest.json` | DataArts artifact manifest (nodes, edges, SQL refs) |
| `target/sql/*.sql` | DLI-compatible SQL scripts (one statement per file) |
| `validation/validation_plan.json` | Validation plan for equivalence checking |
| `expected/equivalence_summary_result.json` | Expected results for equivalence comparison |
| `runtime/setup/*.sql` | Setup SQL for initializing demo data |
| `runtime/validation/validation_queries.json` | Queries for runtime result validation |

---

## Installation

```bash
cd dataarts-deploy-agent
npm install
npm test
```

Expected: 508/508 tests pass.

---

## Configuration

Create `.env.dataarts` in the `dataarts-deploy-agent/` directory:

```bash
HUAWEI_REGION=
HUAWEI_PROJECT_ID=
HUAWEI_AK=
HUAWEI_SK=
DATAARTS_WORKSPACE_ID=
DLI_QUEUE_NAME=default
```

### Configuration Rules

- **`.env.dataarts` must never be committed.** It is listed in `.gitignore`.
- **AK/SK are masked in all reports.** Only the last 4 characters are ever displayed (e.g., `***abcd`).
- **`process.env` overrides `.env.dataarts`.** If you set environment variables in your shell, they take precedence.
- **`.env.dataarts` is used by both legacy and native DLI tooling.** The same credential file supports all adapters.

---

## Safe First Commands

These commands are **safe** — they do not execute SQL, do not create cloud resources, and do not require `--confirm`.

### 1. Run the test suite

```bash
npm test
```

Runs 508 unit/integration tests. No cloud access. No SQL.

### 2. Batch assessment

```bash
npm run migration:batch-assess -- --packages-dir cases/golden
```

Produces a portfolio readiness report for all golden packages. Local only. No SQL. No runtime.

### 3. Batch validation

```bash
npm run migration:batch-validate -- \
  --packages-dir cases/golden \
  --adapter legacy-demo \
  --dli-queue default
```

Full local dry-run validation across all packages. Runs plan, doctor, prepare-runtime, execute-plan, and execute dry-run. No confirm. No SQL.

### 4. DLI client doctor

```bash
npm run dli:client:doctor
```

Validates local configuration and DLI client interface. No cloud calls unless credentials are configured.

### 5. DLI live preflight

```bash
npm run dli:client:live-preflight -- \
  --dli-queue default \
  --read-only
```

Read-only check of DLI queue accessibility and configuration. Requires `--read-only`. No SQL. Touches cloud only for read-only queue metadata queries.

---

## Single Package Workflow

### orders_pipeline_simple (Runtime-Confirmed MVP)

```bash
# Step 1: Package health check
npm run migration:doctor -- \
  --package-dir cases/golden/orders_pipeline_simple

# Step 2: Prepare runtime artifacts
npm run migration:prepare-runtime -- \
  --package-dir cases/golden/orders_pipeline_simple

# Step 3: Dry-run execution
npm run migration:execute -- \
  --dry-run \
  --adapter legacy-demo \
  --package-dir cases/golden/orders_pipeline_simple \
  --job-name test_orders_dryrun \
  --dli-queue default
```

This is the safe path. The `--dry-run` flag ensures no DataArts job is created and no SQL is executed.

### customer_status_pipeline_simple (Package/Dry-Run/Native Validated)

```bash
# Step 1: Package health check
npm run migration:doctor -- \
  --package-dir cases/golden/customer_status_pipeline_simple

# Step 2: Native DLI plan (deterministic, no cloud calls)
npm run runtime:native-plan -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default

# Step 3: Native DLI simulate (synthetic, no cloud calls)
npm run runtime:native-simulate -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default

# Step 4: Native DLI mock execution (mock client, no cloud calls)
npm run runtime:native-execute:mock -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default
```

---

## Adapter Explanation

### legacy-demo

| Capability | Supported |
|------------|-----------|
| `--dry-run` | Yes |
| `--confirm` | Yes |
| Real execution | Yes (wraps original validated one-shot runtime) |
| DataArts job creation | Yes (when `--confirm` is used) |
| DLI result validation | Yes (when `--confirm` is used) |

The `legacy-demo` adapter wraps the original validated one-shot runtime that confirmed the MVP. It is the only adapter that supports `--confirm` for real execution. When `--confirm` is used, it creates a DataArts Factory job and triggers run-immediate.

**Caution:** `--confirm` with `legacy-demo` creates real DataArts jobs. Always use unique job names and dry-run first.

### native-dli

| Capability | Supported |
|------------|-----------|
| `--dry-run` | Yes |
| `--simulate` | Yes |
| `--mock` | Yes |
| Guarded execution | Yes (requires triple flag) |
| `--confirm` via `migration:execute` | **No — blocked by design** |

The `native-dli` adapter provides a controlled path to real DLI execution through the guarded executor. It does not support `--confirm` through the standard `migration:execute` command.

### koocli

| Capability | Supported |
|------------|-----------|
| Diagnostic | Yes |
| Future command planning | Yes |
| DataArts/DLI execution | **No** — current implementation is diagnostic only |

The `koocli` adapter is a diagnostic and planning adapter for future KooCLI-based execution. It does not execute DataArts or DLI operations.

### runtime-engine

| Capability | Supported |
|------------|-----------|
| `--dry-run` | Yes (legacy-compatible command planning) |

The `runtime-engine` adapter provides dry-run legacy-compatible command planning.

---

## Batch Commands

### migration:batch-assess

```bash
npm run migration:batch-assess -- --packages-dir cases/golden
```

- Produces a **portfolio readiness report** for all migration packages in the given directory.
- **Local assessment only** — no SQL, no runtime, no cloud calls.
- Output: `out/batch_assessment_result.json`

### migration:batch-validate

```bash
npm run migration:batch-validate -- \
  --packages-dir cases/golden \
  --adapter legacy-demo \
  --dli-queue default
```

- Runs **full local dry-run validation** for each package.
- Executes: plan, doctor, prepare-runtime, execute-plan, execute dry-run.
- **No confirm.** No SQL. No cloud writes.
- Output: `out/batch_validation_result.json`

---

## DLI Client Commands

### dli:client:doctor

```bash
npm run dli:client:doctor
```

Validates local configuration and DLI client interface. Checks that `.env.dataarts` is present and contains required variables. No cloud calls.

### dli:client:plan

```bash
npm run dli:client:plan -- \
  --package-dir cases/golden/orders_pipeline_simple \
  --dli-queue default
```

Produces 15 DLI request plans for the package. Request planning only — no SQL, no cloud calls.

### dli:client:live-preflight

```bash
npm run dli:client:live-preflight -- \
  --dli-queue default \
  --read-only
```

Read-only live check of DLI queue accessibility and configuration. Requires `--read-only` flag. No SQL execution. Touches cloud for read-only queue metadata only.

### dli:transport:plan

```bash
npm run dli:transport:plan -- \
  --package-dir cases/golden/orders_pipeline_simple \
  --dli-queue default
```

Transport-level request planning. No SQL. No cloud calls.

---

## Native Guarded Execution

> **ADVANCED / CONTROLLED USE ONLY**

The guarded execution path provides access to real DLI execution behind explicit guardrails. It requires three confirmation flags to prevent accidental execution.

### Plan-Only (Safe)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --plan-only
```

This produces the execution plan without running anything. **Safe — no SQL executed.**

### Real Execution (Controlled Only)

```bash
npm run runtime:native-execute:guarded -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default \
  --allow-real-execution \
  --confirm-native-dli \
  --i-understand-this-executes-sql
```

### Warnings

- **This executes real SQL on DLI.**
- Use **only after** doctor, live-preflight, transport-plan, and plan-only all pass.
- **Do not run without owner approval.**
- **Do not retry blindly after partial execution.** If SQL partially executes and fails, re-running may produce incorrect results due to partial state.
- **Do not use `migration:execute --confirm --adapter native-dli`.** This path is blocked by design. Use the guarded executor instead.

---

## Evidence Outputs

All output is written to `out/` (gitignored). These files are generated at runtime and should never be committed.

| File | Produced By | Description |
|------|-------------|-------------|
| `out/batch_assessment_result.json` | `migration:batch-assess` | Portfolio readiness report |
| `out/batch_validation_result.json` | `migration:batch-validate` | Full dry-run validation results |
| `out/migration_execute_result.json` | `migration:execute` | Single package execution result |
| `out/dli_client_plan_result.json` | `dli:client:plan` | DLI request plans |
| `out/native_dli_guarded_execution_result.json` | `runtime:native-execute:guarded` | Guarded execution result |
| `out/runs/<run_id>/` | Demo/one-shot commands | Per-run evidence directory |
| `out/equivalence_summary_report.md` | `demo:equivalence-summary` | Human-readable equivalence table |
| `out/equivalence_summary_result.json` | `demo:equivalence-summary` | Machine-readable equivalence result |

---

## Safety Model

| Rule | Details |
|------|---------|
| No secrets printed | AK/SK are always masked to last 4 characters |
| No `.env.dataarts` commit | Listed in `.gitignore` — never stage or push |
| No confirm by default | All execution commands require explicit `--confirm` or `--dry-run` |
| `--dry-run` / `--simulate` / `--mock` are safe | No SQL, no cloud writes, no job creation |
| `native-dli` confirm is blocked | `migration:execute --confirm --adapter native-dli` is unsupported |
| Guarded execution requires three flags | `--allow-real-execution --confirm-native-dli --i-understand-this-executes-sql` |
| `legacy-demo` confirm creates DataArts jobs | Use unique job names to avoid collisions |
| No blind retry after partial failure | If SQL or job creation partially executes, investigate before retrying |
| No `out/` commit | All generated output is gitignored |

---

## How to Add a New Migration Package

Create a new directory under `cases/golden/` with this structure:

```
cases/golden/<migration_id>/
├── source/
│   └── snowflake_task_graph.sql       Original Snowflake task graph
├── target/
│   ├── artifact_manifest.json         DataArts artifact manifest
│   └── sql/
│       ├── node_01.sql                DLI SQL for node 1
│       ├── node_02.sql                DLI SQL for node 2
│       └── ...                        One SQL file per node
├── validation/
│   └── validation_plan.json           Validation plan
├── expected/
│   └── equivalence_summary_result.json  Expected equivalence results
└── runtime/
    ├── setup/
    │   ├── setup_01.sql               Setup SQL step 1
    │   └── ...                        One SQL file per setup step
    └── validation/
        └── validation_queries.json    Runtime validation queries
```

### Rules

- **Every SQL file must be single-statement.** The framework processes one statement per file.
- **`artifact_manifest.json`** must list all nodes with their SQL file references and dependencies.
- **`validation_plan.json`** must define the validation checks for equivalence comparison.
- **`equivalence_summary_result.json`** must define the expected results.
- After creating the package, validate it:

```bash
npm run migration:doctor -- --package-dir cases/golden/<migration_id>
npm run migration:batch-assess -- --packages-dir cases/golden
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `npm run <command>` fails from repo root | `cd dataarts-deploy-agent` — all commands must run from this directory |
| DLI doctor reports missing config | Check that `.env.dataarts` exists and contains all required variables |
| Live preflight reports not configured | Missing `HUAWEI_REGION`, `HUAWEI_AK`, `HUAWEI_SK`, or `HUAWEI_PROJECT_ID` in `.env.dataarts` |
| Queue inaccessible | Verify the DLI queue name and that your account has DLI permissions |
| Dry-run fails with missing artifacts | Run `migration:prepare-runtime` before `migration:execute` |
| `out/` or `.env.dataarts` appear in git status | These are gitignored — do not stage them. Run `git reset HEAD out/ .env.dataarts` if accidentally staged |
| `migration:execute --confirm --adapter native-dli` fails | This path is blocked by design. Use `runtime:native-execute:guarded` with the three required flags |
| Test failure after adding a package | Ensure `artifact_manifest.json` is valid and all referenced SQL files exist |

---

## Quickstart for Teammates (10 Minutes)

This quickstart gets you from zero to a validated migration package in 10 minutes, without executing any SQL or creating any cloud resources.

```bash
# 1. Enter the tool directory
cd dataarts-deploy-agent

# 2. Install dependencies
npm install

# 3. Run the test suite (should show 508/508 passing)
npm test

# 4. Run batch assessment (local, no cloud)
npm run migration:batch-assess -- --packages-dir cases/golden

# 5. Run batch validation (local dry-run, no cloud)
npm run migration:batch-validate -- \
  --packages-dir cases/golden \
  --adapter legacy-demo \
  --dli-queue default

# 6. Check a single package
npm run migration:doctor -- \
  --package-dir cases/golden/orders_pipeline_simple

# 7. Dry-run a single package
npm run migration:execute -- \
  --dry-run \
  --adapter legacy-demo \
  --package-dir cases/golden/orders_pipeline_simple \
  --job-name my_first_dryrun \
  --dli-queue default

# 8. Explore the native DLI path (safe)
npm run runtime:native-plan -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default

npm run runtime:native-simulate -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default

npm run runtime:native-execute:mock -- \
  --package-dir cases/golden/customer_status_pipeline_simple \
  --dli-queue default

# 9. (Optional) If you have .env.dataarts configured:
npm run dli:client:doctor

npm run dli:client:live-preflight -- \
  --dli-queue default \
  --read-only
```

**You have now validated the migration framework without executing any SQL or creating any cloud resources.**

Next steps:
- Read the architecture guide: `docs/dataarts-migration-architecture.md`
- Add your own migration packages under `cases/golden/`
- For real execution, coordinate with the team owner for `--confirm` access
