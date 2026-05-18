#!/usr/bin/env bash
set -euo pipefail

# ─── oh-my-opencode-slim-huawei-maas Bootstrap ───────────────────────────────
#
# End-to-end orchestrator: deploy LiteLLM (via upstream skill) → install
# opencode + oh-my-opencode-slim → mint virtual key → configure → validate.
#
# Idempotent — safe to re-run.
#
# LiteLLM location strategy:
#   - If litellm-huawei-maas is already installed somewhere → find it, use it
#   - If not found → deploy as subdirectory of this project
#
# Usage:
#   ./bootstrap.sh                                    # interactive — prompts for keys
#   ./bootstrap.sh --maas-key=KEY                     # non-interactive MaaS key
#   ./bootstrap.sh --virtual-key=sk-...               # use existing virtual key (skip minting)
#   ./bootstrap.sh --workdir=/path                    # custom LiteLLM working directory
#   ./bootstrap.sh --dry-run                          # preview changes
# ──────────────────────────────────────────────────────────────────────────────

# ── Constants ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LITELLM_URL="http://127.0.0.1:4000"
LITELLM_REPO="https://github.com/wallacelw/litellm-huawei-maas.git"
CURL_TIMEOUT=15

# ── Defaults ──
MAAS_KEY=""
VIRTUAL_KEY=""
WORKDIR=""
DRY_RUN=false

# ── Parse command-line arguments ──
for arg in "$@"; do
  case "$arg" in
    --maas-key=*)       MAAS_KEY="${arg#--maas-key=}" ;;
    --virtual-key=*)    VIRTUAL_KEY="${arg#--virtual-key=}" ;;
    --workdir=*)        WORKDIR="${arg#--workdir=}" ;;
    --dry-run)          DRY_RUN=true ;;
    *)
      echo "ERROR: Unknown argument: $arg"
      echo "Usage: $0 [--maas-key=KEY] [--virtual-key=sk-...] [--workdir=/path] [--dry-run]"
      exit 1
      ;;
  esac
done

# ── Find existing litellm-huawei-maas installation ──
# Search order:
#   1. --workdir flag (explicit override)
#   2. Docker container label (compose project working_dir)
#   3. Sibling of this project (<parent>/litellm-huawei-maas)
#   4. $HOME/litellm-huawei-maas
#   5. /opt/litellm-huawei-maas
# Returns path if found, empty if not.
find_litellm_dir() {
  # 1. Explicit override
  if [ -n "$WORKDIR" ]; then
    echo "$WORKDIR"
    return 0
  fi

  # 2. Docker container compose project working_dir (most reliable)
  if command -v docker &>/dev/null; then
    local compose_dir
    compose_dir="$(docker inspect litellm_proxy \
      --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>/dev/null || true)"
    if [ -n "$compose_dir" ] && [ -d "$compose_dir" ]; then
      echo "$compose_dir"
      return 0
    fi
  fi

  # 3. Sibling of this project
  local sibling="$(dirname "$PROJECT_DIR")/litellm-huawei-maas"
  if [ -d "$sibling/.git" ] && [ -f "$sibling/docker-compose.yml" ]; then
    echo "$sibling"
    return 0
  fi

  # 4. Home directory
  if [ -d "$HOME/litellm-huawei-maas/.git" ] && [ -f "$HOME/litellm-huawei-maas/docker-compose.yml" ]; then
    echo "$HOME/litellm-huawei-maas"
    return 0
  fi

  # 5. /opt
  if [ -d "/opt/litellm-huawei-maas/.git" ] && [ -f "/opt/litellm-huawei-maas/docker-compose.yml" ]; then
    echo "/opt/litellm-huawei-maas"
    return 0
  fi

  # Not found — return empty
  return 1
}

# ── Resolve LITELLM_MASTER_KEY from multiple sources ──
# Priority: env var → .master-key files → .env files
# Prints info lines + key to stdout. Returns 1 if not found.
resolve_master_key() {
  local litellm_dir="${LITELLM_DIR:-/home/litellm-huawei-maas}"

  # 1. Environment variable
  if [ -n "${LITELLM_MASTER_KEY:-}" ]; then
    echo "  Found LITELLM_MASTER_KEY in environment"
    echo "$LITELLM_MASTER_KEY"
    return 0
  fi

  # 2. .master-key files
  for mkf in "$litellm_dir/.master-key"; do
    if [ -f "$mkf" ]; then
      local found_key="$(cat "$mkf")"
      if [ -n "$found_key" ]; then
        echo "  Found LITELLM_MASTER_KEY in $mkf"
        echo "$found_key"
        return 0
      fi
    fi
  done

  # 3. .env files
  for ef in "$litellm_dir/.env"; do
    if [ -f "$ef" ]; then
      local found_key="$(grep -oP '^LITELLM_MASTER_KEY="?\K[^"]+' "$ef" 2>/dev/null || true)"
      if [ -n "$found_key" ]; then
        echo "  Found LITELLM_MASTER_KEY in $ef"
        # Cache to .master-key for faster future resolution
        echo "$found_key" > "${litellm_dir}/.master-key"
        chmod 600 "${litellm_dir}/.master-key"
        echo "$found_key"
        return 0
      fi
    fi
  done

  return 1
}

# ── Prompt for LITELLM_MASTER_KEY if not found automatically ──
prompt_master_key() {
  if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
    echo "  LITELLM_MASTER_KEY not found in env, .master-key, or .env files."
    echo "  Enter LITELLM_MASTER_KEY (or Ctrl+C to abort):"
    read -r LITELLM_MASTER_KEY
    if [ -z "$LITELLM_MASTER_KEY" ]; then
      echo "ERROR: LITELLM_MASTER_KEY is required to mint virtual keys."
      exit 1
    fi
  fi
}

# ── Try to resolve master key from files/env, set LITELLM_MASTER_KEY ──
try_resolve_master_key() {
  resolve_output="$(resolve_master_key 2>&1)" || true
  LITELLM_MASTER_KEY="$(echo "$resolve_output" | tail -1)"
  if [ -n "$LITELLM_MASTER_KEY" ]; then
    echo "$resolve_output" | head -n -1
    return 0
  fi
  return 1
}

# ── Wait for LiteLLM to become healthy (up to 60s) ──
wait_for_litellm() {
  echo "  Waiting for LiteLLM to become healthy..."
  local waited=0
  while [ $waited -lt 60 ]; do
    if curl -sf -m "$CURL_TIMEOUT" "$LITELLM_URL/health/liveliness" &>/dev/null; then
      echo "  LiteLLM healthy after ~${waited}s."
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  echo "ERROR: LiteLLM did not become healthy within 60s. Check: docker compose -f '$LITELLM_DIR/docker-compose.yml' logs"
  exit 1
}

# ── Error handler ──
STEP_NAME="(startup)"
error_handler() { echo ""; echo "ERROR: Bootstrap failed at step: ${STEP_NAME}"; exit 1; }
trap error_handler ERR

print_step() { echo ""; echo "─── Step ${1}: ${2} ───"; }

# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Banner
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Banner"
echo ""
echo "=== oh-my-opencode-slim-huawei-maas Bootstrap ==="
[ "$DRY_RUN" = true ] && echo "   (DRY RUN — no changes will be made)"

# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Check prerequisites
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Check prerequisites"
print_step "2" "Check prerequisites"

PREREQ_OK=true

check_prereq() {
  local name="$1" cmd="$2"
  if ! command -v "$cmd" &>/dev/null; then
    echo "  ✗ $name NOT found — $3"
    PREREQ_OK=false
  else
    echo "  ✓ $name: $($cmd --version 2>/dev/null | head -1 || echo 'found')"
  fi
}

check_prereq "bun"     bun     "install from https://bun.sh"
check_prereq "jq"      jq      "install from https://stedolan.github.io/jq/"
check_prereq "docker"  docker  "install from https://docs.docker.com/engine/install/"
check_prereq "git"     git     "install git"
check_prereq "python3" python3 "install Python 3"

if command -v docker &>/dev/null && ! docker compose version &>/dev/null; then
  echo "  ✗ docker compose V2 NOT found"
  PREREQ_OK=false
fi

# Resolve MaaS key
if [ -z "$MAAS_KEY" ]; then MAAS_KEY="${HUAWEI_MAAS_API_KEY:-}"; fi
if [ -z "$MAAS_KEY" ]; then
  if [ "$DRY_RUN" = true ]; then
    MAAS_KEY="<HUAWEI_MAAS_API_KEY>"
  else
    echo ""; echo "  Enter Huawei MaaS API key:"; read -r MAAS_KEY
    [ -z "$MAAS_KEY" ] && { echo "ERROR: MaaS API key is required."; PREREQ_OK=false; }
  fi
else
  echo "  ✓ Huawei MaaS API key set"
fi
export HUAWEI_MAAS_API_KEY="$MAAS_KEY"

[ "$PREREQ_OK" = false ] && { echo ""; echo "ERROR: Prerequisites missing. Install them and re-run."; exit 1; }

# ──────────────────────────────────────────────────────────────────────────────
# Step 3: Deploy LiteLLM — 3 scenarios
# ──────────────────────────────────────────────────────────────────────────────
# 1. LiteLLM running       → resolve master key, skip deploy
# 2. LiteLLM deployed but offline → docker compose up -d, resolve master key
# 3. No LiteLLM            → clone, init_env.sh, docker compose up -d
#
# Location strategy:
#   - Find existing installation (Docker labels, sibling, $HOME, /opt)
#   - If not found → deploy as sibling of this project
#   - Always keep both skills in the same parent directory
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Deploy LiteLLM"
print_step "3" "Deploy LiteLLM"
LITELLM_MASTER_KEY=""

# Resolve LITELLM_DIR: find existing or default to sibling of this project
FOUND_LITELLM_DIR="$(find_litellm_dir)" || true
if [ -n "$FOUND_LITELLM_DIR" ]; then
  LITELLM_DIR="$FOUND_LITELLM_DIR"
  echo "  Found existing LiteLLM at: $LITELLM_DIR"

  # Co-location check: both skills should share the same parent directory
  LITELLM_PARENT="$(dirname "$LITELLM_DIR")"
  PROJECT_PARENT="$(dirname "$PROJECT_DIR")"
  if [ "$LITELLM_PARENT" != "$PROJECT_PARENT" ]; then
    echo ""
    echo "  ⚠ LiteLLM is at: $LITELLM_DIR"
    echo "  ⚠ This project is at: $PROJECT_DIR"
    echo "  ⚠ They are in different parent directories."
    echo "  ⚠ For best organization, move this project to: $LITELLM_PARENT/oh-my-opencode-slim-huawei-maas"
    echo ""
  fi
else
  LITELLM_DIR="/home/litellm-huawei-maas"
  echo "  No existing LiteLLM found. Will deploy to: $LITELLM_DIR"
fi

# Helper: check if LiteLLM Docker container exists (running or stopped)
litellm_container_exists() {
  docker ps -a --filter "name=litellm_proxy" --format '{{.Names}}' 2>/dev/null | grep -q 'litellm_proxy'
}

# Helper: check if LiteLLM deployment files exist at LITELLM_DIR
litellm_files_exist() {
  [ -d "$LITELLM_DIR/.git" ] && [ -f "$LITELLM_DIR/docker-compose.yml" ] && [ -f "$LITELLM_DIR/.env" ]
}

if curl -sf -m "$CURL_TIMEOUT" "$LITELLM_URL/health/liveliness" &>/dev/null; then
  # ── Scenario 1: LiteLLM already running ──
  echo "  LiteLLM proxy already running at $LITELLM_URL — skipping deployment."
  if [ "$DRY_RUN" = true ]; then
    LITELLM_MASTER_KEY="<LITELLM_MASTER_KEY>"
  else
    try_resolve_master_key || prompt_master_key
  fi

elif litellm_container_exists; then
  # ── Scenario 2a: Container exists but stopped ──
  echo "  LiteLLM container exists but is not running."
  echo "  Starting existing deployment..."
  if [ "$DRY_RUN" = true ]; then
    echo "  Would run: docker compose -f $LITELLM_DIR/docker-compose.yml up -d"
    LITELLM_MASTER_KEY="<LITELLM_MASTER_KEY>"
  else
    docker compose -f "$LITELLM_DIR/docker-compose.yml" up -d
    wait_for_litellm
    try_resolve_master_key || prompt_master_key
  fi

elif litellm_files_exist; then
  # ── Scenario 2b: Files exist but containers removed (compose down) ──
  echo "  LiteLLM deployment files found at $LITELLM_DIR but no containers."
  echo "  Recreating and starting..."
  if [ "$DRY_RUN" = true ]; then
    echo "  Would run: docker compose -f $LITELLM_DIR/docker-compose.yml up -d"
    LITELLM_MASTER_KEY="<LITELLM_MASTER_KEY>"
  else
    docker compose -f "$LITELLM_DIR/docker-compose.yml" up -d
    wait_for_litellm
    try_resolve_master_key || prompt_master_key
  fi

else
  # ── Scenario 3: Fresh deploy via upstream skill ──
  if [ "$DRY_RUN" = true ]; then
    echo "  Would clone $LITELLM_REPO into $LITELLM_DIR"
    echo "  Would run: scripts/init_env.sh --ci"
    echo "  Would run: docker compose up -d"
    LITELLM_MASTER_KEY="<LITELLM_MASTER_KEY>"
  else
    echo "  No LiteLLM deployment found. Deploying via upstream skill..."

    # Clone if not already present
    if [ ! -d "$LITELLM_DIR/.git" ]; then
      echo "  Cloning $LITELLM_REPO ..."
      git clone --depth 1 "$LITELLM_REPO" "$LITELLM_DIR"
    else
      echo "  Repo already cloned at $LITELLM_DIR"
    fi

    # Configure .env via upstream script
    if [ ! -f "$LITELLM_DIR/.env" ]; then
      echo "  Running init_env.sh --ci ..."
      (cd "$LITELLM_DIR" && ./scripts/init_env.sh --ci)
    else
      echo "  .env already exists — skipping init_env.sh"
    fi

    # Start Docker Compose
    echo "  Starting Docker Compose..."
    docker compose -f "$LITELLM_DIR/docker-compose.yml" up -d
    wait_for_litellm
    try_resolve_master_key || prompt_master_key
  fi
fi

export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-}"

# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Install opencode + plugin + configure
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Install opencode + plugin + configure"
print_step "4" "Install opencode, plugin, and configure"

INSTALL_CMD=("$SCRIPT_DIR/install.sh")
[ -n "$VIRTUAL_KEY" ] && INSTALL_CMD+=("--virtual-key=$VIRTUAL_KEY")
[ "$DRY_RUN" = true ] && INSTALL_CMD+=("--dry-run")

if [ "$DRY_RUN" = true ]; then
  echo "  Would run: ${INSTALL_CMD[*]}"
else
  "${INSTALL_CMD[@]}"
  echo "  Installation and configuration complete."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 5: Validate
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Validate"
print_step "5" "Validate"

VALIDATE_CMD=("$SCRIPT_DIR/validate.sh")
[ "$DRY_RUN" = true ] && VALIDATE_CMD+=("--dry-run")

if [ "$DRY_RUN" = true ]; then
  echo "  Would run: ${VALIDATE_CMD[*]}"
else
  "${VALIDATE_CMD[@]}"
  echo "  Validation complete."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 6: Summary
# ──────────────────────────────────────────────────────────────────────────────
STEP_NAME="Summary"
print_step "6" "Summary"

if [ "$DRY_RUN" = true ]; then
  echo ""; echo "=== Dry run complete — no changes made ==="; exit 0
fi

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "LiteLLM location:  $LITELLM_DIR"
echo "LiteLLM proxy:     $LITELLM_URL"
echo "LiteLLM Admin UI:  ${LITELLM_URL}/ui"
echo "Prometheus:         http://127.0.0.1:9090"
echo "Grafana:            http://127.0.0.1:3000"
echo ""
echo "opencode config:    ~/.config/opencode/opencode.jsonc"
echo "plugin config:      ~/.config/opencode/oh-my-opencode-slim.json"
echo ""
echo "Preset: LiteLLM-Huawei-MaaS (default) — all 5 models via LiteLLM"
echo "Fallback: LiteLLM-Huawei-MaaS-Lite — 3 models (no v4-pro/v4-flash)"
echo "Direct: Huawei-MaaS / Huawei-MaaS-Lite — bypass LiteLLM proxy"
echo ""
echo "Next steps:"
echo "  1. Run: opencode"
echo "  2. Verify preset: status bar should show LiteLLM-Huawei-MaaS"
echo "  3. Switch preset: /preset LiteLLM-Huawei-MaaS-Lite"
