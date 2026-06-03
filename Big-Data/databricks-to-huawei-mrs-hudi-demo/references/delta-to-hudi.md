# Delta to Hudi Replacement

The original Databricks process uses Delta table semantics. The Huawei MRS replacement uses Apache Hudi on OBS.

## Bronze Mapping

Original intent:

- Read raw CDC JSON.
- Normalize `after.*` for insert/update/read.
- For deletes, use `before.*`.
- Add CDC metadata.
- Persist as bronze Delta.

Hudi replacement:

- Write `COPY_ON_WRITE` Hudi table.
- `operation=upsert`.
- `recordkey.field=id`.
- `precombine.field=_cdc_timestamp`.
- Partition by `_cdc_date`.
- Hive sync disabled for minimal smoke.

## Silver Mapping

Original intent:

- Read bronze.
- Deduplicate by `id` using latest CDC timestamp.
- Apply deletes.
- Merge into silver Delta.

Hudi replacement:

- Read bronze Hudi.
- Window by `id`, order by descending `_cdc_timestamp`.
- Split latest records into upserts and deletes.
- Write upserts with `operation=upsert`.
- Write deletes with `operation=delete`.
- `recordkey.field=id`.
- `precombine.field=_cdc_timestamp`.
- Partition by `tenant_id`.

## Important MRS Compatibility Notes

- Keep `hoodie.datasource.hive_sync.enable=false` for the first minimal PoC. The MRS smoke failed when Hive sync was enabled, even after Hudi write stages completed.
- Add Hudi bundle through Spark submit `--jars obs://docktest/jobs/jars/hudi-spark3.3-bundle_2.12-0.15.0.jar`.
- Use Spark 3.3 compatible bundle: `hudi-spark3.3-bundle_2.12-0.15.0.jar`.
- Set `fs.obs.endpoint=obs.la-south-2.myhuaweicloud.com` in MRS job properties.
- Ensure `${DEMO_BUCKET}` is expanded before submitting MRS jobs; an unexpanded jar path caused an earlier failure.

## Future Hive/SQL Visibility

After the Hudi write path is stable, add one of:

- Hudi Hive sync with properly configured Hive Metastore and MRS component configs.
- Explicit Hive external table DDL over Hudi paths.
- A separate validation SparkSQL job that reads Hudi paths directly.
