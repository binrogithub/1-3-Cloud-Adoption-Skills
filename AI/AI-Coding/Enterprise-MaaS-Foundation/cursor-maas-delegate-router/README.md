# Cursor MaaS Delegate Router

**USER-GLOBAL** task-level hybrid routing for [Cursor](https://cursor.com):
keep the main Agent on Cursor subscription / premium models as the
**orchestrator**, and send execution-class work to **Huawei Cloud MaaS GLM**
via isolated `delegate.py` / `workflow.py` runners.

Inspired by
[claude-code-oauth-delegate-router](https://github.com/binrogithub/1-3-Cloud-Adoption-Skills/tree/main/AI/AI-Coding/Enterprise-MaaS-Foundation/claude-code-oauth-delegate-router),
adapted to Cursor Rules + Hooks (no Claude Code OAuth transport changes).

## Skill Level

**Level 1 — Validated by local installer, policy, hook, and delegate runner smoke tests.**

```
User ──► Cursor Agent (subscription / premium) ──► plan / premium only
           │  USER-GLOBAL: ~/.cursor/rules + memory + hooks
           │
           └─ code execution (DEFAULT) ──► delegate.py | workflow.py
                └─ Huawei MaaS openai/v1  OR  LiteLLM :4000
                     └─ glm-5.1 / glm-5.2
```

## When to use

| Intent | Use this skill? |
|--------|-----------------|
| Cursor plans; MaaS writes most code / tests / docs / batch | **Yes** |
| Whole Cursor chat should be GLM (Override Base URL only) | No — use Cursor Models UI with an OpenAI-compatible MaaS endpoint |
| Claude Code OAuth hybrid | No — use `claude-code-oauth-delegate-router` |

## What “USER-GLOBAL” means

Install writes under the **user home**, not a single repo:

| Artifact | Path |
|----------|------|
| Skill copy | `~/.cursor/skills/cursor-maas-delegate-router/` |
| alwaysApply Rule | `~/.cursor/rules/maas-delegate-router.mdc` |
| Memory | `~/.cursor/memory/maas-delegate-router.md` |
| Hooks | `~/.cursor/hooks.json` + `~/.cursor/hooks/maas-*.py` |
| Runtime | `~/.cursor-hybrid/env.json`, `bin/`, `route-audit.jsonl` |

Hooks:

- `sessionStart` — injects routing policy into every Agent chat
- `beforeSubmitPrompt` — reminds on each send

Affects **all workspaces** on that machine. Project-local overlay is optional
(`configure_policy.py --project`) and not the default.

## Install

### 1) Copy skill into Cursor

From this directory (or the monorepo checkout):

```powershell
# Windows
.\install.ps1 -ApiKey "<MAAS_KEY>" -BaseUrl "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
```

```bash
# macOS / Linux
export DELEGATE_API_KEY="<MAAS_KEY>"
export DELEGATE_API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
chmod +x install.sh scripts/*.sh 2>/dev/null || true
./install.sh
```

This:

1. Copies the skill folder to `~/.cursor/skills/cursor-maas-delegate-router/`
2. Writes `~/.cursor-hybrid/env.json` (preserves existing key on re-install)
3. Writes USER-GLOBAL memory + alwaysApply rule
4. Registers USER-GLOBAL hooks (`sessionStart` + `beforeSubmitPrompt`)

### 2) Verify

```powershell
python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/verify.py
```

Expect `VERIFY PASS`. If you see `ModelArts.81003`, switch region (keys are
region-bound): Hong Kong vs Guiyang Base URL.

### 3) Operate (Agent)

User does **not** need to name this skill. After a UI/architecture plan, the
orchestrator should write a brief and run:

```text
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py --root . --brief-file briefs/task.json
```

Example briefs: [examples/briefs/](examples/briefs/).

## Invariant

Do **not** set Override OpenAI Base URL on the *orchestrator* Cursor profile
for hybrid mode. Only the isolated delegate process uses `DELEGATE_*`.

## Uninstall

```powershell
python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/uninstall.py
# optional: --purge  (deletes ~/.cursor-hybrid)
```

Removes USER-GLOBAL rule, memory, hooks, and launchers. Does not touch Cursor login.

## Docs

- [SKILL.md](SKILL.md) — agent-facing deploy / operate steps
- [docs/PRD.md](docs/PRD.md) — architecture and acceptance
- [docs/VISION_PDF.md](docs/VISION_PDF.md) — image/PDF gate before GLM

## Sibling skills

| Skill | Role |
|-------|------|
| Cursor Models UI | Tier A: whole-chat MaaS endpoint configuration |
| `LiteLLM-Huawei-MaaS-Proxy` | Shared proxy if you route via `:4000` |
| `claude-code-oauth-delegate-router` | Same idea for Claude Code |
