# Design — ROUTE self-check + phase-chain close hook + intent-scenario suggest

## G1 — close hook

`cmd_close`'s existing tail (merge → archive → cleanup) gets one more step,
strictly after archive succeeds: look up the closed change id across
`.ai-dlc/initiatives/*.json` (same lookup `initiative advance` already does
internally) and, on a match, call the same function
`plan.py initiative advance --change <id>` calls today. No new function; a
new call site. A change id absent from every manifest leaves `close`
byte-identical to today (regression case, see spec).

## G2 — doctor advisory

New function in `bin/report.py`, named for symmetry with
`design_auto_due`/`codegraph_auto_due`:

```
route_doctor_advisory(repo: Path) -> str | None
```

Checks, in order, stopping at the first failure:
1. `bin/plan.py` and `bin/report.py` exist and are executable.
2. `config/collapsed.config.yaml` exists and parses.
3. The gateway client configured for dispatch is reachable (a cheap
   connectivity probe, not a full dispatch).

Returns `None` when all pass; otherwise a single human-readable string
naming the failed check and a copy-pasteable repair command (e.g. "run
`./install.sh` from `<canonical-source>`"). `cmd_next` calls this once and,
if non-`None`, adds it under a new `advisory` key in its existing return
object. No existing key's meaning changes.

## G3 — suggest

New subcommand `plan.py suggest --repo <repo> [--change <id>] "<text>"`.

Candidate table (fixed, not user-configurable in this version):

| name | signal |
|---|---|
| `inline_quick_fix` | text implies a single file / mechanical edit; `classify_target` reports small |
| `planned_full_pipeline` | text mentions multiple modules or "architecture"; `codegraph-scope` applicable |
| `prd_spec_only` | text explicitly asks for PRD/spec output before implementation |
| `design_first` | `design-scope` reports the change's surface is web/deck |
| `deploy_extra_gate` | text or recent diff mentions deploy/production/prod |

Scoring reuses `_extract_change_keywords`'s IDF/CJK-bigram tokenizer against
each candidate's keyword set; ties broken by declaration order in the table
above. Output: up to 4 `{name, why, first_command}` objects, JSON to stdout.
An all-zero score returns an empty list plus a one-line fallback pointing at
`plan.py next`'s default judgment — never a forced non-empty answer.

## G4 — install version sync check

New root file `VERSION` (single-line semver). `install.sh`'s existing
install path copies it alongside the rest of the toolchain into any target
directory the same way it already copies `SKILL.md`/`config/`. New flag
`--check-sync`: for each target path listed in `targets/*.json`, read its
`VERSION` file (missing file counts as a mismatch, reported as such — not a
crash) and compare byte-for-byte against the repo's own `VERSION`; append
one line per mismatch to `--doctor`'s output. Exit code of `--doctor` is
unaffected by a mismatch (advisory, not a failure gate — consistent with
G2's INV-21).
