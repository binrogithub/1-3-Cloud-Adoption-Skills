# delivery-criteria Specification

## Purpose
State what decides whether work is delivered, now that no verification role
exists, and require the report to say plainly what was not checked.

## Requirements

### Requirement: Delivery is decided without a verification role

A task SHALL be reported as delivered only when the repository head advanced,
product files landed, the change passes strict spec validation, the cost gate is
green, and a human approved the merge gate. No other automated judgement of
correctness SHALL be consulted, because none exists upstream.

#### Scenario: All conditions hold

- **WHEN** the head advanced, product files landed, strict validation exited
  zero, the cost gate is green, and the merge gate carries an approval with a
  rationale
- **THEN** the outcome SHALL be reported as delivered
- **AND** the report SHALL state that correctness was judged by the human

#### Scenario: Strict validation fails

- **WHEN** strict validation of the change exits non-zero
- **THEN** the outcome SHALL NOT be delivered
- **AND** the validator output SHALL be carried into the report

#### Scenario: The merge gate is unanswered

- **WHEN** no approval with a rationale exists
- **THEN** the outcome SHALL be reported as merge pending
- **AND** nothing SHALL be merged

### Requirement: No correctness judgement is ever built here

Code that inspects a product artifact and returns its own pass or fail SHALL NOT
be added, whatever the pressure to add it.

#### Scenario: A correctness rule is proposed

- **WHEN** a change would add such code
- **THEN** the change SHALL be rejected
- **AND** the reviewer SHALL name an upstream capability that makes the
  judgement, or record that the property belongs to the human

#### Scenario: The advisory upstream review skill is proposed as a gate

- **WHEN** the upstream change-verification skill is proposed as a delivery
  criterion
- **THEN** it SHALL be refused, because it directs a model to infer from keyword
  search and to prefer the softer finding
- **AND** its output MAY be recorded as advice

### Requirement: The report states what was not checked

Because no machine judges correctness, every delivery report SHALL say so
plainly rather than letting silence read as verification.

#### Scenario: Reporting a delivery

- **WHEN** a delivery report is produced
- **THEN** it SHALL name spec validity, cost and the human approval as the
  criteria applied
- **AND** it SHALL state that artifact correctness was not machine-checked
