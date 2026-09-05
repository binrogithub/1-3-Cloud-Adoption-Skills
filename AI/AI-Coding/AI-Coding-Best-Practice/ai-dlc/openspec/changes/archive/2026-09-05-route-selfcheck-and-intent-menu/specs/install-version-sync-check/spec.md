## ADDED Requirements

### Requirement: `install.sh --check-sync` reports version drift without acting on it

`install.sh --check-sync` SHALL compare the repo's own `VERSION` file
against each installed target's `VERSION` file and report any mismatch,
without modifying any target.

#### Scenario: A target's version matches the repo's

- **WHEN** an installed target listed in `targets/*.json` has a `VERSION`
  file identical to the repo's own
- **THEN** no mismatch line SHALL be produced for that target

#### Scenario: A target's version differs

- **WHEN** an installed target's `VERSION` file differs from the repo's own
- **THEN** `--doctor` output SHALL include one line naming the target path
  and both version strings

#### Scenario: A target's `VERSION` file is missing

- **WHEN** an installed target has no `VERSION` file
- **THEN** it SHALL be reported as a mismatch, not treated as a crash or
  skipped silently

#### Scenario: A registered target no longer exists on disk

- **WHEN** a target path listed in `targets/*.json` does not exist locally
- **THEN** `--check-sync` SHALL skip it without error and without requiring
  the registration to be cleaned up first

### Requirement: The sync check never modifies a target or changes doctor's exit code

- **WHEN** `--check-sync` runs, regardless of how many mismatches are found
- **THEN** no installed target's files SHALL be created, modified, or
  deleted
- **AND** `--doctor`'s exit code SHALL be determined exactly as before this
  change (a version mismatch is advisory, not a health-check failure)
