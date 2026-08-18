# Lessons Learned

## From Code and Tests (VERIFIED_FROM_CODE, VERIFIED_FROM_TEST)

1. DRS MCP safety guards are robust: CIDR /32, region, pre-check, duplicate detection
2. 58 tests pass across 8 test suites - high confidence in MCP reliability
3. Secret redaction works correctly in reports
4. explicit_approval gates prevent accidental task creation/start

## From Documentation (VERIFIED_FROM_DOCUMENTATION)

1. PostgreSQL-to-PostgreSQL DRS uses db_use_type=sync (Data Synchronization), NOT migration
2. Source endpoint for self-managed ECS is "offline" type with is_self_managed=true
3. EIP role separation is critical - never confuse source EIP with DRS EIP
4. Object selection (BatchSetObjects) is a separate post-creation step
5. Connection testing uses BatchValidateConnections, NOT BatchExecuteJobActions

## Recommendations

1. VPN connectivity is OUT_OF_SCOPE_FOR_THIS_SCENARIO per GAP-PG-004 (EIP architecture is the intended design; if VPN is needed for a different scenario, implement separately)
2. Add DRS task stop tool to MCP
3. Add PostgreSQL configuration validation tool
4. Add DDL comparison and row count validation tools
5. Resolve DRS pricing in huaweicloud-pricing MCP
