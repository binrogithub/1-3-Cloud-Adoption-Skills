# claude-code-huawei-maas

This skill documents Claude Code CLI usage patterns for connecting to Huawei Cloud MaaS through `claude-code-router`.

It is intended for operators who want either:

- side-by-side commands where `claude` continues using Anthropic Claude models and `claude-glm` uses Huawei MaaS `glm-5.1`
- a full migration where the installed `claude` command is wrapped to use a ModelArts MaaS endpoint

## Scope

Preferred side-by-side scope:

```text
claude CLI
  -> Anthropic Claude models

claude-glm CLI
  -> claude-code-router on http://127.0.0.1:3456
  -> Huawei Cloud MaaS OpenAI-compatible /chat/completions
  -> glm-5.1
```

Legacy full migration scope:

```text
claude CLI
  -> claude-code-router on http://127.0.0.1:3456
  -> Huawei Cloud MaaS OpenAI-compatible /chat/completions
  -> glm-5.1
```

For Claude Agent SDK or custom proxy patterns, use the separate `Claude-Code-SDK-Agent-MaaS-Skill`.

## Quick Start

```bash
export API_KEY='replace-with-your-maas-api-key'
./scripts/configure-claude-glm.sh
```

The side-by-side script configures:

- `~/.claude-code-router/config.json`
- `~/.config/claude-glm/env`
- `~/.local/bin/claude-glm`
- `~/.local/bin/Claude-glm`
- `ANTHROPIC_MODEL=glm-5.1` only inside the `claude-glm` wrapper
- `ANTHROPIC_CUSTOM_MODEL_OPTION=glm-5.1` only inside the `claude-glm` wrapper
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000` only inside the `claude-glm` wrapper
- `DISABLE_COMPACT=true` only inside the `claude-glm` wrapper so Claude Code honors the 190K context override
- `claude --model glm-5.1` only from the `claude-glm` wrapper, so the interactive header also selects `glm-5.1`
- background startup and readiness checks for `ccr` when the router is not already running
- real router health checks against `http://127.0.0.1:3456/`, so stale pid/status files do not cause `FailedToOpenSocket` or `ConnectionRefused` retries
- stop/start race handling: if `ccr` is unhealthy, the wrapper stops it, waits for the old process to release, then waits up to 30 seconds for the restarted router to become healthy

It also runs a smoke test and expects the result to report `modelUsage.glm-5.1`.

## Local Router Recovery

When Claude Code reports errors such as:

```text
Unable to connect to API (FailedToOpenSocket)
ConnectionRefused: http://127.0.0.1:3456/v1/messages?beta=true
ccr failed to start; see /tmp/claude-glm-ccr.log
```

Check the local router before changing MaaS credentials:

```bash
ccr status
ss -ltnp | grep ':3456'
curl -fsS -H "Authorization: Bearer ${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}" http://127.0.0.1:3456/
```

If `ccr status` says running but the curl check fails, the router state is stale. Re-run `./scripts/configure-claude-glm.sh` or use the generated `claude-glm` wrapper; it now stops stale `ccr`, waits for shutdown, starts it in the background, and verifies the local socket before launching Claude Code.

To wrap plain `claude` instead:

```bash
export API_KEY='replace-with-your-maas-api-key'
./scripts/configure.sh
```

The script configures:

- `~/.claude-code-router/config.json`
- for side-by-side mode, a `claude-glm` wrapper that exports the router environment
- for migration mode, a `claude` wrapper that exports the router environment
- `ANTHROPIC_MODEL=glm-5.1`
- `ANTHROPIC_CUSTOM_MODEL_OPTION=glm-5.1`
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000`

It also runs a smoke test and expects the result to report `modelUsage.glm-5.1`.

## Files

```text
claude-code-huawei-maas/
├── README.md
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    ├── configure-claude-glm.sh
    └── configure.sh
```

## Security

Do not commit a real MaaS API key. The side-by-side script writes `api_key: "$HUAWEI_MAAS_API_KEY"` into the router config and stores the local secret in `~/.config/claude-glm/env` with `0600` permissions. The legacy migration script writes `api_key: "$API_KEY"` into the router config so the secret remains in the runtime environment.
