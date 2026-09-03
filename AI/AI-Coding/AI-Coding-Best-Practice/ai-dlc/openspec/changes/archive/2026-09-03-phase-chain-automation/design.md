# Design — Phase-chain automation

## Data contract

`.ai-dlc/initiatives/<initiative-id>.json`:

```json
{
  "initiative_id": "openjiuwen-efficiency-v1",
  "title": "openjiuwen agent-core efficiency optimization",
  "created_by": "robin",
  "created_at": "2026-09-03T12:00:00Z",
  "phases": [
    {"seq": 1, "change_id": "openjiuwen-efficiency-v1-phase1", "status": "delivered"},
    {"seq": 2, "change_id": "openjiuwen-efficiency-v1-phase2", "status": "queued"},
    {"seq": 3, "change_id": "openjiuwen-efficiency-v1-phase3", "status": "pending"}
  ]
}
```

`status` has exactly four values:

- `pending` — not yet created.
- `queued` — `report.py init` has run for this phase; a person owns WORK
  next.
- `delivered` — this phase's `plan.py close` succeeded.
- `blocked` — a human paused the initiative here. Automation never writes
  this value and never advances past it; only a human sets or clears it.

A change id may appear in exactly one phase of exactly one manifest.
`register` rejects a change id that already names a phase elsewhere.

## Command surface

`plan.py initiative register --initiative <id> --repo <repo> --phases <c1>[,<c2>...]`
writes the manifest. Phase order is argument order. Re-registering the same
initiative id with a longer phase list appends only the new tail; it never
rewrites a phase already present.

`plan.py initiative advance --change <closed-change-id> --repo <repo>` is the
one function with a side effect beyond writing JSON:

1. Find the manifest owning `<closed-change-id>`. Not found → no-op, exit 0
   (this is what makes every non-initiative task unaffected).
2. Mark that phase `delivered`.
3. If the next `seq` exists and its status is `pending`: call the same
   internal function `report.py init` calls (not a re-implementation) with
   that phase's `change_id` and the caller-supplied `--repo`; on success mark
   it `queued` and emit `INITIATIVE_PHASE_QUEUED`. On failure, leave it
   `pending`, do not touch the just-marked-`delivered` phase, and surface the
   failure to the caller of `advance` (the `close` hook logs and continues —
   it does not fail `close` itself, since merge and archive already
   succeeded by this point).
4. If the next phase is `blocked` or does not exist: if it does not exist,
   mark the initiative `complete` and emit `INITIATIVE_COMPLETE`; if
   `blocked`, do nothing further (already paused).

`plan.py initiative status --initiative <id> --repo <repo>` reads and prints
the manifest. No writes.

## The `close` hook

`plan.py close` today ends with: merge task branch → archive change upstream
→ remove worktree and task branch → report closed. This change appends one
more step, after archive succeeds and before `close` returns:

```
manifest = find_manifest_for_change(change_id, repo)
if manifest is not None:
    initiative_advance(change_id, repo)   # same function `plan.py initiative advance` calls
```

`find_manifest_for_change` is a plain filesystem scan of
`.ai-dlc/initiatives/*.json` for a phase whose `change_id` matches. No new
long-lived process, no daemon, no polling — the check runs exactly once, at
the moment `close` already has the change id in hand.

If `close` was invoked without an approval (today's existing early return) or
archive exits non-zero (today's existing stop-and-report path), this new step
never runs, because `close` never reaches its tail in either case — the
existing control flow is the guard, not a new conditional this change adds.

## Isolation from the design (D0-D3) and delivery flow

`report.py deliver`'s design auto-dispatch keys off the surface files of the
change being measured — it has no awareness of initiatives and this change
does not touch it. A queued phase created by `advance` goes through the
identical `report.py init` path a manually created task does, so it is
measured, routed, and (if it carries a web/deck surface) design-dispatched
exactly as any hand-created task would be. Nothing about being "phase 2 of an
initiative" changes how that phase's own change is later delivered.
