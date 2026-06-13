#!/usr/bin/env bash
set -euo pipefail

# run-test-phase.sh — Generate and run tests from specification via MaaS
# Usage: run-test-phase.sh --spec=<file>

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

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Test Phase ==="
echo "Input: $SPEC_FILE"

SPEC_CONTENT=$(cat "$SPEC_FILE" 2>/dev/null || echo "")

TEST_PROMPT="You are a test engineer generating tests from a specification. Follow these rules:
1. Derive tests from the specification, NOT the implementation
2. Test naming: test_<function>_<scenario>_<expected_result>
3. Cover: happy path, edge cases, error paths
4. Mock all MaaS API calls (never call real MaaS in tests)
5. Each test must be independent (no execution order dependency)
6. Include assertions with descriptive error messages

Generate tests for the following specification:
${SPEC_CONTENT}

For each test file, provide the complete content with clear markers:
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
    'max_tokens': 16384,
    'temperature': 0.1
}))
" "$TEST_PROMPT")")

TEST_CONTENT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: Failed to parse MaaS response: {e}', file=sys.stderr)
    sys.exit(1)
")

echo "$TEST_CONTENT" > "${OUTPUT_DIR}/test-results.md"
echo "Test code written to ${OUTPUT_DIR}/test-results.md"

# Run the actual test suite
echo ""
echo "=== Running Test Suite ==="
TEST_EXIT=0

if command -v pytest &>/dev/null; then
  pytest --tb=short -q 2>&1 || TEST_EXIT=$?
elif command -v go &>/dev/null && [ -f go.mod ]; then
  go test ./... 2>&1 || TEST_EXIT=$?
elif [ -f pom.xml ]; then
  mvn test -q 2>&1 || TEST_EXIT=$?
elif [ -f package.json ]; then
  npx jest --coverage 2>&1 || TEST_EXIT=$?
else
  echo "WARNING: No test runner detected"
fi

if [ "$TEST_EXIT" -ne 0 ]; then
  echo "TEST GATE FAILED — some tests failed"
  exit 1
fi

echo "=== Test Phase Complete ==="
