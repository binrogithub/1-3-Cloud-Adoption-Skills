## ADDED Requirements

### Requirement: A successful close advances the owning initiative

When `plan.py close` succeeds (merge and archive both succeed) for a change
id that is a phase of a registered initiative, the system SHALL call the
existing initiative-advance behavior for that change id.

#### Scenario: Closed change is a registered phase

- **WHEN** `plan.py close` succeeds for a change id present in some
  `.ai-dlc/initiatives/*.json` manifest
- **THEN** the same effects `plan.py initiative advance --change <id>`
  produces SHALL occur as part of `close`
- **AND** no second, independent implementation of advancement SHALL be
  introduced

#### Scenario: Closed change is not registered

- **WHEN** `plan.py close` succeeds for a change id absent from every
  initiative manifest
- **THEN** `close`'s behavior, output, and side effects SHALL be identical
  to its behavior before this change

### Requirement: The hook never fires on an unsuccessful close

- **WHEN** `plan.py close` takes its existing early-return path (no
  approval recorded)
- **THEN** no initiative lookup or advancement SHALL occur

#### Scenario: Archive fails

- **WHEN** the upstream archive command exits non-zero during `close`
- **THEN** no initiative lookup or advancement SHALL occur
- **AND** `close`'s existing failure reporting SHALL be unchanged

### Requirement: Advancement failure does not affect the closed phase's record

- **WHEN** the advancement step fails after a successful merge and archive
- **THEN** the failure SHALL be reported
- **AND** the phase that just closed SHALL remain recorded as delivered
- **AND** `close`'s own exit status and already-written merge/archive
  result SHALL be unaffected
