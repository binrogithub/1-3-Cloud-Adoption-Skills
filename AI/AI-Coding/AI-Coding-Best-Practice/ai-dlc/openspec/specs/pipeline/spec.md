# pipeline Specification

## Purpose
Fix the path a requirement travels from a person to a merged change, and the
division of labour along it.

## Requirements

### Requirement: Claude Code composes an explicit handoff package

The handoff SHALL be an explicit package. A role SHALL NOT infer the task from
ambient state.

#### Scenario: Composing the package

- **WHEN** a requirement is routed to the planning plane
- **THEN** the package SHALL carry the requirement text, the change id, the
  capability path, the repository path, and the planning budget
- **AND** the package SHALL state behaviour only
- **AND** a package naming a file count, a module count, or a directory layout
  SHALL be rejected before dispatch

#### Scenario: Planning exceeds its budget

- **WHEN** planning passes the budget named in the package
- **THEN** the run SHALL stop and present whatever artifacts exist
- **AND** extending, narrowing, or planning inline SHALL be the human choice

### Requirement: Dispatch goes through the shipped gateway client

The planning plane SHALL be reached by running the client the gateway ships and
reading its line-delimited event stream. A hand-built socket client SHALL NOT be
used.

#### Scenario: Dispatching a role

- **WHEN** a role is dispatched
- **THEN** the invocation SHALL use the shipped client with the event stream
  enabled and the repository as the working directory
- **AND** the outcome SHALL be judged from the event frames, never from the
  final envelope alone

#### Scenario: A blocked run reports success

- **WHEN** the frames carry an interrupt and no responder exists
- **THEN** the dispatch SHALL exit non-zero naming the tool and the argument
- **AND** the envelope claiming success SHALL be disregarded

### Requirement: A role writes one artifact through the authoring skill

A role SHALL invoke the authoring skill and write exactly the artifact it owns,
at the path openspec reports. It SHALL NOT validate its own output, because the
acceptor must be the judge.

#### Scenario: Authoring an artifact

- **WHEN** a role receives its dispatch
- **THEN** it SHALL write only its own artifact at the reported path
- **AND** it SHALL NOT invoke the validator
- **AND** it SHALL NOT write any product file

#### Scenario: The plane writes outside its artifact

- **WHEN** the product surface diff is non-empty at the end of planning,
  excluding the gateway bookkeeping directories
- **THEN** the task SHALL abort with a non-zero exit naming the offending paths

### Requirement: Claude Code validates, then implements

Acceptance and implementation both belong to Claude Code. Rejection SHALL carry
the validator text.

#### Scenario: Accepting a plan

- **WHEN** the planning plane reports completion
- **THEN** Claude Code SHALL run strict validation
- **AND** only an exit of zero SHALL accept the plan
- **AND** on acceptance Claude Code SHALL write the product files itself, in the
  task worktree

#### Scenario: Rejecting a plan

- **WHEN** strict validation exits non-zero
- **THEN** the validator output SHALL be returned verbatim to the role that owns
  the failing artifact
- **AND** the failed attempt SHALL be billed against the planning budget
- **AND** a revision that changes requirement or scenario counts unbidden SHALL
  be rejected again

### Requirement: The human sees four states and holds the merge gate

The surface presented to a person SHALL be four states, and approval SHALL
carry a rationale and an approver stated by the caller, never assumed.

#### Scenario: Reporting progress

- **WHEN** the state of a task is presented
- **THEN** it SHALL be one of working, checking, ready, or needs your decision
- **AND** planning internals, token accounting and role transcripts SHALL NOT be
  shown unless asked

#### Scenario: Approving a merge

- **WHEN** the merge gate is answered
- **THEN** an approval SHALL carry a rationale and an approver stated by the
  caller
- **AND** an answer whose approver is unstated, or whose approver claims a human
  without naming one, SHALL be refused before anything is written
- **AND** only after approval SHALL the branch merge and the change be archived

#### Scenario: Requesting the gate's answer

- **WHEN** the merge gate's answer is requested
- **THEN** the request SHALL carry no approver
- **AND** the request SHALL NOT be refused for lacking one
