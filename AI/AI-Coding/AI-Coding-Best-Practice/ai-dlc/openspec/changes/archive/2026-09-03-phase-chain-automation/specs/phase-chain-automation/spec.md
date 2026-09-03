## ADDED Requirements

### Requirement: A closed phase queues the next phase's task skeleton only

When a change registered as a phase of an initiative closes with an approved
merge, the system SHALL create the next phase's task skeleton through the
same initialization path a human uses, and SHALL NOT execute WORK, CHECK,
REPORT, or MERGE_GATE for that next phase.

#### Scenario: The next phase is pending

- **WHEN** `plan.py close` succeeds (merge and archive both succeed) for a
  change id that is a phase of an initiative
- **AND** the next phase in that initiative has status `pending`
- **THEN** a task skeleton for the next phase's change id SHALL be created
  using the same function `report.py init` uses
- **AND** the next phase's status SHALL become `queued`
- **AND** no `WORK`, `report.py deliver`, or `report.py gate --request`
  SHALL run for that phase as part of this action

#### Scenario: No next phase exists

- **WHEN** the closed phase is the last phase in its initiative
- **THEN** the initiative SHALL be marked `complete`
- **AND** no task skeleton SHALL be created

#### Scenario: The next phase is blocked

- **WHEN** the next phase's status is `blocked`
- **THEN** no task skeleton SHALL be created
- **AND** the phase SHALL remain `blocked`

### Requirement: Advancement never triggers without an approved close

The next phase SHALL NOT be queued unless the current phase's merge gate
carries an approval with a rationale and the archive step succeeded.

#### Scenario: Close has no approval

- **WHEN** `plan.py close` is invoked without a recorded approval
- **THEN** `close` SHALL take its existing early-return path
- **AND** no initiative SHALL be advanced

#### Scenario: Archive fails

- **WHEN** the upstream archive command exits non-zero during `close`
- **THEN** `close` SHALL stop and report the failure as it does today
- **AND** no initiative SHALL be advanced

### Requirement: A queued phase starts from a clean state

A task skeleton created by advancement SHALL NOT inherit planning state,
design decisions, or any other field from the phase that just closed.

#### Scenario: The prior phase recorded a design decision

- **WHEN** the closing phase's `planning.json` carries a `design_decision`
  entry
- **THEN** the newly created next phase's `planning.json` SHALL be created
  empty, with no `design_decision` or other field copied from the prior
  phase

### Requirement: A change id belongs to at most one phase of at most one initiative

Registering an initiative SHALL reject a change id that already names a
phase in any existing manifest.

#### Scenario: A change id is already registered elsewhere

- **WHEN** `plan.py initiative register` is given a change id that already
  appears as a phase in another initiative manifest, or elsewhere in the
  same manifest
- **THEN** the registration SHALL be rejected
- **AND** no file SHALL be written or modified

#### Scenario: Extending an existing initiative

- **WHEN** `plan.py initiative register` is given the same initiative id
  with a longer phase list than the stored manifest
- **THEN** only the phases beyond the currently stored length SHALL be
  appended
- **AND** phases already present SHALL NOT be rewritten

### Requirement: Advancement failure never affects the phase that already closed

A failure while queuing the next phase SHALL be reported and SHALL NOT alter
the status or task record of the phase that just closed.

#### Scenario: Task skeleton creation fails

- **WHEN** creating the next phase's task skeleton fails (for example, the
  target path cannot be created)
- **THEN** the next phase SHALL remain `pending`
- **AND** the failure SHALL be surfaced to the caller
- **AND** the phase that just closed SHALL remain `delivered`
- **AND** `plan.py close`'s own exit status and already-written merge and
  archive result SHALL be unaffected

### Requirement: A task with no initiative registration is unaffected

`plan.py close` SHALL behave identically to its pre-existing behavior for
any change id that does not appear in any initiative manifest.

#### Scenario: Closing a standalone task

- **WHEN** `plan.py close` succeeds for a change id absent from every
  initiative manifest
- **THEN** no initiative lookup SHALL change the merge, archive, or cleanup
  result already produced
- **AND** no event beyond today's existing close-related events SHALL be
  written
