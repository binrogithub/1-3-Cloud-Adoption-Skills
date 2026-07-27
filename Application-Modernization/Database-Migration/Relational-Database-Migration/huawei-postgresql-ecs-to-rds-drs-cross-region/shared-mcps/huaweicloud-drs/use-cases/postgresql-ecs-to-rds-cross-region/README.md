# PostgreSQL ECS to RDS Cross-Region Migration via DRS

## Purpose

Migrate a self-managed PostgreSQL database on ECS to Huawei Cloud RDS for PostgreSQL, across different regions, using DRS Full+Incremental replication over public network (EIP).

## Architecture

- **Source:** PostgreSQL on ECS (self-managed) in source region
- **Target:** RDS for PostgreSQL in target region
- **Replication:** DRS Full+Incremental
- **Network:** Public internet via DRS EIP (no VPN)
- **Regions:** Different (cross-region)

## Prerequisites

1. Source PostgreSQL with `wal_level=logical`
2. Replication user created on source
3. `pg_hba.conf` updated to allow DRS EIP
4. Security Group rule for DRS EIP on source ECS
5. Target RDS instance created and accessible
6. DRS service enabled in target region

## Execution runbook

| Step | Description | Classification |
|------|-------------|----------------|
| 1 | Create DRS task with `drs_create_postgresql_full_incremental_task` | AUTOMATED |
| 2 | Capture DRS replication instance EIP with `drs_capture_replication_instance_eip` | AUTOMATED |
| 3 | Generate source access plan with `drs_generate_source_access_plan` | AUTOMATED |
| 4 | Apply Security Group rule on source ECS | ASSISTED |
| 5 | Update `pg_hba.conf` on source PostgreSQL | MANUAL |
| 6 | Reload PostgreSQL config (`SELECT pg_reload_conf()`) | MANUAL |
| 7 | Run connection test with `drs_run_connection_test` | AUTOMATED |
| 8 | Run pre-check with `drs_run_precheck` | AUTOMATED |
| 9 | Review and resolve pre-check warnings | ASSISTED |
| 10 | Start DRS task with `drs_start_task` (requires explicit_approval) | AUTOMATED |
| 11 | Monitor full sync progress with `drs_get_task_status` | AUTOMATED |
| 12 | Validate data counts (source vs target) | ASSISTED |
| 13 | Insert incremental test data on source | MANUAL |
| 14 | Validate incremental data on target | ASSISTED |
| 15 | Cutover: stop application writes to source | MANUAL |
| 16 | Wait for incremental sync to complete | AUTOMATED |
| 17 | Switch application to target RDS | MANUAL |
| 18 | Generate report with `drs_generate_report` | AUTOMATED |

## Validation

- Row count comparison between source and target
- Sample data queries on both sides
- Incremental insert verification
- DRS task status monitoring

## Rollback

1. Stop DRS task (if still running)
2. Revert application connection to source ECS
3. Drop migrated data from target RDS (if needed)
4. Remove DRS EIP Security Group rule from source

## Known issues

- Load balancers, EIPs, and DNS are not migrated by DRS
- PostgreSQL extensions must be compatible between source and target
- Object ownership may differ; verify with `\dn+` on both sides
- Sequence values may need manual synchronization after cutover
- Large objects (LOB) may require special handling

## Advertencias

- **Load balancers:** Not migrated; must be recreated in target region
- **EIP:** Source EIP cannot be transferred cross-region
- **DNS:** Must be updated manually after cutover
- **StorageClasses:** Not applicable (RDS manages storage)
- **Persistent Volumes:** Not migrated; RDS uses managed storage
- **Kubernetes compatibility:** N/A for this use case
- **Secrets:** Database credentials differ between source and target
- **ConfigMaps with endpoints:** Must be updated for target region
- **Stateful applications:** Require careful cutover timing

## Lessons learned

- DRS pre-checks are critical; never skip them
- Cross-region public network adds latency; monitor replication delay
- Always validate data counts before cutover
- Test incremental replication with small inserts before full cutover
- Keep source available for rollback until validation is complete
