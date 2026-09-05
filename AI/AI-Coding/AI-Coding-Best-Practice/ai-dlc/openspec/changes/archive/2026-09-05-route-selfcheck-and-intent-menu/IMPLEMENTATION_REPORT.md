# Implementation Report — ROUTE self-check + phase-chain close hook + intent-scenario suggest

Branch: `ai-dlc/route-selfcheck-and-intent-menu-v0.22.0`
Date: 2026-09-05

## What changed

- **`bin/plan.py`** — G1 + G3.
  - G1: `cmd_close` now looks up the closed change id across
    `.ai-dlc/initiatives/*.json` (reusing
    `initiative._find_manifest_for_change`) after merge + archive succeed
    and, on a match, calls the existing Phase A `init_advance` function
    (no second implementation). A change in no manifest skips the hook
    entirely → byte-identical to pre-change. Advancement failure is
    surfaced under `initiative_advance` but never affects the closed
    phase's record or close's exit code (INV-20).
  - G3: new `suggest` subcommand + `score_candidates` reusing
    `_tokenize_query` (the IDF/CJK-bigram tokenizer
    `_extract_change_keywords` uses) against a fixed 5-row candidate
    table; up to 4 ranked `{name, why, first_command}` objects, empty-list
    fallback on all-zero, read-only (INV-23/INV-24). `--change` reshapes
    `design_first`'s rationale when a `design_selection` is already
    recorded.
- **`bin/report.py`** — G2.
  - New `route_doctor_advisory(repo) -> str | None`: read-only subset of
    `install.sh --doctor` (toolchain scripts present+executable, config
    parses, gateway client reachable), first-failure-wins, never raises.
  - `cmd_next` is now a thin wrapper around the original body
    (`_cmd_next_base`) that runs the advisory once and injects an
    `advisory` key only when non-`None`. Exit code and existing fields
    are unchanged (INV-21/INV-22).
- **`install.sh`** — G4.
  - `install_full_toolkit` explicitly copies the root `VERSION` into each
    full-toolkit target with a read-back (the existing `cp -r` already
    carried it; this makes the contract explicit).
  - New `run_check_sync()` + `--check-sync` flag: iterates
    `targets/*.json`, compares each full-toolkit target's `VERSION`
    against the repo's own, names drift per mismatch (missing target
    `VERSION` = mismatch; registered target absent locally = skip).
    With `--doctor`, appends to its output; never changes `--doctor`'s
    exit code (INV-25).
- **`VERSION`** — new root file, `0.22.0`.
- **`tests/collapse/dt1_gates.sh`** — added `suggest` to the expected
  `plan.py` subcommand list (the one gate-line update the PRD §06
  anticipated).
- **`tests/test_close_initiative_hook.py`** (new) — G1 tests: registered
  advance, unregistered byte-identical, archive-fail no-op, no-approval
  no-op, advance-failure isolation.
- **`tests/test_route_doctor_advisory.py`** (new) — G2 tests: all-healthy
  → `None`, each of the three checks failing independently, first-failure
  ordering, `cmd_next` wiring (advisory key present/absent, exit code
  unchanged), read-only.
- **`tests/test_suggest.py`** (new) — G3 tests: each candidate row's
  trigger ranks it first, unrecognizable → empty fallback, ≤4 cap,
  read-only, `--change` design_selection reshapes rationale, CJK triggers.
- **`tests/collapse/g4_check_sync.sh`** (new) — G4 tests: matching silent,
  mismatch + missing each produce one drift line naming both versions,
  absent target skipped, `--doctor` exit code unchanged, read-only.

## Non-goals respected

No git-hook bypass guard, no G2 auto-repair, no G4 auto-sync, no
cost/budget gate. `suggest` writes nothing; `route_doctor_advisory`
writes nothing; `--check-sync` writes nothing. `openspec` CLI was not
invoked to produce or validate any content.

## Test suite result

**Not executed in this environment.** Every `python3` / `python3.12` /
`pytest` / `bash <script>` invocation — including `bash -n install.sh`
and the gate scripts — was refused by the session's permission rules
("This command requires approval", auto-denied). File edits (Edit/Write)
and read-only git succeeded; no command that could execute Python or
mutate git state was permitted.

Consequently the four items are implemented and their tests are written,
but **the full suite has not been run green by me**. The user must run:

```
python3.12 -m pytest -q
bash tests/collapse/dt1_gates.sh
bash tests/collapse/g4_check_sync.sh
```

and the rest of `tests/collapse/*.sh` to confirm no regression. All
commits are also pending — `git add` / `git commit` were likewise
blocked by the same permission rules, so the changes remain uncommitted
in the working tree (see `git status`). The intended per-item commits
are G1 (plan.py + test_close_initiative_hook.py), G2 (report.py +
test_route_doctor_advisory.py), G3 (plan.py + test_suggest.py +
dt1_gates.sh), G4 (VERSION + install.sh + g4_check_sync.sh), then this
report.

## Incomplete items

None of the G1–G4 deliverables are left unfinished. The only unfinished
steps are those the environment blocked: running the test suite and
creating the git commits. No item from `tasks.md` was skipped or
deferred for design reasons.

## Verification addendum (post-delegation, by the reviewing session)

claude-maas's file edits were reviewed by hand against the live codebase
(confirmed `_tokenize_query`, `AI_DLC_CLIENT` default, and the
`targets/*.json` field schema all match existing code — nothing
hallucinated), then actually executed, since the headless session's own
permission rules had blocked every Python/git invocation:

- `python3.12 -m pytest -q` — **118 passed**, 0 failed (27 of those are
  the new G1/G2/G3 tests; the rest is the pre-existing suite, unchanged).
- `bash tests/collapse/dt1_gates.sh` — fails on `v0.8.0:bin/oracle.py
  missing — deletion has no rollback anchor` (a missing git tag object).
  Confirmed **pre-existing**: the same failure reproduces identically on
  `main` in a throwaway worktree, before any of this change's commits —
  unrelated to G1–G4, not a regression introduced here.
- `bash tests/collapse/g4_check_sync.sh` — **pass**.
- `bash -n install.sh` — clean.

Commits were then made in 3 groups rather than the 4 originally sketched
above (G1 and G3 both land in `bin/plan.py`, so they were committed
together rather than hand-splitting one file's diff into two patches):

- `7b5c8d2` — G1 (close→initiative-advance hook) + G3 (`plan.py suggest`)
- `9138ce1` — G2 (`route_doctor_advisory` + `plan.py next` wiring)
- `7eaebd2` — G4 (`VERSION` + `install.sh --check-sync`)

Not done, and left for a human: `plan.py validate` (CHECK, dispatches to
the plane), `report.py deliver` (REPORT), and `report.py gate --request`
→ `plan.py close` (MERGE_GATE) — per this tool's own hard rule, no merge
without a human's approved, rationale-carrying answer. This branch
(`ai-dlc/route-selfcheck-and-intent-menu-v0.22.0`) has not been pushed.
