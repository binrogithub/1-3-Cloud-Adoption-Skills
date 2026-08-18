# Known Issues

1. **VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO**: This scenario intentionally uses public Internet (EIP) connectivity. Security mitigated by /32 CIDR, SG rules, and pg_hba.conf restrictions. VPN is not required for this architecture.
2. **DRS task stop**: No MCP tool for stopping DRS tasks. Requires manual console operation.
3. **PostgreSQL config**: Source configuration validation requires manual SSH access.
4. **Extension compatibility**: Must be checked manually before migration.
5. **DRS pricing BLOCKED**: huaweicloud-pricing MCP cannot price DRS (resource_spec not found in BSS/OCE).
6. **Object selection**: DRS may not select all objects by default. Verify object selection after task creation.
7. **Public exposure**: PostgreSQL port is exposed via EIP during migration. Remove access post-migration.
