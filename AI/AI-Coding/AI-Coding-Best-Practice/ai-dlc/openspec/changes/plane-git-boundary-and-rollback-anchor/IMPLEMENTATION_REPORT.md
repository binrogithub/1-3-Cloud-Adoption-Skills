# Implementation Report — plane git safe.directory + rollback-anchor SKIP

Change: `plane-git-boundary-and-rollback-anchor` (v0.24.0)
Branch: `ai-dlc/plane-git-boundary-and-rollback-anchor-v0.24.0`
Date: 2026-09-05

## What changed

| File | Change |
|---|---|
| `bin/plan.py` | **G1** added `git_run(args, repo, cwd=None, timeout=None)` next to `run()`; it builds `["git", "-c", f"safe.directory={repo}", "-C", str(repo)] + args` and calls `run()` — a per-process argument, never written to any config file. |
| `bin/plan.py` | **G2** `git_status_paths()` now calls `git_run(["status","--porcelain","-uall"], repo)` instead of `run(["git","-C",str(repo),...])`. No signature change. |
| `bin/plan.py` | **G3** `cmd_sweep`'s two direct git calls (`ls-files`, `checkout --`) now route through `git_run([...], root)`. |
| `bin/plan.py` | **G4** `git_status_paths` captures stderr into a module-level `_GIT_STATUS_LAST_ERROR` on failure (cleared on success); `_run_role`'s baseline-snapshot failure path reads it and returns a `git_error` field when the target is an existing directory but git errored, vs. a distinct "target not readable or not a directory" message when it isn't. `"boundary": "unknown"` stays as the outcome label for both. |
| `tests/collapse/dt1_gates.sh` | **G5** rollback-anchor check now probes `git rev-parse -q --verify v0.8.0` first: tag absent → named `SKIP` line, no non-zero exit; tag present but `bin/oracle.py` missing → `FAIL` + `exit 1` (unchanged). Header comment + final echo updated to not claim unconditional verification. |
| `SKILL.md` | **G6** one-line correction under the `Oracle plane: v0.8.0` bullet noting the anchor is not reachable in this repo's history (a republished copy). |
| `tests/test_plane_git_boundary.py` | new — unit/integration tests for G1–G5 (argv construction, foreign-uid contrast, `git_status_paths` routing + healthy path, `cmd_sweep` routing, G4 distinguishability, and the three `dt1_gates.sh` anchor branches plus the in-repo SKIP acceptance). |

No other files touched. `cmd_migrate`'s chown/mode logic, global git config, environment variables, and all non-plane git call sites are unchanged.

## G4 — error-detail plumbing: mechanism choice and why

**Chosen: a module-level `_GIT_STATUS_LAST_ERROR` string that the caller reads immediately after a `None` result.**

Why (least invasive):
- `git_status_paths`'s existing contract is `list[str] | None`, and every
  current caller relies on that shape — notably `cmd_sweep` does
  `git_status_paths(root) or []` and `boundary_scan` / `_run_role` test
  `is None`. Returning a `(list[str] | None, str | None)` tuple would make
  the `or []` fallback always truthy (a 2-tuple is truthy even when its
  first element is `None`) and force every call site to unpack — invasive
  across the codebase.
- A small result object has the same problem: it breaks `... or []` and
  `is None` at every caller.
- A module-level "last error" slot changes no signature, breaks no caller,
  and is read only by the one caller (`_run_role`) that needs the detail,
  immediately after the `None` it just observed. The slot is cleared on
  every successful call, so it never carries stale detail into a later
  unrelated failure.

The two failure causes stay distinguishable in the returned dict (INV-33):
- target not a directory / not readable → `{"boundary": "unknown",
  "error": "baseline snapshot target not readable or not a directory: <path>"}`
  (no `git_error` field).
- target is an existing directory but git itself errored →
  `{"boundary": "unknown", "error": "git status failed (baseline snapshot)",
  "git_error": <captured stderr>}`.

The outcome label `"boundary": "unknown"` is retained for genuinely
indeterminate cases per tasks.md / the spec; the `git_error` field's
presence/absence is what distinguishes the two causes.

## G7 — `v0.5.1-delegated-final` reachability

`git tag` in this repository returns no tags. Accordingly
`git rev-parse -q --verify v0.5.1-delegated-final` fails: the tag is
**not reachable** in this repo's history (same situation as `v0.8.0` — a
republished copy whose pre-history did not carry the tag forward).

Per the change's Non-goals, the same SKIP treatment was **not** applied to
`v0.5.1-delegated-final` in this change. It is flagged for a separate
follow-up decision: a future change should decide whether `dt1_gates.sh`
(or whichever gate references it) should gain the same tag-absent SKIP
branch for `v0.5.1-delegated-final`, or whether that anchor is referenced
nowhere and can be left as a historical note only. `SKILL.md`'s
"Delegated orchestrator: `v0.5.1-delegated-final`" bullet was left
unchanged for the same reason — correcting it is part of the follow-up,
not this change.

## Test suite result

Tests written: `tests/test_plane_git_boundary.py` covers every Tests
section in `tasks.md`:

- G1: argv has `-c safe.directory=<repo>` before `-C`; cwd/timeout
  pass-through; on a foreign-uid repo `git_run` succeeds where raw `run`
  fails with dubious-ownership (skipped if the environment can't chown or
  can't reproduce the refusal).
- G2: `git_status_paths` healthy path returns the right paths; it routes
  through `git_run` (stubbed).
- G3: `cmd_sweep` routes its `ls-files` (and `checkout --`) through
  `git_run` (stubbed).
- G4: `git_status_paths` failure captures stderr into
  `_GIT_STATUS_LAST_ERROR`; success clears it; `_run_role`'s two failure
  branches produce distinguishable dicts (`git_error` present vs. absent)
  while both keep `"boundary": "unknown"`.
- G5: the anchor block SKIPs (exit 0) when the tag is absent, FAILs
  (exit 1) when the tag exists but `bin/oracle.py` is missing, and passes
  (exit 0, no SKIP/FAIL) when both exist; plus the in-repo acceptance
  test asserting `dt1_gates.sh` emits SKIP and exits 0 in this checkout.

**Execution status:** the session sandbox blocked execution of `pytest`
and the `tests/collapse/*.sh` scripts (commands that execute code or
write git state require user approval that was not granted during this
turn). The code was verified by review against the design and specs; the
exact commands to run for a green suite are:

```
python3 -m pytest -q tests/                          # all python tests
bash tests/collapse/dt1_gates.sh                     # should now SKIP + exit 0
for s in tests/collapse/*.sh; do bash "$s"; done     # full collapse suite
```

Expected: `dt1_gates.sh` exits 0 with a `SKIP: v0.8.0 anchor not carried
by this repo's history …` line (previously exited 1). No other gate's
behavior should change — `git_run`'s `safe.directory` override is a no-op
on same-owner repos, and no non-plane git call site was touched.

## Anything not completed

- **Test execution / commits:** all code, tests, and this report are
  written, but the sandbox blocked running the suite and making the git
  commits during this turn. The commits (one per section G1–G6, plus the
  test file, plus this report) still need to be made — see the command
  list above for the verification run, then commit per section.
- **G7 follow-up:** `v0.5.1-delegated-final` is unreachable and was
  intentionally not given the SKIP treatment in this change; flagged for
  a separate decision.

## Verification addendum (post-delegation, by the reviewing session)

The production code (G1-G4 in `bin/plan.py`, G5 in `dt1_gates.sh`, G6 in
`SKILL.md`) was reviewed by hand against the design and specs and matched
exactly -- no changes needed there. Two real, separate bugs were found
and fixed during verification, neither in the production code:

**Bug 1 -- the new test file's own git fixtures.** `test_plane_git_boundary.py`
deliberately nulls global/system git config (`GIT_CONFIG_GLOBAL=/dev/null`,
correct for determinism) but never sets a local identity on its own
throwaway repos before committing -- every sibling test file in this repo
(`test_close_initiative_hook.py`, `test_codegraph_*.py`, etc.) does this
with a `config user.email`/`config user.name` pair before any commit. Four
tests failed with "Author identity unknown" as a result. Fixed by adding
the same two-line convention to all four affected fixtures
(`test_git_run_succeeds_on_foreign_owned_repo_where_raw_run_fails`,
`test_dt1_gates_skip_when_tag_absent`,
`test_dt1_gates_fail_when_tag_present_but_file_missing`,
`test_dt1_gates_pass_when_tag_and_file_present`).

**Bug 2 -- two collapse gate scripts' own plane-fixture git calls.**
`d3_plan_boundary.sh` and `l7_sweep.sh` (pre-existing scripts, not part
of this change's file list) call the real `plan.py migrate` via the
shared `lib_plane.sh` helper to build a realistic plane-root fixture
(exactly reproducing the swarm:swarm chown), then make their own raw
`git -C "$PLANE_ROOT" add/commit/checkout` calls to seed content into it
-- hitting the identical dubious-ownership refusal this change's G1-G3
exist to fix, except at the bash test-fixture layer rather than inside
`plan.py`. Fixed by adding a `plane_git()` helper to `lib_plane.sh`,
mirroring `git_run()` exactly (same `-c safe.directory=<path>` pattern,
same per-invocation scope, no global config), and routing the five
affected call sites in the two scripts through it.

**Test results after both fixes:**
- `python3.12 -m pytest -q` -- **131 passed**, 0 failed (127 pre-existing
  + the new `test_plane_git_boundary.py`'s tests).
- `bash tests/collapse/dt1_gates.sh` -- **SKIP: v0.8.0 anchor not carried
  by this repo's history (republished copy)**, exit **0** (was exit 1
  before this change).
- The four gates this PRD specifically targets --
  `d3_plan_boundary.sh`, `l7_sweep.sh`, `l7_target_safety.sh`,
  `open_plane.sh` -- all **pass**. (`open_plane.sh` needed a longer
  timeout than my first attempt; it's a real gateway-provisioning
  round-trip, not broken -- it was already slow before this change.)
- Full collapse suite re-run (47 of 48 scripts, `open_plane.sh` confirmed
  separately): **40 passed, 7 failed**. All 7 failures are pre-existing
  and unrelated to this change (verified against a baseline run at the
  pre-change commit): a hardcoded `/usr/bin/python3.9` path that doesn't
  exist on this host (`dr_review_round.sh`), a stale expected-text
  fixture in a doctor description check (`root_skill_sync.sh`), and
  others already flagged in the original review as separate, unrelated
  root causes. **No new regressions.**
- Net effect on the full 48-script suite compared to the pre-change
  baseline (30 passed / 18 failed): **41 passed / 7 failed**. Six of the
  eleven newly-passing gates beyond this change's own four targets
  (`ad_red_first`, `d4_reverse_cases`, `l3_resume`, `rs2_timing`,
  `rs3_concurrency`, `rs4_decide`) turned green as a side effect of the
  separate `openspec-author-conduit` change's real deployment to the
  shared gateway workspace (host-global state, not scoped to this
  branch) -- not because of anything in this branch's own code.

All temporary git config overrides used during manual verification
(`--global --add safe.directory` on one scratch plane path, added and
removed for an earlier, separate test) were confirmed absent from this
host's global git config before finishing.
