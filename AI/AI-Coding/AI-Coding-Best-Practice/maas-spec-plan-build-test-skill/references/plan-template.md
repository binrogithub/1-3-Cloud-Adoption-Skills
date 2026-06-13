# Plan Template

## Approach

[High-level approach to implementing the specification. What design pattern? What architecture?]

## Files Affected

| File | Action | Description |
|------|--------|-------------|
| src/module/new-file.py | Create | [What this file does] |
| src/module/existing-file.py | Modify | [What changes] |
| tests/module/test-new.py | Create | [Tests for new file] |

## Change Description per File

### src/module/new-file.py (Create)

[Detailed description of what this file will contain. Key functions, classes, their signatures and behavior.]

### src/module/existing-file.py (Modify)

[Specific lines/sections to change. What the current code does, what the new code will do.]

## Dependencies

- [New dependency to add: name, version, reason]
- [Existing dependency: no change needed]

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|:---:|:---:|-------------|
| [Risk 1] | Low | High | [Mitigation strategy] |
| [Risk 2] | Medium | Medium | [Mitigation strategy] |

## Rollback Strategy

[How to revert this change if it fails in production. Feature flag? Blue-green? Simple revert?]

## Estimated Complexity

- Lines of code: ~[N]
- Files changed: [N]
- Estimated effort: [hours/days]
- Test coverage needed: [N] new tests

## Vertical Slice Order

1. [Slice 1: smallest testable increment]
2. [Slice 2: builds on slice 1]
3. [Slice 3: builds on slice 2]
4. [Slice N: final increment]

Each slice: write test -> implement -> verify -> commit
