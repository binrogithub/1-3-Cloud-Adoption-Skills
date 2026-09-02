# reviewer-roles Specification

## Purpose
Define the reviewers so their outputs do not converge, and choose which of them
run for a given change.

## Requirements

### Requirement: Reviewer axes are named in advance and chosen per change

The available axes SHALL be a fixed, named list. The axes that run for a change
SHALL be chosen from it and recorded with the reason.

#### Scenario: Choosing axes

- **WHEN** the review round is prepared
- **THEN** the axes SHALL be chosen from the named list, at most the configured
  maximum
- **AND** the choice and the reason for each chosen axis SHALL be recorded
- **AND** the axes considered and not chosen SHALL be recorded too

#### Scenario: An axis outside the list is proposed

- **WHEN** an axis not on the named list is proposed for a round
- **THEN** it SHALL be refused
- **AND** adding it SHALL require amending the list first

### Requirement: Reviewer personas are mutually antagonistic

Each reviewer SHALL carry a stance that pulls against the others, so that
findings do not converge on the same trivial observations.

#### Scenario: Defining a reviewer

- **WHEN** a reviewer is defined for an axis
- **THEN** its persona SHALL state what it is suspicious of, what it considers
  an acceptable trade, and what it will not accept
- **AND** two reviewers SHALL NOT share a stance

#### Scenario: Findings converge

- **WHEN** the findings of a round restate the same concern
- **THEN** the round SHALL be recorded as convergent
- **AND** the personas SHALL be revised before the axes are used again

### Requirement: Reviewers are dispatched like every other role

A reviewer SHALL run through the same dispatch as an artifact role, with the
same isolation and the same judging.

#### Scenario: Dispatching a reviewer

- **WHEN** a reviewer is dispatched
- **THEN** it SHALL have its own named session, its own frame file and its own
  boundary baseline
- **AND** the run SHALL be judged from the frames, never from the final envelope
- **AND** reviewers whose dependencies are satisfied MAY be dispatched together

#### Scenario: Team mode is proposed for the round

- **WHEN** a change would run the round through team mode
- **THEN** it SHALL be rejected, and the reason recorded: an ad-hoc team cannot
  be given the named reviewers, its progress is invisible until it ends, and it
  takes an order of magnitude longer than the dispatch already in use
