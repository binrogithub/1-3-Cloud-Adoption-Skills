#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# source_postgresql_bootstrap.sh
# Bootstrap script for self-managed PostgreSQL on Ubuntu ECS
# Configures PostgreSQL for DRS Full + Incremental migration
# ============================================================
# SECURITY WARNING:
#   This script opens PostgreSQL to network access for DRS.
#   In this EXPERIMENTAL phase, DRS connects over public Internet.
#   For presentation/production, replace public access with VPN/private CIDR.
# ============================================================

PG_VERSION="${PG_VERSION:-16}"
PG_PORT="${PG_PORT:-5432}"
DEMO_DB="${DEMO_DB:-demomigration}"
DEMO_USER="${DEMO_USER:-demoadmin}"
DRS_USER="${DRS_USER:-drs_replicator}"

# DRS source IP/CIDR placeholder
# Replace with the actual DRS source IP or CIDR shown during DRS task creation
# EXPERIMENTAL: This will be a public IP/CIDR
# FUTURE VPN: Replace with VPN/private CIDR (e.g., 10.x.x.x/24)
ALLOWED_DRS_CIDR="${ALLOWED_DRS_CIDR:-REPLACE_WITH_DRS_SOURCE_CIDR}"

echo "=== PostgreSQL Bootstrap Start ==="
echo "PostgreSQL version: ${PG_VERSION}"
echo "Demo database: ${DEMO_DB}"
echo "DRS user: ${DRS_USER}"
echo "Allowed DRS CIDR: ${ALLOWED_DRS_CIDR}"

# ----------------------------------------------------------
# 1. Install PostgreSQL
# ----------------------------------------------------------
echo "--- Installing PostgreSQL ${PG_VERSION} ---"
sudo apt-get update -y
sudo apt-get install -y curl ca-certificates

sudo sh -c "echo 'deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main' > /etc/apt/sources.list.d/pgdg.list"
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg

sudo apt-get update -y
sudo apt-get install -y "postgresql-${PG_VERSION}" "postgresql-client-${PG_VERSION}"

echo "PostgreSQL installed: $(psql --version)"

# ----------------------------------------------------------
# 2. Configure postgresql.conf for DRS logical replication
# ----------------------------------------------------------
echo "--- Configuring postgresql.conf ---"
PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"

sudo cp "${PG_CONF}" "${PG_CONF}.bak.$(date +%Y%m%d%H%M%S)"

configure_param() {
    local param="$1"
    local value="$2"
    local conf="$3"
    if sudo grep -q "^${param}" "${conf}"; then
        sudo sed -i "s|^${param}.*|${param} = ${value}|" "${conf}"
    elif sudo grep -q "^#${param}" "${conf}"; then
        sudo sed -i "s|^#${param}.*|${param} = ${value}|" "${conf}"
    else
        echo "${param} = ${value}" | sudo tee -a "${conf}" > /dev/null
    fi
    echo "  Set ${param} = ${value}"
}

configure_param "wal_level"             "logical"  "${PG_CONF}"
configure_param "max_replication_slots"  "4"        "${PG_CONF}"
configure_param "max_wal_senders"        "4"        "${PG_CONF}"
configure_param "listen_addresses"       "'"*'"     "${PG_CONF}"
configure_param "wal_keep_size"          "256MB"    "${PG_CONF}"

# ----------------------------------------------------------
# 3. Configure pg_hba.conf for DRS access
# ----------------------------------------------------------
echo "--- Configuring pg_hba.conf ---"
PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

sudo cp "${PG_HBA}" "${PG_HBA}.bak.$(date +%Y%m%d%H%M%S)"

echo "" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# ============================================================" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# DRS REPLICATION ACCESS - EXPERIMENTAL INTERNET PHASE" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# Replace ${ALLOWED_DRS_CIDR} with actual DRS source CIDR" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# FUTURE VPN: Change CIDR to VPN/private network CIDR" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# ============================================================" | sudo tee -a "${PG_HBA}" > /dev/null
echo "host  ${DEMO_DB}  ${DRS_USER}  ${ALLOWED_DRS_CIDR}  md5" | sudo tee -a "${PG_HBA}" > /dev/null
echo "host  replication  ${DRS_USER}  ${ALLOWED_DRS_CIDR}  md5" | sudo tee -a "${PG_HBA}" > /dev/null

echo "" | sudo tee -a "${PG_HBA}" > /dev/null
echo "# Local admin access for demo user" | sudo tee -a "${PG_HBA}" > /dev/null
echo "local  ${DEMO_DB}  ${DEMO_USER}  md5" | sudo tee -a "${PG_HBA}" > /dev/null
echo "host   ${DEMO_DB}  ${DEMO_USER}  127.0.0.1/32  md5" | sudo tee -a "${PG_HBA}" > /dev/null

# ----------------------------------------------------------
# 4. Restart PostgreSQL
# ----------------------------------------------------------
echo "--- Restarting PostgreSQL ---"
sudo systemctl restart postgresql
sudo systemctl enable postgresql
sleep 3
sudo systemctl status postgresql --no-pager

# ----------------------------------------------------------
# 5. Create demo database and users
# ----------------------------------------------------------
echo "--- Creating database and users ---"
sudo -u postgres psql -p "${PG_PORT}" -c "CREATE DATABASE ${DEMO_DB};"
sudo -u postgres psql -p "${PG_PORT}" -c "CREATE USER ${DEMO_USER} WITH PASSWORD 'REPLACE_WITH_SECURE_DEMO_PASSWORD';"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DEMO_USER};"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "GRANT ALL ON SCHEMA public TO ${DEMO_USER};"

# ----------------------------------------------------------
# 6. Create DRS replication user with minimum required privileges
# ----------------------------------------------------------
echo "--- Creating DRS replication user ---"
sudo -u postgres psql -p "${PG_PORT}" -c "CREATE USER ${DRS_USER} WITH REPLICATION LOGIN PASSWORD 'REPLACE_WITH_SECURE_DRS_PASSWORD';"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "GRANT CONNECT ON DATABASE ${DEMO_DB} TO ${DRS_USER};"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "GRANT USAGE ON SCHEMA public TO ${DRS_USER};"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${DRS_USER};"
sudo -u postgres psql -p "${PG_PORT}" -d "${DEMO_DB}" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${DRS_USER};"

echo ""
echo "=== PostgreSQL Bootstrap Complete ==="
echo ""
echo "NEXT STEPS:"
echo "  1. Replace ALLOWED_DRS_CIDR with the actual DRS source IP/CIDR"
echo "  2. Replace placeholder passwords with secure values"
echo "  3. Reload pg_hba.conf: sudo systemctl reload postgresql"
echo "  4. Run schema SQL:  psql -d ${DEMO_DB} -f sql/01_schema.sql"
echo "  5. Run seed SQL:    psql -d ${DEMO_DB} -f sql/02_seed_data.sql"
echo "  6. Run validation:  psql -d ${DEMO_DB} -f sql/03_source_validation.sql"
echo ""
echo "SECURITY REMINDER:"
echo "  - This configuration uses PUBLIC INTERNET for DRS connectivity"
echo "  - For presentation/production, switch to VPN/private network"
echo "  - Update pg_hba.conf CIDR from public to VPN/private CIDR"
echo "  - Remove or restrict the EIP on the ECS if no longer needed"
