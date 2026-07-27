# Rollback Procedure

## Pre-cutover Rollback
1. Stop DRS task (manual console operation)
2. No data impact - source remains authoritative
3. Clean up DRS task if needed

## Post-cutover Rollback
1. Immediately redirect application connections to source ECS PostgreSQL
2. Verify source database is operational
3. Stop DRS task (manual console operation)
4. Assess data divergence between source and target
5. If source was modified during cutover: verify source data integrity
6. Document rollback reason and timeline

## Cleanup
1. Delete DRS task
2. Remove source SG rules for DRS EIP
3. Remove pg_hba.conf entries for DRS
4. Consider RDS data cleanup or instance deletion
