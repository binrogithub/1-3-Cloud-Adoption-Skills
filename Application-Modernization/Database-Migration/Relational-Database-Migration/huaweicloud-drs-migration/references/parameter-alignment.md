# Parameter Alignment for DRS Migration

DRS precheck validates that source and target database parameters are compatible. Mismatches on critical parameters will **FAIL** and block the job start. Mismatches on warning parameters will generate **ALARMS** but allow the job to proceed.

## Parameter Categories

### FAILED (blocks migration)

| Parameter | AWS RDS MySQL 8.0 default | Huawei RDS MySQL 8.0 default | Resolution |
|-----------|--------------------------|------------------------------|------------|
| `transaction_isolation` | REPEATABLE-READ | READ-COMMITTED | Custom param template on target |
| `innodb_strict_mode` | ON | OFF | Custom param template on target |
| `lower_case_table_names` | 0 (Linux) | 1 | **ForceNew — recreate RDS** |
| `log_bin` (source) | OFF (if backup_retention=0) | N/A | Enable on source (see aws-rds-preparation.md) |

### ALARM (warnings, non-blocking)

| Parameter | Note |
|-----------|------|
| `explicit_defaults_for_timestamp` | Different values (ON vs OFF). Warning only. |
| `sql_mode` | AWS uses `NO_ENGINE_SUBSTITUTION`, Huawei uses empty. Warning only. |
| `gtid_mode` | GTID OFF on source. DRS uses binlog position instead. Alarm only. |
| `dstDbDiskSize` | Target disk size vs source data size. Informational. |

## Procedure: Create Custom Parameter Template

### Step 1: Identify mismatches

Connect to both databases and compare:

```bash
# Source (AWS RDS)
mysql -h <source-endpoint> -u <user> -p<password> -e "
  SHOW VARIABLES LIKE 'transaction_isolation';
  SHOW VARIABLES LIKE 'innodb_strict_mode';
  SHOW VARIABLES LIKE 'lower_case_table_names';
  SHOW VARIABLES LIKE 'explicit_defaults_for_timestamp';
  SHOW VARIABLES LIKE 'sql_mode';
"

# Target (Huawei RDS) — from Huawei ECS
mysql -h <target-ip> -u root -p<password> -e "
  SHOW VARIABLES LIKE 'transaction_isolation';
  SHOW VARIABLES LIKE 'innodb_strict_mode';
  SHOW VARIABLES LIKE 'lower_case_table_names';
  SHOW VARIABLES LIKE 'explicit_defaults_for_timestamp';
  SHOW VARIABLES LIKE 'sql_mode';
"
```

### Step 2: Create custom parameter template on Huawei Cloud

```bash
hcloud RDS CreateConfiguration --cli-region=<region> \
  --project_id=<pid> \
  --name=drs-migration-mysql80 \
  --description="Custom MySQL 8.0 params for DRS migration" \
  --datastore.type=MySQL \
  --datastore.version=8.0 \
  --values.transaction_isolation=REPEATABLE-READ \
  --values.innodb_strict_mode=ON \
  --values.explicit_defaults_for_timestamp=ON \
  --cli-output=json
```

Note the `id` from the response (e.g. `86051aa9a79346e1bbef11332700df3epr01`).

### Step 3: Apply to RDS instance

```bash
hcloud RDS EnableConfiguration --cli-region=<region> \
  --config_id=<template-id> \
  --project_id=<pid> \
  --instance_ids.1=<rds-instance-id> \
  --cli-output=json
```

If `restart_required: true`, reboot the RDS:

```bash
hcloud RDS StartInstanceRestartAction --cli-region=<region> \
  --instance_id=<rds-instance-id> \
  --restart=true \
  --cli-output=json
```

### Step 4: Verify parameters took effect

```bash
# Check via MySQL connection
mysql -h <target-ip> -u root -p<password> -e "
  SHOW VARIABLES LIKE 'transaction_isolation';
  SHOW VARIABLES LIKE 'innodb_strict_mode';
"
```

## The lower_case_table_names Trap

### The problem

- AWS RDS MySQL on Linux: `lower_case_table_names = 0` (case-sensitive)
- Huawei Cloud RDS MySQL 8.0: `lower_case_table_names = 1` (case-insensitive, **default**)
- On MySQL 8.0, this parameter **cannot be changed after initialization**
- In the `huaweicloud_rds_instance` Terraform resource, it is `ForceNew` — changing it destroys and recreates the RDS

### Impact

- DRS precheck will **FAIL** with `DB_TBL_NAME_CASE_SENSITIVE_INCONSISTENCY_FOR_UP`
- The migration job **cannot start** until this is resolved
- For WordPress and most web apps, this is functionally irrelevant (they use lowercase table names)
- But DRS enforces the check regardless

### Resolution: Recreate RDS with lower_case_table_names=0

#### Option A: In Terraform (recommended)

Add to the `huaweicloud_rds_instance` resource:

```hcl
resource "huaweicloud_rds_instance" "demo_db" {
  name                   = "demo-db"
  lower_case_table_names = "0"    # Match AWS RDS (case-sensitive)
  param_group_id         = "<custom-template-id>"

  # ... rest of config
}
```

Terraform will plan to destroy and recreate the RDS. Apply with caution — **this deletes the existing RDS and all its data**.

#### Option B: Delete and recreate manually

```bash
# Delete existing RDS
hcloud RDS DeleteInstance --cli-region=<region> \
  --instance_id=<id> --project_id=<pid>

# Create new RDS with lower_case_table_names=0
# (via Terraform or hcloud CLI)
```

### Handling the DRS job recreation

When the RDS is recreated (new instance ID), any existing DRS job that references the old instance ID becomes invalid. Since `instance_id` is `NonUpdatable` in `huaweicloud_drs_job_v5`, you must:

1. **Force terminate** the DRS job:
   ```bash
   hcloud DRS BatchDeleteJobs --cli-region=<region> \
     --project_id=<pid> \
     --jobs.1.job_id=<job_id> \
     --jobs.1.delete_type=force_terminate \
     --cli-output=json
   ```

2. **Delete** the DRS job:
   ```bash
   hcloud DRS BatchDeleteJobs --cli-region=<region> \
     --project_id=<pid> \
     --jobs.1.job_id=<job_id> \
     --jobs.1.delete_type=delete \
     --cli-output=json
   ```

3. **Remove from Terraform state**:
   ```bash
   terraform state rm huaweicloud_drs_job_v5.<resource_name>
   ```

4. **Apply Terraform** — the RDS will be recreated, and the DRS job will be created with the new instance ID.

## Parameter Template Reference

### Huawei Cloud RDS MySQL 8.0 default values (that differ from AWS)

| Parameter | Huawei Default | AWS Default | Migration Fix |
|-----------|---------------|-------------|---------------|
| `transaction_isolation` | READ-COMMITTED | REPEATABLE-READ | Set to REPEATABLE-READ |
| `innodb_strict_mode` | OFF | ON | Set to ON |
| `explicit_defaults_for_timestamp` | OFF | ON | Set to ON (alarm only) |
| `lower_case_table_names` | 1 | 0 | Set to 0 at creation (ForceNew) |
| `sql_mode` | (empty) | NO_ENGINE_SUBSTITUTION | Alarm only |

### Creating the template via hcloud CLI

```bash
hcloud RDS CreateConfiguration --cli-region=<region> \
  --project_id=<pid> \
  --name=<template-name> \
  --description="<description>" \
  --datastore.type=MySQL \
  --datastore.version=8.0 \
  --values.transaction_isolation=REPEATABLE-READ \
  --values.innodb_strict_mode=ON \
  --values.explicit_defaults_for_timestamp=ON \
  --cli-output=json
```

### Applying the template

```bash
hcloud RDS EnableConfiguration --cli-region=<region> \
  --config_id=<template-id> \
  --project_id=<pid> \
  --instance_ids.1=<rds-id> \
  --cli-output=json
```

### Referencing in Terraform

```hcl
resource "huaweicloud_rds_instance" "demo_db" {
  param_group_id = "<template-id>"
  # ...
}
```
