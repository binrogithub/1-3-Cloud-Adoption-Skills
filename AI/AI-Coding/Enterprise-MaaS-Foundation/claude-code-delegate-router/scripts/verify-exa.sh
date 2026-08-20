#!/usr/bin/env bash
# verify-exa.sh — Exa release verification for the isolated claude-maas profile.
#
# Offline gates (default; no network, no key required for most):
#   1. key-mode      — ~/.config/claude-maas/exa-api-key is 0600 regular
#   2. helper        — scripts/exa-headers-helper.py exists and compiles
#   3. plain-absent  — plain ~/.claude has no exa-search MCP / EXA_API_KEY
#   4. isolated      — ~/.claude-maas/.claude.json has the exa-search HTTP entry
#   5. tools         — exactly web_search_exa + web_fetch_exa allowed
#
# Live gates (only with --live and a key on stdin):
#   6. mcp-health    — CLAUDE_CONFIG_DIR=~/.claude-maas claude mcp list shows Connected
#   7. search        — a search canary returns an HTTPS source URL
#   8. fetch         — a fetch canary returns page content
#   9. model         — glm-5.2 only
#  10. context       — contextWindow 1000000
#
# The key is read from stdin (never argv) and redacted from all output.
set -euo pipefail

###############################################################################
# Constants
###############################################################################

EXA_SERVER="exa-search"
EXA_URL="https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
EXPECTED_HOST="mcp.exa.ai"
EXPECTED_PATH="/mcp"
PERM_SEARCH="mcp__exa-search__web_search_exa"
PERM_FETCH="mcp__exa-search__web_fetch_exa"
ALLOWED_PERMS=("$PERM_SEARCH" "$PERM_FETCH")
EXPECTED_MODEL="glm-5.2"
EXPECTED_CONTEXT="1000000"

###############################################################################
# Helpers
###############################################################################

die() {
    echo "verify-exa: $*" >&2
    exit 1
}

OVERALL_OK=1
VERIFY_KEY=""

redact() {
    local text="$1"
    if [[ -n "$VERIFY_KEY" ]]; then
        text="${text//"$VERIFY_KEY"/[REDACTED]}"
    fi
    printf '%s' "$text"
}

gate_pass() {
    echo "  $1: PASS"
}

gate_fail() {
    echo "  $1: FAIL"
    OVERALL_OK=0
}

###############################################################################
# Parse flags
###############################################################################

MODE="offline"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --offline) MODE="offline"; shift ;;
        --live)    MODE="live";    shift ;;
        --help|-h)
            cat <<'USAGE'
verify-exa.sh — Exa release verification

Usage:
  ./scripts/verify-exa.sh --offline   # offline gates only (default)
  printf '%s\n' "$KEY" | ./scripts/verify-exa.sh --live   # offline + live gates
USAGE
            exit 0
            ;;
        *) die "unknown option: $1" ;;
    esac
done

###############################################################################
# Read key from stdin (for redaction; live mode requires it)
###############################################################################

IFS= read -r VERIFY_KEY || true
VERIFY_KEY="${VERIFY_KEY%$'\r'}"

if [[ "$MODE" == "live" && -z "$VERIFY_KEY" ]]; then
    die "live mode requires the Exa key on stdin"
fi

###############################################################################
# Paths
###############################################################################

KEY_FILE="$HOME/.config/claude-maas/exa-api-key"
CLAUDE_MAAS_DIR="$HOME/.claude-maas"
CLAUDE_JSON="$CLAUDE_MAAS_DIR/.claude.json"
SETTINGS_JSON="$CLAUDE_MAAS_DIR/settings.json"
PLAIN_CLAUDE_JSON="$HOME/.claude/.claude.json"
PLAIN_SETTINGS="$HOME/.claude/settings.json"
HELPER="$(cd "$(dirname "$0")" && pwd)/exa-headers-helper.py"

###############################################################################
# Offline gates
###############################################################################

echo "[verify-exa] offline gates"

# --- Gate 1: key-mode ---
echo "key-mode:"
if [[ -f "$KEY_FILE" ]]; then
    mode=$(stat -c '%a' "$KEY_FILE" 2>/dev/null || stat -f '%A' "$KEY_FILE" 2>/dev/null) || true
    if [[ -n "$mode" ]]; then
        mode=$(( 8#${mode} & 8#777 ))
        if [[ "$mode" -eq 8#600 ]]; then
            # Check it's a regular file, not a symlink.
            if [[ -L "$KEY_FILE" ]]; then
                gate_fail "key-mode"
                echo "    key file is a symlink"
            else
                gate_pass "key-mode"
            fi
        else
            gate_fail "key-mode"
            echo "    mode is $(printf '%o' "$mode"), expected 600"
        fi
    else
        gate_fail "key-mode"
        echo "    cannot determine mode"
    fi
else
    gate_fail "key-mode"
    echo "    key file missing: $KEY_FILE"
fi

# --- Gate 2: helper ---
echo "helper:"
if [[ -f "$HELPER" ]]; then
    if python3 -m py_compile "$HELPER" 2>/dev/null; then
        gate_pass "helper"
    else
        gate_fail "helper"
        echo "    helper does not compile"
    fi
else
    gate_fail "helper"
    echo "    helper missing: $HELPER"
fi

# --- Gate 3: plain-absent ---
echo "plain-absent:"
plain_ok=1
if [[ -f "$PLAIN_CLAUDE_JSON" ]]; then
    if python3 - "$PLAIN_CLAUDE_JSON" "$EXA_SERVER" <<'PYEOF'
import json, sys
path, server = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)
mcp = data.get("mcpServers", {}) if isinstance(data, dict) else {}
if server in mcp:
    sys.exit(1)
sys.exit(0)
PYEOF
    then
        :
    else
        plain_ok=0
        echo "    plain .claude.json still has exa-search MCP"
    fi
fi
if [[ -f "$PLAIN_SETTINGS" ]]; then
    if python3 - "$PLAIN_SETTINGS" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)
env = data.get("env", {}) if isinstance(data, dict) else {}
if "EXA_API_KEY" in env:
    sys.exit(1)
sys.exit(0)
PYEOF
    then
        :
    else
        plain_ok=0
        echo "    plain settings.json still has EXA_API_KEY"
    fi
fi
if [[ $plain_ok -eq 1 ]]; then
    gate_pass "plain-absent"
else
    gate_fail "plain-absent"
fi

# --- Gate 4: isolated ---
echo "isolated:"
isolated_ok=0
if [[ -f "$CLAUDE_JSON" ]]; then
    if python3 - "$CLAUDE_JSON" "$EXA_SERVER" "$EXA_URL" "$EXPECTED_HOST" "$EXPECTED_PATH" <<'PYEOF'
import json, sys
from urllib.parse import urlsplit
path, server, expected_url, expected_host, expected_path = sys.argv[1:6]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(1)
mcp = data.get("mcpServers", {}) if isinstance(data, dict) else {}
if server not in mcp:
    sys.exit(1)
entry = mcp[server]
if entry.get("type") != "http":
    sys.exit(1)
if entry.get("url") != expected_url:
    sys.exit(1)
parts = urlsplit(entry.get("url", ""))
if (parts.scheme or "").lower() != "https":
    sys.exit(1)
if (parts.hostname or "").lower() != expected_host:
    sys.exit(1)
if parts.path != expected_path:
    sys.exit(1)
if "headersHelper" not in entry:
    sys.exit(1)
sys.exit(0)
PYEOF
    then
        isolated_ok=1
    fi
fi
if [[ $isolated_ok -eq 1 ]]; then
    gate_pass "isolated"
else
    gate_fail "isolated"
    echo "    isolated exa-search HTTP MCP entry missing or wrong"
fi

# --- Gate 5: tools ---
echo "tools:"
tools_ok=0
if [[ -f "$SETTINGS_JSON" ]]; then
    if python3 - "$SETTINGS_JSON" "$PERM_SEARCH" "$PERM_FETCH" <<'PYEOF'
import json, sys
path = sys.argv[1]
allowed_perms = set(sys.argv[2:])
try:
    data = json.load(open(path))
except Exception:
    sys.exit(1)
perms = data.get("permissions", {}) if isinstance(data, dict) else {}
allow = perms.get("allow", [])
if not isinstance(allow, list):
    sys.exit(1)
allow_set = set(allow)
# Must contain exactly the two allowed Exa perms and no other exa-search perms.
exa_perms = {p for p in allow_set if p.startswith("mcp__exa-search__")}
if exa_perms != allowed_perms:
    sys.exit(1)
sys.exit(0)
PYEOF
    then
        tools_ok=1
    fi
fi
if [[ $tools_ok -eq 1 ]]; then
    gate_pass "tools"
else
    gate_fail "tools"
    echo "    tool allowlist is not exactly web_search_exa + web_fetch_exa"
fi

echo ""

###############################################################################
# Live gates (only in --live mode)
###############################################################################

if [[ "$MODE" == "live" ]]; then
    echo "[verify-exa] live gates"

    # --- Gate 6: mcp-health ---
    echo "mcp-health:"
    if command -v claude >/dev/null 2>&1; then
        mcp_out=$(CLAUDE_CONFIG_DIR="$CLAUDE_MAAS_DIR" claude mcp list 2>&1 || true)
        mcp_redacted=$(redact "$mcp_out")
        if echo "$mcp_redacted" | grep -qi "exa-search.*connected\|connected.*exa-search"; then
            gate_pass "mcp-health"
        else
            gate_fail "mcp-health"
            echo "    exa-search not Connected"
        fi
    else
        gate_fail "mcp-health"
        echo "    claude binary not found"
    fi

    # --- Gates 7-10: search/fetch/model/context via claude-maas canary ---
    echo "search:"
    echo "fetch:"
    echo "model:"
    echo "context:"
    if command -v claude-maas >/dev/null 2>&1; then
        canary_out=$(claude-maas --print --output-format json \
            'Use web_search_exa to search for "Anthropic Claude" and list one source URL. Then use web_fetch_exa on that URL.' \
            2>&1 || true)
        canary_redacted=$(redact "$canary_out")

        # Gate 7: search — at least one HTTPS source URL.
        if echo "$canary_redacted" | grep -qiE 'https://[^[:space:]]+'; then
            gate_pass "search"
        else
            gate_fail "search"
            echo "    no HTTPS source URL in canary output"
        fi

        # Gate 8: fetch — some identifiable content returned.
        if echo "$canary_redacted" | grep -qi '.'; then
            gate_pass "fetch"
        else
            gate_fail "fetch"
            echo "    no fetch content in canary output"
        fi

        # Gate 9: model — glm-5.2 only.
        if echo "$canary_redacted" | grep -qi "$EXPECTED_MODEL"; then
            gate_pass "model"
        else
            gate_fail "model"
            echo "    model is not $EXPECTED_MODEL"
        fi

        # Gate 10: context — 1000000.
        if echo "$canary_redacted" | grep -qi "$EXPECTED_CONTEXT"; then
            gate_pass "context"
        else
            gate_fail "context"
            echo "    contextWindow is not $EXPECTED_CONTEXT"
        fi
    else
        gate_fail "search"
        gate_fail "fetch"
        gate_fail "model"
        gate_fail "context"
        echo "    claude-maas binary not found"
    fi
    echo ""
fi

###############################################################################
# Summary
###############################################################################

if [[ $OVERALL_OK -eq 1 ]]; then
    echo "[verify-exa] PASS"
    exit 0
else
    echo "[verify-exa] FAIL"
    exit 1
fi
