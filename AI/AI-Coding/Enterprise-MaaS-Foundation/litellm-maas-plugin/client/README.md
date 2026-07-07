# Claude Code Client Setup (LiteLLM Gateway)

Configure a **native Claude Code** installation to use a LiteLLM gateway as its
API endpoint. No client-side proxy, router, or adapter is installed — Claude
Code talks the Anthropic `/v1/messages` protocol directly to LiteLLM.

```
Claude Code (this machine) ──Anthropic /v1/messages──► LiteLLM gateway :4000 ──► GLM-5.2
```

Multiple Claude Code clients can share one gateway; each client should use its
own LiteLLM **virtual key** (issued by the gateway admin, see
[`../server/README.md`](../server/README.md)).

## Prerequisites

- Claude Code installed (`claude --version`)
- `curl` and `python3` available
- Network access to the gateway (`http://<gateway-host>:4000`); for remote
  gateways the admin must allow your IP on port 4000 (cloud security group)
- A LiteLLM virtual API key for this client

## Quick start

```bash
./configure-claude-code.sh sk-your-virtual-key \
  --base-url http://<gateway-host>:4000 \
  --verify
```

Then **restart any open Claude Code session** (`exit`, then `claude`).

The API key is the only required input. On the gateway host itself,
`--base-url` can be omitted (defaults to `http://127.0.0.1:4000`).

The switch is reversible at any time — see
[Switching back to Anthropic](#switching-back-to-anthropic-uninstall).

## What the script writes

1. `~/.claude/settings.json` → `env` block (authoritative; read by Claude Code
   regardless of shell type or stale exported variables):

   | Variable | Value | Purpose |
   |---|---|---|
   | `ANTHROPIC_BASE_URL` | gateway URL | route all API calls to LiteLLM |
   | `ANTHROPIC_API_KEY` | your virtual key | gateway authentication |
   | `ANTHROPIC_MODEL` | `claude-opus-4-6` | primary model alias |
   | `ANTHROPIC_DEFAULT_HAIKU_MODEL` | same | background/fast calls |
   | `ANTHROPIC_SMALL_FAST_MODEL` | same | background/fast calls |
   | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | skip telemetry calls to anthropic.com |
   | `ANTHROPIC_AUTH_TOKEN` | (only with `--pin-auth-token`) | outranks `ANTHROPIC_API_KEY`; pin it on hosts where legacy proxies/wrappers may have exported a stale token. Causes a harmless "Both ... set" notice |

2. `~/.claude.json` → the API key is **pre-approved** in
   `customApiKeyResponses.approved` (skip with `--no-approve`). Claude Code
   does not adopt `ANTHROPIC_API_KEY` just because it is set: the key must be
   approved via the "Detected a custom API key … use it?" startup prompt, and
   with an active claude.ai login and no approval Claude Code silently keeps
   sending its claude.ai **OAuth token** — which the gateway rejects with
   `401` on every request. The script writes the same approval record a "Yes"
   answer would (the key's last 20 characters). Note: `/logout` clears all
   approvals; re-run the script after logging out.

3. Optionally (`--profile ~/.bashrc`) an idempotent managed export block for
   shells and scripts that read env vars directly.

Every modified file gets a timestamped `.bak.*` backup.

## Options

```
--api-key KEY    virtual key (or pass as the first positional argument)
--base-url URL   gateway URL (default http://127.0.0.1:4000, env LITELLM_BASE_URL)
--model NAME     model alias (default claude-opus-4-6)
--profile FILE   also write a managed export block to a shell profile
--no-settings    skip settings.json (exports only)
--no-approve     do not pre-approve the key in ~/.claude.json (you will have
                 to answer "Yes" to the API-key prompt at next launch)
--print-env      print export commands, write nothing
--verify         verify /v1/messages and structured tool-call capability
--restore        switch back to Anthropic's API (see below)
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| connection refused / timeout | wrong `--base-url`; port 4000 not reachable | check URL; gateway admin opens security group for your IP |
| `401 key_model_access_denied` | key not allowed for the requested model | admin: key ACL must include `claude-*` (Claude Code uses several internal model names) |
| `404 ... /responses ... APIG.0101` | gateway missing the chat-completions routing flag / plugin | admin: run `server/install-litellm-plugin.sh` |
| works at low effort, breaks at `/effort max` | gateway missing the stream-fix plugin | admin: run `server/install-litellm-plugin.sh` |
| tool calls print raw `<tool_call>...` text and no tools execute | backend endpoint is not parsing function/tool calls | admin: enable OpenAI-compatible function calling on MaaS, or start vLLM with `--enable-auto-tool-choice` and the matching `--tool-call-parser`; confirm with `--verify` |
| every request 401s; gateway logs show `POST /v1/messages?beta=true` | session is still authenticating with the claude.ai **OAuth token**, not the virtual key — the key was never approved (`customApiKeyResponses` empty/null in `~/.claude.json`), often after a `/logout` cleared approvals or after configuring with `--no-approve` | re-run this script (it pre-approves the key), or start `claude` and answer **Yes** to the "Detected a custom API key" prompt; verify with `/status` and expect `200` in `docker logs -f litellm_proxy` |
| old session still failing after configure | env captured at session start | fully exit Claude Code and start it again |
| 401 with a non-`sk-` key in gateway logs | stale `ANTHROPIC_AUTH_TOKEN` exported in a long-running shell (legacy wrapper) | log out of that shell and back in, or re-run this script with `--pin-auth-token` |
| "Both ANTHROPIC_AUTH_TOKEN and ANTHROPIC_API_KEY set" notice | `--pin-auth-token` was used, or the shell exports a stale AUTH_TOKEN | harmless if both hold the same key; to silence it, start a fresh login shell and configure without `--pin-auth-token` |
| gateway container logs show requests from the machine's own **public** IP | Docker routes host-originated traffic through the host's primary interface | not external probing — expected for local clients; check the request path/key to identify the caller |

## Switching back to Anthropic (uninstall)

The gateway switch is fully reversible. Your claude.ai login (OAuth
credentials) is stored separately from `settings.json` and is never touched by
this script, so it survives switching in both directions.

```bash
./configure-claude-code.sh --restore                    # settings.json only
./configure-claude-code.sh --restore --profile ~/.bashrc # also remove the export block
```

Then **restart any open Claude Code session** (`exit`, then `claude`).

`--restore` removes exactly the variables listed under
[What the script writes](#what-the-script-writes) from `~/.claude/settings.json`,
revokes the gateway key's approval entry in `~/.claude.json`, and, with
`--profile`, deletes the managed export block from that shell profile. Other
settings and env vars are left untouched, and each modified file gets a
timestamped `.bak.*` backup first. Running it again is a no-op.

If a long-running shell still exports the gateway variables, start a fresh
login shell, or unset them in place:

```bash
eval "$(./configure-claude-code.sh --restore --print-env)"
```

To switch back to the gateway later, just re-run the script with your virtual
key as in [Quick start](#quick-start). You can flip between Anthropic and the
gateway as often as you like.

Manual alternative: remove the `env` block from `~/.claude/settings.json` (or
restore a `.bak.*` backup) and delete the managed block from your shell
profile.
