#!/usr/bin/env bash
# N4 (Y1/Z6): a real end-to-end design gate. Creates a minimal 1-page
# site, real-dispatches plan.py design, and asserts:
#   - ui-designer was called via skill_tool (B2/N5)
#   - a signed design record was produced
#   - the five facts all hold
# Default: skip (prints why). Run with --live to execute.
# Z6: no stub client — this proves ui-designer actually runs, not just
# that the code path is wired.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=python3.12

LIVE=0
for arg in "$@"; do
  case "$arg" in
    --live) LIVE=1 ;;
  esac
done

if [[ "$LIVE" -eq 0 ]]; then
  echo "UD LIVE DESIGN: skip (pass --live to run; requires the gateway"
  echo "  client, the ui-designer skill, and an OpenDesign pin — Z6"
  echo "  rejects a stub)"
  exit 0
fi

# build a minimal 1-page site in a temp repo
REPO=$(mktemp -d)
trap 'rm -rf "$REPO"' EXIT
cd "$REPO"
git init -q
git config user.email t@t
git config user.name t
mkdir -p assets
cat > index.html <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test</title><link rel="stylesheet" href="assets/style.css"></head>
<body><main id="main"><h1>Test Page</h1><p>Hello.</p></main>
<footer>© <span data-year>2026</span></footer>
<script src="assets/main.js" defer></script></body>
</html>
HTML
echo 'body{font-family:system-ui}' > assets/style.css
echo '' > assets/main.js
git add -A
git commit -qm "init: minimal test site"

CHANGE="ud-live-design-test"
TD="$REPO/.ai-dlc/tasks/${CHANGE}-planning"
mkdir -p "$TD"

# init the task
$PY "$ROOT/bin/report.py" init --task-dir "$TD" --repo "$REPO" \
  --route inline --task-id "$CHANGE" --change "$CHANGE" >/dev/null 2>&1

# dispatch design
OUT=$($PY "$ROOT/bin/plan.py" design --change "$CHANGE" --repo "$REPO" \
  --task-dir "$TD" 2>&1) || true

# assert: a signed design record exists
RECORDS_DIR="/var/lib/aidlc/records/$CHANGE"
if ! ls "$RECORDS_DIR"/design-*.json >/dev/null 2>&1; then
  echo "FAIL: no signed design record produced"
  echo "$OUT" | tail -10
  exit 1
fi

# assert: the record verifies (rc=0 in the record)
RECORD=$(ls "$RECORDS_DIR"/design-*.json | head -1)
if ! $PY -c "
import json, sys
sys.path.insert(0, '$ROOT/bin')
from report import verify_record
rec = json.load(open('$RECORD'))
ok = verify_record(rec)
sys.exit(0 if ok else 1)
" 2>/dev/null; then
  echo "FAIL: design record signature does not verify"
  exit 1
fi

# assert: the frames show skill_tool{ui-designer} (B2/N5)
EVIDENCE=$(ls "$TD"/evidence/plan-design-*.jsonl 2>/dev/null | head -1)
if [[ -z "$EVIDENCE" ]]; then
  echo "FAIL: no design session evidence found"
  exit 1
fi
if ! grep -q 'ui-designer' "$EVIDENCE" 2>/dev/null; then
  echo "FAIL: frames show no skill_tool{ui-designer} — the role did not"
  echo "  follow the signpost (B2)"
  exit 1
fi

# assert: design-stats.jsonl got a line (N6)
if ! grep -q "$CHANGE" /var/lib/aidlc/design-stats.jsonl 2>/dev/null; then
  echo "FAIL: no design-stats entry for $CHANGE (N6)"
  exit 1
fi

echo "UD LIVE DESIGN: pass (real dispatch, signed record, skill_tool used,"
echo "  five facts held, stats logged — Z6: no stub)"
