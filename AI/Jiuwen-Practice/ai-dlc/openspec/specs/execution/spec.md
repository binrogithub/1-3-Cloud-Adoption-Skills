# execution Specification

## Purpose
Checks the execution skill's routing table against the measured change, records
the duration of every dispatch, reports the planning phase's timing, and
dispatches independent roles in parallel.

## Requirements

### Requirement: The recorded route is checked against the measured change

The routing table SHALL be checked against the measured change when a task
starts. An inline route that carries a change the table sends to the planning
plane SHALL stop the task for a person, naming the count of such inline routes,
the threshold allowed, and the route.

A recorded exception SHALL carry a reason and an author, both stated by the
caller. The author SHALL never be assumed: the command SHALL refuse an
exception whose author is unstated or claims a human without naming one, and a
refused exception SHALL write nothing.

#### Scenario: An inline route carries a change the table sends to the planning plane

- **WHEN** a task starts with an inline route that carries a change the routing
  table sends to the planning plane
- **THEN** the task SHALL stop before dispatch
- **AND** the stop SHALL name the count of such inline routes, the threshold
  allowed, and the route
- **AND** the person SHALL be offered the option to re-run the change through
  the planning plane
- **AND** the person SHALL be offered the option to record an explicit exception
  with a reason

#### Scenario: No inline route carries a change the table sends to the plane

- **WHEN** a task starts and no inline route carries a change the table sends
  to the planning plane
- **THEN** the task SHALL proceed

#### Scenario: An explicit exception is recorded for the inline route

- **WHEN** the person records an explicit exception with a reason and a stated
  author for the inline route
- **THEN** the exception, its reason and its author SHALL be recorded in the
  task record
- **AND** the task SHALL proceed

#### Scenario: An exception without a stated author is refused

- **WHEN** an exception is recorded with no author, or with an author that
  claims a human without naming one
- **THEN** the command SHALL refuse it before anything is written
- **AND** the refusal SHALL say that the author is stated by the caller, never
  assumed

### Requirement: Every dispatch records its start, end and elapsed seconds

Each dispatch SHALL record its start time, end time, and elapsed seconds beside
its outcome, whether the dispatch succeeded or failed.

#### Scenario: A dispatch completes successfully

- **WHEN** a dispatch completes successfully
- **THEN** the dispatch record SHALL include its start time, end time, and
  elapsed seconds beside its outcome

#### Scenario: A dispatch fails

- **WHEN** a dispatch fails
- **THEN** the dispatch record SHALL include its start time, end time, and
  elapsed seconds beside its outcome

### Requirement: The planning phase reports role durations and the wall-clock span

The planning phase SHALL report each role's duration, the sum of the role
durations, and the wall-clock span of the planning phase.

#### Scenario: The planning phase completes

- **WHEN** the planning phase completes
- **THEN** the report SHALL state each role's duration
- **AND** the report SHALL state the sum of the role durations
- **AND** the report SHALL state the wall-clock span of the planning phase

### Requirement: Independent roles dispatch together with isolated sessions

Roles that depend only on the proposal SHALL be dispatched together. Each role
SHALL keep its own session, frame file, and boundary baseline. When one role
fails, no new dispatches SHALL start, but running roles SHALL finish and every
outcome SHALL be reported.

#### Scenario: Independent roles are dispatched together

- **WHEN** two or more roles depend only on the proposal
- **THEN** they SHALL be dispatched together
- **AND** each role SHALL keep its own session, frame file, and boundary baseline

#### Scenario: One role fails while others are still running

- **WHEN** a role fails while other independent roles are still running
- **THEN** no new dispatches SHALL start
- **AND** the running roles SHALL be allowed to finish
- **AND** every outcome SHALL be reported
