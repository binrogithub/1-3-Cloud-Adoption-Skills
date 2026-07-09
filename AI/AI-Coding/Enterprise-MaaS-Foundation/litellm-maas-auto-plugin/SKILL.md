# LiteLLM MaaS Coding Auto Router Skill

## Purpose

This skill describes how to deploy and operate the LiteLLM MaaS coding auto router plugin for Claude Code and Anthropic-compatible clients.

The plugin is designed for teams that want a single coding model alias, usually `coding-auto`, while routing each request to the most appropriate backend model:

- GLM-5.2 for most coding execution, test generation, documentation, refactoring, CI fixes, and low-risk implementation work.
- Opus-4.8 for high-complexity planning, complex debugging, security review, infrastructure changes, high-risk repositories, fallback escalation, and contexts that GLM should not handle directly.
- A vision-capable model for image or screenshot requests.

The value of this plugin is operational control. It lets platform teams expose one stable model name to Claude Code while applying server-side policy for quality, cost, latency, risk, context limits, and auditability.

The plugin is a LiteLLM custom callback. It runs as a pre-call hook. It does not require forking Claude Code, does not patch the Claude Code client, and does not require model routing logic on developer machines.

## Why This Plugin Exists

Claude Code and similar coding agents often run multi-step tasks:

1. Understand the task.
2. Inspect files.
3. Design a change.
4. Edit files.
5. Run tests.
6. Fix failures.
7. Summarize the result.

Not every step needs the same model.

Using a premium reasoning model for every turn can be expensive and slow. Using a cheaper execution model for every turn can degrade quality for architecture, security, incident, or high-risk reasoning work.

This plugin provides a pragmatic split:

- Use Opus when the decision quality matters most.
- Use GLM when the work is implementation-heavy and testable.
- Avoid frequent back-and-forth switching because context replay and compression can cost more than the switch saves.
- Record routing decisions in request metadata so operators can debug why a request used one model instead of another.

## Prerequisites

Before deploying this plugin, the LiteLLM environment must already be working.

Required:

1. A running LiteLLM proxy.
2. A working database-backed LiteLLM deployment is strongly recommended, because spend logs are the easiest way to verify real model usage.
3. A working GLM-5.2 model group in LiteLLM.
4. A working Opus-4.8 model group in LiteLLM.
5. A valid LiteLLM virtual key for Claude Code or another Anthropic-compatible client.
6. Docker Compose access if LiteLLM is containerized.
7. Permission to edit the LiteLLM config and restart the LiteLLM proxy.

Optional:

1. A vision model group, such as `vision-openrouter`, if screenshot/image routing is required.
2. A summary model group, such as `opus-summary`, if Claude context management summarization is enabled.
3. `semantic-router` and an embedding backend, if semantic prompt classification is required. This is disabled by default.

Important Opus note:

Direct Anthropic OAuth-based Opus access may not work through a server-side LiteLLM deployment, depending on the client, account, and OAuth flow. For server-side routing, prefer an API-key-backed Opus deployment that LiteLLM can call directly. In the examples below, Opus is exposed as the LiteLLM model group `opus-4.8`.

## Expected LiteLLM Model Groups

The plugin assumes these logical model groups exist:

- `coding-auto`: the main public alias used by Claude Code.
- `glm-5.2`: the GLM execution model group.
- `opus-4.8`: the premium reasoning model group.
- `vision-openrouter`: optional vision model group.
- `opus-summary`: optional context summary model group.

The public alias `coding-auto` can initially point to GLM-5.2 in `model_list`. The plugin can then rewrite requests server-side to `opus-4.8` or `vision-openrouter` when policy requires it.

Example GLM group:

```yaml
model_list:
  - model_name: glm-5.2
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
      tpm: 500000
      rpm: 30
    model_info:
      max_tokens: 198000
      max_input_tokens: 192000
      max_output_tokens: 128000
```

Example `coding-auto` alias:

```yaml
  - model_name: coding-auto
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
      tpm: 500000
      rpm: 30
    model_info:
      max_tokens: 198000
      max_input_tokens: 192000
      max_output_tokens: 128000
```

Example Opus group:

```yaml
  - model_name: opus-4.8
    litellm_params:
      model: openrouter/anthropic/claude-opus-4.8
      api_base: https://openrouter.ai/api/v1
      api_key: os.environ/OpenRouter_API_KEY
      tpm: 400000
      rpm: 50
    model_info:
      max_tokens: 32000
      max_input_tokens: 200000
      max_output_tokens: 32000
```

Use the provider and credential style that is correct for your environment. The important part is that LiteLLM can successfully call the model group named `opus-4.8`.

## Plugin Files

The plugin package is:

```text
litellm_plugins/cc_glm52_guard/
```

The main callback file is:

```text
litellm_plugins/cc_glm52_guard/callback.py
```

It exports:

```python
proxy_handler_instance
```

LiteLLM loads this object from config:

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance
```

## Deployment Overview

Deployment has five parts:

1. Put the plugin code where the LiteLLM container can import it.
2. Mount the plugin into the LiteLLM container.
3. Add the plugin callback to LiteLLM config.
4. Configure model groups, fallbacks, and pre-call checks.
5. Restart LiteLLM and verify routing.

## Step 1: Copy Or Mount The Plugin

A common host path is:

```text
/root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard/
```

The directory should contain:

```text
callback.py
README.md
config.example.yaml
__init__.py
```

If your source checkout is elsewhere, copy or sync the plugin directory into the host path used by Docker Compose.

Example:

```bash
mkdir -p /root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard
cp -r ./litellm_plugins/cc_glm52_guard/* \
  /root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard/
```

Adjust the source path to match your repository layout.

## Step 2: Mount The Plugin Into LiteLLM

In `docker-compose.yml`, mount the callback into the LiteLLM container.

Single-file mount:

```yaml
services:
  litellm:
    volumes:
      - /root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard/callback.py:/app/cc_glm52_guard.py:ro
```

Directory mount:

```yaml
services:
  litellm:
    volumes:
      - /root/litellm-maas-auto-plugin/litellm_plugins/cc_glm52_guard:/app/cc_glm52_guard:ro
```

Use one style consistently.

If you mount a single file to `/app/cc_glm52_guard.py`, the callback path is:

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance
```

If you mount a package directory to `/app/cc_glm52_guard`, the callback path is also:

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance
```

## Step 3: Configure LiteLLM Callback

In the LiteLLM config, add the plugin callback.

Example:

```yaml
litellm_settings:
  drop_params: true
  callbacks:
    - prometheus
    - cc_glm52_guard.proxy_handler_instance
```

If you already have callbacks, append `cc_glm52_guard.proxy_handler_instance` to the existing list. Do not remove existing operational callbacks unless you intentionally want to change behavior.

## Step 4: Configure Router Settings

Enable LiteLLM native pre-call checks and fallbacks.

Example:

```yaml
router_settings:
  routing_strategy: simple-shuffle
  enable_pre_call_checks: true
  num_retries: 3
  max_fallbacks: 2
  cooldown_time: 30
  allowed_fails: 3
  fallbacks:
    - coding-auto:
        - opus-4.8
    - glm-5.2:
        - opus-4.8
    - claude-opus-4-6:
        - opus-4.8
  context_window_fallbacks:
    - coding-auto:
        - opus-4.8
    - glm-5.2:
        - opus-4.8
    - claude-opus-4-6:
        - opus-4.8
```

`enable_pre_call_checks` depends on correct `model_info.max_input_tokens` values in each model deployment. Without those values, LiteLLM cannot reliably know when a request exceeds a deployment context window.

Do not use unsupported router keys for your LiteLLM version. For example, LiteLLM `1.83.14` accepts `enable_pre_call_checks`, `fallbacks`, `context_window_fallbacks`, `max_fallbacks`, `allowed_fails`, and `cooldown_time`, but does not accept every experimental router option from newer examples.

## Step 5: Configure Context Management

If you want LiteLLM/Claude-compatible context management support, set a summary model:

```yaml
general_settings:
  context_management_summary_model: opus-summary
```

The plugin can inject or merge Claude context management edits:

- `clear_tool_uses_20250919`
- `compact_20260112`

Default triggers:

- Clear tool uses at about `100000` estimated input tokens.
- Compact at about `150000` estimated input tokens.

These defaults are controlled by environment variables.

## Environment Variables

Recommended defaults:

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

export CC_GLM52_SEMANTIC_ROUTER_ENABLED=false
export CC_GLM52_SEMANTIC_ROUTER_ENCODER=huggingface
export CC_GLM52_SEMANTIC_ROUTER_HF_MODEL=intfloat/multilingual-e5-small
```

The most important variables are:

- `CC_GLM52_EXECUTION_MODEL`: the GLM execution model group.
- `CC_GLM52_PREMIUM_MODEL`: the Opus/premium reasoning model group.
- `CC_GLM52_VISION_MODEL`: the vision model group.
- `CC_GLM52_MAX_LIMIT`: the maximum raw context size GLM should receive.
- `CC_GLM52_SWITCH_COOLDOWN_TURNS`: prevents frequent GLM/Opus oscillation.
- `CC_GLM52_PREMIUM_STICKY_TURNS`: keeps a session on premium briefly after an upgrade.

## Restart LiteLLM

After editing config or plugin files, restart LiteLLM.

Docker Compose example:

```bash
cd /root/LiteLLM
docker compose restart litellm
```

Check health:

```bash
curl -fsS http://127.0.0.1:4000/health/readiness
```

Expected:

```json
{
  "status": "healthy",
  "db": "connected"
}
```

If the callback fails to import, inspect logs:

```bash
cd /root/LiteLLM
docker compose logs --tail=200 litellm
```

## Configure Claude Code

Claude Code should call LiteLLM instead of calling Anthropic directly.

Typical settings:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
    "ANTHROPIC_API_KEY": "YOUR_LITELLM_VIRTUAL_KEY",
    "ANTHROPIC_MODEL": "coding-auto",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "coding-auto",
    "ANTHROPIC_SMALL_FAST_MODEL": "coding-auto",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
```

Use a LiteLLM virtual key with access to:

- `coding-auto`
- `glm-5.2`
- `opus-4.8`
- optional legacy aliases
- optional vision aliases

Do not expose the LiteLLM master key to developer machines.

## Auto Routing Strategy

The main user-facing alias is:

```text
coding-auto
```

When a request uses `coding-auto`, the plugin classifies the request and rewrites the internal model when needed.

### Classification Order

The plugin classifies tasks in this order:

1. Explicit `metadata.task_type`.
2. GitHub signals.
3. Changed file paths.
4. Optional `semantic-router` prompt classification.
5. Regex prompt fallback.
6. Default classification.

### Metadata First

If the caller provides:

```json
{
  "metadata": {
    "task_type": "unit_test_generation"
  }
}
```

that value wins over prompt-based inference.

Recommended task types:

- `architecture_planning`
- `complex_debug`
- `unit_test_generation`
- `documentation`
- `ci_auto_fix`
- `security_review`
- `code_generation`
- `bug_fix`
- `refactoring`
- `repo_summary`
- `dependency_update`
- `infrastructure_change`
- `production_incident`

### GitHub Signals

The plugin can infer task type from metadata such as:

- `github_event`
- `github_action`
- `check_name`
- `check_conclusion`
- `check_status`
- `alert_type`
- `alert_severity`
- `labels`
- `github_labels`
- `dependabot`
- `dependabot_security_update`
- `merge_conflict`
- `codeowners_required`

Examples:

- Failed workflow run routes as `ci_auto_fix`.
- Code scanning alert routes as `security_review`.
- Dependabot security update routes as `security_review`.
- Normal Dependabot version update routes as `dependency_update`.

### Changed Path Signals

Changed paths can classify the work:

- `.github/workflows/*` -> `ci_auto_fix`
- `docs/*`, `README`, `CHANGELOG`, `adr/*` -> `documentation`
- `tests/*`, `*_test.*`, `*.spec.*` -> `unit_test_generation`
- dependency manifests -> `dependency_update`
- migration directories -> `migration_execution`
- Terraform/Kubernetes/Helm paths -> `infrastructure_change`
- auth/security/risk paths -> `security_review`

### Optional Semantic Router

Semantic classification is disabled by default.

Enable only if you have installed and tested `semantic-router` and the encoder dependencies:

```bash
export CC_GLM52_SEMANTIC_ROUTER_ENABLED=true
```

Supported semantic intents:

- `architecture_planning`
- `complex_debug`
- `unit_test_generation`
- `documentation`
- `ci_auto_fix`
- `security_review`

If the semantic dependency is missing, the plugin logs a warning and falls back to deterministic regex classification.

### GLM Execution Tasks

These task types normally route to GLM-5.2:

- `unit_test_generation`
- `documentation`
- `repo_summary`
- `ci_auto_fix`
- `code_generation`
- `bug_fix`
- `refactoring`
- `migration_execution`
- `dependency_update`
- `merge_conflict_resolution`

This is the intended default for normal coding work.

### Opus Premium Tasks

These task types route to Opus-4.8:

- `architecture_planning`
- `complex_debug`
- `production_incident`
- `security_review`
- `infrastructure_change`

Opus is not treated as a "design-only" model. It is the premium reasoning model for high-complexity, high-risk, or hard-to-recover decisions.

### Context-Based Routing

The plugin estimates input tokens and also respects `metadata.context_tokens`.

Default policy:

- Up to `160000` tokens: GLM direct is allowed.
- `160000` to `196000` tokens: compression or context management may be required.
- Above `196000` tokens: route to premium or require file selection, RAG, summary, or split.

The plugin should not send raw context above the GLM maximum limit directly to GLM.

### Fallback-Based Routing

The plugin upgrades to Opus when fallback signals indicate GLM is not the right next step.

Fallback signals include:

- `context_unsegmentable=true`
- `context_split_failed=true`
- `compression_failed=true`
- `retry_count >= 2`
- `test_failed_twice=true`
- `latency_p95_ms > 60000`
- `model_error_rate > 0.03`
- `tpm_queue_delay_ms > 30000`

For context split failures, the route reason becomes:

```text
context_unsegmentable_to_premium
```

### Risk-Based Routing

High-risk or restricted repositories route to Opus.

Risk can be supplied explicitly:

```json
{
  "metadata": {
    "repo_risk": "high"
  }
}
```

Recognized values:

- `low`
- `medium`
- `high`
- `restricted`

The plugin can also infer risk from tags such as:

- `payment`
- `payments`
- `auth`
- `risk`
- `pci`
- `security`

### Budget-Based Routing

If `metadata.budget_state` is:

- `near_limit`
- `limited`
- `exhausted`

then eligible execution tasks prefer GLM.

Hard safety routes still win. For example, a security review should not be forced to GLM only because budget is near limit.

### Capacity-Based Routing

If GLM is unavailable and the request is interactive, the plugin can route to premium:

```json
{
  "metadata": {
    "glm_available": false,
    "latency_slo": "interactive"
  }
}
```

Capacity metadata can be provided by external controllers or platform telemetry.

## Model Switch Suppression

Frequent GLM <-> Opus switching can hurt quality and increase cost because every switch requires context replay. The plugin includes hysteresis.

Recommended session metadata:

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

Default behavior:

- Hard upgrades are not suppressed.
- Opus -> GLM downgrade is suppressed during the premium sticky window.
- Opus -> GLM downgrade is suppressed during cooldown.
- Opus -> GLM downgrade can require a GLM success streak.
- Maximum model switches per session can be capped.

This prevents routing from becoming worse than a fixed-model strategy.

## Context Handoff

Models do not share hidden state.

When a task switches from GLM to Opus, or from Opus to GLM, the next model only sees the visible conversation and tool context that the client sends in the next request.

There is no transfer of:

- KV cache.
- Hidden reasoning state.
- Provider-private scratchpad state.
- Internal model memory.

Therefore, reliable handoff requires the caller or agent to replay the canonical visible context.

For GLM-to-Opus escalation after failed context splitting:

```json
{
  "model": "coding-auto",
  "messages": [
    "...full canonical conversation and packed repo context..."
  ],
  "metadata": {
    "context_split_failed": true,
    "canonical_context_replayed": true,
    "previous_attempt_id": "glm-attempt-1",
    "attempt_id": "opus-attempt-2",
    "glm_attempt_summary": "GLM identified the dependency graph but could not split payment flows safely."
  }
}
```

The plugin injects a context handoff system note and records the handoff in audit metadata.

If `canonical_context_replayed` is missing, the plugin records a warning:

```text
caller_must_replay_full_canonical_context_to_avoid_context_loss
```

## Usage Patterns

### Pattern 1: Normal Coding

Use `coding-auto`.

Prompt:

```text
Add unit tests for the parser and run pytest.
```

Expected model:

```text
glm-5.2
```

### Pattern 2: Medium Or High Complexity Design Then Implementation

Use two requests:

Request 1:

```text
You are only doing architecture planning. Do not edit files.
Design the module boundaries, policy pipeline, data model, error handling, and test strategy.
```

Expected model:

```text
opus-4.8
```

Request 2:

```text
Now implement the project according to the previous plan. Write code, tests, run pytest, and fix failures.
```

Expected model:

```text
glm-5.2
```

This works because Claude Code sends a new request after the first answer. The router evaluates each request independently.

Opus does not "hand the task" to GLM. The outer agent sends the visible Opus design as context in the next request, and LiteLLM routes the next request to GLM.

### Pattern 3: Security Review

Prompt:

```text
Review this PR for authentication, authorization, injection, secret leakage, and data exposure risks.
```

Expected model:

```text
opus-4.8
```

### Pattern 4: Failed CI Fix

Metadata:

```json
{
  "metadata": {
    "github_event": "workflow_run",
    "check_conclusion": "failure",
    "repo_risk": "low"
  }
}
```

Expected model:

```text
glm-5.2
```

### Pattern 5: GLM Failure Escalation

Metadata:

```json
{
  "metadata": {
    "retry_count": 2,
    "test_failed_twice": true
  }
}
```

Expected model:

```text
opus-4.8
```

## Verification

### Health Check

```bash
curl -fsS http://127.0.0.1:4000/health/readiness
```

### Direct GLM Probe

Send a low-risk execution task:

```bash
curl -sS http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "coding-auto",
    "messages": [
      {"role": "user", "content": "Generate unit tests for a simple parser."}
    ],
    "max_tokens": 64,
    "metadata": {
      "task_type": "unit_test_generation",
      "repo_risk": "low",
      "context_tokens": 1000
    }
  }' -D -
```

Check response headers:

```text
x-litellm-model-group: glm-5.2
```

### Direct Opus Probe

Send an architecture planning task:

```bash
curl -sS http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "coding-auto",
    "messages": [
      {"role": "user", "content": "Design the architecture for a policy simulation engine with extensible policy stages and audit output."}
    ],
    "max_tokens": 64,
    "metadata": {
      "repo_risk": "low",
      "context_tokens": 1000
    }
  }' -D -
```

Check response headers:

```text
x-litellm-model-group: opus-4.8
```

### Spend Log Verification

If LiteLLM uses Postgres, inspect `LiteLLM_SpendLogs`.

Example:

```bash
cd /root/LiteLLM
docker compose exec -T db psql -U llmproxy -d litellm -P pager=off -F $'\t' -A -c '
SELECT
  to_char("startTime", '\''YYYY-MM-DD HH24:MI:SS'\'') AS utc_time,
  model,
  model_group,
  custom_llm_provider,
  prompt_tokens,
  completion_tokens,
  request_duration_ms,
  ROUND(spend::numeric, 6) AS spend,
  metadata->'\''model_map_information'\''->>'\''model_map_key'\'' AS map_key
FROM "LiteLLM_SpendLogs"
WHERE "startTime" > now() - interval '\''30 minutes'\''
ORDER BY "startTime" DESC
LIMIT 30;
'
```

Interpretation:

- `model` is the actual upstream model.
- `model_group` is the LiteLLM model group that served the request.
- `map_key` helps confirm which configured deployment was selected.

If `model_group` says `claude-opus-4-6` but `model` says `openai/glm-5.2`, then the alias is not actually using Opus. It is only a client-facing name mapped to GLM.

## Troubleshooting

### The Callback Does Not Load

Symptoms:

- LiteLLM starts without `cc_glm52_guard`.
- Logs show import errors.
- Requests stay on the configured default model.

Check:

1. The plugin file is mounted into the container.
2. The callback path is correct:

   ```yaml
   callbacks:
     - cc_glm52_guard.proxy_handler_instance
   ```

3. The container can import the file:

   ```bash
   docker compose exec -T litellm python -c "import cc_glm52_guard; print(cc_glm52_guard.proxy_handler_instance)"
   ```

### Requests Do Not Route To Opus

Check the spend logs.

If you see:

```text
model_group=claude-opus-4-6
model=openai/glm-5.2
```

then the alias is mapped to GLM, not Opus.

Make sure the plugin is installed and the premium model group exists:

```yaml
model_name: opus-4.8
```

Make sure `CC_GLM52_PREMIUM_MODEL` points to that group:

```bash
CC_GLM52_PREMIUM_MODEL=opus-4.8
```

### Opus OAuth Does Not Work

Server-side LiteLLM routing generally needs server-side credentials. Claude desktop or Claude Code OAuth credentials may not be usable by LiteLLM as a backend provider credential.

Use one of:

- Anthropic API key, if supported in your environment.
- OpenRouter key for an Anthropic Opus route.
- Another provider-supported Opus-compatible deployment.

Then expose it as the LiteLLM model group `opus-4.8`.

### GLM And Opus Switch Too Often

Use session metadata:

```json
{
  "metadata": {
    "session_id": "coding-session-123",
    "session_turn": 10,
    "previous_internal_route_model": "opus-4.8",
    "last_model_switch_turn": 8,
    "model_switch_count": 1,
    "premium_sticky_until_turn": 13,
    "glm_success_streak": 0
  }
}
```

Tune:

```bash
CC_GLM52_SWITCH_COOLDOWN_TURNS=3
CC_GLM52_PREMIUM_STICKY_TURNS=5
CC_GLM52_MAX_SWITCHES_PER_SESSION=2
CC_GLM52_GLM_DOWNGRADE_SUCCESS_STREAK=2
```

### Context Is Lost After A Switch

This is expected if the caller does not replay context.

The plugin cannot transfer hidden model state. Ensure the next request includes:

- The visible conversation.
- Relevant files or summaries.
- Tool results.
- The previous model's visible design or attempt summary.

For context failure escalation, set:

```json
{
  "metadata": {
    "canonical_context_replayed": true
  }
}
```

### LiteLLM Rejects Router Settings

Different LiteLLM versions accept different router settings. Check startup logs:

```bash
docker compose logs --tail=200 litellm
```

If a key is not accepted, remove that key or upgrade LiteLLM.

For LiteLLM `1.83.14`, the following are valid:

- `routing_strategy`
- `enable_pre_call_checks`
- `num_retries`
- `max_fallbacks`
- `cooldown_time`
- `allowed_fails`
- `fallbacks`
- `context_window_fallbacks`

## Operational Best Practices

1. Expose `coding-auto` to users, not provider-specific model names.
2. Keep the LiteLLM master key admin-only.
3. Mint virtual keys per team or service.
4. Restrict virtual keys to the model aliases they need.
5. Use spend logs to verify actual upstream models.
6. Treat model switching as a request-boundary event, not an in-stream handoff.
7. Keep Opus for high-value reasoning and GLM for testable implementation.
8. Do not over-route small coding tasks to Opus.
9. Keep fallback and context-window fallback configured at the LiteLLM router level.
10. Keep plugin audit metadata for dashboards and incident review.

## Minimal End-To-End Deployment Checklist

1. LiteLLM is healthy:

   ```bash
   curl -fsS http://127.0.0.1:4000/health/readiness
   ```

2. GLM model group works:

   ```text
   glm-5.2
   ```

3. Opus model group works:

   ```text
   opus-4.8
   ```

4. Plugin file is mounted into LiteLLM.
5. Callback is listed in `litellm_settings.callbacks`.
6. Router settings include `enable_pre_call_checks`, `fallbacks`, and `context_window_fallbacks`.
7. Claude Code uses:

   ```text
   ANTHROPIC_BASE_URL=http://127.0.0.1:4000
   ANTHROPIC_MODEL=coding-auto
   ```

8. A low-risk coding probe routes to `glm-5.2`.
9. An architecture/security probe routes to `opus-4.8`.
10. Spend logs confirm actual upstream models, not only alias names.

## Summary

This plugin turns LiteLLM into a server-side smart router for coding agents.

The default operating model is:

```text
coding-auto -> GLM for normal implementation
coding-auto -> Opus for premium reasoning and hard fallback
coding-auto -> vision model for image requests
```

The plugin's main benefit is not just cost reduction. It makes routing explainable, auditable, and controllable while preserving a simple client experience for Claude Code users.
