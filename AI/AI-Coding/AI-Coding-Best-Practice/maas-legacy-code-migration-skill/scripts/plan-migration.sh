#!/usr/bin/env bash
set -euo pipefail

# plan-migration.sh — MaaS agent plans migration batches
# Usage: plan-migration.sh --analysis=<file>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

ANALYSIS_FILE=""
BATCH_SIZE="${BATCH_SIZE:-10}"

for arg in "$@"; do
  case "$arg" in
    --analysis=*) ANALYSIS_FILE="${arg#--analysis=}" ;;
    --help|-h)
      echo "Usage: $0 --analysis=<understanding-doc>"
      exit 0
      ;;
  esac
done

if [ -z "$ANALYSIS_FILE" ]; then
  echo "ERROR: --analysis=<file> is required" >&2
  exit 1
fi

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Migration Planning ==="
echo "Input: $ANALYSIS_FILE"
echo "Batch size: $BATCH_SIZE"

ANALYSIS_CONTENT=$(cat "$ANALYSIS_FILE")

PLAN_PROMPT="You are a migration specialist creating a migration plan. Given the following understanding document, produce a migration plan with:
1. Migration targets (files/modules that need to change)
2. Dependencies between targets (must migrate together)
3. Batch groupings ($BATCH_SIZE files per batch, respecting dependencies)
4. Migration order (leaf modules first, core modules last)
5. Risk per batch (high/medium/low based on complexity and test coverage)
6. Characterization test requirements (which paths need tests before migration)

Rules:
- Never exceed $BATCH_SIZE files per batch
- If file A depends on file B, they must be in the same batch or B's batch must come first
- Mix high-risk and low-risk files in each batch
- Each batch must be independently testable

Understanding Document:
${ANALYSIS_CONTENT}"

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

echo "$PLAN_CONTENT" > "${OUTPUT_DIR}/migration-plan.md"
echo "Migration plan written to ${OUTPUT_DIR}/migration-plan.md"
echo ""
echo "=== MIGRATION PLAN REQUIRES HUMAN REVIEW ==="
echo "Review the plan and approve before running batch transforms."
