# Build Standards

## Surgical Change Rules

### Rule 1: Touch Only What You Must

- Change only the files listed in the approved plan
- Do not "improve" adjacent code
- Do not refactor unrelated functions
- Every changed line must trace to the specification

### Rule 2: Match Existing Style

- Follow the existing code style in each file you modify
- Do not introduce new patterns that differ from the codebase
- Run the linter before committing; fix all violations

### Rule 3: Minimum Diff

- The diff should be as small as possible while correctly implementing the spec
- No speculative features ("while we're here, let's also...")
- No premature abstractions ("this might be needed later")

### Rule 4: Commit as Save Point

- Commit after each vertical slice (test + implementation)
- Commit message format: `feat(module): description (#issue)`
- Each commit should leave the codebase in a working state

### Rule 5: No Speculative Features

- Implement only what the spec requires
- If you think of a better approach, update the spec first, then implement
- "Might be needed later" is not a reason to add code now

## Branch Naming

- Feature: `feat/<issue-number>-<short-description>`
- Bug fix: `fix/<issue-number>-<short-description>`
- Refactor: `refactor/<short-description>`

## Commit Message Format

```
type(scope): description (#issue)

type: feat, fix, refactor, test, docs, chore
scope: module or component name
description: imperative mood, lowercase, no period
```

Examples:
- `feat(auth): add MaaS token refresh logic (#123)`
- `fix(proxy): handle 429 rate limit response (#124)`
- `test(coverage): add edge case tests for token counting (#125)`
