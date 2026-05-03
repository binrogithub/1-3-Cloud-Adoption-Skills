# Production Notes

## Real Teradata Source

The local `tdsim` source is for demos only. For a real Teradata source, replace the export layer:

- JDBC: `scripts/export_real_teradata_jdbc.py`
- BTEQ/TPT: use native Teradata export tooling
- Large tables: unload by date partitions or business keys

Do not treat Citus/PostgreSQL syntax as Teradata syntax. Use the template to model workload shape and validation flow.

## DWS Loading

Client-side `\copy` is acceptable for demo data. For production, prefer:

- Teradata export to OBS
- DWS parallel load from OBS/GDS/external table patterns
- partition-level load and validation
- retryable load batches with control tables

The template includes:

- `config/obs.env.example`
- `scripts/upload_export_to_obs.sh`
- `scripts/prepare_obs_parallel_load.sh`
- `scripts/generate_dws_obs_load_sql.py`
- `docs/obs_parallel_load.md`

Generated OBS load SQL is intentionally commented and must be adapted to the target DWS version, agency/AKSK policy, and external table capability.

## SQL Conversion Risk Areas

Scan Teradata SQL with:

```bash
./scripts/scan_teradata_compatibility.py /path/to/teradata/sql --fail-on-high
```

The scanner flags:

- `PRIMARY INDEX`, `PARTITION BY`, `COLLECT STATISTICS`
- `QUALIFY`
- `VOLATILE TABLE`
- `TOP`, `SAMPLE`
- `FORMAT`, `COMPRESS`
- macros, stored procedures, BTEQ commands
- Teradata-specific date/time functions and UDFs

Use `scripts/convert_teradata_sql_to_dws.py` only as a helper; manually review complex SQL.

## DWS Optimization

Default demo choices:

- facts: column store, middle compression, `DISTRIBUTE BY HASH(customer_id)`
- dimensions: column store, middle compression, `DISTRIBUTE BY REPLICATION`
- report marts: CTAS column store, refreshed full or incrementally
- partitioned copies: date-key range partitioning for fact tables

Review distribution keys against actual workloads. Run `scripts/check_dws_skew.sh` and inspect `reports.distribution_skew_report`.

## Validation

For demos:

- full row counts
- report CSV parity
- optimized report parity

For production:

- table count/sum/min/max
- partition checksum
- sampled row-level compare
- report metric thresholds
- execution plan capture

## Security

Never commit:

- AK/SK
- DWS passwords
- `config/dws.env`
- `.secrets/`
- raw customer data

Rotate any credentials that appear in chat logs, shell history, or screenshots.
