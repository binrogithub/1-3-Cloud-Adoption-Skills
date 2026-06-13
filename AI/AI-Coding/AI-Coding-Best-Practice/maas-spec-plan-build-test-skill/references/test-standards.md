# Test Standards

## Derive Tests from Specification, Not Implementation

Tests must verify the behavior described in the specification, not the implementation details. If the implementation changes but the behavior is the same, tests should still pass.

**Bad**: Test that a function calls a specific internal helper
**Good**: Test that a function returns the correct result for given input

## Test Naming

- `test_<function>_<scenario>_<expected_result>`
- Example: `test_process_payment_invalid_card_raises_error`
- Group by module in describe/context blocks

## Coverage Requirements

| Language | Minimum | Target |
|----------|:---:|:---:|
| Java | 80% | 90% |
| Python | 70% | 85% |
| Go | 60% | 80% |
| JavaScript | 70% | 85% |
| .NET | 70% | 85% |

## Test Types

### Unit Tests (80% of test suite)

- Test individual functions/methods in isolation
- Mock external dependencies (MaaS API calls, database, file system)
- Fast execution (< 1s per test)
- No network calls

### Integration Tests (15% of test suite)

- Test component interactions
- May call real MaaS API (with test key) or use recorded fixtures
- Test the full request/response cycle
- Verify schema compliance

### End-to-End Tests (5% of test suite)

- Test complete user workflows
- Run against staging environment
- Include MaaS-backed flows end-to-end
- Slow; run in CI only, not locally

## Edge Case Requirements

Every function that processes input must be tested for:
- Empty input
- Null/nil/undefined input
- Maximum length input
- Boundary values (0, 1, max-int, min-int)
- Concurrent access (if applicable)
- Network failure (for functions that call MaaS)

## MaaS Mock Rules

- **Never** call real MaaS in unit tests
- Mock at the HTTP layer (nock, responses, httptest)
- Record real MaaS responses for integration fixtures (cassette pattern)
- Stubs return deterministic responses matching expected schema
- Verify mock coverage: every MaaS endpoint in production has a corresponding mock

## Test Execution

- Run full suite on every commit (CI)
- Run affected tests on every save (local, watch mode)
- Never skip tests without documenting the reason and linking an issue
- Flaky tests must be fixed immediately, not quarantined
