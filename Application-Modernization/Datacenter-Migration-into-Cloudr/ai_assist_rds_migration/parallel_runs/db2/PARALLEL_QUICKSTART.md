# DB2 Parallel Migration Quickstart

This directory is an isolated copy for a second migration task.

Paths:
- DB1 base: `/root/ai_assit_migration/ai_assist_rds_migration`
- DB2 base: `/root/ai_assit_migration/ai_assist_rds_migration/parallel_runs/db2`

Notes:
- `reports/`, `logs/`, `approvals/` in this DB2 folder are reset and independent.
- Copied old state is kept in `*_seed_db1` folders only for reference.
- `configs/migration.yaml` has a unique `job_name_prefix: task-migration-mysql-db2`.

## 1) Update DB2 parameters

Edit these files in DB2 base:
- `.env` (or set env vars directly)
- `.env.runtime` (if you use runtime key switching)
- `configs/migration.yaml` (source/target instance info, scope, VPC/SG)

At minimum, ensure:
- `SRC_DB_*` points to DB2 source.
- `TGT_DB_*` points to DB2 target.
- `HW_*` is the account that creates/runs DRS for DB2.

## 2) Run DB2 flow in terminal B

```bash
cd /root/ai_assit_migration/ai_assist_rds_migration/parallel_runs/db2
export MIGRATION_BASE_DIR=/root/ai_assit_migration/ai_assist_rds_migration/parallel_runs/db2

set -a
source .env
set +a

bash scripts/00_env_check.sh
python3 scripts/01_db_precheck.py
python3 scripts/02_generate_drs_payload.py
touch approvals/APPROVED_CREATE_DRS_JOB
python3 scripts/03_create_drs_job.py
python3 scripts/04_wait_drs_job_ready.py
python3 scripts/05_test_connection.py
python3 scripts/06_run_precheck.py
touch approvals/APPROVED_START_DRS_JOB
python3 scripts/07_start_migration.py
python3 scripts/08_monitor_migration.py
```

## 3) Keep DB1 running in terminal A

For DB1, continue using:

```bash
cd /root/ai_assit_migration/ai_assist_rds_migration
export MIGRATION_BASE_DIR=/root/ai_assit_migration/ai_assist_rds_migration
```

Do not mix DB1 and DB2 commands in the same terminal session without resetting `MIGRATION_BASE_DIR`.
