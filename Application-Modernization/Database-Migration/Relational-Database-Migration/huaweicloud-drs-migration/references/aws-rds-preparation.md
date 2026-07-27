# AWS RDS Preparation for DRS Migration

This guide covers all the preparation steps needed on an AWS RDS MySQL instance before DRS can migrate it to Huawei Cloud.

## Overview of Required Changes

| Change | Why | Revert After Migration |
|--------|-----|----------------------|
| Make RDS publicly accessible | DRS (in Huawei Cloud) needs to reach the RDS over the internet | Yes |
| Add IGW route to private route table | Public IP is assigned but traffic can't flow without IGW route | Yes |
| Add SG rule for port 3306 | DRS needs inbound MySQL access | Yes |
| Enable binary logging | Required for FULL_INCR_TRANS (incremental replication) | Optional |
| Set backup retention > 0 | Enables `log_bin=ON` (hidden requirement) | Optional |

## Step 1: Make RDS Publicly Accessible

```bash
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --publicly-accessible \
  --apply-immediately
```

Wait for the modification:

```bash
aws rds wait db-instance-available --region <region> \
  --db-instance-identifier <db-id>
```

**Important**: After the modification, the RDS endpoint DNS will resolve to a public IP. Verify:

```bash
nslookup <rds-endpoint>
# Should return a public IP (e.g. 3.x.x.x), not a private 10.x.x.x
```

## Step 2: Add IGW Route to Private Route Table (CRITICAL)

This is the **most commonly missed step**. Even with `PubliclyAccessible=true` and a public IP assigned to the RDS ENI, the RDS is unreachable from the internet if its subnet's route table doesn't have a route to the Internet Gateway.

### Diagnose

```bash
# Find the RDS subnet
aws rds describe-db-instances --region <region> \
  --db-instance-identifier <db-id> \
  --query 'DBInstances[0].DBSubnetGroup.Subnets[].SubnetIdentifier' \
  --output json

# Find the route table for that subnet
aws ec2 describe-route-tables --region <region> \
  --filters Name=vpc-id,Values=<vpc-id> \
  --query 'RouteTables[].{Id:RouteTableId,Assoc:Associations[].SubnetId,
    HasIGW:contains(Routes[].GatewayId,`igw-xxx`)}' \
  --output json
```

If the route table for the RDS subnet does **not** have a `0.0.0.0/0 → igw-xxx` route, add one:

```bash
aws ec2 create-route --region <region> \
  --route-table-id <private-rt-id> \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id <igw-id>
```

**Security note**: This temporarily makes all instances in the private subnet internet-accessible. This is acceptable for a migration window. Revert after cutover.

### Verify

```bash
# From Huawei Cloud ECS (or any internet host)
nc -z -w 10 <rds-endpoint> 3306 && echo OPEN || echo CLOSED
```

## Step 3: Add Security Group Rule

Allow MySQL (TCP 3306) from the internet (or restrict to the DRS node's EIP if known):

```bash
# Allow from anywhere (for migration window)
aws ec2 authorize-security-group-ingress --region <region> \
  --group-id <rds-sg-id> \
  --protocol tcp --port 3306 --cidr 0.0.0.0/0

# Or restrict to DRS EIP (more secure)
aws ec2 authorize-security-group-ingress --region <region> \
  --group-id <rds-sg-id> \
  --protocol tcp --port 3306 --cidr <drs-eip>/32
```

## Step 4: Enable Binary Logging

Binary logging is **required** for `FULL_INCR_TRANS` (incremental migration). Without it, only `FULL_TRANS` (one-time copy) is possible.

### The hidden requirement

On AWS RDS MySQL 8.0, setting `binlog_format=ROW` in a parameter group does **NOT** automatically enable binary logging. The `log_bin` system variable stays `OFF` unless **automated backups are enabled** (`backup_retention_period > 0`).

This is the sequence:

1. Create a custom DB parameter group with `binlog_format=ROW` and `binlog_row_image=FULL`
2. Apply the parameter group to the RDS instance
3. Set `backup_retention_period` to at least 1 (this enables `log_bin=ON`)
4. Reboot the RDS instance
5. Verify `log_bin=ON`

### Commands

```bash
# 1. Create custom parameter group
aws rds create-db-parameter-group --region <region> \
  --db-parameter-group-name drs-migration-params \
  --db-parameter-group-family mysql8.0 \
  --description "DRS migration - binlog enabled"

# 2. Set binlog parameters
aws rds modify-db-parameter-group --region <region> \
  --db-parameter-group-name drs-migration-params \
  --parameters "ParameterName=binlog_format,ParameterValue=ROW,ApplyMethod=IMMEDIATE" \
               "ParameterName=binlog_row_image,ParameterValue=FULL,ApplyMethod=IMMEDIATE"

# 3. Apply parameter group to RDS
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --db-parameter-group-name drs-migration-params \
  --apply-immediately

aws rds wait db-instance-available --region <region> \
  --db-instance-identifier <db-id>

# 4. Enable automated backups (THIS turns on log_bin)
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --backup-retention-period 1 \
  --apply-immediately

aws rds wait db-instance-available --region <region> \
  --db-instance-identifier <db-id>

# 5. Reboot to ensure all changes take effect
aws rds reboot-db-instance --region <region> \
  --db-instance-identifier <db-id>

aws rds wait db-instance-available --region <region> \
  --db-instance-identifier <db-id>
```

### Verify binlog is enabled

```bash
# From any MySQL client that can reach the RDS
mysql -h <rds-endpoint> -P 3306 -u <user> -p<password> \
  -e "SHOW VARIABLES LIKE 'log_bin'; SHOW VARIABLES LIKE 'binlog_format';"
```

Expected output:
```
log_bin         ON
binlog_format   ROW
```

If `log_bin` is still `OFF`, the `backup_retention_period` change hasn't taken effect. Wait and reboot again.

## Step 5: Verify End-to-End Connectivity

From the Huawei Cloud ECS:

```bash
# Install mysql client if needed
apt-get install -y mysql-client

# Test TCP connectivity
nc -z -w 10 <rds-endpoint> 3306 && echo OPEN || echo CLOSED

# Test MySQL connection
mysql -h <rds-endpoint> -P 3306 -u <user> -p<password> \
  -e "SELECT VERSION(); SHOW VARIABLES LIKE 'log_bin';"
```

## Cleanup Commands (Run After Migration Cutover)

```bash
# Remove temp SG rule
aws ec2 revoke-security-group-ingress --region <region> \
  --group-id <rds-sg-id> \
  --protocol tcp --port 3306 --cidr 0.0.0.0/0

# Remove IGW route from private route table
aws ec2 delete-route --region <region> \
  --route-table-id <private-rt-id> \
  --destination-cidr-block 0.0.0.0/0

# Disable public access
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --no-publicly-accessible \
  --apply-immediately

# (Optional) Revert backup retention to 0
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --backup-retention-period 0 \
  --apply-immediately

# (Optional) Revert to default parameter group
aws rds modify-db-instance --region <region> \
  --db-instance-identifier <db-id> \
  --db-parameter-group-name default.mysql8.0 \
  --apply-immediately
```

## Common Pitfalls

### Pitfall 1: "Port is closed despite PubliclyAccessible=true"

**Cause**: The RDS subnet's route table doesn't have an IGW route.

**Fix**: Add `0.0.0.0/0 → igw-xxx` to the route table associated with the RDS subnet.

### Pitfall 2: "log_bin is OFF despite binlog_format=ROW"

**Cause**: `backup_retention_period` is 0. AWS RDS only enables binary logging when automated backups are enabled.

**Fix**: Set `backup_retention_period` to at least 1, then reboot.

### Pitfall 3: "RDS modification times out"

**Cause**: Some RDS modifications require a reboot and can take 5-10 minutes.

**Fix**: Use `aws rds wait db-instance-available` with a sufficient timeout (300+ seconds).
