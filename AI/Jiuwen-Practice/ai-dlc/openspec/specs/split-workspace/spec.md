# split-workspace Specification

## Purpose
Read a project where it lives by separating where the plane writes from where it
reads, so that no project needs to move for the plane to work on it.

## Requirements

### Requirement: The plane writes to a scratch path and reads the project in place

For a readable target, the dispatch SHALL set its working directory to a scratch
path inside the runtime's writable area, and SHALL grant the project as an
additional readable location.

#### Scenario: Dispatching against a readable project

- **WHEN** a role is dispatched for a readable target
- **THEN** the working directory SHALL be a scratch path inside the writable
  area, created for this change
- **AND** the project SHALL be granted as an additional trusted location so the
  role may read it by absolute path
- **AND** the prompt SHALL carry the project's absolute path as the place to
  read

#### Scenario: Only one location is granted

- **WHEN** a dispatch grants only the scratch path
- **THEN** the role will refuse to read the project and ask for a confirmation
  that no headless run can answer
- **AND** the dispatch SHALL therefore fail before starting, naming the missing
  grant

### Requirement: The project is not written during a read-in-place round

Nothing SHALL be written into a project read in place, its bookkeeping
directories included.

#### Scenario: After a read-in-place round

- **WHEN** a round against a readable target completes
- **THEN** the project SHALL carry no gateway bookkeeping directory
- **AND** every tracked and untracked path in the project SHALL be as it was
  before the round

#### Scenario: A write to the project is attempted

- **WHEN** the frames of a round show a write whose path lies inside the project
- **THEN** the dispatch SHALL fail, naming the path

### Requirement: The artifacts are produced in the scratch and returned deliberately

The round's own artifacts SHALL be written in the scratch, and brought into the
project only by the caller.

#### Scenario: Returning the round's work

- **WHEN** a read-in-place round completes
- **THEN** the change directory produced in the scratch SHALL be copied into the
  real project by the caller
- **AND** nothing else from the scratch SHALL be copied
- **AND** what was copied SHALL be listed in the record

#### Scenario: The round produced nothing

- **WHEN** the round ends without a change directory in the scratch
- **THEN** nothing SHALL be copied and the record SHALL say so

### Requirement: A read-in-place round states that it was not snapshotted

Reading in place means the project may change underneath the round. The record
SHALL say so.

#### Scenario: Recording a read-in-place round

- **WHEN** the round is recorded
- **THEN** the record SHALL name the project path, the scratch path, and the
  project's revision at the start if it has one
- **AND** it SHALL state that the project was read live and not snapshotted

#### Scenario: Disposing of the scratch

- **WHEN** the round is finished with the scratch
- **THEN** the scratch SHALL be removed, or its retention SHALL be recorded with
  a reason
