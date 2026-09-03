# Claude-MaaS Universal Delegate Router

A task-level delegate router for Claude Code that connects **directly** to a
MaaS (Model-as-a-Service) endpoint exposing the native Anthropic Messages API.
No LiteLLM, no Claude Code Router (CCR), no OpenRouter, no Sidecar, no model
fallback chain, and no protocol adapter.

## What it is

The word "router" here means **task-level delegation**, not an HTTP router.
The system never silently switches provider within a session. Two commands
coexist on one machine:

```text
claude       -> official Claude Code OAuth -> Anthropic
claude-maas  -> official Claude Code CLI -> MaaS Anthropic API -> glm-5.2
```

`claude-maas` is an isolated launcher: it reads a stored API key, injects the
MaaS endpoint, key, and model into the child process environment, then `exec`s
the official `claude` binary. It starts no service, converts no protocol, and
listens on no port.

## Two audiences

### 1. Operators running Claude Code against a MaaS endpoint

If you have an Anthropic-compatible MaaS endpoint (e.g. Huawei Cloud ModelArts)
and want to use the official Claude Code CLI against it without any gateway
process, this project gives you a single isolated launcher (`claude-maas`) and a
universal installer (`install.sh`). You keep using plain `claude` for OAuth
work against Anthropic; `claude-maas` is a separate, credential-isolated path
to your MaaS model.

### 2. Users of other coding agents (Codex, Copilot, Cursor, OpenCode)

Your host agent keeps its own provider, model, and subscription. This project
installs an **additive** global Skill and routing policy that delegates only
bounded execution work — implementation, testing, bug fixes, mechanical
refactors, CI repairs, documentation — to `claude-maas`. Architecture, security,
payment, incident response, complex diagnosis, and work that has failed twice
remain local to the host agent. The host's provider and authentication are
never modified.

## Two operating modes

| Mode | When | Behavior |
| --- | --- | --- |
| **A — OAuth Orchestrator** | Logged into Anthropic via `claude` | Plain `claude` plans and orchestrates; bounded execution is delegated to `claude-maas` via `delegate` or `workflow`. Premium/visual/security/architecture work stays in the OAuth session. |
| **B — MaaS-only** | Not logged into Anthropic | Invoke `claude-maas` directly. No `claude /login` required. Every model request goes to the configured MaaS model. |

## Key properties

- **Direct connection.** The launcher `exec`s the real `claude` binary with
  MaaS environment variables set. There is no daemon between Claude Code and
  the upstream.
- **Single model, single upstream per instance.** One `claude-maas` instance
  serves exactly one upstream and one model. Switching upstreams is a config
  change, not a code change.
- **Credential isolation.** The MaaS key lives only in a 0600 file, is read as
  data, and is injected into the child environment. It never appears in argv,
  logs, audit records, or error output. OAuth and MaaS credentials never cross.
- **No fallback.** `fallback` is always `false` in the audit log. A MaaS-only
  failure never triggers an Anthropic or OpenRouter request.
- **Session reuse.** `maas-delegate` maps one host conversation to one Claude
  session and resumes it on later turns, with a per-handle lock to prevent
  cross-talk.

## Image limitation

The configured MaaS model (`glm-5.2`) does not support image input. This
project does not fake vision or reroute images to another provider:

- **OAuth mode:** image tasks stay in the OAuth `claude` session, which has
  native vision.
- **MaaS-only mode:** image requests return a clear
  `unsupported_capability:image` result.

## Where to go next

- [INSTALL.md](INSTALL.md) — safe installation and validation.
- [ARCHITECTURE.md](ARCHITECTURE.md) — components and invariants.
- [OPERATIONS.md](OPERATIONS.md) — commands and troubleshooting.
- [SECURITY.md](SECURITY.md) — credential handling and provider isolation.
- [RELEASE-NOTES.md](RELEASE-NOTES.md) — capabilities, supported hosts, limitations.
