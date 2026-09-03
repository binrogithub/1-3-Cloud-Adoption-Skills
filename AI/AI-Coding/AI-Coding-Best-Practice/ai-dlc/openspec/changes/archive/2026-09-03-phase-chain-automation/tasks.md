# Tasks — Phase-chain automation

## 1. Data contract

- Define the `.ai-dlc/initiatives/<initiative-id>.json` schema (see
  `design.md`): `initiative_id`, `title`, `created_by`, `created_at`,
  `phases[]` with `seq`, `change_id`, `status`.
- Enforce at write time: a `change_id` may appear in at most one phase of at
  most one manifest across `.ai-dlc/initiatives/`.

## 2. `plan.py initiative register`

- `--initiative <id> --repo <repo> --phases <c1>[,<c2>...]`.
- Create the manifest if absent; if present, append only phases beyond the
  current length (never rewrite an existing phase entry).
- Reject (non-zero exit, no partial write) if any listed change id already
  names a phase in this or another manifest.

## 3. `plan.py initiative advance`

- `--change <closed-change-id> --repo <repo>`.
- Look up the owning manifest; no match is a no-op (exit 0).
- Mark the matched phase `delivered`.
- If the next `seq` is `pending`: call the same initialization function
  `report.py init` uses (import and reuse — do not fork a second
  implementation) to create that phase's task skeleton; mark it `queued` on
  success; on failure leave it `pending`, report the failure, and do not
  alter the phase already marked `delivered`.
- If the next `seq` is `blocked`: leave it untouched.
- If there is no next `seq`: mark the initiative `complete`.
- Append `INITIATIVE_PHASE_QUEUED` or `INITIATIVE_COMPLETE` to the repo's
  `events.jsonl` (same file and format existing task events already use).

## 4. `plan.py initiative status`

- `--initiative <id> --repo <repo>`. Read-only; prints the manifest's
  phases and statuses. No writes, no side effects.

## 5. `close` tail hook

- After `plan.py close`'s existing merge + archive succeed (and only then —
  the existing no-approval and archive-failure early-return paths are
  unchanged and this step is unreachable from either), scan
  `.ai-dlc/initiatives/*.json` for a phase matching the closed change id.
- If found, call the same function `plan.py initiative advance` calls. A
  failure in this step is logged and does not change `close`'s own exit
  status or its already-written merge/archive result.
- If not found, `close` behaves exactly as it does today — this is the
  regression case to test explicitly (INV-6 in the PRD).

## 6. Tests

- Round-trip `register` → `status` shows the phases in order, all
  `pending`.
- `advance` on a change id absent from every manifest is a no-op (exit 0,
  no file written).
- `advance` on a phase whose next phase is `pending` creates the next
  phase's task skeleton via the same code path as manual `report.py init`,
  and that skeleton's `planning.json` is empty/default — not copied from
  the phase that just delivered.
- `advance` on the last phase marks the initiative `complete` and does not
  attempt to create a further phase.
- `advance` on a phase whose next phase is `blocked` leaves it `blocked`.
- `register` rejects a change id already registered elsewhere; no partial
  write occurs.
- A `close` run for a change id in no manifest produces byte-identical
  before/after task-record state to `close` today (the compatibility
  regression named in the PRD's §05).
- A `close` run that stops early (no approval, or archive exits non-zero)
  never reaches the new hook — assert the hook function is not called.

## 7. CHECK → REPORT → MERGE_GATE

- `plan.py validate` for the signed verdict on this proposal + spec.
- `report.py deliver` for the delivery report (this change lands only
  planning artifacts: PRD, proposal, design, tasks, spec — no
  implementation in this pass, per the phasing in the PRD §08).
- Present the diff and validator conclusion at MERGE_GATE for the human.
