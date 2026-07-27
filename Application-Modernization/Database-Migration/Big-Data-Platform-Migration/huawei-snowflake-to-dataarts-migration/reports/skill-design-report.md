# Skill Design Report

## Date

2026-07-27

## Convention Selection

No pre-existing skill convention was found in the codebase or OpenCode configuration.

The following convention is defined for this package:

### Skill Format

- **SKILL.md**: YAML front matter + Markdown body (operational instructions for agent)
- **skill.yaml**: Machine-readable manifest (YAML)
- **mcp-dependencies.yaml**: MCP tool dependency mapping (YAML)
- **workflows/**: Phase-specific workflow definitions (Markdown)
- **prompts/**: Ready-to-use prompts per phase (Markdown)
- **docs/**: Supporting documentation (Markdown)

### Naming Convention

- Skills: kebab-case, prefixed with domain (huawei-*, mcp-*)
- Files: UPPERCASE.md for primary docs, lowercase.md for secondary
- YAML: kebab-case for keys

### Status Values

READY, READY_WITH_WARNINGS, PARTIAL, EXPERIMENTAL, DRAFT, BLOCKED

### Automation Levels

AUTOMATED, ASSISTED, MANUAL, NOT_IMPLEMENTED

### Evidence Tags

VERIFIED_FROM_CODE, VERIFIED_FROM_TEST, VERIFIED_FROM_DOCUMENTATION, INFERRED, NOT_VERIFIED

## Skills Designed

| Skill | Status | Rationale |
|---|---|---|
| huawei-cce-cross-region-velero-migration | EXPERIMENTAL | CCE not in deploy MCP, Velero not automated, 7/10 phases MANUAL |
| huawei-postgresql-ecs-to-rds-drs-cross-region | READY_WITH_WARNINGS | 10/13 DRS tools available, safety guards verified, VPN not implemented |
| huawei-snowflake-to-dataarts-migration | PARTIAL | Demo flow works, production migration not available |
| mcp-capability-builder | READY_WITH_WARNINGS | Local-only operation, no cloud risk, generated MCPs need review |
