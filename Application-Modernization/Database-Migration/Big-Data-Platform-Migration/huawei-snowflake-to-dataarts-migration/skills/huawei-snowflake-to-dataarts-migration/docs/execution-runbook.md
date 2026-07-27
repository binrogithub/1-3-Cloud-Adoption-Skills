# Execution Runbook

## Phase 1: Discovery
```
snowflake_dataarts_demo_plan({ job_name: "...", artifact_dir: "...", dli_queue: "default" })
snowflake_dataarts_demo_status({ job_name: "..." })
```

## Phase 4: Plan Generation
```
snowflake_dataarts_demo_plan({ job_name: "...", artifact_dir: "..." })
```

## Phase 6: Execution (requires confirm=true)
```
snowflake_dataarts_demo_run({ confirm: true, job_name: "...", artifact_dir: "..." })
# OR async:
snowflake_dataarts_demo_start({ confirm: true, job_name: "...", artifact_dir: "..." })
```

## Phase 7: Validation
```
snowflake_dataarts_demo_status({ job_name: "..." })
snowflake_dataarts_demo_equivalence_summary({ job_name: "..." })
snowflake_dataarts_demo_last_report({ job_name: "..." })
```
