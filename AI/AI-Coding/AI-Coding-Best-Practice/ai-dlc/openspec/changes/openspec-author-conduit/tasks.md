# Tasks — openspec-author conduit + doctor workspace coverage

## 1. G1 — conduit skill

- Write `supervisor/skills/workspace/openspec-author/SKILL.md` per
  `design.md` — frontmatter `name`/`description`, three-section body,
  no restated discipline (INV-26), no `--schema` (INV-27).
- Do not modify `install.sh`'s deployment loop — `install_workspace_skills()`
  already picks up any directory under `supervisor/skills/workspace/`.

## 2. G2 — doctor workspace coverage

- Replace the hard-coded `ui-designer` check in `run_doctor` (around
  install.sh:256-267) with a loop over `${WS_SKILLS_DIR}/*/`, checking
  each skill's `SKILL.md` presence at the installed destination and its
  registration count in `skills_state.json` (must be exactly 1).
- A missing/unregistered skill fails `--doctor` (exit 1) and names the
  skill and the expected-vs-found count (INV-29).
- Missing `skills_state.json` entirely stays a `warn`, not a `fail` (an
  uninitialized gateway workspace is a different condition from a missing
  registration — do not conflate them).

## 3. Tests

- Fixture: a fake `supervisor/skills/workspace/` with two subdirectories,
  one registered correctly in a fake `skills_state.json`, one not
  registered at all. Assert `run_doctor`'s workspace section fails and
  names the unregistered one.
- Fixture: same two skills, both registered — assert workspace section
  passes.
- Fixture: skill directory has no `SKILL.md` — assert failure names the
  missing file, not just the registration count.
- Fixture: `skills_state.json` has two entries for the same skill name —
  assert failure (INV-30, "must be exactly 1", not silently deduped).
- Fixture: `skills_state.json` absent — assert `warn`, not `fail`, and
  overall doctor exit code for this reason alone stays 0 if every other
  check passes.

## 4. End-to-end (real environment, install.sh --target against a live
   gateway; record the actual result in IMPLEMENTATION_REPORT.md)

- Run `install.sh --target <a-real-target>` and confirm
  `openspec-author` gets deployed and registered exactly like `ui-designer`
  and `codegraph` are today.
- Run `install.sh --doctor` before and after deliberately un-registering
  `openspec-author` from that target's `skills_state.json` — confirm the
  doctor exit code flips 0 → 1 and back.
- **The PRD's real acceptance bar**: dispatch a real planned-route role
  (via `plan.py dispatch` or `plan.py phase` against a disposable scratch
  repo) and inspect the resulting evidence frames'
  (`.ai-dlc/tasks/<id>/evidence/*.jsonl`) `commands_seen` — confirm
  `openspec instructions <artifact> --change <id> --json` actually
  appears. `authoring_skill_state().ok == true` alone does not satisfy
  this bar; the frames must show the CLI was actually invoked in-session.

## 5. CHECK → REPORT → MERGE_GATE

- `plan.py validate` for the signed spec verdict.
- `report.py deliver` for the delivery report.
- Present the diff and validator conclusion at MERGE_GATE for a human;
  no merge without an approved, rationale-carrying answer.
