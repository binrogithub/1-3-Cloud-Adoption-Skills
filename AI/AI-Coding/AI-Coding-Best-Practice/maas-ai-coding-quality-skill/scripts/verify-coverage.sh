#!/usr/bin/env bash
set -euo pipefail

# verify-coverage.sh — Run coverage and compare against threshold
# Usage: verify-coverage.sh --threshold=<number>

THRESHOLD=80

for arg in "$@"; do
  case "$arg" in
    --threshold=*) THRESHOLD="${arg#--threshold=}" ;;
    --help|-h)
      echo "Usage: $0 --threshold=<number>"
      echo "  --threshold=N  Minimum coverage percentage (default: 80)"
      exit 0
      ;;
  esac
done

echo "Checking coverage (threshold: ${THRESHOLD}%)..."

COVERAGE_PCT=0

# Python
if [ -f pyproject.toml ] || [ -f setup.py ]; then
  if command -v pytest &>/dev/null; then
    COVERAGE_PCT=$(pytest --cov=src --cov-report=term-missing -q 2>&1 \
      | grep -oP 'TOTAL\s+\K\d+' || echo 0)
  fi
fi

# Go
if [ -f go.mod ]; then
  COVERAGE_PCT=$(go test -coverprofile=coverage.out ./... 2>/dev/null \
    && go tool cover -func=coverage.out 2>/dev/null \
    | grep total | awk '{print int($3)}' || echo 0)
fi

# Java
if [ -f pom.xml ]; then
  if command -v mvn &>/dev/null; then
    mvn test jacoco:report -q 2>/dev/null || true
    COVERAGE_PCT=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('target/site/jacoco/jacoco.xml')
    root = tree.getroot()
    missed = int(root.find('.//counter[@type=\"LINE\"]').get('missed'))
    covered = int(root.find('.//counter[@type=\"LINE\"]').get('covered'))
    print(int(covered * 100 / (missed + covered)))
except: print(0)
" 2>/dev/null || echo 0)
  fi
fi

# JavaScript
if [ -f package.json ]; then
  if command -v npx &>/dev/null; then
    COVERAGE_PCT=$(npx jest --coverage --coverageReporters=text-summary 2>&1 \
      | grep -oP 'All files\s+\|\s+\K\d+' || echo 0)
  fi
fi

echo "Coverage: ${COVERAGE_PCT}% (threshold: ${THRESHOLD}%)"

if [ "$COVERAGE_PCT" -lt "$THRESHOLD" ]; then
  echo "FAIL: Coverage ${COVERAGE_PCT}% below threshold ${THRESHOLD}%"
  exit 1
fi

echo "PASS: Coverage meets threshold"
exit 0
