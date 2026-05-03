# Workflow Reference

## Local Source Demo

Run a local source simulation when no real Teradata environment is available:

```bash
./scripts/start_source_cluster.sh
./scripts/init_finance_demo.sh
./scripts/run_reports.sh
```

The source simulator creates:

- 2,000 customers
- 8,000 accounts
- 120,000 transactions
- 728,000 daily balances
- 1,500 loan snapshots
- finance reports under `reports/output/`

## DWS Cluster

Create a minimal DWS cluster when requested and credentials are available:

```bash
export CLOUD_SDK_AK="$AK"
export CLOUD_SDK_SK="$SK"
./scripts/create_huawei_dws_min_cluster.sh
```

Default values:

- region: `la-south-2`
- project_id: `89a76cc1484440b38810ecb9e3b5c0d7`
- cluster name: `dws-finance-demo-min3`
- node count: 3
- port: 8000
- database user: `dbadmin`

Configure connection:

```bash
export DWS_PASSWORD='<admin-password>'
./scripts/configure_dws_env.sh
```

If auto-discovery is not possible, edit `config/dws.env` manually.

## Migration

Scan Teradata SQL before conversion when source scripts are available:

```bash
./scripts/scan_teradata_compatibility.py /path/to/teradata/sql
```

Outputs:

- `reports/teradata_compatibility_scan.csv`
- `reports/teradata_compatibility_scan.md`

Run:

```bash
./scripts/migrate_td_to_dws.sh
```

This performs:

1. `export_td_data.sh`
2. `load_dws_data.sh`
3. `run_dws_reports.sh`
4. `validate_dws_migration.sh`

Success requires:

```text
DWS migration validation passed.
```

## Optimization

Run:

```bash
./scripts/optimize_dws.sh
./scripts/create_partitioned_facts.sh
./scripts/check_dws_skew.sh
./scripts/refresh_dws_marts_incremental.sh 202506 2025-06-30
./scripts/run_dws_reports_optimized.sh
./scripts/validate_dws_optimized_reports.sh
```

Success requires:

```text
Optimized DWS report validation passed.
```

## Report and Resource Management

Generate a delivery report:

```bash
./scripts/generate_migration_report.sh
```

DWS lifecycle:

```bash
./scripts/manage_dws_cluster.sh status
./scripts/manage_dws_cluster.sh stop
./scripts/manage_dws_cluster.sh start
```

Deletion must be explicit:

```bash
./scripts/manage_dws_cluster.sh delete --yes --confirm-name dws-finance-demo-min3
```

## OBS Parallel Load Template

For production-scale data paths:

```bash
cp config/obs.env.example config/obs.env
vi config/obs.env
./scripts/prepare_obs_parallel_load.sh
```

This uploads `data/export/*.csv` to OBS and generates `sql/dws/08_load_from_obs.generated.sql`. Treat the generated SQL as a reviewed template, not as blindly executable SQL.
