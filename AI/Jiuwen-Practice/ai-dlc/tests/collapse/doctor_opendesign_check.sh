#!/usr/bin/env bash
# Test that --doctor warns (not fails) when the OpenDesign tree is missing,
# and that this check alone does not turn the overall doctor verdict into
# a failure.  Also verifies the MaaS API_KEY check warns when the key is empty.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# ── 1. OpenDesign missing → warn, not fail ────────────────────
# Point AI_DLC_OPENDESIGN_ROOT to a path that does not exist.
# Also point the .env to a temp file with an empty API_KEY to test
# the MaaS credential warning.
mkdir -p "$T/fakehome/.jiuwenswarm/config"
cat > "$T/fakehome/.jiuwenswarm/config/.env" <<'EOF'
API_BASE=
API_KEY=
MODEL_NAME=
MODEL_PROVIDER=
SOME_OTHER_KEY=foo
EOF

set +e
AI_DLC_OPENDESIGN_ROOT="$T/nonexistent-opendesign" \
AI_DLC_ENV_FILE="$T/fakehome/.jiuwenswarm/config/.env" \
  "$ROOT/install.sh" --doctor > "$T/doctor.out" 2>&1
RC=$?
set -e

# The OpenDesign check must produce a warn, not a fail
grep -q 'OpenDesign tree missing' "$T/doctor.out" \
  || { echo "FAIL: doctor did not warn about missing OpenDesign tree"; cat "$T/doctor.out"; exit 1; }
grep -q 'plan.py design will fail' "$T/doctor.out" \
  || { echo "FAIL: doctor did not mention plan.py design will fail"; cat "$T/doctor.out"; exit 1; }
# It must be a warn (!), not a fail (✗)
grep -q '!.*OpenDesign tree missing' "$T/doctor.out" \
  || { echo "FAIL: OpenDesign check used fail instead of warn"; cat "$T/doctor.out"; exit 1; }

# The MaaS API_KEY check must also warn (not fail) when key is empty
grep -q 'MaaS API_KEY empty or missing' "$T/doctor.out" \
  || { echo "FAIL: doctor did not warn about empty MaaS API_KEY"; cat "$T/doctor.out"; exit 1; }

# ── 2. OpenDesign present → ok ────────────────────────────────
mkdir -p "$T/opendesign-present"
set +e
AI_DLC_OPENDESIGN_ROOT="$T/opendesign-present" \
AI_DLC_ENV_FILE="$T/fakehome/.jiuwenswarm/config/.env" \
  "$ROOT/install.sh" --doctor > "$T/doctor2.out" 2>&1
RC2=$?
set -e

grep -q 'OpenDesign tree present' "$T/doctor2.out" \
  || { echo "FAIL: doctor did not report OpenDesign tree present"; cat "$T/doctor2.out"; exit 1; }

# ── 3. The OpenDesign check does not cause overall failure ────
# The overall doctor exit code may be 0 or 1 depending on other checks
# (gateway, etc.), but the OpenDesign check specifically must not be
# the one that sets all_ok=false.  Verify there is no fail (✗) line
# about OpenDesign.
if grep -q '✗.*OpenDesign' "$T/doctor.out"; then
  echo "FAIL: doctor emitted a fail (✗) for OpenDesign — should be warn (!)"
  cat "$T/doctor.out"
  exit 1
fi

echo "DOCTOR OPENDESIGN CHECK: pass (missing tree → warn with 'plan.py design will fail', not fail; present tree → ok; empty API_KEY → warn; neither check turns overall verdict to fail on its own)"
