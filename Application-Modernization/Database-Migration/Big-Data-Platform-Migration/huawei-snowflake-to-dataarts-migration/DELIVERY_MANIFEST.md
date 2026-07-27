# Delivery Manifest

## Package

huawei-cloud-migration-skills-handoff-20260727

## Date

2026-07-27

## Skills Included

- huawei-cce-cross-region-velero-migration (EXPERIMENTAL)
- huawei-postgresql-ecs-to-rds-drs-cross-region (READY_WITH_WARNINGS)
- huawei-snowflake-to-dataarts-migration (PARTIAL)
- mcp-capability-builder (READY_WITH_WARNINGS)

## MCPs Included (full source code)

- huaweicloud-pricing (25 tools, READY, 6 src files, 21 test files)
- huaweicloud-deploy (4 tools, READY, 5 src files, 9 test files)
- huaweicloud-drs (13 tools, READY, 6 src files, 3 test files)
- huaweicloud-ticket (10 tools, READY, 3 src files, 1 test file)
- dataarts-deploy-agent (6 tools, PARTIAL, 89 src files, 35 test files)

## MCPs Generated

None

## Total Tools Referenced

58 (25 + 4 + 13 + 10 + 6)

## Capability Gaps

20 total (14 MANUAL_STEP, 1 EXTEND_EXISTING_MCP, 3 NOT_REQUIRED, 1 BLOCKED)

## Validation Result

PASS (all 20 checks)

## Known Risks

- CCE Velero migration: EXPERIMENTAL (most phases manual)
- DRS VPN: OUT_OF_SCOPE_FOR_THIS_SCENARIO (public EIP is the supported architecture)
- DRS pricing: BLOCKED (optional — affects cost estimation only, does not block core migration)
- DataArts: PARTIAL (demo only)

## Pending Items

See reports/known-pending-items.md

## Files Excluded

See inventory/excluded-files.md
