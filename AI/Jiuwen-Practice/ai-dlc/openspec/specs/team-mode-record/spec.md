# team-mode-record Specification

## Purpose
Record what was measured about team mode, so the question is not reopened from
the same starting point and re-answered by the same experiments.

## Requirements

### Requirement: The team-mode findings are recorded as settled

What was measured about team mode SHALL be recorded where a reader proposing it
will find it, with the evidence that settled each point.

#### Scenario: Recording the findings

- **WHEN** the record is written
- **THEN** it SHALL state that a team is structurally a leader with teammates:
  the runtime accepts only those two roles and demotes anything else, the loader
  creates a leader when none is given, and adds a teammate when only a leader
  exists — so there is no peer model
- **AND** it SHALL state that a configured roster for the wildcard team is not
  read on the command-line path, evidenced by a run where the roster names
  appeared nowhere and the leader named its own workers from its own plan
- **AND** it SHALL state the measured duration of a completed team round beside
  that of the equal-reviewer round
- **AND** it SHALL state that the leader is not idle when it appears to be: it
  dispatches and then blocks awaiting a completion notification

#### Scenario: Team mode is proposed again

- **WHEN** a change proposes team mode for a round
- **THEN** it SHALL be refused with reference to this record
- **AND** refusing SHALL require no new experiment unless the proposal names a
  fact the record does not cover

### Requirement: Inert configuration is removed or marked

Configuration that no path reads SHALL NOT be left looking effective.

#### Scenario: A configured roster proves inert

- **WHEN** a configuration entry is shown to be read by no path this project
  uses
- **THEN** it SHALL be removed, or annotated in place with what reads it and
  what does not
- **AND** the backup taken before it was added SHALL be named in the record
