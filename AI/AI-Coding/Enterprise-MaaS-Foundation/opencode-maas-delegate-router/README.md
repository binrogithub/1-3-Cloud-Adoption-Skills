# OpenCode MaaS Delegate Router

Task-level hybrid routing for **OpenCode**: **GLM-5.2** (premium) handles planning,
architecture, reviews, and decisions; execution-class work (tests, docs, CI fixes,
codegen, batch refactors) is delegated to **GLM-5.1** via subagents on Huawei MaaS.

```
user prompt ──► opencode (GLM-5.2, premium orchestrator)
                   │  planning, architecture, security, high-risk PR, images
                   │
                   └─ Task tool → ds-executor (GLM-5.1, execution pool)
                        └─ unit tests, docs, CI fixes, codegen, batch refactors
```

Both models use the same Huawei MaaS base URL and API key. Only the `model`
parameter differs (`glm-5.2` vs `glm-5.1`).

## How It Works

The routing policy is injected into **every** opencode session via the global
config `instructions` field. GLM-5.2 automatically classifies each task and
delegates execution work to `ds-executor` (GLM-5.1) — no explicit prompting needed.

| Pool | Model | Role |
|------|-------|------|
| Premium | GLM-5.2 (Huawei MaaS) | orchestrator: planning, architecture, debugging, security, review |
| Execution | GLM-5.1 (Huawei MaaS) | worker: tests, codegen, docs, CI fixes, batch refactors |

## Positioning vs Sibling Assets

| | claude-code-oauth-delegate-router | cursor-maas-delegate-router | **this asset** |
|---|---|---|---|
| Platform | Claude Code | Cursor | OpenCode |
| Premium model | Anthropic Claude (OAuth) | Claude via API | GLM-5.2 (Huawei MaaS) |
| Execution model | GLM-5.1 (LiteLLM proxy) | GLM-5.1 | GLM-5.1 (Huawei MaaS) |
| Gateway | LiteLLM :4000 | LiteLLM :4000 | None (direct provider config) |
| Install | bash scripts | bash scripts | `install.ps1` (PowerShell) |
| Policy | CLAUDE.md + hooks | Cursor rules | opencode `instructions` + `AGENTS.md` |

## Quick Start

```powershell
# Clone or copy this directory, then:
.\scripts\install.ps1 -maasApiKey "your-huawei-maas-api-key"

# Restart opencode. Hybrid routing is now the default.
```

## Skill Level

**Level 1** — Validated on a live single-host deployment.

## Required Tools

| Tool | Purpose |
|------|---------|
| OpenCode ≥ 1.18.5 | AI coding agent |
| Huawei MaaS API key | Model access (GLM-5.2 + GLM-5.1) |

## Naming

The repository package is `opencode-maas-delegate-router`. The main OpenCode
skill installed under `~/.config/opencode/skills/` is named
`maas-delegate-router`, matching the `SKILL.md` frontmatter and the session-start
policy.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill definition (auto-loaded when placed in `.opencode/skills/`) |
| `docs/PRD.md` | Product requirements document |
| `scripts/install.ps1` | Automated global installation |
| `scripts/verify-setup.ps1` | Setup verification |
| `scripts/delegate.ps1` | Delegation brief helper |
| `assets/ds-executor.agent.md` | Execution subagent definition |
| `assets/ds-reviewer.agent.md` | Code reviewer subagent definition |
| `assets/skills/` | GLM-twin skills (review, repo-summary, test-batch) |
| `assets/orchestrator-policy.md` | AGENTS.md routing policy template |
| `reference/opencode.json` | Project-level config reference |
| `reference/AGENTS.md` | Project-level AGENTS.md reference |
