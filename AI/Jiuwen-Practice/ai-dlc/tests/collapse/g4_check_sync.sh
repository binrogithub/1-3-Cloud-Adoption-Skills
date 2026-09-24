#!/usr/bin/env bash
# G4 — install.sh --check-sync: compare the repo's own VERSION against
# each installed target's VERSION and name drift, without modifying any
# target or changing --doctor's exit code (INV-25). Self-contained: runs
# install.sh from a throwaway sandbox so the real targets/ are untouched.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/targets"
cp "$REPO/install.sh" "$WORK/install.sh"
printf '0.22.0\n' > "$WORK/VERSION"

# Fixture install dests. codex-native-skill → dest = <config_dir>/ai-dlc.
make_dest() {  # <dest> <version|empty>
  mkdir -p "$1"
  if [[ -n "$2" ]]; then printf '%s\n' "$2" > "$1/VERSION"; fi
}
make_dest "$WORK/match/ai-dlc"    "0.22.0"   # matches repo
make_dest "$WORK/mismatch/ai-dlc" "0.99.0"   # differs
make_dest "$WORK/missing/ai-dlc"  ""         # dest exists, no VERSION
# absent: $WORK/absent is never created → skip without error

cat > "$WORK/targets/match.json"    <<JSON
{"name":"match","kind":"codex-native-skill","config_dir":"$WORK/match"}
JSON
cat > "$WORK/targets/mismatch.json" <<JSON
{"name":"mismatch","kind":"codex-native-skill","config_dir":"$WORK/mismatch"}
JSON
cat > "$WORK/targets/missing.json"  <<JSON
{"name":"missing","kind":"codex-native-skill","config_dir":"$WORK/missing"}
JSON
cat > "$WORK/targets/absent.json"   <<JSON
{"name":"absent","kind":"codex-native-skill","config_dir":"$WORK/absent"}
JSON

# 1. --check-sync standalone: exactly two drift lines (mismatch + missing),
#    none for match or absent.
OUT=$(bash "$WORK/install.sh" --check-sync 2>&1 || true)
DRIFT=$(grep -c 'version drift' <<<"$OUT" || true)
[[ "$DRIFT" -eq 2 ]] \
  || { echo "FAIL: expected 2 drift lines, got $DRIFT:"; echo "$OUT"; exit 1; }
grep -q 'mismatch.*repo=.0.22.0.*target=.0.99.0' <<<"$OUT" \
  || { echo "FAIL: mismatch line missing or wrong versions:"; echo "$OUT"; exit 1; }
grep -q 'missing.*repo=.0.22.0.*target=.' <<<"$OUT" \
  || { echo "FAIL: missing-VERSION line not reported as drift:"; echo "$OUT"; exit 1; }
if grep -q 'match.*version drift' <<<"$OUT"; then
  echo "FAIL: matching target reported as drift"; exit 1
fi
if grep -q 'absent' <<<"$OUT"; then
  echo "FAIL: absent target was not skipped"; exit 1
fi

# 2. --doctor's exit code is unchanged by --check-sync (advisory, not a gate).
set +e
bash "$WORK/install.sh" --doctor >/dev/null 2>&1; D1=$?
bash "$WORK/install.sh" --doctor --check-sync >/dev/null 2>&1; D2=$?
set -e
[[ "$D1" == "$D2" ]] \
  || { echo "FAIL: --check-sync changed --doctor exit code ($D1 → $D2)"; exit 1; }

# 3. --check-sync never modifies a target's files (read-only).
BEFORE=$(cat "$WORK/mismatch/ai-dlc/VERSION")
bash "$WORK/install.sh" --check-sync >/dev/null 2>&1 || true
AFTER=$(cat "$WORK/mismatch/ai-dlc/VERSION")
[[ "$BEFORE" == "$AFTER" ]] \
  || { echo "FAIL: --check-sync modified a target VERSION"; exit 1; }

echo "G4 CHECK-SYNC: pass (drift named for mismatch+missing, match silent, absent skipped, doctor exit code unchanged, read-only)"
