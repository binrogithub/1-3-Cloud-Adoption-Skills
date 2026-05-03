---
name: teradata-to-huawei-dws
description: Build, run, or adapt a Teradata-to-Huawei-Cloud-DWS migration demo or migration toolkit, especially for finance analytics workloads. Use when Codex needs to scaffold a local Teradata-source simulation, create a minimal Huawei Cloud DWS cluster, migrate schemas/data/report SQL to DWS, validate row counts and report parity, optimize DWS tables/marts, generate migration reports, or manage DWS demo resources. Also use for real Teradata export planning through JDBC/BTEQ/TPT into DWS.
---

# Teradata to Huawei DWS

Use this skill to create and operate a complete Teradata-to-DWS finance migration demo. The bundled project template includes scripts for:

- local Teradata-source simulation with Citus/PostgreSQL (`tdsim`)
- Huawei Cloud DWS 3-node cluster creation
- source export, DWS DDL creation, CSV load, report migration, parity validation
- DWS optimization with mart tables, partitioned fact copies, skew checks, incremental refresh
- Teradata SQL/BTEQ/TPT compatibility scanning for DWS migration risks
- OBS upload and DWS OBS/GDS-style parallel load templates for production-scale migrations
- migration report generation and DWS resource lifecycle commands

## Start Here

1. Scaffold the project into the user's working directory:

```bash
python3 /root/.codex/skills/teradata-to-huawei-dws/scripts/scaffold_project.py --target .
```

2. Read only the reference needed for the current task:

- `references/workflow.md` for end-to-end demo/migration commands.
- `references/production-notes.md` for real Teradata, OBS/GDS loading, governance, and production hardening.

3. Never write AK/SK, database passwords, or DWS connection strings into tracked files or final answers. Use `config/dws.env`, environment variables, or `.secrets/`; these paths are ignored by the template.

## Core Workflow

For a local demo:

```bash
./scripts/start_source_cluster.sh
./scripts/init_finance_demo.sh
./scripts/run_reports.sh
```

For DWS migration after `config/dws.env` is configured:

```bash
./scripts/scan_teradata_compatibility.py /path/to/teradata/sql
./scripts/migrate_td_to_dws.sh
./scripts/optimize_dws.sh
./scripts/run_dws_reports_optimized.sh
./scripts/validate_dws_optimized_reports.sh
./scripts/generate_migration_report.sh
```

For production-style OBS loading, configure `config/obs.env`, then run:

```bash
./scripts/prepare_obs_parallel_load.sh
```

Review generated `sql/dws/08_load_from_obs.generated.sql` before execution; syntax and credential strategy vary by DWS version and security policy.

For Huawei Cloud DWS cluster creation:

```bash
export CLOUD_SDK_AK="$AK"
export CLOUD_SDK_SK="$SK"
./scripts/create_huawei_dws_min_cluster.sh
./scripts/configure_dws_env.sh
```

Use `./scripts/manage_dws_cluster.sh status|start|stop` for lifecycle operations. Delete requires `delete --yes --confirm-name <cluster-name>`.

## Important Constraints

- Teradata does not have an open-source database cluster distribution. For a local demo, use the bundled `tdsim` Citus/PostgreSQL source simulator. For real Teradata, use the JDBC exporter or replace the export layer with BTEQ/TPT.
- The local host may have a broken `psql`; the template defaults to containerized `psql` for DWS access.
- DWS standard clusters require an existing VPC, subnet, and security group; the bundled DWS creation script can create/reuse demo networking.
- Validate before declaring success: row counts, report CSV parity, optimized report parity, and skew checks should pass.
- For production-scale data, prefer OBS/GDS parallel loading over client-side `\copy`.

## Template Contents

The project template is under `assets/project-template`. It contains the runnable scripts, SQL, config examples, and docs used by the demo. Copy it with `scripts/scaffold_project.py`; do not edit the skill template in place unless the user is updating the skill itself.
