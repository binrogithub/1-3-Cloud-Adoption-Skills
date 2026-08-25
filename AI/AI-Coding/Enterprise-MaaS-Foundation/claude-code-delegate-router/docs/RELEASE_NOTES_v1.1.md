# Release Notes — v1.1

**Date:** 2026-08-22
**Branch:** `main`
**Commits:** 8 (from `b7c986e` v1.0 to `65b6fcd` HEAD)

## Summary

Seven rounds of production hardening (V1–V7) addressing stream reliability,
capacity leaks, observability, and the GLM-5.2 malformed-tool-args failure
mode. The release criterion changed from "root cause eliminated" to
"failure controlled and explainable" — the 9.0% hard failure rate
(`stream protocol error`) is converted to a soft degradation via safe
fallback text blocks.

## What changed

### Stream reliability (V1–V2, commits `93a4b30` → `8a35e6b`)
- **K1/K2**: Keepalive timer fixed — worst-case byte gap is now
  `INTERVAL + jitter` instead of `2× INTERVAL`. Test thresholds tightened
  to constant tolerance with bidirectional FAIL/PASS evidence.
- **R1 (P0)**: Concurrency slot leak fixed — `cleanup()` moved into
  `finally`, made idempotent, `onClose`/watchdog call it directly, reaper
  safety net added. Previously 8 failures = total outage.
- **R5**: Structured per-request terminal logging (`fs.writeSync` to stderr
  for unbuffered delivery), `/status` enriched with `error_counts`,
  `recent_errors`, `reaped_slots`.
- **D4**: Keepalive ping shape aligned to `{"type":"ping"}`.

### Diagnostics (V3–V5, commits `eb4336c` → `86e15c0`)
- **T1**: Three-gate tool args repair (source/structure/semantic).
  `tool_args_repaired` has been 0 in production — the repair layer is
  a safety net, not a working fix.
- **T2**: `client_bytes` fixed from `res.bytesWritten` (undefined) to
  write-side counter. Bidirectional gates prove discrimination.
- **T3**: Hang path + reaper reverse gates added. `test_idle_hang_releases_slot`
  and `test_reaper_releases_orphan_slot` (reaped_slots 0→1).
- **T4**: `protocol_error_reason` — 13 `protocolError` sites each carry a
  constant reason string for log diagnostics.
- **V1**: Tool-call fragment aggregation key fixed (`call.index ??
  toolCalls.size` → OpenAI streaming semantics). `tool_call_index_absent`
  is always `false` in production — V1 fixed a real but untriggered defect.
- **U2/U3**: Reject-class classification (7 enums, no raw `err.message`)
  and `error_counts` double-count fix (idempotent by requestId).

### Safe degradation (V6–V7, commit `65b6fcd`)
- **V6 D1**: Shape diagnostics — `first_char_code` (integer code point) +
  `char_class_counts`. No payload characters logged.
- **X1**: Safe degradation — unresolvable tool args produce a text block
  with a safe message instead of killing the stream. `stop_reason:
  end_turn`. No tool executed, no `{}` fabricated.
- **X2**: Named classification — `<tool_call` markup as args →
  `tool_markup_as_args` (distinct from `tool_args_malformed`).
- **X3**: Normalization whitelist R1/R5/R6 — schema-directed, idempotent,
  re-validated after application.
- **X4**: Three-state mode `MAAS_TOOL_ARG_MODE = off|observe|enforce`,
  default `observe`.

## Known limitations

- **Tool args degradation rate**: baseline 9.0% (12/133 requests in the
  `7c0af42` window), reduced to 0.58% (1/172) in the `enforce` window.
  Bad tool args exist in **at least two distinct shapes**:
  - **Historical cluster** (25 occurrences, `7c0af42` / `86e15c0` windows):
    `args_len ∈ {39, 41}`, `reject_class: not_json`. Diagnostic fields were
    not yet deployed; `first_char_code` was not recorded.
  - **`enforce` window observation** (1 occurrence, `b5117fa4`):
    `args_len: 433`, `reject_class: unterminated_string`,
    `first_char_code: 0x7B` (`{`), `is_markup: false` — the args start with
    a valid JSON object and are truncated mid-string, while the upstream
    simultaneously provides a clean `finish_reason`.
  - **~~Hypothesis (revoked 2026-08-23)~~**: an earlier analogy from
    `litellm-auto-plugin`'s `<tool_call` markup prefix predicted
    `first_char_code = 0x3C`. **This hypothesis has been disproved by
    production observation** (`first_char_code: 0x7B`, `is_markup: false`).
    The analogy gave the correct *architectural* direction (safe degradation)
    but the wrong *shape* prediction.
- **T1 repair layer**: `tool_args_repaired` = 0 in production. The three-gate
  repair is a safety net that has not been triggered — it covers truncation
  *after a complete value* (e.g. `{"city":"Beijing"` → closeable to
  `{"city":"Beijing"}`), but the production observation (`b5117fa4`) is
  truncation *mid-string* (`{"city":"Beij`), which gate 2 rejects by design.
  Both are truncation; the difference is the truncation position, and the
  gate correctly distinguishes them.
- **V1 aggregation key fix**: `tool_call_index_absent` = `false` in all
  production requests. V1 fixed a real adapter defect that is not the
  production root cause.
- **Loop continuity (PRD LOOP_CONTINUITY_V1)**: in the initial v1.1 `enforce`
  deployment, malformed tool args caused the turn to end silently with
  `stop_reason: end_turn` and only the degradation text — the agent loop
  stopped with 0% self-recovery (vs. 32% for the old hard failure). Observation
  rate: 1.07% (6/559 turns). This is a regression relative to v1.0 on the
  task-completion dimension. **Fixed post-v1.1 by L1-A (upstream retry) +
  L1-B (error termination instead of silent end_turn) + L2 (continue instead
  of break, so subsequent valid tools are not dropped).** The fix restores
  ≥32% self-recovery while keeping X1's "never execute the tool" guarantee.
- **Tool args retry (PRD LOOP_CONTINUITY_V2 §3)**: when tool args are
  malformed, the adapter retries the call once via a non-streaming directed
  request (`stream: false` + `tool_choice`). Production success rate: **17/18
  (94%)** in the first window, 9/10 (90%) in the current window. If retry
  fails, the turn terminates with a protocol error (historically ~32%
  self-recovered by the client) instead of a silent `end_turn`. The retry's
  token consumption is **not currently included** in the `usage` returned to
  the client (M6, deferred to v1.2). The retry does not include the current
  turn's already-streamed text in its context (M7, deferred to v1.2). The
  retry occupies a concurrency slot for up to 30s; its interaction with the
  total-timeout watchdog is not yet gated (M8, deferred to v1.2).

## Release criteria (V7 §4)

1. **Hard failure zeroed**: `enforce` mode deployed for 24h,
   `isApiErrorMessage === true` new = 0. (Degradation path produces no
   API Error, so this is achievable.)
2. **Degradation rate visible and bounded**: `tool_args_malformed /
   request_end` has a clear value in Known limitations. If > 12%
   (baseline +3pp), degradation is masking a new problem → block release.
3. **Root cause attributed**: `first_char_code` distribution gives a clear
   conclusion. "Located but unfixed" is allowed; "unlocated" is not.
   **Current conclusion**: the `enforce`-window shape is an upstream contract
   issue — the upstream truncates args mid-string while signaling completion
   via `finish_reason ∈ {tool_calls, stop}`. No adapter-side repair is
   possible (closing an unterminated string silently drops characters).
   X1 safe degradation covers this; the `<tool_call` markup hypothesis is
   disproved (see Known limitations).

## Verification

- `make verify-offline` → 706 passed (build `7edc1ae0…`, after V10 test
  isolation fix)
- `make verify-live` → all 7 gates PASS (build `7edc1ae0…`; previous green
  was on `ae22fd4d…`, not carried forward)
- Runtime freshness: SHA-256 match, MainPID changed, `/status` reachable
- Real HOME (`~/.claude/`) unchanged

## Post-release watch (7 days from v1.1 tag; V9 §D3)

| Trigger | Action |
| --- | --- |
| `tool_args_degraded` > 0 | Update Known limitations with the measured degradation rate; use `first_char_code` distribution to qualitatively attribute root cause per cluster |
| `stream protocol error` recurs (`isApiErrorMessage === true`, full-scope) | X1 has a missed path — handle per V8 §D2 "≥1 hard failure" cell: block, investigate, do not re-delegate |
| Single-day degradation rate > 12% | Switch `MAAS_TOOL_ARG_MODE=observe` + restart, re-evaluate before re-enabling `enforce` |

These are watch items, not release gates. They are written into release
notes and do not require code changes unless triggered.

## Deployment mode

Shipped in `observe` mode (default), then switched to `enforce` via
`/etc/claude-code-proxy/maas.env` (`MAAS_TOOL_ARG_MODE=enforce`) at
2026-08-23 01:50:47. The original 24h window was interrupted twice by
deployments (LOOP_CONTINUITY_V1 at 01:25:15, V2 at 04:33:40) that changed
the code under observation. **The current window started at 2026-08-24
04:33:40 CST and ends 2026-08-25 04:33:40 CST** (build `b8c7069b…`).
One production observation (`b5117fa4`, `first_char_code: 0x7B`) is
recorded — see Known limitations. This is a single data point, not a
distribution; the historical cluster's `first_char_code` was never recorded.
