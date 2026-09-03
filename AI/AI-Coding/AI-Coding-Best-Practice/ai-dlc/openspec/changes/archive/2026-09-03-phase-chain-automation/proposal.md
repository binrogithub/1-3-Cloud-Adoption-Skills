## Why

A multi-phase initiative today exists only as prose. `openjiuwen-efficiency-v1`
splits an optimization effort into three phases inside its `proposal.md`, but
`.ai-dlc/tasks/` carries no field connecting those phases to one another.
Nothing records which change is phase 1 of what, and nothing creates phase 2's
task skeleton when phase 1 merges. A separate task (`frontend-design-tokens`)
shows the same class of gap at the single-task level: a delivery report can
print the exact remedy command and still nothing carries it to a person. This
change addresses the multi-phase case: give an initiative a small persistent
record, and queue the next phase's task skeleton automatically once the
current phase's merge gate is approved and closed — without touching WORK,
CHECK, REPORT, or MERGE_GATE for the new phase.

## What Changes

- A new data contract, `.ai-dlc/initiatives/<initiative-id>.json`, recording
  an ordered list of phases (`change_id`, `status`) for one initiative.
- A new `plan.py initiative` command group:
  - `register` — create or update a manifest from an ordered list of change
    ids (manual, no side effect beyond writing the file).
  - `advance` — given a change id that just closed, mark it `delivered` in
    its manifest and, if the next phase is `pending`, run the same
    initialization path `report.py init` already uses to create that
    phase's task skeleton (`queued`); if no next phase remains, mark the
    initiative `complete`. Writes `INITIATIVE_PHASE_QUEUED` /
    `INITIATIVE_COMPLETE` to the repo's `events.jsonl`.
  - `status` — read-only, prints each phase's current state.
- A new step at the tail of `plan.py close`, strictly after merge and
  archive succeed: look up the just-closed change id in any initiative
  manifest and, if found, call `advance`. A change id absent from every
  manifest leaves `close` byte-for-byte unchanged from today.

## Non-goals

- No automatic scheduling, resourcing, or concurrency control across phases.
- No automatic retry, skip, or degrade of a failed or blocked phase — a
  human sets `blocked` and a human clears it; automation never writes it.
- No dashboard or cross-initiative visualization in this change — only the
  data contract, the `register`/`advance`/`status` commands, and the
  `close` hook.
- No change to `report.py deliver`, `plan.py design`, or
  `config/collapsed.config.yaml`'s `planning_threshold_files` — an
  initiative's phase-to-phase handoff is a separate layer from a single
  change's own design/delivery measurement.
- `advance` never runs WORK, `report.py deliver`, or
  `report.py gate --request` for the queued phase — it only reaches the
  same INIT step a human would run by hand.
