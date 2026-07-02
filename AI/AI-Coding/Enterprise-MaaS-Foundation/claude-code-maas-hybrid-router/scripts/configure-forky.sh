#!/usr/bin/env bash
# configure-forky.sh — probe backends, write .env, install systemd service,
# wire .bashrc + settings.json hooks, save memory, restart service.
# Idempotent: safe to re-run.
set -euo pipefail

FORKY_DIR="${FORKY_DIR:-$HOME/dev/forky}"
VISION_BRANCH="${FORKY_VISION_BRANCH:-forky-vision-routing}"
BUN_BIN="${BUN_BIN:-$HOME/.bun/bin/bun}"
SKILL_DIR="$HOME/.claude/skills/claude-code-maas-hybrid-router"

# --- tunables (env overrides) ------------------------------------------------
LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:4000/v1}"
LITELLM_KEY="${LITELLM_KEY:-${LITELLM_CCR_KEY:-${EXEC_API_KEY:-}}}"
EXEC_MODEL="${FORKY_EXEC_MODEL:-glm-5.2}"
FORKY_PORT="${FORKY_PORT:-3458}"
OPUS_MODEL="${FORKY_OPUS_MODEL:-claude-opus-4-8}"
PLAN_MODEL_OVERRIDE="${FORKY_PLAN_MODEL:-}"
VISION_MODEL_OVERRIDE="${FORKY_VISION_MODEL:-}"
REVIEW_MODEL_OVERRIDE="${FORKY_REVIEW_MODEL:-}"
WRAPPER="$HOME/.local/bin/claude-forky"
TRUST_ROOT_WORKSPACE="${FORKY_TRUST_ROOT_WORKSPACE:-1}"

log()  { printf '\033[1;34m[configure-forky]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[configure-forky] warn:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[configure-forky] error:\033[0m %s\n' "$*" >&2; exit 1; }

# --- sanity ------------------------------------------------------------------
[[ -d "$FORKY_DIR/.git" ]] || die "forky not installed at $FORKY_DIR. Run install-forky.sh first."
[[ -n "$LITELLM_KEY" ]]   || die "LITELLM_KEY (or LITELLM_CCR_KEY / EXEC_API_KEY) not set."

mkdir -p "$HOME/.forky"

# === 1. probe LiteLLM ========================================================
log "probing LiteLLM at $LITELLM_URL"
models_json="$(curl -fsS -H "Authorization: Bearer $LITELLM_KEY" "$LITELLM_URL/models" 2>/dev/null)" \
  || die "LiteLLM /v1/models unreachable at $LITELLM_URL. Is the LiteLLM proxy running? (claude-code-maas-direct-router skill owns it.)"

echo "$models_json" | jq -e --arg m "$EXEC_MODEL" '.data[] | select(.id == $m)' >/dev/null 2>&1 \
  || die "model '$EXEC_MODEL' not in LiteLLM /v1/models. Available: $(echo "$models_json" | jq -r '.data[].id' | tr '\n' ' ')"

# real chat call — catches the glm-5.1 trap (listed but 400s)
log "sending test chat/completions to '$EXEC_MODEL'"
chat_resp="$(curl -fsS -H "Authorization: Bearer $LITELLM_KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"$EXEC_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}" \
  "$LITELLM_URL/chat/completions" 2>&1)" \
  || die "chat/completions to '$EXEC_MODEL' failed. The model is listed but not callable — check LiteLLM config (api_base, api_key, quota)."

log "LiteLLM OK — '$EXEC_MODEL' serves requests"

# === 2. verify OAuth creds ===================================================
CREDS="$HOME/.claude/.credentials.json"
[[ -f "$CREDS" ]] || die "OAuth credentials missing at $CREDS. Run 'claude /login' first."
jq -e '.claudeAiOauth.accessToken // .accessToken // .access_token // .oauthAccount.accessToken' "$CREDS" >/dev/null 2>&1 \
  || die "$CREDS exists but has no OAuth token. Re-run 'claude /login'. (Expected .claudeAiOauth.accessToken)"
log "OAuth credentials present"

# === 2b. verify compatibility patches ========================================
grep -q 'request.normalized_roles' "$FORKY_DIR/src/server.ts" 2>/dev/null \
  || die "forky src/server.ts lacks request-role normalization. Re-run install-forky.sh so Claude Code system/developer message roles do not 400."

# === 3. port conflict check ==================================================
if command -v ss >/dev/null 2>&1; then
  if ss -ltn "sport = :$FORKY_PORT" 2>/dev/null | grep -q ":$FORKY_PORT"; then
    owner_pid="$(ss -ltnp "sport = :$FORKY_PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
    if [[ -n "$owner_pid" ]] && ps -p "$owner_pid" -o args= 2>/dev/null | grep -q "bin/forky"; then
      log "port $FORKY_PORT owned by an existing forky process (will restart it)"
    else
      die "port $FORKY_PORT is in use by PID ${owner_pid:-unknown} (not forky). Stop it or set FORKY_PORT to a free port."
    fi
  fi
fi

# === 4. write .env ===========================================================
ENV_FILE="$FORKY_DIR/.env"
log "writing $ENV_FILE"
cat > "$ENV_FILE" <<EOF
# Managed by claude-code-maas-hybrid-router skill. Re-run configure-forky.sh to update.
EXEC_BASE_URL="$LITELLM_URL"
EXEC_API_KEY="$LITELLM_KEY"
EXEC_MODEL="$EXEC_MODEL"
FORKY_OPUS_MODEL="$OPUS_MODEL"
PORT="$FORKY_PORT"
EOF
[[ -n "$PLAN_MODEL_OVERRIDE" ]] && printf 'FORKY_PLAN_MODEL="%s"\n' "$PLAN_MODEL_OVERRIDE" >> "$ENV_FILE"
[[ -n "$VISION_MODEL_OVERRIDE" ]] && printf 'FORKY_VISION_MODEL="%s"\n' "$VISION_MODEL_OVERRIDE" >> "$ENV_FILE"
[[ -n "$REVIEW_MODEL_OVERRIDE" ]] && printf 'FORKY_REVIEW_MODEL="%s"\n' "$REVIEW_MODEL_OVERRIDE" >> "$ENV_FILE"
chmod 600 "$ENV_FILE"

# === 5. systemd user service =================================================
UNIT_SRC="$SKILL_DIR/assets/forky.service"
UNIT_DST="$HOME/.config/systemd/user/forky.service"
mkdir -p "$(dirname "$UNIT_DST")"
log "installing systemd unit → $UNIT_DST"
cp "$UNIT_SRC" "$UNIT_DST"

systemctl --user daemon-reload
systemctl --user enable forky.service >/dev/null 2>&1

# linger so it survives logout/reboot
if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "$USER" 2>/dev/null || warn "enable-linger failed (may need root)"
fi

log "restarting forky.service"
systemctl --user restart forky.service

# wait for readiness
for i in $(seq 1 20); do
  if tail -5 "$HOME/.forky/forky.log" 2>/dev/null | grep -q "server.start\|Listening\|listening on"; then
    break
  fi
  sleep 0.5
done
sleep 1
if ! systemctl --user is-active --quiet forky.service; then
  warn "forky.service not active — check: journalctl --user -u forky -n 50 --no-pager"
fi
log "forky.service active"

# === 6. claude-forky wrapper + .bashrc block (idempotent) =====================
log "writing $WRAPPER"
mkdir -p "$(dirname "$WRAPPER")"
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
# claude-forky: route this Claude Code session through forky only.
# Plain \`claude\` intentionally remains on the Claude.ai OAuth connector.
set -euo pipefail

export ANTHROPIC_BASE_URL="http://127.0.0.1:$FORKY_PORT"
export ANTHROPIC_MODEL="\${ANTHROPIC_MODEL:-claude-sonnet-4-6}"
export CLAUDE_CODE_AUTO_COMPACT_WINDOW="\${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-180000}"
export CLAUDE_CODE_DISABLE_MOUSE_CLICKS="\${CLAUDE_CODE_DISABLE_MOUSE_CLICKS:-1}"
# Keep Claude.ai MCP connectors enabled. Claude Code disables them whenever an
# API key/auth token source is present, but forky does not require inbound auth.
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY
case ",\${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="\${NO_PROXY:+\$NO_PROXY,}127.0.0.1,localhost" ;;
esac

if command -v systemctl >/dev/null 2>&1; then
  if ! systemctl --user is-active --quiet forky.service 2>/dev/null; then
    systemctl --user start forky.service >/dev/null 2>&1 || true
  fi
fi

for _ in {1..20}; do
  if curl -fsS -m 1 "\$ANTHROPIC_BASE_URL/health" >/dev/null 2>&1 ||
     curl -fsS -m 1 "\$ANTHROPIC_BASE_URL/" >/dev/null 2>&1; then
    exec claude "\$@"
  fi
  sleep 0.25
done

echo "claude-forky: forky is not reachable at \$ANTHROPIC_BASE_URL" >&2
echo "claude-forky: check 'systemctl --user status forky.service' and ~/.forky/forky.log" >&2
exit 1
EOF
chmod 700 "$WRAPPER"

BASHRC="$HOME/.bashrc"
SNIPPET="$SKILL_DIR/assets/bashrc-snippet.sh"
BEGIN='# >>> forky-claude-routing >>>'
END='# <<< forky-claude-routing <<<'

log "updating $BASHRC"
if grep -q "^$BEGIN" "$BASHRC" 2>/dev/null; then
  # replace existing block
  python3 - "$BASHRC" "$SNIPPET" "$BEGIN" "$END" <<'PY'
import sys, pathlib
target, snippet, begin, end = sys.argv[1:5]
lines = pathlib.Path(target).read_text().splitlines(keepends=True)
out = []
i = 0
replaced = False
while i < len(lines):
    if lines[i].strip() == begin:
        # skip to end
        while i < len(lines) and lines[i].strip() != end:
            i += 1
        i += 1  # skip end line
        out.append(pathlib.Path(snippet).read_text())
        if not out[-1].endswith('\n'):
            out[-1] += '\n'
        replaced = True
    else:
        out.append(lines[i])
        i += 1
if not replaced:
    out.append(pathlib.Path(snippet).read_text())
pathlib.Path(target).write_text(''.join(out))
PY
else
  printf '\n' >> "$BASHRC"
  cat "$SNIPPET" >> "$BASHRC"
fi
log ".bashrc updated"

# === 7. settings.json hooks ==================================================
SETTINGS="$HOME/.claude/settings.json"
log "merging hooks into $SETTINGS"
python3 - "$SETTINGS" "$FORKY_DIR" <<'PY'
import json, sys, pathlib
settings_path = pathlib.Path(sys.argv[1])
forky_dir = sys.argv[2]
hook_cmd = f"{forky_dir}/bin/forky-hook"

settings_path.parent.mkdir(parents=True, exist_ok=True)
if settings_path.exists():
    s = json.loads(settings_path.read_text())
else:
    s = {}

hooks = s.setdefault("hooks", {})
us = hooks.setdefault("UserPromptSubmit", [])
entry = {"hooks": [{"type": "command", "command": hook_cmd}]}
if not any(h.get("hooks", [{}])[0].get("command") == hook_cmd for h in us):
    us.append(entry)

ptu = hooks.setdefault("PostToolUse", [])
pm_entry = {"matcher": "ExitPlanMode", "hooks": [{"type": "command", "command": hook_cmd}]}
if not any(h.get("matcher") == "ExitPlanMode" and h.get("hooks", [{}])[0].get("command") == hook_cmd for h in ptu):
    ptu.append(pm_entry)

settings_path.write_text(json.dumps(s, indent=2) + "\n")
PY
log "settings.json hooks merged"

# === 7b. trust /root workspace for local permissions ==========================
if [[ "$TRUST_ROOT_WORKSPACE" == "1" && -f "$HOME/.claude.json" ]]; then
  log "trusting /root workspace in ~/.claude.json so settings.local.json permissions are honored"
  cp "$HOME/.claude.json" "$HOME/.claude.json.bak.$(date +%Y%m%d%H%M%S)"
  tmp="$(mktemp)"
  jq '.projects["/root"].hasTrustDialogAccepted = true' "$HOME/.claude.json" > "$tmp"
  mv "$tmp" "$HOME/.claude.json"
fi

# === 8. memory ===============================================================
MEM_DIR="$HOME/.claude/projects/-root/memory"
if [[ -d "$MEM_DIR" ]]; then
  log "writing memory"
  cp "$SKILL_DIR/assets/memory-template.md" "$MEM_DIR/forky-claude-routing.md"
  # update MEMORY.md index
  INDEX="$MEM_DIR/MEMORY.md"
  LINE='- [forky claude routing](forky-claude-routing.md) — `claude-forky` via forky(:3458, systemd): exec→GLM-5.2, plan/vision→Opus(OAuth); plain `claude` keeps Claude.ai connectors'
  if [[ -f "$INDEX" ]]; then
    if ! grep -q "forky-claude-routing.md" "$INDEX"; then
      printf '%s\n' "$LINE" >> "$INDEX"
    fi
  else
    printf '%s\n' "$LINE" > "$INDEX"
  fi
else
  warn "memory dir $MEM_DIR not found — skipped memory save"
fi

# === 9. final restart to pick up .env ========================================
systemctl --user restart forky.service
sleep 1

log ""
log "done. Open a NEW terminal and run: claude-forky"
log "verify with: $SKILL_DIR/scripts/verify-forky.sh"
