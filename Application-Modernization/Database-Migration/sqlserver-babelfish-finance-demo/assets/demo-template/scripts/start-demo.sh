#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASSWORD="${DEMO_PASSWORD:-Demo_Passw0rd!}"
NETWORK="${DEMO_NETWORK:-babelfish-demo}"
SQLSERVER_CONTAINER="${SQLSERVER_CONTAINER:-sqlserver-demo}"
BABELFISH_CONTAINER="${BABELFISH_CONTAINER:-babelfish-demo}"

docker_cmd() {
    env -u LD_LIBRARY_PATH docker "$@"
}

wait_for_sqlserver() {
    for _ in $(seq 1 90); do
        if docker_cmd exec "$SQLSERVER_CONTAINER" /opt/mssql-tools18/bin/sqlcmd \
            -C -S localhost -U sa -P "$PASSWORD" -Q "SELECT 1" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done

    docker_cmd logs --tail=80 "$SQLSERVER_CONTAINER" >&2 || true
    return 1
}

wait_for_babelfish() {
    for _ in $(seq 1 60); do
        if docker_cmd exec "$BABELFISH_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done

    docker_cmd logs --tail=80 "$BABELFISH_CONTAINER" >&2 || true
    return 1
}

docker_cmd rm -f "$SQLSERVER_CONTAINER" "$BABELFISH_CONTAINER" >/dev/null 2>&1 || true
docker_cmd network inspect "$NETWORK" >/dev/null 2>&1 || docker_cmd network create "$NETWORK" >/dev/null

docker_cmd run -d \
    --name "$SQLSERVER_CONTAINER" \
    --network "$NETWORK" \
    -p 11433:1433 \
    --memory=3g \
    -e ACCEPT_EULA=Y \
    -e SA_PASSWORD="$PASSWORD" \
    -e MSSQL_PID=Express \
    -e MSSQL_MEMORY_LIMIT_MB=2048 \
    mcr.microsoft.com/mssql/server:2019-latest >/dev/null

docker_cmd run -d \
    --name "$BABELFISH_CONTAINER" \
    --network "$NETWORK" \
    -p 15432:5432 \
    -p 21433:1433 \
    --memory=1g \
    -e LD_LIBRARY_PATH=/usr/local/lib \
    -e POSTGRES_PASSWORD="$PASSWORD" \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_HOST_AUTH_METHOD=md5 \
    -e PGDATA=/var/lib/postgresql/data/pgdata \
    -e POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale=C.UTF-8 --auth-host=md5" \
    rsubr/postgres-babelfish:latest \
    -c shared_preload_libraries=babelfishpg_tds \
    -c listen_addresses='*' \
    -c babelfishpg_tds.listen_addresses='*' \
    -c babelfishpg_tds.port=1433 \
    -c password_encryption=md5 >/dev/null

wait_for_sqlserver
wait_for_babelfish

docker_cmd exec -i "$BABELFISH_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres <<SQL
SET password_encryption = 'md5';
CREATE USER babelfish_user WITH CREATEDB CREATEROLE PASSWORD '$PASSWORD' INHERIT;
CREATE DATABASE demo OWNER babelfish_user;
ALTER DATABASE demo SET babelfishpg_tsql.migration_mode = 'multi-db';
\\connect demo
CREATE EXTENSION IF NOT EXISTS "babelfishpg_tds" CASCADE;
CALL SYS.INITIALIZE_BABELFISH('babelfish_user');
ALTER SYSTEM SET babelfishpg_tsql.database_name = 'demo';
SELECT pg_reload_conf();
SQL

docker_cmd exec -i "$SQLSERVER_CONTAINER" /opt/mssql-tools18/bin/sqlcmd \
    -C -S localhost -U sa -P "$PASSWORD" -b < "$ROOT_DIR/sql/01_source_sqlserver.sql"

"$ROOT_DIR/scripts/migrate.sh"
"$ROOT_DIR/scripts/verify.sh"
