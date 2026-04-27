#!/bin/bash
# deploy_ecs_demo.sh — Bootstrap Huawei Cloud ECS and deploy telco AI demo
# Usage: bash deploy_ecs_demo.sh --demo=1|2 --ip=<ecs-ip> --key=<ssh-key-path> [--asr] [--region=<region>]
#
# Sanitized: no real IPs, passwords, or customer names.
# Reads credentials from environment: MAAS_API_KEY, DB_PASSWORD (optional)

set -euo pipefail

DEMO=""
ECS_IP=""
SSH_KEY=""
WITH_ASR=false
REGION="${REGION:-la-north-2}"

usage() {
    cat <<EOF
Usage: $0 --demo=1|2 --ip=<ecs-ip> --key=<ssh-key-path> [--asr] [--region=<region>]

  --demo=1       Deploy Customer Intelligence (ASR + backend + dashboard, GPU)
  --demo=2       Deploy Agentic Engineering (backend + dashboard, no GPU)
  --ip=<ip>      ECS public IP address
  --key=<path>   Path to SSH private key
  --asr          Deploy Qwen3-ASR (Demo 1 only, requires GPU)
  --region=<r>   Huawei Cloud region (default: la-north-2)
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --demo=*) DEMO="${1#*=}" ;;
        --ip=*)   ECS_IP="${1#*=}" ;;
        --key=*)  SSH_KEY="${1#*=}" ;;
        --asr)    WITH_ASR=true ;;
        --region=*) REGION="${1#*=}" ;;
        *)        usage ;;
    esac
    shift
done

[[ -z "$DEMO" || -z "$ECS_IP" || -z "$SSH_KEY" ]] && usage
[[ "$DEMO" != "1" && "$DEMO" != "2" ]] && { echo "ERROR: --demo must be 1 or 2"; exit 1; }
[[ ! -f "$SSH_KEY" ]] && { echo "ERROR: SSH key not found: $SSH_KEY"; exit 1; }

SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no root@$ECS_IP"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

echo "=== Telco AI Demo Deploy ==="
echo "Demo:    $DEMO"
echo "ECS IP:  $ECS_IP"
echo "Region:  $REGION"
echo "ASR:     $WITH_ASR"
echo ""

# ── Step 1: Verify SSH connectivity ──
echo "[1/7] Verifying SSH connectivity..."
if ! $SSH "echo OK" > /dev/null 2>&1; then
    echo "ERROR: Cannot SSH to $ECS_IP as root"
    echo "  Check: security group allows port 22 from your IP"
    echo "  Check: keypair is correct (Huawei Cloud Ubuntu uses 'root', not 'ubuntu')"
    exit 1
fi
echo "  SSH OK"

# ── Step 2: Fix DNS and install Docker ──
echo "[2/7] Configuring DNS and installing Docker..."
$SSH "bash -s" << 'DOCKER_SETUP'
set -e

# Fix DNS (Huawei Cloud internal resolvers can be slow)
if ! grep -q "8.8.8.8" /etc/resolv.conf; then
    sed -i '1inameserver 8.8.8.8' /etc/resolv.conf
fi

# Install Docker if missing
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose plugin if missing
if ! docker compose version &>/dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/libexec/docker/cli-plugins/docker-compose 2>/dev/null || \
    curl -SL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64" \
        -o /usr/local/libexec/docker/cli-plugins/docker-compose
    mkdir -p /usr/local/libexec/docker/cli-plugins
    mv /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose 2>/dev/null || true
    chmod +x /usr/local/libexec/docker/cli-plugins/docker-compose
fi

echo "Docker: $(docker --version)"
echo "Compose: $(docker compose version)"
DOCKER_SETUP
echo "  Docker OK"

# ── Step 3: Install NVIDIA drivers and toolkit (Demo 1 only) ──
if [[ "$DEMO" == "1" && "$WITH_ASR" == "true" ]]; then
    echo "[3/7] Installing NVIDIA drivers and container toolkit..."
    $SSH "bash -s" << 'NVIDIA_SETUP'
set -e

# Check GPU
if ! lspci | grep -i nvidia &>/dev/null; then
    echo "WARNING: No NVIDIA GPU detected. ASR will run on CPU (slow)."
fi

# Install NVIDIA Container Toolkit if GPU present
if command -v nvidia-smi &>/dev/null && ! command -v nvidia-container-toolkit &>/dev/null; then
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update
    apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
fi
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'not detected')"
NVIDIA_SETUP
    echo "  GPU setup done"
else
    echo "[3/7] Skipping GPU setup (not needed for Demo $DEMO)"
fi

# ── Step 4: Create app directory ──
echo "[4/7] Creating application directory..."
DEPLOY_PATH="/opt/telco-demo${DEMO}"
$SSH "mkdir -p $DEPLOY_PATH"
echo "  Path: $DEPLOY_PATH"

# ── Step 5: Generate .env file ──
echo "[5/7] Generating environment configuration..."
if [[ "$DEMO" == "1" ]]; then
    $SSH "cat > $DEPLOY_PATH/.env << 'ENVEOF'
# Demo 1 — Customer Intelligence
DEMO_MODE=deterministic
MAAS_API_KEY=${MAAS_API_KEY:-<maas-api-key>}
MAAS_API_URL=${MAAS_API_URL:-https://<maas-endpoint>/v1/chat/completions}
MAAS_MODEL=${MAAS_MODEL:-glm-5.1}
ASR_ENDPOINT=http://127.0.0.1:8001
DB_HOST=localhost
DB_PORT=5432
DB_USER=${DB_USER:-telco_demo}
DB_PASSWORD=${DB_PASSWORD:-<db-password>}
DB_NAME=${DB_NAME:-telco_demo}
NEXT_PUBLIC_API_URL=http://$ECS_IP:8000
NEXT_PUBLIC_WS_URL=ws://$ECS_IP:8000/ws
ENVEOF"
else
    $SSH "cat > $DEPLOY_PATH/.env << 'ENVEOF'
# Demo 2 — Agentic Engineering
DEMO_MODE=deterministic
NEXT_PUBLIC_API_URL=http://$ECS_IP:8000
NEXT_PUBLIC_WS_URL=ws://$ECS_IP:8000/ws
ENVEOF"
fi
echo "  .env created"

# ── Step 6: Health check placeholders ──
echo "[6/7] Deploying smoke check..."
$SSH "cat > $DEPLOY_PATH/smoke_check.sh" < scripts/smoke_check.sh
$SSH "chmod +x $DEPLOY_PATH/smoke_check.sh"
echo "  Smoke check deployed"

# ── Step 7: Final instructions ──
echo "[7/7] Done!"
echo ""
echo "=== Next Steps ==="
echo "1. Transfer application code to ECS:"
echo "   tar czf - --exclude='node_modules' --exclude='.next' . | $SSH 'cd $DEPLOY_PATH && tar xzf -'"
echo ""
echo "2. Build and start services:"
echo "   $SSH 'cd $DEPLOY_PATH && docker compose up -d --build'"
echo ""
echo "3. Run smoke check:"
echo "   $SSH 'bash $DEPLOY_PATH/smoke_check.sh --ip=$ECS_IP'"
echo ""
echo "4. Verify endpoints:"
echo "   curl http://$ECS_IP:8000/health"
echo "   curl http://$ECS_IP:3000"
