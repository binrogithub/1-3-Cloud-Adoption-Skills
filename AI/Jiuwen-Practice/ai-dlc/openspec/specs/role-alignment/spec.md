# role-alignment Specification

## Purpose
Shape the planning roles to the artifact graph openspec already defines, so role
boundaries, their order, and their prompts all come from upstream.

## Requirements

### Requirement: One role per openspec artifact

The role set SHALL be derived from the artifacts of the active schema. No role
SHALL exist that owns no artifact.

#### Scenario: Deriving the role set

- **WHEN** the role set is established for a change
- **THEN** it SHALL be read from the artifact list the schema reports
- **AND** under the spec-driven schema the roles SHALL be proposal, specs,
  design and tasks
- **AND** no verification role and no implementation role SHALL exist

#### Scenario: A role owning no artifact is proposed

- **WHEN** a role is proposed whose output is not an artifact of the schema
- **THEN** the role SHALL be rejected

### Requirement: A role prompt is built from the upstream instruction

A role prompt SHALL be assembled from what openspec reports for that artifact.
We SHALL NOT maintain a hand-written description of the artifact format.

#### Scenario: Building a prompt

- **WHEN** a role is dispatched for an artifact
- **THEN** the prompt SHALL carry the handoff package, the upstream authoring
  instruction verbatim, the reported output path, and the language context
- **AND** the template the upstream reports SHALL be included when one exists

#### Scenario: A hand-written format guide exists

- **WHEN** the authoring skill carries its own description of the artifact
  format
- **THEN** that description SHALL be removed in favour of the upstream text
- **AND** the removal SHALL be justified by the upstream instruction covering the
  same ground

### Requirement: Order and parallelism follow the artifact dependencies

Dispatch order SHALL be the dependency order openspec reports, and completion
SHALL be the completeness it reports.

#### Scenario: Ordering the roles

- **WHEN** roles are dispatched for a change
- **THEN** a role SHALL NOT start before every artifact it depends on is done
- **AND** roles whose dependencies are all satisfied MAY be dispatched together

#### Scenario: Judging the phase complete

- **WHEN** the planning phase is assessed
- **THEN** the assessment SHALL use the completeness openspec reports
- **AND** a phase openspec does not consider complete SHALL NOT be accepted

#### Scenario: An optional artifact is not warranted

- **WHEN** the upstream instruction for an artifact states conditions for
  including it and none apply
- **THEN** that role MAY be skipped
- **AND** the skip and its reason SHALL be recorded in the task record
