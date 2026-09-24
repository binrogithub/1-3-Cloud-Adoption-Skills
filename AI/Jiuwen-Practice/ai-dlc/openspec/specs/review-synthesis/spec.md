# review-synthesis Specification

## Purpose
Place a synthesis between the findings and the revision, so that relationships
the equal reviewers cannot see are stated once, by the party that holds them
all, without becoming another opinion.

## Requirements

### Requirement: The synthesis is produced by the caller, not by a dispatch

The synthesis SHALL be produced by the party orchestrating the round from the
material it already holds. No role SHALL be dispatched to produce it.

#### Scenario: Producing the synthesis

- **WHEN** every reviewer of a round has returned and the round passed its
  contract checks
- **THEN** the caller SHALL produce the synthesis before the author is
  dispatched to revise
- **AND** no session SHALL be opened for it

#### Scenario: A synthesis role is proposed

- **WHEN** a change would dispatch a role to synthesise, or introduce a leader
  role for the round
- **THEN** it SHALL be rejected, and the reason recorded: the caller already
  holds the design and every finding, and the round's reviewers are equal by
  construction

### Requirement: The synthesis surfaces relationships and nothing else

The synthesis SHALL state where findings land and how they relate. It SHALL NOT
decide between them, rank them by importance, or edit the design.

#### Scenario: Composing the synthesis

- **WHEN** the synthesis is composed
- **THEN** it SHALL group the findings by the part of the design each addresses
- **AND** it SHALL name every pair whose proposed changes pull against each
  other, stating what one increases that the other would reduce
- **AND** it SHALL order the groups by where they land in the design

#### Scenario: The synthesis takes a side

- **WHEN** the synthesis recommends which of two opposing findings to follow, or
  marks a finding as more important than another
- **THEN** the round SHALL fail the contract, naming the passage

#### Scenario: No findings pull against each other

- **WHEN** no pair of findings opposes another
- **THEN** the synthesis SHALL say so explicitly
- **AND** silence SHALL NOT stand in for that statement

### Requirement: Every concern in the synthesis maps to a finding

The synthesis SHALL introduce nothing of its own. Each concern it names SHALL be
traceable to a finding that a reviewer filed.

#### Scenario: Checking the synthesis

- **WHEN** the synthesis is checked
- **THEN** each concern it names SHALL cite the finding it came from
- **AND** a concern citing no finding SHALL fail the contract, naming it

#### Scenario: A finding is omitted

- **WHEN** a finding filed by a reviewer appears in no group of the synthesis
- **THEN** the contract SHALL fail, naming the omitted finding

### Requirement: The author answers the findings, not the synthesis

The revision contract SHALL remain unchanged: the author SHALL answer each
finding a reviewer filed. The synthesis SHALL accompany those findings as a
reading aid and SHALL NOT become the thing answered.

#### Scenario: Dispatching the revision

- **WHEN** the author is dispatched to revise
- **THEN** the prompt SHALL carry every original finding in full, and the
  synthesis alongside them
- **AND** the prompt SHALL state that the answers are owed to the findings

#### Scenario: The revision answers only the synthesis

- **WHEN** the revision answers the synthesis without answering each finding
- **THEN** the phase SHALL NOT be reported complete, naming the unanswered
  findings

### Requirement: The synthesis is recorded with the round

The synthesis SHALL survive with the round's evidence and travel into the
report as advice.

#### Scenario: Recording the round

- **WHEN** the round is recorded
- **THEN** the synthesis SHALL be stored with the findings and the answers
- **AND** the delivery report SHALL carry it as advice, taking no part in the
  delivery decision
