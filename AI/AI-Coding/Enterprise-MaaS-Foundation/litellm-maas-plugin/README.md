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

## Legacy

`litellm_plugins/cc_glm52_guard/`, `docs/PRD.md`, `docs/EPICS.md`, and the
`tests/test_*.py` unit tests belong to an earlier adapter-based design and are
kept for reference only; they are not part of the current deployment.
