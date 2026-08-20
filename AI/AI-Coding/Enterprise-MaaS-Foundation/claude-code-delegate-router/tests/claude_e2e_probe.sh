#!/usr/bin/env bash
# claude_e2e_probe.sh — end-to-end probe of the token-only Claude CLI + tool round trip.
#
# This script verifies that the official Claude Code CLI, when invoked with ONLY
# ANTHROPIC_AUTH_TOKEN (never ANTHROPIC_API_KEY), can reach the MaaS endpoint
# as model glm-5.2 and execute a single harmless Bash tool call.
#
# Contract:
#   * Creates a validated mktemp -d temporary directory.
#   * Sets an empty CLAUDE_CONFIG_DIR (isolated config, no shared state).
#   * Uses ONLY ANTHROPIC_AUTH_TOKEN for auth — NEVER ANTHROPIC_API_KEY.
#   * Invokes: claude --model glm-5.2 --print --output-format json
#   * Checks that the JSON response's modelUsage contains glm-5.2.
#   * Executes one harmless Bash marker (touch a marker file) in the temp dir
#     to test tool round trip, pre-authorized via --allowedTools=Bash.
#   * Trap cleanup removes the temp dir on exit.
#   * NEVER uses --dangerously-skip-permissions.
#   * Never prints the key.
#   * Exits 0 on success, 1 on failure.
#
# Environment expected (set by the caller / verify.sh / launcher):
#   ANTHROPIC_AUTH_TOKEN  — the MaaS Bearer token (required)
#   ANTHROPIC_BASE_URL    — the MaaS Anthropic endpoint (required)
#   PATH                  — must contain the real claude binary
set -euo pipefail

MODEL="glm-5.2"

###############################################################################
# Helpers
###############################################################################

die() {
    echo "claude_e2e_probe: $*" >&2
    exit 1
}

###############################################################################
# Validate required environment
###############################################################################

[[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]] || die "ANTHROPIC_AUTH_TOKEN not set"
[[ -n "${ANTHROPIC_BASE_URL:-}" ]] || die "ANTHROPIC_BASE_URL not set"

# CRITICAL: never allow ANTHROPIC_API_KEY to be the auth source.
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    die "ANTHROPIC_API_KEY is set; this probe must use ANTHROPIC_AUTH_TOKEN only"
fi

###############################################################################
# Locate the real claude binary
###############################################################################

claude_bin=""
if command -v claude >/dev/null 2>&1; then
    claude_bin="$(command -v claude)"
fi
[[ -n "$claude_bin" ]] || die "claude binary not found on PATH"

###############################################################################
# Create a validated temporary directory
###############################################################################

TMP_DIR="$(mktemp -d 2>/dev/null)" || die "failed to create temp directory"
# Validate it is a real directory we own.
[[ -d "$TMP_DIR" ]] || die "temp dir not a directory: $TMP_DIR"
[[ -w "$TMP_DIR" ]] || die "temp dir not writable: $TMP_DIR"

# Cleanup trap — always remove the temp dir.
trap 'rm -rf "$TMP_DIR"' EXIT

###############################################################################
# Set up an isolated, empty CLAUDE_CONFIG_DIR
###############################################################################

CLAUDE_CONFIG_DIR="$TMP_DIR/.claude-config"
mkdir -p "$CLAUDE_CONFIG_DIR"
export CLAUDE_CONFIG_DIR

# Ensure ANTHROPIC_API_KEY is NOT exported to the child.
unset ANTHROPIC_API_KEY 2>/dev/null || true

###############################################################################
# Step 1: Invoke claude with a simple prompt and check modelUsage
###############################################################################

MARKER_FILE="$TMP_DIR/tool_round_trip_marker"

# Build a prompt that asks claude to run one harmless Bash command.
# We pre-authorize the exact test tool with --allowedTools=Bash.
# NEVER use --dangerously-skip-permissions.
PROMPT="Use the Bash tool to run: touch ${MARKER_FILE}"

# Capture the JSON output into a protected file inside TMP_DIR.
# CRITICAL (PRD FR-1): the response must travel through a single file data
# channel — never `pipe | python3 - <<HEREDOC`, where the heredoc steals stdin.
RESPONSE_FILE="$TMP_DIR/response.json"
umask 077
claude \
    --model "$MODEL" \
    --print \
    --output-format json \
    --allowedTools=Bash \
    "$PROMPT" >"$RESPONSE_FILE" 2>/dev/null || die "claude invocation failed (exit $?)"

# Validate the response: JSON object with a non-empty modelUsage whose
# extracted model set is exactly {MODEL}.  The response path is passed as
# argv; the validator never reads stdin.  (PRD FR-1, FR-2)
python3 - "$MODEL" "$RESPONSE_FILE" <<'PYEOF' || exit 1
import json
import sys
from pathlib import Path

MODEL = sys.argv[1]
response_path = Path(sys.argv[2])

raw = response_path.read_text()

# FR-2.1: must be a JSON object.
try:
    obj = json.loads(raw)
except (json.JSONDecodeError, ValueError) as exc:
    sys.stderr.write(f"E2E_INVALID_JSON: response is not valid JSON: {exc}\n")
    sys.exit(1)

if not isinstance(obj, dict):
    sys.stderr.write("E2E_INVALID_JSON: response is not a JSON object\n")
    sys.exit(1)

# FR-2.2: non-empty modelUsage must exist.
usage = obj.get("modelUsage")
if not isinstance(usage, dict) or not usage:
    sys.stderr.write("E2E_MODEL_USAGE_MISSING: response has no modelUsage\n")
    sys.exit(1)

# Extract the model set from modelUsage.  modelUsage is a dict whose keys are
# model ids (e.g. {"glm-5.2": {"inputTokens": 1, ...}}).  Some formats nest a
# "model" key inside each entry; we collect both the keys and any nested
# "model" string values to be robust, then require the set to be exactly {MODEL}.
def _extract_models(usage_obj):
    models = set()
    for key, val in usage_obj.items():
        if isinstance(key, str) and key:
            models.add(key)
        if isinstance(val, dict):
            inner = val.get("model")
            if isinstance(inner, str) and inner:
                models.add(inner)
    return models

models = _extract_models(usage)
if not models:
    sys.stderr.write("E2E_MODEL_USAGE_MISSING: modelUsage contains no model ids\n")
    sys.exit(1)

# FR-2.3: the extracted model set must be exactly {MODEL}.
if models != {MODEL}:
    extra = sorted(models - {MODEL})
    sys.stderr.write(
        f"E2E_MODEL_MISMATCH: expected {{{MODEL}}}, got {sorted(models)}"
        + (f" (unexpected: {extra})" if extra else "")
        + "\n"
    )
    sys.exit(1)

sys.exit(0)
PYEOF

echo "claude_e2e_probe: model=$MODEL ok"

###############################################################################
# Step 2: Verify the tool round trip — marker file must exist
###############################################################################

if [[ ! -f "$MARKER_FILE" ]]; then
    echo "claude_e2e_probe: E2E_TOOL_MARKER_MISSING: tool round trip failed: marker file not created" >&2
    exit 1
fi

echo "claude_e2e_probe: tool round trip ok"

###############################################################################
# Success
###############################################################################

exit 0
