#!/usr/bin/env bash
set -euo pipefail

# analyze-legacy.sh — MaaS agent reads legacy code and produces understanding document
# Usage: analyze-legacy.sh --language=<lang> --path=<dir>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

LANGUAGE=""
SOURCE_PATH="."

for arg in "$@"; do
  case "$arg" in
    --language=*) LANGUAGE="${arg#--language=}" ;;
    --path=*)     SOURCE_PATH="${arg#--path=}" ;;
    --help|-h)
      echo "Usage: $0 --language=<java|cobol|dotnet> [--path=<dir>]"
      exit 0
      ;;
  esac
done

if [ -z "$LANGUAGE" ]; then
  echo "ERROR: --language=<java|cobol|dotnet> is required" >&2
  exit 1
fi

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY environment variable not set" >&2
  exit 1
fi

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

echo "=== Legacy Code Analysis ==="
echo "Language: $LANGUAGE"
echo "Path: $SOURCE_PATH"

# Find source files based on language
case "$LANGUAGE" in
  java)   FILES=$(find "$SOURCE_PATH" -name "*.java" -type f 2>/dev/null | head -50) ;;
  cobol)  FILES=$(find "$SOURCE_PATH" \( -name "*.cbl" -o -name "*.cob" -o -name "*.cpy" \) -type f 2>/dev/null | head -50) ;;
  dotnet) FILES=$(find "$SOURCE_PATH" \( -name "*.cs" -o -name "*.vb" \) -type f 2>/dev/null | head -50) ;;
  *)      echo "ERROR: Unsupported language: $LANGUAGE (use java, cobol, or dotnet)" >&2; exit 1 ;;
esac

if [ -z "$FILES" ]; then
  echo "ERROR: No source files found for $LANGUAGE in $SOURCE_PATH" >&2
  exit 1
fi

FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "Found $FILE_COUNT source files"

ANALYSIS_PROMPT="You are a migration specialist analyzing legacy $LANGUAGE code. For each file, produce:
1. Purpose and responsibility of the file
2. Dependencies (imports, calls, data access)
3. Business logic encoded in the file
4. Complexity estimate (lines, branches, dependencies)
5. Migration risk (high/medium/low)

After analyzing all files, produce an aggregate understanding document with:
- Overview (what the system does in business terms)
- Architecture (high-level diagram)
- Entry points
- Data flow
- Key modules
- Seams (points where behavior can be isolated)
- Known risks
- Recommended migration order"

# Analyze files (respecting rate limit)
ANALYSIS_RESULTS=""
for file in $FILES; do
  echo "  Analyzing: $file"
  FILE_CONTENT=$(head -c 50000 "$file" 2>/dev/null || echo "")
  [ -z "$FILE_CONTENT" ] && continue

  sleep 1.2

  RESPONSE=$(curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
msg = f'${ANALYSIS_PROMPT}\n\nFile: {sys.argv[1]}\n\n\`\`\`\n{sys.argv[2]}\n\`\`\`'
print(json.dumps({'model': '${MAAS_MODEL}', 'messages': [{'role': 'user', 'content': msg}], 'max_tokens': 4096, 'temperature': 0.1}))
" "$file" "$FILE_CONTENT")" 2>/dev/null) || true

  if [ -n "$RESPONSE" ]; then
    RESULT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except: pass
" 2>/dev/null || echo "")
    ANALYSIS_RESULTS="${ANALYSIS_RESULTS}\n\n---\n## File: ${file}\n${RESULT}"
  fi
done

# Generate aggregate understanding document
echo -e "$ANALYSIS_RESULTS" > "${OUTPUT_DIR}/understanding.md"
echo "Understanding document written to ${OUTPUT_DIR}/understanding.md"
echo "=== Analysis Complete ==="
