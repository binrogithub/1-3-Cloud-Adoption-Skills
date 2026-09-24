# glue-boundary Specification

## Purpose
TBD - created by archiving change glue-only-architecture. Update Purpose after archive.

## Requirements

### Requirement: Our code contains no acceptance logic

Every module we own SHALL limit itself to starting processes, passing paths,
reading exit codes and machine-readable output, and tallying results. No module
we own SHALL decide whether a produced artifact is correct.

#### Scenario: A hand-written correctness rule is proposed

- **WHEN** a change would add code that inspects a product artifact and returns
  a pass or fail judgment of its own
- **THEN** the change SHALL be rejected
- **AND** the reviewer SHALL name an existing external tool that makes that
  judgment, or record that the property is not machine-checkable and belongs to
  the human

#### Scenario: An existing hand-written rule is audited

- **WHEN** `bin/oracle.py` is audited for judgment logic
- **THEN** `run_property` and the `PROPERTY_RULES` tuple SHALL be absent
- **AND** the only surviving evaluation paths SHALL delegate to an external
  process

### Requirement: Dead and duplicated modules are removed

Modules with no code callers, and modules whose capability an installed
dependency already provides, SHALL NOT remain in the active surface.

#### Scenario: Auditing for callers

- **WHEN** `grep -rn "openspec_gateway" --include=*.py` runs over the active
  surface
- **THEN** the result SHALL be empty
- **AND** `executor/openspec_gateway.py` SHALL be absent from the tree

#### Scenario: Auditing for dead wiring

- **WHEN** a grep for `runtime_bridge` or `jiuwenswarm` runs over the active
  surface, excluding `evidence/` and `CHANGELOG.md`
- **THEN** the result SHALL contain no instruction to execute either
