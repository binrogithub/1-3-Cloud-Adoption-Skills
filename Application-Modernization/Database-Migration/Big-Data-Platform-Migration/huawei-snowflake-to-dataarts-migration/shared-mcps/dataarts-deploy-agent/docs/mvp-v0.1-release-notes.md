# Migration Framework MVP v0.1 — Release Notes

**Release Date:** 2026-06-26
**Branch:** `refactor/migration-core-v0.1`
**Commit:** `eba5b81`
**Status:** CONFIRMED

## MVP Name

Migration Framework MVP v0.1

## Scope

Snowflake Task Graph → Huawei Cloud DataArts Factory + DLI

## Validated Packages

| Package | Status | Source Pattern | Runtime Confirmed |
|---------|--------|----------------|-------------------|
| `cases/golden/orders_pipeline_simple` | runtime-confirmed | MERGE (upsert) | Yes |
| `cases/golden/customer_status_pipeline_simple` | package/dry-run validated | INSERT INTO SELECT (non-upsert) | No |

## Execution Command Path

```
npm run migration:execute -- --confirm --adapter legacy-demo --package-dir cases/golden/orders_pipeline_simple --job-name <unique_job_name> --dli-queue default
```

## Runtime Adapter

`legacy-demo`

## Evidence Summary

| Field | Value |
|-------|-------|
| Job Name | `orders_pipeline_framework_v02_20260626123934` |
| Migration Run ID | `run_20260626173934._95b6bf9b` |
| Runtime Run ID | `run_20260626173934._669f05b1` |
| DataArts Instance ID | `1332281` |
| Runtime Validation | PASS |
| Final Equivalence | EQUIVALENT |
| Doctor | Healthy (Findings: 0, Warnings: 0) |
| Stale Result | No |
| Tests | 159/159 pass |
| MVP Report | CONFIRMED |

## Safety Controls

| Control | Description |
|---------|-------------|
| No publish | Jobs are not published after creation |
| No scheduled start | No cron/schedule is configured |
| No delete | No delete operations are performed |
| No update | Existing jobs are not updated |
| No overwrite | Existing resources are not overwritten |
| Run-immediate only | Job is triggered via run-immediate only |
| Abort if job exists | Execution aborts if a job with the same name already exists |
| Stale result protection | Stale results from prior runs are detected and reported |

## Known Limitations

- `customer_status_pipeline_simple` is package/dry-run validated but not runtime-confirmed yet
- DLI full-refresh is demo-safe only, not a universal MERGE replacement
- `legacy-demo` adapter still wraps one-shot runtime
- Native `runtime-engine` confirm not implemented (dry-run only)
- KooCLI is diagnostic/future adapter only
- Snowflake discovery not automated yet
- DWS/CDM/OBS/Lineage not implemented

## Next Roadmap

1. Runtime-confirm `customer_status_pipeline_simple`
2. Batch package assessment
3. Native runtime-engine confirm
4. KooCLI DataArts API mapping
5. Snowflake discovery
6. DWS support for MERGE/incremental workloads
