#!/usr/bin/env bash
# Aggregate the delegation audit log.
python3 - "${DELEGATE_AUDIT:-$HOME/.claude-hybrid/route-audit.jsonl}" <<'PY'
import json, sys, collections
try: recs=[json.loads(l) for l in open(sys.argv[1])]
except FileNotFoundError: sys.exit("no audit log yet")
by=collections.Counter((r["route"],r["outcome"]) for r in recs)
tok_in=sum(r.get("tokens_in") or 0 for r in recs); tok_out=sum(r.get("tokens_out") or 0 for r in recs)
esc=sum(1 for r in recs if r["outcome"]=="escalated"); att=sum(1 for r in recs if r["route"]=="glm")
print(f"records={len(recs)} glm_attempts={att} escalations={esc} "
      f"escalation_rate={esc/max(att,1):.0%} glm_tokens in={tok_in} out={tok_out}")
for (route,outcome),n in sorted(by.items()): print(f"  {route:8s} {outcome:12s} {n}")
PY
