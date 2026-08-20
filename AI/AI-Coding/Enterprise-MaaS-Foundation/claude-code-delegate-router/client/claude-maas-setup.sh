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
# Validate base URL
#
# Reject: credentials (user:pass@), fragments (#), query strings (?),
#         non-HTTPS schemes unless host is localhost or 127.0.0.1.
###############################################################################

validate_base_url() {
    local url="$1"

    # Reject empty.
    [[ -n "$url" ]] || die "base URL must not be empty"

    # Parse the URL with python3 stdlib for robustness.
    if ! python3 - "$url" <<'PYEOF'
import sys
from urllib.parse import urlparse

url = sys.argv[1]
parsed = urlparse(url)

scheme = (parsed.scheme or "").lower()
if not scheme:
    sys.stderr.write("base URL missing scheme\n")
    sys.exit(1)

# Reject credentials.
if parsed.username or parsed.password:
    sys.stderr.write("base URL must not contain credentials\n")
    sys.exit(1)

# Reject fragments.
if parsed.fragment:
    sys.stderr.write("base URL must not contain a fragment\n")
    sys.exit(1)

# Reject query strings.
if parsed.query:
    sys.stderr.write("base URL must not contain a query string\n")
    sys.exit(1)

host = (parsed.hostname or "").lower()

# Reject non-HTTPS unless host is localhost or 127.0.0.1.
if scheme != "https":
    if host not in ("localhost", "127.0.0.1"):
        sys.stderr.write(
            f"base URL must use HTTPS (got {scheme}); "
            "non-HTTPS is only allowed for localhost/127.0.0.1\n"
        )
        sys.exit(1)

# Require a host.
if not host:
    sys.stderr.write("base URL must have a host\n")
    sys.exit(1)

sys.exit(0)
PYEOF
    then
        die "invalid base URL: $OPT_BASE_URL"
    fi
}

validate_base_url "$OPT_BASE_URL"

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
# Write protection (PRD CLIENT_CONFIG_PROTECTION §2 D1)
#
# If a config.json already exists and its base-url port differs from the new
# base-url port, refuse by default. This prevents test/try-install runs from
# silently clobbering a production client config (the 2026-08-20 port-38123
# incident). Use --force to override.
###############################################################################

_extract_port() {
    # Echo the port from a URL like http://host:PORT/path, or empty if none.
    python3 - "$1" <<'PYEOF' 2>/dev/null || true
import sys, re
m = re.search(r":(\d+)(?:/|$)", sys.argv[1])
if m:
    print(m.group(1))
PYEOF
}

if [[ -f "$CONFIG_DIR/config.json" && "$OPT_FORCE" == "no" ]]; then
    _EXISTING_URL=""
    _EXISTING_URL="$(python3 - "$CONFIG_DIR/config.json" <<'PYEOF' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1]) as f:
        print(json.load(f).get("anthropic_base_url", ""))
except Exception:
    pass
PYEOF
    )" || true
    _EXISTING_PORT="$(_extract_port "$_EXISTING_URL")"
    _NEW_PORT="$(_extract_port "$OPT_BASE_URL")"
    if [[ -n "$_EXISTING_PORT" && -n "$_NEW_PORT" && "$_EXISTING_PORT" != "$_NEW_PORT" ]]; then
        cat >&2 <<EOF
claude-maas-setup: REFUSING to overwrite existing config.
  existing config:  $CONFIG_DIR/config.json
  existing base-url: $_EXISTING_URL (port $_EXISTING_PORT)
  new base-url:      $OPT_BASE_URL (port $_NEW_PORT)
  The ports differ — this looks like a test/try-install run that would
  clobber a production client config. To override, pass --force.
EOF
        exit 2
    fi
    unset _EXISTING_URL _EXISTING_PORT _NEW_PORT
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
# Install project-owned launchers into ~/.local/bin
#
# Copy or symlink client/claude-maas, client/claude-select, scripts/delegate,
# scripts/workflow into ~/.local/bin. Record ownership in manifest.json.
# If a source file does not exist yet, record its intended path in the manifest
# but do not fail.
###############################################################################

LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"

# Resolve the project root (directory containing this script's parent).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Intended launcher source paths and their install names.
declare -a LAUNCHER_SOURCES=(
    "$PROJECT_ROOT/client/claude-maas"
    "$PROJECT_ROOT/client/claude-select"
    "$PROJECT_ROOT/scripts/delegate"
    "$PROJECT_ROOT/scripts/workflow"
)
declare -a LAUNCHER_NAMES=(
    "claude-maas"
    "claude-select"
    "delegate"
    "workflow"
)

# Build the manifest JSON with python3, passing source paths and existence.
MANIFEST_TMP=$(mktemp "${CONFIG_DIR}/tmp.XXXXXX") || die "failed to create temp file for manifest"
trap 'rm -f "$MANIFEST_TMP"' EXIT
chmod 600 "$MANIFEST_TMP"

# Pass the launcher info to python3 via a temp file to avoid argv limits and
# to keep paths out of potentially-sensitive logs.
LAUNCHER_INFO_TMP=$(mktemp "${CONFIG_DIR}/tmp.XXXXXX") || die "failed to create temp file for launcher info"
trap 'rm -f "$MANIFEST_TMP" "$LAUNCHER_INFO_TMP"' EXIT
chmod 600 "$LAUNCHER_INFO_TMP"

{
    for i in "${!LAUNCHER_SOURCES[@]}"; do
        src="${LAUNCHER_SOURCES[$i]}"
        name="${LAUNCHER_NAMES[$i]}"
        exists="no"
        [[ -f "$src" ]] && exists="yes"
        printf '%s\t%s\t%s\n' "$name" "$src" "$exists"
    done
} >"$LAUNCHER_INFO_TMP"

python3 - "$MANIFEST_TMP" "$LAUNCHER_INFO_TMP" "$LOCAL_BIN" "$OPT_BASE_URL" <<'PYEOF'
import json
import os
import sys

manifest_path = sys.argv[1]
info_path = sys.argv[2]
local_bin = sys.argv[3]
base_url = sys.argv[4]

launchers = []
with open(info_path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        name, source, exists = line.split("\t")
        installed_path = os.path.join(local_bin, name)
        launchers.append({
            "name": name,
            "source": source,
            "installed": installed_path,
            "source_exists": exists == "yes",
        })

manifest = {
    "version": 1,
    "launchers": launchers,
    "local_bin": local_bin,
    # Ownership fields consumed by scripts/migrate.sh to remove only values
    # this project provably owns (endpoint + marker ownership proof).
    "endpoint": base_url,
    "markers": [
        "<!-- BEGIN claude-maas-policy -->",
        "<!-- END claude-maas-policy -->",
    ],
    "owned_hook_command": "route-hint",
    "owned_env_keys": [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
    ],
    "owned_wrapper": "claude-glm",
}

with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2)
    fh.write("\n")
PYEOF

MANIFEST_FILE="$CONFIG_DIR/manifest.json"
mv "$MANIFEST_TMP" "$MANIFEST_FILE"
chmod 600 "$MANIFEST_FILE"

# Clean up the launcher info temp file.
rm -f "$LAUNCHER_INFO_TMP"
trap - EXIT

# Actually copy/symlink launchers that exist. Use symlinks so updates to the
# project are reflected automatically. Remove any stale existing entry first.
for i in "${!LAUNCHER_SOURCES[@]}"; do
    src="${LAUNCHER_SOURCES[$i]}"
    name="${LAUNCHER_NAMES[$i]}"
    dest="$LOCAL_BIN/$name"
    if [[ -f "$src" ]]; then
        # Remove existing file/symlink (but never follow a symlink to a dir).
        rm -f "$dest" 2>/dev/null || true
        ln -s "$src" "$dest"
    fi
done

###############################################################################
# Success — print a safe (key-free) confirmation
###############################################################################

echo "claude-maas-setup: configuration written to $CONFIG_DIR"
echo "claude-maas-setup: model=$OPT_MODEL base-url=$OPT_BASE_URL"
echo "claude-maas-setup: launchers installed to $LOCAL_BIN (see manifest.json)"
