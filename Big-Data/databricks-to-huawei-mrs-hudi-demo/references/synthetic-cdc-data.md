# Synthetic CDC Data

Use synthetic CDC because the source archive has no customer DDL, schema checkpoint, or raw event samples.

## Generated Data Contract

- 21 inferred tables from task names.
- 1,250 CDC events per table:
  - 1,000 initial `c`/`r` records.
  - 200 update `u` events.
  - 50 delete `d` events.
- Fixed random seed for reproducibility.
- No real PII.

## Envelope

Each JSON line uses a Debezium-like envelope compatible with the original script logic:

```json
{
  "before": {},
  "after": {},
  "op": "c",
  "source": {},
  "ts_ms": 1780000000000
}
```

Rules:

- Non-delete events require `after.id`.
- Delete events require `before.id` and `after=null`.
- All tables include `id`, `created_at`, `update_date`, `tenant_id`, and `source_system`.

## Table Semantics

- `payment_*`: payment ids, amount, currency, status, method, outbox/event fields.
- `connector_*`: connector ids, account ids, operation type, step status, payload/log fields.
- `billing_*`: contract/profile/cycle/statement/installment ids, amount, due date, status, event fields.

## OBS Layout

Raw path pattern:

```text
raw/dockone_exampleapp/kfk.prd.cdc.dockone_exampleapp.<domain>.<entity>/part-00001.json
```

Example:

```text
raw/dockone_exampleapp/kfk.prd.cdc.dockone_exampleapp.payment.outbox/part-00001.json
```

## Validation

Check:

- 21 schemas exist.
- 21 raw folders exist.
- Every event has `op` and `ts_ms`.
- Delete uses `before`; non-delete uses `after`.
- DDL and JSON schema agree on field names.
