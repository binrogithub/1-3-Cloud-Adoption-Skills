---
name: claude-code-oauth-delegate-router
description: Deploy task-level hybrid routing for Claude Code — plain `claude` stays on Claude.ai OAuth as premium pool + orchestrator (policy in CLAUDE.md, UserPromptSubmit hint hook), while execution-class tasks and token-burn workflows (multi-agent fan-out, batch pipelines, loops, CI) are delegated via `delegate`/`workflow` runners to an isolated `claude-glm` client through LiteLLM to GLM on Huawei MaaS. Use when a Pro/Max subscription user wants MaaS execution offload with zero OAuth transport changes (no proxy, no token replay, no cache resets). Requires the LiteLLM-Huawei-MaaS-Proxy stack and litellm-maas-auto-plugin server plugins.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# Claude Code OAuth Delegate Router — Deploy / Verify / Operate

Architecture, contracts, and acceptance criteria: [docs/PRD.md](docs/PRD.md).
Product overview: [README.md](README.md).

## Prerequisites (check all before starting)

1. LiteLLM stack healthy on the target host (`LiteLLM-Huawei-MaaS-Proxy`, `:4000`).
2. `claude` CLI installed AND logged in via OAuth (`claude /login`) — the orchestrator.
3. `python3` present (runners are stdlib-only).
4. This monorepo checked out on the host (sibling assets are reused by relative path;
   otherwise set `CONFIGURE_CC` / `LIVE_SMOKE` to their locations).

## Step 1 — Server side (once, on the LiteLLM host)

Install the plugins from `../litellm-maas-auto-plugin/`:

```bash
../litellm-maas-auto-plugin/server/install-litellm-plugin.sh   # anthropic_stream_guard
```

Then ensure (manually, or confirm the installer applied them):

- `context_window_guard` mounted alongside (`../litellm-maas-plugin/litellm_plugins/context_window_guard/callback.py` → `/app/context_window_guard.py:ro`) and registered in `litellm_settings.callbacks`.
- `use_chat_completions_url_for_anthropic_messages: true` in `litellm_settings`.
- A **`claude-*` wildcard route** in `model_list` pointing at the execution model
  (this is what makes W1 sub-orchestration land subagent traffic on GLM):

```yaml
  - model_name: "claude-*"
    litellm_params:
      model: openai/glm-5.1          # or glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
      tpm: 500000
      rpm: 30
```

Restart the proxy (**check for in-flight Claude Code streams first**) and confirm:
liveness 200; a `/v1/messages` request with a `thinking` param returns a message
(not 404); a non-alias name like `claude-haiku-4-5-20251001` gets served.

> If the deployment generates `litellm_config.yaml` via `generate_config.sh`,
> re-running the generator **clobbers** the wildcard/callback edits — re-apply them.

## Step 2 — Mint the delegate virtual key

```bash
source /path/to/LiteLLM-stack/.env
curl -s http://localhost:4000/key/generate -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "content-type: application/json" \
  -d '{"key_alias":"delegate-<host>","metadata":{"purpose":"oauth-delegate-router execution pool"}}'
```

Give CI/loops their own key. Budget circuit breaker: set `BUDGET_TIER_KEY`
(rolling-window, e.g. `5h:12`) in the stack `.env`.

## Step 3 — Client install + orchestrator policy

```bash
./scripts/install.sh sk-<virtual-key> --base-url http://127.0.0.1:4000
./scripts/configure-policy.sh
```

`install.sh` reuses `configure-claude-code.sh` under `CLAUDE_CONFIG_DIR=$HOME/.claude-glm`
(env + key approval land only in the isolated dir), writes the `claude-glm` wrapper,
and links `delegate`/`workflow`. `configure-policy.sh` installs the marker-fenced
policy block into `~/.claude/CLAUDE.md`, the UserPromptSubmit hint hook, the
`glm-executor` agent, and the three GLM-twin skills. **Neither script writes any
`ANTHROPIC_*` variable for the plain `claude` client.**

## Step 4 — Verify

```bash
./scripts/verify.sh
```

Expected: `VERIFY PASS` + `TOOL-CALL PASS` (structured tool_use — if TOOL-CALL
fails, the MaaS endpoint/model has no function calling: fix server-side, do not
proceed); live-smoke `text`/`tools` HTTP 200; functional delegate smoke
`success | verified: True`; spend-log rows in window; both isolation invariants
PASS. E2E workflow check (optional, burns a few subscription turns): give the
plain `claude` a natural batch task ("add tests for these two modules and a
docs summary") and confirm new `glm … success` records appear in
`~/.claude-hybrid/route-audit.jsonl` with a workflow id.

## Operate

- `./scripts/route-stats.sh` — coverage / escalation / token split (review weekly; tune `scripts/route-hint.sh` signal words).
- Escalation semantics: an item failing twice returns `needs_escalation` — the orchestrator finishes it in-session and never re-delegates it. Workflow remainder >30% ⇒ abort + reclassify as premium (PRD §7).
- Concurrency: size `workflow` `concurrency` to the delegate key's rpm (default 3).

## Uninstall

```bash
./scripts/uninstall.sh   # removes policy block, hook, agent, skills, binaries
```

Never touches OAuth credentials, plain-`claude` transport, or the LiteLLM stack.
`~/.claude-glm` and the audit log are kept (delete manually); revoke the virtual
key via `/key/delete`.

## Troubleshooting

- **Delegate prints raw `<tool_call>` text / TOOL-CALL FAIL** — endpoint has no
  function-calling: see `../litellm-maas-auto-plugin/README.md` troubleshooting.
- **`claude -p` inside an `ssh bash -s` heredoc misbehaves** — it consumes the
  rest of the script as stdin (prompt pollution + skipped lines). Always append
  `< /dev/null` to `claude -p` in scripts.
- **First delegate run asks about the API key** — approval record missing;
  re-run `install.sh` (writes `customApiKeyResponses` into the isolated `.claude.json`).
- **429 storms under fan-out** — concurrency exceeds key rpm; lower `concurrency`,
  don't raise retries.
- **`asg_*`/`cwg_*` counters absent from `/metrics`** — lazy registration; they
  appear on the first repair event. Absence + healthy streams = nothing to repair.
- **Orchestrator stops delegating (policy drift)** — check the policy block
  survived in `~/.claude/CLAUDE.md`, hook still registered; consider strict mode
  (PRD §6.1 C4).
