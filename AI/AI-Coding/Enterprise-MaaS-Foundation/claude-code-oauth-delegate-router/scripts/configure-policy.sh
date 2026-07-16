#!/usr/bin/env bash
# oauth-delegate-router: install C3 policy + C4 hooks + C5 agent + C8 skills
# into the ORCHESTRATOR client (~/.claude). Idempotent; marker-fenced; additive.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CD="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HY="$HOME/.claude-hybrid"
mkdir -p "$CD" "$HY" "$CD/skills" "$CD/agents"

# ── C3 policy block into CLAUDE.md (replace between markers if present) ──
MD="$CD/CLAUDE.md"
B='# >>> oauth-delegate-router policy v1 >>>'
E='# <<< oauth-delegate-router policy v1 <<<'
touch "$MD"
python3 - "$MD" "$SRC/assets/orchestrator-policy.md" "$B" "$E" <<'PY'
import sys
md, blk, b, e = sys.argv[1:5]
cur = open(md).read()
new = open(blk).read().strip() + "\n"
if b in cur and e in cur:
    pre = cur.split(b)[0]; post = cur.split(e, 1)[1]
    cur = pre + new + post.lstrip("\n")
else:
    cur = cur.rstrip() + ("\n\n" if cur.strip() else "") + new
open(md, "w").write(cur)
print(f"policy block installed in {md}")
PY

# ── C4 hook merge into settings.json ──
cp "$SRC/scripts/route-hint.sh" "$HY/route-hint.sh"; chmod +x "$HY/route-hint.sh"
python3 - "$CD/settings.json" "$HY/route-hint.sh" <<'PY'
import json, os, sys
p, hook = sys.argv[1:3]
d = json.load(open(p)) if os.path.exists(p) else {}
hooks = d.setdefault("hooks", {})
ups = hooks.setdefault("UserPromptSubmit", [])
entry = {"hooks": [{"type": "command", "command": hook}]}
if not any(hook in json.dumps(x) for x in ups):
    ups.append(entry)
json.dump(d, open(p, "w"), indent=2)
print(f"UserPromptSubmit hook merged into {p}")
PY

# ── C5 agent + C8 skills + schemas ──
cp "$SRC/assets/glm-executor.agent.md" "$CD/agents/glm-executor.md"
for s in glm-review glm-repo-summary glm-test-batch; do
  mkdir -p "$CD/skills/$s"
  cp "$SRC/assets/skills/$s/SKILL.md" "$CD/skills/$s/SKILL.md"
done
cp "$SRC/assets/brief-schema.json" "$SRC/assets/manifest-schema.json" "$HY/"
echo "agent, 3 skills, schemas installed"
echo "DONE — plain 'claude' transport untouched (no ANTHROPIC_* written anywhere)"
