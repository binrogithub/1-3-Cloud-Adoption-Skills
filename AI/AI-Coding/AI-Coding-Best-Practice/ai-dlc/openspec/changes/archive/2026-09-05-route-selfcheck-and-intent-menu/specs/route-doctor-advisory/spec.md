## ADDED Requirements

### Requirement: `plan.py next` surfaces a toolchain health advisory without blocking

`plan.py next` SHALL run a lightweight toolchain health check before
returning, and SHALL include a human-readable advisory in its output when
that check fails, without altering its existing return contract otherwise.

#### Scenario: Toolchain is healthy

- **WHEN** `bin/plan.py`, `bin/report.py`, and `config/collapsed.config.yaml`
  are present and executable/parseable, and the configured gateway is
  reachable
- **THEN** `plan.py next`'s return object SHALL contain no `advisory` key
- **AND** `stage`, `blocked_on`, `do`, `then`, and `not_yet` SHALL be
  computed exactly as before this change

#### Scenario: A required file is missing or not executable

- **WHEN** `bin/plan.py`, `bin/report.py`, or `config/collapsed.config.yaml`
  is missing, unreadable, or (for the two scripts) not executable
- **THEN** `plan.py next`'s return object SHALL contain an `advisory` string
  naming the specific missing or broken item and a copy-pasteable repair
  command
- **AND** `stage`, `blocked_on`, `do`, `then`, and `not_yet` SHALL still be
  computed and returned

#### Scenario: The gateway is unreachable

- **WHEN** the configured dispatch gateway does not respond to a
  connectivity probe
- **THEN** `plan.py next`'s return object SHALL contain an `advisory` string
  naming gateway unreachability
- **AND** the command SHALL still return its normal exit code for the
  underlying task state

### Requirement: The advisory check never blocks or retries

- **WHEN** the health check fails for any reason
- **THEN** `plan.py next` SHALL still return normally (no non-zero exit
  caused by the health check itself)
- **AND** the check SHALL run at most once per `next` invocation, with no
  automatic retry

### Requirement: The advisory check is read-only

- **WHEN** the health check runs, regardless of outcome
- **THEN** no file SHALL be created, modified, or deleted as a result
