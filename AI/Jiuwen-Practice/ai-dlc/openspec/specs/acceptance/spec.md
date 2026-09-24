# acceptance Specification

## Purpose
Set the bar the chain must clear before it is called landed: a repository it did
not prepare, held at arm's length from anyone's live work, and an honest account
of what each role cost.

## Requirements

### Requirement: Acceptance is a repository the chain did not prepare

The acceptance run SHALL use a repository that existed before the run and was
not built for it.

#### Scenario: Running acceptance

- **WHEN** the chain is accepted
- **THEN** the target SHALL be a repository with pre-existing history and
  pre-existing uncommitted state
- **AND** the run SHALL complete the full path from package to archive
- **AND** the boundary check SHALL judge only what the run caused, not what it
  found

#### Scenario: A synthetic repository is offered as acceptance

- **WHEN** the acceptance target was created by or for the run
- **THEN** it SHALL NOT count as acceptance
- **AND** the run SHALL be recorded as a rehearsal

### Requirement: The acceptance target is a disposable copy, never a live working tree

Being unprepared is not sufficient. The target SHALL also be expendable: a copy
taken for the run from a repository that already had real history, never a tree
anyone is working in.

#### Scenario: Preparing the target

- **WHEN** an acceptance target is chosen
- **THEN** it SHALL be a local copy of a pre-existing repository, so that its
  history and its uncommitted state are genuine while the copy itself is
  expendable
- **AND** the copy SHALL be recorded together with the repository it came from

#### Scenario: A live working tree is offered

- **WHEN** a candidate target is a tree someone is working in, or holds source
  of a dependency this project may not modify
- **THEN** it SHALL be refused as a target
- **AND** the refusal SHALL name which of the two conditions applied

#### Scenario: The chain is pointed at a live tree anyway

- **WHEN** a dispatch would run against a repository holding dependency source
  this project may not modify
- **THEN** the run SHALL stop before dispatching
- **AND** the human SHALL be told which path triggered the stop

### Requirement: The run leaves the target as it found it

Bookkeeping directories are excluded from the boundary check so that a role is
not blamed for them; that exclusion SHALL NOT be read as permission to leave
them behind. A run SHALL remove what it introduced into the target, or SHALL
record why it stays.

#### Scenario: Finishing a run in a target

- **WHEN** a run completes, whether it delivered or stopped
- **THEN** every directory the run introduced that is not part of the
  deliverable SHALL be removed, or its retention SHALL be recorded with a
  reason
- **AND** the branch and worktree the run created SHALL be removed or recorded
  the same way
- **AND** the target's own pre-existing uncommitted state SHALL be untouched

#### Scenario: Cleanup would remove something the run did not create

- **WHEN** cleanup would touch a path present in the pre-run baseline
- **THEN** that path SHALL be left alone
- **AND** the skip SHALL be recorded

### Requirement: A partial view of the target is detected before planning

Roles plan against the working tree. A tree that does not show what the
repository contains SHALL be reported, so nobody discovers it afterwards.

#### Scenario: The working tree is a partial view

- **WHEN** the target's working tree holds fewer files than its head commit,
  as a sparse or partial checkout does
- **THEN** the difference SHALL be reported before the first dispatch
- **AND** the report SHALL state what the roles will and will not see
- **AND** the run MAY proceed once a human accepts the narrower view

#### Scenario: The working tree is complete

- **WHEN** the working tree matches the head commit
- **THEN** the check SHALL pass silently

### Requirement: Each role reports its own cost from its own source

The acceptance record SHALL state what each role cost, read from the upstream
records, without combining conventions.

#### Scenario: Recording the acceptance

- **WHEN** the acceptance run is recorded
- **THEN** each dispatch SHALL be listed with the upstream record it came from
- **AND** the cold figure and the cache figure SHALL be distinguished
- **AND** no total across sources SHALL be presented

### Requirement: The optional artifact is skipped when it is not warranted

The design artifact SHALL be decided before dispatch on the conditions the
upstream instruction names. The decision SHALL be recorded either way, together
with the conditions considered, the reason, not only the triggering condition,
and who decided — stated by the caller, never assumed.

A decision whose decider is unstated, or whose decider claims a human without
naming one, SHALL be refused, and no decision SHALL be recorded.

#### Scenario: The conditions do not apply

- **WHEN** none of the conditions the upstream instruction names for the design
  artifact apply to the change
- **THEN** the decision SHALL be made before dispatch
- **AND** that role SHALL be skipped
- **AND** the decision SHALL record the conditions considered, the reason, and
  who decided

#### Scenario: The conditions apply

- **WHEN** any condition applies
- **THEN** the decision SHALL be made before dispatch
- **AND** the role SHALL run
- **AND** the decision SHALL record the conditions considered, the reason, and
  who decided

#### Scenario: A decision without a stated decider is refused

- **WHEN** a decision is recorded with no decider, or with a decider that claims
  a human without naming one
- **THEN** the command SHALL refuse it and no decision SHALL be recorded
- **AND** the refusal SHALL say that who decided is stated by the caller, never
  assumed
