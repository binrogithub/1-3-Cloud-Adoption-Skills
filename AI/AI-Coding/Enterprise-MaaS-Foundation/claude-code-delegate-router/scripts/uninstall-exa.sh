#!/usr/bin/env bash
# uninstall-exa.sh — uninstall the isolated Exa MCP configuration.
#
# Default mode removes only the project-owned Exa state from the isolated
# claude-maas profile:
#   ~/.claude-maas/.claude.json  -> mcpServers.exa-search
#   ~/.claude-maas/settings.json -> two exa-search tool permissions
#
# Default mode RETAINS the Exa key at ~/.config/claude-maas/exa-api-key.
# --purge (must be explicit) also deletes the key file.
#
# Invariants (PRD §12.3, G-EXA6):
#   * Never modifies plain Claude, MaaS config, or unrelated MCP/state.
#   * Idempotent: running twice is a no-op (exit 0).
#   * Without --purge, never deletes the key file.
#   * The key never appears in stdout or stderr.
set -euo pipefail

###############################################################################
# Constants
###############################################################################

EXA_SERVER="exa-search"
PERM_SEARCH="mcp__exa-search__web_search_exa"
PERM_FETCH="mcp__exa-search__web_fetch_exa"

###############################################################################
# Helpers
###############################################################################

die() {
    echo "uninstall-exa: $*" >&2
    exit 1
}

###############################################################################
# Parse flags
###############################################################################

PURGE="no"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge) PURGE="yes"; shift ;;
        --help|-h)
            cat <<'USAGE'
uninstall-exa.sh — uninstall the isolated Exa MCP config

Usage:
  ./scripts/uninstall-exa.sh            # remove MCP + permissions, retain key
  ./scripts/uninstall-exa.sh --purge    # also delete the Exa key file
USAGE
            exit 0
            ;;
        *) die "unknown option: $1 (use --purge)" ;;
    esac
done

###############################################################################
# Paths
###############################################################################

CLAUDE_MAAS_DIR="$HOME/.claude-maas"
CLAUDE_JSON="$CLAUDE_MAAS_DIR/.claude.json"
SETTINGS_JSON="$CLAUDE_MAAS_DIR/settings.json"
KEY_FILE="$HOME/.config/claude-maas/exa-api-key"

###############################################################################
# Remove the exa-search MCP entry from ~/.claude-maas/.claude.json
###############################################################################

if [[ -f "$CLAUDE_JSON" ]]; then
    python3 - "$CLAUDE_JSON" "$EXA_SERVER" <<'PYEOF'
import json
import os
import sys

path = sys.argv[1]
server = sys.argv[2]

with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

if not isinstance(data, dict):
    sys.exit(0)

mcp = data.get("mcpServers")
if not isinstance(mcp, dict) or server not in mcp:
    sys.exit(0)

new_mcp = dict(mcp)
new_mcp.pop(server, None)
data["mcpServers"] = new_mcp

# Atomic write via same-dir temp.
d = os.path.dirname(path)
fd, tmp = __import__("tempfile").mkstemp(prefix="tmp.", dir=d)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise

print(f"uninstall-exa: removed mcpServers.{server} from {path}")
PYEOF
fi

###############################################################################
# Remove the two exa-search permissions from ~/.claude-maas/settings.json
###############################################################################

if [[ -f "$SETTINGS_JSON" ]]; then
    python3 - "$SETTINGS_JSON" "$PERM_SEARCH" "$PERM_FETCH" <<'PYEOF'
import json
import os
import sys

path = sys.argv[1]
to_remove = set(sys.argv[2:])

with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

if not isinstance(data, dict):
    sys.exit(0)

perms = data.get("permissions")
if not isinstance(perms, dict):
    sys.exit(0)

allow = perms.get("allow")
if not isinstance(allow, list):
    sys.exit(0)

new_allow = [p for p in allow if p not in to_remove]
if len(new_allow) == len(allow):
    sys.exit(0)  # nothing to remove

perms["allow"] = new_allow

d = os.path.dirname(path)
fd, tmp = __import__("tempfile").mkstemp(prefix="tmp.", dir=d)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise

print(f"uninstall-exa: removed exa-search permissions from {path}")
PYEOF
fi

###############################################################################
# Purge the key file if requested
###############################################################################

if [[ "$PURGE" == "yes" ]]; then
    if [[ -f "$KEY_FILE" ]]; then
        rm -f "$KEY_FILE"
        echo "uninstall-exa: purged key file $KEY_FILE"
    fi
    echo "uninstall-exa: --purge complete"
else
    if [[ -f "$KEY_FILE" ]]; then
        echo "uninstall-exa: retained key at $KEY_FILE (use --purge to delete)"
    fi
    echo "uninstall-exa: default complete — MCP and permissions removed, key retained"
fi

exit 0
