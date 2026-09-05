# Implementation Report — openspec-author conduit + doctor workspace coverage

Branch: `ai-dlc/openspec-author-conduit-v0.23.0`
Date: 2026-09-05

## What changed

- **`supervisor/skills/workspace/openspec-author/SKILL.md`** (new) — G1. The
  thin authoring conduit. YAML frontmatter (`name: openspec-author`, a
  `description` matching `design.md`); a three-section body: *What you are*
  (writing one change artifact; instructions are intentionally not in the
  prompt), *What to run* (`openspec instructions <artifact> --change <id>
  --json`, follow the returned instruction/template/output path; no
  `--schema`), *If it fails* (do not improvise/guess/retry; follow the stop
  protocol the dispatch prompt already gives — pointed at, not restated).
  No restated role-prompt discipline (INV-26), no `--schema` (INV-27).
- **`install.sh`** (edited, `run_doctor` lines ~255-286) — G2. Replaced the
  hard-coded single `ui-designer` registration-count check with a loop over
  `${WS_SKILLS_DIR}/*/` (the shipped source the installer deploys from). For
  each shipped skill: asserts `${WORKSPACE_SKILLS_DIR}/<skill>/SKILL.md`
  exists and that `skills_state.json`'s `installed_plugins` contains exactly
  one entry with that `name`. A missing `SKILL.md` or a count other than 1
  fails `--doctor` (exit 1) and names the skill plus expected-vs-found state
  (INV-28/29/30). A missing `skills_state.json` entirely stays a `warn`
  (uninitialized gateway workspace ≠ missing registration). No change to
  `install_workspace_skills()`'s deployment loop — it already picks up the
  new directory automatically.
- **`tests/collapse/doctor_workspace_coverage.sh`** (new) — the five fixtures
  tasks.md §3 calls for: all-registered (pass), one unregistered (fail names
  skill + count 0), missing `SKILL.md` (fail names the file), duplicate
  registration (fail count 2, not deduped), missing `skills_state.json`
  (warn, not fail; no per-skill fail lines). Driven by `AI_DLC_SKILLS_DIR`
  pointed at a per-case fixture; asserts on the workspace-specific output
  lines so it is independent of the gateway/client checks.
- **`openspec/changes/openspec-author-conduit/IMPLEMENTATION_REPORT.md`** (new)
  — this file.

## Test suite result

**Not run in this environment.** The session's permission gate denied every
attempt to execute `python3.12` (pytest), `bash` on the collapse scripts, and
`bash -n` syntax checks. Only read-only inspection commands and the Write/Edit
file tools were permitted. The implementation is therefore **unverified by
me** — the user must run the suite:

```
python3.12 -m pytest -q tests/
for t in tests/collapse/*.sh; do bash "$t" || echo "FAIL: $t"; done
```

`tests/collapse/doctor_workspace_coverage.sh` was written to match the existing
`doctor_opendesign_check.sh` / `l4_doctor.sh` patterns (assert on
workspace-specific lines, independent of the live gateway state) and is picked
up by the `tests/collapse/*.sh` glob automatically. No existing test was
modified, so the only intended behavioral change is `--doctor`'s workspace
section — which the existing `l4_doctor.sh` / `doctor_opendesign_check.sh`
assertions do not constrain (they check executables, gateway, OpenDesign, MaaS
key, and the absence of budget/cost references, none of which the G2 edit
touches). Expected: no regression in the existing suite; the new file adds
coverage.

## Live end-to-end (tasks.md §4)

**Not run.** No access to a live gateway target in this environment, and
script execution was permission-blocked regardless. The three §4 steps
(real `install.sh --target` deploy + register; `--doctor` exit-code flip on
deliberate un-registration; real `plan.py dispatch`/`phase` with
`openspec instructions …` appearing in evidence-frame `commands_seen`) were
not executed. Per the PRD, `authoring_skill_state().ok == true` alone does
not satisfy the acceptance bar — the frames must show the CLI invoked
in-session. That bar remains **unmet by this work** and must be checked by a
human with a live gateway before merge.

## Commits

**Not made.** `git add` / `git commit` were denied by the session permission
gate on every attempt. The three logical commits the task requested exist only
as uncommitted working-tree changes:

1. G1 — `supervisor/skills/workspace/openspec-author/SKILL.md`
2. G2 — `install.sh` (doctor workspace loop) + `tests/collapse/doctor_workspace_coverage.sh`
3. Report — this file

Suggested commit commands (run after verifying tests):

```
git add supervisor/skills/workspace/openspec-author/SKILL.md
git commit -m "ai-dlc: G1 openspec-author conduit skill"
git add install.sh tests/collapse/doctor_workspace_coverage.sh
git commit -m "ai-dlc: G2 doctor workspace coverage loop + tests"
git add openspec/changes/openspec-author-conduit/IMPLEMENTATION_REPORT.md
git commit -m "ai-dlc: implementation report for openspec-author-conduit"
```

## Could not complete

- **Committing** each item as its own commit (permission gate).
- **Running the full test suite** to confirm no regression (permission gate).
- **The live end-to-end check** in tasks.md §4 — no live gateway access in
  this environment; this is the PRD's real acceptance bar and must be run by a
  human before close.
- **`plan.py validate` / `report.py deliver` / MERGE_GATE** (tasks.md §5) —
  out of scope for this implementation pass and not executable here.

## Verification addendum (post-delegation, by the reviewing session)

All items this report flagged as unverified were subsequently run for real:

- `bash -n install.sh` — clean.
- `python3.12 -m pytest -q` — **118 passed**, 0 failed (unchanged from
  before this change — these are pre-existing unit tests, not the new
  shell gate).
- `bash tests/collapse/doctor_workspace_coverage.sh` — **pass**, all five
  fixture cases as designed.

**Live end-to-end (tasks.md §4) — all three steps run for real:**

1. `install.sh --doctor` before deploying the workspace skills showed
   `workspace skill 'openspec-author' not installed: SKILL.md missing`
   (exit 1). Ran `./install.sh` (default, no flags — the branch that calls
   `install_workspace_skills()`; `--target <name>` alone does not, since
   workspace skills are shared across targets, not per-target). After
   install, `--doctor` showed `workspace: openspec-author registered (1
   entry, SKILL.md present)` and exited 0 — confirming the doctor fix
   actually detects both states, not just the healthy one.
2. Dispatched a real `proposal` role (`plan.py dispatch --role proposal`)
   against an isolated, migrated scratch repo. `authoring_skill_state()`
   correctly reported `verified_before_dispatch: true`, and the dispatch
   completed (`boundary: clean`).
3. **The PRD's real acceptance bar**: grepped the resulting evidence file
   (`evidence/plan-proposal-1.jsonl`) and found the role actually ran
   `openspec instructions proposal --change oactest --json` — the exact
   command, for real, inside the session — and wrote `proposal.md` in the
   real `openspec` CLI's own template shape (`## Why / ## What Changes /
   ## Capabilities / ## Impact`), not the `Why/What Changes/Non-goals`
   shape a hand-written proposal in this repo normally takes. This
   confirms the artifact came from the CLI, not from memory or the
   dispatch prompt.

One pre-existing, unrelated bug was hit and worked around (not fixed) to
complete step 2-3: the plane root's git dubious-ownership issue (the exact
bug `docs/prd-plane-git-boundary-and-rollback-anchor.md` targets, on a
separate branch/worktree) blocked the pre-dispatch boundary baseline until
a temporary `git config --global --add safe.directory <that one scratch
plane path>` was added for the duration of the test and removed
immediately after. This is independent of openspec-author-conduit and is
being fixed properly, narrowly (not via global config), in the other
change.

All scratch repos, plane trees, records, and the temporary global git
config entry were removed after verification; nothing left over.
