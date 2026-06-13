#!/usr/bin/env bash
set -euo pipefail

# run-spec-phase.sh — Generate specification from requirements via MaaS
# Usage: run-spec-phase.sh --input=<file> [--grill]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

INPUT_FILE=""
GRILL=false

for arg in "$@"; do
  case "$arg" in
    --input=*) INPUT_FILE="${arg#--input=}" ;;
    --grill)   GRILL=true ;;
    --help|-h)
      echo "Usage: $0 --input=<requirements-file> [--grill]"
      echo "  --input=<file>  Requirements document to process"
      echo "  --grill         Challenge the spec with adversarial questions"
      exit 0
      ;;
  esac
done

if [ -z "$INPUT_FILE" ]; then
  echo "ERROR: --input=<file> is required" >&2
  exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
  echo "ERROR: File not found: $INPUT_FILE" >&2
  exit 1
fi

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Spec Phase ==="
echo "Input: $INPUT_FILE"

REQUIREMENTS=$(cat "$INPUT_FILE")

SPEC_PROMPT="You are a senior engineer writing a specification. Analyze the following requirements and produce a specification document with these sections:
1. Problem Statement - what problem this solves and why it's needed
2. Success Criteria - each criterion must be testable (no 'should', 'might', 'if possible'). Format: [criterion] -> verify: [how to test]
3. Assumptions - explicitly state all assumptions
4. Constraints - technical, regulatory, performance constraints
5. Out of Scope - what this feature explicitly does NOT do
6. Test Scenarios - happy path, edge cases, error paths
7. Dependencies - external services, libraries, other features
8. Risks - likelihood, impact, mitigation for each risk

Requirements:
${REQUIREMENTS}"

if $GRILL; then
  SPEC_PROMPT="${SPEC_PROMPT}

After producing the specification, challenge it with these grilling questions:
- What if each dependency is unavailable?
- What happens at the boundary of each constraint?
- How do you verify each success criterion?
- What is the rollback if this fails?
- Are there regulatory/compliance requirements?
Update the specification to address any gaps found."
fi

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
" "$SPEC_PROMPT")")

SPEC_CONTENT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: Failed to parse MaaS response: {e}', file=sys.stderr)
    sys.exit(1)
")

echo "$SPEC_CONTENT" > "${OUTPUT_DIR}/specification.md"
echo "Specification written to ${OUTPUT_DIR}/specification.md"

# Gate check: verify no ambiguous language
AMBIGUOUS=$(echo "$SPEC_CONTENT" | grep -ciE '\b(should|might|if possible|maybe|perhaps)\b' || echo 0)
if [ "$AMBIGUOUS" -gt 0 ]; then
  echo "WARNING: Specification contains $AMBIGUOUS instances of ambiguous language (should/might/if possible)"
  echo "Consider running with --grill to refine the specification"
fi

echo "=== Spec Phase Complete ==="
