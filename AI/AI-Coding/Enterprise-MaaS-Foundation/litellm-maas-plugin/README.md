# litellm-maas-plugin

Connect **native Claude Code** clients directly to a **LiteLLM** gateway
backed by GLM-5.2 (Huawei MaaS). No client-side router, proxy, or adapter —
the client speaks the Anthropic `/v1/messages` protocol straight to LiteLLM.

```
Claude Code #1..N ──/v1/messages──► LiteLLM :4000 ──/chat/completions──► GLM-5.2
   (per-client virtual keys)          │ anthropic_stream_guard plugin
                                      │ claude-* wildcard route, budgets, metrics
```

## Deliverables

| Path | What it is |
|---|---|
| [`client/configure-claude-code.sh`](client/configure-claude-code.sh) | Client setup script — input: a LiteLLM virtual API key |
| [`client/README.md`](client/README.md) | Client-side documentation |
| [`litellm_plugins/anthropic_stream_guard/`](litellm_plugins/anthropic_stream_guard/) | Server-side LiteLLM plugin (custom callback, no core patches) |
| [`litellm_plugins/cc_glm52_guard/`](litellm_plugins/cc_glm52_guard/) | GLM-5.2 smart routing plugin for virtual coding models |
| [`server/install-litellm-plugin.sh`](server/install-litellm-plugin.sh) | Plugin installer for docker-compose LiteLLM deployments |
| [`server/README.md`](server/README.md) | Server-side documentation |
| [`docs/PRD-anthropic-stream-guard.md`](docs/PRD-anthropic-stream-guard.md) | PRD / root-cause analysis for the plugin |
| [`docs/PRD-smart-routing.md`](docs/PRD-smart-routing.md) | PRD for GLM-5.2 / Opus / Vision smart routing |
| [`docs/EPICS-smart-routing.md`](docs/EPICS-smart-routing.md) | Epic breakdown for commercial smart routing delivery |
| [`tests/live_smoke.py`](tests/live_smoke.py) | Live smoke test (text / 185K context / image / search) |
| [`.claude/skills/deploy-litellm-plugin/`](.claude/skills/deploy-litellm-plugin/SKILL.md) | Claude Code skill: guided plugin deploy / verify / rollback |

## Quick start

Server (once, on the LiteLLM host):

```bash
server/install-litellm-plugin.sh
# then: add a claude-* wildcard model route and issue per-client keys
# (see server/README.md)
```

Each client:

```bash
client/configure-claude-code.sh sk-<virtual-key> --base-url http://<gateway>:4000 --verify
```

## Troubleshooting

### Tool calls show up as raw text (`<tool_call>...`) in Claude Code

**Symptom** ([issue #111](https://github.com/binrogithub/1-3-Cloud-Adoption-Skills/issues/111)):
Claude Code prints the model's whole "process" — file trees, file contents,
and markup like `<tool_call>Bash_tool> <command>mkdir ...</command>` — as
plain text, and no tools actually execute.

**Root cause**: the model endpoint behind LiteLLM is not parsing tool calls.
When the OpenAI-compatible backend has no tool-call parser, GLM writes its
tool invocations as improvised markup inside normal text; LiteLLM faithfully
converts that text to `text_delta` events and Claude Code displays it. This
is an **endpoint capability problem**, not a client or plugin bug — the
plugin intentionally does not try to re-parse improvised markup (the syntax
is unstable across models and rewriting risks corrupting legitimate code
that contains similar strings).

**Diagnose**:
- Client: `configure-claude-code.sh <key> --verify` now includes a tool-call
  probe (`TOOL-CALL PASS / FAIL / WARN`).
- Server: `python3 tests/live_smoke.py tools`, or watch the
  `asg_unparsed_tool_markup_total` Prometheus counter — it increments when
  raw `<tool_call` markup streams through while the request declared tools.

**Fix (server side)**:
- Huawei MaaS: use a model / endpoint version with **function calling
  enabled** for OpenAI-compatible requests (verify with the probe above).
- Self-hosted vLLM: start the server with `--enable-auto-tool-choice` and
  the matching `--tool-call-parser` for your model family.

### Image requests fail with "prompt length ... must less than ..." (400)

A base64 screenshot tokenizes at ~2.5 chars/token on the GLM tokenizer — a
single 703KB PNG is 100K+ real tokens — and the text-only backend cannot use
it anyway. `context_window_guard` handles images two ways:

- **Vision routing (recommended)**: set `CWG_VISION_MODEL=vision-openrouter`
  in the LiteLLM container environment. Image-bearing requests are rerouted
  to that model with a vision-window budget (`CWG_VISION_TRIGGER/TARGET`,
  default 110K/100K); images are kept and only text history is trimmed.
  Aliases in `CWG_VISION_KEEP_MODELS` are never rerouted.
- **Fallback (no vision model configured)**: oversized images are replaced
  with an explanatory text stub during trimming so the request no longer
  400s (`CWG_STRIP_IMAGES=never` disables this).

### Messages typed during a running task are silently ignored

**Symptom** ([issue #115](https://github.com/binrogithub/1-3-Cloud-Adoption-Skills/issues/115)):
messages typed while Claude Code is mid-task get queued and injected into the
next tool result as `<system-reminder>` text ("you MUST address the user's
message"), but the model never acknowledges them and keeps executing its plan.

**Root cause**: that delivery is soft - plain text buried inside a tool
result, competing with the model's completion bias. Anthropic models are
aligned to honor it; GLM-5.2 is not.

**Fix**: `anthropic_stream_guard` detects the queued-message reminder in the
newest user message and re-surfaces it as a standalone text block at the END
of that message ("[USER INTERJECTION ...] Respond to the user message below
FIRST..."), where every chat template gives it top salience. Only the newest
message is scanned (history is never resurrected), ordinary system-reminders
are untouched, and the rewrite is idempotent across retries. Disable with
`ASG_AMPLIFY_INTERJECTIONS=false`; observe via
`asg_amplified_interjections_total`.

### Long sessions: tools invoked with "invalid tool parameters" (InputValidationError)

**Symptom**: deep into a large session (context past `CWG_TRIGGER_TOKENS`),
the model starts calling tools with input
`{"cleared_by_proxy": "tool input removed to fit the model context window"}`
and Claude Code rejects every call ("required parameter ... is missing /
unexpected parameter cleared_by_proxy").

**Root cause**: `context_window_guard` used to replace cleared historical
`tool_use` inputs with that stub dict. With hundreds of cleared blocks in
context, the backend model learns the stub as the calling convention and
imitates it for new calls. Fixed: trimmed inputs now keep their real
parameter keys and silently truncate oversized values, so every example the
model sees stays valid-shaped. The errors are self-healing (the validation
error feeds back and the model retries), but the wasted turns disappear after
updating the plugin and restarting the proxy.

### Streams end with "API Error: Connection closed mid-response"

The guard synthesizes terminal events when the upstream ends a stream early,
so transient upstream truncations no longer surface this error. If you still
see it, the proxy process itself was restarted (or its network reconfigured)
while the stream was in flight — check `docker events` and the container's
`StartedAt` against the failure time, and avoid docker/network operations on
the gateway while Claude Code sessions are active. The
`asg_synthesized_terminations_total` / `asg_upstream_stream_errors_total`
counters show how often upstream truncation is being repaired.

## Design History

`docs/PRD.md` and `docs/EPICS.md` describe the earlier Claude Code
GLM-5.2 service-side adapter plan. The current smart-routing product
definition is `docs/PRD-smart-routing.md` and `docs/EPICS-smart-routing.md`.
The `cc_glm52_guard` package is active for the smart-routing contract tests.
