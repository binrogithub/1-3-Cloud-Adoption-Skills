# Testing Checklist

## Coverage Thresholds by Language

| Language | Unit Test Minimum | Integration Test | Tool |
|----------|:---:|:---:|------|
| Java | 80% | Required for MaaS-backed flows | JUnit 5 + JaCoCo |
| Python | 70% | Required for API endpoints | pytest + coverage |
| Go | 60% | Required for HTTP handlers | go test + cover |
| JavaScript/TypeScript | 70% | Required for API routes | Jest + c8 |
| COBOL | N/A | Golden-file comparison | Custom harness |
| .NET | 70% | Required for API controllers | xUnit + coverlet |

## Unit Test Requirements

- Every public function/method must have at least one test
- Edge cases: empty input, null/nil, max length, boundary values
- Error paths: invalid input, network failure, timeout
- No test should depend on execution order
- No test should modify shared state without cleanup

## Integration Test Requirements for MaaS-Backed Flows

- Test the full request/response cycle: client → proxy → MaaS → response
- Verify response schema matches expected format
- Verify error handling: MaaS returns 429, 500, timeout
- Verify rate limiting: requests queue correctly at 1 QPS
- Use a MaaS test endpoint or mock server (never call production MaaS in tests)

## Smoke Test Pattern

The standard MaaS smoke test:

```bash
curl -s -X POST "${MAAS_BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5.1","messages":[{"role":"user","content":"Reply with OK only"}],"max_tokens":10}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); assert r['choices'][0]['message']['content'].strip()=='OK', f'Expected OK, got {r}'"
```

## Test Naming Conventions

- `test_<function>_<scenario>_<expected_result>`
- Example: `test_process_payment_invalid_card_raises_error`
- Group tests by module in describe/context blocks

## Mock/Stub Rules for MaaS API Calls

- **Never** call real MaaS in unit tests
- Mock the MaaS client at the HTTP layer (nock, responses, httptest)
- Record real MaaS responses for integration test fixtures (cassette pattern)
- Stubs return deterministic responses matching the expected schema
- Verify mock coverage: every MaaS endpoint used in production has a corresponding mock

## Performance Test Thresholds

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| MaaS chat completion p50 | < 2s | Client-side timing |
| MaaS chat completion p99 | < 10s | Client-side timing |
| Proxy overhead | < 100ms | Proxy timing vs direct MaaS |
| Token throughput | > 100 tokens/s | Output tokens / wall time |

## Evidence Requirements

Every test run must produce:
- Exit code (0 = pass, non-zero = fail)
- Coverage percentage per module
- List of failing tests (if any)
- Duration per test suite
- Timestamp

This evidence is consumed by the quality gate in `maas-ai-coding-quality-skill`.
