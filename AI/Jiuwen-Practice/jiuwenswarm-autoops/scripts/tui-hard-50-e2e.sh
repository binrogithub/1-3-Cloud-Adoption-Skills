#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DOC_FILE="${HARD_OPS_CASES_DOC:-$ROOT_DIR/docs/jiuwen-autoops-50-hard-operations-test-cases.md}"
RUN_PREFIX="${RUN_PREFIX:-hardops-$(date -u +%Y%m%dT%H%M%SZ)}"
START_AT="${START_AT:-1}"
RESULT_DIR="${RESULT_DIR:-$ROOT_DIR/.runtime/hard-50-e2e/$RUN_PREFIX}"

mkdir -p "$RESULT_DIR"

extract_cases() {
  python3 - "$DOC_FILE" <<'PY'
from pathlib import Path
import re
import sys

lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
for index, line in enumerate(lines):
    heading = re.match(r"^### OPS-(\d{2})：", line)
    if not heading:
        continue
    number = heading.group(1)
    for candidate in lines[index + 1:]:
        if candidate.startswith("### OPS-"):
            break
        user_input = re.match(r"^\*\*用户输入：\*\*(.*)$", candidate)
        if user_input:
            prompt = user_input.group(1).strip()
            if prompt.startswith("“") and prompt.endswith("”"):
                prompt = prompt[1:-1]
            prompt = re.sub(r"\s+", " ", prompt).strip()
            print(f"{number}\t{prompt}")
            break
PY
}

case_count=0
while IFS=$'\t' read -r number prompt; do
  case_count=$((case_count + 1))
  if (( 10#$number < START_AT )); then
    continue
  fi
  session="${RUN_PREFIX}-${number}"
  case_log="$RESULT_DIR/${number}.driver.log"
  printf '[%s/50] START session=%s\n' "$number" "$session"
  # Use the project launcher so every natural-language request is prefixed
  # with the ProjectManager route. Calling the upstream TUI binary directly
  # would test free-form agent behavior and can bypass the AutoOps contract.
  if ! "$SCRIPT_DIR/Jiuwen_autoops_tui" \
      --no-install \
      --once \
      --session "$session" \
      "$prompt" >"$case_log" 2>&1; then
    printf '[%s/50] FAIL session=%s log=%s\n' "$number" "$session" "$case_log" >&2
    tail -n 100 "$case_log" >&2
    exit 1
  fi
  printf '[%s/50] PASS session=%s history=/root/.jiuwenswarm/agent/sessions/%s/history.jsonl\n' "$number" "$session" "$session"
done < <(extract_cases)

if (( case_count != 50 )); then
  printf 'expected 50 cases, extracted %s\n' "$case_count" >&2
  exit 2
fi
printf 'TUI_HARD_50_E2E_RESULT=PASS total=50 result_dir=%s\n' "$RESULT_DIR"
