## Why

A review of two real `/ai-dlc` sessions on claude-maas found four candidate
automations. Checking each against the current codebase showed two are
already shipped (jiuwenswarm subagent registration in `install.sh`,
codegraph-brief autodispatch in `report.py`/`plan.py`), one is half-shipped
(`plan.py initiative register/advance/status` landed in Phase A, but
`cmd_close` never calls `advance` — Phase B was explicitly deferred in
`docs/prd-phase-chain-automation.md` §08), and one is a real, previously
unrecorded gap: nothing in the session-facing flow (`SKILL.md`, `plan.py
next`) ever checks that the skill's own toolchain is actually installed and
reachable — `install.sh --doctor` only runs at install/bootstrap time. Both
observed sessions discovered a broken or partial install mid-task, at real
cost (a full DESIGN round spent finding and copying missing files by hand).

Separately, the person who commissioned this review asked for a second
capability: given a customer's free-text request and the repo's current
state, list the different automation routes available with their tradeoffs,
and let the human pick — rather than the session silently deciding for
itself and only narrating the decision in chat, as both observed sessions
did.

This change claims Phase B of phase-chain-automation, closes the toolchain
self-check gap, adds the requested advisory command, and closes the loop on
install-target version drift that made the toolchain gap possible in the
first place.

## What Changes

- **G1 — phase-chain-automation Phase B.** `plan.py close` calls the
  existing `initiative advance` function once its merge + archive succeed,
  for any change id that appears in an initiative manifest. Reuses the
  Phase A function; adds no new data contract.
- **G2 — ROUTE self-check advisory.** `plan.py next` runs a lightweight
  subset of `install.sh --doctor`'s checks (toolchain files present and
  executable, gateway reachable) before returning, and adds an optional
  `advisory` field to its output when a check fails. Never blocks the
  return; never modifies anything.
- **G3 — `plan.py suggest`.** A new read-only command:
  `plan.py suggest --repo <repo> [--change <id>] "<free text>"`. Scores a
  fixed set of candidate routes (inline quick fix, planned full pipeline,
  PRD/spec-only, design-first, deploy-needs-extra-gate) against the input
  text and repo state, using the existing IDF/keyword extraction already
  used for change-keyword scoring. Returns up to 4 ranked candidates, each
  with a one-line rationale and its first command — never executes,
  never writes state.
- **G4 — `install.sh --check-sync`.** A new `VERSION` file at the repo
  root; `--check-sync` compares it against the same file inside each
  installed target listed in `targets/*.json` and names any mismatch in
  `--doctor` output. Read-only.

## Non-goals

- No mechanism to block or intercept a session that bypasses `plan.py`
  entirely (direct `git commit`/`git push`/deploy outside the flow) — this
  is a real, separately-observed problem, but the fix (installing a git
  hook in the user's own repositories) has a materially larger blast
  radius and needs its own security/scope review. Recorded for a future
  change.
- `plan.py suggest` never executes a candidate, never opens a session,
  never writes to `state.json` or `events.jsonl` — advisory only.
- No cost/budget gate of any kind (per `SKILL.md`'s standing prohibition).
- No change to `report.py deliver`, `plan.py design`, or
  `config/collapsed.config.yaml`'s `planning_threshold_files`.
- G2's self-check reports only; it never auto-repairs a broken install.
- G4 reports only; it never auto-syncs an installed target.
- No automatic `initiative register` from parsing a PRD's phase language —
  registration stays a manual, explicit call.
