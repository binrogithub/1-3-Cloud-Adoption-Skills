#!/usr/bin/env bash
# claude-maas-setup.sh — install the isolated MaaS credential configuration.
#
# Reads the MaaS API key from stdin (NEVER argv) and writes:
#   ~/.config/claude-maas/api-key      (mode 0600) — raw single-line key
#   ~/.config/claude-maas/config.json  (mode 0600) — non-secret settings
#   ~/.config/claude-maas/manifest.json(mode 0600) — launcher path manifest
#
# The key is stored as DATA (read with IFS= read -r), never sourced or eval'd.
# The key never appears in argv, stdout, stderr, logs, or the manifest.
#
# This installer NEVER writes shell profiles (~/.bashrc, ~/.zshrc, ...) or the
# plain Claude config directory (~/.claude/). It only writes under
# ~/.config/claude-maas/ and creates ~/.local/bin for launcher copies/symlinks.
#
# Usage:
#   printf '%s\n' "$HUAWEI_MAAS_API_KEY" | ./client/claude-maas-setup.sh \
#       --base-url https://api-ap-southeast-1.modelarts-maas.com/anthropic \
#       --model glm-5.2 \
#       --context-tokens 1000000 \
#       --max-output-tokens 32768
set -euo pipefail

###############################################################################
# Defaults
###############################################################################

DEFAULT_BASE_URL="https://api-ap-southeast-1.modelarts-maas.com/anthropic"
DEFAULT_MODEL="glm-5.2"
DEFAULT_CONTEXT_TOKENS="1000000"
DEFAULT_MAX_OUTPUT_TOKENS="32768"

OPT_BASE_URL="$DEFAULT_BASE_URL"
OPT_MODEL="$DEFAULT_MODEL"
OPT_CONTEXT_TOKENS="$DEFAULT_CONTEXT_TOKENS"
OPT_MAX_OUTPUT_TOKENS="$DEFAULT_MAX_OUTPUT_TOKENS"
OPT_CONFIG_DIR=""
OPT_FORCE="no"

###############################################################################
# Helpers
###############################################################################

die() {
    # Print a safe error message (never the key) to stderr and exit 1.
    echo "claude-maas-setup: $*" >&2
    exit 1
}

###############################################################################
# Parse flags
###############################################################################

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-url)
            [[ $# -ge 2 ]] || die "--base-url requires a value"
            OPT_BASE_URL="$2"
            shift 2
            ;;
        --base-url=*)
            OPT_BASE_URL="${1#--base-url=}"
            shift
            ;;
        --model)
            [[ $# -ge 2 ]] || die "--model requires a value"
            OPT_MODEL="$2"
            shift 2
            ;;
        --model=*)
            OPT_MODEL="${1#--model=}"
            shift
            ;;
        --context-tokens)
            [[ $# -ge 2 ]] || die "--context-tokens requires a value"
            OPT_CONTEXT_TOKENS="$2"
            shift 2
            ;;
        --context-tokens=*)
            OPT_CONTEXT_TOKENS="${1#--context-tokens=}"
            shift
            ;;
        --max-output-tokens)
            [[ $# -ge 2 ]] || die "--max-output-tokens requires a value"
            OPT_MAX_OUTPUT_TOKENS="$2"
            shift 2
            ;;
        --max-output-tokens=*)
            OPT_MAX_OUTPUT_TOKENS="${1#--max-output-tokens=}"
            shift
            ;;
        --config-dir)
            [[ $# -ge 2 ]] || die "--config-dir requires a value"
            OPT_CONFIG_DIR="$2"
            shift 2
            ;;
        --config-dir=*)
            OPT_CONFIG_DIR="${1#--config-dir=}"
            shift
            ;;
        --force)
            OPT_FORCE="yes"; shift
            ;;
        --help|-h)
            cat <<'USAGE'
claude-maas-setup.sh — install isolated MaaS credentials

Reads the API key from stdin (never argv).

Options:
  --base-url URL          MaaS Anthropic base URL (default: .../anthropic)
  --model MODEL           Model id (default: glm-5.2)
  --context-tokens N      Max context tokens (default: 1000000)
  --max-output-tokens N   Max output tokens (default: 32768)
  --config-dir PATH       Config directory (default: ~/.config/claude-maas)
  --force                 Overwrite existing config even if the base-url port
                          differs (default: refuse to avoid clobbering a
                          production config with a test port)
USAGE
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

###############################################################################
# Validate numeric flags
###############################################################################

[[ "$OPT_CONTEXT_TOKENS" =~ ^[0-9]+$ ]] || \
    die "--context-tokens must be a non-negative integer (got: $OPT_CONTEXT_TOKENS)"
[[ "$OPT_MAX_OUTPUT_TOKENS" =~ ^[0-9]+$ ]] || \
    die "--max-output-tokens must be a non-negative integer (got: $OPT_MAX_OUTPUT_TOKENS)"

###############################################################################
# Validate base URL (HTTPS or localhost, no creds/fragment/query, must have host)
###############################################################################

python3 -c '
import sys; from urllib.parse import urlparse as u
p = u(sys.argv[1]); s = (p.scheme or "").lower(); h = (p.hostname or "").lower()
if not s: sys.exit("base URL missing scheme")
if p.username or p.password: sys.exit("base URL must not contain credentials")
if p.fragment: sys.exit("base URL must not contain a fragment")
if p.query: sys.exit("base URL must not contain a query string")
if s != "https" and h not in ("localhost", "127.0.0.1"): sys.exit(f"base URL must use HTTPS (got {s})")
if not h: sys.exit("base URL must have a host")
' "$OPT_BASE_URL" || die "invalid base URL: $OPT_BASE_URL"

###############################################################################
# Read the API key from stdin
#
# Read exactly one non-empty line. Reject empty input and multiline input.
# The key is read as DATA (IFS= read -r), never sourced or eval'd.
###############################################################################

# Read the first line.
IFS= read -r API_KEY || true

# Strip a trailing carriage return (in case stdin came from a Windows file).
API_KEY="${API_KEY%$'\r'}"

# Reject empty / whitespace-only first line.
# Check for at least one non-whitespace character using a regex.
if [[ ! "$API_KEY" =~ [^[:space:]] ]]; then
    die "api key must not be empty or whitespace-only"
fi

# Reject multiline input: if there is more data on stdin, fail.
# We read a second line; if it is non-empty, the input was multiline.
IFS= read -r _SECOND_LINE || true
if [[ -n "$_SECOND_LINE" ]]; then
    # Do NOT print the second line — it could be key material.
    die "api key must be a single line (multiline input rejected)"
fi
unset _SECOND_LINE

###############################################################################
# Create the configuration directory (0700)
###############################################################################

# Resolve config directory: --config-dir overrides the default.
if [[ -n "$OPT_CONFIG_DIR" ]]; then
    CONFIG_DIR="$OPT_CONFIG_DIR"
else
    CONFIG_DIR="$HOME/.config/claude-maas"
fi
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

###############################################################################
# Write protection — refuse if existing config has a different port (§2 D1)
###############################################################################

if [[ -f "$CONFIG_DIR/config.json" && "$OPT_FORCE" == "no" ]]; then
    _EXISTING_PORT="$(python3 -c 'import json,sys,re
try:
    u=json.load(open(sys.argv[1])).get("anthropic_base_url","")
    m=re.search(r":(\d+)(?:/|$)",u)
    if m: print(m.group(1))
except: pass' "$CONFIG_DIR/config.json" 2>/dev/null || true)"
    _NEW_PORT="$(python3 -c 'import sys,re
m=re.search(r":(\d+)(?:/|$)",sys.argv[1])
if m: print(m.group(1))' "$OPT_BASE_URL" 2>/dev/null || true)"
    if [[ -n "$_EXISTING_PORT" && -n "$_NEW_PORT" && "$_EXISTING_PORT" != "$_NEW_PORT" ]]; then
        echo "claude-maas-setup: REFUSING to overwrite — port mismatch ($_EXISTING_PORT vs $_NEW_PORT). Pass --force to override." >&2
        exit 2
    fi
    unset _EXISTING_PORT _NEW_PORT
fi

###############################################################################
# Write the api-key file atomically (mktemp + chmod 0600 + mv)
###############################################################################

# Create a temp file inside the config dir (same filesystem for atomic mv).
KEY_TMP=$(mktemp "${CONFIG_DIR}/tmp.XXXXXX") || die "failed to create temp file for api-key"
# Ensure the temp file is removed on error.
trap 'rm -f "$KEY_TMP"' EXIT

chmod 600 "$KEY_TMP"
# Write the key followed by a newline. Using printf to avoid echo portability
# issues. The key is in a variable, never on the command line of another tool.
printf '%s\n' "$API_KEY" >"$KEY_TMP"

KEY_FILE="$CONFIG_DIR/api-key"
mv "$KEY_TMP" "$KEY_FILE"
chmod 600 "$KEY_FILE"
# Clear the trap since the temp file is gone.
trap - EXIT

###############################################################################
# Write config.json atomically (mode 0600)
###############################################################################

CFG_TMP=$(mktemp "${CONFIG_DIR}/tmp.XXXXXX") || die "failed to create temp file for config.json"
trap 'rm -f "$CFG_TMP"' EXIT
chmod 600 "$CFG_TMP"

# Write config.json using python3 for proper JSON encoding.
python3 - "$CFG_TMP" "$OPT_BASE_URL" "$OPT_MODEL" "$OPT_CONTEXT_TOKENS" "$OPT_MAX_OUTPUT_TOKENS" <<'PYEOF'
import json
import sys

out_path = sys.argv[1]
base_url = sys.argv[2]
model = sys.argv[3]
context_tokens = int(sys.argv[4])
max_output_tokens = int(sys.argv[5])

data = {
    "anthropic_base_url": base_url,
    "model": model,
    "context_tokens": context_tokens,
    "max_output_tokens": max_output_tokens,
}

with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PYEOF

CFG_FILE="$CONFIG_DIR/config.json"
mv "$CFG_TMP" "$CFG_FILE"
chmod 600 "$CFG_FILE"
trap - EXIT

###############################################################################
# Install project-owned launchers into ~/.local/bin (symlinks)
###############################################################################

LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for pair in \
    "client/claude-maas:claude-maas" \
    "client/claude-select:claude-select" \
    "scripts/delegate:delegate" \
    "scripts/maas-delegate:maas-delegate" \
    "scripts/workflow:workflow"; do
    src="$PROJECT_ROOT/${pair%%:*}"
    name="${pair##*:}"
    if [[ -f "$src" ]]; then
        rm -f "$LOCAL_BIN/$name" 2>/dev/null || true
        ln -s "$src" "$LOCAL_BIN/$name"
    fi
done

###############################################################################
# Warn about repo-pointing symlinks elsewhere on PATH (R1 hygiene)
###############################################################################

_repo_real="$(readlink -f "$PROJECT_ROOT" 2>/dev/null || echo "$PROJECT_ROOT")"
IFS=':' read -r -a _warn_path_parts <<<"${PATH:-}"
for _wd in "${_warn_path_parts[@]}"; do
    [[ -n "$_wd" && -d "$_wd" ]] || continue
    [[ "$_wd" == "$LOCAL_BIN" ]] && continue
    for _we in "$_wd"/*; do
        [[ -L "$_we" ]] || continue
        _wt="$(readlink -f "$_we" 2>/dev/null || true)"
        [[ -n "$_wt" ]] || continue
        if [[ "$_wt" == "$_repo_real" || "$_wt" == "$_repo_real"/* ]]; then
            echo "claude-maas-setup: WARNING — duplicate repo symlink outside ~/.local/bin: $_we -> $_wt" >&2
            echo "claude-maas-setup:   remove with: rm -f '$_we'" >&2
        fi
    done
done
unset _repo_real _warn_path_parts _wd _we _wt

###############################################################################
# R2 hygiene: never leave key backups in ~/.config (PRD PROJECT_CLOSURE_V1 §3.2)
#
# The setup writes the key atomically (mktemp + mv) and never creates a .bak
# intentionally. This defensive sweep removes any stray backup residue left
# by older manual rotations and forces the live key/config to 0600.
###############################################################################

rm -f "$CONFIG_DIR"/api-key.bak "$CONFIG_DIR"/api-key.bak-* \
      "$CONFIG_DIR"/config.json.bak "$CONFIG_DIR"/config.json.bak-* 2>/dev/null || true
chmod 600 "$KEY_FILE" "$CFG_FILE" 2>/dev/null || true

###############################################################################
# Success — print a safe (key-free) confirmation
###############################################################################

echo "claude-maas-setup: configuration written to $CONFIG_DIR"
echo "claude-maas-setup: model=$OPT_MODEL base-url=$OPT_BASE_URL"
echo "claude-maas-setup: launchers installed to $LOCAL_BIN (see manifest.json)"
