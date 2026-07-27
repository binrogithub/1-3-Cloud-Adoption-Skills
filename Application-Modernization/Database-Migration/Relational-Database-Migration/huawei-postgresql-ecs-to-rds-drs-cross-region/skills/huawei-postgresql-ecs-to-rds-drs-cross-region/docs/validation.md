# Validation

## Pre-migration
- Source PostgreSQL accessible
- Target RDS accessible
- DRS connectivity verified (connection test PASS)
- DRS pre-check PASS
- Source config validated (wal_level, replication slots)

## Post-migration (Full Sync)
- DDL structure matches (tables, columns, types, constraints)
- Row counts match per table
- Indexes and sequences match
- Extensions present on target

## Post-migration (Incremental)
- Insert test data on source
- Verify replication to target within acceptable lag
- Verify data integrity

## Post-cutover
- Application connects to RDS successfully
- Application functionality verified (smoke tests)
- Performance acceptable
