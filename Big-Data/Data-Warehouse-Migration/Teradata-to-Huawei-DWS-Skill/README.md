# Teradata to Huawei DWS Skill

This reusable skill package helps build, run, and adapt a Teradata-to-Huawei-Cloud-DWS migration demo and migration toolkit for finance analytics workloads.

It covers a complete migration lifecycle:

- Local Teradata-source simulation with an MPP SQL workload
- Huawei Cloud DWS minimal cluster creation
- Source data export, DWS schema creation, data loading, and report migration
- Row-count and report-result parity validation
- DWS optimization with column-store reporting marts, partitioned fact copies, skew checks, and incremental refresh
- Teradata SQL/BTEQ/TPT compatibility scanning
- OBS upload and DWS OBS/GDS-style parallel load templates
- Migration report generation and DWS demo resource lifecycle management

## Included Assets

- [SKILL.md](./SKILL.md): Agent-facing workflow, trigger description, and core operating rules
- [references/](./references): End-to-end workflow and production migration notes
- [scripts/](./scripts): Project scaffolding script for copying the runnable template into a workspace
- [assets/project-template/](./assets/project-template): Runnable migration demo, SQL, scripts, config examples, and documentation
- [agents/](./agents): Agent UI metadata

## Typical Use

- Build a Teradata-to-DWS migration demo for a finance data warehouse
- Migrate analytical tables and report SQL into Huawei Cloud DWS
- Validate source and target row counts and report outputs
- Add DWS performance optimizations after migration
- Scan Teradata SQL for DWS compatibility risks before conversion
- Prepare an OBS-based production loading path to replace client-side CSV loading

## Quick Start

Copy the runnable project template into a workspace:

```bash
python3 scripts/scaffold_project.py --target /path/to/workspace
cd /path/to/workspace
```

Run the local source demo:

```bash
./scripts/start_source_cluster.sh
./scripts/init_finance_demo.sh
./scripts/run_reports.sh
```

Configure DWS and run migration:

```bash
cp config/dws.env.example config/dws.env
vi config/dws.env
./scripts/migrate_td_to_dws.sh
```

Run optimization and generate the migration report:

```bash
./scripts/optimize_dws.sh
./scripts/create_partitioned_facts.sh
./scripts/check_dws_skew.sh
./scripts/run_dws_reports_optimized.sh
./scripts/validate_dws_optimized_reports.sh
./scripts/generate_migration_report.sh
```

## Security Notes

Do not commit credentials, connection strings, customer data, `config/*.env`, `.secrets/`, or generated export/report data. The template `.gitignore` excludes those paths by default.

