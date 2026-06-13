#!/usr/bin/env bash
# init_env.sh — Initialize .env for deployment
#
# Three modes:
#   interactive  (default)  — prompt for each secret, offer generated defaults
#   --auto                  — generate all secrets, prompt only for HUAWEI_MAAS_API_KEY + extras
#   --ci                   — generate all secrets non-interactively;
#                            requires HUAWEI_MAAS_API_KEY env var pre-set
#                            optional HUAWEI_MAAS_EXTRA_API_KEYS (comma-separated)
#
# Usage:
#   ./scripts/init_env.sh              # interactive — you choose every value
#   ./scripts/init_env.sh --auto       # agent mode — auto-generate, prompt for MaaS keys only
#   ./scripts/init_env.sh --ci         # CI mode — all from env vars, no prompts

set -euo pipefail

# ── Resolve project root ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_EXAMPLE="$PROJECT_ROOT/assets/config/.env.example"
ENV_FILE="$PROJECT_ROOT/.env"

# ── Parse mode ────────────────────────────────────────────────────
MODE="interactive"
if [[ "${1:-}" == "--auto" ]]; then MODE="auto"
elif [[ "${1:-}" == "--ci" ]]; then MODE="ci"
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--auto|--ci]" >&2; exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────
generate_secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(32))'; }
generate_master_key() { echo "sk-$(generate_secret)"; }

prompt_value() {
  local varname="$1" description="$2" default="$3" is_secret="${4:-yes}"
  if [[ "$MODE" == "ci" ]]; then
    # CI mode: use env var or default, never prompt
    local val="${!varname:-$default}"
    echo "$val"
    return
  fi

  local display_default
  if [[ "$is_secret" == "yes" && ${#default} -gt 8 ]]; then
    display_default="${default:0:6}...${default: -4}"
  else
    display_default="$default"
  fi

  if [[ "$MODE" == "auto" && "$varname" != "HUAWEI_MAAS_API_KEY" ]]; then
    # Auto mode: accept default for everything except MaaS key
    echo "$default"
    return
  fi

  # Interactive or auto+MaaS key: prompt the user
  local prompt_text
  if [[ -n "$default" ]]; then
    prompt_text="  $description [$display_default]: "
  else
    prompt_text="  $description: "
  fi

  if [[ -t 0 ]]; then
    # Terminal: use read
    if [[ "$is_secret" == "yes" ]]; then
      read -r -p "$prompt_text" input < /dev/tty
    else
      read -r -p "$prompt_text" input < /dev/tty
    fi
  else
    # Piped/agent: read from stdin
    read -r input
  fi

  echo "${input:-$default}"
}

# ── Banner ────────────────────────────────────────────────────────
echo "══════════════════════════════════════════════════════"
echo "  LiteLLM Huawei MaaS Proxy — Environment Setup"
echo "  Mode: $MODE"
echo "══════════════════════════════════════════════════════"
echo ""

# ── Check .env.example exists ────────────────────────────────────
if [[ ! -f "$ENV_EXAMPLE" ]]; then
  echo "ERROR: $ENV_EXAMPLE not found." >&2; exit 1
fi

# ── Check if .env already exists ─────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  if [[ "$MODE" == "ci" ]]; then
    echo "WARNING: .env already exists. Overwriting in CI mode."
  else
    echo "WARNING: .env already exists."
    read -r -p "  Overwrite? [y/N]: " overwrite < /dev/tty
    if [[ "${overwrite,,}" != "y" ]]; then
      echo "Aborting. Edit .env manually or remove it first."; exit 0
    fi
  fi
fi

# ── Generate defaults ────────────────────────────────────────────
DEFAULT_MASTER_KEY=$(generate_master_key)
DEFAULT_SALT_KEY=$(generate_secret)
DEFAULT_DB_PASSWORD=$(generate_secret)
DEFAULT_GRAFANA_PASSWORD=$(generate_secret)
DEFAULT_MAAS_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
DEFAULT_RETENTION="15d"

# ── Collect values ────────────────────────────────────────────────
echo "Configuring secrets and endpoints..."
echo ""

MASTER_KEY=$(prompt_value "LITELLM_MASTER_KEY" "LITELLM_MASTER_KEY (admin key, must start with sk-)" "$DEFAULT_MASTER_KEY" "yes")
SALT_KEY=$(prompt_value "LITELLM_SALT_KEY" "LITELLM_SALT_KEY (key encryption salt, immutable after first virtual key)" "$DEFAULT_SALT_KEY" "yes")
DB_PASSWORD=$(prompt_value "DB_PASSWORD" "DB_PASSWORD (PostgreSQL llmproxy user)" "$DEFAULT_DB_PASSWORD" "yes")
MAAS_API_KEY=$(prompt_value "HUAWEI_MAAS_API_KEY" "HUAWEI_MAAS_API_KEY (main key from ModelArts MaaS console, ap-southeast-1)" "" "yes")
MAAS_API_BASE=$(prompt_value "HUAWEI_MAAS_API_BASE" "HUAWEI_MAAS_API_BASE (MaaS endpoint URL)" "$DEFAULT_MAAS_BASE" "no")
RETENTION=$(prompt_value "PROMETHEUS_RETENTION" "PROMETHEUS_RETENTION (TSDB retention)" "$DEFAULT_RETENTION" "no")
GRAFANA_PASSWORD=$(prompt_value "GRAFANA_PASSWORD" "GRAFANA_PASSWORD (Grafana admin)" "$DEFAULT_GRAFANA_PASSWORD" "yes")

# ── Collect additional MaaS API keys ─────────────────────────────
EXTRA_KEYS=()
if [[ "$MODE" == "ci" ]]; then
  # CI mode: read from HUAWEI_MAAS_EXTRA_API_KEYS (comma-separated)
  if [[ -n "${HUAWEI_MAAS_EXTRA_API_KEYS:-}" ]]; then
    IFS=',' read -ra EXTRA_KEYS <<< "$HUAWEI_MAAS_EXTRA_API_KEYS"
  fi
else
  # Interactive / auto: ask for count, then prompt for each
  local_count_prompt="  Number of additional MaaS API keys [0]: "
  if [[ -t 0 ]]; then
    read -r -p "$local_count_prompt" extra_count < /dev/tty
  else
    read -r extra_count
  fi
  extra_count="${extra_count:-0}"

  if [[ "$extra_count" -gt 0 ]] 2>/dev/null; then
    for i in $(seq 1 "$extra_count"); do
      local_key_prompt="  Additional MaaS API key $i: "
      if [[ -t 0 ]]; then
        read -r -p "$local_key_prompt" extra_key < /dev/tty
      else
        read -r extra_key
      fi
      if [[ -n "$extra_key" ]]; then
        EXTRA_KEYS+=("$extra_key")
      else
        echo "  WARNING: Key $i was empty — skipping."
      fi
    done
  fi
fi

# Total key count: 1 (main) + extras
KEY_COUNT=$((1 + ${#EXTRA_KEYS[@]}))

# ── Validate ──────────────────────────────────────────────────────
ERRORS=0

if [[ ! "$MASTER_KEY" == sk-* ]]; then
  echo "ERROR: LITELLM_MASTER_KEY must start with 'sk-'. Got: ${MASTER_KEY:0:6}..." >&2
  ((ERRORS++))
fi

if [[ -z "$MAAS_API_KEY" ]]; then
  echo "ERROR: HUAWEI_MAAS_API_KEY is required. Get it from https://console.huaweicloud.com/modelarts/" >&2
  ((ERRORS++))
fi

if [[ "$MAAS_API_KEY" == *"change-me"* ]] || [[ "$MAAS_API_KEY" == *"xxx"* ]]; then
  echo "ERROR: HUAWEI_MAAS_API_KEY still has a placeholder value." >&2
  ((ERRORS++))
fi

# Validate extra keys
for i in "${!EXTRA_KEYS[@]}"; do
  key="${EXTRA_KEYS[$i]}"
  if [[ -z "$key" ]]; then
    echo "ERROR: Additional MaaS API key $((i + 1)) is empty." >&2
    ((ERRORS++))
  elif [[ "$key" == *"change-me"* ]] || [[ "$key" == *"xxx"* ]]; then
    echo "ERROR: Additional MaaS API key $((i + 1)) still has a placeholder value." >&2
    ((ERRORS++))
  fi
done

if [[ "$ERRORS" -gt 0 ]]; then
  echo "" >&2
  echo "Validation failed with $ERRORS error(s). Fix the above and re-run." >&2
  exit 1
fi

# ── Write .env ────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
# ── Proxy Auth ───────────────────────────────────
LITELLM_MASTER_KEY="${MASTER_KEY}"
LITELLM_SALT_KEY="${SALT_KEY}"

# ── Database ─────────────────────────────────────
DB_PASSWORD="${DB_PASSWORD}"

# ── Huawei MaaS ──────────────────────────────────
HUAWEI_MAAS_API_KEY="${MAAS_API_KEY}"
HUAWEI_MAAS_API_KEY_COUNT=${KEY_COUNT}
HUAWEI_MAAS_API_KEY_0="${MAAS_API_KEY}"
EOF

# Write extra keys
for i in "${!EXTRA_KEYS[@]}"; do
  echo "HUAWEI_MAAS_API_KEY_$((i + 1))=\"${EXTRA_KEYS[$i]}\"" >> "$ENV_FILE"
done

cat >> "$ENV_FILE" <<EOF
HUAWEI_MAAS_API_BASE="${MAAS_API_BASE}"

# ── Prometheus ───────────────────────────────────
PROMETHEUS_RETENTION="${RETENTION}"

# ── Grafana ──────────────────────────────────────
GRAFANA_PASSWORD="${GRAFANA_PASSWORD}"
EOF

chmod 600 "$ENV_FILE"

# ── Generate litellm_config.yaml ─────────────────────────────────
echo ""
echo "Generating litellm_config.yaml..."
if "$SCRIPT_DIR/generate_config.sh" 2>&1; then
  echo "Config generation successful."
else
  echo "WARNING: Config generation failed. Run scripts/generate_config.sh manually after fixing .env."
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  .env written to $ENV_FILE"
echo "  Permissions: $(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE")"
echo ""
echo "  Values set:"
echo "    LITELLM_MASTER_KEY  = ${MASTER_KEY:0:8}...${MASTER_KEY: -4}"
echo "    LITELLM_SALT_KEY    = ${SALT_KEY:0:6}...${SALT_KEY: -4}"
echo "    DB_PASSWORD         = ${DB_PASSWORD:0:6}...${DB_PASSWORD: -4}"
echo "    HUAWEI_MAAS_API_KEY = ${MAAS_API_KEY:0:6}...${MAAS_API_KEY: -4}"
echo "    MaaS API key count  = ${KEY_COUNT} (${KEY_COUNT} deployment(s) per model, $((KEY_COUNT * 5)) total)"
if [[ "$KEY_COUNT" -gt 1 ]]; then
  for i in "${!EXTRA_KEYS[@]}"; do
    echo "    Additional key $((i + 1))   = ${EXTRA_KEYS[$i]:0:6}...${EXTRA_KEYS[$i]: -4}"
  done
fi
echo "    HUAWEI_MAAS_API_BASE= $MAAS_API_BASE"
echo "    PROMETHEUS_RETENTION= $RETENTION"
echo "    GRAFANA_PASSWORD    = ${GRAFANA_PASSWORD:0:6}...${GRAFANA_PASSWORD: -4}"
echo ""
echo "  Next steps:"
echo "    docker compose up -d"
echo "    ./scripts/validate_e2e.sh"
echo "══════════════════════════════════════════════════════"
