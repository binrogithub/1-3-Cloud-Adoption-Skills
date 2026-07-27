# PRD: Cursor Task-Level MaaS Delegate Router

Status: v0.1 · skeleton validated for local install/configure/verify  
Inspired by: claude-code-oauth-delegate-router (binrogithub/1-3-Cloud-Adoption-Skills)

## 1. Goal

One entry point — Cursor Agent on the user's **subscription / premium** models,
transport for that session left alone — that:

- **defaults code execution to Huawei MaaS GLM** after install (durable memory +
  alwaysApply rule); this route **outranks Cursor Task/subagent routing**;
- executes **premium-class** work in-session only;
- **delegates execution-class** work as discrete briefs to an isolated process →
  LiteLLM or Huawei MaaS GLM;
- **delegates workflows** (fan-out, batch, CI-style loops) so token multiplication
  burns MaaS budget, not subscription quota;
- carries routing policy in **Cursor memory** + **Cursor Rules** + optional
  **beforeSubmitPrompt** hook.

Split layer = **task** (who does the work), not transport (where every request goes).

## 2. Why not Override Base URL for hybrid

Cursor Override OpenAI Base URL replaces the OpenAI-compatible path for custom
models. Using it as the *only* session backend collapses the premium pool.
Hybrid mode therefore:

- keeps the orchestrator on Cursor-native / subscription models;
- runs `delegate.py` / `workflow.py` as subprocesses with their own `DELEGATE_*` env.

## 3. Task classification

### Premium — stay in-session

| Class | Signals |
|-------|---------|
| architecture_planning | plan mode, cross-service design |
| complex_debugging | >2 subsystems, repeated failed fixes |
| security_review | auth/crypto/secrets/injection |
| production_incident | outage, rollback |
| pr_review (high risk) | payment, auth, infra, migrations |
| image / screenshot | vision required — GLM-5.1 has **no multimodal** |
| scanned PDF | OCR or multimodal first; see `docs/VISION_PDF.md` |
| huge context | cannot brief under ~196K and resists split |

### Execution — delegate (DEFAULT; priority over Cursor routing)

| Class | Acceptance idea |
|-------|-----------------|
| unit_test_generation | tests pass |
| documentation | files written |
| ci_auto_fix | CI green / bounded diff |
| normal codegen | single-module, verifiable |
| batch refactoring | mechanical after premium plan |
| pr_review (low/med) | findings list returned |
| workflow fan-out | per-item success or escalate |

Install persists `CODE_EXECUTION_ROUTE=maas_glm` and
`ROUTE_PRIORITY=maas_over_cursor` in `~/.cursor-hybrid/env.json`, plus:

- `~/.cursor/memory/maas-delegate-router.md`
- `~/.cursor/rules/maas-delegate-router.mdc` (`alwaysApply: true`)

## 4. Contracts

### Brief (delegate)

See `assets/brief-schema.json`. Required: `goal`, `files`, `acceptance`.
Optional: `constraints`, `context` (`VISION_SUMMARY:` / `DOC_TEXT:`),
`accept_cmd`, `max_attempts` (default 2).

### Vision / PDF preprocess

See `docs/VISION_PDF.md` and `scripts/preprocess_doc.py`. Non-goal: sending
raw images to the Huawei MaaS GLM endpoint.

### Manifest (workflow)

See `assets/manifest-schema.json`. Items must have **disjoint** `files` scopes.
`concurrency` default 3.

## 5. Escalation

1. Attempt ≤ `max_attempts`; on failure retry with error summary in brief.
2. After max attempts → `status: needs_escalation`.
3. Orchestrator completes in-session; do not re-delegate same item.
4. If workflow remainder (failed/escalated) > 30% of items → abort and reclassify
   remaining as premium.

## 6. Audit + KPIs

Audit path: `~/.cursor-hybrid/route-audit.jsonl` (one JSON object per line).

Target KPIs (tune after real usage):

- GLM / delegate token share of *generated* work: 40–70%
- Workflow token share on delegate path: ≥ 90%
- Escalation rate: 15–35%
- Zero orchestrator Base URL override while hybrid mode is active

## 7. Non-goals

- No mid-turn backend swap inside one Cursor completion
- No replaying Cursor auth tokens into third-party proxies
- No multi-tenant key portal (use LiteLLM separately)
- No claim that GLM matches premium quality — gaps use escalation

## 8. Acceptance (install)

- [ ] `install.py` creates `~/.cursor-hybrid` with `CODE_EXECUTION_ROUTE=maas_glm`
- [ ] `install.py` writes `~/.cursor/memory/maas-delegate-router.md` and alwaysApply rule
- [ ] `configure_policy.py` re-writes memory + marker-fenced rule
- [ ] `verify.py` gets HTTP 200 from delegate endpoint and one smoke brief
- [ ] `uninstall.py` removes policy/memory/hook/bin without deleting Cursor login
