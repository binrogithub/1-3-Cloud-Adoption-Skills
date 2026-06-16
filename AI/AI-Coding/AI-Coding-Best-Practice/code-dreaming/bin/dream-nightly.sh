#!/usr/bin/env bash
# Nightly dream pass — dedup + stale-path validation + L3 compress + conflict
# detection over the project memory. Safe to cron. Dry-run unless MCE_APPLY=1.
#
#   bin/dream-nightly.sh [/path/to/repo]
#
# Env:
#   MCE_MEMORY_DIR  memory store (default: native ~/.claude/projects/<key>/memory)
#   MCE_APPLY=1     actually write (default: dry-run, report only)
#   MCE_DREAM_INTERVAL_DAYS=7  minimum days between scheduled runs
#   MCE_FORCE=1     bypass scheduling gates
#   MCE_LLM=1       run bin/dream-llm.sh after deterministic dream when present
#   PYTHON          python binary (default: python3)
set -uo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
REPO="${1:-$PWD}"
APPLY=""; [ "${MCE_APPLY:-0}" = "1" ] && APPLY="--apply"
INTERVAL="${MCE_DREAM_INTERVAL_DAYS:-7}"
FORCE=""; [ "${MCE_FORCE:-0}" = "1" ] && FORCE="--force"

args=(scripts/dream.py --repo-root "$REPO" $APPLY)
[ -n "${MCE_MEMORY_DIR:-}" ] && args+=(--memory-dir "$MCE_MEMORY_DIR")

sched=(scripts/should_run.py check --repo-root "$REPO" --interval-days "$INTERVAL" --owner-pid "$$" $FORCE)
[ -n "${MCE_MEMORY_DIR:-}" ] && sched+=(--memory-dir "$MCE_MEMORY_DIR")

stamp=(scripts/should_run.py stamp --repo-root "$REPO" --interval-days "$INTERVAL" --owner-pid "$$")
[ -n "${MCE_MEMORY_DIR:-}" ] && stamp+=(--memory-dir "$MCE_MEMORY_DIR")

release=(scripts/should_run.py release --repo-root "$REPO" --owner-pid "$$")
[ -n "${MCE_MEMORY_DIR:-}" ] && release+=(--memory-dir "$MCE_MEMORY_DIR")

cd "$PROJ" || exit 1
sched_rc=0
"$PY" "${sched[@]}" || sched_rc=$?
if [ "$sched_rc" != "0" ]; then
  rc=$sched_rc
  [ "$rc" = "2" ] && exit 0
  exit "$rc"
fi

cleanup() {
  "$PY" "${release[@]}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "[$(date '+%F %T' 2>/dev/null || echo nightly)] dream over repo=$REPO apply=${MCE_APPLY:-0}"
"$PY" "${args[@]}"
rc=$?
if [ "$rc" != "0" ]; then
  exit "$rc"
fi

if [ "${MCE_LLM:-0}" = "1" ]; then
  if [ -x "bin/dream-llm.sh" ]; then
    llm_args=(--repo-root "$REPO")
    [ -n "${MCE_MEMORY_DIR:-}" ] && llm_args+=(--memory-dir "$MCE_MEMORY_DIR")
    bin/dream-llm.sh "${llm_args[@]}"
    rc=$?
    if [ "$rc" != "0" ]; then
      exit "$rc"
    fi
  else
    echo "MCE_LLM=1 requested, but bin/dream-llm.sh is not present; skipping LLM leg."
  fi
fi

"$PY" "${stamp[@]}"
trap - EXIT INT TERM
