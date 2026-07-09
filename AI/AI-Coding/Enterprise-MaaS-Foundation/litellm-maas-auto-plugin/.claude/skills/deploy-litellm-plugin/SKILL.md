---
name: deploy-litellm-plugin
description: Deploy, verify, upgrade, or roll back the anthropic_stream_guard LiteLLM plugin on a docker-compose LiteLLM gateway. Use when asked to install/uninstall the plugin, wire a LiteLLM deployment for native Claude Code clients, or verify the gateway stream fix.
---

# Deploy the anthropic_stream_guard LiteLLM plugin

This repo ships a LiteLLM custom callback (no core patches) that makes
`/v1/messages` safe for native Claude Code clients when the backend is an
OpenAI-compatible reasoning model whose `reasoning_content` cannot be disabled
(e.g. GLM-5.2 on Huawei MaaS). It re-sequences the malformed SSE stream and
strips `thinking`/`reasoning` request params. Details: `server/README.md`,
`docs/PRD-anthropic-stream-guard.md`.

## 1. Preflight

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep -i litellm   # container healthy?
docker compose -f <LITELLM_DIR>/docker-compose.yml config --services  # service name
```

Defaults assumed by the installer: deployment dir `/root/LiteLLM`, service
`litellm`, container `litellm_proxy`. Override with `--litellm-dir`,
`--service`, `--container`, `--config-file` if different.

On a shared/production gateway: the install restarts the container (seconds of
downtime). Confirm the window with the operator first.

## 2. Dry run, then install

```bash
server/install-litellm-plugin.sh --dry-run     # preview edits
server/install-litellm-plugin.sh               # backup + mount + callback + flag + restart + import check
```

The script is idempotent and backs up every file it touches (`.bak.<ts>`). It:
mounts `litellm_plugins/anthropic_stream_guard/callback.py` as a SINGLE FILE at
`/app/anthropic_stream_guard.py` (package dirs are not supported by LiteLLM's
loader), registers `anthropic_stream_guard.proxy_handler_instance` under
`litellm_settings.callbacks`, and sets
`use_chat_completions_url_for_anthropic_messages: true`.

## 3. Config the script does NOT handle — check and apply manually

- `model_list` needs a `claude-*` wildcard route (Claude Code sends several
  internal model names). Template in `server/README.md`.
- Single-deployment backends: raise `router_settings.allowed_fails` (e.g. 1000)
  so transient failures cannot cooldown the only deployment into a total outage.
- Issue per-client virtual keys whose ACL includes `claude-*`
  (`/key/generate`, see `server/README.md`).

## 4. Verify

```bash
# stream protocol: first block "thinking", deltas legal, start/stop paired
curl -sN <BASE>/v1/messages -H 'content-type: application/json' \
  -H 'x-api-key: <key>' -H 'anthropic-version: 2023-06-01' \
  -d '{"model":"claude-opus-4-6","max_tokens":128,"stream":true,
       "thinking":{"type":"enabled","budget_tokens":1024},
       "messages":[{"role":"user","content":"what is 2+2?"}]}' \
  | grep -oE '"content_block": \{"type": "[a-z]+"'
# expect: thinking first, then text

curl -s <BASE>/metrics/ | grep '^asg_'        # plugin metrics live

# full unit suite (9 tests) inside the container
docker cp litellm_plugins/anthropic_stream_guard/callback.py <CONTAINER>:/tmp/asg/anthropic_stream_guard.py
docker cp tests/test_anthropic_stream_guard.py <CONTAINER>:/tmp/asg_test.py
docker exec <CONTAINER> python /tmp/asg_test.py   # expect: ALL 9 TESTS PASS

python3 tests/live_smoke.py all               # optional end-to-end regression
```

## 5. Rollback

```bash
server/install-litellm-plugin.sh --uninstall   # removes mount + callback, restarts
```

or restore the `.bak.<ts>` files and restart. The plugin is stateless.

## Known display quirk: WebSearch shows "Did 0 searches"

On this gateway, a Claude Code `WebSearch` call renders like:

```
Web Search("<query>")
  ⎿  Did 0 searches in 34s
```

**This is cosmetic — the search worked.** Claude Code's counter tallies
server-side `web_search_tool_result` events, which only Anthropic's own
hosted search produces. This gateway fulfills searches differently:
`anthropic_stream_guard` strips the `web_search` server tool (the GLM
backend rejects it with a 400, see `asg_server_tools_stripped_total`), a
search hook injects real engine results into the prompt, and the model
returns the findings as ordinary text in the tool result. The content
reaches the session; only the counter reads zero.

How to confirm results were delivered: the tool result body contains
"Web search results for query: ..." with substantive content, and the
proxy logs show the injection (`docker logs <CONTAINER> | grep -i
search`).

**Do not "fix" this.** Making the counter count would require
synthesizing fake `server_tool_use` / `web_search_tool_result` SSE
events for searches the backend never performed — protocol risk for a
purely cosmetic gain.

## Gotchas

- The callback class must define its hooks directly (LiteLLM checks
  `type(callback).__dict__`) — do not wrap it in a subclass.
- After editing the mounted plugin file, `docker compose up -d` is NOT enough
  (content changes don't trigger recreate) — use `docker restart <CONTAINER>`.
- Alert on `asg_parse_errors_total` growth after LiteLLM upgrades (format
  drift), and consider retiring the plugin when `asg_retyped_blocks_total`
  stops increasing under traffic (upstream fixed).
