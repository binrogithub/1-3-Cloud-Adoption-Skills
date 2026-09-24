# external-verification Specification

## Purpose
TBD - created by archiving change glue-only-architecture. Update Purpose after archive.

## Requirements

### Requirement: Verification is performed by declared external checkers

The oracle declaration SHALL name external executables to run. The runner SHALL
start each one, read its exit code and machine-readable output, and report the
union. The runner SHALL NOT interpret the artifact itself.

#### Scenario: Declaring checkers for a web deliverable

- **WHEN** a task declares an oracle of kind `external_checkers`
- **THEN** each entry SHALL name a tool, its arguments, and the flag that makes
  it emit machine-readable output
- **AND** the runner SHALL report failure if any checker exits non-zero or
  reports findings
- **AND** the runner SHALL record each checker name, version, exit code and
  finding count in the verification record

#### Scenario: A declared checker is unavailable on the host

- **WHEN** a declared checker cannot be executed
- **THEN** the outcome SHALL be `unverified`, never `delivered`
- **AND** the run SHALL stop and ask the human

### Requirement: A checker set is accepted only after it rejects a known-bad artifact

A checker set SHALL NOT be adopted on the strength of passing a good artifact.
It SHALL first be shown to report failure on a frozen artifact known to be
broken, and the findings it produces SHALL name the specific defects.

#### Scenario: The broken-site fixture goes red

- **WHEN** the checker set runs against the fixture site whose pages contain
  only a doctype and a closing html tag, whose nav links to a missing file, and
  whose stylesheet reference does not resolve
- **THEN** the result SHALL be failure
- **AND** the findings SHALL include a stray-end-tag or missing-required-content
  error from the HTML validator
- **AND** the findings SHALL include both unresolved links from the link checker

#### Scenario: The superseded rule is recorded as passing the same fixture

- **WHEN** the same fixture is evaluated by the retired `html_document` rule
- **THEN** that rule SHALL be shown to return pass
- **AND** the comparison SHALL be recorded in the change evidence as the reason
  the rule was removed
