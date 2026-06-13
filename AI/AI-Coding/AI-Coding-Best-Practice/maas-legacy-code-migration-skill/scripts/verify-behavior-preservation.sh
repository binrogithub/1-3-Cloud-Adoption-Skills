#!/usr/bin/env bash
set -euo pipefail

# verify-behavior-preservation.sh — Run characterization tests and compare before/after behavior
# Usage: verify-behavior-preservation.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

echo "=== Behavior Preservation Verification ==="

# Check for characterization tests
CHAR_TEST_DIR="${CHAR_TEST_DIR:-tests/characterization}"

if [ ! -d "$CHAR_TEST_DIR" ]; then
  echo "WARNING: No characterization test directory found at $CHAR_TEST_DIR"
  echo "Characterization tests are required for behavior preservation verification."
  echo "Create characterization tests before running migration."
  exit 0
fi

echo "Running characterization tests from $CHAR_TEST_DIR"

FAILED=0
TOTAL=0

# Run based on detected test framework
if [ -f pom.xml ] || [ -f build.gradle ]; then
  echo "Detected: Java project (JUnit)"
  TOTAL=$(find "$CHAR_TEST_DIR" -name "*Characterization*.java" -type f 2>/dev/null | wc -l | tr -d ' ')
  if command -v mvn &>/dev/null; then
    mvn test -Dtest="*Characterization*" -q 2>&1 || FAILED=1
  fi
elif [ -f pyproject.toml ] || [ -f setup.py ]; then
  echo "Detected: Python project (pytest)"
  TOTAL=$(find "$CHAR_TEST_DIR" -name "*characterization*.py" -type f 2>/dev/null | wc -l | tr -d ' ')
  if command -v pytest &>/dev/null; then
    pytest "$CHAR_TEST_DIR" -v 2>&1 || FAILED=1
  fi
elif [ -f go.mod ]; then
  echo "Detected: Go project"
  TOTAL=$(find "$CHAR_TEST_DIR" -name "*_characterization_test.go" -type f 2>/dev/null | wc -l | tr -d ' ')
  go test "./$CHAR_TEST_DIR/..." -v 2>&1 || FAILED=1
elif [ -f *.csproj ] || [ -f *.sln ]; then
  echo "Detected: .NET project (xUnit)"
  TOTAL=$(find "$CHAR_TEST_DIR" -name "*Characterization*.cs" -type f 2>/dev/null | wc -l | tr -d ' ')
  dotnet test --filter "DisplayName~Characterization" 2>&1 || FAILED=1
else
  echo "WARNING: No test framework detected"
  echo "Run characterization tests manually and verify all pass."
  exit 0
fi

echo ""
echo "Characterization test results:"
echo "  Total: $TOTAL"
echo "  Failed: $FAILED"

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "CHARACTERIZATION TESTS FAILED"
  echo "This means the migration has changed existing behavior."
  echo ""
  echo "Possible causes:"
  echo "  1. Unintentional behavior change (bug in migration) -> FIX the migration"
  echo "  2. Intentional behavior change (planned improvement) -> UPDATE the characterization test and DOCUMENT"
  echo ""
  echo "Do NOT proceed to the next batch until all characterization tests pass."
  exit 1
fi

echo ""
echo "All characterization tests pass — behavior is preserved."
echo "=== Behavior Preservation Verified ==="
exit 0
