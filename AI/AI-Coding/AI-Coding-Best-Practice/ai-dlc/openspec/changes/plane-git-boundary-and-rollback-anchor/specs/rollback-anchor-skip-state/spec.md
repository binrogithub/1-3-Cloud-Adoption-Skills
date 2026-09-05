## ADDED Requirements

### Requirement: An unreachable rollback anchor reports SKIP, not FAIL, and never a fabricated PASS

`dt1_gates.sh`'s rollback-anchor check SHALL distinguish "this repo's
history does not carry the named tag at all" from "the tag exists but the
anchored file is missing from it."

#### Scenario: The tag does not exist in this repo's history

- **WHEN** `git rev-parse -q --verify v0.8.0` fails (no such tag)
- **THEN** the check SHALL emit a line naming SKIP, the tag, the file, and
  the reason ("not carried by this repo's history — a republished copy")
- **AND** this SHALL NOT cause the overall gate script to exit non-zero
  for this reason alone

#### Scenario: The tag exists but the file is missing from it

- **WHEN** `git rev-parse -q --verify v0.8.0` succeeds
- **AND** `git cat-file -e v0.8.0:bin/oracle.py` fails
- **THEN** the check SHALL FAIL and the overall gate script SHALL exit
  non-zero, exactly as before this change

#### Scenario: The tag exists and the file is present

- **WHEN** both checks succeed
- **THEN** the check SHALL report success as it does today

### Requirement: No fabricated history satisfies this check

Under no circumstance SHALL a tag or commit be created solely to make this
check pass without that tag genuinely representing history this specific
repo copy carries forward.

#### Scenario: Reviewing an implementation of this change

- **WHEN** the implementation is reviewed
- **THEN** it SHALL NOT include creating, backfilling, or importing a
  `v0.8.0` tag or a `bin/oracle.py` blob into this repository's history
