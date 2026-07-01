---
name: opus-advisor-maas-executor
description: Install and configure forky (github.com/vladharl/forky) end-to-end so `claude-forky` routes plan-mode + image turns to Claude Opus via the user's Pro/Max OAuth subscription while sending normal execution turns to Huawei Cloud MaaS (GLM-5.2) through an existing local LiteLLM proxy. Use when the user wants to keep their Opus advisor for design/planning and let GLM do cheap code execution, while preserving plain `claude` for Claude.ai OAuth connectors. Sets up forky as a systemd user service, applies local compatibility patches (vision routing and Claude Code system/developer message-role normalization), writes a `claude-forky` wrapper that uses ANTHROPIC_BASE_URL without ANTHROPIC_AUTH_TOKEN, adds copy-friendly mouse settings, trusts `/root` when requested so local permissions are honored, and merges plan-mode hooks into `~/.claude/settings.json`. Assumes LiteLLM is already running on :4000 and that the user has logged into Claude Code (`claude /login`) so OAuth credentials exist.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# Opus-advisor-MaaS-executor

## Overview

This skill installs **forky** (https://github.com/vladharl/forky) and adds a `claude-forky` command that splits traffic between two backends while keeping plain `claude` on Claude.ai OAuth/connectors:

| User action | Routes to | Why |
|---|---|---|
| Normal coding / tool calls | **GLM-5.2** via LiteLLM → Huawei MaaS | Cheap execution |
| `Shift+Tab` plan mode | **Claude Opus** via user's OAuth subscription | Quality reasoning |
| Any request containing an image | **Claude Opus** via OAuth | GLM-5.2 has no vision |
| Tool-less classifier pings | **Claude Sonnet** via OAuth | Forky's built-in safety heuristic |

The chain is:

```
claude-forky ──ANTHROPIC_BASE_URL=http://127.0.0.1:3458──► forky ──┬──► api.anthropic.com (OAuth, Pro/Max)
                                                                    │
                                                                    └──► http://127.0.0.1:4000/v1 (LiteLLM)
                                                                             ──► Huawei MaaS glm-5.2
```

Plain `claude` keeps Claude.ai connectors. `claude-glm` keeps working unchanged on CCR port `:3456`.

## Prerequisites (the skill checks all of them)

1. **LiteLLM running on `127.0.0.1:4000`** with a `glm-5.2` model alias and a working API key. Provisioned by the separate `LiteLLM-Huawei-MaaS-Proxy` / `claude-code-huawei-maas` skill — this skill **assumes** it, fails fast if absent.
2. **`bun >= 1.3`** in PATH (forky's runtime).
3. **`git`** in PATH.
4. **`claude` CLI** installed (`npm install -g @anthropic-ai/claude-code` if missing).
5. **User logged into Claude Code** via `claude /login` so `~/.claude/.credentials.json` exists with a valid OAuth token. Forky reads this directly — the OAuth path silently fails without it.
6. **Pro or Max subscription** on the OAuth account (Opus access).
7. **Port `3458` free** (forky's default; the skill detects conflicts).
8. **Systemd user services available** (`systemctl --user is-system-running` returns anything but `offline`). Falls back to a manual launcher if not.

## Quick Path

```bash
# 1. (one-time, by user) make sure Claude Code is logged in for OAuth
claude /login

# 2. confirm the litellm key + model
export LITELLM_CCR_KEY="sk-..."          # or whatever the local LiteLLM uses
export FORKY_EXEC_MODEL="glm-5.2"        # optional override
export FORKY_OPUS_MODEL="claude-opus-4-8" # optional OAuth Opus model override

# 3. run the installer (clones, branches, builds vision patch)
~/.claude/skills/Opus-advisor-MaaS-executor/scripts/install-forky.sh

# 4. configure: writes .env, systemd unit, claude-forky wrapper, .bashrc helper block, settings.json hooks, memory
~/.claude/skills/Opus-advisor-MaaS-executor/scripts/configure-forky.sh

# 5. verify (text → GLM, image → Opus, hook toggles sentinel, LiteLLM DB confirms)
~/.claude/skills/Opus-advisor-MaaS-executor/scripts/verify-forky.sh

# 6. open a new terminal and run:
claude-forky
```

To revert everything:

```bash
~/.claude/skills/Opus-advisor-MaaS-executor/scripts/uninstall-forky.sh
```

## What the scripts do (and why each step is necessary)

### `install-forky.sh`
- Verifies `bun`, `git`, `claude`, and `curl` are present. Errors with install hints if not.
- Clones `https://github.com/vladharl/forky` to `~/dev/forky` (idempotent: pulls if already there, but only on a clean tree).
- Runs `bun install` to populate `node_modules`.
- Creates a local branch **`forky-vision-routing`** off `main` and commits local patches:
  - `src/route.ts`: `hasImageContent()` + `vision` routing so image requests go to Opus.
  - `src/server.ts`: normalize Claude Code `system`/`developer` roles inside `messages` into the top-level `system` field before validation. Without this, Claude Code 2.1.x can fail with `400 request shape invalid ... messages[1].role`.
- Checks out `forky-vision-routing` as the active branch (this is what the service runs).

### `configure-forky.sh`
- **Probes LiteLLM** at `http://127.0.0.1:4000/v1/models` with the provided key. If the request fails or `glm-5.2` is missing from `/v1/models`, errors out with a pointer to the `claude-code-huawei-maas` skill. Then sends a real `/v1/chat/completions` ping to confirm the model actually serves (it can be listed but unreachable — that exact gotcha bit us with `glm-5.1`).
- **Verifies OAuth creds** exist at `~/.claude/.credentials.json`. If missing or malformed, prints the `claude /login` hint and exits.
- Writes `~/dev/forky/.env` with `EXEC_BASE_URL`, `EXEC_API_KEY`, `EXEC_MODEL`, `FORKY_OPUS_MODEL`, and `PORT=3458` (gitignored by forky's `.gitignore`). `FORKY_OPUS_MODEL` defaults to `claude-opus-4-8`; plan, vision, and review routes inherit it unless optional route-specific overrides (`FORKY_PLAN_MODEL`, `FORKY_VISION_MODEL`, `FORKY_REVIEW_MODEL`) are set before configuration.
- **Detects port `3458` conflicts**. If something else owns it, prompts to change `FORKY_PORT` or stop the other process.
- Installs `~/.config/systemd/user/forky.service`, enables it, enables `loginctl enable-linger` so it survives reboot + logout, starts it, waits for `server.start` in the log.
- Writes `~/.local/bin/claude-forky`. The wrapper sets `ANTHROPIC_BASE_URL=http://127.0.0.1:3458`, `ANTHROPIC_MODEL=claude-sonnet-4-6`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000`, and `CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1`, then explicitly unsets `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` so Claude.ai MCP connectors stay enabled.
- **Idempotent `.bashrc` block** between `# >>> forky-claude-routing >>>` / `# <<< forky-claude-routing <<<` markers — rewrites if present, appends if not. It does not route plain `claude`; it only sets copy-friendly mouse behavior and `NO_PROXY`.
- Sets `projects["/root"].hasTrustDialogAccepted=true` in `~/.claude.json` by default (`FORKY_TRUST_ROOT_WORKSPACE=0` to skip) so `/root/.claude/settings.local.json` permission allows are honored and the trust warning disappears.
- **Merges hooks** into `~/.claude/settings.json` (uses `jq` if present, else a small python fallback). Adds `UserPromptSubmit` + `PostToolUse`/ExitPlanMode entries pointing at `~/dev/forky/bin/forky-hook`. Preserves all other settings; idempotent on re-run.
- Saves an **auto-memory entry** to `~/.claude/projects/-root/memory/forky-claude-routing.md` and indexes it in `MEMORY.md` (skipped if memory dir absent).
- Restarts the systemd unit so `.env` changes take effect.

### `verify-forky.sh`
- Confirms a **fresh login shell** has no global `ANTHROPIC_*` gateway/auth vars, and that `claude-forky` carries the scoped forky env.
- Confirms `forky.service` is `active`, `:3458` is owned by forky.
- Sends three requests:
  1. **Text + tools** (mimics real Claude Code) → expects `routedVia: execution` → `aistack` → LiteLLM logs `openai/glm-5.2`.
  2. **Image + tools** (real 8×8 PNG, generated inline) → expects `routedVia: vision` → configured `FORKY_VISION_MODEL` / `FORKY_OPUS_MODEL`.
  3. **Plan-mode hook simulation** (pipe payload to `forky-hook`) → expects `~/.forky/opus` sentinel to appear and clear.
- Cross-checks the LiteLLM Postgres spend log for `openai/glm-5.2` rows in the test window (independent confirmation beyond forky's own logs).
- Optionally spawns a real `claude -p` subprocess and times one round-trip end-to-end.

### `uninstall-forky.sh`
- Stops + disables + removes `forky.service` (and `loginctl disable-linger` if no other services need it).
- Strips the `.bashrc` block by markers.
- Removes the two hook entries from `~/.claude/settings.json` (preserves everything else).
- Asks before deleting `~/dev/forky` and the memory file (those may have customizations).
- Does NOT touch LiteLLM, OAuth credentials, or the `claude-glm` setup.

## Manual controls after install

| What | Command |
|---|---|
| Service status | `systemctl --user status forky` |
| Restart after `.env` change | `systemctl --user restart forky` |
| Live log | `tail -f ~/.forky/forky.log` |
| Change OAuth Opus model | edit `FORKY_OPUS_MODEL` in `~/dev/forky/.env`, then restart |
| Force Opus for next 4h (override routing) | `~/dev/forky/bin/forky-opus on` |
| Cancel force-Opus | `~/dev/forky/bin/forky-opus off` |
| Show current routing mode | `~/dev/forky/bin/forky-opus status` |
| Upgrade forky (preserve vision patch) | `cd ~/dev/forky && git fetch && git checkout main && git pull && git checkout forky-vision-routing && git rebase main` |

## Verification

```bash
# 1. fresh-shell env must NOT globally route plain claude
bash -lic 'env | grep -E "^(ANTHROPIC_BASE_URL|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY)=" || true'

# 2. service alive
systemctl --user is-active forky

# 3. real claude-forky proves end-to-end (run in a NEW terminal)
claude-forky -p "Create /tmp/x.py that prints hi, then run it with python3."

# 4. the model that actually served the work — LiteLLM's own DB
docker exec litellm_pg_db psql -U llmproxy -d litellm -t -A -F'|' \
  -c "select to_char(\"startTime\",'HH24:MI:SS'), model from \"LiteLLM_SpendLogs\" order by \"startTime\" desc limit 5;"
# expect: openai/glm-5.2 rows in the request window
```

## Troubleshooting

- **`bun: command not found`**: install via `curl -fsSL https://bun.sh/install | bash`, then re-source `~/.bashrc`.
- **`Could not read OAuth credentials at ~/.claude/.credentials.json`**: run `claude /login` first; if already logged in but credentials are missing, run `claude setup-token`. Plan mode and vision will be broken without OAuth — exec-only mode is not supported by this skill.
- **`Port 3458 already in use`**: another process owns it. Either stop it, or set `FORKY_PORT=3459` before running `configure-forky.sh` (the script also updates the `.env`, the systemd unit, and the `.bashrc` block).
- **`LiteLLM /v1/models returned HTTP 401`**: wrong `LITELLM_CCR_KEY`. Check `/root/LiteLLM/.env` or your shell.
- **`glm-5.2 is listed but a real chat/completions call returns 400`**: the model is declared in LiteLLM but its `litellm_params.model` or `api_base` is wrong, or the MaaS quota is exhausted. Use the `claude-code-huawei-maas` skill's recovery scripts. This skill will not silently fall back to a different model — it surfaces the error.
- **Plain `claude` still uses Anthropic directly**: expected. Use `claude-forky` for hybrid routing.
- **`claude-forky` shows `claude.ai connectors are disabled...`**: wrong. Check `~/.local/bin/claude-forky` unsets `ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY`, and check your shell/IDE did not inject those variables. Claude Code disables connectors when auth-token/API-key env vars are present.
- **`400 request shape invalid ... messages[1].role`**: forky is missing the server role-normalization patch. Re-run `install-forky.sh`, confirm `grep request.normalized_roles ~/dev/forky/src/server.ts`, then `systemctl --user restart forky`.
- **`Ignoring ... permissions.allow entries ... workspace has not been trusted`**: set `/root` trusted in `~/.claude.json`, or re-run `configure-forky.sh`. The script backs up `~/.claude.json` before setting `projects["/root"].hasTrustDialogAccepted=true`.
- **Cannot copy text in Claude Code fullscreen over SSH**: this skill sets `CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1`. If selection still fails, start with `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1 claude-forky`.
- **Plan mode doesn't route to Opus**: check `~/.forky/hook.log` for `UserPromptSubmit` events. The hook only fires if `~/.claude/settings.json` has the `hooks.UserPromptSubmit` entry — re-run `configure-forky.sh` if missing. Also check `~/.forky/opus` sentinel toggling.
- **Image request fails with `Could not process image`**: usually a malformed test image, not forky. Try a real PNG (e.g. a screenshot). 1×1 placeholder PNGs are rejected by Anthropic.
- **Need a different Opus model**: set `FORKY_OPUS_MODEL` in `~/dev/forky/.env`, then `systemctl --user restart forky`. Use `FORKY_PLAN_MODEL`, `FORKY_VISION_MODEL`, or `FORKY_REVIEW_MODEL` only when that route should use a different OAuth model.
- **Long sessions overflow at ~196k tokens**: `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` must be in env. `bash -lic 'echo $CLAUDE_CODE_AUTO_COMPACT_WINDOW'` should print `180000`. If 0/empty, re-run `configure-forky.sh`.
- **Upstream `git pull` lost vision routing**: you switched to `main` and pulled without re-merging. Run `cd ~/dev/forky && git checkout forky-vision-routing && git rebase main` to restore the patch on top of latest.
- **`claude-glm` (the other skill) broke after this install**: it shouldn't — they don't share ports (3458 vs 3456) or wrappers. If `claude-glm` now behaves like forky, something else set `ANTHROPIC_BASE_URL` globally to forky's port; check the script's `.bashrc` block didn't break the `claude-glm` wrapper's own export.
- **OAuth creds structure**: `~/.claude/.credentials.json` uses `.claudeAiOauth.accessToken` (not `.accessToken` at top level). The configure script checks this. If you see "no OAuth token", run `claude /login` and verify with `jq '.claudeAiOauth.accessToken' ~/.claude/.credentials.json`.
- **Vision patch not on upstream `main`**: as of 2026-06, upstream may not have the `hasImageContent()` / `vision` routing branch. `install-forky.sh` detects this and applies the patch automatically via `apply-vision-patch.py`. If it fails, apply the changes from `assets/route-vision.patch` by hand.

## Coexistence with `claude-code-huawei-maas`

| | This skill (forky) | claude-code-huawei-maas (ccr) |
|---|---|---|
| Port | 3458 | 3456 |
| Command | `claude-forky` | `claude-glm` |
| Backend choice | OAuth (plan/vision) **+** GLM (exec) | GLM only |
| Model alias trick | none — sends Anthropic format, translates internally | uses `claude-opus-4-6` alias on LiteLLM |
| When to use | want Opus advisor & GLM executor in one command | want a dedicated GLM-only command |

Both can be installed side by side. Plain `claude` remains available for Claude.ai OAuth/connectors.

## Example: multi-agent workflow with forky → GLM-5.2

A Claude Code workflow can dispatch work to GLM-5.2 via forky instead of using Claude for every step. The orchestrator agents run on Claude, but each agent calls forky's API with `curl`, and forky routes the request to GLM-5.2 for execution.

### Architecture

```
Workflow orchestrator (Claude or claude-forky)
  ├── agent-a (quicksort)      ──curl──► forky :3458 ──► GLM-5.2
  ├── agent-b (binary search)  ──curl──► forky :3458 ──► GLM-5.2
  ├── agent-c (BFS)            ──curl──► forky :3458 ──► GLM-5.2
  └── synthesizer              ──curl──► forky :3458 ──► GLM-5.2
```

### How each agent calls forky

```bash
curl -s http://127.0.0.1:3458/v1/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 512,
    "tools": [{"name":"Bash","description":"run bash","input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}],
    "messages": [{"role":"user","content":"Write a Python quicksort function. Return only the code."}]
  }'
```

Forky sees `claude-sonnet-4-6` + tools → routes to `execution → aistack → GLM-5.2`. The agent gets back a normal Anthropic Messages response and never knows it wasn't Claude.

### Real run result (2026-06-30)

4 agents (3 fan-out + 1 synthesizer), 380s duration:

| Agent | Task | Code generated |
|---|---|---|
| agent-a | quicksort | 287 chars — `def quicksort(arr): if len(arr) <= 1: return arr...` |
| agent-b | binary search | 303 chars — `def binary_search(arr, target): low = 0; high = len(arr) - 1...` |
| agent-c | BFS | 399 chars — `from collections import deque; def bfs(adj, start): visited = set(...)` |
| synthesizer | combine all 3 + tests | 3776 chars — combined module |

**161 forky requests, all routed `execution → aistack` (GLM-5.2). Zero execution calls to Claude/Opus.** LiteLLM DB confirmed `openai/glm-5.2` served all work (863K input + 9.5K output tokens).

The `classifier → anthropic-oauth` calls (tool-less pings) are forky's built-in safety heuristic — they go to OAuth Sonnet. To avoid them, always include a `tools` array in the request so forky routes to execution.

### Key takeaway

The workflow orchestrator (Claude) plans and dispatches; GLM-5.2 does all the code generation. Forky is the transparent bridge — same Anthropic Messages API format, different backend. This lets you run multi-agent workflows with cheap execution while reserving Claude/Opus for orchestration and review.

## Resources

- `scripts/install-forky.sh` — clones forky, applies vision-routing branch.
- `scripts/configure-forky.sh` — probes LiteLLM + OAuth, writes config, installs service, updates `.bashrc` + `settings.json` + memory.
- `scripts/verify-forky.sh` — end-to-end checks with independent LiteLLM-side confirmation.
- `scripts/uninstall-forky.sh` — reversible teardown.
- `assets/forky.service` — systemd user unit template.
- `assets/bashrc-snippet.sh` — the env block written into `~/.bashrc`.
- `assets/route-vision.patch` — the vision-routing patch applied to forky's `src/route.ts`.
- `assets/memory-template.md` — auto-memory file template.
- `references/how-it-works.md` — architecture deep-dive (the request lifecycle, how OAuth is injected, how the hook detects plan mode).
