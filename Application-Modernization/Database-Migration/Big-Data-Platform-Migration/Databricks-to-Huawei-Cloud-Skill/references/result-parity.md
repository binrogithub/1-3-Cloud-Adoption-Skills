# Result Parity

## Goal

Prove that the migrated MRS workload preserves the Databricks business result before discussing tuning or production hardening.

## Minimum Checks

Always compare at least these metrics:

- row counts for major source and derived tables
- distinct business-key counts
- aggregate sums for key financial or business fields
- category-level totals such as product or tax treatment totals
- exception or rule-hit counts
- one or more traceable sample records

## Suggested Metric Table

Use this shape:

| metric_name | databricks_value | mrs_value | match_flag |
|---|---:|---:|---|
| source_rows | 0 | 0 | true |
| derived_rows | 0 | 0 | true |
| exception_count | 0 | 0 | true |
| category_x_total | 0.0 | 0.0 | true |

## Comparison Strategy

### Exact-match metrics

Use exact matches for:

- counts
- distinct counts
- rule-hit counts
- status counts
- categorical totals expected to be deterministic

### Numeric metrics

Use exact matches first. If floating-point noise is expected, compare:

- rounded values
- absolute delta
- relative delta

Document the rule used. Do not silently accept drift.

## Performance Comparison

Compare end-to-end wall-clock time only after the result set is proven equivalent.

When comparing run time, record:

- data volume
- source path type
  - `Volumes`
  - `OBS`
  - `HDFS`
- execution model
  - SQL warehouse
  - single `spark-submit`
  - multi-job chain
- target table count
- output write pattern

## Performance Caveat

Do not claim a platform is universally faster from a small or migration-scale timing result. A single measured run is heavily influenced by:

- storage path
- session startup overhead
- cluster sizing
- job decomposition
- metadata/write pattern

Use measured wording such as:

- "In this execution path, MRS completed faster."
- "This reflects the current path and environment, not a universal performance claim."

## Acceptance Criteria

Treat a migration as functionally aligned when:

- major row counts match
- core aggregate metrics match
- category-level business outputs match
- exception outputs match
- at least one sample business flow can be traced from source to final output
