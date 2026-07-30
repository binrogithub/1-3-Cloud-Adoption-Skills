# anthropic_stream_guard

LiteLLM custom callback that makes `/v1/messages` safe for native Claude Code
clients when the backend is an OpenAI-compatible reasoning model that emits
`reasoning_content` (e.g. GLM-5.1 on Huawei MaaS). The recommended deployment
keeps model thinking enabled and uses the companion response filter to hide
internal reasoning only at the Anthropic client boundary.

- **Request side** (`async_pre_call_hook`): strips `thinking` / `reasoning` /
  `reasoning_effort` so LiteLLM keeps `/v1/messages` on `/chat/completions`
  instead of the unsupported OpenAI Responses API. It also strips Anthropic
  server tools that the OpenAI-compatible backend cannot execute, normalizes
  OpenAI-style `image_url` blocks into Anthropic `image/source` blocks, and can
  translate forced Anthropic `tool_choice` values into OpenAI-compatible
  function choice for direct-provider adapters that validate the OpenAI shape.
  Keep `ASG_TRANSLATE_TOOL_CHOICE=false` for LiteLLM `/v1/messages` ingress;
  enable it only for direct Huawei endpoint adapter deployments. Opt out of
  thinking stripping with `ASG_STRIP_THINKING=false`.
- **Response side** (`async_post_call_streaming_iterator_hook`): re-sequences
  the malformed SSE stream produced by the messages->chat/completions adapter
  (single `text` block mixing `thinking_delta` + `text_delta`) into a
  protocol-correct stream: first-block retyping, synthesized
  `content_block_stop`/`start` pairs, index remapping. Byte-identical
  pass-through for already-correct streams; fail-open on errors; never touches
  OpenAI-protocol streams.
- **Huawei SSE compatibility**: repairs raw byte chunks framed as bare
  `data:` plus un-prefixed pretty JSON into compact Anthropic SSE, and drops
  trailing OpenAI-style `data: [DONE]` only after `message_stop`. Multi-event
  malformed chunks fail open and pass through unchanged instead of risking
  data loss.
- **Tool-call diagnostics**: increments `asg_unparsed_tool_markup_total` and
  logs one redacted warning when a tools request streams raw `<tool_call`
  markup as visible text. The guard intentionally does not rewrite improvised
  model markup; fix the backend endpoint so it returns structured tool calls.

Install, configuration requirements, verification, and rollback:
see [`../../server/README.md`](../../server/README.md).
Design rationale: [`../../docs/PRD-anthropic-stream-guard.md`](../../docs/PRD-anthropic-stream-guard.md).

Deploy as a **single file** mounted at `/app/anthropic_stream_guard.py` and
register `anthropic_stream_guard.proxy_handler_instance` under
`litellm_settings.callbacks`.

## Tool-call markup in Claude Code

If Claude Code shows raw text such as `<tool_call>Bash_tool>` and file
contents instead of the normal tool progress UI, the backend model endpoint is
not parsing function/tool calls. Diagnose it with:

```bash
client/configure-claude-code.sh sk-<key> --base-url http://<gateway>:4000 --verify
python3 tests/live_smoke.py tools
```

Expected result: a structured `tool_use` block. If the response contains raw
markup, enable function calling on the endpoint. For Huawei MaaS, use a
model/endpoint version with OpenAI-compatible tools enabled. For self-hosted
vLLM, start with `--enable-auto-tool-choice` and the matching
`--tool-call-parser`.

## Hardening (10k-user scale)

Security invariants (enforced in code comments I1-I7 and by the test suite
`tests/test_anthropic_stream_guard.py`, 32 checks):

| Invariant | Mechanism |
|---|---|
| Tenant isolation | all state is per-request (`_StreamState`); no shared mutable state - verified by a concurrent-interleaving test |
| Fail-open | any per-chunk error flushes buffers and forwards original bytes; the guard can never kill a stream |
| No SSE injection | only whitelist-validated event types are ever re-serialized |
| Bounded parsing | chunks above `ASG_MAX_PARSE_BYTES` (default 256 KiB) are forwarded unparsed and counted |
| Log redaction | logs carry event indexes / block types / exception class names only - never payload content |
| Adversarial-safe fast path | steady-state deltas are classified by byte markers without JSON parsing; faked markers inside user-influenced text cause ambiguity, which falls back to full parsing (extra CPU, never a wrong rewrite) |
| Minimal supply chain | stdlib + litellm only; metrics degrade to no-ops without `prometheus_client` |

Prometheus metrics on the proxy `/metrics` endpoint:

```
asg_retyped_blocks_total        first-block type corrections
asg_synthesized_blocks_total    synthesized stop/start pairs
asg_parse_errors_total          unparseable chunks (passed through)
asg_oversize_passthrough_total  chunks skipped by the size cap
asg_synthesized_terminations_total streams finalized after early upstream end
asg_upstream_stream_errors_total upstream iterator exceptions finalized
asg_unparsed_tool_markup_total  raw <tool_call markup seen in tool requests
asg_raw_sse_repaired_total      Huawei raw pretty-JSON SSE frames repaired
asg_openai_done_dropped_total   trailing data: [DONE] chunks dropped
asg_tool_choice_translated_total forced Anthropic tool_choice translations
```

Alerting suggestions: page when `asg_parse_errors_total` rate stays above zero
(format drift after a LiteLLM upgrade), and when `asg_retyped_blocks_total`
stops increasing while traffic is nonzero (upstream fixed - plugin can be
retired).

Env: `ASG_STRIP_THINKING` (default true), `ASG_NORMALIZE_IMAGE_URL` (default
true), `ASG_TRANSLATE_TOOL_CHOICE` (default false), `ASG_MAX_PARSE_BYTES`
(default 262144).
