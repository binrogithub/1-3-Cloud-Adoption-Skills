---
name: ai-dlc
description: Spec-driven coding lifecycle for AI coding agents — executes a task through ROUTE→WORK→[DESIGN]→CHECK→REPORT→MERGE_GATE with a spec validator and a human-held merge gate. Use for multi-step or planned software engineering work in a git repo that wants a structured, auditable delivery flow with a signed spec verdict and an approved merge. Not for one-off quick answers, pure Q&A, or non-coding chat.
---

This skill's own directory (wherever it was installed — e.g.
`~/.codex/skills/ai-dlc/`) also contains the full toolkit: `bin/plan.py`,
`bin/report.py`, `config/`, `openspec/`. Run those from this skill's own
directory, targeting whatever project you're actually developing with
`--repo <path-to-that-project>` — this skill's directory itself is the
tool, not the thing being worked on.


# AI-DLC Doctor

`./install.sh --doctor` checks: bin/report.py and bin/plan.py present,
config present, the environment's validator discriminates (the smoke
runs it host-side — a valid change passes `--strict`, a scenario-less
requirement is rejected; inside a run the caller reads verdicts only as
signed records), and the planning dispatch can reach the gateway — the client it invokes, the
service it talks to, the config that service reads. No cost or budget
gate is checked; none exists. Exit 0 healthy, 1 a check failed.

<!-- L0 · first screen — self-contained (V4). Read this + `plan.py next` and
     you can run a task. L1 (full flow) and L2 (boundaries) are below. -->

# AI-DLC — you write the code; the plane validates the spec; a human holds the merge gate.

## Don't read these
`CHANGELOG.md` and `docs/` are human-facing history and design rationale.
Task execution never needs them — everything you need is in this file and
`plan.py next`.

## Ask the system, don't memorize 26 commands
```bash
python3 bin/plan.py next --task-dir <td> --repo <repo>
```
Returns `stage`, `blocked_on`, `do` (a directly executable command),
`then`, and `not_yet` (what you can't run yet + the exit code it would give).

## The flow
`INIT → ROUTE → WORK → CHECK → REPORT → MERGE_GATE`. Work in `<repo>`,
state under `.ai-dlc/tasks/<task_id>/`. Worktree first; nothing merges
except through MERGE_GATE. 1–3 files → inline; 4+ → planned.

0. **INIT** — if `<repo>` does not exist or is not a git repo, create the
   directory and run `git init` + an initial empty commit so worktree
   operations work. A path that cannot be created is refused, not silent.
1. **ROUTE** — `report.py init --route inline|planned --change <id>`.
2. **WORK** — read, write code, run tests. Planned: `plan.py validate` for the
   signed spec verdict.
3. **REPORT** — `report.py deliver` measures landed files + spec validity.
4. **MERGE_GATE** — `report.py gate --request` → human answers with rationale
   → `plan.py close` merges, archives, cleans up.

## Three rules that bite
1. **No auto-merge.** A human approves with a rationale or nothing merges.
2. **No report is verification.** Present the diff; the human reads it.
3. **--repo must be an existing git repo.** A typo'd path is refused, not silent.
4. **A live result is not `delivered`.** A page that renders, a server that
   answers on its port — none of that is the flow's definition of done.
   Before telling the user a task is finished, call `plan.py next` and do
   what it says; if `do` names `report.py deliver`, run it. Only
   `delivered: true` (or an explicit sweep) closes a task.

## Signed by a human, never a model
Gate approvals, route exceptions, and design skips must name a human
(`--approver <name>`, `--author <name>`). A model name is refused.

---
<!-- L1 · full task flow — read when you need the why behind a step -->

## Routing table (decide BEFORE reading the code)

| Judgment | Action | Route |
|----------|--------|-------|
| 1–3 files, or one mechanical change | inline, done | inline |
| 4+ files / reading-is-for-writing / 2+ non-trivial changes | planning plane: roles author the change artifacts; you implement inline | planned |
| A persistent artifact would materially reduce ambiguity | propose the planning plane; the human decides | planned |

Size, file count, or risk never select the plane alone. Record the route
(`report.py init --route planned --change <id>`). Any other value
is rejected at init, and a task record that carries a value naming no
existing plane stops the run for the human rather than guessing an
equivalent.

The count is one configured number — `execution.planning_threshold_files`
(currently **4**) in `config/collapsed.config.yaml` — and it is not prose:
`report.py deliver` measures the change's product files (task records,
evidence, gateway bookkeeping and the openspec tree excluded, excluded
patterns listed beside the count) and an inline route carrying a change at
or above the number stops the task for a person. The options are to
re-run through the plane or to record an explicit exception with a reason
(`report.py exception`), which travels into the delivery report. No
configured number stops the task too — the check never assumes one.

## Task flow (full)

`INIT → ROUTE → WORK → DESIGN → CHECK → REPORT → MERGE_GATE`.
Work in `<repo>`, state under `.ai-dlc/tasks/<task_id>/`. Worktree first
(`git worktree add ../wt/<id> -b task/<id>`); nothing merges except
through MERGE_GATE.

**0 · INIT** — before anything else, ensure `<repo>` is a usable git repo:
if the directory does not exist, `mkdir -p` it; if it is not a git repo,
`git init` and make an initial empty commit (`git commit --allow-empty -m
"init"`) so `git worktree add` has a HEAD to branch from. If the repo
already exists with at least one commit, INIT is a no-op. A path that
cannot be created or initialised is refused and the run stops — that is
the typo guard, not a missing-feature error.

**1 · WORK** — you, inline: read what the task needs (not everything),
write the code, run the tests. Route planned: dispatch through
`bin/plan.py` — one role per artifact, judged from the event frames. The
target is admitted first: a tree holding source of a dependency this
project may never modify (delegate-router / jiuwenswarm / openjiuwen /
openspec source) is refused before the client exists, and a working
tree showing fewer files than its head commit (a sparse or partial
checkout) is reported and waits for a human's acceptance
(`--accept-partial-view`). A strict-validation rejection is returned
verbatim to the owning role; a
run stopped by an interrupt waits for the human — no automatic
re-dispatch. Re-entering planning resumes rather than restarts: roles
whose artifact openspec already reports done are skipped and recorded,
and a re-dispatched role continues its own named session — work already
paid for is never paid for again.

**1b · REVIEW (planned route)** — once the design artifact stands, run the
adversarial round: `plan.py review --change <id> --repo <repo> --axes
"axis: reason, ..."` (comma-free reasons; the stage flag stops after the
reviewers or resumes at the revision). The axes are the named list under
`review:` in `config/collapsed.config.yaml` — each chosen with a reason,
never more than the configured maximum, never off the list, never two
personas sharing a stance. Each reviewer holds exactly one axis and one
antagonistic persona, dispatched through the same per-role path (own
session, frames, boundary baseline), and files exactly one finding — or
an explicit nothing-found naming what it examined; a second finding, a
write outside its own path (the design included) or silence fails the
dispatch. Then **you synthesise the findings yourself** — no session is
opened for it, no role dispatched: you already hold the design and
every finding. Write `review/synthesis.md` in the round's record:
groups ordered by where in the design each finding lands, every
opposing pair named with what one increases and the other reduces (or
an explicit statement that none oppose — silence does not stand in for
it), every concern citing its finding as `- [axis] …`; the round fails
if a concern cites nothing, a filed finding appears in no group, or a
passage recommends or ranks between findings — the synthesis surfaces,
it never decides. `--stage synthesis` checks it; `--stage revision`
then dispatches the author once more with every finding in full, the
synthesis alongside, and the answers owed to the findings, not to the
synthesis — each answered on the record (`accepted: yes` + what
changed, or `no` + why); answering only the synthesis blocks as
unanswered. An unanswered finding blocks the phase from reporting
complete — it never touches the delivery criteria: the round and
the synthesis travel into the delivery report as advice, and nothing in
either gates delivery. Team mode is refused outright by reference to
`docs/team-mode-record.md` (a wildcard-matched team cannot be given
named reviewers, it is an order of magnitude slower, and its progress
is invisible until it ends — measured there, so refusing needs no new
experiment unless a proposal names a fact the record does not cover);
a roster role named for synthesis or leadership is refused the same
way — the reviewers are equal by construction.

**1c · DESIGN (v2: SELECT → SPECIFY → BUILD → VERIFY)** — design is a
**product that code must conform to**, not an action on finished code.
The frontend surface gets a concrete design spec before pages are written,
and the pages are mechanically verified against it. Four phases:

- **D0 SELECT** — a pre-built frontmatter index of 428 design candidates
  is scored down to a top-12 shortlist (millisecond, no session), then a
  120s small session judges the shortlist and answers: which `SKILL.md` +
  one-line reason. Result lands in `state.json.design_selection` (with
  `shortlist`, `chosen`, `skill_sha256`, `degraded`). On timeout, the
  highest-scored candidate is chosen with `degraded: true`.

- **D1 SPECIFY** — the ui-designer reads the selected `SKILL.md` full text
  and produces five design artifacts in `design/` — `tokens.css` (colors,
  spacing, typography as CSS custom properties), `tokens.json`
  (machine-readable), `components.md` (component specs), `pages.md` (page
  layouts), `assets.md` (asset requirements). These are **product files**:
  they count toward `landed_files`/`landed_bytes` — the merge gate sees
  them (S1 fix). D1 failure only loses five small files; the failure is
  isolated.

- **D2 BUILD** — you, the main session, write pages **per the spec**. No
  design decisions here — only content and assembly. Colors, font sizes,
  spacing come from `design/tokens.css`. Components match `components.md`.

- **D3 VERIFY** — six mechanical checks against the filesystem (never
  reads frames): `tokens_used` (every color/size/spacing in pages comes
  from tokens), `skill_sha_match` (SKILL.md sha256 equals
  design_selection), `components_conform`, `no_placeholder`
  (lorem/TODO/FIXME = fail), `design_artifacts_exist`, `tokens_json_valid`.
  Result: `design_verified` | `design_nonconforming` | `design_unspecified`.

`plan.py design --change <id> --repo <repo>` runs D0→D1→D3 automatically.
`report.py deliver` auto-dispatches it once via subprocess when the
surface carries a web/deck file and no design record stands. **Design
state never hard-blocks merge** — it is visible information at the gate,
not a gate itself. To skip: `report.py deliver --no-design` (skip is
reported, never silent) or `plan.py decide --design skip --change <id>
--repo <repo> --decided-by <name> --why <reason>`. The legacy
single-session 1800s rewrite path is behind `--retrofit`; `--shard N` is
the default for large surfaces.

**2 · CHECK** — the plane's signed validate verdict, never a CLI you
run: `plan.py validate --change <id> --repo <repo>` dispatches the
normalized command through openjiuwen and writes the signed record
(exit 22 = no verdict exists; exit 23 = the session's frames carried
no normalized call; otherwise the record's rc and validator text
travel verbatim — from the record, never from a tool you executed).
Then present the diff for human reading — that presentation IS the
check of correctness; no machine performs it.

**3 · REPORT** — `report.py deliver`: G-DELIVER-1 landed files/bytes from
the actual git diff (design/ files included — they are product files),
spec validity, design state (six states, visible not gating), and the
not-machine-checked statement. `delivered = head advanced ∧ product
files ∧ spec valid ∧ merge approved`; anything less reports honestly
(`spec_invalid` / `merge_pending`). Design state never makes `delivered`
false — it is reported for the human to read at the gate.

**4 · MERGE_GATE** — `report.py gate --request` → present one screen
(the diff for reading, validator conclusion) → the human answers with a
rationale → then the tail: `plan.py close --change <id> --repo <repo>`
merges the task branch, archives the change through the upstream
command, and removes the worktree and task branch the run created —
and only runs with an approved, rationale-carrying answer;
without one it reports waiting on a person and touches nothing. **No
auto-merge. Ever.** A run that stops without delivering leaves the
target as it found it: `plan.py sweep --change <id> --repo <repo>`
removes what the run introduced (never a path the pre-run baseline
carries — the skip is recorded), retains the openspec tree for a person
to commit, and keeps an unmerged task branch whose worktree holds the
only copy of the work, recording why.

## The states (all the human sees)

**Working → Checking → Ready | Needs your decision** — derived on every
write, never stored ahead. Token plumbing, retries, worker internals are
not shown unless asked; results and criteria only.

Design carries six states (visible, never gating): `design_unspecified`
(no spec artifacts) | `design_nonconforming` (spec exists, D3 checks
fail) | `design_verified` (all D3 checks pass) | `design_declined`
(skip recorded) | `design_not_applicable` (no web/deck surface) |
`design_unmeasured` (no files measured). The split of
`design_unspecified` ≠ `design_nonconforming` replaces the old
`design_unverified` — they mean different things to a human.

## Where usage lives (no budget exists)

Nothing here computes, caps or reports a token total. A dispatch's usage
is in the shipped plane's session history for that dispatch (the exact
record and its path: docs/plane-runtime.md §5); an executor's usage is
in its own agent transcript. The two follow different conventions — one
already includes the cache figure in its input figure, the other does
not — so they are read where they live and never combined.

---
<!-- L2 · boundaries & prohibitions — read when you need the guardrails -->

## Hard prohibitions

1. No shape constraints in task text. Behavior only.
2. Never reintroduce a cost gate, cap, warning or advisory total derived
   from a token figure computed here — budgeting is not provided
   upstream.
3. Never merge without an approved, rationale-carrying answer.
4. Never present a delivery report as verification of correctness — the
   human reads the deliverable; the report says so itself.
5. Never propose the upstream change-verification skill as a delivery
   gate (it infers from keyword search and prefers the softer finding);
   record its output as advice at most.
6. Never automatically re-dispatch a run stopped by an interrupt; only a
   validator rejection returns to the owning role.

## Two disciplines

1. **Strict spec validation is the plan criterion, and NO machine checks
   the artifact.** The plane's SIGNED validate verdict decides whether
   the change is well-formed — `plan.py validate` dispatches the
   normalized command through openjiuwen and you read the record; you
   never run the tool, and it is invisible to you (containment N1).
   Nothing decides whether the implementation is correct. The
   correctness judge is the human who reads the deliverable at the merge
   gate. Never present a report as verification, and never build a
   checker to fill the gap: that judgement belongs to the human.
2. **Task text writes behavior, never shape.** No "at least 4 modules",
   no file counts, no layering decrees. Measured on a CSV-parsing
   benchmark project, one shape
   sentence cost 12× wall / 11× input and bought −1 correctness. State
   structure as verifiable behavior ("the lexer is independently
   importable").

## Retired (rollback anchors)

- Delegated orchestrator: `v0.5.1-delegated-final`
- Oracle plane: `v0.8.0` (not reachable in this repo's history — a
  republished copy; the anchor is real in the original lineage, not this one)
- Budget capability: removed outright (landing L1) — nothing stops,
  warns or annotates on a token total computed here.
