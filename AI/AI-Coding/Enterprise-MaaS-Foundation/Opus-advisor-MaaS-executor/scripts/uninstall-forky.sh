#!/usr/bin/env bash
# uninstall-forky.sh — reversible teardown. Stops service, strips .bashrc block,
# removes hooks, optionally deletes repo + memory. Does NOT touch LiteLLM,
# OAuth creds, or claude-glm.
set -euo pipefail

FORKY_DIR="${FORKY_DIR:-$HOME/dev/forky}"
SKILL_DIR="$HOME/.claude/skills/Opus-advisor-MaaS-executor"

log()  { printf '\033[1;34m[uninstall-forky]\033[0m %s\n' "$*"; }
ask()  { printf '\033[1;33m[uninstall-forky]\033[0m %s [y/N] ' "$*"; read -r ans; [[ "$ans" == "y" || "$ans" == "Y" ]]; }

# --- 1. stop + disable service ------------------------------------------------
if systemctl --user is-active --quiet forky.service 2>/dev/null; then
  log "stopping forky.service"
  systemctl --user stop forky.service
fi
systemctl --user disable forky.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/forky.service"
systemctl --user daemon-reload
log "service removed"

# --- 2. strip .bashrc block ---------------------------------------------------
BASHRC="$HOME/.bashrc"
BEGIN='# >>> forky-claude-routing >>>'
END='# <<< forky-claude-routing <<<'
if grep -q "^$BEGIN" "$BASHRC" 2>/dev/null; then
  log "removing .bashrc block"
  python3 - "$BASHRC" "$BEGIN" "$END" <<'PY'
import sys, pathlib
target, begin, end = sys.argv[1:4]
lines = pathlib.Path(target).read_text().splitlines(keepends=True)
out, i = [], 0
while i < len(lines):
    if lines[i].strip() == begin:
        while i < len(lines) and lines[i].strip() != end:
            i += 1
        i += 1
    else:
        out.append(lines[i]); i += 1
pathlib.Path(target).write_text(''.join(out))
PY
fi

rm -f "$HOME/.local/bin/claude-forky"
log "claude-forky wrapper removed"

# --- 3. remove hooks from settings.json ---------------------------------------
SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$SETTINGS" ]]; then
  log "removing forky hooks from settings.json"
  python3 - "$SETTINGS" "$FORKY_DIR" <<'PY'
import json, sys, pathlib
settings_path = pathlib.Path(sys.argv[1])
forky_dir = sys.argv[2]
hook_cmd = f"{forky_dir}/bin/forky-hook"
s = json.loads(settings_path.read_text())
hooks = s.get("hooks", {})
for key in ("UserPromptSubmit", "PostToolUse"):
    if key in hooks:
        hooks[key] = [h for h in hooks[key]
                      if h.get("hooks", [{}])[0].get("command") != hook_cmd]
        if not hooks[key]:
            del hooks[key]
if not hooks:
    s.pop("hooks", None)
settings_path.write_text(json.dumps(s, indent=2) + "\n")
PY
fi

# --- 4. optional: delete repo + memory ----------------------------------------
if ask "delete forky repo at $FORKY_DIR?"; then
  rm -rf "$FORKY_DIR"
  log "repo deleted"
fi

MEM="$HOME/.claude/projects/-root/memory/forky-claude-routing.md"
if [[ -f "$MEM" ]] && ask "delete memory file $MEM?"; then
  rm -f "$MEM"
  INDEX="$HOME/.claude/projects/-root/memory/MEMORY.md"
  if [[ -f "$INDEX" ]]; then
    grep -v "forky-claude-routing.md" "$INDEX" > "$INDEX.tmp" && mv "$INDEX.tmp" "$INDEX"
  fi
  log "memory removed"
fi

log "uninstall complete. Open a new terminal for env changes to take effect."
