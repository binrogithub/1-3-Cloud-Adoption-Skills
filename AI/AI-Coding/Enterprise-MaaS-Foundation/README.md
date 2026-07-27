# Enterprise MaaS Foundation

This directory provides the skills, adapters, and scripts needed to run
Claude Code against Huawei Cloud MaaS (Model-as-a-Service) backends instead
of, or in addition to, the official Anthropic API.

Two entry-point skills are provided. They are **kept separate on purpose** —
they serve different intents and must not be merged.

## When to use which

| Skill | Command | Backend | Relationship to Anthropic API |
| --- | --- | --- | --- |
| `claude-code-maas-direct-router` | `claude-glm` | GLM-5.1 via LiteLLM on `:3456` | **Direct router.** The `claude-glm` command talks only to MaaS. The official Anthropic endpoint is not used by that command. |
| `claude-code-maas-hybrid-router` | `claude-forky` | Claude OAuth for plan/vision/classifier + GLM-5.2 for execution, via forky on `:3458` | **Hybrid router.** Claude is retained for planning, image/vision, and classifier traffic; MaaS (GLM) handles execution. Both Anthropic and MaaS are used. |

### `claude-glm` — Direct Router (MaaS-only)

`claude-code-maas-direct-router` provisions a CCR/LiteLLM path that speaks the
Anthropic API shape but forwards `claude-glm` requests to Huawei MaaS (GLM).
The resulting command is a fully self-contained MaaS-backed Claude Code
instance that does not contact the Anthropic API. Use this when the Anthropic
endpoint is unavailable, blocked, or not desired, and you want every Claude
Code capability (chat, tools, agents, MCP) served by MaaS.

### `claude-forky` — Hybrid Router (Claude + MaaS)

`claude-code-maas-hybrid-router` installs a forky router (`:3458`) that splits
traffic by intent: planning, image/vision, and classifier requests go through
the official Claude OAuth path, while execution (code edits, shell commands,
agent runs) goes to GLM on MaaS. The resulting `claude-forky` command keeps
Claude available where it matters and adds MaaS as the execution backend.
Use this when you want Claude-quality planning and vision but prefer MaaS
for the bulk of execution work.

## Prerequisite relationship

`claude-code-maas-hybrid-router` depends on the LiteLLM stack provisioned by
`claude-code-maas-direct-router` (or by `LiteLLM-Huawei-MaaS-Proxy`). Install the
MaaS proxy skill first, then layer forky on top. The reverse dependency
does not hold — `claude-glm` is self-contained.

## Other entries in this directory

- `LiteLLM-Huawei-MaaS-Proxy` — the shared LiteLLM proxy both skills build on.
- `claude-code-oauth-delegate-router` — task-level hybrid for Claude Code (OAuth
  orchestrator + `delegate`/`workflow` to GLM); closest conceptual sibling to the
  Cursor entry below.
- `cursor-maas-delegate-router` — **USER-GLOBAL** task-level hybrid for Cursor:
  subscription/premium Agent orchestrates; MaaS GLM executes via `delegate.py`
  (Rules + Hooks under `~/.cursor/`, all workspaces).
- `codex-maas-hybrid-router`, `codex-huawei-maas`, `copilot-huawei-maas`,
  `codearts-huawei-maas`, `CSS-Code-Search-MCP` — sibling integrations for
  other clients; unrelated to the two Claude Code entries above.
