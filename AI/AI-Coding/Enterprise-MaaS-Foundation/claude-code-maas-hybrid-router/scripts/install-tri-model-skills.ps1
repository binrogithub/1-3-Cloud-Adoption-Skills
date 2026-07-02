param(
  [string]$CodexSkillDir = "$env:USERPROFILE\.codex\skills\tri-model-workflow",
  [string]$ClaudeSkillDir = "$env:USERPROFILE\.claude\skills\tri-model-workflow"
)

$ErrorActionPreference = "Stop"

$codexSkill = @'
---
name: tri-model-workflow
description: Coordinate Claude fable5, GLM-5.2, and Codex for demos, workflows, customer-facing presentations, learning projects, image creation, and mixed deliverables. Use when the user asks how to split work across models/tools, wants Codex to join a Claude Code/GLM task, or wants a reusable plan for building demos, PPTs, automations, study labs, or visual assets.
---

# Tri-model Workflow

## Routing Rule

Use this skill to decide the working split before doing substantial work.

Default responsibilities:

| Work type | Primary owner | Use for |
|---|---|---|
| Strategy, reasoning, quality bar | Claude fable5 | plans, tradeoffs, customer narrative, review |
| Cheap repeated execution | GLM-5.2 via `claude-forky` | routine coding turns, tool execution, implementation churn |
| Local delivery | Codex | files, repos, tests, screenshots, PPT/doc/image artifacts, verification |

## Workflows

### Demo Builder

Claude fable5 plans the product story, user flow, architecture, and acceptance checks. Codex creates or modifies the project, runs it locally, fixes errors, and verifies with tests or screenshots. GLM-5.2 handles ordinary implementation turns when the task stays inside Claude Code.

### Workflow Builder

Claude fable5 defines decision logic, failure modes, and human checkpoints. Codex turns the workflow into scripts, docs, config files, diagrams, or checklists. GLM-5.2 handles repeated execution and simple edits.

### Customer PPT Builder

Claude fable5 owns storyline, business value, objections, and executive wording. Codex owns deck creation, diagrams, screenshots, formatting, speaker notes, and exported files.

### Learning Lab

Claude fable5 explains concepts, mental models, and study path. Codex creates runnable notebooks, mini demos, exercises, and local references. GLM-5.2 handles quick Q&A, summaries, and repeated practice turns.

### Image And Visual Creation

Claude fable5 helps define visual direction, audience, and prompt quality. Codex uses image generation/editing tools or local asset workflows to create deliverables.

## Handoff Pattern

Use this compact handoff format:

```text
Goal:
Context:
Claude plan:
Codex deliverables:
GLM execution scope:
Verification:
Open questions:
```
'@

$claudeSkill = @'
---
name: tri-model-workflow
description: Coordinate Claude Code running through claude-forky with Codex for demos, workflows, customer-facing PPTs, learning labs, image creation, and deliverable-heavy work. Use when the user wants Codex to join a Claude/GLM task, wants to decide what Claude fable5, GLM-5.2, and Codex should each do, or needs a handoff from Claude Code to Codex.
---

# Tri-model Workflow

## Core Split

When using `claude-forky`:

| Role | Best owner | Notes |
|---|---|---|
| High-quality planning | Claude fable5 | Use Plan mode before expensive or ambiguous work |
| Routine execution | GLM-5.2 | Default execution backend through forky |
| Deliverables and verification | Codex | Repos, demos, scripts, PPTs, docs, images, screenshots, tests |

## How To Handoff To Codex

Use this format:

```text
Codex handoff:
Goal:
Current repo/folder:
Claude plan:
Files/artifacts needed:
What GLM already did:
What to verify:
Open questions:
```

## Routing Checks

To check what actually ran where, ask Codex to run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\forky-route-stats.ps1
```

Interpretation:

- `actualProvider: aistack` means GLM-5.2 when forky has `EXEC_MODEL=glm-5.2`.
- `actualProvider: anthropic-oauth` with `routedVia: classifier` is normal Claude Code classifier traffic.
- `routedVia: sentinel` means Plan mode or forced Claude fable5 routing.
'@

New-Item -ItemType Directory -Force $CodexSkillDir | Out-Null
New-Item -ItemType Directory -Force $ClaudeSkillDir | Out-Null

Set-Content -Path (Join-Path $CodexSkillDir "SKILL.md") -Value $codexSkill -Encoding UTF8
Set-Content -Path (Join-Path $ClaudeSkillDir "SKILL.md") -Value $claudeSkill -Encoding UTF8

Write-Host "Installed Codex skill: $CodexSkillDir"
Write-Host "Installed Claude Code skill: $ClaudeSkillDir"
