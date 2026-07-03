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
| [`server/install-litellm-plugin.sh`](server/install-litellm-plugin.sh) | Plugin installer for docker-compose LiteLLM deployments |
| [`server/README.md`](server/README.md) | Server-side documentation |
| [`docs/PRD-anthropic-stream-guard.md`](docs/PRD-anthropic-stream-guard.md) | PRD / root-cause analysis for the plugin |
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

### Streams end with "API Error: Connection closed mid-response"

The guard synthesizes terminal events when the upstream ends a stream early,
so transient upstream truncations no longer surface this error. If you still
see it, the proxy process itself was restarted (or its network reconfigured)
while the stream was in flight — check `docker events` and the container's
`StartedAt` against the failure time, and avoid docker/network operations on
the gateway while Claude Code sessions are active. The
`asg_synthesized_terminations_total` / `asg_upstream_stream_errors_total`
counters show how often upstream truncation is being repaired.

## Legacy

`litellm_plugins/cc_glm52_guard/`, `docs/PRD.md`, `docs/EPICS.md`, and the
`tests/test_*.py` unit tests belong to an earlier adapter-based design and are
kept for reference only; they are not part of the current deployment.
