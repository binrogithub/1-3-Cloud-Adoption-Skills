# Enterprise MaaS Foundation

This directory provides the skills, adapters, and scripts needed to run
Claude Code against Huawei Cloud MaaS (Model-as-a-Service) backends instead
of, or in addition to, the official Anthropic API.

The customer-facing Claude Code entry point is the MaaS-only direct router. It
keeps the client-side setup simple and avoids installing local router/forky
components on customer terminals.

## When to use which

| Skill | Command | Backend | Relationship to Anthropic API |
| --- | --- | --- | --- |
| `claude-code-maas-direct-router` | `claude-glm` | GLM-5.1 via LiteLLM on `:3456` | **Direct router.** The `claude-glm` command talks only to MaaS. The official Anthropic endpoint is not used by that command. |

### `claude-glm` — Direct Router (MaaS-only)

`claude-code-maas-direct-router` provisions a CCR/LiteLLM path that speaks the
Anthropic API shape but forwards `claude-glm` requests to Huawei MaaS (GLM).
The resulting command is a fully self-contained MaaS-backed Claude Code
instance that does not contact the Anthropic API. Use this when the Anthropic
endpoint is unavailable, blocked, or not desired, and you want every Claude
Code capability (chat, tools, agents, MCP) served by MaaS.

## Prerequisite relationship

`claude-code-maas-direct-router` can use the LiteLLM stack provisioned by
`LiteLLM-Huawei-MaaS-Proxy`. Install the MaaS proxy skill first when you need
the shared proxy, observability, or optional search profile.

## Other entries in this directory

- `LiteLLM-Huawei-MaaS-Proxy` — the shared LiteLLM proxy both skills build on.
- `claude-code-oauth-delegate-router` — task-level hybrid for Claude Code (OAuth
  orchestrator + `delegate`/`workflow` to GLM); closest conceptual sibling to the
  Cursor entry below.
- `cursor-maas-delegate-router` — **USER-GLOBAL** task-level hybrid for Cursor:
  subscription/premium Agent orchestrates; MaaS GLM executes via `delegate.py`
  (Rules + Hooks under `~/.cursor/`, all workspaces).
- `opencode-maas-delegate-router` — task-level hybrid for OpenCode: GLM-5.2
  orchestrates through global instructions, while named GLM-5.1 subagents handle
  execution-class tasks on the same Huawei MaaS provider.
- `codex-maas-hybrid-router`, `codex-huawei-maas`, `copilot-huawei-maas`,
  `codearts-huawei-maas`, `CSS-Code-Search-MCP` — sibling integrations for
  other clients; unrelated to the Claude Code direct-router entry above.
