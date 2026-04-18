# Architecture

## Generic processing model

Use this model for high-frequency transaction systems:

1. Producer writes a command or domain event to `trade.request`.
2. Consumer reads the event from Kafka.
3. Consumer opens a local GaussDB transaction.
4. Consumer inserts into `trade_inbox` using `event_id` as a uniqueness key.
5. Consumer updates `trade_state`.
6. Consumer inserts downstream event metadata into `trade_outbox`.
7. Consumer commits the GaussDB transaction.
8. Consumer commits the Kafka offset.
9. A publisher emits rows from `trade_outbox` to `trade.processed`.

## Why this works

- Kafka absorbs spikes and preserves partition ordering.
- GaussDB enforces constraints, current state, and query access.
- Inbox prevents duplicate processing on replay.
- Outbox prevents lost downstream events.
- Manual offset commit avoids acknowledging work before it is durable.

## Topic design

Use a small, explicit topic taxonomy:
- `trade.request`
- `trade.processed`
- `trade.failed`
- `trade.audit`
- `trade.dlq`

For a small demo, `trade.failed` can be omitted if `trade.dlq` contains failure metadata.

## Partition strategy

Pick the partition key from the highest-conflict entity:
- payments: `account_id`
- broker orders: `order_id` or `portfolio_id`
- clearing: `merchant_id` or `settlement_batch_id`
- inventory reservation: `sku_id` or `warehouse_sku_id`

Never partition on a random UUID if ordering is required by a business entity.

## Table pattern

Use these tables:

### `trade_inbox`

Purpose:
- deduplicate inbound Kafka events
- store processing status and error metadata

Suggested columns:
- `event_id` primary key
- `trace_id`
- `aggregate_id`
- `event_type`
- `payload_json`
- `status`
- `error_code`
- `error_message`
- `received_at`
- `processed_at`

### `trade_state`

Purpose:
- authoritative current state per business aggregate

Suggested columns:
- `aggregate_id` primary key
- `account_id`
- `state`
- `amount`
- `currency`
- `version`
- `updated_at`

### `trade_outbox`

Purpose:
- reliable downstream publication after DB commit

Suggested columns:
- `id` primary key
- `event_id` unique
- `aggregate_id`
- `topic_name`
- `payload_json`
- `publish_status`
- `created_at`
- `published_at`

### `trade_audit`

Purpose:
- immutable trail for reconciliation and support

Suggested columns:
- `id` primary key
- `event_id`
- `trace_id`
- `aggregate_id`
- `action`
- `detail_json`
- `created_at`

## Java guidance

Recommend Java for production application code because:
- Kafka clients are mature and well understood.
- thread pools and batching are easier to control under heavy load.
- JDBC and connection pools are operationally straightforward.

For the bundled demo:
- use `kafka-clients`
- use JDBC through `java.sql.*`
- use the GaussDB JDBC driver at runtime

## Ops guidance

- one consumer thread per partition lane
- bounded retries
- DLQ for poison messages
- metrics on lag, commit latency, DB latency, and duplicate rate
- reconciliation jobs that compare Kafka-derived facts with DB state
