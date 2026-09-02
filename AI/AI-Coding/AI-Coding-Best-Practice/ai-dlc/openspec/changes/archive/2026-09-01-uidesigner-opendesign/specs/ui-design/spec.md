## ADDED Requirements

### Requirement: applicability-is-measured

The runtime SHALL decide the design role's applicability from the
change's product surface by file extension, and SHALL NOT accept a
model's self-description or prompt adjectives as evidence of
applicability.

#### Scenario: A backend change

- **WHEN** the change's product surface carries no `web` or `deck`
  file, and the design dispatch is requested

- **THEN** the dispatch is refused before any session opens (exit 24),
  and the measured surface travels in the refusal verbatim

#### Scenario: A frontend change

- **WHEN** the change's product surface carries at least one `web` or
  `deck` file

- **THEN** the dispatch is applicable, with the measured classes and
  files recorded

### Requirement: design-conclusions-are-signed-records

A design conclusion SHALL exist only as an HMAC-signed record the
caller wrote from the session's frames, and `deliver` SHALL report
exactly one of four design states — `design_applied`,
`design_declined`, `design_unverified`, `design_not_applicable` —
derived from the record, a recorded skip, and the applicability
measurement.

#### Scenario: No record

- **WHEN** the change is applicable and no signed design record
  verifies

- **THEN** `deliver` reports `design_unverified`, the delivery does
  not fail on it, and nothing re-runs the dispatch on its own

#### Scenario: A tampered record

- **WHEN** a design record's signature does not verify

- **THEN** the record counts as no record, reported as tampering
  evidence, and the state is `design_unverified`

#### Scenario: A recorded skip

- **WHEN** the change is applicable and a person recorded skipping the
  design pass with a reason

- **THEN** `deliver` reports `design_declined` carrying the reason
  verbatim

#### Scenario: Not applicable

- **WHEN** the change's product surface carries no `web` or `deck`
  file

- **THEN** `deliver` reports `design_not_applicable` and asks for
  nothing

### Requirement: facts-from-frames-not-claims

The design record SHALL be written only when the session's frames show
all five facts — a read of an upstream `SKILL.md`, files written that
the filesystem confirms, every referenced asset resolving, pages
rendering with a non-empty DOM, and no placeholder text in the
produced surface — and SHALL NOT be written on the role's claim alone.

#### Scenario: The claim without the read

- **WHEN** the role reports the surface beautified and the frames show
  zero reads under the upstream tree

- **THEN** no record is written, the dispatch reports why, and the
  delivery state is `design_unverified`

### Requirement: one-pointer-skill

The runtime SHALL reach the upstream tree through exactly one gateway
workspace skill that points at it and copies none of its content, and
SHALL refuse the design dispatch when that skill is not installed and
registered, with the remedy, instead of installing anything itself.

#### Scenario: The skill is missing

- **WHEN** the pointer skill's `SKILL.md` is absent or unregistered in
  the workspace state

- **THEN** the dispatch is refused before any session opens (exit 25)
  carrying the remedy, and nothing is installed

### Requirement: pinned-readonly-upstream

The runtime SHALL treat the upstream tree as a pinned, read-only
reference, and SHALL refuse the design dispatch when the pin is
missing or the tree's measured digest does not match it (exit 26),
with the remedy naming the pin.

#### Scenario: The tree drifted

- **WHEN** a file under the upstream tree has been modified since the
  pin was written

- **THEN** the dispatch is refused before any session opens and the
  remedy names the pin and the mismatch

### Requirement: shell-cannot-see-the-upstream

The CC runtime shell SHALL mask the upstream tree and every `od`
entry on PATH under the same rule as the spec surface: masked, or the
shell refuses to start.

#### Scenario: The upstream stands

- **WHEN** the upstream tree stands on the host and the shell builds
  its mask

- **THEN** the tree and the `od` entries are in the mask, and reading
  them inside the unit fails while the same read outside succeeds

#### Scenario: The mask missed them

- **WHEN** the upstream tree or an `od` entry exists and escaped the
  mask

- **THEN** the shell refuses to start rather than running
  under-contained

### Requirement: zero-direct-upstream-calls

The runtime's `bin/` SHALL make no process call to `od` or
`open-design`: every reach through the upstream tree belongs to a
dispatched plane session reading files, never to the caller's own
argv.

#### Scenario: The regression gate

- **WHEN** `bin/` is scanned for subprocess or argv invocations naming
  `od` or `open-design`

- **THEN** the scan finds none, and a future addition that adds one
  fails the suite
