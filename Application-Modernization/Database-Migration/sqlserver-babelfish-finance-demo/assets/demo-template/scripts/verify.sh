#!/usr/bin/env bash
set -euo pipefail

PASSWORD="${DEMO_PASSWORD:-Demo_Passw0rd!}"
SQLSERVER_CONTAINER="${SQLSERVER_CONTAINER:-sqlserver-demo}"
BABELFISH_CONTAINER="${BABELFISH_CONTAINER:-babelfish-demo}"
BABELFISH_HOST="${BABELFISH_HOST:-127.0.0.1}"
BABELFISH_TDS_PORT="${BABELFISH_TDS_PORT:-21433}"

docker_cmd() {
    env -u LD_LIBRARY_PATH docker "$@"
}

echo "== SQL Server source =="
docker_cmd exec -i "$SQLSERVER_CONTAINER" /opt/mssql-tools18/bin/sqlcmd \
    -C -S localhost -U sa -P "$PASSWORD" -d FinanceDemo -W -Q "EXEC dbo.usp_customer_exposure; EXEC dbo.usp_daily_payment_liquidity"

echo
echo "== Babelfish TDS target =="
TDSVER=7.4 tsql -H "$BABELFISH_HOST" -p "$BABELFISH_TDS_PORT" \
    -U babelfish_user -P "$PASSWORD" <<'SQL'
USE FinanceDemo
GO
EXEC dbo.usp_customer_exposure
GO
EXEC dbo.usp_daily_payment_liquidity
GO
SQL

echo
echo "== PostgreSQL view of the migrated Babelfish database =="
docker_cmd exec "$BABELFISH_CONTAINER" psql -U postgres -d demo \
    -c "select schemaname, tablename from pg_tables where schemaname like 'financedemo%' order by 1,2;" \
    -c "select * from financedemo_dbo.v_customer_exposure order by \"OpenAlertCount\" desc, \"OutgoingAmount\" desc;" \
    -c "select * from financedemo_dbo.v_daily_payment_liquidity order by \"BusinessDate\", currencycode;"
