#!/usr/bin/env bash
# Full reversal. Never touches OAuth creds, plain claude transport, or LiteLLM.
set -euo pipefail
CD="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 - "$CD/CLAUDE.md" <<'PY'
import sys,os
p=sys.argv[1]; b='# >>> oauth-delegate-router policy v1 >>>'; e='# <<< oauth-delegate-router policy v1 <<<'
if os.path.exists(p):
    c=open(p).read()
    if b in c and e in c:
        open(p,"w").write(c.split(b)[0] + c.split(e,1)[1].lstrip("\n")); print("policy block removed")
PY
python3 - "$CD/settings.json" <<'PY'
import json,sys,os
p=sys.argv[1]
if os.path.exists(p):
    d=json.load(open(p)); ups=d.get("hooks",{}).get("UserPromptSubmit",[])
    d.get("hooks",{})["UserPromptSubmit"]=[x for x in ups if "route-hint" not in json.dumps(x)]
    json.dump(d,open(p,"w"),indent=2); print("hook removed")
PY
rm -f "$CD/agents/glm-executor.md"; rm -rf "$CD/skills/glm-review" "$CD/skills/glm-repo-summary" "$CD/skills/glm-test-batch"
rm -f /usr/local/bin/claude-glm /usr/local/bin/delegate /usr/local/bin/workflow
echo "kept: ~/.claude-glm (delegate config+sessions), ~/.claude-hybrid (audit) — remove manually if desired"
echo "to revoke the virtual key: POST /key/delete on LiteLLM with the master key"
