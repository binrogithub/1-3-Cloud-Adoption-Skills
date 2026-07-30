#!/usr/bin/env bash
# oauth-delegate-router install — C1 wrapper + isolated config dir + runners.
#
# Usage: install.sh <litellm-virtual-key> [--base-url URL] [--model NAME]
#
# Reuses ../../litellm-maas-auto-plugin/client/configure-claude-code.sh (it
# honors CLAUDE_CONFIG_DIR) instead of vendoring client-config logic.
# Server-side prerequisites (install first — see SKILL.md):
#   anthropic_stream_guard + anthropic_reasoning_filter + smart_router mounted
#   and registered, with smart_router_rules.json,
#   use_chat_completions_url_for_anthropic_messages: true,
#   a `claude-*` wildcard model route (required for W1 sub-orchestration).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="http://127.0.0.1:4000"; MODEL="claude-opus-4-6"; KEY=""
while [ $# -gt 0 ]; do case "$1" in
  --base-url) BASE_URL="$2"; shift 2;;
  --model) MODEL="$2"; shift 2;;
  *) KEY="$1"; shift;;
esac; done
[ -n "$KEY" ] || { echo "usage: install.sh <litellm-virtual-key> [--base-url URL] [--model NAME]" >&2; exit 1; }
command -v claude >/dev/null || { echo "claude CLI not found (npm i -g @anthropic-ai/claude-code)" >&2; exit 1; }

CONFIGURE="${CONFIGURE_CC:-$ROOT/../litellm-maas-auto-plugin/client/configure-claude-code.sh}"
[ -f "$CONFIGURE" ] || { echo "configure-claude-code.sh not found at $CONFIGURE — set CONFIGURE_CC" >&2; exit 1; }

GLM_DIR="$HOME/.claude-glm"
mkdir -p "$GLM_DIR" "$HOME/.claude-hybrid"
CLAUDE_CONFIG_DIR="$GLM_DIR" bash "$CONFIGURE" "$KEY" --base-url "$BASE_URL" --model "$MODEL" >/dev/null
python3 - "$GLM_DIR" "$KEY" <<'PY'
import json, os, sys
d, key = sys.argv[1], sys.argv[2]
s = json.load(open(f"{d}/settings.json"))
s.setdefault("env", {})["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = "198000"
json.dump(s, open(f"{d}/settings.json", "w"), indent=2)
p = f"{d}/.claude.json"
c = json.load(open(p)) if os.path.exists(p) else {}
c["hasCompletedOnboarding"] = True
c["customApiKeyResponses"] = {"approved": [key[-20:]], "rejected": []}
json.dump(c, open(p, "w"), indent=2)
print("isolated client configured:", d)
PY
chmod 600 "$GLM_DIR/settings.json" "$GLM_DIR/.claude.json"

BIN="${BIN_DIR:-/usr/local/bin}"; [ -w "$BIN" ] || BIN="$HOME/.local/bin"
mkdir -p "$BIN"
cat > "$BIN/claude-glm" <<W
#!/usr/bin/env bash
# oauth-delegate-router C1: isolated Claude Code client -> LiteLLM -> MaaS.
export CLAUDE_CONFIG_DIR="$GLM_DIR"
unset ANTHROPIC_AUTH_TOKEN CLAUDECODE CLAUDE_CODE_ENTRYPOINT
exec claude "\$@"
W
chmod +x "$BIN/claude-glm"
ln -sf "$ROOT/scripts/delegate" "$BIN/delegate"
ln -sf "$ROOT/scripts/workflow" "$BIN/workflow"
echo "installed: $BIN/claude-glm, $BIN/delegate, $BIN/workflow"
echo "next: scripts/configure-policy.sh (orchestrator policy+hooks), then scripts/verify.sh"
