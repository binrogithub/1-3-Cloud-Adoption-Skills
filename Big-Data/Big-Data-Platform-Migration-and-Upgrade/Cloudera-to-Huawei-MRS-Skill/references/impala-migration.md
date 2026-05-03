# Impala Migration

## Impala to Spark SQL / Hive SQL

Impala is Cloudera's massively parallel processing (MPP) SQL engine. MRS does not include an Impala equivalent. The migration targets are:

1. **Spark SQL** (recommended for performance on Parquet data)
2. **Hive on Tez** (for Hive-compatible workloads)

## Syntax Conversion

### Data Types

| Impala Type | Spark SQL / Hive Type | Notes |
| --- | --- | --- |
| `TINYINT` | `TINYINT` | Same |
| `SMALLINT` | `SMALLINT` | Same |
| `INT` | `INT` | Same |
| `BIGINT` | `BIGINT` | Same |
| `FLOAT` | `FLOAT` | Same |
| `DOUBLE` | `DOUBLE` | Same |
| `DECIMAL(p,s)` | `DECIMAL(p,s)` | Same |
| `STRING` | `STRING` | Same |
| `VARCHAR(n)` | `VARCHAR(n)` | Same |
| `CHAR(n)` | `CHAR(n)` | Same |
| `BOOLEAN` | `BOOLEAN` | Same |
| `TIMESTAMP` | `TIMESTAMP` | Same |
| `DATE` | `DATE` | Same |
| `ARRAY<type>` | `ARRAY<type>` | Same |
| `MAP<k,v>` | `MAP<k,v>` | Same |
| `STRUCT<...>` | `STRUCT<...>` | Same |

### Functions

| Impala Function | Spark SQL Equivalent | Notes |
| --- | --- | --- |
| `NDV(expr)` | `APPROX_COUNT_DISTINCT(expr)` | Approximate distinct count |
| `GROUP_CONCAT(expr)` | `COLLECT_LIST(expr)` then `ARRAY_JOIN(arr, ',')` | Two-step in Spark |
| `IFNULL(a, b)` | `COALESCE(a, b)` | Use COALESCE |
| `ISNULL(expr)` | `expr IS NULL` | Syntax change |
| `ZEROIFNULL(expr)` | `COALESCE(expr, 0)` | Use COALESCE |
| `POSIX_REGEX` / `REGEXP` | `REGEXP_EXTRACT` / `REGEXP_REPLACE` | Different API |
| `SHA1()` / `SHA2()` | `SHA1()` / `SHA2()` | Same |
| `MURMUR_HASH()` | `HASH()` | Different algorithm |
| `FMOD()` | `MOD()` or `%` | Use MOD |
| `TRUNCATE()` | `ROUND(expr, -n)` | Different semantics for numeric truncation |
| `APPROX_COUNT_DISTINCT()` | `APPROX_COUNT_DISTINCT()` | Same |

### DDL Differences

| Impala DDL | Spark SQL / Hive Equivalent |
| --- | --- |
| `COMPUTE STATS <table>` | `ANALYZE TABLE <table> COMPUTE STATISTICS` |
| `SHOW TABLE STATS <table>` | `DESCRIBE EXTENDED <table>` |
| `SHOW PARTITIONS <table>` | `SHOW PARTITIONS <table>` (same) |
| `INVALIDATE METADATA` | `MSCK REPAIR TABLE <table>` or `REFRESH TABLE <table>` |
| `INVALIDATE METADATA <table>` | `REFRESH TABLE <table>` |
| `REFRESH <table>` | `REFRESH TABLE <table>` |
| `ALTER TABLE <t> RECOVER PARTITIONS` | `MSCK REPAIR TABLE <t>` |

### Query Hints

Impala query hints (`/* +SHUFFLE */`, `/* +NOSHUFFLE */`, `/* +CLUSTERED */`) are not supported in Spark SQL. Remove them and rely on Spark's query optimizer, or use Spark-specific hints:

```sql
-- Impala
SELECT /* +SHUFFLE */ ... FROM t1 JOIN t2 ON ...

-- Spark SQL
SELECT /* +REPARTITION(100) */ ... FROM t1 JOIN t2 ON ...
```

## Performance Considerations

### Impala vs. Spark SQL Performance

- **Impala** is optimized for low-latency MPP queries on small-to-medium result sets
- **Spark SQL** is optimized for throughput on large-scale data processing
- For interactive/BI queries, Spark SQL may be slower than Impala
- For ETL/batch processing, Spark SQL is comparable or faster

### Mitigation Strategies

1. **Use columnar formats** (Parquet/ORC) with proper partitioning
2. **Leverage Spark caching** for frequently queried tables:
   ```sql
   CACHE TABLE finance_dw.dim_branch;
   ```
3. **Optimize partition pruning** by ensuring partition columns are used in WHERE clauses
4. **Consider materialized views** for expensive aggregations
5. **Use Spark SQL result caching** for repeated queries

## Impala-Specific Features Without Direct Equivalent

| Feature | Migration Path |
| --- | --- |
| Impala Daemon metadata cache | Spark SQL reads from Metastore on each query |
| Impala admission control | Use YARN queues for resource management |
| Impala query profiles | Use Spark UI for query profiling |
| Impala `LOAD DATA` | Use `hdfs dfs -put` or `obsutil cp` then `MSCK REPAIR` |
| Kudu integration | Use HBase or CloudTable on Huawei Cloud |
| Impala UDFs | Rewrite as Spark UDFs |
