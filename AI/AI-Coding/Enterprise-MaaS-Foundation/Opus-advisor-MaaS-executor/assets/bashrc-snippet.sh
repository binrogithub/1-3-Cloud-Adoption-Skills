# >>> forky-claude-routing >>>
# Claude Code launch modes:
# - `claude` stays on Claude.ai OAuth/connectors.
# - `claude-forky` routes through forky on :3458.
# - `claude-glm` keeps its own CCR route on :3456.
# Managed by the Opus-advisor-MaaS-executor skill — edit via scripts/configure-forky.sh, not by hand.
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac
export CLAUDE_CODE_DISABLE_MOUSE_CLICKS="${CLAUDE_CODE_DISABLE_MOUSE_CLICKS:-1}"
case ",${NO_PROXY:-}," in *,127.0.0.1,*) ;; *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;; esac
# <<< forky-claude-routing <<<
