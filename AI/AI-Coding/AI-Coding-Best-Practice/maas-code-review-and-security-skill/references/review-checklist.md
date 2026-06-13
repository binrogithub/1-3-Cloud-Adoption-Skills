# Code Review Checklist

## Correctness

- [ ] Does the code do what the spec/issue claims?
- [ ] Are all edge cases handled (empty input, null, max length, boundary)?
- [ ] Are return values correct for all code paths?
- [ ] Is the logic correct (no off-by-one, no wrong comparison operator)?
- [ ] Are there any dead code paths (unreachable code)?

## Error Handling

- [ ] Are errors caught at the appropriate level?
- [ ] Are error messages informative but not leaking sensitive data?
- [ ] Are errors propagated correctly (not swallowed silently)?
- [ ] Are timeouts handled (MaaS API calls, network requests)?
- [ ] Are retry conditions correct (retry on 429/503, not on 400/401)?

## Test Coverage

- [ ] Are new code paths covered by tests?
- [ ] Are tests derived from the specification, not the implementation?
- [ ] Are edge cases tested?
- [ ] Are error paths tested?
- [ ] Are MaaS API calls mocked in unit tests?

## Style and Maintainability

- [ ] Does the code conform to project style (linter should catch most)?
- [ ] Are names descriptive and consistent with project conventions?
- [ ] Is the code at the right level of abstraction?
- [ ] Are there any unnecessary abstractions (YAGNI)?
- [ ] Is the code self-documenting (minimal comments needed)?

## Documentation

- [ ] Are public APIs documented?
- [ ] Are ADRs updated for architectural decisions?
- [ ] Is the README updated for user-facing changes?
- [ ] Are migration guides updated for breaking changes?

## Architecture

- [ ] Does this change fit the existing architecture?
- [ ] Are new dependencies justified (not adding a library for one function)?
- [ ] Is the change scoped correctly (not mixing concerns)?
- [ ] Does this introduce coupling that should be avoided?

## Change Sizing

- Ideal review: ~100-300 lines changed
- If > 500 lines: consider splitting into smaller PRs
- If > 1000 lines: must justify why splitting is not possible
