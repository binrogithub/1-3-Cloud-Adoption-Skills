# install-sync Specification

## Purpose
What stands in the code also stands in the install face and the
documentation.

## Requirements

### Requirement: The doctor sees the campaign assets

doctor SHALL check the eval set, the deterministic replay runner with
node, a live chromium launch (not merely the tree), the
dispatch_policy section and the validator model posture - warn-level,
never fail.

#### Scenario: A dead shell is named although the tree stands

- **WHEN** the chromium headless shell cannot start
- **THEN** doctor SHALL warn with the EL8 remedy line

### Requirement: The toolkit read-back covers the campaign assets

install_full_toolkit SHALL assert eval.py, evals/set.json and
scripts/browser-spec-runner.js exist after the copy.

#### Scenario: A dropped runner fails the read-back

- **WHEN** the copy omits scripts/browser-spec-runner.js
- **THEN** the install SHALL fail the read-back naming the missing file

### Requirement: The browser installer owns the OS libraries

install-browser-verify SHALL probe the shell after pinning, best-effort
install the OS set on failure, and name the remedy when still dead.

#### Scenario: A fresh EL8 host gets its libraries

- **WHEN** the headless shell cannot start after the pin
- **THEN** the installer SHALL attempt the dnf dependency set and
  re-probe, naming the remedy if it still cannot start

### Requirement: The Readme carries the campaign

The Readme SHALL describe the fourteen capabilities, the new verb
surfaces in its quickstart, and the A/B verdict numbers.

#### Scenario: The quickstart names the new surfaces

- **WHEN** the Readme manual flow section is read
- **THEN** checkpoint, codegraph query, browser-verify --run-spec,
  patterns, stallguard, nudge and dispatch-doctor SHALL appear with
  runnable command lines
