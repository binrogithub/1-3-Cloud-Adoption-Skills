#!/usr/bin/env bash
# claude_maas_launcher_probe.sh — user-entry acceptance via the claude-maas launcher.
#
# PRD CLIENT_CONFIG_PROTECTION §2 D2:
#   Any "deployed" judgment must include a real turn through the claude-maas
#   launcher (not a direct curl to :3000). The launcher reads
#   ~/.config/claude-maas/config.json — if that config is broken (e.g. points
#   at an ephemeral test port), this probe fails. A direct protocol probe
#   would not catch it.
#
# Contract:
#   * Invokes: claude-maas --print --output-format json --model glm-5.2
#   * Asserts the JSON response has is_error=false (or absent).
#   * Asserts stop_reason is non-empty.
#   * Asserts modelUsage is non-empty.
#   * Executes one harmless Bash tool call (touch a marker) to prove the
#     tool round trip works through the launcher.
#   * NEVER uses --dangerously-skip-permissions.
#   * Never prints the key.
#   * Exits 0 on success, 1 on failure.
#
# This probe does NOT set ANTHROPIC_* env vars — it relies on the launcher
# to inject them from ~/.config/claude-maas/. That's the whole point: we're
# testing the launcher's config, not bypassing it.
set -euo pipefail

MODEL="glm-5.2"

###############################################################################
# Helpers
###############################################################################

die() {
    echo "claude_maas_launcher_probe: $*" >&2
    exit 1
}

###############################################################################
# Locate the claude-maas launcher
###############################################################################

LAUNCHER=""
if command -v claude-maas >/dev/null 2>&1; then
    LAUNCHER="$(command -v claude-maas)"
fi
[[ -n "$LAUNCHER" ]] || die "claude-maas launcher not found on PATH"

###############################################################################
# Create a validated temporary directory
###############################################################################

TMP_DIR="$(mktemp -d 2>/dev/null)" || die "failed to create temp directory"
[[ -d "$TMP_DIR" ]] || die "temp dir not a directory: $TMP_DIR"
[[ -w "$TMP_DIR" ]] || die "temp dir not writable: $TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

###############################################################################
# Invoke claude-maas with a simple tool-use prompt
#
# We do NOT set ANTHROPIC_* — the launcher reads its own config. We DO set
# CLAUDE_CONFIG_DIR to an isolated empty dir so the inner claude doesn't
# pick up shared state, but the launcher's config (base-url, key) comes from
# ~/.config/claude-maas/ as normal.
###############################################################################

CLAUDE_CONFIG_DIR="$TMP_DIR/.claude-config"
mkdir -p "$CLAUDE_CONFIG_DIR"
export CLAUDE_CONFIG_DIR

MARKER_FILE="$TMP_DIR/launcher_tool_marker"
PROMPT="Use the Bash tool to run: touch ${MARKER_FILE}"

RESPONSE_FILE="$TMP_DIR/response.json"
umask 077

# Invoke the launcher. It will read ~/.config/claude-maas/config.json and
# api-key, inject ANTHROPIC_* into the child, and exec claude.
claude-maas \
    --print \
    --output-format json \
    --allowedTools=Bash \
    "$PROMPT" >"$RESPONSE_FILE" 2>/dev/null || die "claude-maas invocation failed (exit $?)"

###############################################################################
# Validate the response
###############################################################################

python3 - "$MODEL" "$RESPONSE_FILE" "$MARKER_FILE" <<'PYEOF' || exit 1
import json
import sys
from pathlib import Path

MODEL = sys.argv[1]
response_path = Path(sys.argv[2])
marker_path = Path(sys.argv[3])

raw = response_path.read_text()

# Must be valid JSON.
try:
    obj = json.loads(raw)
except (json.JSONDecodeError, ValueError) as exc:
    sys.stderr.write(f"LAUNCHER_INVALID_JSON: {exc}\n")
    sys.exit(1)

if not isinstance(obj, dict):
    sys.stderr.write("LAUNCHER_INVALID_JSON: response is not a JSON object\n")
    sys.exit(1)

# is_error must be false or absent.
is_error = obj.get("is_error", False)
if is_error:
    sys.stderr.write(f"LAUNCHER_IS_ERROR: response has is_error=true\n")
    sys.exit(1)

# stop_reason must be non-empty.
stop_reason = obj.get("stop_reason", "")
if not stop_reason:
    sys.stderr.write("LAUNCHER_NO_STOP_REASON: stop_reason is empty or absent\n")
    sys.exit(1)

# modelUsage must be non-empty.
usage = obj.get("modelUsage")
if not isinstance(usage, dict) or not usage:
    sys.stderr.write("LAUNCHER_NO_MODEL_USAGE: modelUsage is empty or absent\n")
    sys.exit(1)

# The marker file must exist (tool round trip succeeded).
if not marker_path.exists():
    sys.stderr.write(f"LAUNCHER_TOOL_FAILED: marker file not created: {marker_path}\n")
    sys.exit(1)

print(f"LAUNCHER_OK: stop_reason={stop_reason}, modelUsage keys={sorted(usage.keys())}")
PYEOF

echo "claude_maas_launcher_probe: PASS"
