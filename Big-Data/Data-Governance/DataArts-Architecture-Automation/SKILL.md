---
name: dataarts-architecture-automation
description: Automate Huawei Cloud DataArts Studio DataArts Architecture metadata creation from source tables, CSVs, SQL DDL, catalog exports, or business descriptions. Use when Codex needs to infer domains, subjects, standards, code tables, table models, dimensions, summary tables, atomic metrics, derivative metrics, compound metrics, or business/service indicators and create them through official DataArts Architecture APIs.
---

# DataArts Architecture Automation

## Core Rule

Use only official Huawei Cloud DataArts Studio APIs for DataArts Architecture writes. Do not use undocumented console endpoints. Always perform read/list probes before create calls, make every operation idempotent, and write a machine-readable report with created/reused IDs.

## Workflow

1. Build context from available source artifacts:
   - SQL DDL, database metadata, CSV headers, JSON schema, DataArts exports, BI metric lists, data dictionaries, or business scenario docs.
   - Identify entities, lookup/code domains, dimensions, facts, summary tables, technical metrics, and business metrics.
2. Read `references/api-map.md` before calling APIs.
3. Read `references/inference-guide.md` when source semantics are ambiguous or metric logic must be inferred.
4. Create or reuse dependencies in this order:
   - Model workspaces
   - Directories
   - Topics/subjects
   - Data standards
   - Code/lookup tables
   - Table models
   - Dimensions
   - Summary tables
   - Atomic metrics
   - Derivative metrics
   - Compound metrics
   - Business metrics/service indicators
5. For every object type:
   - List existing objects first.
   - Match by stable English name/code and display name.
   - Create only missing objects.
   - Re-list and verify read-back.
   - Save returned IDs for downstream objects.
6. If a write fails with a validation error, adapt to the workspace constraint rather than forcing the payload:
   - Prefix rules are common for model and summary table names.
   - Some fields require numeric DataArts IDs even when the UI label is shown in docs.
   - Draft subjects may not be valid anchors for dimensions or tables; prefer published subject IDs.

## Reusable Driver

Use `scripts/dataarts_architecture_driver.py` as a starting point for new automations. It provides:

- IAM token authentication from environment variables or a credentials file
- DataArts GET/POST helpers with retry
- list-before-create helpers
- config-driven object creation order
- JSON reporting

Read `references/config-schema.md` before preparing a config file for the driver.

## Required Reporting

For each run, produce a report under the current project, usually `reports/dataarts_<scenario>_<object_type>_report.json`, containing:

- `generated_at`
- scenario name
- project ID, region, workspace ID
- official API URL
- endpoints used
- dependencies discovered or reused
- object results with `action`, `id`, `status`, and `read_back`
- summary counts

## Safety

Never put IAM passwords, AK/SK values, database passwords, or live tokens into skill files or generated docs. Read credentials from the user’s chosen local source, environment variables, or an existing project-specific credential loader. If network access is sandboxed, request approval for the exact DataArts API command that needs it.
