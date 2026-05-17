---
name: claude-code-huawei-maas
description: Configure Claude Code to use Huawei Cloud MaaS or ModelArts MaaS through an OpenAI-compatible endpoint, and optionally add Z.ai web-search-prime MCP search. Use when Codex needs to add a side-by-side claude-glm command that routes to Huawei MaaS glm-5.1 while preserving the original claude command on Anthropic, migrate claude itself to Huawei MaaS, install or configure claude-code-router, set API_KEY-based authentication, adjust context length, verify that Claude Code is actually backed by MaaS, or configure Z.ai MCP search with Z_API_KEY.
---

# Claude Code Huawei MaaS

## Overview

Use this skill to route Claude Code through `claude-code-router` (`ccr`) to Huawei Cloud MaaS OpenAI-compatible chat completions. The preferred setup is side-by-side: keep the original `claude` command on Anthropic and add `claude-glm`/`Claude-glm` for Huawei MaaS `glm-5.1`. A legacy migration script is also available if the user explicitly wants `claude` itself to route to MaaS. It can also add the Z.ai `web-search-prime` MCP search tool for Claude Code.

## Quick Path

1. Confirm the user has a MaaS OpenAI-compatible base URL, model name, and API key environment variable.
2. If the user wants to preserve the original Claude Code command, run `scripts/configure-claude-glm.sh` from this skill. Defaults match the tested setup:
   - base URL: `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
   - model: `glm-5.1`
   - context tokens: `120000`
   - max output tokens: `8192`
3. Verify both the router and Claude Code:
   - `ccr status`
   - `systemctl --user status claude-glm-ccr.service --no-pager` when systemd user services are available
   - `claude-glm --bare --print --output-format json 'Reply with OK only'`
   - `claude --version` still resolves to the original Claude Code install and is not wrapped by this path.
4. If the user has already hit MaaS context overflow or Claude Code resume failure, use the bundled recovery helper:
   - `claude-glm-recover <session-id>`
   - `claude-glm-recover <session-id> --launch`
   - then paste `/tmp/claude-glm-recovery-<session-id>.md` into the fresh session as the first prompt
5. If the user also wants Z.ai search MCP, confirm they have a Z.ai account and API key, export it as `Z_API_KEY`, then run `scripts/configure-zai-search-mcp.sh`.

Example:

```bash
export API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-claude-glm.sh
```

The side-by-side script accepts `HUAWEI_MAAS_API_KEY`, `MAAS_API_KEY`, or `API_KEY` and stores it in `~/.config/claude-glm/env` with `0600` permissions so only `claude-glm` uses it.

If the user explicitly wants to replace `claude` with a MaaS-backed wrapper:

```bash
export API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure.sh
```

Override defaults when needed:

```bash
MAAS_BASE_URL='https://api-ap-southeast-1.modelarts-maas.com/openai/v1' \
MAAS_MODEL='glm-5.1' \
MAAS_CONTEXT_TOKENS=120000 \
MAAS_MAX_OUTPUT_TOKENS=8192 \
/root/.codex/skills/claude-code-huawei-maas/scripts/configure.sh
```

Add Z.ai search MCP:

```bash
export Z_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-zai-search-mcp.sh
```

## Side-By-Side Claude-GLM

`scripts/configure-claude-glm.sh` is the preferred path when the user wants `claude` to keep using Anthropic Claude models and `claude-glm` to use Huawei MaaS.

- Installs `@musistudio/claude-code-router` globally with npm if `ccr` is missing.
- Writes `~/.claude-code-router/config.json` with a provider named `huawei-maas`.
- Uses `api_key: "$HUAWEI_MAAS_API_KEY"` in router config.
- Stores the actual MaaS key in `~/.config/claude-glm/env` with `0600` permissions.
- Sets the provider URL to `${MAAS_BASE_URL}/chat/completions`.
- Routes `default`, `background`, `think`, and `longContext` to `huawei-maas,<model>`.
- Creates `~/.local/bin/claude-glm` and a compatibility symlink `~/.local/bin/Claude-glm`.
- Installs `~/.local/bin/claude-glm-recover` for post-overflow recovery into a fresh session.
- Creates `~/.local/bin/claude-glm-ccr-run` and `~/.local/bin/claude-glm-ccr-health` when systemd user services are available.
- Installs `~/.config/systemd/user/claude-glm-ccr.service`, `claude-glm-ccr-health.service`, and `claude-glm-ccr-health.timer` by default when `systemctl --user` works.
- Leaves the existing `claude` command untouched.
- Exports these defaults only inside the `claude-glm` wrapper:
  - `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`
  - `ANTHROPIC_AUTH_TOKEN=claude-glm-local`
  - `ANTHROPIC_MODEL=<model>`
  - `ANTHROPIC_CUSTOM_MODEL_OPTION=<model>`
  - `CLAUDE_CODE_MAX_CONTEXT_TOKENS=<context>`
- Starts `ccr` in the background when needed, validates the router with a real `http://127.0.0.1:3456/` health check instead of trusting only the pid/status file, and runs the real `claude` command with `--model <model>` unless the user already passed `--model` or invoked a Claude Code management subcommand.
- If `ccr status` is stale or the router socket is closed, stops `ccr`, waits briefly for the old process/port to release, then waits up to 30 seconds for the restarted router to become healthy.
- Keeps `ccr` resident through a systemd user service when supported, enables a 60-second health timer that restarts the service on failed status/socket checks, and best-effort enables user lingering with `loginctl enable-linger`.
- Restarts `ccr` and validates a small request through `claude-glm`.

Set `INSTALL_SYSTEMD_USER_SERVICE=0` before running `scripts/configure-claude-glm.sh` if the user wants wrapper-only startup and no systemd user units.

`scripts/configure.sh` is the legacy migration path. It wraps the current `claude` command and preserves the original binary as `<claude-path>.real`.

## Recovery Workflow

Use this when the user reports one of these patterns:

- `prompt length ... must less than the maximum input length ...`
- repeated `/compact` failure
- `--resume` or `/resume` no longer restores usable context
- a long `claude-glm` session has become too large to continue safely

Preferred recovery flow:

1. Find the failed session id from the terminal history or `~/.claude-glm-config/history.jsonl`.
2. Run:

```bash
claude-glm-recover <session-id>
```

3. Open a fresh `claude-glm` session:

```bash
cd <original-project-dir>
claude-glm
```

4. Paste the generated recovery file:

```bash
cat /tmp/claude-glm-recovery-<session-id>.md
```

Or let the helper open the fresh session for you:

```bash
claude-glm-recover <session-id> --launch
```

Important limits:

- The helper does not repair the old session in place.
- The helper does not use `--resume`.
- On root/sudo environments, Claude Code often blocks interactive first-prompt injection, so the reliable recovery path is still a fresh session plus a pasted recovery pack.

## Manual Configuration

Use this if the script cannot be run or if the user wants to review each step.

1. Install CCR:

```bash
npm install -g @musistudio/claude-code-router
```

2. Write `~/.claude-code-router/config.json`:

```json
{
  "LOG": true,
  "LOG_LEVEL": "info",
  "API_TIMEOUT_MS": 600000,
  "NON_INTERACTIVE_MODE": false,
  "Providers": [
    {
      "name": "huawei-maas",
      "api_base_url": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions",
      "api_key": "$API_KEY",
      "models": ["glm-5.1"],
      "transformer": {
        "use": [
          ["maxtoken", { "max_tokens": 8192 }],
          "cleancache",
          "enhancetool"
        ]
      }
    }
  ],
  "Router": {
    "default": "huawei-maas,glm-5.1",
    "background": "huawei-maas,glm-5.1",
    "think": "huawei-maas,glm-5.1",
    "longContext": "huawei-maas,glm-5.1",
    "longContextThreshold": 120000
  }
}
```

3. Start or restart CCR:

```bash
ccr restart
```

For persistent `ccr` startup on systemd user environments, install units equivalent to the script-generated service:

```bash
systemctl --user enable --now claude-glm-ccr.service claude-glm-ccr-health.timer
loginctl enable-linger "$USER"
```

Verify the resident router:

```bash
systemctl --user status claude-glm-ccr.service --no-pager
systemctl --user list-timers claude-glm-ccr-health.timer --no-pager
curl -fsS -H "Authorization: Bearer ${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}" http://127.0.0.1:3456/
```

4. Make `claude-glm` use the router while preserving `claude`:

```bash
mkdir -p ~/.config/claude-glm ~/.local/bin
chmod 700 ~/.config/claude-glm ~/.local/bin
cat > ~/.config/claude-glm/env <<'EOF'
export HUAWEI_MAAS_API_KEY='replace-with-your-maas-api-key'
export CLAUDE_GLM_ROUTER_KEY='claude-glm-local'
EOF
chmod 600 ~/.config/claude-glm/env
```

Then create `~/.local/bin/claude-glm`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/.config/claude-glm/env"
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$CLAUDE_GLM_ROUTER_KEY}"
export ANTHROPIC_BASE_URL=http://127.0.0.1:3456
case ",${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;;
esac
export ANTHROPIC_MODEL=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION='Huawei Cloud MaaS glm-5.1'
export CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000
unset CLAUDE_CODE_USE_BEDROCK

ccr_healthy() {
  ccr status 2>/dev/null | grep -q "Status: Running" &&
    curl -fsS -m 2 \
      -H "Authorization: Bearer $ANTHROPIC_AUTH_TOKEN" \
      "$ANTHROPIC_BASE_URL/" >/dev/null 2>&1
}

wait_for_ccr_stop() {
  for _ in {1..20}; do
    if ! ccr status 2>/dev/null | grep -q "Status: Running"; then
      return 0
    fi
    sleep 0.25
  done
}

start_ccr() {
  ccr_log="${CLAUDE_GLM_CCR_LOG:-/tmp/claude-glm-ccr.log}"
  if command -v setsid >/dev/null 2>&1; then
    setsid ccr start > "$ccr_log" 2>&1 < /dev/null &
  else
    nohup ccr start > "$ccr_log" 2>&1 < /dev/null &
  fi

  for _ in {1..60}; do
    ccr_healthy && break
    sleep 0.5
  done

  if ! ccr_healthy; then
    echo "ccr failed to start; see $ccr_log" >&2
    ccr status >&2 || true
    exit 1
  fi
}

if ! ccr_healthy; then
  ccr stop >/dev/null 2>&1 || true
  wait_for_ccr_stop
  start_ccr
fi
exec claude --model "$ANTHROPIC_MODEL" "$@"
```

## Z.ai Web Search MCP

Use this when the user wants Claude Code to have the Z.ai `web-search-prime` MCP search tool, exposed as `mcp__web-search-prime__web_search_prime`.

Prerequisites:

- The user has a Z.ai account.
- The user has created a Z.ai API key.
- The key is available in the shell as `Z_API_KEY`.

Do not write the raw Z.ai API key into Claude config. Store it in the environment and configure Claude Code to build the MCP `Authorization` header at runtime.

Preferred setup:

```bash
export Z_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-zai-search-mcp.sh
```

Manual user-scope config in `~/.claude.json`:

```json
{
  "mcpServers": {
    "web-search-prime": {
      "type": "http",
      "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
      "headersHelper": "python3 -c 'import json, os; print(json.dumps({\"Authorization\": \"Bearer \" + os.environ[\"Z_API_KEY\"]}))'"
    }
  }
}
```

The helper produces this HTTP header when Claude Code starts the MCP connection:

```text
Authorization: Bearer <Z_API_KEY>
```

## Verification

Prefer a non-interactive JSON check because it reports actual `modelUsage`:

```bash
claude-glm --bare --print --output-format json 'Reply with OK only'
```

Successful output should include:

```json
"modelUsage": {
  "glm-5.1": {
    "contextWindow": 120000
  }
}
```

If `claude-glm` still says Sonnet/Opus, check whether the user launched an old shell or old session. The wrapper must export `ANTHROPIC_MODEL` and `ANTHROPIC_CUSTOM_MODEL_OPTION` and pass `--model "$ANTHROPIC_MODEL"` to `claude`; then restart the interactive `claude-glm` process. If plain `claude` says Sonnet/Opus, that is expected in side-by-side mode.

For Z.ai MCP search, verify the MCP connection:

```bash
claude mcp get web-search-prime
```

Successful output should show `Status: ✓ Connected`. If it is connected, Claude Code can call `mcp__web-search-prime__web_search_prime`.

## Troubleshooting

- **`Not logged in` from `claude-glm`**: Claude was started without router environment variables. Use the wrapper, `ccr code`, or export `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`.
- **Plain `claude` still uses Claude/Sonnet/Opus**: Expected in side-by-side mode. Use `claude-glm` for Huawei MaaS.
- **`claude-glm` interactive mode shows Sonnet/Opus but JSON shows `glm-5.1`**: Ensure the wrapper invokes `claude --model "$ANTHROPIC_MODEL"` instead of only `ccr code`.
- **`HUAWEI_MAAS_API_KEY, MAAS_API_KEY, or API_KEY is not set`**: Export one of those variables before running `configure-claude-glm.sh`.
- **`API_KEY is not set` from legacy configure**: Export `API_KEY` before `ccr start` or before launching `claude`; the legacy config intentionally references `$API_KEY`.
- **`claude-glm` hangs before Claude Code starts**: Check the generated wrapper. It must not run foreground `ccr start >/dev/null`; it should background `ccr start`, then wait until `ccr status` includes `Status: Running`.
- **`Unable to connect to API (FailedToOpenSocket)` or `ConnectionRefused` against `http://127.0.0.1:3456/v1/messages?beta=true`**: Treat this as a local router/socket problem first, not a MaaS key problem. Check `ccr status`, `ss -ltnp | grep ':3456'`, and `curl -fsS -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" http://127.0.0.1:3456/`. If status says running but curl fails, stop and restart `ccr`; the side-by-side wrapper should do this automatically.
- **`ccr failed to start; see /tmp/claude-glm-ccr.log` after an automatic restart**: This can be a stop/start race where the old router process or port has not fully released. Use the current wrapper logic that waits for `ccr stop`, then waits up to 30 seconds for a real router health check. Inspect `/tmp/claude-glm-ccr.log` and `ccr status` if it still fails.
- **Persistent `ccr` did not start after reboot/login**: Check `systemctl --user is-enabled claude-glm-ccr.service claude-glm-ccr-health.timer`, `systemctl --user status claude-glm-ccr.service --no-pager`, and `loginctl show-user "$USER" -p Linger`. On systems without a running user systemd manager, run with `INSTALL_SYSTEMD_USER_SERVICE=0` and rely on wrapper startup instead.
- **Health timer keeps restarting `ccr`**: Check `journalctl --user -u claude-glm-ccr.service -u claude-glm-ccr-health.service --no-pager -n 100`, then verify `~/.config/claude-glm/env`, the router key, and `curl -fsS -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" http://127.0.0.1:3456/`.
- **`Z_API_KEY is not set`**: Export `Z_API_KEY` before starting Claude Code or before running `claude mcp get web-search-prime`.
- **Z.ai MCP fails with auth errors**: Confirm the user has a Z.ai account, the API key is active, and the environment variable name is exactly `Z_API_KEY`.
- **Z.ai MCP was added with a literal `${Z_API_KEY}` header**: Replace the static `headers` entry with `headersHelper` so Claude Code reads the current environment at runtime.
- **`curl` fails with shared library errors**: Use Node `fetch` or `claude --print` for verification instead of curl.
- **Long context mismatch**: Treat `120k` as context length, not output length. Keep `maxtoken.max_tokens` as a generation cap such as `8192`; set `CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000`.
- **Existing `claude` wrapper**: Preserve user changes. Inspect the wrapper before replacing it, and keep the original binary or script as `.real`.

## Resources

- `scripts/configure.sh`: end-to-end installer/configurator and smoke test.
- `scripts/configure-claude-glm.sh`: side-by-side installer that preserves `claude` and adds `claude-glm`/`Claude-glm` for Huawei MaaS.
- `scripts/configure-zai-search-mcp.sh`: add and verify Z.ai `web-search-prime` MCP search using `Z_API_KEY`.
