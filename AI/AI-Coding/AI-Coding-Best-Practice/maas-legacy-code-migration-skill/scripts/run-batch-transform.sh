#!/usr/bin/env bash
set -euo pipefail

# run-batch-transform.sh — MaaS agent transforms a batch of files
# Usage: run-batch-transform.sh --batch-size=<N> --batch-number=<M>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

BATCH_SIZE="${BATCH_SIZE:-10}"
BATCH_NUMBER="${BATCH_NUMBER:-1}"
DONE_LIST="${OUTPUT_DIR}/done.list"

for arg in "$@"; do
  case "$arg" in
    --batch-size=*)   BATCH_SIZE="${arg#--batch-size=}" ;;
    --batch-number=*) BATCH_NUMBER="${arg#--batch-number=}" ;;
    --help|-h)
      echo "Usage: $0 [--batch-size=N] [--batch-number=M]"
      exit 0
      ;;
  esac
done

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Batch Transform ==="
echo "Batch: $BATCH_NUMBER (size: $BATCH_SIZE)"

# Read migration plan
if [ ! -f "${OUTPUT_DIR}/migration-plan.md" ]; then
  echo "ERROR: migration-plan.md not found. Run plan-migration.sh first." >&2
  exit 1
fi

PLAN_CONTENT=$(cat "${OUTPUT_DIR}/migration-plan.md")

# Get files for this batch (skip done files)
touch "$DONE_LIST"
BATCH_FILES=$(git ls-files 2>/dev/null | grep -v -f "$DONE_LIST" | head -"$BATCH_SIZE" || echo "")

if [ -z "$BATCH_FILES" ]; then
  echo "No files remaining to migrate. All done!"
  exit 0
fi

echo "Files in this batch:"
echo "$BATCH_FILES" | while read -r f; do echo "  $f"; done

TRANSFORM_PROMPT="You are a migration specialist transforming legacy code. Follow these rules strictly:
1. Preserve existing behavior (this is a transform, not a rewrite)
2. Touch only the files in this batch
3. Match existing code style in the target codebase
4. Do not add speculative features
5. Document any behavior differences you discover

Migration Plan:
${PLAN_CONTENT}

Transform the following files. For each file, provide the complete new content:
--- FILE: <path> ---
<content>
--- END FILE ---"

# Transform files (respecting rate limit)
for file in $BATCH_FILES; do
  if [ ! -f "$file" ]; then
    echo "WARNING: File not found: $file (skipping)"
    continue
  fi

  echo "  Transforming: $file"
  FILE_CONTENT=$(head -c 50000 "$file" 2>/dev/null || echo "")
  [ -z "$FILE_CONTENT" ] && continue

  sleep 1.2

  RESPONSE=$(curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
msg = f'${TRANSFORM_PROMPT}\n\nFile: {sys.argv[1]}\n\n\`\`\`\n{sys.argv[2]}\n\`\`\`'
print(json.dumps({'model': '${MAAS_MODEL}', 'messages': [{'role': 'user', 'content': msg}], 'max_tokens': 16384, 'temperature': 0.1}))
" "$file" "$FILE_CONTENT")" 2>/dev/null) || true

  if [ -n "$RESPONSE" ]; then
    echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except: pass
" >> "${OUTPUT_DIR}/batch-${BATCH_NUMBER}-transform.md" 2>/dev/null || true
  fi
done

echo "Batch transform written to ${OUTPUT_DIR}/batch-${BATCH_NUMBER}-transform.md"

# Run characterization tests
echo ""
echo "=== Running Characterization Tests ==="
if [ -f "${SCRIPT_DIR}/verify-behavior-preservation.sh" ]; then
  "${SCRIPT_DIR}/verify-behavior-preservation.sh" || {
    echo "CHARACTERIZATION TESTS FAILED — behavior has changed"
    echo "Investigate the failures before proceeding."
    echo "Do NOT continue to the next batch until this batch is fixed."
    exit 1
  }
else
  echo "WARNING: Behavior verification script not found"
fi

# Run quality gate
echo ""
echo "=== Running Quality Gate ==="
if [ -f "${SKILL_DIR}/../maas-ai-coding-quality-skill/scripts/run-quality-gate.sh" ]; then
  "${SKILL_DIR}/../maas-ai-coding-quality-skill/scripts/run-quality-gate.sh" --all || {
    echo "QUALITY GATE FAILED — fix issues before proceeding"
    exit 1
  }
fi

# Record done files
COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
for file in $BATCH_FILES; do
  echo "$file $BATCH_NUMBER $COMMIT_HASH" >> "$DONE_LIST"
done

echo "=== Batch $BATCH_NUMBER Complete ==="
echo "Files recorded in $DONE_LIST"
echo ""
echo "NEXT STEPS:"
echo "1. Create PR for batch $BATCH_NUMBER"
echo "2. Wait for CI to pass"
echo "3. Get human review"
echo "4. Merge PR"
echo "5. Run next batch: $0 --batch-number=$((BATCH_NUMBER + 1))"
