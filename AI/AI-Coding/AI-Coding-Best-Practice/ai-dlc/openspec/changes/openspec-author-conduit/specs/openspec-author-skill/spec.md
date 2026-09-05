## ADDED Requirements

### Requirement: A dispatched authoring role can fetch its instructions through openspec-author

Once `openspec-author` is installed and registered in the gateway
workspace, a role dispatched by `plan.py dispatch` or `plan.py phase` for
a planned-route artifact SHALL be able to run
`openspec instructions <artifact> --change <id> --json` and follow its
returned instruction, template, and output path.

#### Scenario: Skill installed and registered

- **WHEN** `openspec-author/SKILL.md` exists in the gateway workspace
- **AND** it is registered exactly once in `skills_state.json`'s
  `installed_plugins`
- **THEN** `authoring_skill_state().ok` SHALL be `true`
- **AND** `cmd_dispatch`/`cmd_phase` SHALL proceed to open the client
  rather than refusing with `EXIT_SKILL_MISSING`

#### Scenario: A dispatched role actually uses the conduit

- **WHEN** a planned-route role is dispatched with the skill installed
- **THEN** the dispatch's evidence frames SHALL contain a command matching
  `openspec instructions <artifact> --change <id> --json`
- **AND** the role's produced artifact SHALL be written to the output path
  that command reported, not to a path the role invented

### Requirement: The conduit never restates role-prompt discipline

The `openspec-author` `SKILL.md` SHALL NOT duplicate the authoring
constraints already carried by the dispatch prompt (write-only-your-own-
artifact, no self-validation, the CLI-unavailable stop protocol).

#### Scenario: Reviewing the skill file's content

- **WHEN** the skill file's body is read
- **THEN** it SHALL describe only: what artifact/change context it serves,
  the exact CLI invocation to run, and a pointer to the dispatch prompt's
  existing stop protocol (not a restatement of it)

### Requirement: The conduit does not pin a schema

`openspec-author` SHALL NOT pass `--schema` to `openspec instructions`.

#### Scenario: A repo uses a non-default schema

- **WHEN** the target repo's `config.yaml` selects a schema other than
  `spec-driven`
- **THEN** the conduit's invocation SHALL still omit `--schema`, relying on
  openspec's own auto-detection
- **AND** an artifact-name mismatch this produces SHALL surface as the
  role's existing fail-closed stop (the CLI reporting an error), never as
  a silently wrong artifact
