---
name: cursor-maas-delegate-router
description: >-
  USER-GLOBAL hybrid routing for Cursor (all workspaces): after install, writes
  ~/.cursor/rules + ~/.cursor/memory + ~/.cursor/hooks (sessionStart +
  beforeSubmitPrompt). Code execution (HTML/CSS/JS, Hello World, greenfield,
  输出代码, tests, docs, CI) MUST use delegate.py → Huawei MaaS GLM — user need
  not name this skill. Plan in chat, then delegate; do not Write app source
  locally. Priority over Cursor Task routing. Premium stay: hard debug, security,
  vision. Pair with Cursor Models UI or LiteLLM-Huawei-MaaS-Proxy. Part of
  Enterprise-MaaS-Foundation.
---

# Cursor MaaS Delegate Router — Deploy / Verify / Operate

Architecture and acceptance: [docs/PRD.md](docs/PRD.md).
Product overview: [README.md](README.md).

**Scope:** USER-GLOBAL (`~/.cursor/…`) — applies to **all** Cursor workspaces on
the machine after install. Users do not need to name this skill.

```
User ──► Cursor Agent (subscription / premium) ──► orchestrator only
           │  memory + Rule + hooks (sessionStart / beforeSubmitPrompt)
           │
           └─ execution/codegen (DEFAULT) ──► scripts/delegate.py | workflow.py
                └─ LiteLLM :4000  OR  direct Huawei MaaS openai/v1
                     └─ glm-5.1 / glm-5.2
```

**Default after install:** `CODE_EXECUTION_ROUTE=maas_glm` and
`ROUTE_PRIORITY=maas_over_cursor`. Mechanical coding must go through the
delegate path before Cursor native Task/subagents or large in-session patches.

**Invariant:** do not set Override OpenAI Base URL on the *orchestrator* session
for hybrid mode. Delegation uses env vars in an isolated process only.

## Prerequisites

1. **Python 3.8+** on PATH (`python` / `python3`).
2. Huawei MaaS API key **or** LiteLLM proxy on `:4000` with a virtual key.
3. Optional: sibling endpoint skill / Cursor Models UI for chat-as-GLM (Tier A).
4. Cursor Hooks enabled (Settings → Hooks) so USER-GLOBAL hooks load.

## Install / configure / verify

```
Deploy progress:
- [ ] Step 1: Choose backend (direct MaaS vs LiteLLM) + region
- [ ] Step 2: ./install.ps1 or ./install.sh — skill + ~/.cursor-hybrid + USER-GLOBAL policy/hooks
- [ ] Step 3: verify.py PASS
- [ ] Step 4: New Agent chat — plan in Cursor, code via delegate (no skill name needed)
```

### Step 1 — Backend

**A) Direct MaaS (simplest):**

```powershell
$env:DELEGATE_API_BASE = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
$env:DELEGATE_API_KEY = "<maas-key>"
$env:DELEGATE_MODEL = "glm-5.1"
```

Guiyang region: `https://api.modelarts-maas.com/openai/v1`.
If you see `ModelArts.81003 Invalid authorization`, switch region (key is region-bound).

**B) LiteLLM:**

```powershell
$env:DELEGATE_API_BASE = "http://127.0.0.1:4000/v1"
$env:DELEGATE_API_KEY = "sk-<virtual-key>"
$env:DELEGATE_MODEL = "glm-5.1"
```

### Step 2 — Install (USER-GLOBAL)

```powershell
# From this skill directory
.\install.ps1 -ApiKey "<key>" -BaseUrl "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
```

```bash
export DELEGATE_API_KEY="<key>"
export DELEGATE_API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
chmod +x install.sh && ./install.sh
```

Creates / updates (**every workspace**, not project-local):

- `~/.cursor/skills/cursor-maas-delegate-router/`
- `~/.cursor-hybrid/env.json` (`CODE_EXECUTION_ROUTE=maas_glm`, `ROUTE_PRIORITY=maas_over_cursor`)
- `~/.cursor/memory/maas-delegate-router.md`
- `~/.cursor/rules/maas-delegate-router.mdc` (`alwaysApply: true`)
- `~/.cursor/hooks.json` + `~/.cursor/hooks/maas-*.py`
  (`sessionStart` + `beforeSubmitPrompt`)

Skip memory with `-SkipMemory` / hooks with `-SkipHook`.
Re-apply policy only: `python scripts/configure_policy.py`.

### Step 3 — Verify

```powershell
python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/verify.py
```

Expect `VERIFY PASS`.

### Step 4 — Operate

After UI/architecture planning in the main Agent, write a brief and run:

```powershell
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py --root . --brief-file briefs/task.json
```

Batch / fan-out:

```powershell
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/workflow.py --manifest-file manifest.json
```

Schemas: [assets/brief-schema.json](assets/brief-schema.json),
[assets/manifest-schema.json](assets/manifest-schema.json).
Examples: [examples/briefs/](examples/briefs/).

Stats:

```powershell
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/route_stats.py
```

## Task classification

**Default — delegate to MaaS GLM:** unit tests, docs, CI fixes, normal codegen
(including new Hello World / landing pages), batch refactor, low/med review,
mechanical transforms, multi-file fan-out — after media is reduced to text.

**Premium — stay in Cursor:** architecture, hard debugging, security, incidents,
high-risk PR, images/vision, scanned PDF until text exists, huge unsplittable
context, or post-`needs_escalation` finish.

Vision/PDF: [docs/VISION_PDF.md](docs/VISION_PDF.md).

## Escalation

Delegate returns `needs_escalation` after 2 failed attempts. Orchestrator
finishes in-session and must **not** re-delegate the same item.

## Uninstall

```powershell
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/uninstall.py
```

Removes USER-GLOBAL policy, memory, hooks, and `~/.cursor-hybrid/bin`.
Keeps audit log and `env.json` unless `--purge`. Never touches Cursor login.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| VERIFY FAIL auth / 81003 | Wrong region Base URL or bad key |
| Agent writes code in-session | New Agent chat; confirm Hooks + alwaysApply rule; check `~/.cursor/hooks.json` |
| Orchestrator stops delegating | Re-run `configure_policy.py`; reload Cursor |
| 429 under fan-out | Lower `concurrency` in manifest |
| Main chat suddenly on GLM | Clear Override OpenAI Base URL on orchestrator profile |

## Policy source

- [assets/orchestrator-policy.md](assets/orchestrator-policy.md)
- [assets/orchestrator-memory.md](assets/orchestrator-memory.md)
