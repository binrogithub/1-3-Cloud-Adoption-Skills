## ADDED Requirements

### Requirement: doctor's workspace check covers every shipped workspace skill

`install.sh --doctor` SHALL verify registration and installation for every
skill directory under `supervisor/skills/workspace/`, not a hard-coded
subset.

#### Scenario: A shipped skill is installed and registered

- **WHEN** every directory under `supervisor/skills/workspace/` has a
  corresponding installed `SKILL.md` and exactly one registration entry
  in the target's `skills_state.json`
- **THEN** `--doctor` SHALL report all workspace checks OK
- **AND** its exit code SHALL be 0 (assuming no other check fails)

#### Scenario: A shipped skill is missing or unregistered

- **WHEN** a directory exists under `supervisor/skills/workspace/` whose
  corresponding installed `SKILL.md` is absent, or whose registration
  count in `skills_state.json` is not exactly 1
- **THEN** `--doctor` SHALL fail that check, naming the skill and the
  expected-vs-found state
- **AND** `--doctor`'s overall exit code SHALL be 1

#### Scenario: A skill is registered more than once

- **WHEN** `skills_state.json` carries two or more entries with the same
  skill name
- **THEN** `--doctor` SHALL fail, naming the duplicate — it SHALL NOT
  silently treat this as satisfied

#### Scenario: The gateway workspace has no skills_state.json at all

- **WHEN** `skills_state.json` does not exist at the workspace path
- **THEN** `--doctor` SHALL warn, not fail, for this reason alone
- **AND** this warning SHALL NOT by itself cause `--doctor`'s exit code
  to be 1
