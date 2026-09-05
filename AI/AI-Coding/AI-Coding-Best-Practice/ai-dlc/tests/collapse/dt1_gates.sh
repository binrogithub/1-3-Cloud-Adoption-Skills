#!/usr/bin/env bash
# D1 task 1.6 as an executable audit, re-based by landing L1: the
# verification role is deleted, not replaced, and the budget capability
# is gone outright. No oracle executable exists on disk, no checker
# registry survives in our executables, the gates are delivery and
# merge ONLY, no billing/cost subcommand or budget key survives — and
# tag v0.8.0 still carries bin/oracle.py, so the deletion has a
# verified rollback anchor — or, if this republished copy's history does
# not carry v0.8.0 at all, the anchor check SKIPs with a named reason
# rather than failing a promise this copy cannot keep.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)   # audit the checkout this
                                             # script belongs to — the same
                                             # audit runs at master and in a
                                             # task worktree
cd "$REPO"

# 1. no oracle executable anywhere we own — not tracked, not on disk
#    (evidence/ is append-only history and keeps its oracle-era records)
[[ -z "$(git ls-files bin probes | grep -i 'oracle' || true)" ]] \
  || { echo "FAIL: oracle files still tracked"; exit 1; }
[[ ! -e bin/oracle.py ]] || { echo "FAIL: bin/oracle.py on disk"; exit 1; }
[[ ! -d probes ]] || { echo "FAIL: probes/ on disk"; exit 1; }
N=$(find bin -type f -name '*oracle*' | wc -l)
[[ "$N" -eq 0 ]] || { echo "FAIL: ${N} oracle-named file(s) under bin/"; exit 1; }

# 2. no checker registry / hand-written property rule in our executables
if grep -rqiE 'CHECKER_SETS|checker_registry|run_property|PROPERTY_RULES' bin/ 2>/dev/null; then
  echo "FAIL: checker-registry code survives in bin/"; exit 1
fi

# 3. gates limited to delivery and merge (G-DELIVER-1, MERGE_GATE)
#    across every executable we own — no identifier names cost or budget
GOT=$(grep -rhoE 'G-[A-Z0-9]+(-[A-Z0-9]+)*|MERGE_GATE|WORKER_FAILURE' \
      bin/*.py | sort -u)
WANT=$(printf 'G-DELIVER-1\nMERGE_GATE\n' | sort -u)
[[ "$GOT" == "$WANT" ]] \
  || { echo "FAIL: gate ids in bin/ are [$(echo "$GOT" | tr '\n' ' ')], want exactly delivery+merge"; exit 1; }

# 4. (landing L1) no budget capability survives anywhere we own: no
#    budget key, no cap, no ledger write, no cost gate id, no BUDGET
#    stage — in executables AND config
if grep -rqiE 'G-COST|input_token_cap|budget\.json|BUDGET_STOP|usage\.jsonl' \
      bin/ config/ 2>/dev/null; then
  echo "FAIL: budget-capability code survives in bin/ or config/:"; \
  grep -rniE 'G-COST|input_token_cap|budget\.json|BUDGET_STOP|usage\.jsonl' bin/ config/; exit 1
fi

# 5. (landing L1.10) the surface audit: an executable offering a
#    billing or cost subcommand fails. Ours offer exactly these, and
#    nothing else: report = init/deliver/gate/exception/correct/next, plan =
#    roles/prompt/dispatch/phase/decide/review/boundary/accept/close/
#    sweep (v0.7.0 added exception and the phase runner; the
#    design-review change adds review; agent-onboarding adds next).
R_SUBS=$(python3.12 bin/report.py --help 2>&1 \
         | grep -oE '\{[a-z,]+\}' | head -1)
[[ "$R_SUBS" == "{init,deliver,gate,exception,correct,next}" ]] \
  || { echo "FAIL: report.py subcommands are $R_SUBS, want {init,deliver,gate,exception,correct,next}"; exit 1; }
P_SUBS=$(python3.12 bin/plan.py --help 2>&1 \
         | grep -oE '\{[a-z,-]+\}' | head -1)
# any-directory adds the workspace subcommands (classify, stage,
# snapshot, untouched, sandbox); containment P2 adds the plane tool
# dispatches (validate, graph, status); P3's N6 adds migrate and
# retires return (the scratch it copied back is gone with the scratch);
# uidesigner-opendesign adds the design trio (design, design-scope,
# design-pin) — the dashes force the match below to include '-' now;
# phase-chain-automation adds initiative; codegraph-role adds codegraph
# (build/brief) + codegraph-scope; the Understand-Anything backend adds
# codegraph-pin (mirrors design-pin); route-selfcheck-and-intent-menu
# adds suggest (G3 intent-scenario candidate menu)
[[ "$P_SUBS" == "{roles,validate,graph,status,prompt,dispatch,phase,decide,review,boundary,accept,initiative,close,sweep,classify,stage,snapshot,untouched,migrate,sandbox,design,design-index,design-scope,codegraph-scope,codegraph,browser-verify,design-pick,design-pin,codegraph-pin,bench,scaffold,next,suggest}" ]] \
  || { echo "FAIL: plan.py subcommands are $P_SUBS"; exit 1; }
# return is retired outright: argparse rejects it, and the refusal is
# the named kind, not a silent alias
if python3.12 bin/plan.py return --change x \
     --workspace /tmp --project /tmp >/dev/null 2>&1; then
  echo "FAIL: plan.py still accepts the retired subcommand 'return'"; exit 1
fi
# and the runtime rejects the retired subcommands outright (argparse: rc 2)
for sub in bill cost session; do
  if python3.12 bin/report.py "$sub" --task-dir /nonexistent \
       >/dev/null 2>&1; then
    echo "FAIL: report.py still accepts subcommand '$sub'"; exit 1
  fi
done

# 6. the rollback anchor: the deleted oracle is recoverable from tag v0.8.0.
#    Distinguish "this repo's history does not carry the tag at all" (a
#    republished copy — SKIP, not this repo's failure to carry) from "the tag
#    exists but the anchored file is missing from it" (a genuinely broken
#    anchor — FAIL, exactly as before this change).
if ! git rev-parse -q --verify v0.8.0 >/dev/null 2>&1; then
  echo "SKIP: v0.8.0 anchor not carried by this repo's history (republished copy) — see SKILL.md"
elif ! git cat-file -e v0.8.0:bin/oracle.py 2>/dev/null; then
  echo "FAIL: v0.8.0:bin/oracle.py missing — deletion has no rollback anchor"
  exit 1
fi

echo "D1 GATES: pass (no oracle on disk, no checker registry, gates = delivery+merge only, no budget surface, no billing subcommand, v0.8.0 anchor verified or SKIP'd above)"
