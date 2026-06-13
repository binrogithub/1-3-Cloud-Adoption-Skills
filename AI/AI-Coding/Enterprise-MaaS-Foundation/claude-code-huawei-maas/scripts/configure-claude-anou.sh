#!/usr/bin/env bash
# claude-anou opt-in installer: adds an anonymous blind model-test command
# alongside `claude` and `claude-glm`.
#
#   claude-anou -> ccr (127.0.0.1:3456, custom router)
#               -> LiteLLM Provider (127.0.0.1:4000) -> anon-model-a | anon-model-b
#
# claude-anou launches Claude Code displaying only the model name
# "Anonymous-Model" and binds each project directory consistently to one of two
# hidden backends (anon-model-a / anon-model-b) so a human tester can compare two
# models blind. The per-project assignment lives in `.mt` in the project dir and
# is mirrored to ~/.claude-code-router/.session-model, the live signal the CCR
# custom router reads on every request.
#
# This installer is purely additive. It does NOT touch `claude`, `claude-glm`, or
# ~/.claude. It reuses the claude-glm router env, CCR config, and custom router,
# so run scripts/configure-claude-glm.sh first.
#
# Prerequisites:
#   - claude-glm already configured (~/.config/claude-glm/env, ccr, the archived
#     3-provider CCR config + custom-router from assets/ccr/).
#   - The LiteLLM stack (port 4000) exposes the `anon-model-a` and `anon-model-b`
#     model groups (see the separate LiteLLM-Huawei-MaaS-Proxy project). This
#     installer does not provision LiteLLM or decide which real models map to a/b.
set -euo pipefail

CLAUDE_ANOU_BIN_DIR="${CLAUDE_ANOU_BIN_DIR:-$HOME/.local/bin}"
CLAUDE_GLM_ENV_FILE="${CLAUDE_GLM_ENV_FILE:-$HOME/.config/claude-glm/env}"
CCR_CONFIG_DIR="${CCR_CONFIG_DIR:-$HOME/.claude-code-router}"
VERIFY="${VERIFY:-1}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER_SRC="$REPO_DIR/assets/claude-anou"
CLAUDE_ANOU_BIN="$CLAUDE_ANOU_BIN_DIR/claude-anou"

die() {
  echo "error: $*" >&2
  exit 1
}

# --- prerequisites ----------------------------------------------------------
command -v claude >/dev/null 2>&1 || die \
  "claude is required, but the Claude Code CLI is not installed or not in PATH. Install it first with: npm install -g @anthropic-ai/claude-code"

command -v ccr >/dev/null 2>&1 || die \
  "ccr is required. Run scripts/configure-claude-glm.sh first to install claude-code-router and the production CCR config."

[[ -f "$WRAPPER_SRC" ]] || die "archived wrapper not found: $WRAPPER_SRC"

if [[ ! -f "$CLAUDE_GLM_ENV_FILE" ]]; then
  die "claude-glm env not found at $CLAUDE_GLM_ENV_FILE. claude-anou reuses the claude-glm router env (HUAWEI_MAAS_API_KEY, LiteLLM keys). Run scripts/configure-claude-glm.sh first."
fi

# claude-anou depends on the CCR custom router exposing the "Anonymous-Model"
# branch and the anon-model-a/anon-model-b providers. These ship in
# assets/ccr/{custom-router.js,config.json} and are deployed by
# configure-claude-glm.sh / restore-ccr-config.sh. Warn (do not fail) if the
# live CCR state predates them.
router_js="$CCR_CONFIG_DIR/custom-router.js"
config_json="$CCR_CONFIG_DIR/config.json"
if [[ ! -f "$router_js" ]] || ! grep -q "Anonymous-Model" "$router_js" 2>/dev/null; then
  echo "warning: $router_js is missing the Anonymous-Model branch." >&2
  echo "warning: run scripts/restore-ccr-config.sh (or configure-claude-glm.sh) to deploy the archived custom router before using claude-anou." >&2
fi
if [[ ! -f "$config_json" ]] || ! grep -q "anon-model-a" "$config_json" 2>/dev/null; then
  echo "warning: $config_json does not list the anon-model-a/anon-model-b providers." >&2
  echo "warning: run scripts/restore-ccr-config.sh (or configure-claude-glm.sh) to deploy the archived 3-provider config before using claude-anou." >&2
fi

# --- install wrapper --------------------------------------------------------
mkdir -p "$CLAUDE_ANOU_BIN_DIR"
install -m 700 "$WRAPPER_SRC" "$CLAUDE_ANOU_BIN"
echo "installed claude-anou wrapper at $CLAUDE_ANOU_BIN"

# Seed the live routing signal so the first request has a defined assignment
# even before any project `.mt` file exists (the wrapper overwrites it per run).
mkdir -p "$CCR_CONFIG_DIR"
if [[ ! -f "$CCR_CONFIG_DIR/.session-model" ]]; then
  echo "a" > "$CCR_CONFIG_DIR/.session-model"
  echo "seeded $CCR_CONFIG_DIR/.session-model (assignment: a)"
fi

# --- make claude-anou discoverable (mirror claude-glm behavior) -------------
ensure_claude_anou_on_path() {
  hash -r 2>/dev/null || true
  if command -v claude-anou >/dev/null 2>&1; then
    return 0
  fi

  if [[ -d /usr/local/bin && -w /usr/local/bin ]]; then
    ln -sfn "$CLAUDE_ANOU_BIN" /usr/local/bin/claude-anou
    hash -r 2>/dev/null || true
    if command -v claude-anou >/dev/null 2>&1; then
      echo "installed claude-anou link in /usr/local/bin"
      return 0
    fi
  fi

  for shell_file in "$HOME/.bashrc" "$HOME/.profile"; do
    [[ -e "$shell_file" || "$shell_file" == "$HOME/.profile" ]] || continue
    touch "$shell_file" 2>/dev/null || continue
    if [[ -w "$shell_file" ]] && ! grep -q "user-local CLI wrappers such as claude-glm" "$shell_file"; then
      cat >> "$shell_file" <<'EOF'

# Add user-local CLI wrappers such as claude-glm.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
EOF
    fi
  done

  echo "warning: claude-anou was installed at $CLAUDE_ANOU_BIN, but this shell cannot find it yet." >&2
  echo "warning: open a new shell, run hash -r, or export PATH='$CLAUDE_ANOU_BIN_DIR:$PATH'." >&2
}

ensure_claude_anou_on_path

cat <<EOF

claude-anou installed (blind A/B model test).
  - shows model "Anonymous-Model"; never reveals anon-model-a vs anon-model-b
  - per-project binding: <project>/.mt holds "a" or "b" (random on first run)
  - run it from inside a project dir:  cd <project> && claude-anou
  - the plain 'claude' and 'claude-glm' commands are unchanged

Reveal the mapping only when the blind test is over: inspect <project>/.mt and
the anon-model-a/anon-model-b -> real-model mapping in your LiteLLM config.
EOF

if [[ "$VERIFY" == "1" ]]; then
  if command -v claude-anou >/dev/null 2>&1; then
    echo "verify: claude-anou resolves to $(command -v claude-anou)"
  else
    echo "verify: claude-anou not yet on PATH for this shell (see warning above)" >&2
  fi
fi
