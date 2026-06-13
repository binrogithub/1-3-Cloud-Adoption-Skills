#!/usr/bin/env bash
set -euo pipefail

# run-security-audit.sh — Orchestrates security-auditor persona via MaaS
# Usage: run-security-audit.sh [--scope=<secrets|dependencies|all>]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
FINDINGS_DIR="${FINDINGS_DIR:-/tmp/review-findings}"
mkdir -p "$FINDINGS_DIR"

SCOPE="all"

for arg in "$@"; do
  case "$arg" in
    --scope=*) SCOPE="${arg#--scope=}" ;;
    --help|-h)
      echo "Usage: $0 [--scope=<secrets|dependencies|all>]"
      exit 0
      ;;
  esac
done

echo "=== Security Audit (scope: $SCOPE) ==="

# Secret detection (local, no MaaS tokens)
if [ "$SCOPE" = "secrets" ] || [ "$SCOPE" = "all" ]; then
  echo "--- Scanning for secrets ---"
  SECRETS_FOUND=0

  # Common secret patterns
  while IFS= read -r -d '' file; do
    # Skip binary files and common non-source directories
    case "$file" in
      */node_modules/*|*/.git/*|*/vendor/*|*.png|*.jpg|*.gif|*.ico|*.woff|*.woff2) continue ;;
    esac

    # Check for hardcoded secrets
    if grep -nE '(sk-|key-|AKIA)[A-Za-z0-9]{16,}' "$file" 2>/dev/null; then
      echo "  FINDING: Potential API key in $file"
      SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
    if grep -nE '(password|passwd|pwd|secret|token)\s*=\s*['\''"][^'\''"]{8,}' "$file" 2>/dev/null; then
      echo "  FINDING: Potential hardcoded secret in $file"
      SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
    if grep -nE '-----BEGIN (RSA |EC )?PRIVATE KEY-----' "$file" 2>/dev/null; then
      echo "  FINDING: Private key in $file"
      SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
  done < <(git ls-files -z 2>/dev/null || find . -type f -print0 2>/dev/null)

  echo "Secrets scan complete: $SECRETS_FOUND potential findings"
fi

# Dependency audit
if [ "$SCOPE" = "dependencies" ] || [ "$SCOPE" = "all" ]; then
  echo "--- Auditing dependencies ---"

  if [ -f package-lock.json ] || [ -f yarn.lock ]; then
    echo "Running npm audit..."
    npm audit --json 2>/dev/null > "${FINDINGS_DIR}/npm-audit.json" || true
  fi

  if [ -f requirements.txt ] || [ -f Pipfile.lock ] || [ -f poetry.lock ]; then
    echo "Running pip audit..."
    if command -v pip-audit &>/dev/null; then
      pip-audit --format json 2>/dev/null > "${FINDINGS_DIR}/pip-audit.json" || true
    else
      echo "WARNING: pip-audit not installed; skipping Python dependency audit"
    fi
  fi

  if command -v trivy &>/dev/null; then
    echo "Running trivy filesystem scan..."
    trivy fs --format json . 2>/dev/null > "${FINDINGS_DIR}/trivy-audit.json" || true
  fi
fi

# MaaS-backed deep security analysis (only if scope=all and API_KEY is set)
if [ "$SCOPE" = "all" ] && [ -n "${API_KEY:-}" ]; then
  echo "--- MaaS-backed deep security analysis ---"

  MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
  MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"

  CHANGED_FILES=$(git diff --name-only 2>/dev/null || echo "")
  if [ -n "$CHANGED_FILES" ]; then
    SECURITY_PROMPT="You are a security engineer performing a code security audit. Analyze the following code for security vulnerabilities. Classify each finding by OWASP Top 10 category and severity (critical, high, medium, low). For each finding, provide: file, line, severity, category, title, description, evidence (code snippet), and remediation. Return as JSON array."

    for file in $CHANGED_FILES; do
      if [ ! -f "$file" ]; then continue; fi
      FILE_CONTENT=$(head -c 50000 "$file" 2>/dev/null || echo "")
      [ -z "$FILE_CONTENT" ] && continue

      sleep 1.2

      curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$(python3 -c "
import json, sys
msg = f'${SECURITY_PROMPT}\n\nFile: {sys.argv[1]}\n\n\`\`\`\n{sys.argv[2]}\n\`\`\`'
print(json.dumps({'model': '${MAAS_MODEL}', 'messages': [{'role': 'user', 'content': msg}], 'max_tokens': 4096, 'temperature': 0.1}))
" "$file" "$FILE_CONTENT")" 2>/dev/null | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(r['choices'][0]['message']['content'])
except: pass
" >> "${FINDINGS_DIR}/security-findings.json" 2>/dev/null || true

      echo "  Audited: $file"
    done
  fi
fi

echo "=== Security audit complete ==="
echo "Findings saved to ${FINDINGS_DIR}/"
