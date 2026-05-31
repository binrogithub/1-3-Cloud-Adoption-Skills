#!/usr/bin/env bash
# generate_config.sh — Generate litellm_config.yaml from .env
#
# Creates N deployments per model where N = HUAWEI_MAAS_API_KEY_COUNT.
# Each deployment uses a different API key (HUAWEI_MAAS_API_KEY_0 .. _N-1).
# LiteLLM load-balances across deployments with the same model_name.
#
# Usage:
#   ./scripts/generate_config.sh                                    # default: simple-shuffle
#   ./scripts/generate_config.sh --routing-strategy=least-busy      # alternative strategy
#   ./scripts/generate_config.sh --routing-strategy=latency-based-routing

set -euo pipefail

# ── Resolve project root ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CONFIG_FILE="$PROJECT_ROOT/assets/config/litellm_config.yaml"

# ── Parse args ────────────────────────────────────────────────────
ROUTING_STRATEGY="simple-shuffle"
for arg in "$@"; do
  case "$arg" in
    --routing-strategy=*) ROUTING_STRATEGY="${arg#--routing-strategy=}" ;;
    *)
      echo "Usage: $0 [--routing-strategy=STRATEGY]" >&2
      echo "  Strategies: simple-shuffle, least-busy, latency-based-routing, usage-based-routing, cost-based-routing" >&2
      exit 1
      ;;
  esac
done

# ── Load .env ─────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env not found. Run scripts/init_env.sh first." >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

# ── Determine key count ──────────────────────────────────────────
KEY_COUNT="${HUAWEI_MAAS_API_KEY_COUNT:-1}"
if [ "$KEY_COUNT" -lt 1 ]; then
  echo "ERROR: HUAWEI_MAAS_API_KEY_COUNT must be >= 1. Got: $KEY_COUNT" >&2
  exit 1
fi

# ── Validate all keys exist ──────────────────────────────────────
# Fallback: if HUAWEI_MAAS_API_KEY_0 is not set but HUAWEI_MAAS_API_KEY is,
# use HUAWEI_MAAS_API_KEY as HUAWEI_MAAS_API_KEY_0 (supports manual .env setup)
if [ "$KEY_COUNT" -ge 1 ] && [ -z "${HUAWEI_MAAS_API_KEY_0:-}" ] && [ -n "${HUAWEI_MAAS_API_KEY:-}" ]; then
  export HUAWEI_MAAS_API_KEY_0="$HUAWEI_MAAS_API_KEY"
fi

for i in $(seq 0 $((KEY_COUNT - 1))); do
  VAR="HUAWEI_MAAS_API_KEY_$i"
  VAL="${!VAR:-}"
  if [ -z "$VAL" ]; then
    echo "ERROR: $VAR is not set in .env. Each key must be present." >&2
    echo "HINT: Set HUAWEI_MAAS_API_KEY_0 or run scripts/init_env.sh to set up indexed keys." >&2
    exit 1
  fi
  if echo "$VAL" | grep -qi 'change-me\|replace\|xxx'; then
    echo "ERROR: $VAR still has a placeholder value." >&2
    exit 1
  fi
done

# ── Model catalog ────────────────────────────────────────────────
# Format: model_name:tpm:rpm:max_tokens:max_input:max_output:input_cost:output_cost
MODELS=(
  "glm-5.1:500000:30:198000:192000:128000:0.000001078:0.000003774"
  "glm-5:500000:30:198000:192000:64000:0.000000809:0.000002965"
  "deepseek-v4-pro:30000:3:1000000:1000000:128000:0.000001617:0.000003235"
  "deepseek-v4-flash:30000:3:1000000:1000000:128000:0.000000135:0.00000027"
  "deepseek-v3.2:500000:700:160000:128000:32000:0.00000027:0.000000404"
)

MODEL_COUNT=${#MODELS[@]}
TOTAL_DEPLOYMENTS=$((KEY_COUNT * MODEL_COUNT))

# ── Backup existing config ───────────────────────────────────────
if [ -f "$CONFIG_FILE" ]; then
  BACKUP="${CONFIG_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  cp "$CONFIG_FILE" "$BACKUP"
  echo "Backed up existing config to $(basename "$BACKUP")"
fi

# ── Generate config ──────────────────────────────────────────────
{
  echo "model_list:"
  echo ""
  echo "  # ───────── Huawei MaaS Models (${KEY_COUNT} deployment(s) per model, ${TOTAL_DEPLOYMENTS} total) ───────────"
  echo ""

  for model_entry in "${MODELS[@]}"; do
    IFS=':' read -r model_name tpm rpm max_tokens max_input max_output input_cost output_cost <<< "$model_entry"

    for i in $(seq 0 $((KEY_COUNT - 1))); do
      if [ "$KEY_COUNT" -gt 1 ]; then
        echo "  # ── deployment $i (key _${i}) ──"
      fi
      echo "  - model_name: $model_name"
      echo "    litellm_params:"
      echo "      model: openai/$model_name"
      echo "      api_base: os.environ/HUAWEI_MAAS_API_BASE"
      echo "      api_key: os.environ/HUAWEI_MAAS_API_KEY_$i"
      echo "      tpm: $tpm"
      echo "      rpm: $rpm"
      echo "    model_info:"
      echo "      max_tokens: $max_tokens"
      echo "      max_input_tokens: $max_input"
      echo "      max_output_tokens: $max_output"
      echo "      input_cost_per_token: $input_cost"
      echo "      output_cost_per_token: $output_cost"
      echo ""
    done
  done

  echo ""
  echo "litellm_settings:"
  echo "  num_retries: 3 # retry call 3 times within same deployment"
  echo "  request_timeout: 600 # raise TimeoutError if full request takes longer than 600s (default)"
  echo "  stream_timeout: 60 # raise TimeoutError if first token takes longer than 60s (TTFT only)"
  echo "  drop_params: True"
  echo "  set_verbose: False"
  echo "  callbacks:"
  echo "    - \"prometheus\""
  echo "    - custom_callbacks.my_prometheus_logger"
  echo "  ui_theme_config:"
  echo "    logo_url: \"https://upload.wikimedia.org/wikipedia/en/thumb/0/04/Huawei_Standard_logo.svg/3840px-Huawei_Standard_logo.svg.png\""
  echo "    favicon_url: \"https://upload.wikimedia.org/wikipedia/en/thumb/0/04/Huawei_Standard_logo.svg/3840px-Huawei_Standard_logo.svg.png\""
  echo ""
  echo "router_settings:"
  echo "  routing_strategy: $ROUTING_STRATEGY"
  echo "  num_retries: 3"
  echo "  cooldown_time: 30 # seconds to cool down a failed deployment"
  echo "  allowed_fails: 3 # failures before cooldown kicks in"
  echo ""
  echo "general_settings:"
  echo "  database_connection_pool_limit: 10"
  echo "  database_connection_timeout: 60"

} > "$CONFIG_FILE"

# ── Summary ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  Generated: $CONFIG_FILE"
echo "  Deployments: ${TOTAL_DEPLOYMENTS} total (${KEY_COUNT} per model × ${MODEL_COUNT} models)"
echo "  Routing strategy: $ROUTING_STRATEGY"
if [ "$KEY_COUNT" -gt 1 ]; then
  echo ""
  echo "  Effective capacity (per model):"
  for model_entry in "${MODELS[@]}"; do
    IFS=':' read -r model_name tpm rpm _ <<< "$model_entry"
    total_rpm=$((rpm * KEY_COUNT))
    total_tpm=$((tpm * KEY_COUNT))
    echo "    $model_name: $total_rpm RPM, $total_tpm TPM ($KEY_COUNT × $rpm RPM, $KEY_COUNT × $tpm TPM)"
  done
fi
echo "══════════════════════════════════════════════════════"
