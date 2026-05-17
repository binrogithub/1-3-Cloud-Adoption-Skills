#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  claude-glm-recover <session-id> [--cwd DIR] [--lines N] [--launch]

Purpose:
  Build a compact recovery pack from a failed Claude GLM session JSONL so the
  task can continue in a fresh session after context overflow or resume failure.

Behavior:
  - Reads ~/.claude-glm-config/projects/**/<session-id>.jsonl
  - Writes /tmp/claude-glm-recovery-<session-id>.md
  - Prints a fresh claude-glm launch command
  - With --launch, opens a fresh interactive claude-glm session in the original
    working directory after printing the recovery file path

Notes:
  - This does not repair the old session in place.
  - This does not use --resume.
  - On root/sudo environments, interactive prompt injection is unreliable, so
    the script launches a fresh session and tells you which recovery file to paste.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SESSION_ID=""
OVERRIDE_CWD=""
TAIL_LINES=12
LAUNCH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cwd)
      OVERRIDE_CWD="${2:-}"
      shift 2
      ;;
    --lines)
      TAIL_LINES="${2:-}"
      shift 2
      ;;
    --launch)
      LAUNCH=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      if [[ -z "$SESSION_ID" ]]; then
        SESSION_ID="$1"
      else
        echo "Unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

SESSION_FILE="$(find "$HOME/.claude-glm-config/projects" -type f -name "${SESSION_ID}.jsonl" | head -n 1)"
if [[ -z "${SESSION_FILE:-}" ]]; then
  echo "Session file not found for: $SESSION_ID" >&2
  exit 1
fi

OUT_MD="/tmp/claude-glm-recovery-${SESSION_ID}.md"

python3 - "$SESSION_FILE" "$OUT_MD" "$TAIL_LINES" "$OVERRIDE_CWD" <<'PY'
import json
import os
import sys
from pathlib import Path

session_file = Path(sys.argv[1])
out_md = Path(sys.argv[2])
tail_lines = int(sys.argv[3])
override_cwd = sys.argv[4].strip()

records = []
with session_file.open("r", encoding="utf-8") as f:
    for raw in f:
        raw = raw.rstrip("\n")
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except Exception:
            continue

if not records:
    raise SystemExit("No readable records found in session file")

def compact(text: str, limit: int = 900) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"

def extract_content(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t == "text":
            txt = item.get("text", "")
            if txt:
                parts.append(txt)
        elif t == "tool_use":
            name = item.get("name", "tool")
            payload = item.get("input", {})
            if isinstance(payload, dict):
                desc = payload.get("description") or payload.get("command") or payload.get("url") or ""
            else:
                desc = str(payload)
            parts.append(f"[tool_use:{name}] {compact(desc, 220)}")
        elif t == "tool_result":
            body = item.get("content", "")
            if isinstance(body, str):
                parts.append(f"[tool_result] {compact(body, 500)}")
            elif isinstance(body, list):
                nested = []
                for child in body:
                    if isinstance(child, dict) and child.get("type") == "text":
                        nested.append(child.get("text", ""))
                if nested:
                    parts.append(f"[tool_result] {compact(' '.join(nested), 500)}")
    return "\n".join(p for p in parts if p).strip()

cwd = override_cwd
last_prompt = ""
last_user_text = ""
api_error = ""
recent = []

for rec in records:
    if not cwd and rec.get("cwd"):
        cwd = rec["cwd"]
    if rec.get("type") == "last-prompt":
        last_prompt = rec.get("lastPrompt", last_prompt)
    if rec.get("type") == "assistant" and rec.get("isApiErrorMessage"):
        api_error = extract_content(rec.get("message", {}).get("content", [])) or api_error

for rec in reversed(records):
    if rec.get("type") not in {"user", "assistant"}:
        continue
    msg = rec.get("message", {})
    role = msg.get("role") or rec.get("type")
    text = extract_content(msg.get("content", []))
    if not text:
        continue
    if role == "user" and not last_user_text:
        last_user_text = text
    recent.append((role, compact(text, 1400)))
    if len(recent) >= tail_lines:
        break

recent.reverse()

if not last_prompt:
    last_prompt = last_user_text
if not cwd:
    cwd = os.getcwd()

last_prompt = compact(last_prompt, 900) if last_prompt else "(not found)"

lines = [
    "# Claude GLM Recovery Pack",
    "",
    "Use this file as the first prompt in a fresh `claude-glm` session.",
    "Do not use `--resume` for the failed session.",
    "",
    "## Session",
    f"- Session ID: `{session_file.stem}`",
    f"- Original session file: `{session_file}`",
    f"- Original cwd: `{cwd}`",
    "",
    "## Failure",
    compact(api_error, 1200) if api_error else "Context likely overflowed or the session became too large.",
    "",
    "## Last User Request",
    last_prompt,
    "",
    "## Recent Context",
]

for role, text in recent:
    lines.extend([f"### {role}", text, ""])

lines.extend([
    "## Instructions For New Session",
    "1. Continue the same task without resuming the old session.",
    "2. Re-read only the minimum necessary local files before editing.",
    "3. Avoid dumping large tool outputs back into the conversation.",
    "4. If web content is needed, fetch narrowly and persist results to local files.",
    "5. Keep MaaS prompt input safely below the model hard limit.",
    "",
    "## Ready-To-Paste Prompt",
    "The previous Claude GLM session overflowed its context window. Continue this task from the recovery pack above. Do not ask to resume the old session. First restate the task briefly, inspect only the minimum necessary local files, then continue the work.",
    "",
])

out_md.write_text("\n".join(lines), encoding="utf-8")
os.chmod(out_md, 0o600)
print(cwd)
PY

RECOVERY_CWD="$(python3 - "$OUT_MD" <<'PY'
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for line in text.splitlines():
    prefix = '- Original cwd: `'
    suffix = '`'
    if line.startswith(prefix) and line.endswith(suffix):
        print(line[len(prefix):-1])
        break
PY
)"

cat <<EOF
Recovery pack written:
  $OUT_MD

Fresh session:
  cd "$RECOVERY_CWD" && claude-glm

Paste this into the new session:
  cat "$OUT_MD"
EOF

if [[ "$LAUNCH" == "1" ]]; then
  echo
  echo "Launching fresh claude-glm session in: $RECOVERY_CWD"
  echo "Paste this file as the first prompt after Claude opens:"
  echo "  $OUT_MD"
  echo
  cd "$RECOVERY_CWD"
  exec claude-glm
fi
