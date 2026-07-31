# Testing Standard for Generated MCPs

## Test Categories

1. **Unit tests**: Test tool logic in isolation with mocks
2. **Contract tests**: Validate input/output schemas
3. **Safety tests**: Verify approval gates, CIDR checks, secret redaction
4. **Integration tests**: Test against real service (requires credentials, SKIPPED_CLOUD_SIDE_EFFECT)

## Test Requirements

- All unit tests must pass without cloud credentials
- All safety tests must pass without cloud credentials
- Integration tests are optional and require controlled environment
- Test coverage for all tool contracts
- No test should create real cloud resources

## Test Result Classification

| Result | Description |
|---|---|
| EXECUTED_PASS | Test ran and passed |
| EXECUTED_FAIL | Test ran and failed |
| SKIPPED_REQUIRES_CREDENTIALS | Test needs real credentials |
| SKIPPED_CLOUD_SIDE_EFFECT | Test would modify cloud state |
| NOT_AVAILABLE | Test not yet implemented |
