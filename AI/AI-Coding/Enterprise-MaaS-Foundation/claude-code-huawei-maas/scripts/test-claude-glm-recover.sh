#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_SCRIPT="$SCRIPT_DIR/claude-glm-recover.sh"

TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

SESSION_ID="recover-test-session"
SESSION_DIR="$TMP_HOME/.claude-glm-config/projects/project"
SESSION_FILE="$SESSION_DIR/${SESSION_ID}.jsonl"
OUT_MD="/tmp/claude-glm-recovery-${SESSION_ID}.md"

mkdir -p "$SESSION_DIR"
rm -f "$OUT_MD"

LONG_PROMPT="$(python3 - <<'PY'
print("user-request " * 200)
PY
)"

cat > "$SESSION_FILE" <<EOF
{"type":"last-prompt","lastPrompt":"$LONG_PROMPT"}
{"type":"assistant","isApiErrorMessage":true,"message":{"content":[{"type":"text","text":"prompt length 197218 must less than the maximum input length 196608"}]}}
{"type":"user","message":{"role":"user","content":[{"type":"text","text":"short fallback request"}]}}
EOF

HOME="$TMP_HOME" bash "$TARGET_SCRIPT" "$SESSION_ID" >/dev/null

python3 - "$OUT_MD" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r"## Last User Request\n(.*?)\n\n## Recent Context", text, re.S)
if not match:
    raise SystemExit("missing last user request section")
payload = match.group(1).strip()
if len(payload) > 950:
    raise SystemExit(f"last user request not compacted: {len(payload)} chars")
if "[truncated]" not in payload:
    raise SystemExit("expected truncated marker in compacted last user request")
PY

MODE="$(stat -f %Lp "$OUT_MD")"
if [[ "$MODE" != "600" ]]; then
  echo "expected $OUT_MD mode 600, got $MODE" >&2
  exit 1
fi

rm -f "$OUT_MD"
