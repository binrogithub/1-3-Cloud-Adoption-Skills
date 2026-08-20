# Claude Code Direct MaaS Delegate Router — Approved Design

Date: 2026-08-19  
Status: approved  
Decision owner: user  
Target: `/root/claude-code-delegate-router`

## Context

The existing `litellm-auto-plugin` routes Claude Code's Anthropic Messages
traffic through LiteLLM to Huawei Cloud MaaS. It also contains compatibility
repairs, smart routing, fallbacks, and Vision/Premium Sidecars. The reference
`claude-code-oauth-delegate-router` keeps the official OAuth `claude` transport
untouched and delegates execution tasks to a second MaaS-backed Claude Code
client.

Huawei MaaS now exposes a native Anthropic Messages endpoint. Live validation
on 2026-08-19 showed that the endpoint handles non-streaming messages, valid
Anthropic SSE, adaptive thinking, automatic tool use, forced tool choice, and a
complete Claude Code tool round trip. Image input still returns HTTP 400.

## Decision

Build a task-level delegate router with two explicit commands and no network
router:

```text
claude       -> official Claude Code OAuth -> Anthropic
claude-maas  -> official Claude Code CLI -> Huawei MaaS Anthropic API -> glm-5.2
```

When OAuth is available, plain `claude` acts as planner and orchestrator.
Premium, visual, security, architecture, and complex debugging work remains in
the OAuth session. Bounded text execution work is delegated through
`delegate`/`workflow` to `claude-maas`.

When OAuth is absent, the user invokes `claude-maas` directly. This mode is a
single-provider product: every model request goes to Huawei MaaS `glm-5.2`.

The word "router" in the project name means task classification and subprocess
delegation. It does not mean an HTTP proxy or protocol conversion service.

## Explicit removals

- LiteLLM and its virtual keys, model registry, callbacks, spend logs, and ACLs.
- Claude Code Router (`ccr`) and local ports 3456/3458.
- Anthropic-to-OpenAI protocol conversion.
- Runtime SSE, `[DONE]`, thinking, and forced-tool-choice repair middleware.
- Vision and Premium Sidecars, including their internal credentials and caches.
- OpenRouter and GLM-5.1 fallbacks.
- Gateway smart routing, prefix-affinity routing, and cross-provider fallback.
- Hidden provider switching of any kind.

## Retained product capabilities

- Native `claude` remains byte-for-byte and environment-wise untouched.
- Isolated `claude-maas` state and credentials.
- Marker-fenced OAuth orchestration policy and advisory route hint hook.
- Structured `delegate` and parallel `workflow` runners.
- Two-attempt ceiling, timeout, maximum turns, bounded 429 backoff, and
  acceptance-command verification.
- Disjoint-scope enforcement for parallel workflows.
- Local JSONL route audit without prompt or credential contents.
- Install, uninstall, migration, and direct-endpoint verification tools.

## Sidecar replacement policy

| Old Sidecar or fallback | Replacement |
| --- | --- |
| Vision Sidecar | Keep images in OAuth `claude`; MaaS-only returns a clear unsupported-capability result. |
| Premium Advisor Sidecar | OAuth Claude handles premium work and failed delegations. |
| Premium Tool Repair | Tool schemas plus bounded retry; unresolved failures return `needs_escalation`. |
| GLM-5.1 fallback | No replacement; retry the same GLM-5.2 endpoint only. |
| OpenRouter fallback | No replacement; provider boundaries stay explicit. |

## Credential and configuration design

The installer reads the MaaS key from stdin or a narrowly scoped environment
variable. It stores the raw single-line key in
`~/.config/claude-maas/api-key` with mode `0600`; it never places the key in
argv, shell profiles, JSON audit records, or project files. The wrapper reads
the file as data rather than sourcing it as shell code.

Non-secret settings live in `~/.config/claude-maas/config.json`:

```json
{
  "anthropic_base_url": "https://api-ap-southeast-1.modelarts-maas.com/anthropic",
  "model": "glm-5.2",
  "context_tokens": 1000000
}
```

Only the `claude-maas` child receives:

```text
ANTHROPIC_BASE_URL=<configured Anthropic base URL>
ANTHROPIC_AUTH_TOKEN=<key read from the 0600 file>
ANTHROPIC_MODEL=glm-5.2
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.2
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.2
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.2
CLAUDE_CONFIG_DIR=~/.claude-maas
```

`ANTHROPIC_API_KEY` is unset in the child to keep one unambiguous credential
path. No `ANTHROPIC_*` values are written to the plain Claude configuration or
parent shell.

## Failure model

- Authentication errors stop immediately without printing credentials.
- HTTP 429 honors a bounded `Retry-After`; one work item still has at most two
  attempts.
- Image input is never captioned or rerouted silently.
- A failed OAuth delegation returns `needs_escalation`; the orchestrator may
  complete it in the OAuth session and must not delegate it again.
- A failed MaaS-only session reports the MaaS error and never changes provider
  or model.
- Endpoint protocol regression fails verification and blocks installation or
  release; it is not repaired silently at runtime.

## Verification strategy

Move the useful compatibility knowledge from `litellm-auto-plugin` into
read-only canaries. The release gate must verify:

1. Non-streaming Anthropic response structure.
2. Strict SSE framing and JSON-decodable `data:` frames.
3. No OpenAI `[DONE]` after `message_stop`.
4. Correct `thinking`/`text` block and delta pairing.
5. Automatic and forced structured `tool_use`.
6. Real Claude Code text request with token-only authentication and no OAuth.
7. Real Claude Code tool execution and `tool_result` continuation.
8. Plain `claude` command, config, OAuth metadata, and environment isolation.
9. Image input produces the documented unsupported outcome unless MaaS gains
   verified native image support in a future revision.

## Revisit triggers

Reconsider a runtime compatibility layer only if a fresh, repeatable direct
MaaS canary fails and the defect cannot be avoided by documented Claude Code or
MaaS configuration. Reconsider Sidecars only through a new product decision
that explicitly permits multi-provider traffic. Neither is a v1 requirement.
