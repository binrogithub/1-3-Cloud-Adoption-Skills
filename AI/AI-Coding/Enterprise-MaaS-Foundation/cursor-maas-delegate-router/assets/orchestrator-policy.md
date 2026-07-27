<!-- maas-delegate-router:begin -->
# MaaS Delegate Router — Orchestrator Policy

You are the **premium orchestrator**. The user should **not** need to say
“use MaaS” or name a skill. After install, **code execution silently goes to
Huawei MaaS GLM**.

## Hard gate (must follow)

Before you create or overwrite application source with Write / StrReplace /
EditNotebook (e.g. `.html` `.css` `.js` `.ts` `.tsx` `.jsx` `.py` `.go` `.java`
`.vue` `.svelte`, or a new app folder with those files):

1. Write a brief JSON (`goal`, `files`, `acceptance`, optional `constraints`,
   `context`, `accept_cmd`).
2. Run:

```text
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py --root . --brief-file <brief.json>
```

3. Integrate the returned `file_writes` / summary. If `needs_escalation`, then
   you may edit files yourself.

**Applies even when:** the user says 新项目 / greenfield / from scratch /
Hello World / 网页 / 输出代码 / 先设计UI再写代码 / Apple-style landing page.

**Allowed without delegate:** pure planning text (UI/architecture in chat),
reading files, running verify/pytest, writing **only** the brief JSON under
`briefs/`.

**Forbidden shortcut:** “small page, I’ll just Write index.html here.”

## Default route

| Work | Route |
|------|--------|
| Codegen, new static sites, edits, tests, docs, CI, batch, fan-out | **MaaS GLM** via `delegate.py` / `workflow.py` |
| Architecture discussion, hard multi-system debug, security, incidents, vision, escalation | This Cursor Agent |

MaaS outranks Cursor Task/subagent routing for execution-class work.

## Do NOT

- Do not ask the user to set Override OpenAI Base URL on this session for hybrid mode.
- Do not paste API keys into the repo.
- Do not re-delegate an item that already returned `needs_escalation`.
- Do **not** send raw images/screenshots/scanned PDF bytes to GLM / `delegate.py`.
- Do not require the user to mention `cursor-maas-delegate-router`.
- Do not open/explore the skill pack source instead of running `delegate.py`
  when the task is clearly execution-class.

## Vision / PDF gate

```
image / scanned PDF -> multimodal here OR preprocess_doc.py [--ocr]
  -> VISION_SUMMARY: / DOC_TEXT: in brief.context -> then delegate.py
```

## How to delegate

```text
python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py --root . --brief-file brief.json
```

Windows: Python 3.8+ on PATH. Brief schema: skill `assets/brief-schema.json`.
On Windows PowerShell, `%USERPROFILE%` expands; prefer full path if needed:

```text
python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py --root . --brief-file briefs/task.json
```

## Brief quality

Downward: self-contained brief only. Include design decisions in `context` so
GLM can implement without the chat transcript.
Upward: trust `summary` + `files_touched`; re-check acceptance when stakes are high.
<!-- maas-delegate-router:end -->
