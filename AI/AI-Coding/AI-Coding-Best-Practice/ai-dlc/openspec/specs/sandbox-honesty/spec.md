# sandbox-honesty Specification

## Purpose
TBD - created by archiving change gateway-open-sandbox. Update Purpose after archive.

## Requirements

### Requirement: probe-creates-nothing

The target classifier SHALL observe the path it classifies without
bringing any of it into existence, and SHALL report every path its
measurement left standing that did not stand before it.

#### Scenario: A path that never stood

- **WHEN** a repository path does not stand before classification

- **THEN** the class is `invisible`, `probe_created_paths` is empty,
  and the path still does not stand afterwards — on the caller's side
  and in the probe's own view

### Requirement: mount-veto

The classifier SHALL compare the deepest mount covering the path
between the gateway's own mountinfo and the caller's, and a mount that
differs SHALL decide the class `invisible` regardless of what the
probe reports behind it.

#### Scenario: The unit rolled back

- **WHEN** the unit runs its hardened form with a private `/tmp`, and
  the repository stands under `/tmp`

- **THEN** the class is `invisible`, `decision_basis` is `mountinfo`,
  and `masked_by` names the mount — not the probe's view of it

#### Scenario: The open unit

- **WHEN** the unit declares no mount the caller lacks

- **THEN** the comparison is recorded as performed and equal, and the
  probe decides

### Requirement: conservative-disagreement

When the unit declares a writable allowlist and the probe disagrees
with it, the classifier SHALL resolve to the most conservative answer
and name `grants` as the deciding basis; an allowlist the unit does
not declare claims nothing.

#### Scenario: Writable beyond a declared allowlist

- **WHEN** the probe can write a path the unit's declared allowlist
  does not cover

- **THEN** the class is `readable` and `decision_basis` is `grants`

### Requirement: close-checks-before-moving

The close SHALL establish the repository's class before the archive
dispatch runs, and SHALL stop without touching the plane's tree when
the class is not `writable`.

#### Scenario: The repository is not writable

- **WHEN** the repository classifies other than `writable` at close
  time

- **THEN** close exits non-zero reporting `closed: false` with the
  reachability it measured, the plane's change directory still stands,
  and no archive record is written

### Requirement: close-resumes-at-write-back

The close SHALL NOT re-run the archive literal when the plane tree's
shape says the archive already ran; the session SHALL run the
write-back alone against the archive directory that stands, and the
signed record SHALL say the session resumed rather than carrying
results for a command that did not run.

#### Scenario: A half-closed tree

- **WHEN** the plane tree holds `archive/<date>-<id>` for the change
  and no `changes/<id>`, and the repository is writable

- **THEN** close writes the standing archive back under a
  plane-authored commit, exactly one archive directory for the change
  stands plane-side, the record carries `resumed: true` with the
  archive command's columns empty, and the close JSON reports
  `resumed_from: "write-back"`

### Requirement: dual-regime-honesty

The runtime SHALL behave correctly under the open unit and under the
hardened form a unit restore brings back, and the test suite SHALL
establish every class by fixtures rather than by the live unit's
regime.

#### Scenario: A fresh /tmp repository end to end

- **WHEN** a change in a fresh `/tmp` repository runs migrate,
  validate and close under the open unit

- **THEN** the repository carries the archived tree under a
  plane-authored commit and no split state stands
