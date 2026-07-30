# Equivalence Summary Report

## Snowflake vs DataArts/DLI Equivalence Table

| VALIDATION_TYPE | OBJECT_NAME | SNOWFLAKE_EXPECTED | DATAARTS_DLI_ACTUAL | STATUS | DETAIL |
|-----------------|-------------|--------------------|---------------------|--------|--------|
| PIPELINE_READY | SNOWFLAKE_TASK_GRAPH_TO_DATAARTS_DAG | PASS | PASS | PASS | Snowflake Task Graph was converted to a DataArts/DLI runtime-safe DAG and executed successfully. |
| TABLE_COUNT | RAW_ORDERS | 5 | 5 | PASS | raw_orders row count: expected=5, actual=5 |
| TABLE_COUNT | SILVER_ORDERS | 5 | 5 | PASS | silver_orders row count: expected=5, actual=5 |
| TABLE_COUNT | GOLD_DAILY_SALES | 2 | 2 | PASS | gold_daily_sales row count: expected=2, actual=2 |
| TABLE_COUNT | TASK_AUDIT_SUCCESS | >=1 | 1 | PASS | task_audit SUCCESS count: expected>=1, actual=1 |
| AGGREGATE_CHECK | 2026-06-20 | order_count=2,total_amount=420.50 | order_count=2,total_amount=420.5 | PASS | 2026-06-20: expected order_count=2,total_amount=420.50; actual order_count=2,total_amount=420.5 |
| AGGREGATE_CHECK | 2026-06-21 | order_count=3,total_amount=630.34 | order_count=3,total_amount=630.34 | PASS | 2026-06-21: expected order_count=3,total_amount=630.34; actual order_count=3,total_amount=630.34 |
| FINAL_EQUIVALENCE | SNOWFLAKE_TO_DATAARTS | EQUIVALENT | EQUIVALENT | PASS | DataArts/DLI output is functionally equivalent to the Snowflake result. |

## Executive Summary

**Functional equivalence: CONFIRMED**

- Job name: snowflake_to_dataarts_demo_live_20260623_165151
- Run ID: run_20260623165224._7389f062
- Instance ID: 1312764
- Runtime validation: PASS
- Safety: no publish, no /start, no delete, no update, run-immediate only
