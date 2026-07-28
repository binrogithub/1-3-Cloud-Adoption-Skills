---
name: codex-maas-hybrid-router
description: Install, configure, verify, or troubleshoot a side-by-side `codex-forky` command that routes normal Codex tool/code-execution turns through an existing external forky service to the MaaS execution backend such as LiteLLM/Huawei MaaS GLM, while routing non-tool ordinary turns and image turns directly to Codex ChatGPT/OAuth.
---

# Codex MaaS Hybrid Router

## Overview

This skill adds a Codex-facing bridge that splits requests:

```text
codex-forky -> Codex Responses API -> codex-forky bridge
  -> tools/no image: forky Anthropic Messages API -> glm-5.2 execution backend
  -> no tools or image: Codex ChatGPT/OAuth Responses endpoint
```

It preserves plain `codex`. It does not install forky itself and does not change the forky routing rules.

## Quick Path

```bash
cd AI/AI-Coding/Enterprise-MaaS-Foundation/codex-maas-hybrid-router
./scripts/configure-codex-forky.sh
codex-forky exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

## Prerequisites

1. `codex`, `node`, and `curl` are in PATH.
2. Forky is reachable at `FORKY_BASE_URL`, default `http://127.0.0.1:3458`.
3. Forky's own execution backend and OAuth routes are already verified.

## Configuration

Environment overrides:

| Variable | Default | Meaning |
|---|---|---|
| `FORKY_BASE_URL` | `http://127.0.0.1:3458` | Existing forky service |
| `CODEX_FORKY_BRIDGE_URL` | `http://127.0.0.1:3460` | Local Responses bridge URL |
| `CODEX_FORKY_ROUTER_KEY` | `codex-forky-local` | Bearer token Codex uses for the bridge |
| `CODEX_FORKY_MODEL` | `claude-sonnet-4-6` | Route-facing model string sent to forky for execution requests |
| `CODEX_FORKY_OAUTH_MODEL` | `gpt-5.5` | Real Codex OAuth model for non-execution requests |
| `CODEX_FORKY_CONTEXT_TOKENS` | `180000` | Codex model catalog context window |
| `CODEX_FORKY_MAX_OUTPUT_TOKENS` | `8192` | Anthropic `max_tokens` |
| `INSTALL_SYSTEMD_USER_SERVICE` | `1` | Install `codex-forky-bridge.service` when possible |
| `INSTALL_CODEX_SKILL` | `1` | Copy this skill into `$CODEX_HOME/skills/codex-maas-hybrid-router` for future auto-discovery |

## Files

- `scripts/configure-codex-forky.sh` writes the Codex profile, model catalog, wrapper, env file, bridge copy, and optional systemd service.
- `scripts/codex-forky-responses-bridge.cjs` exposes `/v1/responses` and translates the practical Codex Responses subset to Anthropic Messages.
- `scripts/verify-codex-forky.sh` checks OAuth tokens, forky health, `EXEC_MODEL`, stale runtime config, skill auto-discovery, bridge startup, OAuth routing, and execution routing.
- `tests/test-bridge-transform.js` covers request and tool conversion.
- `references/how-it-works.md` explains the architecture and routing boundaries.

## Verification

```bash
./scripts/verify-codex-forky.sh
node --check scripts/codex-forky-responses-bridge.cjs
node --check tests/test-bridge-transform.js
node tests/test-bridge-transform.js
```

End-to-end, after forky is running:

```bash
./scripts/configure-codex-forky.sh
codex-forky exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

## Troubleshooting

- `forky is not reachable`: start the original forky service first, usually `systemctl --user start forky.service`.
- `bridge is not reachable`: check `/tmp/codex-forky-bridge.log` or `journalctl --user -u codex-forky-bridge -n 50 --no-pager`.
- Text-only prompts route to Codex OAuth: expected. Agentic Codex execution normally includes tools and routes to forky/glm-5.2.
- Image requests route to Codex OAuth: expected. They bypass forky so GLM's lack of vision does not matter.
- OAuth request fails with 401: run `codex login` again so `~/.codex/auth.json` has fresh ChatGPT tokens.
- `codex-forky` shows `gpt-5.5 high` or loops through many file reads: stale local runtime config is likely. Rerun `env -u CODEX_FORKY_MODEL -u CODEX_FORKY_OAUTH_MODEL ./scripts/configure-codex-forky.sh`, then start a new `codex-forky` session. `./scripts/verify-codex-forky.sh` should report `Codex profile uses claude-sonnet-4-6 with reasoning disabled`.
