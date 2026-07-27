<!-- maas-delegate-router-memory:begin -->
# Memory: code execution → Huawei MaaS GLM (USER-GLOBAL silent default)

Applies to **all Cursor workspaces** on this machine (not one project).
The user does **not** need to name any skill.

1. **Default:** create/edit application code via
   `python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py`
   (model from `~/.cursor-hybrid/env.json`, usually `glm-5.1`).
2. **Hard stop:** Do **not** use Write/StrReplace/EditNotebook to implement
   app code (HTML/CSS/JS/TS/Python/etc.) in this session when a brief can be
   delegated — including **new / greenfield projects**, Hello World pages,
   landing pages, and “先设计再输出代码”.
3. **You may** plan UI/architecture in chat. After the plan, **write a brief
   JSON and run `delegate.py`** for the implementation. Do not skip to local
   file writes “because the project is new”.
4. **Priority over** Cursor Task/subagents and in-session codegen.
5. **Premium stay:** architecture-only Q&A, hard multi-system debug, security,
   incidents, vision/images, scanned PDF until text, `needs_escalation`.
6. Never set Override OpenAI Base URL on the orchestrator for hybrid mode.
<!-- maas-delegate-router-memory:end -->
