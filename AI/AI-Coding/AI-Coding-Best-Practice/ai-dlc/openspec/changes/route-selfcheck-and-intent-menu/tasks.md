# Tasks — ROUTE self-check + phase-chain close hook + intent-scenario suggest

## 1. G1 — close hook

- In `cmd_close`, after archive succeeds, look up the closed change id
  across `.ai-dlc/initiatives/*.json` and call the existing `advance`
  function on a match.
- No new data contract, no new file — reuse Phase A's implementation.
- Test: a change id in no manifest leaves `close`'s behavior and output
  byte-identical to pre-change (regression case named in the PRD).

## 2. G2 — `route_doctor_advisory`

- Implement in `bin/report.py`: file/exec checks, config parse check,
  cheap gateway reachability probe, in that order, first-failure-wins.
- Wire into `cmd_next`: add `advisory` key to its return object only when
  non-`None`; existing keys (`stage`, `blocked_on`, `do`, `then`,
  `not_yet`) unchanged in shape and meaning.
- Test: all-healthy returns `None`/no `advisory` key; each of the three
  checks failing independently produces a distinct, correctly-worded
  advisory string; a failing check never changes `next`'s exit code or
  its other fields.

## 3. G3 — `plan.py suggest`

- New subcommand parser: `--repo` (required), `--change` (optional),
  positional free-text argument.
- `score_candidates(text, repo, state)` reusing
  `_extract_change_keywords`'s tokenizer against the fixed candidate table
  in `design.md`.
- Output up to 4 ranked `{name, why, first_command}` objects as JSON.
- Test: each candidate table row's trigger signal produces that candidate
  ranked first for a representative input string; an unrecognizable input
  produces the empty-list fallback; output never exceeds 4 entries even
  when more than 4 candidates score above zero; command performs no
  writes (assert no file mtime changes across the call).

## 4. G4 — `install.sh --check-sync`

- Add root `VERSION` file; ensure the existing install path copies it into
  every target the same way `SKILL.md` is copied today.
- Add `--check-sync` flag: iterate `targets/*.json`, compare each target's
  `VERSION` against the repo's own, append a line to `--doctor` output per
  mismatch (missing target `VERSION` file counts as a mismatch, not a
  crash).
- Test: matching versions produce no output line; a mismatched or missing
  target `VERSION` produces exactly one line naming the target path and
  both version strings; `--doctor`'s exit code is unaffected either way.

## 5. CHECK → REPORT → MERGE_GATE

- `plan.py validate` for the signed spec verdict on this proposal + specs.
- `report.py deliver` for the delivery report.
- Present the diff and validator conclusion at MERGE_GATE for the human;
  no merge without an approved, rationale-carrying answer.
