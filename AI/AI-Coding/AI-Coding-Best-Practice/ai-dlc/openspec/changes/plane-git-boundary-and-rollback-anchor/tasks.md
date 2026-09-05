# Tasks — plane git safe.directory + rollback-anchor SKIP state

## 1. G1 — `git_run()` helper

- Add `git_run(args, repo, cwd=None, timeout=None)` next to the existing
  `run()` in `bin/plan.py`, per `design.md`.
- Test: constructed argv has `-c safe.directory=<repo>` before `-C`.
- Test: on a directory owned by a different uid than the test process
  (simulate via a temp dir + `sudo chown` in the test fixture, or skip
  with a clear reason if the test environment can't chown), a raw
  `run(["git","-C",dir,"status"])` fails with dubious-ownership while
  `git_run(["status"], dir)` succeeds.

## 2. G2 — `git_status_paths()`

- Route its single git call through `git_run()`. No signature change.
- Test: existing callers (`boundary_scan`, `_run_role`) unaffected by the
  internal change — same return shape for the healthy case.

## 3. G3 — `cmd_sweep`

- Both direct git calls (`ls-files`, `checkout --`) route through
  `git_run()`.
- Test: `cmd_sweep` against a plane-root-owned fixture (different uid)
  succeeds where it previously failed with dubious-ownership.

## 4. G4 — boundary failure classification

- Extend `git_status_paths` to surface *why* it failed (captured stderr)
  without breaking its existing `list[str] | None` contract for callers
  that don't need the detail — e.g. an optional second return via a
  small wrapper, or a module-level "last git error" the caller can read
  immediately after a `None` result. Pick whichever is less invasive to
  the existing call sites; record the choice and why in
  IMPLEMENTATION_REPORT.md.
- `_run_role`'s baseline-snapshot failure path includes this detail in
  its returned dict (a new field, existing `"boundary": "unknown"` stays
  as the outcome label — INV-33 requires the two failure causes stay
  distinguishable in the structure, not that the outcome label changes).
- Test: a target that doesn't exist vs. a target git genuinely can't read
  produce distinguishable detail in the returned dict.

## 5. G5 — `dt1_gates.sh` SKIP state

- Implement per `design.md`'s exact script logic: `git rev-parse -q
  --verify v0.8.0` absent → SKIP line, no exit; tag present but
  `git cat-file -e v0.8.0:bin/oracle.py` fails → FAIL, exit 1 (unchanged
  behavior for a genuinely broken anchor).
- Test: run `dt1_gates.sh` in this repo (no `v0.8.0` tag) — assert SKIP
  line appears, exit code for the *overall script* is 0 (assuming every
  other check in the file passes).
- Test (fixture repo): create a tag `v0.8.0` pointing at a commit that
  does NOT contain `bin/oracle.py` — assert FAIL, exit 1 (the "tag exists
  but broken" path still works).

## 6. G6 — SKILL.md

- Add the one-line correction under the `Oracle plane: v0.8.0` bullet in
  "Retired (rollback anchors)", per `design.md`.

## 7. Investigate (record findings, no code change required unless found broken)

- Check whether `v0.5.1-delegated-final` (the other retired anchor) is
  reachable via `git rev-parse -q --verify v0.5.1-delegated-final` in
  this repo. Record the result in IMPLEMENTATION_REPORT.md. If also
  unreachable, do NOT silently apply the same SKIP treatment to it in
  this change — flag it for a follow-up decision instead (§ Non-goals).

## 8. CHECK → REPORT → MERGE_GATE

- `plan.py validate` for the signed spec verdict.
- `report.py deliver` for the delivery report.
- Present the diff and validator conclusion at MERGE_GATE for a human;
  no merge without an approved, rationale-carrying answer.
