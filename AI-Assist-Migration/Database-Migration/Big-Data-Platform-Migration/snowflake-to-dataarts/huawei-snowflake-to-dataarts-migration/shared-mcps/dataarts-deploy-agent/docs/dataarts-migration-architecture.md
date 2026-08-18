# DataArts Migration Framework — Architecture Guide

## Architecture Overview

The Snowflake-to-DataArts migration framework is a Node.js toolchain that transforms Snowflake Task Graph definitions into Huawei Cloud DataArts Factory job artifacts and validates them through a multi-layer runtime execution system.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Migration Package (Input)                        │
│  source/snowflake_task_graph.sql                                    │
│  target/artifact_manifest.json + target/sql/*.sql                    │
│  validation/validation_plan.json                                     │
│  expected/equivalence_summary_result.json                            │
│  runtime/setup/*.sql + runtime/validation/validation_queries.json    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Migration Framework                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │ Package      │  │ Plan         │  │ Execution Plan         │    │
│  │ Loader       │  │ Builder      │  │ Builder                │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬─────────────┘    │
│         │                 │                      │                   │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────────┴─────────────┐    │
│  │ Package      │  │ Runtime      │  │ Executor                │    │
│  │ Doctor       │  │ Preparer     │  │ (adapter-dispatched)    │    │
│  └──────────────┘  └──────────────┘  └──────────┬─────────────┘    │
│                                                │                   │
└────────────────────────────────────────────────┼───────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Runtime Adapter Layer                            │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ legacy-demo  │  │ native-dli   │  │ koocli   │  │ runtime-  │  │
│  │ adapter      │  │ adapter      │  │ adapter  │  │ engine    │  │
│  │              │  │              │  │          │  │ adapter   │  │
│  │ dry-run: Y  │  │ dry-run: Y  │  │ diag: Y  │  │ dry-run:Y │  │
│  │ confirm: Y  │  │ simulate: Y │  │ exec: N  │  │ confirm:N │  │
│  │              │  │ mock: Y     │  │          │  │           │  │
│  │              │  │ guarded: Y  │  │          │  │           │  │
│  │              │  │ confirm: N  │  │          │  │           │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┘  └───────────┘  │
│         │                 │                                          │
└─────────┼─────────────────┼──────────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌──────────────────┐ ┌────────────────────────────────────────────────┐
│ DataArts Factory │ │ DLI Client Layer                              │
│ (legacy-demo)    │ │                                               │
│                  │ │ ┌──────────────┐  ┌──────────────┐           │
│ - Create Job     │ │ │ HTTP         │  │ Mock DLI     │           │
│ - Run-Immediate  │ │ │ Transport    │  │ Client       │           │
│ - Validate       │ │ │ (guarded)    │  │ (simulation) │           │
│                  │ │ └──────────────┘  └──────────────┘           │
│                  │ │ ┌──────────────┐  ┌──────────────┐           │
│                  │ │ │ Real DLI     │  │ Live         │           │
│                  │ │ │ Client       │  │ Preflight    │           │
│                  │ │ │ (guarded)    │  │ (read-only)  │           │
│                  │ │ └──────────────┘  └──────────────┘           │
└──────────────────┘ └────────────────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Validation & Evidence                            │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │ Equivalence  │  │ Evidence     │  │ Runtime Validation     │    │
│  │ Summary      │  │ Report       │  │ Plan Checker           │    │
│  └──────────────┘  └──────────────┘  └────────────────────────┘    │
│                                                                      │
│  Output: out/batch_assessment_result.json                            │
│          out/batch_validation_result.json                            │
│          out/migration_execute_result.json                           │
│          out/native_dli_guarded_execution_result.json                │
│          out/equivalence_summary_report.md                           │
│          out/runs/<run_id>/                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Module Map

| Module | File | Responsibility |
|--------|------|----------------|
| Package Loader | `src/migration/package-loader.js` | Load and validate migration package structure, artifact manifest, SQL files |
| Package Doctor | `src/migration/package-doctor.js` | Health diagnostics for a migration package |
| Plan Builder | `src/migration/plan-builder.js` | Generate deterministic migration plan from package artifacts |
| Execution Plan Builder | `src/migration/execution-plan-builder.js` | Build execution plan from migration plan |
| Runtime Preparer | `src/migration/runtime-preparer.js` | Prepare runtime artifacts (SQL adaptation, manifest resolution) |
| Executor | `src/migration/executor.js` | Execute migration plan through adapter dispatch |
| Batch Assessor | `src/migration/batch-assessor.js` | Portfolio-level readiness assessment |
| Batch Validator | `src/migration/batch-validator.js` | Portfolio-level dry-run validation |
| MVP Report | `src/migration/mvp-report.js` | MVP status and evidence reporting |
| Runtime Adapter | `src/runtime/adapters/runtime-adapter.js` | Adapter dispatch: routes execution to legacy-demo, native-dli, koocli, or runtime-engine |
| Native Runtime Plan | `src/runtime/native-runtime-plan.js` | Deterministic native DLI runtime plan |
| Native DLI Simulator | `src/runtime/native-dli-simulator.js` | Synthetic local simulation of DLI execution |
| Native DLI Executor | `src/runtime/native-dli-executor.js` | Native DLI execution (mock mode) |
| Native DLI Guarded Executor | `src/runtime/native-dli-guarded-executor.js` | Guarded real DLI execution with triple-flag safety |
| DLI HTTP Transport | `src/runtime/dli/dli-http-transport.js` | Guarded HTTP transport for DLI API calls |
| DLI Client Interface | `src/runtime/dli/dli-client-interface.js` | DLI client abstraction (mock vs real) |
| Mock DLI Client | `src/runtime/dli/mock-dli-client.js` | Mock DLI client for simulation/testing |
| Real DLI Client | `src/runtime/dli/real-dli-client.js` | Real DLI client for guarded execution |
| DLI Client Doctor | `src/runtime/dli/dli-client-doctor.js` | DLI client configuration diagnostics |
| DLI Live Preflight | `src/runtime/dli/dli-live-preflight.js` | Read-only live DLI queue/config check |
| Runtime Validation Plan Checker | `src/runtime/runtime-validation-plan-checker.js` | Validate runtime execution results against validation plan |
| Runtime Engine | `src/runtime/runtime-engine.js` | Core runtime execution engine |
| Runtime Package Loader | `src/runtime/runtime-package-loader.js` | Load runtime-specific package artifacts |
| Config | `src/config.js` | Load `.env.dataarts`, mask secrets, validate configuration |
| Huawei Signer | `src/huawei-signer.js` | Huawei Cloud API request signing |

---

## Command Map

| Command | Script | Safety | Cloud Access |
|---------|--------|--------|--------------|
| `npm test` | `node --test test/**/*.test.js` | Safe | None |
| `npm run migration:plan` | `src/migration-plan.js` | Safe | None |
| `npm run migration:doctor` | `src/migration-doctor.js` | Safe | None |
| `npm run migration:prepare-runtime` | `src/migration-prepare-runtime.js` | Safe | None |
| `npm run migration:execute-plan` | `src/migration-execute-plan.js` | Safe | None |
| `npm run migration:execute -- --dry-run` | `src/migration-execute.js` | Safe | None |
| `npm run migration:execute -- --confirm --adapter legacy-demo` | `src/migration-execute.js` | **Creates resources** | DataArts Factory API |
| `npm run migration:batch-assess` | `src/migration-batch-assess.js` | Safe | None |
| `npm run migration:batch-validate` | `src/migration-batch-validate.js` | Safe | None |
| `npm run runtime:native-plan` | `src/runtime-native-plan.js` | Safe | None |
| `npm run runtime:native-simulate` | `src/runtime-native-simulate.js` | Safe | None |
| `npm run runtime:native-execute:mock` | `src/runtime-native-execute-mock.js` | Safe | None |
| `npm run runtime:native-execute:guarded -- --plan-only` | `src/runtime-native-execute-guarded.js` | Safe | None |
| `npm run runtime:native-execute:guarded -- (triple flag)` | `src/runtime-native-execute-guarded.js` | **Executes SQL** | DLI API |
| `npm run dli:client:doctor` | `src/dli-client-doctor.js` | Safe | None |
| `npm run dli:client:plan` | `src/dli-client-plan.js` | Safe | None |
| `npm run dli:client:live-preflight -- --read-only` | `src/dli-client-live-preflight.js` | Safe | Read-only queue metadata |
| `npm run dli:transport:plan` | `src/dli-transport-plan.js` | Safe | None |
| `npm run koocli:doctor` | `src/koocli-doctor.js` | Safe | None |

---

## Adapter Strategy

### Adapter Dispatch

The runtime adapter (`src/runtime/adapters/runtime-adapter.js`) dispatches execution to one of four adapters based on the `--adapter` flag:

```
--adapter legacy-demo    →  legacy-demo adapter  (one-shot runtime wrapper)
--adapter native-dli     →  native-dli adapter   (native DLI execution)
--adapter koocli         →  koocli adapter       (diagnostic only)
--adapter runtime-engine →  runtime-engine adapter (dry-run planning)
```

### Adapter Comparison

| Feature | legacy-demo | native-dli | koocli | runtime-engine |
|---------|-------------|------------|--------|----------------|
| Dry-run | Yes | Yes | No | Yes |
| Confirm | Yes | **No** | No | No |
| Simulate | No | Yes | No | No |
| Mock | No | Yes | No | No |
| Guarded execution | No | Yes | No | No |
| DataArts job creation | Yes (confirm) | No | No | No |
| DLI SQL execution | Yes (confirm) | Yes (guarded) | No | No |
| Read-only by default | Yes (dry-run) | Yes (dry-run/simulate/mock) | Yes | Yes |

### When to Use Each Adapter

- **legacy-demo**: For full end-to-end validation with DataArts Factory job creation. This is the MVP-confirmed path.
- **native-dli**: For controlled DLI execution without DataArts Factory. Use for SQL validation and incremental testing.
- **koocli**: For diagnostic checks and future KooCLI-based command planning.
- **runtime-engine**: For dry-run command planning compatible with the legacy runtime.

---

## Package Lifecycle

```
1. Create package directory
   cases/golden/<migration_id>/

2. Add source artifacts
   source/snowflake_task_graph.sql

3. Add target artifacts
   target/artifact_manifest.json
   target/sql/*.sql  (one statement per file)

4. Add validation plan
   validation/validation_plan.json

5. Add expected results
   expected/equivalence_summary_result.json

6. Add runtime artifacts
   runtime/setup/*.sql
   runtime/validation/validation_queries.json

7. Validate package
   npm run migration:doctor -- --package-dir cases/golden/<migration_id>

8. Batch assess
   npm run migration:batch-assess -- --packages-dir cases/golden

9. Batch validate
   npm run migration:batch-validate -- --packages-dir cases/golden --adapter legacy-demo --dli-queue default
```

---

## Runtime Lifecycle

```
1. Plan
   npm run migration:plan -- --package-dir <dir>
   → Produces deterministic migration plan

2. Doctor
   npm run migration:doctor -- --package-dir <dir>
   → Validates package health

3. Prepare Runtime
   npm run migration:prepare-runtime -- --package-dir <dir>
   → Adapts SQL, resolves artifacts

4. Execute Plan
   npm run migration:execute-plan -- --package-dir <dir>
   → Executes the migration plan steps

5. Execute (dry-run)
   npm run migration:execute -- --dry-run --adapter legacy-demo --package-dir <dir> --job-name <name> --dli-queue <queue>
   → Full dry-run, no cloud writes

6. Execute (confirm) — legacy-demo only
   npm run migration:execute -- --confirm --adapter legacy-demo --package-dir <dir> --job-name <name> --dli-queue <queue>
   → Creates DataArts job, runs, validates

7. Native Plan
   npm run runtime:native-plan -- --package-dir <dir> --dli-queue <queue>
   → Deterministic native runtime plan

8. Native Simulate
   npm run runtime:native-simulate -- --package-dir <dir> --dli-queue <queue>
   → Synthetic simulation

9. Native Mock
   npm run runtime:native-execute:mock -- --package-dir <dir> --dli-queue <queue>
   → Mock DLI client execution

10. Native Guarded (plan-only)
    npm run runtime:native-execute:guarded -- --package-dir <dir> --dli-queue <queue> --plan-only
    → Plan only, no execution

11. Native Guarded (real execution)
    npm run runtime:native-execute:guarded -- --package-dir <dir> --dli-queue <queue> --allow-real-execution --confirm-native-dli --i-understand-this-executes-sql
    → Real DLI SQL execution (controlled)
```

---

## Validation Lifecycle

```
1. Package structural validation
   migration:doctor → artifact manifest, SQL files, validation plan

2. Batch assessment
   migration:batch-assess → portfolio readiness report

3. Batch dry-run validation
   migration:batch-validate → plan + doctor + prepare + execute-plan + dry-run

4. DLI client validation
   dli:client:doctor → config and interface check

5. DLI live preflight
   dli:client:live-preflight --read-only → queue accessibility

6. DLI transport planning
   dli:transport:plan → transport-level request plans

7. Runtime execution validation
   After execution: equivalence summary + evidence report

8. Equivalence comparison
   demo:equivalence-summary → Snowflake expected vs DataArts/DLI actual
```

---

## Safety Controls

### Layer 1: Default Dry-Run

All execution commands default to dry-run mode. No `--confirm` flag means no cloud writes.

### Layer 2: Adapter Blocking

The `native-dli` adapter blocks `--confirm` through `migration:execute`. This prevents accidental real execution through the standard command path.

### Layer 3: Triple-Flag Guard

Real DLI execution through the guarded executor requires three explicit flags:

```
--allow-real-execution
--confirm-native-dli
--i-understand-this-executes-sql
```

All three must be present. Missing any one blocks execution.

### Layer 4: Secret Masking

AK/SK are always masked to the last 4 characters in all output, reports, and logs.

### Layer 5: Gitignore

`.env.dataarts` and `out/` are gitignored. Generated files and credentials cannot be committed.

### Layer 6: Read-Only Preflight

`dli:client:live-preflight` requires `--read-only` flag. This ensures the preflight check cannot be used for write operations.

---

## Current Limitations

| Limitation | Details |
|------------|---------|
| `native-dli` confirm blocked | `migration:execute --confirm --adapter native-dli` is unsupported |
| `customer_status_pipeline_simple` not runtime-confirmed | Package/dry-run/native validated, but no end-to-end with DataArts Factory yet |
| `koocli` adapter is diagnostic only | No DataArts/DLI execution through KooCLI |
| Single-statement SQL only | Each SQL file must contain exactly one statement |
| No Snowflake discovery layer | Source packages must be manually created |
| No SQL compatibility scoring | No automated classification of Snowflake-to-DLI SQL compatibility |
| No DWS runtime support | MERGE/incremental workloads not yet supported |
| No batch execution policy | No automated batch execution with retry/rollback |
| legacy-demo confirm creates DataArts jobs | Job name collisions possible if non-unique names are used |
| Guarded execution has no partial rollback | If execution fails partway, manual cleanup may be needed |

---

## Roadmap

| Priority | Item | Description |
|----------|------|-------------|
| 1 | First controlled native DLI guarded real execution | Execute `customer_status_pipeline_simple` through the guarded path under controlled conditions |
| 2 | Native DLI real execution evidence report | Generate full evidence report from guarded execution results |
| 3 | Promote native-dli confirm | Enable `migration:execute --confirm --adapter native-dli` only after guarded path proves stable |
| 4 | Snowflake discovery layer | Automated Snowflake task graph discovery and package generation |
| 5 | SQL classification and compatibility scoring | Automated Snowflake-to-DLI SQL compatibility analysis |
| 6 | DWS runtime support | Add DWS adapter for MERGE/incremental workloads |
| 7 | Batch migration execution policy | Automated batch execution with retry, rollback, and progress tracking |
