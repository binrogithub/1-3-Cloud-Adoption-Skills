# DRS Migration Troubleshooting

Common failures encountered during DRS migration and their solutions.

## DRS API Errors

### DRS.M00300 — "Invoke the test connection interface and ensure that the test connection is successful"

**Cause**: You ran `BatchCheckJobs` (precheck) without first calling `BatchValidateConnections` for both source and target.

**Fix**: Always test connections before precheck:

```bash
# Test source connection
hcloud DRS BatchValidateConnections --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.id=<job_id> \
  --jobs.1.end_point_type=so \
  --jobs.1.db_type=mysql \
  --jobs.1.ip=<source_host> \
  --jobs.1.db_port=3306 \
  --jobs.1.db_user=<user> \
  --jobs.1.db_password=<password> \
  --jobs.1.net_type=eip \
  --cli-read-timeout=120 --cli-output=json

# Test target connection
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
  --jobs.1.inst_id=<rds_id> \
  --jobs.1.region=<region> \
  --jobs.1.project_id=<pid> \
  --jobs.1.vpc_id=<vpc_id> \
  --jobs.1.subnet_id=<subnet_id> \
  --cli-read-timeout=120 --cli-output=json
```

### DRS.10010047 — "Service error. Perform the precheck again."

**Cause**: The precheck found FAILED items that block the job from starting.

**Fix**: Run `BatchCheckResults` to see which items failed, fix them, then re-run `BatchCheckJobs`.

### DRS.M00304 — "API cannot be invoked by a task in the current state"

**Cause**: You tried to delete a DRS job that is in a state that doesn't support direct deletion (e.g., `CONFIGURATION` status).

**Fix**: Force terminate first, then delete:

```bash
# Step 1: Force terminate
hcloud DRS BatchDeleteJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --jobs.1.delete_type=force_terminate \
  --cli-read-timeout=120 --cli-output=json

# Step 2: Wait a few seconds, then delete
sleep 10
hcloud DRS BatchDeleteJobs --cli-region=<region> \
  --project_id=<pid> \
  --jobs.1.job_id=<job_id> \
  --jobs.1.delete_type=delete \
  --cli-read-timeout=120 --cli-output=json
```

## Precheck Failures

### SOURCE_DB_BINLOG_IS_OFF_FOR_UP

**Cause**: Binary logging is OFF on the source database. Required for `FULL_INCR_TRANS`.

**Symptoms**:
- `SHOW VARIABLES LIKE 'log_bin'` returns `OFF` even though `binlog_format` is set to `ROW`

**Root cause**: On AWS RDS, `log_bin` stays OFF unless `backup_retention_period > 0`. Setting `binlog_format=ROW` alone is not sufficient.

**Fix**: See [aws-rds-preparation.md](aws-rds-preparation.md) — Step 4: Enable Binary Logging.

**Alternative**: If binlog cannot be enabled, change `task_type` to `FULL_TRANS` (full migration only, no incremental sync).

### DB_TBL_NAME_CASE_SENSITIVE_INCONSISTENCY_FOR_UP

**Cause**: `lower_case_table_names` differs between source and target.
- Source: `0` (case-sensitive, Linux default)
- Target: `1` (case-insensitive, Huawei Cloud default)

**Impact**: DRS precheck FAILS. Job cannot start.

**Fix**: See [parameter-alignment.md](parameter-alignment.md) — The lower_case_table_names Trap.

**Quick summary**: Add `lower_case_table_names = "0"` to the Huawei RDS Terraform resource (ForceNew — destroys and recreates RDS).

### DB_ISOLATION_LEVEL_INCONSISTENCY

**Cause**: `transaction_isolation` differs.
- Source: `REPEATABLE-READ` (AWS default)
- Target: `READ-COMMITTED` (Huawei default)

**Fix**: Create a custom parameter template with `transaction_isolation=REPEATABLE-READ` and apply to the Huawei RDS. See [parameter-alignment.md](parameter-alignment.md).

### INNODB_STRICT_MODE_INCONSISTENT_FOR_UP

**Cause**: `innodb_strict_mode` differs.
- Source: `ON` (AWS default)
- Target: `OFF` (Huawei default)

**Fix**: Add `innodb_strict_mode=ON` to the custom parameter template. See [parameter-alignment.md](parameter-alignment.md).

## Network Issues

### Source RDS port is closed despite PubliclyAccessible=true

**Symptoms**:
- `nc -z -w 10 <rds-endpoint> 3306` returns CLOSED
- DNS resolves to a public IP (e.g. 3.x.x.x)
- `PubliclyAccessible=true` confirmed in AWS console

**Root cause**: The RDS subnet's route table doesn't have a `0.0.0.0/0 → IGW` route. Without this route, inbound traffic from the internet cannot reach the RDS, even with a public IP assigned.

**Diagnosis**:
```bash
# Check the RDS subnet
aws rds describe-db-instances --region <region> \
  --db-instance-identifier <id> \
  --query 'DBInstances[0].DBSubnetGroup.Subnets[].SubnetIdentifier' \
  --output json

# Check route tables
aws ec2 describe-route-tables --region <region> \
  --filters Name=vpc-id,Values=<vpc-id> \
  --query 'RouteTables[].{Id:RouteTableId,Routes:Routes[].{Dest:DestinationCidrBlock,Target:GatewayId}}' \
  --output json
```

**Fix**: Add IGW route to the private route table:
```bash
aws ec2 create-route --region <region> \
  --route-table-id <private-rt-id> \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id <igw-id>
```

### VPN impossible with overlapping CIDRs

**Symptoms**:
- Both source and target VPCs use the same CIDR (e.g. 10.0.0.0/16)
- VPN tunnel establishes but traffic doesn't flow
- Routing table can't distinguish local vs remote for overlapping subnets

**Fix**: Use `net_type = "eip"` instead of VPN. Or re-IP one VPC to a non-overlapping CIDR (e.g. 192.168.0.0/16) before setting up VPN.

## Terraform Issues

### "target_endpoint can't be updated" when RDS is recreated

**Symptoms**:
```
Error: target_endpoint.0.endpoint.0.instance_id can't be updated
```

**Cause**: The `instance_id` field in `huaweicloud_drs_job_v5` is `NonUpdatable`. When the RDS is recreated (e.g., due to `lower_case_table_names` ForceNew), the instance ID changes, but the DRS job can't be updated in-place.

**Fix**:
1. Remove DRS job from Terraform state: `terraform state rm huaweicloud_drs_job_v5.<name>`
2. Force terminate and delete the DRS job via hcloud CLI
3. Apply Terraform — RDS will be recreated, then DRS job will be created with the new instance ID

### DRS job stuck in CONFIGURATION status

**Cause**: The job was created but never started (connections not validated, precheck not run, or precheck failed).

**Fix**: Follow the validation flow: `BatchValidateConnections` → `BatchCheckJobs` → `BatchCheckResults` → `BatchStartJobs`.

## Precheck Result Interpretation

| Result | Meaning | Action |
|--------|---------|--------|
| `PASSED` | Check passed | None |
| `FAILED` | Check failed, blocks job start | Must fix before starting |
| `ALARM` | Warning, does not block | Review but can proceed |
| `""` (empty) | Check still running | Wait and re-check |

### Common ALARM items (safe to proceed)

- `dstDbDiskSize` — Target disk is larger than source data. Informational.
- `sqlModeConsistency` — Different SQL modes. Usually safe for migration.
- `srcGtidStatusCheck` — GTID is OFF on source. DRS uses binlog position instead.
- `dbParamConsistency` — Minor param differences (e.g., `explicit_defaults_for_timestamp`). Usually safe.

## Monitoring Commands Quick Reference

```bash
# Job status
hcloud DRS ShowJobList --cli-region=<region> \
  --cur_page=1 --per_page=10 --db_use_type=migration --cli-output=json

# Progress details
hcloud DRS BatchListProgresses --cli-region=<region> \
  --project_id=<pid> --jobs.1=<job_id> \
  --cli-read-timeout=120 --cli-output=json

# RPO/RTO (incremental sync delay)
hcloud DRS BatchListRposAndRtos --cli-region=<region> \
  --project_id=<pid> --jobs.1=<job_id> \
  --cli-read-timeout=120 --cli-output=json
```

### Status meanings

| Status | Meaning |
|--------|---------|
| `CONFIGURATION` | Job created, not yet started |
| `STARTJOBING` | Job starting up |
| `FULL_TRANSFER_STARTED` | Full data copy in progress |
| `INCRE_TRANSFER_STARTED` | Full copy done, incremental sync active |
| `APPLYING` | Applying data to target |
| `SUCCESS` | Migration complete |
| `FAILED` | Migration failed |
| `PAUSING` / `PAUSED` | Job paused |
