#!/usr/bin/env bash
# Test the MaaS key enforcement (Part A) and review-axes configuration
# (Part B) from docs/prd-install-maas-key-enforce-and-review-axes.md.
#
# A1: empty HOME + non-interactive → exit non-zero, stderr contains
#     "MaaS API_KEY not configured".
# A2: pre-configured .env + non-interactive → exit 0, and the
#     "already configured" path is taken (setup-maas-key.sh not called).
# B1: setup-review-axes.sh with piped selections → axes updated, other
#     top-level keys byte-for-byte unchanged.
# B2: non-factory fixture without --force → no write (file unchanged).
#
# Run:  tests/test_install_maas_key_and_review_axes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

PY="$(command -v python3.12 || command -v python3 || echo ${HOME}/.local/bin/python3.12)"

# ── A1: empty HOME, non-interactive → hard fail ─────────────────────
echo "── A1: no key + non-interactive should hard-fail ──"

A1_HOME="$T/a1-home"
mkdir -p "$A1_HOME"
A1_TARGET="$T/a1-target"
mkdir -p "$A1_TARGET"
A1_ENV="$T/a1-env/.env"   # does not exist yet

# stub setup-maas-key.sh so we don't touch the real gateway config —
# it writes a marker so we can detect if it was called
A1_SCRIPT_DIR="$T/a1-scriptdir"
mkdir -p "$A1_SCRIPT_DIR/scripts"
cat > "$A1_SCRIPT_DIR/scripts/setup-maas-key.sh" <<'STUB'
#!/usr/bin/env bash
echo "STUB-CALLED" >> "$1_MARKER_FILE"
exit 0
STUB
chmod +x "$A1_SCRIPT_DIR/scripts/setup-maas-key.sh"

# We can't easily redirect SCRIPT_DIR, so instead just run install.sh
# from the real repo but with AI_DLC_ENV_FILE pointing nowhere and
# stdin from /dev/null. The real setup-maas-key.sh won't be called
# because ensure_maas_key returns 1 before calling it in non-interactive
# mode.

HOME="$A1_HOME" \
AI_DLC_ENV_FILE="$A1_ENV" \
CLAUDE_CONFIG_DIR="" \
bash "$ROOT/install.sh" --target-dir "$A1_TARGET" </dev/null >"$T/a1.out" 2>&1 \
  && A1_RC=0 || A1_RC=$?

if [[ "$A1_RC" == "0" ]]; then
  echo "FAIL A1: install.sh exited 0 with no MaaS key and non-interactive stdin"
  cat "$T/a1.out"
  exit 1
fi
grep -q "MaaS API_KEY not configured" "$T/a1.out" \
  || { echo "FAIL A1: stderr does not contain 'MaaS API_KEY not configured'"; cat "$T/a1.out"; exit 1; }
echo "PASS A1: exit code $A1_RC, message present"

# ── A2: pre-configured key + non-interactive → exit 0 ───────────────
echo ""
echo "── A2: pre-configured key + non-interactive should succeed ──"

A2_HOME="$T/a2-home"
mkdir -p "$A2_HOME"
A2_TARGET="$T/a2-target"
mkdir -p "$A2_TARGET"
A2_ENV_DIR="$T/a2-env"
mkdir -p "$A2_ENV_DIR"
A2_ENV="$A2_ENV_DIR/.env"
printf 'API_KEY=fake-test-key-for-a2\nAPI_BASE=https://example.test/v1\nMODEL_NAME=glm-5.2\n' > "$A2_ENV"

HOME="$A2_HOME" \
AI_DLC_ENV_FILE="$A2_ENV" \
CLAUDE_CONFIG_DIR="" \
bash "$ROOT/install.sh" --target-dir "$A2_TARGET" </dev/null >"$T/a2.out" 2>&1 \
  && A2_RC=0 || A2_RC=$?

if [[ "$A2_RC" != "0" ]]; then
  echo "FAIL A2: install.sh exited $A2_RC with a pre-configured key"
  cat "$T/a2.out"
  exit 1
fi
grep -q "already configured" "$T/a2.out" \
  || { echo "FAIL A2: output does not contain 'already configured'"; cat "$T/a2.out"; exit 1; }
# setup-maas-key.sh should NOT have been called — its output marker is absent
grep -q "setup-maas-key:" "$T/a2.out" \
  && { echo "FAIL A2: setup-maas-key.sh was called despite key being present"; cat "$T/a2.out"; exit 1; }
echo "PASS A2: exit 0, 'already configured' message present, setup-maas-key.sh not called"

# ── B1: setup-review-axes.sh with piped selections ──────────────────
echo ""
echo "── B1: piped selections update axes, preserve other keys ──"

B1_CFG="$T/b1-config.yaml"
cat > "$B1_CFG" <<'YAMLEOF'
# ── AI-DLC collapsed configuration (v0.6.0) ──────────────────
execution:
  route_default: inline
  planning_threshold_files: 4

delivery:
  product_excludes: [.ai-dlc/**, CLAUDE.md, findings.json]

gates:
  merge_required: true

review:
  max_axes: 3
  axis.security.stance: suspicious of anything that widens who can act or what a process can reach without a named owner
  axis.security.accepts: paying convenience for containment, a slower path with a narrower blast radius
  axis.security.refuses: unattended agents holding unrestricted shells side by side in one tree
  axis.operability.stance: suspicious of anything that holds only while a single process stays alive
  axis.operability.accepts: a rougher tool whose state survives restarts, concurrent runs and partial failure
  axis.operability.refuses: shared state two separate invocations can corrupt and no operator can see
  axis.performance.stance: suspicious of any cost that grows without a named ceiling
  axis.performance.accepts: paying memory or duplication to keep the critical path short
  axis.performance.refuses: unbounded concurrency and unmeasured claims of speed

design:
  select_timeout_s: 120
  specify_timeout_s: 600
YAMLEOF

# Snapshot the non-review content for byte-for-byte comparison
# (strip the review.axis.* lines from both original and result)
extract_non_axis() {
  "$PY" - "$1" <<'PYEOF'
import sys
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
in_review = False
for ln in lines:
    stripped = ln.strip()
    if not stripped or stripped.startswith("#"):
        print(ln); continue
    if not ln[0].isspace():
        section = stripped.split(":", 1)[0].strip()
        in_review = (section == "review")
        print(ln); continue
    if in_review and stripped.startswith("axis."):
        continue
    print(ln)
PYEOF
}
BEFORE_NON_AXIS="$(extract_non_axis "$B1_CFG")"
BEFORE_HASH="$("$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$B1_CFG")"

# Feed: 2 axes, preset 1 (security, as-is), preset 4 (correctness, as-is)
# Input sequence: "2" (num axes), "1" (preset security), "y" (use as-is),
#                 "4" (preset correctness), "y" (use as-is)
bash "$ROOT/scripts/setup-review-axes.sh" --config-file "$B1_CFG" --force \
  <<< $'2\n1\ny\n4\ny' >"$T/b1.out" 2>&1 \
  || { echo "FAIL B1: setup-review-axes.sh exited non-zero"; cat "$T/b1.out"; exit 1; }

# Verify axes were updated
grep -q 'axis.security.stance:' "$B1_CFG" \
  || { echo "FAIL B1: security axis missing"; cat "$B1_CFG"; exit 1; }
grep -q 'axis.correctness.stance:' "$B1_CFG" \
  || { echo "FAIL B1: correctness axis missing"; cat "$B1_CFG"; exit 1; }
grep -q 'axis.operability.stance:' "$B1_CFG" \
  && { echo "FAIL B1: operability axis should have been removed"; cat "$B1_CFG"; exit 1; }
grep -q 'axis.performance.stance:' "$B1_CFG" \
  && { echo "FAIL B1: performance axis should have been removed"; cat "$B1_CFG"; exit 1; }

# Verify non-axis content is byte-for-byte unchanged
AFTER_NON_AXIS="$(extract_non_axis "$B1_CFG")"
[[ "$BEFORE_NON_AXIS" == "$AFTER_NON_AXIS" ]] \
  || { echo "FAIL B1: non-axis content changed"; diff <(echo "$BEFORE_NON_AXIS") <(echo "$AFTER_NON_AXIS"); exit 1; }

echo "PASS B1: axes updated to security+correctness, other keys preserved"

# ── B2: non-factory fixture without --force → no write ──────────────
echo ""
echo "── B2: non-factory config without --force → no write ──"

B2_CFG="$T/b2-config.yaml"
cat > "$B2_CFG" <<'YAMLEOF'
# test config with custom axes
execution:
  route_default: inline

review:
  max_axes: 3
  axis.security.stance: a completely custom stance that is not the factory default
  axis.security.accepts: custom accepts text
  axis.security.refuses: custom refuses text
  axis.maintainability.stance: another custom stance
  axis.maintainability.accepts: another custom accepts
  axis.maintainability.refuses: another custom refuses

gates:
  merge_required: true
YAMLEOF

B2_BEFORE_HASH="$("$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$B2_CFG")"

bash "$ROOT/scripts/setup-review-axes.sh" --config-file "$B2_CFG" \
  <<< $'1\n1\ny' >"$T/b2.out" 2>&1 \
  || { echo "FAIL B2: setup-review-axes.sh exited non-zero on non-factory config"; cat "$T/b2.out"; exit 1; }

B2_AFTER_HASH="$("$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$B2_CFG")"

[[ "$B2_BEFORE_HASH" == "$B2_AFTER_HASH" ]] \
  || { echo "FAIL B2: file was modified without --force"; exit 1; }
grep -q "already has custom review axes" "$T/b2.out" \
  || { echo "FAIL B2: missing 'already has custom' skip message"; cat "$T/b2.out"; exit 1; }

echo "PASS B2: non-factory config unchanged, skip message present"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "ALL TESTS PASSED: A1 (hard-fail) A2 (skip-if-configured) B1 (write) B2 (skip-if-custom)"
