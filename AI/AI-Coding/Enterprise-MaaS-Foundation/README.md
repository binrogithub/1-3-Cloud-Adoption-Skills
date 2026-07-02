# Enterprise MaaS Foundation

This directory provides the skills, adapters, and scripts needed to run
Claude Code against Huawei Cloud MaaS (Model-as-a-Service) backends instead
of, or in addition to, the official Anthropic API.

Two entry-point skills are provided. They are **kept separate on purpose** —
they serve different intents and must not be merged.

## When to use which

| Skill | Command | Backend | Relationship to Anthropic API |
| --- | --- | --- | --- |
| `claude-code-huawei-maas` | `claude-glm` | GLM-5.1 via LiteLLM on `:3456` | **Full replacement.** Claude Code talks only to MaaS. The official Anthropic endpoint is not used at all. |
| `Opus-advisor-MaaS-executor` | `claude-forky` | Opus (OAuth) for plan/vision + GLM-5.2 for execution, via forky on `:3458` | **Hybrid.** The official Claude (Opus) is retained for planning and image/vision tasks; MaaS (GLM) handles execution. Both Anthropic and MaaS are used. |

### `claude-glm` — MaaS-only

`claude-code-huawei-maas` provisions a LiteLLM proxy that speaks the
Anthropic API shape but forwards every request to Huawei MaaS (GLM). The
resulting `claude-glm` command is a fully self-contained Claude Code
instance that **never contacts the Anthropic API**. Use this when the
Anthropic endpoint is unavailable, blocked, or not desired, and you want
every Claude Code capability (chat, tools, agents, MCP) served by MaaS.

### `claude-forky` — Hybrid (Claude + MaaS)

`Opus-advisor-MaaS-executor` installs a forky router (`:3458`) that splits
traffic by intent: planning and image/vision requests go to Opus through
the official Anthropic OAuth path, while execution (code edits, shell
commands, agent runs) goes to GLM on MaaS. The resulting `claude-forky`
command **keeps Claude (Opus) available** and adds MaaS as the execution
backend. Use this when you want Opus-quality planning and vision but
prefer MaaS for the bulk of execution work.

## Prerequisite relationship

`Opus-advisor-MaaS-executor` depends on the LiteLLM stack provisioned by
`claude-code-huawei-maas` (or by `LiteLLM-Huawei-MaaS-Proxy`). Install the
MaaS proxy skill first, then layer forky on top. The reverse dependency
does not hold — `claude-glm` is self-contained.

## Other entries in this directory

- `LiteLLM-Huawei-MaaS-Proxy` — the shared LiteLLM proxy both skills build on.
- `Codex-OAuth-MaaS-Executor`, `codex-huawei-maas`, `copilot-huawei-maas`,
  `codearts-huawei-maas`, `CSS-Code-Search-MCP` — sibling integrations for
  other clients; unrelated to the two Claude Code entries above.
