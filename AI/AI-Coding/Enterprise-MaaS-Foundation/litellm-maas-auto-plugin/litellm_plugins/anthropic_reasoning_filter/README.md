# Anthropic Reasoning Filter

Response-only LiteLLM callback for Claude Code. It keeps provider thinking
enabled upstream but removes Anthropic `thinking` and `redacted_thinking`
blocks before the response reaches the client — **for GLM-family models only**.

## Scope: GLM-only stripping

The filter classifies the requested model into a family and strips thinking
only where thinking is a provider artifact:

| Family | Pattern (default, env-configurable) | Thinking |
| --- | --- | --- |
| GLM | `glm\|coding-\|claude-opus` | **stripped** (provider artifact) |
| Anthropic sonnet | `claude-sonnet` | **passed through** (user selected the model for its thinking) |
| Anthropic haiku | `claude-haiku` | **passed through** |
| other (e.g. `gpt-4o`) | unmatched | **stripped** (conservative default for OpenAI-compatible backends) |

Classification order matters: haiku is checked before sonnet before glm, so
`claude-haiku-4-5` is not caught by the sonnet or glm pattern first.

For sonnet/haiku (routed via OpenRouter to real Anthropic models), stripping
thinking would remove the value the user selected the model for, and the
synthesized thinking blocks the stream guard emits for GLM carry invalid
signatures that Anthropic verifies on later turns — so those models pass through
unchanged.

### Env knobs

- `ARF_HIDE_REASONING` — master switch (default `true`). When `false`, the
  filter passes everything through unchanged. When `true`, it strips only for
  GLM-family and unknown `other` models; sonnet/haiku keep their thinking.
- `GLM_FAMILY_PATTERN` (default `glm|coding-|claude-opus`) — `claude-opus` is
  the GLM compat alias in this deployment.
- `ANTHROPIC_SONNET_PATTERN` (default `claude-sonnet`).
- `ANTHROPIC_HAIKU_PATTERN` (default `claude-haiku`).

## What the filter does (when stripping)

- drops thinking block start/delta/signature/stop events;
- compacts remaining content indexes to `0..n`;
- preserves text, `tool_use`, usage, stop reasons, and terminal events;
- removes thinking blocks from non-streaming Messages responses;
- passes OpenAI chat-completions chunks through unchanged.

## Stream-guard coupling

The `anthropic_stream_guard` synthesizes thinking blocks with `signature: ""`
when repairing GLM streams (mixed `reasoning_content` + text delta families).
Those blocks have invalid signatures. They are safe because (a) the stream
guard only synthesizes for GLM-shaped streams — Anthropic-native streams don't
have mixed families, and (b) this filter strips thinking from GLM responses
before they reach the client. If the stream guard is ever extended to
synthesize thinking for Anthropic streams, this filter's GLM-only scope must be
revisited. (PRD-multi-family-routing Item 4.)
