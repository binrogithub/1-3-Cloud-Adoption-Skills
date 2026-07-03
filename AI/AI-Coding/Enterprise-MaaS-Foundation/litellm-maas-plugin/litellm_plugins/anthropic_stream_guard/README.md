# anthropic_stream_guard

LiteLLM custom callback that makes `/v1/messages` safe for native Claude Code
clients when the backend is an OpenAI-compatible reasoning model whose
`reasoning_content` cannot be disabled (e.g. GLM-5.2 on Huawei MaaS).

- **Request side** (`async_pre_call_hook`): strips `thinking` / `reasoning` /
  `reasoning_effort` so LiteLLM keeps `/v1/messages` on `/chat/completions`
  instead of the unsupported OpenAI Responses API. Opt out with
  `ASG_STRIP_THINKING=false`.
- **Response side** (`async_post_call_streaming_iterator_hook`): re-sequences
  the malformed SSE stream produced by the messages->chat/completions adapter
  (single `text` block mixing `thinking_delta` + `text_delta`) into a
  protocol-correct stream: first-block retyping, synthesized
  `content_block_stop`/`start` pairs, index remapping. Byte-identical
  pass-through for already-correct streams; fail-open on errors; never touches
  OpenAI-protocol streams.

Install, configuration requirements, verification, and rollback:
see [`../../server/README.md`](../../server/README.md).
Design rationale: [`../../docs/PRD-anthropic-stream-guard.md`](../../docs/PRD-anthropic-stream-guard.md).

Deploy as a **single file** mounted at `/app/anthropic_stream_guard.py` and
register `anthropic_stream_guard.proxy_handler_instance` under
`litellm_settings.callbacks`.

## Hardening (10k-user scale)

Security invariants (enforced in code comments I1-I7 and by the test suite
`tests/test_anthropic_stream_guard.py`, 9 tests):

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
```

Alerting suggestions: page when `asg_parse_errors_total` rate stays above zero
(format drift after a LiteLLM upgrade), and when `asg_retyped_blocks_total`
stops increasing while traffic is nonzero (upstream fixed - plugin can be
retired).

Env: `ASG_STRIP_THINKING` (default true), `ASG_MAX_PARSE_BYTES` (default 262144).
