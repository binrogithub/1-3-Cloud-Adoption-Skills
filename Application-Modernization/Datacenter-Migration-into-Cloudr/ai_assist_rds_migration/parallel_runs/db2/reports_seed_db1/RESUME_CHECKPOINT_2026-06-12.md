# RDS DRS Migration Resume Checkpoint

Generated at: 2026-06-12 10:04:36 CST
Workspace: /root/ai_assit_migration/ai_assist_rds_migration
Region: na-mexico-1

## Current Migration Context
- Source RDS instance: e327af04e9204e1e867179f9df2057d7in01
- Target RDS instance: 0f07fd696084478cb58752582bf3e802in01
- DRS active job (use this one): aafd3500-2144-4855-bb53-6bc5932jb101
- Network mode: EIP
- DRS job flow status (last known): CONFIGURATION (not started)

## Network / Whitelist State (already applied)
- Source SG: 3994e159-9592-4aa2-892b-79439f0e20e3
- Added ingress rules (tcp/3306, description: for rds migration):
  - 101.46.208.128/32 (rule id: 418f12f8-ecd5-4a5d-8cc9-11f226468d07)
  - 192.168.0.49/32 (rule id: 2e784089-0167-476f-9e23-bf7ae60c4ef6)

## Validation Status
- reports/drs_job_create_report.json: SUCCESS
- reports/connection_test_report.json: SUCCESS (source and target both SUCCESS)
- reports/precheck_report.json: FAILED

## Blocking Items (Precheck)
- srcDbBinlogIsOff: MYSQL_SOURCE_DB_PRIVILEGES_IS_NOT_ENOUGH_FOR_INCRE
- srcGtidStatusCheck: MYSQL_SOURCE_DB_PRIVILEGES_IS_NOT_ENOUGH_FOR_INCRE
- srcDbPrivilegesIsEnoughForIncre: MYSQL_SOURCE_DB_PRIVILEGES_IS_NOT_ENOUGH_FOR_INCRE
- Warnings:
  - dstDbDiskSize: DST_DB_DISK_SIZE_UP_ALARM
  - isUserRequireSslLink: UNAVAILABLE_TO_QUERY_SSL_INFO

## Next Step To Resume
1) Grant source DB incremental migration permissions for migration user (for example sms_sync), then run FLUSH PRIVILEGES.
2) Re-run precheck only:

```bash
cd /root/ai_assit_migration/ai_assist_rds_migration
set -a
source .env.runtime
set +a
export MIGRATION_BASE_DIR=/root/ai_assit_migration/ai_assist_rds_migration
export HW_ACCESS_KEY="$TGT_HW_ACCESS_KEY"
export HW_SECRET_KEY="$TGT_HW_SECRET_KEY"
export HW_PROJECT_ID="$TGT_HW_PROJECT_ID"
export HW_REGION="na-mexico-1"
export SRC_DB_HOST="119.8.0.182"
export SRC_DB_PORT="3306"
export TGT_DB_HOST="94.74.76.132"
export TGT_DB_PORT="3306"
export DRY_RUN="false"
export SKIP_DB_TCP_CHECK="true"
export ALLOW_DRS_ONLY_PRECHECK="true"
export PRECHECK_POLL_SEC="10"
export PRECHECK_MAX_WAIT_SEC="1800"
python3 scripts/06_run_precheck.py
```

3) If precheck passes, request approval and start migration:
- `touch approvals/APPROVED_START_DRS_JOB`
- `python3 scripts/07_start_migration.py`

## Note
No destructive cleanup was executed. Old job id `ab704a6a-9586-4ffb-8390-f5e910cjb101` still exists and should be ignored.
