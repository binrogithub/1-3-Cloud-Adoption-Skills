# spec-tooling-reuse Specification

## Purpose
TBD - created by archiving change glue-only-architecture. Update Purpose after archive.

## Requirements

### Requirement: The spec surface is the one the openspec CLI installs

Skills and commands for spec-driven work SHALL be the ones `openspec init`
installs. We SHALL NOT maintain hand-written equivalents.

#### Scenario: Installing the spec surface

- **WHEN** the repository is initialised with the claude tool target
- **THEN** the openspec skills and slash commands SHALL be present under
  `.claude/`
- **AND** hand-written `ai-dlc-spec` skills SHALL be absent from every skill
  tree
- **AND** exactly one skill tree SHALL exist, so the two copies cannot diverge

#### Scenario: A capability already provided by the CLI

- **WHEN** a proposed skill would explore, propose, apply, sync, update or
  archive a change
- **THEN** the CLI-installed skill SHALL be used instead

### Requirement: Design documents are openspec changes

A design or plan that others will act on SHALL exist as an openspec change and
SHALL pass strict validation. Any rendered form is a reading surface, not the
source of truth.

#### Scenario: Producing a design document

- **WHEN** a design is written
- **THEN** it SHALL exist under `openspec/changes/`
- **AND** `openspec validate --strict` SHALL exit zero for it
- **AND** every requirement in it SHALL carry at least one scenario stating
  observable behaviour
