#!/usr/bin/env bash
set -euo pipefail

# run-full-workflow.sh — Orchestrates the full Spec-Plan-Build-Test workflow
# Usage: run-full-workflow.sh --input=<requirements-file> [--grill]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

INPUT_FILE=""
GRILL=false

for arg in "$@"; do
  case "$arg" in
    --input=*) INPUT_FILE="${arg#--input=}" ;;
    --grill)   GRILL=true ;;
    --help|-h)
      echo "Usage: $0 --input=<requirements-file> [--grill]"
      exit 0
      ;;
  esac
done

if [ -z "$INPUT_FILE" ]; then
  echo "ERROR: --input=<file> is required" >&2
  exit 1
fi

echo "========================================="
echo "  MaaS Spec-Plan-Build-Test Workflow"
echo "========================================="
echo ""

# Phase 1: Spec
echo ">>> Phase 1: Spec"
GRILL_FLAG=""
if $GRILL; then GRILL_FLAG="--grill"; fi
"$SCRIPT_DIR/run-spec-phase.sh" --input="$INPUT_FILE" $GRILL_FLAG || {
  echo "FAILED at Spec phase gate"
  exit 1
}
echo ""

# Phase 2: Plan
echo ">>> Phase 2: Plan"
"$SCRIPT_DIR/run-plan-phase.sh" --spec="${OUTPUT_DIR}/specification.md" || {
  echo "FAILED at Plan phase gate"
  exit 1
}
echo ""

# Wait for human approval
echo ">>> Plan Approval Required"
echo "Review ${OUTPUT_DIR}/plan.md and add 'APPROVED' when ready."
read -rp "Has the plan been approved? (yes/no): " APPROVED
if [ "$APPROVED" != "yes" ]; then
  echo "Workflow paused. Re-run build phase after approval:"
  echo "  $SCRIPT_DIR/run-build-phase.sh --plan=${OUTPUT_DIR}/plan.md"
  exit 0
fi

# Add APPROVED marker to plan
echo -e "\n\nAPPROVED" >> "${OUTPUT_DIR}/plan.md"
echo ""

# Phase 3: Build
echo ">>> Phase 3: Build"
"$SCRIPT_DIR/run-build-phase.sh" --plan="${OUTPUT_DIR}/plan.md" || {
  echo "FAILED at Build phase gate (quality gate)"
  exit 1
}
echo ""

# Phase 4: Test
echo ">>> Phase 4: Test"
"$SCRIPT_DIR/run-test-phase.sh" --spec="${OUTPUT_DIR}/specification.md" || {
  echo "FAILED at Test phase gate"
  exit 1
}
echo ""

echo "========================================="
echo "  ALL GATES PASSED — Ready to Ship"
echo "========================================="
echo ""
echo "Artifacts produced:"
echo "  - ${OUTPUT_DIR}/specification.md"
echo "  - ${OUTPUT_DIR}/plan.md"
echo "  - ${OUTPUT_DIR}/implementation.md"
echo "  - ${OUTPUT_DIR}/test-results.md"
