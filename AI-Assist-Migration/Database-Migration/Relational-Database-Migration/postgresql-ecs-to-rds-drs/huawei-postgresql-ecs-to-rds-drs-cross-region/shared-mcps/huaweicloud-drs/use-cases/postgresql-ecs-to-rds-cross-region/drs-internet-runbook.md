# DRS Internet Runbook — Supported Architecture

## Overview

This runbook guides you through creating a DRS migration task using **public Internet** connectivity between a self-managed PostgreSQL on ECS and an RDS for PostgreSQL in a different region.

**This is the SUPPORTED architecture for the PostgreSQL ECS-to-RDS cross-region migration skill.** VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO. Security is enforced via /32 CIDR restrictions, Security Groups, and pg_hba.conf.

## Prerequisites

- Source ECS with PostgreSQL installed and configured (see `scripts/source_postgresql_bootstrap.sh`)
- Target RDS for PostgreSQL deployed in la-south-2
- Source ECS has an EIP
- PostgreSQL wal_level = logical
- DRS replication user created on source
- Demo database and data loaded on source

## Step 1: Open DRS Console

1. Log in to Huawei Cloud console
2. Navigate to **Data Replication Service (DRS)**
3. Select the region where you want the DRS task (typically the target region: la-south-2)

## Step 2: Create Migration Task

1. Click **Create Task**
2. Configure:

| Parameter | Value |
|-----------|-------|
| Task Name | `pg-ecs-to-rds-migration` |
| Scenario | Migration |
| Migration Mode | **Full + Incremental** |
| Source DB Type | **PostgreSQL** (self-managed) |
| Target DB Type | **PostgreSQL** (RDS) |
| Network Type | **Public network** (Internet) |

## Step 3: Configure Source Database

| Parameter | Value |
|-----------|-------|
| IP Address | Source ECS **EIP** |
| Port | 5432 |
| Database Name | demomigration |
| Username | drs_replicator |
| Password | *(your secure DRS user password)* |

**Important:** After entering source details, DRS will display the **source IP/CIDR** that DRS will use to connect to your database. **Copy this CIDR** — you need it for security group and pg_hba.conf configuration.

## Step 4: Configure Target Database

| Parameter | Value |
|-----------|-------|
| DB Instance | Select your RDS PostgreSQL instance in la-south-2 |
| Database Name | demomigration |
| Username | root (or your RDS admin user) |
| Password | *(your RDS admin password)* |

## Step 5: Update Source Security for DRS Access

After noting the DRS source CIDR from Step 3:

### 5a. Update Security Group

1. Go to the source ECS security group
2. Add inbound rule:

| Direction | Protocol | Port | Source CIDR | Description |
|-----------|----------|------|-------------|-------------|
| Ingress | TCP | 5432 | *(DRS source CIDR)* | DRS replication access - EXPERIMENTAL |

### 5b. Update pg_hba.conf

SSH to the source ECS and update pg_hba.conf:

```bash
# Replace the placeholder with the actual DRS CIDR
sudo sed -i 's/REPLACE_WITH_DRS_SOURCE_CIDR/<DRS_CIDR>/g' /etc/postgresql/16/main/pg_hba.conf

# Reload PostgreSQL
sudo systemctl reload postgresql
```

### 5c. Verify Connectivity

From the ECS, verify PostgreSQL is listening:

```bash
sudo ss -tlnp | grep 5432
```

## Step 6: DRS Pre-Check

1. In the DRS console, click **Pre-Check** on your task
2. Verify all checks pass:

| Check | Expected Result |
|-------|-----------------|
| Source connectivity | Pass |
| Target connectivity | Pass |
| Source permissions | Pass |
| wal_level = logical | Pass |
| Replication slots available | Pass |
| Schema compatibility | Pass |

If any check fails, resolve the issue and re-run the pre-check.

## Step 7: Start Full Sync

1. Click **Start** on the DRS task
2. Monitor the full sync progress:

| Metric | What to Check |
|--------|---------------|
| Status | Full synchronization in progress |
| Progress percentage | Increasing |
| Tables migrated | Count increasing |
| Errors | None |

3. Wait for full sync to complete (status changes to "Full synchronization completed")

## Step 8: Validate Full Migration

1. Open **Database Admin Service (DAS)** for the target RDS
2. Connect to the `demomigration` database
3. Run the queries from `sql/04_target_validation_das.sql`
4. Compare results with source validation output

**Expected results after full sync:**

| Metric | Expected Value |
|--------|----------------|
| demo_customers count | 5 |
| demo_products count | 5 |
| demo_orders count | 5 |
| demo_order_items count | 9 |
| demo_migration_audit count | 1 |
| Total revenue | 3106.41 |
| Audit phase | INITIAL_LOAD |
| Audit status | READY |

## Step 9: Validate Incremental Sync

After full sync completes, DRS automatically enters incremental sync mode.

1. On the **source ECS**, run:

```bash
psql -d demomigration -f sql/05_incremental_test_source.sql
```

2. Wait 10-30 seconds for DRS incremental replication

3. On the **target RDS via DAS**, run:

```sql
-- From sql/06_incremental_validation_target_das.sql
```

4. Verify:

| Metric | Expected Value |
|--------|----------------|
| C006 customer exists | Yes (Frank Okafor, Nigeria) |
| ORD006 order exists | Yes (status=PENDING) |
| ORD006 line item | product P001, qty=1, total=299.99 |
| INCREMENTAL_TEST audit | phase=INCREMENTAL_TEST, status=INSERTED |
| Final customer count | 6 |
| Final order count | 6 |
| Final revenue | 3406.40 |

## Step 10: Monitor Incremental Sync

While incremental sync is running, you can monitor:

| Metric | Where |
|--------|-------|
| Replication delay | DRS task details |
| DDL/DML events | DRS task event log |
| Error count | DRS task status |

## Step 11: Cleanup Public Exposure

After validation is complete, if you want to reduce exposure:

1. **Stop the DRS task** (if no longer needed)
2. **Remove the DRS CIDR inbound rule** from the source security group
3. **Remove or comment out the DRS pg_hba.conf lines** on the source ECS
4. **Reload PostgreSQL**: `sudo systemctl reload postgresql`
5. **Optionally release the ECS EIP** if not needed for SSH

**Do NOT remove the EIP if you still need SSH access to the ECS.**

## Security Warnings

- **EXPERIMENTAL ONLY**: Public Internet PostgreSQL access is not suitable for production
- The DRS CIDR is typically a narrow range, not 0.0.0.0/0
- Never use 0.0.0.0/0 for PostgreSQL access
- VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO — do not attempt VPN for this scenario
- All public exposure is documented in `docs/security-and-cleanup.md`
- The future-vpn-runbook.md is retained for reference only

## Troubleshooting

| Issue | Solution |
|-------|----------|
| DRS cannot connect to source | Check security group, pg_hba.conf, EIP, PostgreSQL listening |
| Pre-check fails on wal_level | Set wal_level = logical and restart PostgreSQL |
| Pre-check fails on permissions | Grant required privileges to drs_replicator |
| Full sync stuck | Check DRS error log; verify source data is accessible |
| Incremental delay high | Check network latency; verify WAL is being sent |
| Missing data on target | Re-run validation queries; check DRS task for errors |
