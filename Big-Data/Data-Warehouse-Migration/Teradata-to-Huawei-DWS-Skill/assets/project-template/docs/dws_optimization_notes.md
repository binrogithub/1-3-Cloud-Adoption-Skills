# DWS 优化记录

## 已执行优化

1. 报表 mart 预计算：
   - `reports.branch_kpi_mart`
   - `reports.customer_profitability_mart`
   - `reports.liquidity_gap_mart`
   - `reports.loan_risk_snapshot_mart`
   - `reports.suspicious_activity_mart`

2. 事实表分区副本：
   - `finance_dw_partitioned.fact_transaction`
   - `finance_dw_partitioned.fact_daily_balance`
   - `finance_dw_partitioned.fact_loan_snapshot`

3. 哈希分布倾斜检查：
   - 结果表：`reports.distribution_skew_report`
   - 当前 `customer_id` 分布键在交易和日终余额表上较均衡。

4. 增量 mart 刷新：
   - 控制表：`reports.refresh_control`
   - 默认示例刷新 `202506` 月分行 KPI 和 `2025-06-30` 贷款风险快照。

## 常用命令

```bash
./scripts/optimize_dws.sh
./scripts/create_partitioned_facts.sh
./scripts/check_dws_skew.sh
./scripts/refresh_dws_marts_incremental.sh 202506 2025-06-30
./scripts/run_dws_reports_optimized.sh
./scripts/validate_dws_optimized_reports.sh
```

## 当前倾斜结果

| 表 | 分布键 | skew_ratio |
| --- | --- | --- |
| `finance_dw.fact_daily_balance` | `customer_id` | `1.2160` |
| `finance_dw.fact_transaction` | `customer_id` | `1.2160` |
| `finance_dw.fact_loan_snapshot` | `customer_id` | `1.6640` |

`fact_loan_snapshot` 样本较小且客户覆盖较少，因此倾斜值略高；真实生产迁移时应结合 DN 级物理分布、查询 join 键和报表过滤条件复核。

