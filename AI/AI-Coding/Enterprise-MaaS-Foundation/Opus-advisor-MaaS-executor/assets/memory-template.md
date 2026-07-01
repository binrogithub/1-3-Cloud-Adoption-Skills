---
name: forky-claude-routing
description: `claude-forky` is routed through forky (local :3458 systemd service) — execution turns go to GLM-5.2 via LiteLLM→Huawei MaaS, plan-mode and image turns go to Claude Opus via the user's OAuth subscription. Plain `claude` remains on Claude.ai OAuth/connectors.
metadata:
  type: reference
---

# forky claude routing

The `claude-forky` command is wired through **forky** (https://github.com/vladharl/forky),
a local Anthropic Messages API proxy on `127.0.0.1:3458` running as a systemd user service
(`forky.service`, linger enabled). Plain `claude` is intentionally left on Claude.ai
OAuth/connectors. Forky splits each `claude-forky` request:

| Turn type | Routes to | Reason |
|---|---|---|
| Normal execution (tools present) | GLM-5.2 via LiteLLM (`127.0.0.1:4000`) → Huawei MaaS | `execution` |
| Plan mode (`Shift+Tab`, detected via UserPromptSubmit hook + sentinel) | Claude Opus via OAuth | `sentinel` |
| `claude-opus-*` model requested | Claude Opus via OAuth | `opus` |
| Any request containing an image | Claude Opus via OAuth | `vision` |
| Tool-less classifier pings | Claude Sonnet via OAuth | `classifier` |

## Configuration

- **Repo**: `~/dev/forky` (branch `forky-vision-routing` carries the image-routing patch on top of upstream `main`)
- **Env**: `~/dev/forky/.env`
  - `EXEC_BASE_URL=http://127.0.0.1:4000/v1` (local LiteLLM)
  - `EXEC_API_KEY=<litellm key>` (gitignored secret)
  - `EXEC_MODEL=glm-5.2`
  - `FORKY_OPUS_MODEL=claude-opus-4-8` (plan/sentinel/review default; vision inherits it)
  - optional route overrides: `FORKY_PLAN_MODEL`, `FORKY_VISION_MODEL`, `FORKY_REVIEW_MODEL`
  - `PORT=3458`
- **OAuth source**: `~/.claude/.credentials.json` (populated by `claude /login`; forky reads it directly and refreshes tokens via `console.anthropic.com/v1/oauth/token`)
- **systemd unit**: `~/.config/systemd/user/forky.service` (log at `~/.forky/forky.log`)
- **Wrapper**: `~/.local/bin/claude-forky`
  - `ANTHROPIC_BASE_URL=http://127.0.0.1:3458`
  - `ANTHROPIC_MODEL=claude-sonnet-4-6`
  - unsets `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` so Claude.ai connectors stay enabled
  - `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` (MaaS GLM-5.2 hard input limit is ~196608 tokens; this leaves room for one 8K output + tool results before the proxy 400s)
  - `CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1` for copy/selection in fullscreen terminals
- **Shell env** (in `~/.bashrc`, between `>>> forky-claude-routing >>>` markers):
  - `NO_PROXY` includes `127.0.0.1,localhost`
  - no global `ANTHROPIC_*` gateway/auth vars
- **Hooks** (in `~/.claude/settings.json`):
  - `UserPromptSubmit` → `~/dev/forky/bin/forky-hook` (sets plan-mode sentinel)
  - `PostToolUse` matcher `ExitPlanMode` → same hook (clears sentinel)

## How to use

Run `claude-forky` in a new terminal. Plan mode (`Shift+Tab`) and images go to Opus; everything else goes to GLM-5.2. Run plain `claude` when Claude.ai connectors should be used without a custom gateway.

## Coexistence with claude-glm

`claude-glm` (the `claude-code-huawei-maas` skill) uses port `3456` and sets its own `ANTHROPIC_BASE_URL` inside the wrapper. Both can be installed simultaneously; plain `claude` stays clean.

## Manual controls

- Status / restart: `systemctl --user status forky` / `systemctl --user restart forky`
- Log: `tail -f ~/.forky/forky.log`
- Change OAuth Opus model: edit `FORKY_OPUS_MODEL` in `~/dev/forky/.env`, then `systemctl --user restart forky`
- Force Opus for 4h: `~/dev/forky/bin/forky-opus on` (cancel with `off`)
- Upgrade forky (preserve vision patch): `cd ~/dev/forky && git fetch && git checkout main && git pull && git checkout forky-vision-routing && git rebase main`

## Reinstall / teardown

Run the `Opus-advisor-MaaS-executor` skill scripts:
- `scripts/configure-forky.sh` — idempotent re-configure
- `scripts/uninstall-forky.sh` — full reversible teardown (service + .bashrc + hooks; asks before deleting repo + this memory file)

Related: [[qwen36-modelarts-serving]] for the MaaS serving recipe, [[host-149-transfer]] for the dev box.
