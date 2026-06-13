#!/usr/bin/env bash
set -euo pipefail

# run-plan-phase.sh — Generate plan from specification via MaaS
# Usage: run-plan-phase.sh --spec=<file>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

SPEC_FILE=""

for arg in "$@"; do
  case "$arg" in
    --spec=*) SPEC_FILE="${arg#--spec=}" ;;
    --help|-h)
      echo "Usage: $0 --spec=<specification-file>"
      exit 0
      ;;
  esac
done

if [ -z "$SPEC_FILE" ]; then
  echo "ERROR: --spec=<file> is required" >&2
  exit 1
fi

if [ ! -f "$SPEC_FILE" ]; then
  echo "ERROR: File not found: $SPEC_FILE" >&2
  exit 1
fi

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Plan Phase ==="
echo "Input: $SPEC_FILE"

SPEC_CONTENT=$(cat "$SPEC_FILE")

PLAN_PROMPT="You are a senior engineer creating an implementation plan. Given the following specification, produce a plan document with these sections:
1. Approach - high-level design and architecture
2. Files Affected - table of files with action (create/modify/delete) and description
3. Change Description per File - specific changes for each file
4. Dependencies - new and existing dependencies
5. Risk Assessment - table with risk, likelihood, impact, mitigation
6. Rollback Strategy - how to revert if the change fails
7. Estimated Complexity - lines of code, files changed, effort
8. Vertical Slice Order - ordered list of smallest testable increments

IMPORTANT: Each vertical slice must be: write test -> implement -> verify -> commit.
Do NOT plan all tests then all implementation.

Specification:
${SPEC_CONTENT}"

sleep 1.2

RESPONSE=$(curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, sys
print(json.dumps({
    'model': '${MAAS_MODEL}',
    'messages': [{'role': 'user', 'content': sys.argv[1]}],
    'max_tokens': 8192,
    'temperature': 0.2
}))
" "$PLAN_PROMPT")")

PLAN_CONTENT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: Failed to parse MaaS response: {e}', file=sys.stderr)
    sys.exit(1)
")

echo "$PLAN_CONTENT" > "${OUTPUT_DIR}/plan.md"
echo "Plan written to ${OUTPUT_DIR}/plan.md"

echo ""
echo "=== PLAN GATE: HUMAN REVIEW REQUIRED ==="
echo "The plan has been generated but MUST be reviewed and approved by a human."
echo "Read ${OUTPUT_DIR}/plan.md and confirm the approach, risks, and rollback strategy."
echo "Do NOT proceed to Build phase until the plan is approved."
echo "========================================="
