## Why

`plan.py`'s planned-route role dispatch (`cmd_dispatch`, `cmd_phase`) gates on
an `openspec-author` skill being installed and registered in the gateway
workspace before the client is even created. This skill has never existed
anywhere on this host or in this repo's history: not in `install.sh`, not
under `supervisor/skills/workspace/`, not in any `skills_state.json`. The
direct consequence is that the entire authoring half of the planned route
cannot dispatch — confirmed by an end-to-end sweep of the collapse gate
suite, where 7 of 18 failing gates report the identical
`"stopped": "before dispatch — the client was never invoked"`.

The indirect consequence is worse: containment N1 forbids the orchestrating
session from running the `openspec` CLI directly, and with no plane-side
channel to do it either, the only thing that actually happens is the
orchestrating session hand-writes the artifact from memory — exactly the
violation containment exists to prevent. This has already happened at least
once on record (`docs/prd-phase-chain-automation.md` INV-7 self-reports it).

Separately, `install.sh --doctor`'s workspace check hard-codes a single
`ui-designer` registration count, so this entire gap has been invisible to
the one tool whose job is to catch it — `--doctor` reports "All checks
passed" the whole time.

## What Changes

- **New workspace skill**: `supervisor/skills/workspace/openspec-author/SKILL.md`
  — a thin conduit, not a rulebook. It tells the dispatched role to run
  `openspec instructions <artifact> --change <id> --json` and follow the
  instruction, template, and output path it returns. It does not restate
  any of the discipline already carried by the role prompt (only-write-your-
  own-artifact, never self-validate, the `CLI_UNAVAILABLE_MARKER` stop
  protocol) — that stays the role prompt's sole responsibility.
  No `--schema` override: the conduit lets `openspec` auto-detect the
  schema from `config.yaml`, preserving `cmd_roles`' existing stance of
  never querying the schema caller-side.
- **Zero deployment-code changes**: `install_workspace_skills()` already
  walks `supervisor/skills/workspace/*/`, copies, registers in
  `skills_state.json`, and does a read-back assertion. Adding the directory
  is sufficient — no `install.sh` change for G1 itself.
- **`install.sh --doctor` workspace check** (G2): replace the hard-coded
  `ui-designer`-only registration count with a loop over the actual
  contents of `supervisor/skills/workspace/*/`, checking each one's
  registration count is exactly 1 and its `SKILL.md` exists at the
  installed destination. A gap here now fails `--doctor` (exit 1), not
  silently passes.

## Non-goals

- No restatement of role-prompt discipline inside the new skill file
  (single source of truth stays the prompt).
- No `--schema` pinning.
- No changes to `authoring_skill_state()`'s precondition logic, to
  `install_workspace_skills()`'s deployment mechanism, or to the role
  prompt itself.
- No changes to the `validate` or `archive` dispatch paths — both were
  confirmed working without this skill during the review that found this
  gap (a real signed verdict and a real archive dispatch both completed).
- No self-installation or self-registration at runtime — the skill is
  deployed only by the installer, per the existing E6/N4 stance.
- No claim about the quality of artifacts a role produces through this
  channel — this change is responsible only for the channel existing.
