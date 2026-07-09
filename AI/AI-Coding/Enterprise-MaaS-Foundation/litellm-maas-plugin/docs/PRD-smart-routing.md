# PRD: MaaS AI Coding Smart Router

## 1. Goal

Expose stable virtual model names to developers and route each request server-side by workload, risk, context size, modality, budget, and capacity.

Developer tools call:

- `meli-coding-fast`
- `coding-auto`
- `meli-coding-deep`
- `meli-coding-review`
- `meli-coding-vision`

The LiteLLM gateway chooses one production model per request. It does not run anonymous evaluation, shadow traffic, or dual production calls.

## 2. Model Positioning

| Pool | Role | Default Use |
| --- | --- | --- |
| GLM-5.2 | High-throughput execution pool | unit tests, docs, repo summary, CI fixes, normal code generation, batch refactors |
| Opus / Sonnet | Premium reasoning and judgment | architecture, complex debugging, security review, production incidents, high-risk PR review |
| Vision model | Image understanding | screenshot, UI, image blocks before downstream code work |

GLM-5.2 is not a blanket Opus replacement. It is the default low-cost execution pool for verifiable coding work. Premium models remain reserved for high-value reasoning and high-risk judgment.

## 3. Inputs

The gateway consumes request body fields and `metadata`:

| Signal | Examples |
| --- | --- |
| tool source | `tool=claude-code`, `tool=ci-bot` |
| task type | `unit_test_generation`, `ci_auto_fix`, `pr_review`, `architecture_planning` |
| input modality | text, image block, screenshot |
| context size | `context_tokens=85000` |
| repo risk | `repo_risk=low|medium|high|restricted`, `repo_tags=[payment,pci]` |
| budget | `budget_state=normal|near_limit|limited|exhausted` |
| SLA | `latency_slo=interactive|batch` |
| capacity | `glm_available`, `tpm_queue_delay_ms`, `latency_p95_ms`, `model_error_rate` |
| fallback | `retry_count`, `test_failed_twice` |

If `task_type` is absent, the first release uses deterministic prompt rules for tests, CI, review, docs, architecture, security, incident, and image detection.

GitHub-oriented classification follows this priority:

1. Explicit `metadata.task_type` from the tool or platform.
2. GitHub workflow signals:
   - `github_event`, `github_action`, `check_name`, `check_conclusion`, `check_status`
   - `alert_type`, `alert_severity`
   - `actor=dependabot[bot]`, `dependabot_security_update`
   - `labels`, `github_labels`
   - `codeowners_required`, `merge_conflict`
3. Changed file paths from `changed_files`, `file_paths`, `modified_files`, `added_files`, or `removed_files`.
4. Prompt pattern fallback.

Rationale from GitHub practices:

- CODEOWNERS is the repository-native ownership and review-routing signal for PRs.
- Status checks and workflow runs are the native CI failure signal.
- Code scanning, secret scanning, and Dependabot alerts are first-class security signals.
- Repository/path-specific Copilot instructions show that path-specific context matters for code review and task handling.

The plugin writes `task_signal.source` and `task_signal.evidence` so routing decisions can be audited and tuned.

## 4. Routing Policy

Hard rules:

1. Image content routes to `vision-openrouter`.
2. `meli-coding-deep` routes to `opus-4.8`.
3. Architecture, complex debugging, production incidents, and security review route to `opus-4.8`.
4. High or restricted repo risk routes to `opus-4.8` unless a future explicit data-safe documentation exception is added.
5. Context above 196K is not sent raw to GLM-5.2; it routes to premium planning or a future RAG/split path.
6. If a task starts on GLM-5.2 and context packing later proves impossible,
   the next request must set `context_unsegmentable=true`,
   `context_split_failed=true`, or `compression_failed=true`. The gateway then
   routes to `opus-4.8` with `route_reason=context_unsegmentable_to_premium`.
7. Fallback signals route to `opus-4.8`: retry count >= 2, tests failed twice, p95 latency > 60s, model error rate > 3%, or queue delay > 30s.

Execution rules:

| Workload | Low/Medium Risk Default | Upgrade Condition |
| --- | --- | --- |
| unit test generation | GLM-5.2 | repeated failure, high-risk repo, over context limit |
| documentation / repo summary | GLM-5.2 | over context limit, high-risk repo |
| CI auto-fix | GLM-5.2 | repeated failure, production hotfix, high-risk repo |
| normal code generation | GLM-5.2 | cross-service critical logic, high-risk repo |
| batch refactoring | GLM-5.2 | architecture planning needed first |
| PR review | GLM for low risk, Opus for high risk | payment, auth, risk, PCI, security tags |

Budget rule:

- For execution tasks, `budget_state=near_limit|limited|exhausted` prefers GLM-5.2 unless a hard premium rule applies.

Capacity rule:

- If GLM capacity is unavailable for an interactive request, route to premium.
- Batch requests stay eligible for the GLM execution pool and queueing policy.

## 5. Context Policy

| Range | Policy |
| --- | --- |
| <= 160K | GLM direct |
| 160K-196K | compression required |
| > 196K | RAG, file selection, summary compression, task split, or premium planning |

The plugin writes `metadata.cc_glm52_guard.context_policy` for every request.

Switching method for a GLM-started task:

1. First request calls `coding-auto`; low/medium-risk execution work can run on GLM-5.2.
2. The context manager tries repo map, file selection, summary compression, or task split.
3. If that fails or the task is semantically indivisible, the caller retries the same logical task with one of:
   - `metadata.context_unsegmentable=true`
   - `metadata.context_split_failed=true`
   - `metadata.compression_failed=true`
4. The router switches the retry to `opus-4.8` and records `fallback_reason` plus `route_reason`.

Context preservation rule:

- The gateway cannot transfer hidden model state from GLM-5.2 to Opus-4.8.
- The retry must replay the full canonical request context or a formally approved packed context.
- Set `metadata.canonical_context_replayed=true` when the retry contains the complete source context.
- Optionally set `metadata.glm_attempt_summary` to carry a concise summary of what the GLM attempt already discovered.
- The plugin injects a `[Context handoff]` system note on this escalation path and writes `context_handoff` audit fields.
- If `canonical_context_replayed` is missing, the audit includes `warning=caller_must_replay_full_canonical_context_to_avoid_context_loss`.

This follows the production pattern used by LLM gateways: fallback is a new request to another model group, so context continuity is achieved by replaying a stable prompt/context prefix, not by moving model-internal state.

Switch suppression rule:

- The router should not oscillate between GLM-5.2 and Opus-4.8 on adjacent turns.
- Hard upgrades still win immediately: security, high-risk repo, >196K raw context, vision, explicit deep mode, and fallback failures.
- Once a session escalates to Opus-4.8 for context or reasoning, the caller should pass session state:
  - `session_id`
  - `session_turn`
  - `previous_internal_route_model`
  - `last_model_switch_turn`
  - `model_switch_count`
  - `premium_sticky_until_turn`
  - optional `glm_success_streak`
- The plugin suppresses Opus -> GLM downgrades while the premium sticky window or switch cooldown is active.
- Even after cooldown, downgrade requires `glm_success_streak >= 2` or explicit `allow_premium_downgrade=true`.
- If `model_switch_count` reaches the configured max, the plugin keeps the previous model unless a hard route requires escalation.
- Suppression is audited in `model_switch_policy` and `commercial_telemetry.model_switch_suppressed`.

Default stabilization values:

| Setting | Default | Env |
| --- | --- | --- |
| switch cooldown | 3 turns | `CC_GLM52_SWITCH_COOLDOWN_TURNS` |
| premium sticky window | 5 turns | `CC_GLM52_PREMIUM_STICKY_TURNS` |
| max switches per session | 2 | `CC_GLM52_MAX_SWITCHES_PER_SESSION` |
| GLM downgrade success streak | 2 | `CC_GLM52_GLM_DOWNGRADE_SUCCESS_STREAK` |

## 6. Telemetry

Each request receives `metadata.cc_glm52_guard` with:

- external and internal model
- virtual model
- route reason
- task type
- repo risk and tags
- budget state
- latency SLO
- capacity state
- fallback flag and reason
- context policy and token estimate
- search and multimodal flags
- `commercial_telemetry` for PoC dashboards:
  - team, project, repo, language, cost center
  - workload and model pool
  - estimated and declared context tokens
  - reserved TPM and queue delay
  - p95 latency and model error rate
  - retry/test/CI/acceptance state
  - relative cost vs premium model

Dashboards should derive:

- GLM coverage ratio
- premium model ratio
- fallback rate and fallback cost
- p95 latency by workload
- GLM TPM utilization
- cost per accepted task

## 7. Commercial Success Metrics

30-day MELI pilot:

- GLM coverage ratio: 40%-60%
- fallback rate: 20%-35%
- cost per accepted task: 20%+ reduction
- p95 latency meets workload SLO
- reserved TPM curve available for procurement

Cost model:

```text
GLM-routed cost =
  GLM success rate * GLM cost
  + fallback rate * (GLM cost + premium cost)

overall savings =
  1 - smart-routing total cost / Opus-only total cost
```

The historical GLM-vs-Opus cost ratio is only an initial assumption. GLM-5.2 must be measured during PoC using accepted tasks, not raw token price alone.

## 8. Runtime Contract

Example request:

```json
{
  "model": "coding-auto",
  "messages": [{"role": "user", "content": "Generate unit tests for the changed files."}],
  "metadata": {
    "tool": "claude-code",
    "team": "marketplace",
    "project": "checkout",
    "repo": "payments-service",
    "language": "java",
    "task_type": "unit_test_generation",
    "repo_risk": "medium",
    "input_modality": "text",
    "context_tokens": 85000,
    "latency_slo": "batch",
    "cost_center": "marketplace-platform"
  }
}
```
