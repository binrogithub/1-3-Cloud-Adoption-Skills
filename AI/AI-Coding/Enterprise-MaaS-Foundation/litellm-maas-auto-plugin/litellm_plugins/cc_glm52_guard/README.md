# cc_glm52_guard

LiteLLM custom callback for the Claude Code -> LiteLLM -> GLM-5.2 server-side path. It is a pre-call hook and does not fork or patch LiteLLM core.

## What it does

- Exports `proxy_handler_instance` from `cc_glm52_guard.callback`.
- Routes smart coding virtual models:
  - `meli-coding-fast` -> GLM-5.2 execution pool.
  - `coding-auto` -> workload/risk/context/budget/capacity router.
  - `meli-coding-deep` -> premium reasoning model.
  - `meli-coding-review` -> risk-based GLM or premium model.
  - `meli-coding-vision` -> vision model.
- Maps `claude-sonnet-4-6`, `glm-5.2`, and `claude-glm1` to `CC_GLM52_EXECUTION_MODEL` (`glm-5.2` by default).
- Treats `claude-sonnet-4-6-backend`, `glm-5.2-backend`, and `claude-glm1-backend`
  as backend fallback aliases. They still route to `CC_GLM52_EXECUTION_MODEL`.
- Routes requests with image content blocks to `CC_GLM52_VISION_MODEL` (`vision-openrouter` by default).
- In backend fallback mode, search-intent prompts get a `litellm_web_search`
  tool so LiteLLM `websearch_interception` can handle backend search.
- Injects or merges Claude context management edits:
  - `clear_tool_uses_20250919` at `CC_GLM52_CLEAR_TOOL_TRIGGER` (`100000`), keeping 3 tool uses.
  - `compact_20260112` at `CC_GLM52_COMPACT_TRIGGER` (`150000`).
- Keeps existing `context_management` and non-matching edits.
- Removes only `thinking` and `redacted_thinking` content blocks from `messages`, `input`, and list-form `system`.
- Adds namespaced audit data to `metadata.cc_glm52_guard`. If a caller already
  provides `extra_body.cc_glm52_guard_audit`, the hook keeps that namespace in
  sync, but it does not create `extra_body` just for audit data.
- Estimates input size with the first-pass fallback `len(serialized_request_fields) / 4`.
- Writes smart-routing telemetry: virtual model, task type, repo risk/tags,
  budget state, latency SLO, capacity state, fallback reason, and context policy.
- Writes commercial telemetry for PoC dashboards: team/project/cost center,
  workload, model pool, estimated tokens, reserved TPM, queue delay, p95 latency,
  error rate, CI status, acceptance status, and relative cost vs premium.

## Environment

```bash
export CC_GLM52_EXECUTION_MODEL=glm-5.2
export CC_GLM52_PREMIUM_MODEL=opus-4.8
export CC_GLM52_VISION_MODEL=vision-openrouter
export CC_GLM52_SUMMARY_MODEL=opus-summary
export CC_GLM52_DIRECT_LIMIT=160000
export CC_GLM52_MAX_LIMIT=196000
export CC_GLM52_SOFT_LIMIT=180000
export CC_GLM52_COMPACT_TRIGGER=150000
export CC_GLM52_CLEAR_TOOL_TRIGGER=100000
export CC_GLM52_SEARCH_MODE=native
export CC_GLM52_CAPABILITY_MODE=frontend_capable
export CC_GLM52_GLM_RELATIVE_COST=0.22
export CC_GLM52_PREMIUM_RELATIVE_COST=1.0
export CC_GLM52_VISION_RELATIVE_COST=1.0
export CC_GLM52_SWITCH_COOLDOWN_TURNS=3
export CC_GLM52_PREMIUM_STICKY_TURNS=5
export CC_GLM52_MAX_SWITCHES_PER_SESSION=2
export CC_GLM52_GLM_DOWNGRADE_SUCCESS_STREAK=2
```

`CC_GLM52_SEARCH_MODE=native` keeps Claude Code native search as the default.
Backend fallback mode can be selected by request metadata, backend model aliases,
or `CC_GLM52_CAPABILITY_MODE=backend_fallback`.

Smart routing uses request metadata when present:

```json
{
  "model": "coding-auto",
  "metadata": {
    "task_type": "unit_test_generation",
    "repo_risk": "medium",
    "repo_tags": ["checkout"],
    "context_tokens": 85000,
    "budget_state": "normal",
    "latency_slo": "batch",
    "glm_available": true,
    "glm_reserved_tpm": 10000000,
    "tpm_queue_delay_ms": 0,
    "latency_p95_ms": 42000,
    "model_error_rate": 0.01,
    "ci_status": "passed",
    "acceptance_status": "accepted",
    "accepted_task": true
  }
}
```

If `task_type` is absent, the plugin uses deterministic prompt rules for common
coding workloads. It never sends raw >196K context directly to GLM-5.2.

Task classification order:

1. `metadata.task_type`
2. GitHub signals: PR events/actions, check conclusions, CodeQL/code scanning,
   secret scanning, Dependabot, labels, CODEOWNERS, merge conflicts
3. Changed paths such as `.github/workflows/*`, `docs/*`, test directories,
   dependency manifests, migrations, infrastructure files
4. Optional `semantic-router` prompt intent classification
5. Prompt pattern fallback

The audit namespace includes `task_signal.source` and `task_signal.evidence`,
for example `github.check_conclusion=failure` or `changed_path=docs/onboarding.md`.
When semantic routing is enabled, semantic hits use
`task_signal.source=semantic_router`.

The semantic layer is disabled by default so production does not import an
embedding stack unless explicitly configured:

```bash
CC_GLM52_SEMANTIC_ROUTER_ENABLED=true
CC_GLM52_SEMANTIC_ROUTER_ENCODER=huggingface
CC_GLM52_SEMANTIC_ROUTER_HF_MODEL=intfloat/multilingual-e5-small
```

Supported semantic task intents are `architecture_planning`, `complex_debug`,
`unit_test_generation`, `documentation`, `ci_auto_fix`, and `security_review`.
If `semantic-router` or its encoder dependency is unavailable, the plugin logs
a warning and falls back to prompt patterns.

For tasks that start on GLM-5.2 and later prove impossible to split or compress,
retry the same logical task with one of these metadata flags:

```json
{
  "model": "coding-auto",
  "metadata": {
    "task_type": "repo_summary",
    "context_tokens": 180000,
    "context_unsegmentable": true
  }
}
```

The retry routes to `CC_GLM52_PREMIUM_MODEL` and records
`route_reason=context_unsegmentable_to_premium`.

To avoid context loss, the retry must include the full canonical context and
set `canonical_context_replayed=true`. The plugin cannot transfer hidden model
state from GLM-5.2 to Opus-4.8; it can only route a new request. A recommended
handoff retry looks like:

```json
{
  "model": "coding-auto",
  "messages": ["...full canonical conversation and packed repo context..."],
  "metadata": {
    "context_split_failed": true,
    "canonical_context_replayed": true,
    "previous_attempt_id": "glm-attempt-1",
    "attempt_id": "opus-attempt-2",
    "glm_attempt_summary": "GLM found the checkout dependency graph but could not split payment flows safely."
  }
}
```

The plugin injects a `[Context handoff]` system note for this escalation path
and records `context_handoff` audit fields. If the full context is not replayed,
the audit warning is
`caller_must_replay_full_canonical_context_to_avoid_context_loss`.

To avoid quality loss from GLM/Opus oscillation, pass session state on each
request:

```json
{
  "metadata": {
    "session_id": "coding-session-123",
    "session_turn": 8,
    "previous_internal_route_model": "opus-4.8",
    "last_model_switch_turn": 5,
    "model_switch_count": 1,
    "premium_sticky_until_turn": 10,
    "glm_success_streak": 0
  }
}
```

The plugin suppresses Opus -> GLM downgrades during sticky/cooldown windows and
records the decision in `model_switch_policy`. Hard safety upgrades still route
to Opus immediately.

## LiteLLM loading

Mount the package into the LiteLLM container so Python can import `cc_glm52_guard`. Example Docker Compose fragment:

```yaml
services:
  litellm:
    volumes:
      - /root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard:/app/cc_glm52_guard:ro
```

Then add the callback to the LiteLLM config:

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance

general_settings:
  context_management_summary_model: opus-summary
```

The current host config is `/root/LiteLLM/assets/config/litellm_config.yaml`; apply the same callback line there during deployment, then restart the LiteLLM container in the normal platform window.

See `config.example.yaml` for a complete key-free config fragment with the
virtual models, `glm-5.2`, `opus-4.8`, `opus-summary`, and
`vision-openrouter` aliases. Product and delivery details are in
`docs/PRD-smart-routing.md` and `docs/EPICS-smart-routing.md`.

## Main API

```python
from litellm.integrations.custom_logger import CustomLogger

class CCGLM52Guard(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        ...

proxy_handler_instance = CCGLM52Guard()
```
