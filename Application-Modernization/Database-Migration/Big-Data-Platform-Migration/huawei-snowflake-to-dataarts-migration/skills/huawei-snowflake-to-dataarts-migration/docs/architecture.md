# Architecture: Snowflake to DataArts Migration

## Overview

Migration of data pipelines and SQL workloads from Snowflake to Huawei Cloud DataArts (Factory + DLI).

## Architecture

```
Snowflake ──manual──> Artifacts ──dataarts-deploy-agent──> DataArts Factory + DLI
                          │                                        │
                    SQL files                               Adapted SQL
                    Manifest                                Factory Jobs
                    Expected results                        DLI Tables
```

## Adapters

| Adapter | Description | Status |
|---|---|---|
| legacy-demo | Original demo adapter | Available |
| native-dli | Direct DLI execution | Available |
| koocli | KooCLI-based execution | Available |
| runtime-engine | Runtime engine adapter | Available |

## Golden Packages

| Package | Status |
|---|---|
| orders_pipeline_simple | Runtime-confirmed |
| customer_status_pipeline_simple | Package/dry-run validated |

## Limitations

- Only demo/POC flow supported
- Snowflake extraction is manual
- No incremental migration
