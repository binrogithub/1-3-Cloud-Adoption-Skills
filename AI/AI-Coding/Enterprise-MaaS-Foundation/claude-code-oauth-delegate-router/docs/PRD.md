# PRD: OAuth-Orchestrated Hybrid Router (Task-Level Delegation)

Status: v1.1 · 2026-07-17 · deployed and validated end-to-end on a live single-host deployment (Appendix C)
Repo path: `AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-oauth-delegate-router/docs/PRD.md`
Related: [`litellm-maas-auto-plugin/docs/PRD-smart-routing.md`](../../litellm-maas-auto-plugin/docs/PRD-smart-routing.md) (taxonomy source). The removed Claude Code forky router is retained here only as a historical transport-layer comparison.

## 1. Goal

One entry point — plain `claude` with the user's Claude.ai OAuth subscription, transport completely untouched — that:

- executes **premium-class** work in-session on Claude (architecture planning, complex debugging, security review, production incidents, high-risk PR review, image/screenshot input, >196K raw context);
- **delegates execution-class** work (unit tests, docs, CI fixes, normal codegen, batch refactors, low/medium-risk review) as discrete sub-tasks to an isolated `claude-glm` client → LiteLLM :4000 → GLM-5.1 on Huawei MaaS;
- **delegates whole workflows** — the token-burn class: multi-agent fan-out, repo-wide batch pipelines, recurring loops, scheduled/CI headless runs — so that agent-turn multiplication burns MaaS tokens, never subscription quota (§6.3);
- carries the routing policy in **Claude Code memory/CLAUDE.md** (model-readable policy) enforced by **hooks** (deterministic guardrails), not by a network shim.

The split happens at the **task layer** (who does the work), not the **transport layer** (where requests go). This is the structural difference from forky, and it is what makes the three chronic problems disappear by construction rather than by mitigation (§5).

```
 user ──► claude  (official client, OAuth, ZERO middleware) ──────────► api.anthropic.com
            │  role: premium pool + classifier + orchestrator                (Opus, subscription)
            │  policy: CLAUDE.md / memory + UserPromptSubmit hook hints
            │
            │  execution-class task  ──►  Bash: delegate "<brief>"
            │                                   │
            │                              claude-glm -p   (isolated CLAUDE_CONFIG_DIR,
            │                                   │            LiteLLM virtual key, headless)
            │                                   ▼
            │                              LiteLLM :4000 ── anthropic_stream_guard
            │                                   │           context_window_guard
            │                                   │           rolling_budget_hook
            │                                   │           (optional) cc_glm52_guard telemetry
            │                                   ▼
            │                              GLM-5.1 (Huawei MaaS, ap-southeast-1)
            ▼
        tool_result (structured summary + diff) appended to the OAuth session
```

## 2. Positioning vs Existing Assets

| | Gateway smart router (`cc_glm52_guard`) | removed forky transport router | **This PRD** |
|---|---|---|---|
| Split layer | gateway, per-request | local proxy, per-phase (plan/vision/exec) | orchestrator, per-task |
| Premium pool | API-key model in LiteLLM (OpenRouter/Anthropic) | OAuth token replayed by forky process | the OAuth session itself |
| OAuth ToS exposure | none (OAuth unused) | **yes** — third-party process reads and replays the token | **none** — token never leaves the official client |
| Classifier | code heuristics + metadata | request shape (tools/images/hook sentinel) | frontier model + repo-native signals, hook hints |
| Anthropic prompt cache | n/a | re-paid on every phase switch | **never invalidated** (append-only session) |
| Protocol patches needed | stream guard (GLM side) | 3 forky patches + rebase burden | stream guard (GLM side) only |
| Best for | N clients, central budget/audit | single dev wanting automatic in-session split | single dev/demo wanting compliance + subscription safety |

The gateway smart router remains the correct enterprise multi-client architecture. This PRD is the single-operator architecture where the subscription is the premium pool.

## 3. Task Classification Policy

Taxonomy inherited from `PRD-smart-routing.md` §2/§4, re-anchored to the orchestration layer.

**Premium — stays in-session (OAuth Claude):**

| Class | Signal (orchestrator-visible) |
|---|---|
| architecture_planning | plan requests, cross-service design, tech selection; plan mode |
| complex_debugging | root-cause work spanning >2 subsystems, race conditions, heisenbugs, repeated failed fixes |
| security_review | auth/crypto/secrets/injection surfaces; security-labeled issues |
| production_incident | live outage, rollback decisions, anything tagged incident |
| pr_review (high risk) | paths or tags: payment, auth, pci, infra, migration; CODEOWNERS-protected paths; `repo_risk=high\|restricted` |
| image / screenshot | any image block in the task input (GLM-5.1 has no vision) |
| >196K raw context | task cannot be briefed under GLM's 196,608-token input limit and resists splitting |

**Execution — delegated (`claude-glm` → LiteLLM → GLM-5.1):**

| Class | Notes |
|---|---|
| unit_test_generation | acceptance = tests pass locally |
| documentation / repo summary | acceptance = files written |
| ci_auto_fix | bounded diff, CI green |
| normal code generation | single-module, verifiable, low/medium risk |
| batch refactoring | mechanical, after premium planning if needed |
| pr_review (low/medium risk) | summary + findings list returned |
| mechanical transforms | migrations, format conversions, log analysis |
| **multi-agent workflow fan-out** | sub-orchestrated on GLM (§6.3 W1) — subagent turns are the single largest token multiplier |
| **repo-wide batch pipelines** | N-item manifests via the fan-out runner (§6.3 W2) |
| **repo-wide analysis / review passes (low/med risk)** | GLM-twin skills replace built-in burners (§6.3 W3) |
| **recurring loops, scheduled routines, CI headless runs** | zero-OAuth flows — invoke `claude-glm` directly (§6.3 W4) |

Workflow rule of thumb: the **plan** of a workflow (how to split scope, what the stage gates are) and the final **synthesis/review** are premium; every fan-out worker turn in between is execution.

A structural advantage over gateway classification: the orchestrator classifies with **first-hand repo signals** — it reads the changed files, git history, labels, CODEOWNERS itself — where a gateway must infer the same from prompt text and caller-supplied metadata. The GitHub signal priority in PRD-smart-routing §3 is implemented here by the model actually looking.

## 4. Non-Goals

- No transport-layer switching of the OAuth session. Plan mode, thinking, vision all stay native.
- No automatic mid-conversation backend swap. A task is briefed, delegated, and returns as a tool result.
- No multi-client key management (that is the gateway smart-router product).
- No attempt to reach >GLM quality on delegated work; quality gaps are handled by the escalation ladder (§7), not by tuning.

## 5. Why the Three Chronic Problems Are Solved *by Construction*

### 5.1 Subscription OAuth terms risk → eliminated

The OAuth token is read and presented **only by the official `claude` binary**, exactly as in a vanilla install. No proxy reads `~/.claude/.credentials.json`; no third-party process ever holds or replays the token; `ANTHROPIC_BASE_URL` of the OAuth client is never set. The delegate call is an ordinary Bash subprocess — from Anthropic's side the session is indistinguishable from any normal Claude Code session that runs builds and tests. The GLM path authenticates with a LiteLLM virtual key. **Compliance invariant (verifiable): no process other than `claude` opens `credentials.json`; no process other than `claude` connects to `api.anthropic.com`** (§12 acceptance test A).

### 5.2 Prompt-cache burn / subscription rate-limit burn → eliminated

The OAuth conversation is **append-only on a single backend**. Every Anthropic request extends the same cached prefix; delegation results enter as `tool_result` blocks — the cheapest possible append. There is no cross-backend replay of session history in either direction:

- downward: the delegate receives a **compact self-contained brief** (goal, files, constraints, acceptance), not the session transcript;
- upward: the orchestrator receives a **structured summary + diff**, not the delegate transcript.

Worst case cache cost: a delegation that runs longer than the 5-minute cache TTL causes one prefix re-write on the next turn — *identical* to any long-running test suite or build in vanilla Claude Code, i.e. this design adds **zero** new cache behavior. Compare: forky re-pays the full input on every plan↔exec transition; a per-request shim re-pays on nearly every turn.

Subscription burn therefore scales with **number of decisions** (plan, classify, review results), not **number of generated tokens** — generated bulk lands on GLM at MaaS prices.

### 5.3 Protocol edge cases → eliminated on the OAuth path, contained on the GLM path

All three forky patches (system/developer role normalization, cache-TTL ordering, vision rerouting) existed **because a middleware edited and replayed requests between two protocol dialects**. With zero middleware on the OAuth path, that entire failure class is gone — thinking signatures, cache markers, role shapes are handled end-to-end by the official client against the official API, and Claude Code version upgrades cannot break a proxy that doesn't exist.

The GLM path is a **native Claude Code client speaking unmodified Anthropic protocol to LiteLLM**; its known GLM/MaaS edge cases are already productized in `anthropic_stream_guard` (thinking/reasoning strip → keeps requests on `/chat/completions`; SSE re-sequencing; terminal-event synthesis; interjection amplification; unparsed-tool-markup counter) and `context_window_guard` (196K trim, image stub, vision reroute) — deployed, metered plugins with Prometheus counters. No client-side patches, nothing to rebase.

## 6. Mechanism

### 6.1 Components

| # | Component | What it is |
|---|---|---|
| C1 | `claude-glm` wrapper | `~/.local/bin/claude-glm`: sets `CLAUDE_CONFIG_DIR=$HOME/.claude-glm`, `ANTHROPIC_BASE_URL=http://127.0.0.1:4000`, `ANTHROPIC_API_KEY=<virtual key>`, `ANTHROPIC_MODEL` + `ANTHROPIC_SMALL_FAST_MODEL` → LiteLLM aliases, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` (headroom under GLM's 196K input limit), `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. Env scoped **inside the wrapper only** — never a shell profile. Key pre-approved in the isolated `.claude.json` (reuse `configure-claude-code.sh --print-env` to generate; run under the isolated config dir). |
| C2 | `delegate` script | Thin runner around `claude-glm -p`: builds the brief, sets headless permissions (`--permission-mode acceptEdits`, tool allowlist, workspace-scoped), timeout, retries ≤ 2, writes an audit record (§10), returns structured JSON. Supports `--resume <glm-session>` for iterative rounds on the same work item. |
| C3 | Routing policy in memory | A static policy block (Appendix A) installed into the orchestrator's `~/.claude/CLAUDE.md` (deterministically loaded, cache-stable) plus an auto-memory entry pointing at it. Static content only — variable content in system prompt would invalidate cache (§5.2). |
| C4 | Hooks (deterministic layer) | `UserPromptSubmit`: regex classifier over PRD signal words emits a one-line advisory (`route-hint: execution-class → delegate`) into the turn — deterministic, cache-safe (user-turn content), zero model dependence. `Stop`: appends per-turn route audit. Optional strict mode: `PreToolUse` gate that blocks batch `Edit/Write` bursts in-session unless a `~/.claude-hybrid/premium` sentinel exists (operator opt-in). |
| C5 | `glm-executor` subagent (optional) | `.claude/agents/glm-executor.md`: a named agent whose sole job is to call C2 and relay results. Benefit: delegation plumbing and bulky outputs live in the subagent transcript, keeping the main context (and its cache) even smaller. |
| C6 | Server plugins | `anthropic_stream_guard` + `context_window_guard` (required), `rolling_budget_hook` with `BUDGET_TIER_KEY` on the delegate key, optional `cc_glm52_guard` for route telemetry fields on the GLM side. Installed by existing scripts (`server/install-litellm-plugin.sh`). **Plus the `claude-*` wildcard model route — mandatory for workflows**: it is what maps every internal model name a sub-orchestrator's agents request (opus/sonnet/haiku variants) onto glm-5.1 (§6.3 W1). |
| C7 | `workflow` runner | Fan-out engine over C2: consumes a manifest (mode, items[], brief template, concurrency, verify_cmd, isolation), launches parallel `claude-glm -p` workers with a concurrency governor and 429/TTFT backoff, enforces workspace isolation, aggregates per-item results to JSONL + a summary report, hands failed items back as the premium remainder (§7). |
| C8 | GLM-twin skill pack | Project skills that re-implement built-in token burners on the GLM path: `glm-review` (repo/PR review via W1/W2), `glm-repo-summary`, `glm-test-batch`. Installed into the orchestrator's skills dir; policy maps built-in burners to their twins for low/medium-risk work (§6.3 W3). |

### 6.2 Delegation contract

**Brief (orchestrator → delegate)** — must be self-contained; assume the delegate sees *nothing* of the session:

```json
{
  "task_type": "unit_test_generation",
  "goal": "Add pytest coverage for src/billing/rounding.py::allocate",
  "scope": ["src/billing/rounding.py", "tests/"],
  "constraints": ["no new deps", "match existing test style in tests/test_billing.py"],
  "acceptance": "pytest tests/ -k rounding exits 0",
  "context_notes": "allocate() distributes cents remainder; see docstring",
  "attempt": 1, "max_attempts": 2
}
```

**Result (delegate → orchestrator):**

```json
{
  "status": "success | failure | needs_escalation",
  "summary": "3 tests added, all pass",
  "files_changed": ["tests/test_rounding.py"],
  "verification": {"cmd": "pytest -k rounding", "exit": 0},
  "glm_session": "…", "tokens": {"in": 41200, "out": 3800}, "duration_s": 210
}
```

This is the `canonical_context_replayed` / `glm_attempt_summary` contract of PRD-smart-routing §5, realized naturally: the brief **is** the canonical context; the summary **is** the attempt record.

### 6.3 Workflow delegation — the token-burn class

**Problem.** Workflows multiply context: a multi-agent fan-out spawns N subagents, each with its own conversation; a repo-wide pipeline touches hundreds of files; a loop repeats indefinitely. In a vanilla OAuth session all of that burn lands on the subscription, and Claude Code offers no native way to point a subagent at a different backend — the Agent/Task tool always uses the session's own endpoint. Workflows are therefore delegated **as whole units**, using one of four mechanisms chosen by workflow shape:

**W1 — Whole-workflow sub-orchestration (preferred for agentic workflows).**
Delegate the entire workflow as a single brief. The delegate is a *full Claude Code runtime*: inside its own session it plans, spawns its own native subagents (Task tool, custom agents, skills), runs tests — and every internal request, **including all subagent turns**, goes to LiteLLM, where the `claude-*` wildcard route maps whatever internal model names its agents request onto glm-5.1. Sub-agent fan-out thereby burns only MaaS tokens; the OAuth session receives exactly one `tool_result` with the final report.
- Brief must include **stage gates** ("run the test suite after each module; stop and report on 2 consecutive failures") so errors don't propagate silently down a long agentic chain.
- Server prerequisites: wildcard route + `anthropic_stream_guard` (already the auto-plugin server baseline); `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` in the wrapper keeps the sub-orchestrator inside GLM's 196K window, with `context_window_guard` as the hard backstop.

**W2 — Fan-out runner (preferred for embarrassingly parallel batches).**
When items are independent and uniform (N files × same transform), agentic planning inside the delegate is waste. The orchestrator emits a **manifest**; the C7 runner executes it deterministically:

```json
{
  "workflow": "unit-tests-batch",
  "mode": "fanout",
  "items": [{"scope": ["src/billing/rounding.py"]}, {"scope": ["src/billing/ledger.py"]}],
  "brief_template": "§6.2 brief with ${scope} substituted",
  "concurrency": 3,
  "verify_cmd": "pytest -q ${scope_tests}",
  "isolation": "disjoint"
}
```

- **Concurrency governor**: default 3 parallel workers; backoff on HTTP 429 and TTFT timeout; the delegate key's rpm/tpm caps are the hard ceiling (glm-5.1 per-key rpm 30 — size worker count to capacity, don't fight the limiter).
- **Workspace isolation**: `disjoint` (orchestrator plans non-overlapping file scopes — preferred) or `worktree` (each worker in its own `git worktree`, runner merges at the end). Two workers never touch the same path.
- **Output**: per-item JSONL + aggregate report; failed items form the **premium remainder** (§7).

**W3 — GLM-twin skills for built-in burners.**
Built-in workflow commands (`/code-review` deep passes, `/security-review`, `/init` on large repos) execute on the session's own backend and cannot be re-pointed. Ship GLM twins as project skills built on W1/W2 — `glm-review`, `glm-repo-summary`, `glm-test-batch` — and let policy map: low/medium-risk review → `glm-review`; high-risk review and incident analysis → built-in, in-session (premium by classification, §3).

**W4 — Zero-OAuth flows.**
Recurring loops, cron/scheduled routines, and CI headless jobs never involve the OAuth client at all: they invoke `claude-glm -p` or the C7 runner directly. CI gets its **own virtual key** (separate budget, separate audit trail). The rolling-budget hook doubles as the runaway-loop circuit breaker — a loop that exceeds its window gets 429s, stops, and shows `budget_exhausted` in the audit instead of silently draining quota.

**Validated precedent.** The forky skill's multi-agent example ran 161 requests / 863K input + 9.5K output tokens entirely on GLM with zero premium execution calls — same architecture shape. This PRD upgrades the workers from bare `curl` completions to full Claude Code instances with tools, and moves the premium/execution split from a transport proxy to the orchestrator.

**Cost shape.** For a workflow of N worker turns and one plan + one synthesis, subscription burn is O(plan + synthesis) regardless of N; MaaS burn is O(N). The token-burn class is exactly where this design's savings are largest — and where forky's per-phase split and the vanilla setup are weakest.

## 7. Escalation Ladder & Switch Suppression

Mirrors PRD-smart-routing §4 fallback rules and §5 stabilization, at task granularity:

1. Delegate attempt 1 → on failure, delegate attempt 2 **with the failure evidence appended to the brief** (`--resume` same GLM session).
2. Two failures, or `verification` failing twice, or delegate timeout/429 (budget/capacity) → **orchestrator takes the task in-session** (= premium escalation). Audit `fallback_reason`.
3. **Stickiness**: a work item escalated to premium is never re-delegated (per-item, permanent — stricter than the gateway's turn-window cooldown because task identity is known here).
4. **No oscillation is possible** by construction: the OAuth session never "downgrades" — it only chooses per new task. `CC_GLM52_*` cooldown/sticky machinery is unnecessary at this layer.
5. Budget rule: delegate key 429 (rolling budget) → batch work queues, interactive work escalates with `fallback_reason=budget_exhausted`.
6. Capacity rule: TTFT timeout (LiteLLM `stream_timeout`) twice → escalate with `fallback_reason=glm_capacity`.
7. **Workflow remainder rule**: failed manifest items collect into the premium remainder, which the orchestrator finishes in-session after the batch completes. If the remainder exceeds ~30% of items, abort the workflow and reclassify — the work was probably premium-class from the start (mirrors PRD-smart-routing's "GLM is not a blanket replacement" positioning).

## 8. Context Policy

| Range (brief size) | Policy |
|---|---|
| ≤ 160K est. tokens | delegate directly |
| 160K–196K | orchestrator must compress the brief first (file selection, summarization) — it is good at exactly this |
| > 196K or unsplittable | premium in-session (`route_reason=context_above_glm_limit`) |

- Images/screenshots never enter a brief (premium by policy); `context_window_guard`'s image stub is the server-side backstop if one slips through.
- Server-side `context_window_guard` remains the hard guarantee under GLM's 196,608 input limit.
- The orchestrator's own session uses native Claude Code compaction — unchanged.

## 9. Budget & Capacity

- Delegate virtual key minted with `tpm/rpm` caps and `BUDGET_TIER_KEY` (e.g. `5h:12`), via `bootstrap_finops_team.py` or `/key/generate`. All GLM spend is attributed to that key in `LiteLLM_SpendLogs` → Grafana.
- Subscription-side spend is bounded by design (§5.2); observable via Claude Code `/cost` and the Stop-hook audit.
- Parallel delegations allowed (background Bash); the key's rpm/tpm caps are the concurrency governor.

## 10. Telemetry & Audit

Local audit log `~/.claude-hybrid/route-audit.jsonl`, one record per routed task:

```
{ts, task_type, route: "premium|glm", route_reason, attempt, outcome,
 glm_tokens_in/out, duration_s, fallback_reason?}
```

- GLM side: existing Prometheus counters (`asg_*`, `cwg_*`, spend logs), optional `metadata.cc_glm52_guard` fields if the guard is mounted.
- A `route-stats` script aggregates: GLM coverage ratio, escalation rate, cost per accepted task — same KPI surface as PRD-smart-routing §6/§7 so dashboards stay comparable.

## 11. KPIs

| Metric | Target | Notes |
|---|---|---|
| GLM coverage (generated tokens) | 40–70% | delegated output tokens / total output tokens |
| **Workflow token coverage** | ≥ 90% on GLM | for workflow-class tasks, subscription tokens ≈ plan + synthesis only |
| Escalation (fallback) rate | 15–35% | failures are expected; two attempts max caps waste |
| Subscription turn share | premium classes ≈ 100% in-session; execution classes ≤ orchestration turns only | from audit log |
| Anthropic cache continuity | no cache resets attributable to routing | `/cost` cache-read ratio stable vs vanilla baseline |
| OAuth compliance invariant | 0 violations | acceptance test A, re-run on every change |
| GLM-path protocol repairs | `asg_*` counters present, client errors 0 | stream guard working as designed |

## 12. Rollout & Acceptance

**Phase 0 — infra**: install `anthropic_stream_guard` (+ CWG) into LiteLLM :4000; mint delegate key; install C1/C2; smoke: `claude-glm -p` tool-call probe (reuse `configure-claude-code.sh --verify` under the isolated dir).

**Phase 1 — advisory**: install C3 policy + C4 hooks (advisory only). Operate one week; read route-stats; tune signal words.

**Phase 2 — optional strict mode**: enable the PreToolUse batch-edit gate if advisory adherence is insufficient.

**Acceptance tests (the three problems, verified not asserted):**

- **A (ToS)**: with the stack running and a delegation in flight — `lsof -i @api.anthropic.com` shows only `claude`; `opensnoop`/`fs_usage` (or `auditd -w ~/.claude/.credentials.json`) shows only `claude` reading credentials; delegate traffic appears only on `127.0.0.1:4000`.
- **B (cache)**: run a scripted session: 10 turns, 3 delegations interleaved; assert Anthropic-side cache-read tokens grow monotonically and no full-prefix re-write occurs except where a tool call exceeded the cache TTL (baseline-equivalent); compare `/cost` versus the same session without delegations.
- **C (protocol)**: `/effort max` heavy-thinking session on `claude-glm` completes without 400/429; `asg_synthesized_terminations_total` / re-sequencing counters move; zero forky-class errors in the OAuth session (trivially true — no middleware — but assert no `ANTHROPIC_*` overrides leaked into the plain `claude` env: `bash -lic 'env | grep ANTHROPIC'` empty).

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Policy drift (orchestrator stops delegating) | premium overuse | C4 hook hints (deterministic), weekly route-stats review, strict mode |
| Over-delegation of premium-class work | quality/risk | premium list is short and explicit; hook regex flags premium signals too; escalation ladder recovers |
| Headless delegate safety | rogue edits | `acceptEdits` + tool allowlist + workspace containment in `~/.claude-glm/settings.json`; no network tools for delegate |
| Brief under-specification | failed attempts | brief schema is mandatory (C2 validates); failure evidence auto-appended on attempt 2 |
| Delegate/orchestrator env bleed | wrong backend | wrapper-scoped env only; acceptance C asserts clean shell; wrapper `unset`s inherited `ANTHROPIC_*`/`CLAUDECODE` |
| Two policy surfaces (orchestrator CLAUDE.md vs delegate CLAUDE.md) | drift | both templates ship in this asset dir, versioned together |
| GLM quality ceiling | rework | max 2 attempts then escalate; coverage KPI targets 40–70%, not 100% |
| Claude Code CLI changes (`-p` flags, hooks API) | breakage | pinned smoke test in verify script; no protocol surface to break (worst case: delegation pauses, OAuth session unaffected) |
| Parallel workers collide on files | corrupted edits | manifest isolation is mandatory: disjoint scopes or per-worker git worktrees; runner refuses overlapping scopes |
| Runaway loop / scheduled job drains MaaS budget | quota exhaustion | per-key rolling budget = circuit breaker (429 halts the loop, audited); CI uses its own key |
| Long agentic chains drift inside sub-orchestrator | wasted batch | stage gates in workflow briefs; stop-on-2-failures; premium remainder ≤30% abort rule |
| Sub-orchestrator context overflow | 400s at 196K | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` + `context_window_guard` backstop |
| MaaS rate limits under fan-out | 429 storms | concurrency governor sized to the key's rpm/tpm; backoff, not retry storms |

## 14. Deliverables

```
claude-code-oauth-delegate-router/
  README.md                          product overview, positioning, quick start
  SKILL.md                           agent-facing deploy / verify / operate workflow
  docs/PRD.md                        this document
  scripts/
    install.sh                       C1 wrapper + isolated config dir + key approval
                                     (reuses ../litellm-maas-auto-plugin/client/configure-claude-code.sh)
    delegate                         C2 runner (brief → claude-glm -p → acceptance check → result JSON + audit;
                                     the execution-agent protocol is embedded as PROTOCOL)
    workflow                         C7 fan-out/sub-orchestration runner (disjoint scopes enforced)
    configure-policy.sh              installs C3 CLAUDE.md block + C4 hook + C5 agent + C8 skills (idempotent)
    route-hint.sh                    C4 UserPromptSubmit advisory hook
    route-stats.sh                   audit aggregation (KPIs §10–11)
    verify.sh                        chains reused probes + functional delegate smoke + isolation invariants
    uninstall.sh                     full reversal; never touches OAuth creds or plain claude
  assets/
    orchestrator-policy.md           Appendix A template
    glm-executor.agent.md            C5 optional subagent
    brief-schema.json                §6.2 delegation brief schema
    manifest-schema.json             §6.3 W2 workflow manifest schema
    skills/glm-review/SKILL.md       C8 GLM-twin: repo/PR review on the execution pool
    skills/glm-repo-summary/SKILL.md C8 GLM-twin: repo-wide summarization
    skills/glm-test-batch/SKILL.md   C8 GLM-twin: batch unit-test generation (W2)
```

Reused (not vendored) from sibling assets: `configure-claude-code.sh` (client
config + TOOL-CALL probe; honors `CLAUDE_CONFIG_DIR`), `tests/live_smoke.py`,
`server/install-litellm-plugin.sh` + both LiteLLM plugins, and the spend-log
SQL verification pattern used by the LiteLLM MaaS plugin probes.

Env table (wrapper-internal only): `CLAUDE_CONFIG_DIR`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY` (virtual key), `ANTHROPIC_MODEL=claude-opus-4-6` (LiteLLM alias → glm-5.1), `ANTHROPIC_SMALL_FAST_MODEL=claude-glm1`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. Delegate runner: `DELEGATE_MAX_ATTEMPTS=2`, `DELEGATE_TIMEOUT_S=1800`, `DELEGATE_AUDIT=~/.claude-hybrid/route-audit.jsonl`.

## Appendix A — Orchestrator policy block (installed into `~/.claude/CLAUDE.md`)

```markdown
# Hybrid routing policy (oauth-delegate-router v1)

You are the premium pool and the router. For every substantive work item, classify first:

**Do in-session (premium):** architecture/design, complex debugging (multi-subsystem,
race conditions, repeated failed fixes), security review, production incidents,
PR review touching payment/auth/pci/infra/migrations or CODEOWNERS-protected paths,
any task whose input includes images/screenshots, any task that cannot be briefed
under ~160K tokens.

**Delegate (execution):** unit test generation, documentation/repo summaries,
CI auto-fixes, single-module code generation, batch/mechanical refactors,
low/medium-risk PR review, format/migration transforms.

**How to delegate:** run `delegate '<brief-json>'` via Bash (schema:
~/.claude-hybrid/brief-schema.json). Briefs must be self-contained — the delegate
sees nothing of this session. Read the returned summary and diff; verify acceptance
yourself before integrating.

**Workflows (token-burn class) — delegate by default:** multi-agent fan-out,
batch pipelines over many files, repo-wide summaries and low/medium-risk review
passes, recurring loops, scheduled/CI runs. Plan the split and stage gates
in-session, then run `workflow '<manifest-json>'` (parallel batches) or
`delegate` with a sub-orchestration brief (agentic workflows). Keep only the
plan and the final synthesis in-session. Use the GLM-twin skills (glm-review,
glm-repo-summary, glm-test-batch) instead of built-in review/summary commands
for low/medium-risk work. High-risk review and incident workflows stay
in-session end-to-end.

**Escalation:** if a delegated item fails twice (or returns needs_escalation,
budget_exhausted, glm_capacity), do it yourself in-session and never re-delegate
that item. For workflows: finish failed items yourself after the batch; if more
than ~30% failed, abort and reclassify the whole workflow as premium. Record
nothing manually — the runner writes the audit log.

**Never:** set ANTHROPIC_* variables in this session, pipe session history into a
brief, or delegate anything on the premium list.
```

## Appendix B — Relationship to `PRD-smart-routing.md`

This PRD implements the same taxonomy with the premium pool relocated from a gateway model entry (`opus-4.8` via API key) to the subscription session itself. Consequences: metadata signals (`repo_risk`, `task_type`) are *observed directly* by the classifier instead of being caller-declared; `context_unsegmentable` becomes an orchestrator judgment; switch-suppression machinery is unnecessary (no transport switching exists). The gateway product remains the multi-client, centrally-audited deployment; both share the LiteLLM plugin layer and KPI definitions, so a pilot can run either (or both) against the same Grafana dashboards.

## Appendix C — First deployment validation (2026-07-16/17, single-host, GLM-5.1)

All §12 acceptance criteria measured on a live deployment (LiteLLM-Huawei-MaaS-Proxy
stack, glm-5.1, Claude Code 2.1.211):

| Check | Result |
|---|---|
| TOOL-CALL probe (client script) | PASS — structured `tool_use` from glm-5.1 |
| live_smoke text / tools / big (185K ctx) | all HTTP 200 (context_window_guard path exercised) |
| Wildcard route (`claude-haiku-4-5-*`) | served by glm-5.1 — W1 subagent fan-out prerequisite confirmed |
| Single delegate (unit tests for one function) | success, acceptance-verified (8 pytest), 40 s, attempt 1 |
| W2 fan-out (2 items, concurrency 2) | 2/2 success, aggregate 59 pytest green, 79 s, empty remainder |
| **E2E orchestrator run** (natural prompt, no routing instructions) | orchestrator autonomously built two workflow manifests (test fan-out + doc item), all `glm … success`, 94 pytest green, docs delivered |
| Acceptance A (ToS) | 46/46 sampled delegate connections → 127.0.0.1:4000 only; zero external; OAuth creds read only by official client |
| Acceptance B (cache) | orchestrator session: 22 turns, input=30, output=11.4K, **cache_read=594K, cache_write=33.7K** — no cache resets across 3 interleaved delegations |
| Acceptance C (isolation/protocol) | plain-shell `ANTHROPIC_*` empty; plain-claude settings have no env block; thinking-param and streaming requests clean |
| Spend attribution | all GLM traffic on the delegate virtual key (e.g. 343K in / 2.9K out for the E2E run) via `LiteLLM_SpendLogs` |
| Escalation rate | 0% across 6 delegated tasks (small sample; KPI window is 30 days) |

Operational notes recorded during validation: regenerating the stack's
`litellm_config.yaml` clobbers the wildcard/callback edits (re-apply after
`generate_config.sh`); `asg_*`/`cwg_*` Prometheus counters register lazily
(absent until the first repair event); `claude -p` inside `ssh bash -s`
heredocs must be invoked with `< /dev/null`.
