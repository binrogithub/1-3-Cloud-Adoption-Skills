---
name: dataarts-architecture-automation
description: Documentation for the DataArts Architecture Automation Codex skill.
---

# DataArts Architecture Automation Skill

This skill helps Codex infer and create Huawei Cloud DataArts Studio DataArts Architecture metadata from source tables, CSVs, SQL DDL, catalog exports, data dictionaries, BI metric lists, or business descriptions.

Use it when a task needs DataArts Architecture objects such as:

- model workspaces
- directories
- subjects or topics
- data standards
- code or lookup tables
- table models
- dimensions
- summary tables
- atomic, derivative, and compound metrics
- business metrics or service indicators

## Core Behavior

The skill is intentionally conservative:

- Use only official Huawei Cloud DataArts Studio APIs.
- Never use undocumented console endpoints.
- List existing objects before creating anything.
- Reuse matching objects by stable English name, code, and display name.
- Create objects in dependency order.
- Re-list and verify objects after writes.
- Save returned IDs for downstream dependencies.
- Produce a machine-readable run report.

## Required Inputs

At minimum, an automation run needs:

- Huawei Cloud region
- project ID
- DataArts workspace ID
- credentials supplied outside the skill files
- source artifacts or a reviewed driver config

Do not store IAM passwords, AK/SK values, database passwords, or live tokens in this skill directory.

## Recommended Workflow

1. Collect source context from DDL, metadata exports, CSV headers, JSON schemas, BI definitions, or business documentation.
2. Infer architecture objects using `references/inference-guide.md` when the semantics are not explicit.
3. Review official endpoint requirements in `references/api-map.md`.
4. Prepare a config that follows `references/config-schema.md`.
5. Run or adapt `scripts/dataarts_architecture_driver.py`.
6. Inspect the generated report and verify created or reused IDs.

## Driver

The reusable driver is:

```text
scripts/dataarts_architecture_driver.py
```

It provides:

- IAM token authentication from environment variables or a credentials file
- DataArts GET and POST helpers with retry
- list-before-create helpers
- config-driven object creation order
- JSON reporting

Use the driver as a starting point rather than copying large request blocks by hand.

## References

- `SKILL.md`: activation rules, required workflow, safety requirements, and reporting expectations
- `references/api-map.md`: official DataArts Architecture endpoints and object dependency notes
- `references/config-schema.md`: expected JSON config shape for the driver
- `references/inference-guide.md`: guidance for deriving architecture objects and metrics from source artifacts

## Reporting

Each run should write a report in the current project, usually under:

```text
reports/dataarts_<scenario>_<object_type>_report.json
```

The report should include generated time, scenario name, project and workspace identifiers, API URLs, endpoints used, dependencies discovered or reused, per-object actions, returned IDs, read-back status, and summary counts.
