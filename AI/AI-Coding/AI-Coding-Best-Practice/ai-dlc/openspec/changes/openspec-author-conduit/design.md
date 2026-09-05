# Design — openspec-author conduit + doctor workspace coverage

## G1 — the conduit skill

`supervisor/skills/workspace/openspec-author/SKILL.md`, frontmatter styled
like `codegraph`/`ui-designer`:

```yaml
---
name: openspec-author
description: Authoring conduit — a dispatched role fetches its own artifact
  instructions by running the openspec CLI through this skill, rather than
  improvising from the prompt. Called by plan.py dispatch/phase for planned-
  route change artifacts (proposal/specs/design/tasks).
---
```

Body, three sections only:

1. **What you are** — you are writing one openspec change artifact; the
   instructions for it are not in your prompt on purpose.
2. **What to run** — `openspec instructions <artifact> --change <change_id>
   --json`, where `<artifact>` and `<change_id>` come from the dispatch
   prompt. Follow the returned `instruction`, `template`, and output path
   exactly.
3. **If it fails** — do not improvise, do not guess a different artifact
   name, do not retry with a different schema. Follow the stop protocol
   your dispatch prompt already gives you (this file does not repeat it).

No mention of validate, of other roles, of file-write boundaries — those
live only in the role prompt (`plan.py:552-572`), per INV-26.

## G2 — doctor workspace coverage

Current (`install.sh` around line 256-267): a single hard-coded check
against `ui-designer`'s registration count.

New: iterate `${WS_SKILLS_DIR}/*/` (the same glob `install_workspace_skills`
uses to deploy), and for each directory name `skill_name`:

1. Assert `${WORKSPACE_SKILLS_DIR}/${skill_name}/SKILL.md` exists.
2. Assert `skills_state.json`'s `installed_plugins` contains exactly one
   entry with `name == skill_name`.
3. On either failing: `fail "workspace skill '<skill_name>' not installed
   or not registered (expected N entries, found M)"` and set the doctor's
   overall exit code to 1 (INV-29 — this is a failure, not an advisory,
   because it means an entire dispatch path silently can't run).

This makes the check self-describing against whatever `supervisor/skills/
workspace/` actually ships, so adding a new workspace skill later can never
again go uncovered by `--doctor` the way `openspec-author` did.
