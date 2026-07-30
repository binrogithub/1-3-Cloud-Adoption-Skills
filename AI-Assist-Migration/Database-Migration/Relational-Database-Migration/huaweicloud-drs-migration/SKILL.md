---
name: huaweicloud-drs-migration
description: Migrate databases to Huawei Cloud RDS using DRS (Data Replication Service). Handles AWS and other-cloud MySQL to Huawei Cloud MySQL with full+incremental replication, parameter alignment, network connectivity, and Terraform automation. Use when the user wants to migrate or replicate a database to Huawei Cloud.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: database-migration-huaweicloud
---

# Huawei Cloud DRS Database Migration

Migrate databases from AWS RDS, self-built MySQL, or other clouds to Huawei Cloud RDS using the Data Replication Service (DRS). This skill covers the complete end-to-end workflow: discovery, network preparation, parameter alignment, Terraform automation, validation, migration execution, and cleanup.

## Rules

1. **DISCOVER before ACT** — always inventory the source and target before creating any DRS resources. Know the exact engine, version, parameters, endpoint, and network topology of both sides.
2. **VALIDATE CONNECTIONS before PRECHECK** — DRS precheck will fail (`DRS.M00300`) if you haven't called `BatchValidateConnections` for both source and target first. Always test connections, then precheck, then start.
3. **NEVER SKIP PARAMETER ALIGNMENT** — mismatched `transaction_isolation`, `innodb_strict_mode`, or `lower_case_table_names` will block the migration. Align target to source before creating the DRS job. See [references/parameter-alignment.md](references/parameter-alignment.md).
4. **CHECK DRS LINK COMPATIBILITY** — call `ListLinks` to verify the exact combination of `job_type`, `engine_type`, `net_type`, `task_type`, `source_endpoint_type`, and `target_endpoint_type` is supported in the target region. Never assume.
5. **CHECK NODE TYPE AVAILABILITY** — call `ListAvailableNodeTypes` to find which DRS node specs exist. Some regions only offer `high`; `micro`/`small`/`medium` may not exist.
6. **ALWAYS USE TERRAFORM** — create DRS jobs via `huaweicloud_drs_job_v5` resource, not hcloud CLI. Terraform provides state management, drift detection, and reproducibility. See [references/terraform-drs-job.md](references/terraform-drs-job.md).
7. **PLAN FOR RDS RECREATION** — if `lower_case_table_names` must change, the Huawei RDS must be destroyed and recreated (`ForceNew`). The DRS job must also be deleted and recreated since `instance_id` is `NonUpdatable`. Plan this before applying.
8. **REVERT TEMP CHANGES** — any temporary changes on the source (public access, SG rules, IGW routes, binlog) must be reverted after cutover. Document every temp change and its revert command.
9. **MONITOR RPO AFTER START** — once the full transfer completes and incremental sync begins, track RPO delay via `BatchListRposAndRtos`. Cutover is safe only when RPO = 0s.
10. **NEVER GUESS PASSWORDS OR ENDPOINTS** — always ask the user for source DB credentials. Never extract them from state files, logs, or environment variables.

## Workflow Overview

```
Phase 1          Phase 2          Phase 3          Phase 4
DISCOVER    →    NETWORK    →    PARAM ALIGN  →   SOURCE PREP
(inventory)      (connectivity)   (match params)    (binlog, public)

Phase 5          Phase 6          Phase 7          Phase 8
TERRAFORM   →    VALIDATE   →    START&MONTOR →   CUTOVER&CLEANUP
(drs.tf)         (conn+precheck)  (run job)         (revert, re-point)
```

## Phase 1: DISCOVER

Gather complete information about source and target databases.

### Source inventory (AWS RDS example)

```bash
# Get instance details
aws rds describe-db-instances --region <region> \
  --db-instance-identifier <id> \
  --query 'DBInstances[0].{Engine:Engine,Version:EngineVersion,Endpoint:Endpoint.Address,
    Port:Endpoint.Port,PubliclyAccessible:PubliclyAccessible,
    MultiAZ:MultiAZ,BackupRetention:BackupRetentionPeriod,
    ParamGroups:DBParameterGroups[*].DBParameterGroupName}' \
  --output json

# Get security group rules
aws ec2 describe-security-groups --region <region> \
  --group-ids <sg-id> \
  --query 'SecurityGroups[0].IpPermissions' --output json

# Get route tables (check for IGW route)
aws ec2 describe-route-tables --region <region> \
  --filters Name=vpc-id,Values=<vpc-id> \
  --query 'RouteTables[].{Id:RouteTableId,Assoc:Associations[].SubnetId,
    Routes:Routes[].{Dest:DestinationCidrBlock,Target:GatewayId}}' \
  --output json

# Get VPC CIDR
aws ec2 describe-vpcs --region <region> \
  --vpc-ids <vpc-id> --query 'Vpcs[0].CidrBlock' --output text
```

### Target inventory (Huawei Cloud)

```bash
# List RDS instances
hcloud RDS ListInstances --cli-region=<region> --cli-output=json

# Get RDS parameter configuration
hcloud RDS ShowInstanceConfiguration --cli-region=<region> \
  --instance_id=<id> --project_id=<pid> --cli-output=json

# Check DRS link compatibility
hcloud DRS ListLinks --cli-region=<region> \
  --job_type=migration --cli-output=json

# Check DRS node type availability
hcloud DRS ListAvailableNodeTypes --cli-region=<region> \
  --engine_type=mysql --job_type=migration --cli-output=json

# Get project ID
hcloud IAM KeystoneListProjects --cli-output=json
```

### What to collect

| Item | Source | Target |
|------|--------|--------|
| Engine + version | e.g. MySQL 8.0.45 | e.g. MySQL 8.0.43 |
| Endpoint / IP | hostname or IP | IP or instance ID |
| Port | 3306 | 3306 |
| DB name | wordpress | (to be migrated) |
| Username | admin | root |
| VPC CIDR | 10.0.0.0/16 | 10.0.0.0/16 |
| Publicly accessible | true/false | N/A |
| Backup retention | 0 = binlog OFF | N/A |
| Key parameters | lower_case_table_names, transaction_isolation, innodb_strict_mode | same |

## Phase 2: NETWORK

Decide how DRS will reach the source database.

### Decision tree

```
Source is Huawei Cloud RDS?
├── YES → net_type = "vpc" (same VPC) or "eip" (cross-VPC)
└── NO (AWS/other cloud)
    ├── VPN available with non-overlapping CIDRs?
    │   ├── YES → net_type = "vpn" (see VPN note below)
    │   └── NO → net_type = "eip" (public network, requires source to be reachable)
    └── Source is self-built on Huawei ECS?
        └── net_type = "vpc" (same VPC) or "eip" (cross-VPC)
```

### CIDR overlap check (CRITICAL)

If both source and target VPCs use the same CIDR (e.g. both use 10.0.0.0/16), **VPN is impossible** without re-IP or NAT. The routing table cannot distinguish local traffic from remote traffic for overlapping subnets. Use `net_type = "eip"` instead.

### AWS RDS public accessibility (EIP path)

For `net_type = "eip"`, the source must be reachable from the public internet. For AWS RDS, this requires **three** changes (not just one):

1. **Make RDS publicly accessible** — `aws rds modify-db-instance --publicly-accessible`
2. **Add IGW route to the RDS subnet's route table** — even with a public IP, the RDS is unreachable if its subnet lacks a `0.0.0.0/0 → igw-xxx` route. This is the most commonly missed step.
3. **Add SG rule** — allow TCP 3306 from `0.0.0.0/0` (or restrict to DRS EIP if known)

See [references/aws-rds-preparation.md](references/aws-rds-preparation.md) for the exact commands.

### Verify connectivity

After making the source reachable, verify from the Huawei Cloud side:

```bash
ssh root@<huawei-ecs-eip> "nc -z -w 10 <source-endpoint> 3306 && echo OPEN || echo CLOSED"
```

## Phase 3: PARAMETER ALIGNMENT

The target (Huawei Cloud RDS) must match critical source parameters. DRS precheck will FAIL on mismatches.

### Critical parameters (must match)

| Parameter | AWS RDS default | Huawei RDS default | Fix |
|-----------|----------------|-------------------|-----|
| `transaction_isolation` | REPEATABLE-READ | READ-COMMITTED | Custom param template |
| `innodb_strict_mode` | ON | OFF | Custom param template |
| `explicit_defaults_for_timestamp` | ON | OFF | Custom param template |
| `lower_case_table_names` | 0 (Linux) | 1 | **ForceNew — must recreate RDS** |

### Alarm-only parameters (non-blocking)

| Parameter | Note |
|-----------|------|
| `sql_mode` | Different SQL modes generate warnings, not failures |
| `gtid_mode` | GTID OFF on source is an alarm; DRS uses binlog position instead |
| Disk size | Target disk larger than source is just informational |

### lower_case_table_names trap

This parameter is `ForceNew` on `huaweicloud_rds_instance` — changing it destroys and recreates the RDS. It **cannot** be changed after initialization on MySQL 8.0. If the source uses `0` (case-sensitive, Linux default) and the target defaults to `1`, you **must** recreate the target RDS with `lower_case_table_names = "0"`.

If the DRS job already exists with the old RDS instance ID, you must also delete and recreate the DRS job (because `instance_id` is `NonUpdatable`).

See [references/parameter-alignment.md](references/parameter-alignment.md) for the complete procedure.

## Phase 4: SOURCE PREPARATION

Prepare the source database for DRS connectivity and incremental replication.

### Binlog enablement (AWS RDS)

For `FULL_INCR_TRANS` (full + incremental), binary logging must be ON on the source. On AWS RDS MySQL 8.0:

1. **Set `binlog_format=ROW`** in a custom parameter group
2. **Set `backup_retention_period > 0`** — this is the hidden requirement. Even with `binlog_format=ROW`, `log_bin` stays OFF if `backup_retention_period = 0`. Setting it to 1+ enables automated backups which turns on binary logging.
3. **Reboot** the RDS instance
4. **Verify**: `SHOW VARIABLES LIKE 'log_bin'` must return `ON`

### Source DB credentials

Ask the user for:
- Admin username and password for the source database
- Database name to migrate (e.g. `wordpress`)

Add these as Terraform variables:
```hcl
variable "source_db_password" {
  description = "Source DB admin password"
  type        = string
  sensitive   = true
}
```

See [references/aws-rds-preparation.md](references/aws-rds-preparation.md) for the complete procedure.

## Phase 5: TERRAFORM

Create the DRS job as a Terraform resource.

### Key configuration decisions

| Decision | Options | Recommendation |
|----------|---------|---------------|
| `job_type` | migration, sync, cloudDataGuard | `migration` for one-time migration |
| `task_type` | FULL_TRANS, FULL_INCR_TRANS, INCR_TRANS | `FULL_INCR_TRANS` for zero-downtime |
| `net_type` | eip, vpn, vpc | `eip` for cross-cloud (simplest) |
| `job_direction` | up, down | `up` (ingress into Huawei Cloud) |
| `node_type` | micro, small, medium, high | Check `ListAvailableNodeTypes` — varies by region |
| `charging_mode` | on_demand, period | `on_demand` for migration |

### Source endpoint types

| Source type | `endpoint_type` | `endpoint_name` |
|-------------|----------------|-----------------|
| AWS RDS / other cloud | `offline` | `mysql` |
| Huawei ECS self-built | `ecs` | `ecs_mysql` |
| Huawei Cloud RDS | `cloud` | `cloud_mysql` |

### SG strategy for DRS node

The DRS node needs to connect to the target RDS. Instead of creating a new SG, **reuse the ECS SG** for the DRS node (`node_info.vpc.security_group_id`). This way, the existing RDS SG rule (allow MySQL from ECS SG) already covers the DRS node — no additional SG rules needed.

### Template

See [references/terraform-drs-job.md](references/terraform-drs-job.md) for the complete `huaweicloud_drs_job_v5` resource template with all required and optional fields.

## Phase 6: VALIDATE & PRECHECK

### Step 1: Test connections (BOTH source and target)

```bash
# Source connection test
hcloud DRS BatchValidateConnections --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.id=<job_id> \
  --jobs.1.end_point_type=so \
  --jobs.1.db_type=mysql \
  --jobs.1.ip=<source_endpoint> \
  --jobs.1.db_port=3306 \
  --jobs.1.db_user=<user> \
  --jobs.1.db_password=<password> \
  --jobs.1.net_type=eip \
  --cli-read-timeout=120 --cli-output=json

# Target connection test
hcloud DRS BatchValidateConnections --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.id=<job_id> \
  --jobs.1.end_point_type=ta \
  --jobs.1.db_type=mysql \
  --jobs.1.ip=<target_ip> \
  --jobs.1.db_port=3306 \
  --jobs.1.db_user=root \
  --jobs.1.db_password=<password> \
  --jobs.1.net_type=eip \
  --jobs.1.inst_id=<rds_instance_id> \
  --jobs.1.region=<region> \
  --jobs.1.project_id=<pid> \
  --jobs.1.vpc_id=<vpc_id> \
  --jobs.1.subnet_id=<subnet_id> \
  --cli-read-timeout=120 --cli-output=json
```

Both must return `"success": true` before proceeding.

### Step 2: Run precheck

```bash
hcloud DRS BatchCheckJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --jobs.1.precheck_mode=forStartJob \
  --cli-read-timeout=120 --cli-output=json
```

Wait 30-60 seconds, then check results:

```bash
hcloud DRS BatchCheckResults --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1=<job_id> \
  --cli-read-timeout=120 --cli-output=json
```

### Step 3: Interpret results

- **FAILED** items block the job start. Must fix before proceeding.
- **ALARM** items are warnings. The job can start, but review for potential issues.
- **PASSED** items are good.

See [references/troubleshooting.md](references/troubleshooting.md) for failure resolution.

## Phase 7: START & MONITOR

### Start the job

```bash
hcloud DRS BatchStartJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --cli-read-timeout=120 --cli-output=json
```

### Monitor progress

```bash
# Job status
hcloud DRS ShowJobList --cli-region=<region> \
  --cur_page=1 --per_page=10 --db_use_type=migration \
  --cli-output=json

# Detailed progress
hcloud DRS BatchListProgresses --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1=<job_id> \
  --cli-read-timeout=120 --cli-output=json

# RPO/RTO (incremental sync delay)
hcloud DRS BatchListRposAndRtos --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1=<job_id> \
  --cli-read-timeout=120 --cli-output=json
```

### Status progression

```
CONFIGURATION → STARTJOBING → FULL_TRANSFER_STARTED → INCRE_TRANSFER_STARTED
```

- `FULL_TRANSFER_STARTED`: Full data copy in progress. Check `progress` field (0-100%).
- `INCRE_TRANSFER_STARTED`: Full copy complete, incremental sync active. Monitor `incre_trans_delay` — when it reaches 0, source and target are in sync.

### Cutover readiness

The migration is ready for cutover when:
1. Status is `INCRE_TRANSFER_STARTED`
2. RPO delay is `0` seconds
3. `incre_trans_delay` is `0`

## Phase 8: CUTOVER & CLEANUP

### Cutover steps

1. **Stop writes on source** — application downtime begins
2. **Wait for DRS to sync** — RPO should already be 0 if incremental is running
3. **Stop the DRS job** — `BatchDeleteJobs` with `delete_type=terminate`
4. **Verify data on target** — connect to Huawei RDS and spot-check tables/row counts
5. **Re-point application** — update DB host to Huawei RDS private IP
6. **Revert temp changes** — see below

### Revert temporary source changes

Every temporary change made during Phase 2 and Phase 4 must be reverted:

```bash
# Remove temp SG rule
aws ec2 revoke-security-group-ingress --region <region> \
  --group-id <sg-id> --protocol tcp --port 3306 --cidr 0.0.0.0/0

# Remove IGW route from private route table
aws ec2 delete-route --region <region> \
  --route-table-id <rt-id> --destination-cidr-block 0.0.0.0/0

# Disable public access
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <id> --no-publicly-accessible --apply-immediately

# (Optional) Revert backup retention
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <id> --backup-retention-period 0 --apply-immediately
```

### Delete DRS job

```bash
# Terminate first (if still running)
hcloud DRS BatchDeleteJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --jobs.1.delete_type=force_terminate \
  --cli-read-timeout=120 --cli-output=json

# Then delete
hcloud DRS BatchDeleteJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --jobs.1.delete_type=delete \
  --cli-read-timeout=120 --cli-output=json
```

Remove the DRS resource from Terraform state and `drs.tf` file.

## Quick Reference: DRS API Flow

```
1. ListLinks              → verify engine/net/task compatibility
2. ListAvailableNodeTypes → check node specs
3. Create job (Terraform) → huaweicloud_drs_job_v5
4. BatchValidateConnections → test source + target (BOTH)
5. BatchCheckJobs         → run precheck
6. BatchCheckResults      → read precheck results
7. BatchStartJobs         → start migration
8. ShowJobList            → monitor status
9. BatchListProgresses    → monitor progress %
10. BatchListRposAndRtos  → monitor RPO delay
11. BatchDeleteJobs       → terminate + delete
```

## References

- [AWS RDS Preparation](references/aws-rds-preparation.md) — binlog, public access, SG, IGW route
- [Parameter Alignment](references/parameter-alignment.md) — matching source and target params
- [Terraform DRS Job](references/terraform-drs-job.md) — resource schema and examples
- [Troubleshooting](references/troubleshooting.md) — common failures and fixes
