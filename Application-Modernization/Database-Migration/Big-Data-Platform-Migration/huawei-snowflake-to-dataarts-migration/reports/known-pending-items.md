# Known Pending Items

## From Source Package

1. **CCE cross-region Velero migration**: NOT_IMPLEMENTED in MCP. Skill status: EXPERIMENTAL.
2. **DataArts production migration**: PARTIAL. Only demo/POC flow available.
3. **DRS VPN connectivity**: OUT_OF_SCOPE_FOR_THIS_SCENARIO. Public EIP is the supported architecture for this scenario. VPN is not required.
4. **Playwright version pinning**: RESOLVED. Pinned to @playwright/mcp@0.0.78.
5. **DRS migration operator**: Available in migration-lab but not in handoff package.

## From Skills Analysis

6. **CCE support in deploy MCP**: GAP-CCE-007. CCE not in supported services.
7. **DRS task stop tool**: GAP-PG-003. No MCP tool for stopping DRS tasks.
8. **PostgreSQL config validation**: GAP-PG-001. Requires manual SSH.
9. **DRS pricing**: BLOCKED in huaweicloud-pricing MCP.
10. **Snowflake source extraction**: GAP-DA-001. No automated extraction.

## Recommendations

- Add CCE to huaweicloud-deploy supported services (resolves GAP-CCE-007)
- Create Velero MCP for backup/restore automation (resolves GAP-CCE-002)
- Add DRS task stop tool to huaweicloud-drs MCP (resolves GAP-PG-003)
- VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO — do not attempt VPN design or creation for this scenario (resolves GAP-PG-004)
- Pin Playwright version after validation
