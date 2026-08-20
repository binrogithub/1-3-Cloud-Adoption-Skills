# Huawei Cloud migration assessment

Read this file only when the user asks to assess, plan, transform, refactor, or migrate discovered assets.
Verify current Huawei Cloud capabilities and regional availability from official documentation before making
an implementation recommendation.

## Guiding rule

Do not perform a mechanical product-name substitution. Classify each asset by workload behavior, data format,
latency, scale, governance, operational model, and compatibility requirements. One Databricks workspace can map
to several Huawei services.

## Initial candidate mapping

| Databricks concern | Huawei candidates | Validate before selection |
|---|---|---|
| Workflow orchestration, data integration, catalog/governance | DataArts Studio | Connectors, scheduling semantics, lineage, permission model, environment promotion |
| Spark/Hadoop batch processing and open-source ecosystem | MRS | Runtime/component versions, Spark APIs, autoscaling, storage integration, cluster operations |
| Serverless SQL/Spark data-lake workloads | DLI | SQL dialect, Spark compatibility, quotas, networking, supported formats, job packaging |
| Enterprise warehouse, dimensional marts, BI serving | GaussDB(DWS) | SQL compatibility, distribution keys, partitions, workload management, procedures/functions |
| Object storage backing data lakes | OBS | URI rewrite, credentials, encryption, lifecycle, consistency, transfer throughput |

Treat these as candidates, not final destinations. A single job may split into DataArts orchestration plus MRS,
DLI, or DWS execution.

## Assessment sequence

1. Establish scope from `manifest.json` and resolve warnings.
2. Classify tables by format, size, update pattern, managed/external status, sharing protocol, and consumers.
3. Classify code by language, libraries, Spark APIs, Databricks utilities, widgets, secrets, and notebook coupling.
4. Classify workloads by schedule, dependencies, retries, compute type, SLA, streaming/batch behavior, and outputs.
5. Build a compatibility matrix with `compatible`, `refactor`, `redesign`, `retire`, or `blocked` status.
6. Select target services per workload and record the decision rationale and assumptions.
7. Design data transfer, reconciliation, cutover, rollback, security, and observability.
8. Generate transformations only after target choices and acceptance criteria are approved.

## Future skill modules

- Add SQL dialect analysis and Databricks-to-DWS/DLI rewrite rules.
- Add PySpark/notebook compatibility scanning for MRS and DLI.
- Add DataArts workflow generation from job dependency edges.
- Add S3/Delta-to-OBS transfer manifests and Delta conversion policy.
- Add function/procedure conversion with test generation.
- Add permissions, principals, secrets-reference, and network mapping.
- Add reconciliation scripts for row counts, checksums, schemas, and business metrics.
- Add deployment packaging, dry runs, cutover plans, and rollback artifacts.

Never write target resources, start compute, transfer data, rotate credentials, or change production workloads
unless the user explicitly authorizes that migration phase.
