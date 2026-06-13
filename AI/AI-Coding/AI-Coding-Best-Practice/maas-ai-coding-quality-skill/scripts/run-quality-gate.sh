#!/usr/bin/env bash
set -euo pipefail

# run-quality-gate.sh — Main quality gate orchestrator
# Usage: run-quality-gate.sh --gate=<name> or --all
# Gates: lint, test, coverage, security

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="${SKILL_DIR}/assets/config/quality-gates.json"
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/quality-gate-evidence}"
mkdir -p "$EVIDENCE_DIR"

GATE=""
ALL_GATES=false

for arg in "$@"; do
  case "$arg" in
    --gate=*)  GATE="${arg#--gate=}" ;;
    --all)     ALL_GATES=true ;;
    --help|-h)
      echo "Usage: $0 --gate=<lint|test|coverage|security> | --all"
      echo "  --gate=<name>  Run a specific gate"
      echo "  --all          Run all gates in sequence"
      exit 0
      ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

run_gate() {
  local gate_name="$1"
  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "=== Gate: $gate_name ($timestamp) ==="

  case "$gate_name" in
    lint)
      "$SCRIPT_DIR/check-lint.sh"
      ;;
    test)
      # Run project test command (auto-detect)
      if command -v pytest &>/dev/null; then
        pytest --tb=short -q 2>&1
      elif command -v go &>/dev/null && [ -f go.mod ]; then
        go test ./... 2>&1
      elif [ -f pom.xml ]; then
        mvn test -q 2>&1
      elif [ -f package.json ]; then
        npx jest --no-coverage 2>&1 || npm test 2>&1
      else
        echo "ERROR: No test runner detected" >&2
        return 1
      fi
      ;;
    coverage)
      "$SCRIPT_DIR/verify-coverage.sh"
      ;;
    security)
      echo "Security gate delegates to maas-code-review-and-security-skill"
      echo "Run: ../maas-code-review-and-security-skill/scripts/run-security-audit.sh"
      if [ -d "${SKILL_DIR}/../maas-code-review-and-security-skill/scripts" ]; then
        "${SKILL_DIR}/../maas-code-review-and-security-skill/scripts/run-security-audit.sh"
      else
        echo "WARNING: Security skill not found; skipping security gate"
      fi
      ;;
    *)
      echo "ERROR: Unknown gate: $gate_name" >&2
      return 1
      ;;
  esac

  local exit_code=$?
  echo "{\"gate\":\"$gate_name\",\"exit_code\":$exit_code,\"timestamp\":\"$timestamp\"}" \
    > "${EVIDENCE_DIR}/${gate_name}-evidence.json"

  if [ "$exit_code" -ne 0 ]; then
    echo "FAIL: Gate $gate_name failed (exit code $exit_code)"
    return 1
  fi
  echo "PASS: Gate $gate_name"
  return 0
}

if $ALL_GATES; then
  echo "Running all quality gates..."
  FAILED=0
  # Parallel: lint and test
  run_gate lint || FAILED=1
  run_gate test || FAILED=1
  # Sequential: coverage depends on test
  run_gate coverage || FAILED=1
  # Sequential: security last (highest token cost)
  run_gate security || FAILED=1
  if [ "$FAILED" -ne 0 ]; then
    echo "QUALITY GATE FAILED — see evidence in $EVIDENCE_DIR"
    exit 1
  fi
  echo "QUALITY GATE PASSED — all gates green"
  exit 0
elif [ -n "$GATE" ]; then
  run_gate "$GATE"
  exit $?
else
  echo "ERROR: Specify --gate=<name> or --all" >&2
  exit 1
fi
