# Claude Code OAuth Delegate Router

Task-level hybrid routing for **native Claude Code**: plain `claude` stays on the
user's Claude.ai **OAuth subscription** (transport untouched — no proxy, no token
replay) and acts as premium pool, classifier, and orchestrator; execution-class
work and whole **token-burn workflows** are delegated as discrete sub-tasks to an
isolated `claude-glm` client → LiteLLM :4000 → GLM on Huawei MaaS.

```
user ──► claude (official client, OAuth, ZERO middleware) ─────► api.anthropic.com
           │  premium pool + router (CLAUDE.md policy + UserPromptSubmit hint hook)
           │
           └─ execution/workflow task ──► delegate / workflow (runners)
                └─ claude-glm -p (CLAUDE_CONFIG_DIR isolation, virtual key)
                     └─ LiteLLM :4000 (stream guard, context guard, budgets)
                          └─ GLM-5.1/5.2 (Huawei MaaS)  ← incl. all subagent fan-out
```

Full product definition, mechanism specs, and acceptance criteria: [docs/PRD.md](docs/PRD.md).

## Skill Level

**Level 1 — Validated end-to-end on a live single-host deployment** (see PRD Appendix C).

## Applicable Scenario

A subscription (Pro/Max) Claude Code user who wants GLM/MaaS execution offload —
especially for multi-agent workflows, batch pipelines, loops, and CI — **without**
touching the OAuth transport. The three chronic problems of transport-layer
splitting are eliminated *by construction* (PRD §5):

| Problem | Why it disappears here |
|---|---|
| Subscription OAuth terms risk | token is only ever held/presented by the official `claude` binary; delegation is an ordinary Bash subprocess |
| Prompt-cache / rate-limit burn on backend switches | the OAuth session is append-only on one backend; briefs go down, summaries come up — no cross-backend replay |
| Protocol edge cases (role shapes, cache TTL, thinking signatures) | zero middleware on the OAuth path; GLM-path quirks handled server-side by `anthropic_stream_guard` + `context_window_guard` |

## Positioning vs Sibling Assets

| | [litellm-maas-auto-plugin](../litellm-maas-auto-plugin/) smart router | legacy forky transport router | **this asset** |
|---|---|---|---|
| Split layer | gateway, per-request | local proxy, per-phase | orchestrator, per-task |
| Premium pool | API-key model in LiteLLM | OAuth token replayed by proxy | the OAuth session itself |
| OAuth ToS exposure | none (OAuth unused) | gray zone | none |
| Best for | N clients, central audit | automatic in-session split | subscription safety + workflow offload |

## Required Tools

| Tool | Purpose |
|---|---|
| LiteLLM proxy (LiteLLM-Huawei-MaaS-Proxy stack) | execution-pool gateway on :4000 |
| litellm-maas-auto-plugin server plugins | `anthropic_stream_guard` (mandatory), `context_window_guard`, `claude-*` wildcard route |
| Claude Code CLI ≥ 2.1.x | orchestrator (OAuth) and delegate (virtual key) runtimes |
| python3 (stdlib) | `delegate` / `workflow` runners |

## Workflow

1. **Server prerequisites** — plugins + wildcard route on the LiteLLM host (SKILL.md step 1).
2. **Mint a delegate virtual key** — own budget/rpm/tpm; CI gets a separate key.
3. **`scripts/install.sh <key>`** — isolated `claude-glm` client (reuses `configure-claude-code.sh`), wrapper, runners.
4. **`scripts/configure-policy.sh`** — policy block into `~/.claude/CLAUDE.md`, route-hint hook, `glm-executor` agent, 3 GLM-twin skills. Plain `claude` transport is never touched.
5. **`scripts/verify.sh`** — chained reused probes + functional delegate smoke + isolation invariants.

## Expected Outputs

- `delegate '<brief>'` — one execution task on GLM, acceptance-verified, audited, ≤2 attempts then `needs_escalation`.
- `workflow '<manifest>'` — W2 parallel fan-out (disjoint scopes enforced, concurrency governor) or W1 whole-workflow sub-orchestration; failed items return as the premium remainder.
- Route audit at `~/.claude-hybrid/route-audit.jsonl`; `scripts/route-stats.sh` aggregates coverage/escalation KPIs (PRD §10–11).

## Reusable Assets

| Asset | Description |
|---|---|
| `scripts/delegate` | C2 runner: brief → `claude-glm -p` → acceptance check → result JSON + audit |
| `scripts/workflow` | C7 fan-out/sub-orchestration runner with disjoint-scope enforcement |
| `scripts/install.sh` / `configure-policy.sh` / `verify.sh` / `uninstall.sh` | lifecycle (install is fully reversible; uninstall never touches OAuth creds) |
| `assets/orchestrator-policy.md` | the CLAUDE.md policy block (PRD Appendix A) |
| `scripts/route-hint.sh` | deterministic UserPromptSubmit advisory hook |
| `assets/skills/` | GLM-twin skills: `glm-review`, `glm-repo-summary`, `glm-test-batch` |
| `assets/glm-executor.agent.md` | optional subagent keeping delegation plumbing out of the main context |
| `assets/brief-schema.json` / `manifest-schema.json` | delegation contracts (PRD §6.2–6.3) |

Reused, not vendored: `../litellm-maas-auto-plugin/client/configure-claude-code.sh`
(honors `CLAUDE_CONFIG_DIR`), `../litellm-maas-auto-plugin/tests/live_smoke.py`,
server plugin installers, and the spend-log SQL verification pattern used by
the LiteLLM MaaS plugin probes.

## KPIs (PRD §11)

GLM coverage 40–70% of generated tokens; **workflow token coverage ≥ 90%**;
escalation rate 15–35%; zero OAuth-compliance violations; no cache resets
attributable to routing.

## Common Risks

| Risk | Mitigation |
|---|---|
| Policy drift (orchestrator stops delegating) | hook hints, weekly `route-stats`, optional strict mode |
| Parallel workers collide on files | disjoint scopes enforced; overlapping manifests refused |
| Runaway loop drains MaaS budget | per-key rolling budget = circuit breaker (429 halts, audited) |
| Regenerating `litellm_config.yaml` clobbers wildcard/callback edits | re-apply after `generate_config.sh` (tracked in SKILL.md) |
| `claude -p` inside heredocs eats trailing script as stdin | always `< /dev/null` (see SKILL.md troubleshooting) |

## Quick Start

```bash
cd AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-oauth-delegate-router
# server prerequisites once (see SKILL.md step 1), then:
./scripts/install.sh sk-<litellm-virtual-key> --base-url http://127.0.0.1:4000
./scripts/configure-policy.sh
./scripts/verify.sh
```
