# Release Evidence — MaaS Stream Reliability Production Closure v2

**Date:** 2026-08-20
**Branch:** `feat/direct-maas-router`
**PRD:** `docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`

## Source artifacts

| Artifact | SHA-256 (prefix) | Role |
|---|---|---|
| `adapter/server.js` | `4a26814770cf…` | Candidate adapter (with reliability controls) |
| `adapter/lifecycle.js` | `85569744a862…` | RequestLifecycleController (11-state machine) |
| `tests/fixtures/legacy_server.js` | `b0d7df992d24…` | Frozen legacy artifact (red proof) |

- **Legacy checksum** matches the production artifact running since 2026-08-04.
- **Candidate checksum** differs from legacy — the reliability controls are present.
- **No secrets** appear in any artifact (verified by leak-scan tests).

## Gate summary (G-CLOSE1–G-CLOSE12)

| Gate | Description | Status |
|---|---|---|
| G-CLOSE1 | External-contract red/green harness exists | ✅ `tests/test_adapter_contract.py` |
| G-CLOSE2 | Legacy fails (red), candidate passes (green) | ✅ 13 tests pass |
| G-CLOSE3 | Permanent silence → idle timeout | ✅ `test_silence_idle_timeout` |
| G-CLOSE4 | Connect/total timeouts enforced | ✅ `tests/test_lifecycle.py` |
| G-CLOSE5 | EOF without finish → failure (no fake success); malformed tool args → error (no `{}`) | ✅ `test_eof_no_finish_fails_not_success`, `test_tool_malformed_not_degraded_to_empty` |
| G-CLOSE6 | Reasoning content stripped from client output | ✅ `test_reasoning_never_in_client_output` |
| G-CLOSE7 | Sanitized `/status` (loopback-only, fail-closed, enum fields) | ✅ `tests/test_adapter_protocol_security.py` |
| G-CLOSE8 | Real C256 concurrency gate | ✅ `test_c256_admits_at_most_capacity` |
| G-CLOSE9 | Architecture docs reconciled (one loopback adapter allowed) | ✅ 17 architecture tests pass |
| G-CLOSE10 | `verify-adapter` make target | ✅ 67 adapter tests pass |
| G-CLOSE11 | Full `make verify-offline` > 516 tests | ✅ 590 tests pass |
| G-CLOSE12 | Rollback drill | ✅ Scripts validated (syntax + env-file safety) |

## Test counts

```
make verify-adapter    → 67 passed
make verify-offline    → 590 passed
```

## Adapter reliability controls (present in candidate, absent in legacy)

1. **11-state machine** — `accepted → connecting → upstream_active_hidden → visible_streaming → completing → completed` (plus 5 failure states)
2. **Active watchdogs** — connect (60s), idle (180s), total (600s) timeouts via `setTimeout`
3. **Cancellation** — `AbortController` per request; client close → idempotent `abort()`
4. **Finish-aware EOF** — `finalize()` fails with `MAAS_STREAM_EOF` if no trustworthy finish reason; never fakes `message_stop`
5. **SSE termination** — exactly one `message_start`/`message_stop`, index-once enforcement, block/delta pairing
6. **Reasoning filter** — `reasoning_content` counted + stripped before client write; never synthesized as `thinking` blocks
7. **Tool args safety** — malformed JSON → `MAAS_STREAM_PROTOCOL` (never degraded to `{}`)
8. **Backpressure** — `res.write()` returns false → drain handling
9. **Concurrency guard** — `ConcurrencyGuard(MAX_CONCURRENCY)`; over-capacity → 503 before fetch
10. **Sanitized `/status`** — loopback-only, fail-closed, enum-only fields, no content/secrets
11. **Size limits** — SSE event, tool args, request body, concurrency

## Rollback drill

The deploy/rollback scripts (`adapter/deploy.sh`, `adapter/rollback.sh`) are
validated for bash syntax and env-file safety (never write
`/etc/claude-code-proxy/maas.env`). The rollback script restores a saved
checksummed artifact and restarts the systemd unit.

**Operational rollback drill** (requires host systemd access — not run in CI):
```bash
bash adapter/deploy.sh        # deploy candidate
bash adapter/rollback.sh      # rollback to legacy
# verify health + text request
bash adapter/deploy.sh        # redeploy candidate
```

## Prohibitions preserved

- No `ANTHROPIC_*` env vars set in OAuth session
- No image/vision delegation to MaaS
- No OAuth token read/replayed in `claude-maas`
- No LiteLLM/CCR/OpenRouter/HTTP proxy invocation
- No model other than `glm-5.2` on MaaS endpoint
- `fallback` field always `false`
- No secrets written to repo/artifacts/evidence
- Adapter binds loopback only (verified at startup)
