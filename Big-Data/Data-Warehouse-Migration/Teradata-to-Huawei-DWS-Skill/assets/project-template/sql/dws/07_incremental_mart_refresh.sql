CREATE TABLE IF NOT EXISTS reports.refresh_control (
  mart_name varchar(80) NOT NULL,
  refresh_key varchar(20) NOT NULL,
  refreshed_at timestamp NOT NULL,
  row_count bigint NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

-- Monthly branch KPI refresh.
DELETE FROM reports.branch_kpi_mart
WHERE year_num = :year_num
  AND month_num = :month_num;

INSERT INTO reports.branch_kpi_mart
SELECT *
FROM reports.branch_kpi
WHERE year_num = :year_num
  AND month_num = :month_num;

DELETE FROM reports.refresh_control
WHERE mart_name = 'branch_kpi_mart'
  AND refresh_key = :'refresh_month';

INSERT INTO reports.refresh_control
SELECT 'branch_kpi_mart',
       :'refresh_month',
       current_timestamp,
       count(*)::bigint
FROM reports.branch_kpi_mart
WHERE year_num = :year_num
  AND month_num = :month_num;

-- Snapshot refresh for loan risk.
DELETE FROM reports.loan_risk_snapshot_mart
WHERE snapshot_date = to_date(:'snapshot_date', 'YYYY-MM-DD');

INSERT INTO reports.loan_risk_snapshot_mart
SELECT *
FROM reports.loan_risk_snapshot
WHERE snapshot_date = to_date(:'snapshot_date', 'YYYY-MM-DD');

DELETE FROM reports.refresh_control
WHERE mart_name = 'loan_risk_snapshot_mart'
  AND refresh_key = :'snapshot_date';

INSERT INTO reports.refresh_control
SELECT 'loan_risk_snapshot_mart',
       :'snapshot_date',
       current_timestamp,
       count(*)::bigint
FROM reports.loan_risk_snapshot_mart
WHERE snapshot_date = to_date(:'snapshot_date', 'YYYY-MM-DD');

ANALYZE reports.branch_kpi_mart;
ANALYZE reports.loan_risk_snapshot_mart;
ANALYZE reports.refresh_control;

