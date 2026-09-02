# legacy-removal Specification

## Purpose
Remove the surface left by the retired delegated design, so that no instruction
in the tree points at a plane that no longer exists.

## Requirements

### Requirement: No instruction points at the retired worker plane

Skills, routing tables and configuration SHALL NOT direct work to the delegated
worker path. The path stays retired behind its rollback tag.

#### Scenario: Auditing the skills

- **WHEN** the skills we own are read
- **THEN** none SHALL describe dispatching product work to a delegated worker
- **AND** the routing row for a task too large to do inline SHALL send it to the
  planning plane instead

#### Scenario: Auditing the configuration

- **WHEN** our configuration is read
- **THEN** it SHALL NOT carry a switch for the delegated worker plane
- **AND** every key present SHALL correspond to behaviour that exists

### Requirement: The route vocabulary names only planes that exist

A recorded route SHALL be one of the planes this design defines.

#### Scenario: Recording a route

- **WHEN** a task records its route
- **THEN** the value SHALL be inline or planned
- **AND** a value naming a retired plane SHALL be rejected

#### Scenario: A stale route value is encountered

- **WHEN** a task record carries a route value that names no existing plane
- **THEN** the run SHALL stop and ask the human rather than guessing an
  equivalent

### Requirement: One change is the source of truth

Superseded design documents SHALL NOT remain alongside the current one.

#### Scenario: Superseded changes exist

- **WHEN** more than one unarchived change describes the same architecture
- **THEN** all but the current one SHALL be removed
- **AND** the removal SHALL be recorded in the surviving proposal
