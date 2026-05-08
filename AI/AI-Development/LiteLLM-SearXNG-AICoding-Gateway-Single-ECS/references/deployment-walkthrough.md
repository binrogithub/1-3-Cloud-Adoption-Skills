# Deployment Walkthrough

End-to-end recipe captured from a real deployment on Huawei Cloud `la-north-2`,
Ubuntu 22.04, ECS `s6.2xlarge.2`. Replace placeholders surrounded by `<...>`.

## 0. Variables

```bash
export HUAWEI_AK='<AK>'
export HUAWEI_SK='<SK>'
export HUAWEI_PROJECT='<PROJECT_ID>'
export HUAWEI_REGION='la-north-2'

export ECS_PUBLIC_IP='<ECS_PUBLIC_IP>'
export SSH_KEY='~/.ssh/<keypair>'                      # private key file
export LAPTOP_CIDR="$(curl -s https://ifconfig.me)/32"

export HUAWEI_MAAS_API_BASE='https://api-ap-southeast-1.modelarts-maas.com/openai/v1'
export HUAWEI_MAAS_API_KEY='<MAAS_KEY>'

export REDIS_PWD=$(openssl rand -hex 16)
export PG_PWD=$(openssl rand -hex 16)
export LITELLM_MASTER_KEY="sk-$(openssl rand -hex 24)"
export MCP_TOKEN=$(openssl rand -hex 16)
```

## 1. Provision ECS

Use `scripts/provision_huawei_ecs.py` (or the Console). Important:

- Reuse the default VPC/subnet if `router quota exceeded` shows up.
- Generate a fresh keypair locally; import the public half as the Huawei keypair.
- Bind an EIP, allocate a `100–200 GB` general-purpose v2 EVS.
- Open `22` from `$LAPTOP_CIDR` only.

After ACTIVE:

```bash
ssh -o StrictHostKeyChecking=accept-new -i $SSH_KEY root@$ECS_PUBLIC_IP \
    "uname -a; id; df -h /; free -h | head -2"
```

If you ever see `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`, the EIP was
recycled and a new ECS got the same address. Run
`ssh-keygen -f ~/.ssh/known_hosts -R $ECS_PUBLIC_IP` and reconnect with
`accept-new`.

## 2. Install runtime

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP 'set -e
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3-venv python3-pip redis-server postgresql postgresql-contrib \
  build-essential libpq-dev curl openssl docker.io docker-compose-v2
systemctl enable --now redis-server postgresql docker
'
```

## 3. Configure Redis + PostgreSQL

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP \
    "REDIS_PWD='$REDIS_PWD' PG_PWD='$PG_PWD' bash -s" <<'REMOTE'
set -e
sed -i 's/^# *requirepass .*/requirepass '"$REDIS_PWD"'/' /etc/redis/redis.conf
grep -q '^requirepass' /etc/redis/redis.conf || echo "requirepass $REDIS_PWD" >> /etc/redis/redis.conf
sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
systemctl restart redis-server
redis-cli -a "$REDIS_PWD" ping

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
PGPASSWORD="$PG_PWD" psql -h 127.0.0.1 -U litellm -d litellm -c 'SELECT version();'
REMOTE
```

## 4. Install LiteLLM

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP 'set -e
id litellm 2>/dev/null \
  || useradd --system --home /opt/litellm --shell /usr/sbin/nologin litellm
mkdir -p /opt/litellm /etc/litellm
chown -R litellm:litellm /opt/litellm /etc/litellm
python3 -m venv /opt/litellm-venv
/opt/litellm-venv/bin/pip install -q --upgrade pip wheel
/opt/litellm-venv/bin/pip install -q "litellm[proxy]" prisma psycopg redis
/opt/litellm-venv/bin/litellm --version
chown -R litellm:litellm /opt/litellm-venv
'
```

## 5. Write env and config

Use `assets/config/litellm.env.example` and `assets/config/litellm.config.yaml.example`.
Substitute the variables you exported above.

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP \
    "REDIS_PWD='$REDIS_PWD' PG_PWD='$PG_PWD' \
     MASTER_KEY='$LITELLM_MASTER_KEY' \
     HUAWEI_KEY='$HUAWEI_MAAS_API_KEY' \
     HUAWEI_BASE='$HUAWEI_MAAS_API_BASE' \
     bash -s" <<'REMOTE'
set -e
cat > /etc/litellm/litellm.env <<EOF
LITELLM_MASTER_KEY=$MASTER_KEY
DATABASE_URL=postgresql://litellm:$PG_PWD@127.0.0.1:5432/litellm
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=$REDIS_PWD
HUAWEI_MAAS_API_BASE=$HUAWEI_BASE
HUAWEI_MAAS_API_KEY=$HUAWEI_KEY
HOME=/opt/litellm
PATH=/opt/litellm-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF
chmod 640 /etc/litellm/litellm.env
chown root:litellm /etc/litellm/litellm.env
REMOTE
```

Drop `config.yaml` next to it (see asset).

## 6. Bootstrap Prisma

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP 'set -e
SCHEMA=/opt/litellm-venv/lib/python3.10/site-packages/litellm_proxy_extras/schema.prisma
export PATH=/opt/litellm-venv/bin:$PATH
export DATABASE_URL=$(grep ^DATABASE_URL /etc/litellm/litellm.env | cut -d= -f2-)
/opt/litellm-venv/bin/prisma generate --schema "$SCHEMA"
/opt/litellm-venv/bin/prisma db push --schema "$SCHEMA" --accept-data-loss --skip-generate
ENGINE=$(find / -name "query-engine-debian-openssl-3.0.x" -path "*node_modules/prisma/*" 2>/dev/null | head -1)
echo "engine: $ENGINE"
echo "PRISMA_QUERY_ENGINE_BINARY=$ENGINE" >> /etc/litellm/litellm.env
chmod -R o+rX "$(dirname "$(dirname "$(dirname "$ENGINE")")")"
'
```

## 7. systemd LiteLLM

Drop `assets/config/litellm.service.example` to `/etc/systemd/system/litellm.service`,
then:

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP '
systemctl daemon-reload
systemctl enable --now litellm.service
sleep 25
systemctl is-active litellm.service
ss -tlnp | grep :4000
journalctl -u litellm.service -n 60 --no-pager | tail -20
'
```

## 8. Open SG and validate from laptop

```bash
# Open 4000 to your /32 via SDK or Console. Then:
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  http://$ECS_PUBLIC_IP:4000/health/liveliness         # "I'm alive!"
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  http://$ECS_PUBLIC_IP:4000/health | jq '.healthy_count, .unhealthy_count'

curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
     -H 'Content-Type: application/json' \
     -X POST http://$ECS_PUBLIC_IP:4000/v1/chat/completions \
     -d '{"model":"huawei/glm-5.1","messages":[{"role":"user","content":"hi"}]}'
```

## 9. SearXNG (Docker)

Drop `assets/config/searxng-docker-compose.yml` and
`assets/config/searxng-settings.yml`, then:

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP 'set -e
mkdir -p /opt/searxng/searxng
SECRET=$(openssl rand -hex 32)
# Write the two files; substitute $SECRET into settings.yml.
cd /opt/searxng
docker compose pull
docker compose up -d
sleep 8
curl -s -G "http://127.0.0.1:8080/search" \
  --data-urlencode "q=hello" --data-urlencode "format=json" \
  -H "Accept: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(\"results:\", len(d.get(\"results\",[])))"
'
```

## 10. SearXNG MCP HTTP

Use `assets/config/searxng_mcp_server.py` and
`assets/config/searxng-mcp.service.example`.

```bash
ssh -i $SSH_KEY root@$ECS_PUBLIC_IP "MCP_TOKEN='$MCP_TOKEN' bash -s" <<'REMOTE'
set -e
useradd --system --home /opt/searxng-mcp --shell /usr/sbin/nologin searxmcp 2>/dev/null || true
mkdir -p /opt/searxng-mcp
python3 -m venv /opt/searxng-mcp/venv
/opt/searxng-mcp/venv/bin/pip install -q --upgrade pip
/opt/searxng-mcp/venv/bin/pip install -q "fastmcp>=2,<3" httpx
# scp the server.py and unit before this step.
chown -R searxmcp:searxmcp /opt/searxng-mcp
systemctl daemon-reload
systemctl enable --now searxng-mcp.service
sleep 5
ss -tlnp | grep :8788
REMOTE
```

## 11. Open SG 8788 and probe MCP

```bash
# Open 8788 to $LAPTOP_CIDR.

# Without token:
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://$ECS_PUBLIC_IP:8788/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
# 401

# With token, capture session id, list tools, call web_search.
HDRS=$(mktemp)
curl -s -i -X POST http://$ECS_PUBLIC_IP:8788/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  | tee "$HDRS" >/dev/null
SID=$(grep -i '^mcp-session-id' "$HDRS" | awk '{print $2}' | tr -d '\r')

curl -s -X POST http://$ECS_PUBLIC_IP:8788/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "mcp-session-id: $SID" \
  -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

curl -s -X POST http://$ECS_PUBLIC_IP:8788/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" -H "mcp-session-id: $SID" \
  -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | sed -n '/^data:/p'
```

## 12. Wire AI coding agent (`claude-glm`) on the laptop

Mint an unrestricted virtual key for the operator, point ccr at LiteLLM with
that key, register the MCP under an isolated config dir.

```bash
# Mint LiteLLM virtual key
LITELLM_VIRTUAL_KEY=$(curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -X POST http://$ECS_PUBLIC_IP:4000/key/generate \
  -d '{"key_alias":"claude-glm-operator"}' | jq -r .key)

# Drop the wrapper and ccr config from the assets, with substitutions.
mkdir -p ~/.config/claude-glm ~/.claude-code-router ~/.claude-glm-config

cat > ~/.config/claude-glm/env <<EOF
export LITELLM_VIRTUAL_KEY="$LITELLM_VIRTUAL_KEY"
export CLAUDE_GLM_ROUTER_KEY="claude-glm-local"
EOF

# Use assets/config/claude-code-router.config.json.example, substitute ECS_PUBLIC_IP.
# Use assets/config/claude-glm-wrapper.sh.example as ~/.local/bin/claude-glm; chmod +x.

ccr stop || true ; sleep 1 ; ccr start ; sleep 2 ; ccr status

# Register MCP under isolated config dir only:
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp add \
  --transport http --scope user searxng \
  http://$ECS_PUBLIC_IP:8788/mcp \
  --header "Authorization: Bearer $MCP_TOKEN"
```

## 13. End-to-end smoke

```bash
claude-glm -p '只回复两个字：你好'                           # 你好
claude-glm --permission-mode bypassPermissions -p \
  '用 mcp__searxng__web_search 查 Anthropic Claude，前 3 条 title+url。'
claude mcp list | grep searxng && echo "BAD: leaked into plain claude" \
  || echo "OK: plain claude clean"
```
