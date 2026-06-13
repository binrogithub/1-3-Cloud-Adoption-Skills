#!/usr/bin/env bash
set -euo pipefail

# run-review.sh — Orchestrates code-reviewer persona via MaaS
# Usage: run-review.sh [--with-security] [--no-security] [--files=<list>] [--base=<branch>]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="${SKILL_DIR}/assets/config/review-config.json"
FINDINGS_DIR="${FINDINGS_DIR:-/tmp/review-findings}"
mkdir -p "$FINDINGS_DIR"

WITH_SECURITY=false
NO_SECURITY=false
FILES=""
BASE_BRANCH="main"

for arg in "$@"; do
  case "$arg" in
    --with-security) WITH_SECURITY=true ;;
    --no-security)   NO_SECURITY=true ;;
    --files=*)       FILES="${arg#--files=}" ;;
    --base=*)        BASE_BRANCH="${arg#--base=}" ;;
    --help|-h)
      echo "Usage: $0 [--with-security] [--no-security] [--files=<list>] [--base=<branch>]"
      exit 0
      ;;
  esac
done

# Default: run review only (no security unless --with-security)
if $WITH_SECURITY && $NO_SECURITY; then
  echo "ERROR: Cannot use --with-security and --no-security together" >&2
  exit 1
fi

# Get changed files
if [ -z "$FILES" ]; then
  FILES=$(git diff --name-only "$BASE_BRANCH" 2>/dev/null || git diff --name-only --cached 2>/dev/null || echo "")
fi

if [ -z "$FILES" ]; then
  echo "No changed files found. Nothing to review."
  exit 0
fi

echo "Reviewing files:"
echo "$FILES" | tr ' ' '\n' | while read -r f; do echo "  $f"; done

# Check for API key
if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  echo "Export your MaaS API key: export API_KEY='your-key-here'" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Run code-reviewer persona
echo "=== Running code-reviewer persona ==="
REVIEW_PROMPT="You are a senior staff engineer performing a code review. Review the following changed files for correctness, readability, architecture, security (shallow), and performance. Produce findings as JSON array with fields: id, file, line, severity, category, title, description, evidence, remediation. Severity levels: critical, high, medium, low, info."

for file in $FILES; do
  if [ ! -f "$file" ]; then
    echo "WARNING: File not found: $file (skipping)"
    continue
  fi

  FILE_CONTENT=$(head -c 50000 "$file" 2>/dev/null || echo "")
  if [ -z "$FILE_CONTENT" ]; then
    continue
  fi

  # Rate limit: wait minimum interval between MaaS calls
  sleep 1.2

  RESPONSE=$(curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
prompt = sys.argv[1]
content = sys.argv[2]
msg = f'{prompt}\n\nFile: {sys.argv[3]}\n\n\`\`\`\n{content}\n\`\`\`'
print(json.dumps({
    'model': '${MAAS_MODEL}',
    'messages': [{'role': 'user', 'content': msg}],
    'max_tokens': 4096,
    'temperature': 0.1
}))
" "$REVIEW_PROMPT" "$FILE_CONTENT" "$file")" 2>/dev/null) || true

  # Extract findings from response
  if [ -n "$RESPONSE" ]; then
    echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    content = r['choices'][0]['message']['content']
    print(content)
except: pass
" >> "${FINDINGS_DIR}/review-findings.json" 2>/dev/null || true
  fi

  echo "  Reviewed: $file"
done

echo "Review findings saved to ${FINDINGS_DIR}/review-findings.json"

# Run security audit if requested
if $WITH_SECURITY; then
  echo "=== Running security-auditor persona ==="
  if [ -f "${SKILL_DIR}/scripts/run-security-audit.sh" ]; then
    "${SKILL_DIR}/scripts/run-security-audit.sh"
  else
    echo "WARNING: Security audit script not found"
  fi
fi

echo "=== Review complete ==="
