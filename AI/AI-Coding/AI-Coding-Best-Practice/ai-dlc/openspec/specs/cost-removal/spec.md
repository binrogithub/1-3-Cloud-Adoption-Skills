# cost-removal Specification

## Purpose
Remove the budget capability, because upstream does not provide budgeting, and
leave usage readable exactly where upstream already records it.

## Requirements

### Requirement: No budget gate exists

There SHALL be no cost gate, no cap and no budget decision file. A run SHALL NOT
be stopped, warned or annotated on the basis of a token total computed here.

#### Scenario: Auditing the gates

- **WHEN** the gate identifiers in our executables are listed
- **THEN** they SHALL be the delivery gate and the merge gate only
- **AND** no identifier naming cost or budget SHALL be present

#### Scenario: A softer replacement is proposed

- **WHEN** a change would reintroduce a stop, a warning or an advisory total
  derived from a token figure computed here
- **THEN** the change SHALL be rejected
- **AND** the reviewer SHALL record that budgeting is not provided upstream

### Requirement: Figures from different sources are never combined

Usage SHALL be read from the records upstream produces, and figures from sources
with different conventions SHALL NOT be summed.

#### Scenario: Reporting what a run cost

- **WHEN** the cost of a run is asked for
- **THEN** the answer SHALL name the upstream records that hold it and where
  they are
- **AND** it SHALL NOT present a total computed by this project

#### Scenario: Two conventions meet

- **WHEN** a gateway figure and an agent transcript figure would be combined
- **THEN** they SHALL NOT be combined, because one convention already includes
  the cache figure in its input figure and the other does not
- **AND** each source SHALL be reported on its own terms

### Requirement: The handoff package carries no budget

The package SHALL carry the requirement, the change id, the capability and the
repository, and nothing about cost.

#### Scenario: Composing a package

- **WHEN** a requirement is routed to the planning plane
- **THEN** a package carrying a budget key SHALL be rejected, naming the key
- **AND** no budget line SHALL appear in the assembled role prompt

#### Scenario: The shape rule still fires

- **WHEN** a package states a file count, a module count or a directory layout
- **THEN** it SHALL be rejected before dispatch, naming the offending phrase

### Requirement: Delivery depends on validity, landing and a human

A task SHALL be reported as delivered only when the head advanced, product files
landed, the change passes strict validation, and a human approved the merge
gate. No cost term SHALL take part.

#### Scenario: All conditions hold

- **WHEN** the head advanced, product files landed, strict validation exited
  zero, and the merge gate carries an approval with a rationale
- **THEN** the outcome SHALL be reported as delivered
- **AND** no cost verdict SHALL appear in the report
- **AND** the report SHALL still state that artifact correctness was not
  machine-checked
