#!/usr/bin/env bash
# D3 task 3.4/3.5: the outcome is judged from the event frames. An
# interrupt with no responder exits non-zero naming the tool and its
# argument; round-complete is chat.processing_status(is_processing=false);
# a final envelope claiming success NEVER decides alone — an interrupt
# earlier in the stream still fails the dispatch. Offline judge mode
# (--frames-file): no client, no billing, no live plane anywhere.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$T/pkg.json" <<EOF
{"requirement": "Visitors cannot move between pages; the site needs navigation on every page.", "change_id": "add-nav-bar", "capability": "website", "repo": "$REPO"}
EOF

# (a) an interrupt frame: a permission interrupt naming the tool and its
#     argument — no responder exists headless -> exit 7
cat > "$T/interrupt.jsonl" <<'EOF'
{"type":"event","event":"chat.delta","payload":{"text":"considering the shell command"}}
{"type":"event","event":"chat.ask_user_question","payload":{"event_type":"chat.ask_user_question","request_id":"r1","source":"permission_interrupt","tool_name":"bash","tool_args":{"command":"cat /etc/shadow"},"questions":[{"question":"requires permission: bash cat /etc/shadow","header":"Permission","options":["allow","deny"],"multi_select":false}]}}
EOF
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs --package-file "$T/pkg.json" --frames-file "$T/interrupt.jsonl" > "$T/a.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 7 ]] || { echo "FAIL: interrupt exited $RC, want 7"; cat "$T/a.json"; exit 1; }
grep -q '"interrupted": true' "$T/a.json"
grep -q '"tool": "bash"' "$T/a.json"
grep -q '"cat /etc/shadow"' "$T/a.json"

# (b) round-complete: processing_status with is_processing false -> exit 0
cat > "$T/complete.jsonl" <<'EOF'
{"type":"event","event":"chat.delta","payload":{"text":"the artifact is written"}}
{"type":"event","event":"chat.tool_call","payload":{"tool":"write_file","arguments":{"path":"openspec/changes/add-nav-bar/specs/website/spec.md"}}}
{"type":"event","event":"chat.processing_status","payload":{"is_processing":false}}
EOF
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs --package-file "$T/pkg.json" --frames-file "$T/complete.jsonl" > "$T/b.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: round-complete exited $RC, want 0"; cat "$T/b.json"; exit 1; }
grep -q '"round_complete": true' "$T/b.json"
grep -q '"interrupted": false' "$T/b.json"

# (c) the trap: a final envelope claiming ok AND an interrupt earlier in
#     the stream -> STILL exit 7; the envelope never decides alone
cat > "$T/trap.jsonl" <<'EOF'
{"type":"event","event":"chat.ask_user_question","payload":{"event_type":"chat.ask_user_question","request_id":"r2","source":"permission_interrupt","tool_name":"write_file","tool_args":{"path":"/root/elsewhere/pwn.py"}}}
{"type":"event","event":"chat.processing_status","payload":{"is_processing":false}}
{"type":"event","event":"chat.final","payload":{"ok":true,"status":"ok","content":"all done; the artifact was written"}}
EOF
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs --package-file "$T/pkg.json" --frames-file "$T/trap.jsonl" > "$T/c.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 7 ]] || { echo "FAIL: envelope-over-interrupt exited $RC, want 7"; cat "$T/c.json"; exit 1; }
grep -q '"interrupted": true' "$T/c.json"
grep -q '"tool": "write_file"' "$T/c.json"
grep -q '"final_envelope_seen": true' "$T/c.json"
grep -q '"final_envelope_claims_ok": true' "$T/c.json"

# (d) the measured live shape (devteam D5 dispatch 1): a successful
#     round in a code mode ends at a genuine chat.final with NO closing
#     processing_status frame — these sessions carry zero
#     processing_status frames. The final frame's PRESENCE completes the
#     round; its payload is never the verdict
cat > "$T/live.jsonl" <<'EOF'
{"type":"event","event":"chat.processing_status","payload":{"is_processing":true,"is_complete":false}}
{"type":"event","event":"chat.reasoning","payload":{"text":"planning the artifact"}}
{"type":"event","event":"chat.tool_call","payload":{"tool":"write_file","arguments":{"path":"openspec/changes/add-nav-bar/proposal.md"}}}
{"type":"event","event":"chat.final","payload":{"event_type":"keepalive"}}
{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"the artifact was written"}}
EOF
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs --package-file "$T/pkg.json" --frames-file "$T/live.jsonl" > "$T/d.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: live-shape stream exited $RC, want 0"; cat "$T/d.json"; exit 1; }
grep -q '"round_complete": true' "$T/d.json"

# (e) a keepalive final alone is NOT a close: no closing status, no
#     genuine final -> inconclusive
cat > "$T/keepalive.jsonl" <<'EOF'
{"type":"event","event":"chat.processing_status","payload":{"is_processing":true}}
{"type":"event","event":"chat.final","payload":{"event_type":"keepalive"}}
EOF
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs --package-file "$T/pkg.json" --frames-file "$T/keepalive.jsonl" > "$T/e.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: keepalive-only stream exited $RC, want 1"; cat "$T/e.json"; exit 1; }
grep -q '"round_complete": false' "$T/e.json"
echo "D3 PLAN JUDGE: pass (interrupt names tool+argument and exits 7; round-complete exits 0; a final envelope claiming ok never overrides an interrupt; the measured live shape — genuine chat.final, no closing status — completes the round; keepalive alone does not)"
