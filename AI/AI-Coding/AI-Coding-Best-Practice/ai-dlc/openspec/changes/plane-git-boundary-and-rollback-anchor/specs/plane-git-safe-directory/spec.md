## ADDED Requirements

### Requirement: git operations against plane-owned paths succeed regardless of caller uid

Git calls against `plane_root()`-derived paths SHALL succeed even when the
calling process's uid differs from the path's owning uid, via a
per-invocation `safe.directory` override scoped to exactly that path.

#### Scenario: Caller uid differs from plane path owner

- **WHEN** `git_status_paths`, `cmd_sweep`'s file restoration, or the
  per-role boundary baseline snapshot operates on a `plane_root()`-derived
  path owned by a different uid
- **THEN** the git invocation SHALL succeed rather than failing with a
  dubious-ownership error

#### Scenario: The override never leaks

- **WHEN** any `git_run()` call completes, successfully or not
- **THEN** no file on disk (including `~/.gitconfig` or any repo-level
  git config) SHALL be modified as a result
- **AND** no environment variable SHALL be set as a result
- **AND** a subsequent, unrelated git invocation against the same or a
  different path SHALL be unaffected by any prior `git_run()` call

### Requirement: Non-plane git calls are unaffected

Git calls that do not operate on a `plane_root()`-derived path SHALL NOT
be routed through `git_run()`'s safe.directory override.

#### Scenario: A call against the caller's own --repo

- **WHEN** a git call targets the target repository the user supplied via
  `--repo`, not a plane path
- **THEN** it SHALL continue to use the existing `run()` path unchanged

### Requirement: Boundary-check failure causes remain distinguishable

A failure in the pre-dispatch boundary baseline snapshot SHALL report
enough detail to distinguish "the target could not be read at all" from
"git itself reported a specific error."

#### Scenario: Target path does not exist

- **WHEN** the boundary baseline snapshot's target path does not exist or
  is not a directory
- **THEN** the result SHALL report `"boundary": "unknown"` as it does today

#### Scenario: git reports an error for an existing path

- **WHEN** the target path exists but the git invocation itself fails
  (after the safe.directory override, ruling out ownership mismatch)
- **THEN** the result SHALL include the git error detail distinguishable
  from the "target does not exist" case, so a human reading the report
  can tell the two apart
