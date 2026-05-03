#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASSWORD="${DEMO_PASSWORD:-Demo_Passw0rd!}"
SQLSERVER_CONTAINER="${SQLSERVER_CONTAINER:-sqlserver-demo}"
BABELFISH_HOST="${BABELFISH_HOST:-127.0.0.1}"
BABELFISH_TDS_PORT="${BABELFISH_TDS_PORT:-21433}"
INSERT_FILE="$ROOT_DIR/tmp/financedemo_inserts.sql"

docker_cmd() {
    env -u LD_LIBRARY_PATH docker "$@"
}

tds_exec() {
    TDSVER=7.4 tsql -H "$BABELFISH_HOST" -p "$BABELFISH_TDS_PORT" \
        -U babelfish_user -P "$PASSWORD"
}

tds_exec < "$ROOT_DIR/sql/02_target_babelfish_schema.sql" >/dev/null

docker_cmd exec -i "$SQLSERVER_CONTAINER" /opt/mssql-tools18/bin/sqlcmd \
    -C -S localhost -U sa -P "$PASSWORD" -d FinanceDemo -h -1 -W \
    < "$ROOT_DIR/sql/03_generate_insert_script.sql" \
    | sed -E '/^[[:space:]]*$/d; s/[[:space:]]+$//' > "$INSERT_FILE"

tds_exec < "$INSERT_FILE" >/dev/null

echo "Migrated FinanceDemo schema and data through Babelfish TDS port $BABELFISH_TDS_PORT."
