#!/usr/bin/env bash
# Install LiteLLM + Redis + PostgreSQL on a fresh Ubuntu 22.04 ECS.
# Idempotent: rerunning is safe.
#
# Required env (do not hardcode):
#   REDIS_PWD, PG_PWD, LITELLM_MASTER_KEY,
#   HUAWEI_MAAS_API_BASE, HUAWEI_MAAS_API_KEY
#
# Usage on the laptop:
#   scp install_litellm.sh root@$ECS:/root/
#   ssh root@$ECS REDIS_PWD=... PG_PWD=... LITELLM_MASTER_KEY=... \
#                  HUAWEI_MAAS_API_BASE=... HUAWEI_MAAS_API_KEY=... \
#                  bash /root/install_litellm.sh

set -euo pipefail

: "${REDIS_PWD:?missing}"
: "${PG_PWD:?missing}"
: "${LITELLM_MASTER_KEY:?missing}"
: "${HUAWEI_MAAS_API_BASE:?missing}"
: "${HUAWEI_MAAS_API_KEY:?missing}"

echo "[1/8] apt packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip redis-server \
    postgresql postgresql-contrib build-essential libpq-dev curl openssl
systemctl enable --now redis-server postgresql

echo "[2/8] redis"
sed -i 's/^# *requirepass .*/requirepass '"$REDIS_PWD"'/' /etc/redis/redis.conf
grep -q '^requirepass' /etc/redis/redis.conf || \
    echo "requirepass $REDIS_PWD" >> /etc/redis/redis.conf
sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
systemctl restart redis-server
redis-cli -a "$REDIS_PWD" ping >/dev/null

echo "[3/8] postgres"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='litellm') THEN
    CREATE ROLE litellm LOGIN PASSWORD '$PG_PWD';
  ELSE
    ALTER ROLE litellm WITH LOGIN PASSWORD '$PG_PWD';
  END IF;
END \$\$;
SQL
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='litellm'" \
  | grep -q 1 || sudo -u postgres createdb -O litellm litellm
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE litellm TO litellm;"
PG_HBA=$(sudo -u postgres psql -tAc 'SHOW hba_file;')
grep -q "host litellm litellm 127.0.0.1/32 md5" "$PG_HBA" \
    || echo "host litellm litellm 127.0.0.1/32 md5" >> "$PG_HBA"
systemctl reload postgresql
PGPASSWORD="$PG_PWD" psql -h 127.0.0.1 -U litellm -d litellm -c "SELECT 1;" >/dev/null

echo "[4/8] litellm user and venv"
id litellm 2>/dev/null \
  || useradd --system --home /opt/litellm --shell /usr/sbin/nologin litellm
mkdir -p /opt/litellm /etc/litellm
chown -R litellm:litellm /opt/litellm /etc/litellm
if [ ! -x /opt/litellm-venv/bin/python ]; then
    python3 -m venv /opt/litellm-venv
fi
/opt/litellm-venv/bin/pip install -q --upgrade pip wheel
/opt/litellm-venv/bin/pip install -q "litellm[proxy]" prisma psycopg redis
chown -R litellm:litellm /opt/litellm-venv

echo "[5/8] env and config"
cat > /etc/litellm/litellm.env <<EOF
LITELLM_MASTER_KEY=$LITELLM_MASTER_KEY
DATABASE_URL=postgresql://litellm:$PG_PWD@127.0.0.1:5432/litellm
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=$REDIS_PWD
HUAWEI_MAAS_API_BASE=$HUAWEI_MAAS_API_BASE
HUAWEI_MAAS_API_KEY=$HUAWEI_MAAS_API_KEY
HOME=/opt/litellm
PATH=/opt/litellm-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF
chmod 640 /etc/litellm/litellm.env
chown root:litellm /etc/litellm/litellm.env

cat > /etc/litellm/config.yaml <<'EOF'
model_list:
  - model_name: "huawei/glm-5.1"
    litellm_params:
      model: "openai/glm-5.1"
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      timeout: 120
      input_cost_per_token: 1.078e-06
      output_cost_per_token: 3.774e-06
  - model_name: "huawei-glm-5.1"
    litellm_params:
      model: "openai/glm-5.1"
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      timeout: 120
      input_cost_per_token: 1.078e-06
      output_cost_per_token: 3.774e-06
litellm_settings:
  drop_params: true
  telemetry: false
  cache: true
  cache_params:
    type: redis
    supported_call_types: ["completion", "acompletion", "embedding", "aembedding"]
    host: os.environ/REDIS_HOST
    port: os.environ/REDIS_PORT
    password: os.environ/REDIS_PASSWORD
router_settings:
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
  enable_pre_call_checks: true
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  store_model_in_db: true
  database_connection_pool_limit: 20
  proxy_batch_write_at: 5
  user_api_key_cache_ttl: 120
  background_health_checks: false
EOF
chown root:litellm /etc/litellm/config.yaml
chmod 644 /etc/litellm/config.yaml

echo "[6/8] prisma generate + db push + engine path"
SCHEMA=$(find /opt/litellm-venv -name schema.prisma | head -1)
export PATH=/opt/litellm-venv/bin:$PATH
export DATABASE_URL=$(grep ^DATABASE_URL /etc/litellm/litellm.env | cut -d= -f2-)
/opt/litellm-venv/bin/prisma generate --schema "$SCHEMA"
/opt/litellm-venv/bin/prisma db push --schema "$SCHEMA" --accept-data-loss --skip-generate
ENGINE=$(find / -name 'query-engine-debian-openssl-3.0.x' \
                 -path '*node_modules/prisma/*' 2>/dev/null | head -1)
if [ -n "$ENGINE" ]; then
    if grep -q '^PRISMA_QUERY_ENGINE_BINARY=' /etc/litellm/litellm.env; then
        sed -i "s|^PRISMA_QUERY_ENGINE_BINARY=.*|PRISMA_QUERY_ENGINE_BINARY=$ENGINE|" /etc/litellm/litellm.env
    else
        echo "PRISMA_QUERY_ENGINE_BINARY=$ENGINE" >> /etc/litellm/litellm.env
    fi
    chmod -R o+rX "$(dirname "$(dirname "$(dirname "$ENGINE")")")"
fi

echo "[7/8] systemd unit"
cat > /etc/systemd/system/litellm.service <<EOF
[Unit]
Description=LiteLLM Proxy for Huawei Cloud MaaS
After=network-online.target redis-server.service postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=litellm
Group=litellm
WorkingDirectory=/opt/litellm
EnvironmentFile=/etc/litellm/litellm.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/litellm-venv/bin/litellm --config /etc/litellm/config.yaml --host 0.0.0.0 --port 4000 --use_prisma_db_push
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now litellm.service

echo "[8/8] wait for listener"
for i in $(seq 1 30); do
    if ss -tlnp | grep -q ':4000'; then
        echo "litellm listening on :4000"
        break
    fi
    sleep 2
done
journalctl -u litellm.service -n 20 --no-pager | tail -20
