# PRD: OpenCode MaaS Delegate Router (Global Hybrid Routing)

Status: v1.0 · 2026-07-28 · validated on single-host deployment
Repo path: `AI/AI-Coding/Enterprise-MaaS-Foundation/opencode-maas-delegate-router/`

## 1. Goal

A single OpenCode install that automatically routes work between two Huawei MaaS models:

- **GLM-5.2** (premium) — handles planning, architecture, complex debugging, security review, incidents, high-risk PR review, and image input
- **GLM-5.1** (execution) — handles unit tests, documentation, CI fixes, codegen, batch refactors, and low/medium-risk review

The routing policy is injected into every session via OpenCode's `instructions` mechanism
and enforced by a `MANDATORY` — `Session Start` rule and `HARD RULES` delegation table
in `AGENTS.md`. No explicit prompting is required from the user.

```
user prompt → opencode (GLM-5.2, instructions=AGENTS.md)
                 │
                 ├─ premium: planning / architecture / security / incidents
                 │  → stays in-session (GLM-5.2)
                 │
                 └─ execution: tests / codegen / docs / CI / batch
                    → Task tool → ds-executor (GLM-5.1)
                                   → returns structured result
```

## 2. Architecture

### Components

| # | Component | What it is |
|---|---|---|
| C1 | Global config (`opencode.json`) | Declares providers (huawei-maas with glm-5.2 + glm-5.1), subagents (`ds-executor`, `ds-reviewer`), instructions path, and skills path |
| C2 | AGENTS.md | Routing policy loaded every session via `instructions` field. Contains MANDATORY session-start rule, HARD RULES delegation table, and delegation pattern |
| C3 | `ds-executor` subagent | OpenCode subagent on `huawei-maas/glm-5.1` with edit+write permission |
| C4 | `ds-reviewer` subagent | OpenCode subagent on `huawei-maas/glm-5.1` with read-only permission |
| C5 | GLM-twin skills | `glm-review`, `glm-repo-summary`, `glm-test-batch` — skills that delegate to the execution pool |

### No additional infrastructure

Unlike sibling assets (claude-code-oauth-delegate-router, cursor-maas-delegate-router),
this asset requires **no LiteLLM proxy, no virtual keys, no service plugins**.
OpenCode's native multi-provider/multi-agent architecture handles everything.

## 3. Task Classification Policy

### Premium — stays in-session (GLM-5.2)

| Class | Examples |
|-------|----------|
| architecture/design | cross-service design, tech selection, plan mode |
| complex debugging | multi-subsystem root cause, race conditions, repeated failed fixes |
| security review | auth/crypto/secrets/injection surfaces |
| production incidents | live outage, rollback decisions, incident-labeled issues |
| high-risk PR review | payment/auth/pci/infra/migrations paths, CODEOWNERS-protected |
| image/screenshot | any image block (GLM-5.1 has no vision capability) |
| >128K raw context | cannot be briefed under GLM-5.1's input limit |

### Execution — delegated to ds-executor (GLM-5.1)

| Class | Notes |
|---|---|
| unit test generation | acceptance = tests pass |
| documentation / repo summary | acceptance = files written |
| CI auto-fix | bounded diff, CI green |
| single-module code generation | low/medium risk, verifiable |
| batch/mechanical refactors | after premium planning if needed |
| low/medium-risk PR review | summary + findings returned |
| format/migration transforms | mechanical conversions |

## 4. Installation Mechanism

The `install.ps1` script:

1. Writes `opencode.json` to `~/.config/opencode/` with full provider, agent, instructions, and skills configuration
2. Creates `~/.config/opencode/AGENTS.md` with the routing policy
3. Copies 4 skills to `~/.config/opencode/skills/`
4. Sets `MAAS_API_KEY` as a user-level environment variable

After restart, OpenCode loads:
- `model: huawei-maas/glm-5.2` as the default session model
- `instructions` → AGENTS.md → routing policy injected into system prompt
- `ds-executor` and `ds-reviewer` as globally available subagents
- 4 skills auto-loaded from global skills path

## 5. OpenCode Config Structure

### Global `~/.config/opencode/opencode.json`

```json
{
  "model": "huawei-maas/glm-5.2",
  "instructions": ["C:\\Users\\<user>\\.config\\opencode\\AGENTS.md"],
  "agent": {
    "ds-executor": {
      "model": "huawei-maas/glm-5.1",
      "mode": "subagent",
      "permission": { "edit": "allow", "bash": "allow" }
    },
    "ds-reviewer": {
      "model": "huawei-maas/glm-5.1",
      "mode": "subagent",
      "permission": { "edit": "deny", "bash": { "git *": "allow", "*": "ask" } }
    }
  },
  "skills": { "paths": ["C:\\Users\\<user>\\.config\\opencode\\skills"] },
  "provider": {
    "huawei-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Huawei MaaS",
      "options": {
        "baseURL": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
        "apiKey": "{env:MAAS_API_KEY}"
      },
      "models": {
        "glm-5.1": { "name": "GLM-5.1", "tool_call": true },
        "glm-5.2": { "name": "GLM-5.2", "tool_call": true }
      }
    }
  }
}
```

## 6. Delegation Contract

### Brief (orchestrator → delegate)

```json
{
  "task_type": "unit_test_generation",
  "goal": "Add pytest coverage for src/billing/rounding.py",
  "scope": ["src/billing/rounding.py", "tests/"],
  "constraints": ["match existing test style"],
  "acceptance": "pytest tests/ -k rounding exits 0"
}
```

### Result (delegate → orchestrator)

```json
{
  "status": "success",
  "summary": "3 tests added, all pass",
  "files_changed": ["tests/test_rounding.py"],
  "verification": { "cmd": "pytest -k rounding", "exit": 0 },
  "attempt": 1
}
```

## 7. Escalation

1. Delegate attempt 1: on failure, re-delegate with failure evidence
2. Delegate attempt 2: on failure → orchestrator takes over in-session (premium escalation)
3. A task escalated to premium is never re-delegated (per-item stickiness)
4. Workflow remainder >30% → abort and reclassify as premium

## 8. Deliverables

```
opencode-maas-delegate-router/
  README.md                    product overview
  SKILL.md                     main skill definition
  docs/PRD.md                  this document
  scripts/
    install.ps1                automated global installation
    verify-setup.ps1           setup verification
    delegate.ps1               delegation brief helper
  assets/
    orchestrator-policy.md     AGENTS.md routing policy template
    ds-executor.agent.md       execution subagent definition
    ds-reviewer.agent.md       code reviewer subagent definition
    skills/
      glm-review/SKILL.md      review skill
      glm-repo-summary/SKILL.md repo summarization skill
      glm-test-batch/SKILL.md  batch test generation skill
  reference/
    opencode.json              project-level config reference
    AGENTS.md                  project-level routing policy reference
```

## 9. Verification

```powershell
.\scripts\verify-setup.ps1
```

Checks: global config structure, AGENTS.md completeness, all 4 skills present, MAAS_API_KEY set.
Expected: all checks PASS, routing = GLM-5.2 -> GLM-5.1.

## 10. KPI Targets

| Metric | Target |
|--------|--------|
| Execution coverage (generated tokens on GLM-5.1) | 40-70% |
| Escalation (fallback) rate | 15-35% |
| Premium classification accuracy | >= 95% |
| Zero-config adoption | user runs one command, restarts, done |
