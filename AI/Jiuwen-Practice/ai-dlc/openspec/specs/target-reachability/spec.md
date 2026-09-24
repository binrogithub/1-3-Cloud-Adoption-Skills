# target-reachability Specification

## Purpose
Classify what the plane can do with a target before anything is dispatched, in
three classes rather than two, so that a project which can be read is read
rather than copied.

## Requirements

### Requirement: The target is classified into three before dispatch

Every run SHALL determine, before the first dispatch, whether the plane can
write the target, can only read it, or cannot see it. The classification and how
it was reached SHALL be recorded.

#### Scenario: The target is writable by the plane

- **WHEN** the plane can both read and write the target
- **THEN** the plane SHALL be dispatched against the target itself
- **AND** neither a scratch workspace nor a copy SHALL be made

#### Scenario: The target is readable but not writable

- **WHEN** the plane can read the target but cannot write it
- **THEN** the run SHALL read the project in place through a split workspace
- **AND** no copy of the project SHALL be made

#### Scenario: The target is not visible to the plane

- **WHEN** the plane cannot read the target at all
- **THEN** the run SHALL stage a copy, and the record SHALL state that copying
  was the only option because nothing at the source was readable

### Requirement: Copying is the exception, and choosing it requires the invisible class

A run SHALL NOT copy a project it could read in place.

#### Scenario: A copy is proposed for a readable target

- **WHEN** a run would stage a target classified readable
- **THEN** it SHALL be refused, naming the split workspace as the mechanism
- **AND** the refusal SHALL record the size the copy would have cost

#### Scenario: Recording the cost of a copy that was necessary

- **WHEN** an invisible target is copied
- **THEN** the record SHALL carry the copy's duration and size

### Requirement: Widening the service sandbox is not the remedy

A target SHALL NOT be made reachable by granting the service write access to it.

#### Scenario: A change would widen the sandbox for a target

- **WHEN** a change would add a project path to the service unit's writable
  paths
- **THEN** it SHALL be rejected, naming the split workspace as the remedy
- **AND** the rejection SHALL record that the sandbox is the only boundary left
  once the permission engine is off, and that widening returns the gateway's
  bookkeeping to somebody's tree

#### Scenario: An existing widening is found

- **WHEN** the service unit names a writable path that is a project tree rather
  than the runtime's own area
- **THEN** it SHALL be reported as a finding, naming the path

### Requirement: Reachability is established by probing, not by matching a path

The classification SHALL rest on what the plane can actually do.

#### Scenario: Determining what the plane can do

- **WHEN** reachability is determined
- **THEN** it SHALL be established by what the service's configuration grants
  and by a probe that confirms it, not by matching the path against a list of
  known prefixes
- **AND** a target that probes unreadable SHALL be treated as invisible whatever
  its path suggests
