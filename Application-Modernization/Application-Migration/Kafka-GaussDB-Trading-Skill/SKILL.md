---
name: kafka-gaussdb-trading
description: Use when the user wants a generic, deployable Huawei Cloud architecture or demo for high-frequency, high-volume, complex transactions using DMS for Kafka plus GaussDB, with Java application code, idempotent processing, partitioning, retry/DLQ, and schema examples. Also use for transaction, payment, order, ledger, clearing, or risk-processing flows on Kafka + GaussDB.
---

# Kafka + GaussDB Trading

Use this skill for generic high-frequency transaction systems on Huawei Cloud where Kafka is the event backbone and GaussDB is the transactional state store.

Recommended application language: Java.

Reason:
- Java has the strongest Kafka client ecosystem.
- Java gives predictable threading, batching, and backpressure behavior under sustained throughput.
- GaussDB JDBC integration fits Java service patterns well.

Do not reuse historical IPs, passwords, topic names, customer names, or environment values from prior chats or random workspace files unless the user explicitly asks for those exact values. Default to generic placeholders and deployment steps.

## Outcome

Produce one of these:
- A deployable reference architecture
- A quick Huawei Cloud demo plan
- Java code skeletons or a runnable demo app
- Topic, schema, and idempotency design for a new transaction flow

## Default architecture

Use this baseline unless the user provides constraints that require something else:

1. Ingress topic receives transaction commands or trade requests.
2. Java consumer service reads from Kafka with manual offset commit disabled.
3. Service writes to GaussDB in a local database transaction.
4. Service inserts an inbox/idempotency row keyed by `event_id`.
5. Service updates current business state tables.
6. Service writes an outbox or audit row in the same DB transaction.
7. Commit DB transaction.
8. Commit Kafka offset only after DB commit succeeds.
9. A separate publisher or the same service emits downstream events from the outbox.

This is the safest default for complex transaction chains without attempting distributed XA.

## Core design rules

### 1. Partition by conflict key

Pick the Kafka partition key from the field that must be serialized:
- `account_id` for account balance changes
- `order_id` for order lifecycle
- `merchant_id` for merchant settlement
- `instrument_id` for market-level sequencing

If two updates conflict, they must hash to the same partition.

### 2. Keep Kafka and DB responsibilities separate

- Kafka stores the event flow, buffering, replay, and downstream fan-out.
- GaussDB stores the authoritative current state, constraints, queries, and reconciliation data.

Do not treat Kafka as the query database.

### 3. Prefer inbox + outbox over distributed transactions

For high-volume systems, use:
- Inbox table for deduplication and processing status
- Business tables for current state
- Outbox table for reliable downstream publication

This is the default recommendation for payments, trades, ledgers, inventory, and settlement.

### 4. Commit order

Always use this order:
1. Read Kafka message
2. Begin DB transaction
3. Upsert inbox row
4. Apply business SQL
5. Insert outbox row
6. Commit DB transaction
7. Commit Kafka offset

Never commit the Kafka offset before the database transaction commits.

### 5. Reliability defaults

Kafka producer defaults:
- `acks=all`
- `enable.idempotence=true`
- `compression.type=lz4`
- `delivery.timeout.ms` sized for the workload

Kafka topic defaults:
- replication factor 3 where available
- `min.insync.replicas=2`
- `unclean.leader.election.enable=false`

Kafka consumer defaults:
- `enable.auto.commit=false`
- `auto.offset.reset=earliest` for demos and replay workflows

### 6. Failure lanes

Design these topics up front:
- `trade.request`
- `trade.processed`
- `trade.failed`
- `trade.audit`
- `trade.dlq`

Keep retries bounded. Push poison messages to DLQ with the original payload and error metadata.

### 7. Reconciliation and audit

Always include:
- `event_id`
- `trace_id`
- `aggregate_id`
- `event_time`
- `producer_service`
- `schema_version`

Store them in both Kafka payloads and GaussDB tables.

## Huawei Cloud deployment defaults

Prefer this topology:
- DMS for Kafka and GaussDB in the same region
- Java app on ECS or CCE in the same VPC and subnet family
- Private network access first
- Ciphertext Kafka access when enabled
- Security groups restricted to app nodes only

Based on Huawei Cloud docs:
- DMS for Kafka supports open-source Kafka clients and uses different addresses by network mode.
- Same-region same-VPC private access is the normal path.
- Official docs describe private access ports `9092` plaintext or `9093` ciphertext, and public access ports `9094` plaintext or `9095` ciphertext.
- For GaussDB JDBC, use the GaussDB-compatible JDBC driver class and `jdbc:opengauss://...` URL when following the Huawei JDBC path.

Read [references/huawei-cloud-deploy.md](references/huawei-cloud-deploy.md) before giving final deployment steps.

## What to ask or infer

Infer reasonable defaults unless the user gives stronger requirements:
- TPS target
- payload size
- dominant contention key
- latency SLA
- ordering scope
- replay requirement
- public or private access
- whether Kafka auth is plaintext, SASL_SSL, or another enabled mode

If not specified, assume:
- private VPC access
- Java 17
- 3 Kafka brokers
- 3 partitions for demo, more for scale
- 1 consumer thread per partition
- a single GaussDB writer service per partition lane

## Demo workflow

When the user wants a quick demo on Huawei Cloud:

1. Create DMS for Kafka.
2. Create GaussDB.
3. Collect:
   - Kafka bootstrap servers
   - Kafka topic names
   - Kafka auth mode and credentials if enabled
   - GaussDB JDBC URL pieces
   - database user and password
4. Copy the Java demo from `assets/java-demo/`.
5. Fill in `app.properties`.
6. Create the tables with `bootstrap-db`.
7. Produce sample events with `produce-demo`.
8. Run the consumer with `consume`.
9. Query `trade_state`, `trade_inbox`, and `trade_outbox`.

Read:
- [references/architecture.md](references/architecture.md) for the generic design
- [references/java-demo.md](references/java-demo.md) for how to run the bundled Java demo
- [references/performance-tuning.md](references/performance-tuning.md) for reusable Kafka + GaussDB tuning guidance

Use bundled scripts when speed matters:
- `scripts/smoke_check.py`: preflight Kafka TCP reachability and GaussDB login/query checks
- `scripts/render_app_properties.py`: generate `app.properties` for plaintext or SASL_SSL Kafka plus GaussDB JDBC
- `scripts/topic_plan.py`: estimate partitions, consumer concurrency, and starting batch sizes from target TPS and handler latency

## Response shape

Prefer this order in responses:
1. State the recommended architecture in 4 to 8 lines.
2. State the Huawei Cloud deployment topology.
3. Give the topic list and partition-key rule.
4. Give the GaussDB table pattern.
5. Give Java example code or point to the bundled demo.
6. Give exact run steps for a demo.

## When not to overcomplicate

Do not propose:
- XA or two-phase commit by default
- Flink, Debezium, CDC, or event sourcing unless the user asks
- multi-region active-active unless explicitly required
- dozens of microservices for a demo

For demos and first deployments, keep it to:
- 1 request topic
- 1 consumer app
- 1 GaussDB schema
- inbox, state, outbox, audit tables
- optional processed and DLQ topics

## What was generalized from prior implementations

These patterns were repeated enough in earlier code and runbooks to justify bundling them into this skill:
- preflight connectivity checks for both Kafka and GaussDB
- explicit topic durability configuration
- manual offset commit after successful DB work
- partition-based worker ownership
- GaussDB batch writing with JDBC batching or COPY-style fast paths
- host rotation across multiple DB nodes for parallel loaders and benchmarks

If the user asks for a productionization or optimization plan, explicitly surface those patterns instead of answering only at the architecture level.
