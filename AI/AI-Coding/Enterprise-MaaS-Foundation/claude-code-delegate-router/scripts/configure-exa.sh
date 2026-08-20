#!/usr/bin/env bash
# configure-exa.sh — install the isolated Exa MCP configuration for claude-maas.
#
# Reads the Exa API key from stdin (NEVER argv) and writes:
#   ~/.config/claude-maas/exa-api-key   (mode 0600) — raw single-line key
#
# Then additively merges into the isolated claude-maas profile:
#   ~/.claude-maas/.claude.json   — mcpServers.exa-search (http, no key)
#   ~/.claude-maas/settings.json  — two exact tool permissions (no key)
#
# The key never appears in argv, stdout, stderr, logs, or any JSON file.
# Re-running replaces only the key file; the JSON files stay byte-stable.
# This installer does NOT touch the MaaS config (~/.config/claude-maas/config.json).
#
# Usage:
#   printf '%s\n' "$EXA_API_KEY" | ./scripts/configure-exa.sh
set -euo pipefail

###############################################################################
# Constants — the exact Exa contract (PRD §5.1)
###############################################################################

EXA_URL="https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
EXA_SERVER="exa-search"
PERM_SEARCH="mcp__exa-search__web_search_exa"
PERM_FETCH="mcp__exa-search__web_fetch_exa"

###############################################################################
# Helpers
###############################################################################

die() {
    echo "configure-exa: $*" >&2
    exit 1
}

###############################################################################
# Parse flags
###############################################################################

OPT_CONFIG_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config-dir)
            [[ $# -ge 2 ]] || die "--config-dir requires a value"
            OPT_CONFIG_DIR="$2"; shift 2 ;;
        --config-dir=*)
            OPT_CONFIG_DIR="${1#--config-dir=}"; shift ;;
        --help|-h)
            cat <<'USAGE'
configure-exa.sh — install isolated Exa MCP for claude-maas

Reads the Exa API key from stdin (never argv).
Writes the key to ~/.config/claude-maas/exa-api-key (0600).
Merges the exa-search HTTP MCP and two tool permissions into ~/.claude-maas/.
USAGE
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

###############################################################################
# Resolve the absolute path to the headersHelper
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER_PATH="$SCRIPT_DIR/exa-headers-helper.py"
[[ -f "$HELPER_PATH" ]] || die "headersHelper not found: $HELPER_PATH"

###############################################################################
# Read the Exa key from stdin (one non-empty line, no multiline)
###############################################################################

IFS= read -r EXA_KEY || true
EXA_KEY="${EXA_KEY%$'\r'}"

if [[ ! "$EXA_KEY" =~ [^[:space:]] ]]; then
    die "exa key must not be empty or whitespace-only"
fi

IFS= read -r _SECOND_LINE || true
if [[ -n "$_SECOND_LINE" ]]; then
    die "exa key must be a single line (multiline input rejected)"
fi
unset _SECOND_LINE

###############################################################################
# Write the key file atomically (0600)
###############################################################################

# Resolve config directory: --config-dir overrides the default.
if [[ -n "$OPT_CONFIG_DIR" ]]; then
    CONFIG_DIR="$OPT_CONFIG_DIR"
else
    CONFIG_DIR="$HOME/.config/claude-maas"
fi
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

KEY_TMP=$(mktemp "${CONFIG_DIR}/tmp.XXXXXX") || die "failed to create temp file"
trap 'rm -f "$KEY_TMP"' EXIT
chmod 600 "$KEY_TMP"
printf '%s\n' "$EXA_KEY" >"$KEY_TMP"

KEY_FILE="$CONFIG_DIR/exa-api-key"
mv "$KEY_TMP" "$KEY_FILE"
chmod 600 "$KEY_FILE"
trap - EXIT

###############################################################################
# Merge the exa-search MCP entry into ~/.claude-maas/.claude.json (additive)
###############################################################################

CLAUDE_MAAS_DIR="$HOME/.claude-maas"
mkdir -p "$CLAUDE_MAAS_DIR"
CLAUDE_JSON="$CLAUDE_MAAS_DIR/.claude.json"

# Use a same-dir temp for atomic write.
CJ_TMP=$(mktemp "${CLAUDE_MAAS_DIR}/tmp.XXXXXX") || die "failed to create temp for .claude.json"
trap 'rm -f "$CJ_TMP"' EXIT
chmod 600 "$CJ_TMP"

python3 - "$CLAUDE_JSON" "$CJ_TMP" "$EXA_SERVER" "$EXA_URL" "$HELPER_PATH" <<'PYEOF'
import json
import os
import sys

src_path = sys.argv[1]
out_path = sys.argv[2]
server = sys.argv[3]
url = sys.argv[4]
helper = sys.argv[5]

if os.path.isfile(src_path):
    with open(src_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
else:
    data = {}

if not isinstance(data, dict):
    data = {}

mcp = data.get("mcpServers")
if not isinstance(mcp, dict):
    mcp = {}

# Set the exa-search entry. This is idempotent — the exact same object each run.
mcp[server] = {
    "type": "http",
    "url": url,
    "headersHelper": helper,
}
data["mcpServers"] = mcp

with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PYEOF

mv "$CJ_TMP" "$CLAUDE_JSON"
chmod 600 "$CLAUDE_JSON"
trap - EXIT

###############################################################################
# Merge the two exact permissions into ~/.claude-maas/settings.json (additive)
###############################################################################

SETTINGS_JSON="$CLAUDE_MAAS_DIR/settings.json"
SJ_TMP=$(mktemp "${CLAUDE_MAAS_DIR}/tmp.XXXXXX") || die "failed to create temp for settings.json"
trap 'rm -f "$SJ_TMP"' EXIT
chmod 600 "$SJ_TMP"

python3 - "$SETTINGS_JSON" "$SJ_TMP" "$PERM_SEARCH" "$PERM_FETCH" <<'PYEOF'
import json
import os
import sys

src_path = sys.argv[1]
out_path = sys.argv[2]
perm_search = sys.argv[3]
perm_fetch = sys.argv[4]

if os.path.isfile(src_path):
    with open(src_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
else:
    data = {}

if not isinstance(data, dict):
    data = {}

perms = data.get("permissions")
if not isinstance(perms, dict):
    perms = {}

allow = perms.get("allow")
if not isinstance(allow, list):
    allow = []

# Add the two exact permissions if not already present (idempotent).
for perm in (perm_search, perm_fetch):
    if perm not in allow:
        allow.append(perm)

perms["allow"] = allow
data["permissions"] = perms

with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PYEOF

mv "$SJ_TMP" "$SETTINGS_JSON"
chmod 600 "$SETTINGS_JSON"
trap - EXIT

###############################################################################
# Success — key-free confirmation
###############################################################################

echo "configure-exa: exa key written to $KEY_FILE"
echo "configure-exa: MCP 'exa-search' merged into $CLAUDE_JSON"
echo "configure-exa: permissions merged into $SETTINGS_JSON"
