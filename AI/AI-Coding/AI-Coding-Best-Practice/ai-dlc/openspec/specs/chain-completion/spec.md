# chain-completion Specification

## Purpose
Wire the parts of the chain that the specification names but no code performs:
the tail after approval, resuming a stopped role, and a health check that
describes the runtime that exists.

## Requirements

### Requirement: The tail runs after approval and only after approval

Merging and archiving SHALL follow a recorded approval. Neither SHALL happen on
its own.

#### Scenario: Approval is recorded

- **WHEN** the merge gate carries an approval with a rationale
- **THEN** the worktree branch SHALL merge into the target branch
- **AND** the change SHALL be archived through the upstream archive command
- **AND** the task record SHALL close, showing the state that follows delivery

#### Scenario: Approval is absent

- **WHEN** no approval with a rationale exists
- **THEN** neither the merge nor the archive SHALL run
- **AND** the task SHALL report that it is waiting on a person

#### Scenario: The archive command fails

- **WHEN** the upstream archive command exits non-zero
- **THEN** its output SHALL be carried into the report
- **AND** the task SHALL stop rather than reporting a clean close

### Requirement: A stopped role resumes instead of restarting

Work already paid for SHALL NOT be paid for again. A dispatch that was
interrupted SHALL be resumable.

#### Scenario: Resuming after an interruption

- **WHEN** a role dispatch was stopped and its artifact was not written
- **THEN** the resume SHALL reuse that role's session rather than opening a new
  one
- **AND** roles whose artifacts are already done SHALL NOT be dispatched again

#### Scenario: An artifact is already written

- **WHEN** planning is re-entered and an artifact is already reported done
- **THEN** its role SHALL be skipped
- **AND** the skip SHALL be recorded

### Requirement: The health check describes the runtime that exists

The check SHALL exercise the planning dispatch and SHALL NOT test capabilities
that were removed.

#### Scenario: Running the check

- **WHEN** the health check runs
- **THEN** it SHALL verify the executables that exist, the openspec CLI, and
  that the planning dispatch can reach the gateway
- **AND** it SHALL verify that strict validation discriminates, by accepting a
  valid change and rejecting a scenario-less requirement
- **AND** it SHALL NOT reference a cost or budget gate

#### Scenario: The gateway is unreachable

- **WHEN** the gateway cannot be reached
- **THEN** the check SHALL fail and name the reachability setting that is absent

### Requirement: Stale task records are closed or removed

A task record SHALL NOT sit indefinitely in a state that no longer exists.

#### Scenario: A record names a removed stage

- **WHEN** a task record carries a stage or state belonging to a removed
  capability
- **THEN** it SHALL be closed or removed
- **AND** the disposition SHALL be recorded
