#!/usr/bin/env bash
set -euo pipefail

# run-build-phase.sh — Implement code from approved plan via MaaS
# Usage: run-build-phase.sh --plan=<file>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

PLAN_FILE=""

for arg in "$@"; do
  case "$arg" in
    --plan=*) PLAN_FILE="${arg#--plan=}" ;;
    --help|-h)
      echo "Usage: $0 --plan=<plan-file>"
      exit 0
      ;;
  esac
done

if [ -z "$PLAN_FILE" ]; then
  echo "ERROR: --plan=<file> is required" >&2
  exit 1
fi

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: File not found: $PLAN_FILE" >&2
  exit 1
fi

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Build Phase ==="
echo "Input: $PLAN_FILE"

PLAN_CONTENT=$(cat "$PLAN_FILE")

# Verify plan has been approved (check for approval marker)
if ! grep -q "APPROVED" "$PLAN_FILE" 2>/dev/null; then
  echo "WARNING: Plan has not been marked as APPROVED."
  echo "Add 'APPROVED' to the plan file after human review, then re-run."
  echo "Continuing anyway (override with APPROVED marker in plan file)..."
fi

BUILD_PROMPT="You are a senior engineer implementing code from an approved plan. Follow these rules strictly:
1. Touch only the files listed in the plan
2. Match existing code style
3. Minimum diff - no speculative features
4. Implement in vertical slices: one test -> one implementation -> commit
5. Every changed line must trace to the specification

Implement the following plan:
${PLAN_CONTENT}

For each file, provide the complete file content with clear markers:
--- FILE: <path> ---
<content>
--- END FILE ---"

sleep 1.2

RESPONSE=$(curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, sys
print(json.dumps({
    'model': '${MAAS_MODEL}',
    'messages': [{'role': 'user', 'content': sys.argv[1]}],
    'max_tokens': 32768,
    'temperature': 0.1
}))
" "$BUILD_PROMPT")")

BUILD_CONTENT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: Failed to parse MaaS response: {e}', file=sys.stderr)
    sys.exit(1)
")

echo "$BUILD_CONTENT" > "${OUTPUT_DIR}/implementation.md"
echo "Implementation written to ${OUTPUT_DIR}/implementation.md"

# Run quality gate
echo ""
echo "=== Running Quality Gate ==="
if [ -f "${SKILL_DIR}/../maas-ai-coding-quality-skill/scripts/run-quality-gate.sh" ]; then
  "${SKILL_DIR}/../maas-ai-coding-quality-skill/scripts/run-quality-gate.sh" --all || {
    echo "QUALITY GATE FAILED — fix issues before proceeding to Test phase"
    exit 1
  }
else
  echo "WARNING: Quality skill not found; skipping quality gate"
fi

echo "=== Build Phase Complete ==="
