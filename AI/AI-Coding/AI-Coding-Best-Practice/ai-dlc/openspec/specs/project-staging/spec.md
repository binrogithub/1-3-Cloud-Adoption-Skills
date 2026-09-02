# project-staging Specification

## Purpose
Cover the one class that cannot be read in place: a target the plane cannot see
at all. Copying applies here and nowhere else.

## Requirements

### Requirement: A copy is made only for a target the plane cannot see

Staging SHALL be reserved for the invisible class. Its use SHALL record why
reading in place was impossible.

#### Scenario: Staging an invisible target

- **WHEN** a target the plane cannot read is prepared
- **THEN** a copy SHALL be made inside the runtime's writable area
- **AND** the record SHALL state that nothing at the source was readable

#### Scenario: The target became readable

- **WHEN** a target previously classified invisible now probes readable
- **THEN** the run SHALL read it in place rather than reuse an earlier copy

### Requirement: The copy is self-contained

The copy SHALL NOT depend on any path the plane cannot reach.

#### Scenario: Copying a repository

- **WHEN** a project under version control is copied
- **THEN** the copy SHALL carry its own history store rather than point back at
  the original
- **AND** it SHALL carry the working tree the round needs to read

#### Scenario: The copy is not self-contained

- **WHEN** a copy references a path outside the reachable area for its history
  or its content
- **THEN** the run SHALL stop before dispatch, naming the reference

### Requirement: A copied round states what it saw and when

The copy is a point in time, and the record SHALL say so.

#### Scenario: Recording a copied round

- **WHEN** a copied round is recorded
- **THEN** the record SHALL carry the source path, the copy path, the time the
  copy was taken, the source revision if it has one, and the copy's size and
  duration
- **AND** it SHALL state that work done in the source afterwards was not seen

#### Scenario: Returning from a copied round

- **WHEN** a copied round completes
- **THEN** only the change directory SHALL be brought into the real project
- **AND** the copy SHALL be removed, or its retention recorded with a reason
