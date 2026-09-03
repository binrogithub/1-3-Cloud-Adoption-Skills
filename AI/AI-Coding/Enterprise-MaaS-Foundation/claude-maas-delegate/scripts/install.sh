#!/usr/bin/env bash
# User-facing installer for universal Claude-MaaS execution delegation.
set -euo pipefail

api_url=""
model="glm-5.2"
agents="codex,copilot,cursor,opencode"
non_interactive="no"
no_install_claude="no"
force="no"

die() { printf '%s\n' "install: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) [[ $# -ge 2 ]] || die "--api-url requires a value"; api_url="$2"; shift 2 ;;
    --api-url=*) api_url="${1#--api-url=}"; shift ;;
    --model) [[ $# -ge 2 ]] || die "--model requires a value"; model="$2"; shift 2 ;;
    --model=*) model="${1#--model=}"; shift ;;
    --agents) [[ $# -ge 2 ]] || die "--agents requires a value"; agents="$2"; shift 2 ;;
    --agents=*) agents="${1#--agents=}"; shift ;;
    --non-interactive) non_interactive="yes"; shift ;;
    --no-install-claude) no_install_claude="yes"; shift ;;
    --skip-live-verify) shift ;;
    --force) force="yes"; shift ;;
    --help|-h)
      cat <<'USAGE'
Usage: scripts/install.sh [options]

Prompts for an Anthropic-compatible API URL and a hidden one-line API key.
With --non-interactive, provide the key as exactly one line on stdin.

  --api-url URL            Anthropic-compatible Messages endpoint or base URL
  --model MODEL            MaaS model (default: glm-5.2)
  --agents LIST            codex,copilot,cursor,opencode (default: all)
  --non-interactive        Require --api-url and read the key from stdin
  --no-install-claude      Fail instead of installing missing Claude Code
  --skip-live-verify       Accepted for offline automation
  --force                  Replace owned installation files
USAGE
      exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

if [[ -z "$api_url" && "$non_interactive" == "no" ]]; then
  read -r -p "Anthropic-compatible API URL: " api_url
fi
[[ -n "$api_url" ]] || die "--api-url is required in non-interactive mode"
# Providers commonly expose the full Messages endpoint; launcher config needs
# the base URL and appends its own API route.
api_url="${api_url%/}"
api_url="${api_url%/v1/messages}"
[[ "$api_url" == https://* || "$api_url" == http://localhost* || "$api_url" == http://127.0.0.1* ]] || die "API URL must use HTTPS (localhost is allowed for tests)"

if ! command -v claude >/dev/null 2>&1; then
  [[ "$no_install_claude" == "no" ]] || die "Claude Code is missing and --no-install-claude was given"
  if [[ -n "${CLAUDE_INSTALLER:-}" ]]; then
    bash "$CLAUDE_INSTALLER"
  else
    curl -fsSL https://claude.ai/install.sh | bash
  fi
  command -v claude >/dev/null 2>&1 || die "Claude Code installation did not add 'claude' to PATH"
fi
claude --version >/dev/null 2>&1 || die "Claude Code is not runnable"

if [[ "$non_interactive" == "no" && -t 0 ]]; then
  read -r -s -p "Anthropic-compatible API key: " api_key
  printf '\n' >&2
else
  IFS= read -r api_key || true
fi
[[ "$api_key" =~ [^[:space:]] ]] || die "API key must not be empty"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

# Resolve the Skill source from either the development repository layout or
# the self-contained Skill-root layout. Both modes share this one resolver.
if [[ -f "$repo_root/skills/claude-maas-delegate/SKILL.md" ]]; then
  skill_source="$repo_root/skills/claude-maas-delegate"
elif [[ -f "$repo_root/SKILL.md" && -f "$repo_root/references/routing-policy.md" ]]; then
  skill_source="$repo_root"
else
  die "cannot locate Skill source (expected repo layout or Skill-root layout)"
fi

setup_args=(--base-url "$api_url" --model "$model")
[[ "$force" == "yes" ]] && setup_args+=(--force)
printf '%s\n' "$api_key" | bash "$repo_root/client/claude-maas-setup.sh" "${setup_args[@]}"
unset api_key

manifest="${HOME}/.config/claude-maas/agent-adapters-manifest.json"
adapter_args=(install --agents "$agents" --skill-source "$skill_source" --manifest "$manifest")
[[ "$force" == "yes" ]] && adapter_args+=(--force)
python3 "$repo_root/scripts/configure-agents.py" "${adapter_args[@]}"
PATH="$HOME/.local/bin:$PATH" "$HOME/.local/bin/maas-delegate" doctor >/dev/null || die "installed maas-delegate is not runnable"
printf '%s\n' "install: Claude-MaaS delegation is configured for $agents"
