# Spark Migration

## Spark Version Mapping

| Cloudera Spark Version | MRS Spark Version | Notes |
| --- | --- | --- |
| Spark 2.4 (CDH 6.x) | Spark 3.3.1 (MRS 3.5.0) | Major version upgrade; some API changes |
| Spark 3.0-3.2 (CDH 7.x) | Spark 3.3.1 (MRS 3.5.0) | Minor version upgrade; mostly compatible |
| Spark 3.3+ (CDP) | Spark 3.3.1 (MRS 3.5.0) | Near-compatible |

## spark-submit Migration

### Source (Cloudera)

```bash
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 10 \
  --executor-memory 8g \
  --executor-cores 4 \
  --driver-memory 4g \
  --jars /path/to/extra/jars \
  --class com.example.FinanceJob \
  /path/to/app.jar \
  arg1 arg2
```

### Target (MRS)

```bash
# Run as omm user with client environment
su - omm -c 'source /opt/Bigdata/client/bigdata_env && \
  spark-submit \
    --master yarn \
    --deploy-mode cluster \
    --num-executors 10 \
    --executor-memory 8g \
    --executor-cores 4 \
    --driver-memory 4g \
    --jars /opt/Bigdata/client/Spark/spark/jars/<extra-jars> \
    --class com.example.FinanceJob \
    /path/to/app.jar \
    arg1 arg2'
```

### Key Changes

1. **Always source the client environment:**
   ```bash
   source /opt/Bigdata/client/bigdata_env
   ```

2. **Run as `omm` user** (Hadoop service account):
   ```bash
   su - omm -c 'source /opt/Bigdata/client/bigdata_env && <command>'
   ```

3. **Update HDFS paths to OBS paths** in application code:
   - `hdfs://namenode:8020/path` -> `obs://<bucket>/<path>`
   - Or keep HDFS paths if using MRS HDFS

4. **Update dependency JARs:**
   - MRS Spark JARs are in `/opt/Bigdata/client/Spark/spark/jars/`
   - User JARs should be uploaded to HDFS or OBS
   - Remove Cloudera-specific JARs (e.g., `cdh-spark-` prefixed)

5. **Spark configuration:**
   - MRS Spark config is in `/opt/Bigdata/client/Spark/spark/conf/`
   - Do not modify core MRS config; use `--conf` flags instead

## Spark SQL Migration

### Interactive

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && \
  spark-sql --master yarn \
    --executor-memory 4g \
    --executor-cores 2 \
    --num-executors 3'
```

### Batch

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && \
  spark-sql --master yarn \
    --executor-memory 4g \
    --executor-cores 2 \
    --num-executors 3 \
    -f /path/to/script.sql'
```

### Important: Use spark-sql, Not beeline, for Parquet Queries

MRS Hive 3.1's Parquet reader does not support dictionary-encoded Parquet from Spark 3.x. Always use `spark-sql` for querying Spark-generated Parquet tables.

## PySpark Migration

### Source

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("FinanceJob") \
    .enableHiveSupport() \
    .getOrCreate()
```

### Target (MRS)

The same code works on MRS. Key changes:

1. **HDFS paths -> OBS paths** in read/write operations
2. **OBS access configuration:**

```python
spark = SparkSession.builder \
    .appName("FinanceJob") \
    .enableHiveSupport() \
    .config("fs.obs.impl", "org.apache.hadoop.fs.obs.OBSFileSystem") \
    .config("fs.obs.endpoint", "obs.<region>.myhuaweicloud.com") \
    .config("fs.obs.access.key", "<ak>") \
    .config("fs.obs.secret.key", "<sk>") \
    .getOrCreate()
```

Or use MRS agency (recommended for production):

```python
spark = SparkSession.builder \
    .appName("FinanceJob") \
    .enableHiveSupport() \
    .config("fs.obs.impl", "org.apache.hadoop.fs.obs.OBSFileSystem") \
    .config("fs.obs.security.provider", "com.obs.services.InternalObsSecurityProvider") \
    .getOrCreate()
```

## Scala/Java Spark Migration

Same principles as PySpark:

1. Update HDFS paths to OBS
2. Update dependency versions to match MRS Spark
3. Rebuild JARs against MRS Spark classpath
4. Remove Cloudera-specific dependencies

## Spark Streaming Migration

| Cloudera Component | MRS Equivalent |
| --- | --- |
| Spark Streaming + Kafka | Spark Structured Streaming + Kafka on MRS |
| Spark Streaming + Flume | Spark Structured Streaming + Kafka (replace Flume) |

Checkpoint locations need to be updated from HDFS to OBS or MRS HDFS.
