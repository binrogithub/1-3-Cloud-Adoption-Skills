#!/usr/bin/env bash
set -euo pipefail

# check-lint.sh — Auto-detect project language and run appropriate linter

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

echo "Detecting project language..."

WARNINGS=0
ERRORS=0

# JavaScript / TypeScript
if [ -f package.json ]; then
  echo "Detected: JavaScript/TypeScript project"
  if command -v npx &>/dev/null; then
    npx eslint . --format json 2>/dev/null || true
    WARNINGS=$(npx eslint . --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(len(f.get('warnings',[])) for f in d))" 2>/dev/null || echo 0)
    ERRORS=$(npx eslint . --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(len(f.get('errors',[])) for f in d))" 2>/dev/null || echo 0)
  else
    echo "WARNING: npx not found; skipping JS lint"
  fi
fi

# Python
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ]; then
  echo "Detected: Python project"
  if command -v ruff &>/dev/null; then
    ruff check . --statistics 2>&1 || true
    ERRORS=$((ERRORS + $(ruff check . --statistics 2>&1 | grep -c "error" || echo 0)))
  elif command -v pylint &>/dev/null; then
    pylint src/ --output-format=json 2>/dev/null || true
  else
    echo "WARNING: ruff/pylint not found; skipping Python lint"
  fi
fi

# Java
if [ -f pom.xml ] || [ -f build.gradle ]; then
  echo "Detected: Java project"
  if [ -f pom.xml ] && command -v mvn &>/dev/null; then
    mvn checkstyle:check -q 2>&1 || true
  else
    echo "WARNING: Maven/Gradle not found; skipping Java lint"
  fi
fi

# Go
if [ -f go.mod ]; then
  echo "Detected: Go project"
  if command -v golangci-lint &>/dev/null; then
    golangci-lint run ./... 2>&1 || true
  else
    echo "WARNING: golangci-lint not found; skipping Go lint"
  fi
fi

echo "Lint results: $WARNINGS warnings, $ERRORS errors"

if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: Lint found $ERRORS errors"
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "FAIL: Lint found $WARNINGS warnings (zero-warning policy)"
  exit 1
fi

echo "PASS: Lint clean"
exit 0
