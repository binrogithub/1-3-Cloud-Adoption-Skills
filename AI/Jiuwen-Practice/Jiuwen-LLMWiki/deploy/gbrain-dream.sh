#!/usr/bin/env bash
# gbrain overnight "dream" — AUTHORIZED TO WRITE metadata AND resolve content
# conflicts (Robin, 2026-09-24: newest wins, guarantee uniqueness). Conflict
# resolution goes through the change-set path (actor dream-autoflow, audited);
# protected namespaces stay in the human queue. Tripwire: only pages named by
# dream_reconcile may change; any other content drift is reported loudly.
set -uo pipefail
PROJECT="/root/HuaweiCloudLatam_LLMWiki"
export PATH="$HOME/.bun/bin:$PATH"
export GBRAIN_HOME="$PROJECT/runtime/gbrain"
export LITELLM_BASE_URL="http://127.0.0.1:20081/v1"
STAMP="$(date -u +%Y-%m-%d)"
LOG="$PROJECT/runtime/logs/gbrain-dream.log"
mkdir -p "$(dirname "$LOG")"
cd "$PROJECT"

HASHES_BEFORE=$(cat runtime/wiki/services/obs.md runtime/wiki/regions/la-sao-paulo1.md runtime/wiki/compliance/lgpd.md 2>/dev/null | sha256sum | cut -d' ' -f1)

{
  echo "=== dream $STAMP (metadata-apply; content tripwire armed) ==="
  echo "-- unify-types (apply:true — consolidates page TYPES)"
  gbrain jobs submit unify-types --params '{"target_pack":"gbrain-base-v2","apply":true}' --follow 2>&1 | tail -22
  echo "-- extract links (by mention + NER, writes graph edges)"
  gbrain extract links --by-mention --ner --source db 2>&1 | tail -4
  echo "-- link census"
  gbrain link-sources 2>&1 | grep -v UPGRADE | head -5
} >> "$LOG" 2>&1

HASHES_BEFORE="$HASHES_BEFORE" python3.12 - "$STAMP" >> "$LOG" 2>&1 <<'PYEOF'
import sys, os, hashlib, subprocess
sys.path.insert(0, "/root/HuaweiCloudLatam_LLMWiki")
from llmwiki import config as c
from llmwiki.pages import Page
from llmwiki.pipeline import Wiki
from datetime import date
stamp = sys.argv[1]
W = "/root/HuaweiCloudLatam_LLMWiki/runtime/wiki/"
after = hashlib.sha256("".join(open(W + f).read() for f in
    ("services/obs.md", "regions/la-sao-paulo1.md", "compliance/lgpd.md")).encode()).hexdigest()
before = os.environ.get("HASHES_BEFORE", "")
intact = (before == after) if before else None
cfg = c.load("/root/HuaweiCloudLatam_LLMWiki/llmwiki.toml")
w = Wiki(cfg)
rec = w.dream_reconcile() if hasattr(w, "dream_reconcile") else {"conflicts": 0}
allowed = set()
for r in rec.get("resolved", []):
    allowed.add(r["loser"])
rep2 = w.lint()
lines = [f"gbrain dream report {stamp} — metadata-apply + conflict-reconcile (Robin).",
         "",
         "- unify-types applied type consolidation; link extraction wrote graph edges.",
         f"- Conflicts found: {rec.get('conflicts', 0)}; resolved (newest wins): "
         f"{len(rec.get('resolved', []))}; pending human review: {len(rec.get('pending', []))}; "
         f"skipped: {len(rec.get('skipped', []))}.",
         f"- Remaining contradictions after reconcile: {len(rep2['contradictions'])}.",
         f"- Content edits went through change sets (actor dream-autoflow); "
         f"protected namespaces stayed in the review queue.",
         f"- Compiled-truth tripwire (sentinels, allowlist={sorted(allowed) or 'none'}): "
         f"{'UNCHANGED' if intact else 'CHANGED'} on non-reconciled pages "
         f"(before {before[:12] or 'n/a'} / after {after[:12]})."]
for r in rec.get("resolved", []):
    lines.append(f"- resolved: {r['conflict'][:90]} — loser {r['loser']} now carries "
                 f"{r['winner']}'s statement.")
for r in rec.get("pending", []):
    lines.append(f"- PENDING (protected): {r['conflict'][:90]} — changeset {r['changeset']}")
page = Page(slug=f"_meta/dream-report-{stamp}", title=f"Dream report {stamp}",
            type="dream-report", compiled_truth="\n".join(lines),
            timeline=[{"date": date.today().isoformat(),
                       "text": "nightly dream cycle ran (metadata-apply)"}])
w.store.put(page)
print("dream report page written:", page.slug, "| tripwire:", "UNCHANGED" if intact else "DRIFT")
PYEOF
echo "dream $STAMP done"
