# Performance Tuning

Use this reference when the user asks how to accelerate deployment, throughput, or latency tuning for Kafka + GaussDB.

## What earlier implementations already proved useful

These techniques appeared repeatedly in prior code and operational notes and are generic enough to keep:

- Preflight checks for Kafka broker reachability and GaussDB login before any benchmark or demo
- Explicit topic durability settings instead of relying on broker defaults
- Manual partition assignment for stable worker ownership when rebalance churn is harmful
- Manual offset commit only after the database transaction commits
- Producer batching with `linger.ms` and compression
- Bulk writes into GaussDB using JDBC batching or COPY-compatible paths
- Multi-host DB distribution for parallel read or load tests

## First-pass tuning defaults

For a generic Java service:

Kafka producer:
- `acks=all`
- `enable.idempotence=true`
- `compression.type=lz4`
- `linger.ms=10..20`
- `batch.size=131072`
- `delivery.timeout.ms=120000`

Kafka consumer:
- `enable.auto.commit=false`
- `max.poll.records=500..5000` depending on row size and DB batch size
- one consumer thread per owned partition lane

GaussDB:
- use a connection pool
- group writes into batches
- prefer prepared batches for mixed OLTP writes
- prefer COPY-style ingestion for append-heavy bulk flows

## When to use JDBC batch vs COPY-style loading

Use JDBC batch when:
- rows are tied to transactional business logic
- records contain text fields that are awkward to escape for COPY
- partial business validation happens per record

Use COPY-style loading when:
- rows are append-heavy
- transformations are simple
- payload escaping is controlled
- bulk ingestion speed matters more than per-row branching

## Partition sizing heuristic

Start with:

`required_partitions = ceil(target_tps * avg_handler_ms / 1000 / utilization_target)`

Where:
- `avg_handler_ms` is average end-to-end processing time per message for a single partition lane
- `utilization_target` is typically `0.6` to `0.75`

Example:
- target `12000 TPS`
- average per-message lane time `3 ms`
- utilization target `0.7`

Then:
- `12000 * 3 / 1000 / 0.7 ≈ 51.4`
- start around `54` or `60` partitions

This is only a starting point. Validate with a benchmark.

## GaussDB write-path guidance

For high-contention transaction state:
- serialize by business conflict key through Kafka partitioning
- keep DB transactions short
- update only the rows needed for the current aggregate
- avoid large fan-out SQL inside the consumer hot path

For high-throughput event ingest:
- batch inserts
- separate state mutation tables from audit/event history tables
- avoid secondary indexes you do not actively query

## Benchmark order

Use this order:
1. Connectivity and topic configuration validation
2. Kafka produce-only benchmark
3. Kafka consume-only benchmark
4. GaussDB insert-only benchmark
5. End-to-end benchmark
6. Reconciliation and duplicate replay test

If step 4 is already saturated, step 5 will not recover it.

## Metrics to require

- producer send rate
- producer error count
- consumer lag
- consumer commit latency
- DB batch latency
- duplicate event rate
- DLQ rate
- end-to-end p50, p95, and p99 latency

## What to automate

For repeatable demos and first deployments, automate:
- preflight validation
- topic sizing estimates
- config file rendering
- schema bootstrap
- synthetic data generation
- benchmark report capture
