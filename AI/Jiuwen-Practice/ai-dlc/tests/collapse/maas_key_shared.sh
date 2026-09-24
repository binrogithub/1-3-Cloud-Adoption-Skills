#!/usr/bin/env bash
# Regression test: install.sh checks for a configured MaaS gateway key at
# the end of every install run, and the check is host-level, not
# per-agent — the same ~/.jiuwenswarm/config/.env API_KEY is what
# bin/plan.py's CLIENT resolves to regardless of which coding agent
# triggered the install (Claude, Codex, Cursor, Copilot all share one
# fixed client path). A user asked "why wasn't I prompted for a key" —
# answer: skill-install and gateway-credential setup are separate
# concerns, and a key set up for one agent is already usable by every
# other agent's install, with nothing more to configure.
#
# This exercises ensure_maas_key() directly (unit-level, matching this
# project's other collapse tests): key present → informational only, no
# prompt; key absent + non-interactive stdin → warns, does not hang or
# fail the install.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

grep -vxF 'main "$@"' "$ROOT/install.sh" > "$T/install_funcs.sh"
sed -i 's|^SCRIPT_DIR=.*|SCRIPT_DIR="'"$ROOT"'"|' "$T/install_funcs.sh"

# ── 1. key already present: informational only, no prompt invoked ──────
present_home="$T/present"
mkdir -p "$present_home/.jiuwenswarm/config"
echo "API_KEY=already-set-key" > "$present_home/.jiuwenswarm/config/.env"
out=$(
  HOME="$present_home"
  export HOME
  source "$T/install_funcs.sh"
  ensure_maas_key
) 2>&1
echo "$out" | grep -qi "already configured" \
  || { echo "FAIL: present-key case did not report 'already configured': $out"; exit 1; }
echo "$out" | grep -qi "shared by every installed agent" \
  || { echo "FAIL: present-key message doesn't explain the shared-key architecture: $out"; exit 1; }

# ── 2. key absent, non-interactive (stdin not a tty): warns, does not hang ──
missing_home="$T/missing"
mkdir -p "$missing_home"
out2=$(
  HOME="$missing_home"
  export HOME
  source "$T/install_funcs.sh"
  ensure_maas_key < /dev/null
) 2>&1
echo "$out2" | grep -qi "not configured" \
  || { echo "FAIL: missing-key non-interactive case did not warn: $out2"; exit 1; }
echo "$out2" | grep -qi -- "--setup-maas-key" \
  || { echo "FAIL: missing-key warning doesn't name the fix command: $out2"; exit 1; }
[[ ! -f "$missing_home/.jiuwenswarm/config/.env" ]] \
  || { echo "FAIL: non-interactive run should not have written a .env file"; exit 1; }

echo "MAAS KEY SHARED: pass (present key → informational, no reprompt; missing key + non-interactive → warns with fix command, does not hang or write)"
