# EPIC Breakdown — LLMWiki Agent Studio V2 (streaming + thinking)

Source PRD: `docs/PRD_LLMWIKI_AGENTSTUDIO_V2.md` · V2.0 · 2026-09-24.
Marks: ✅ done · 🟡 partial · ⬜ not started. Verification: **L-live** (observed on
247 through the real model/instance) · **L-unit** · **L-none**.

| Epic | Title | Status | Stories ✅/🟡/⬜ |
|---|---|---|---|
| E20 | Glue streaming core | ✅ | 5 / 0 / 0 |
| E21 | SSE v2 protocol | ✅ | 4 / 0 / 0 |
| E22 | Agent Studio page | ✅ | 5 / 0 / 0 |
| E23 | Acceptance & regression | ✅ | 4 / 0 / 0 |

**Critical path:** E20 → E21 → E22 → E23 (strictly serial; each gates the next).

---

## E20 — Glue streaming core ✅

| ID | Story | Status | Verification | Evidence |
|---|---|---|---|---|
| E20-S1 | `jiuwen.run` streaming mode: Popen + per-line `on_event` callback; exit-code mapping unchanged | ✅ | L-unit | `jiuwen.run_stream`; `run()` now wraps it |
| E20-S2 | `chat.reasoning` captured (`RunResult.reasoning`) and forwarded; `chat.tool_update` surfaced | ✅ | L-unit | fake emits `chat.reasoning` |
| E20-S3 | Fake `tests/fakes/jiuwenswarm` emits reasoning + tool_update lines (replaying captured shapes) | ✅ | L-unit | `FAKE_REASONING=off` toggle |
| E20-S4 | Provisional extraction in the callback path (`_role_output` on the tool_result event) | ✅ | L-unit | unit asserts one provisional per ask |
| E20-S5 | Thinking never persisted: ask log & audit unchanged, no reasoning field stored | ✅ | L-unit | log record assert |

## E21 — SSE v2 protocol ✅

| ID | Story | Status | Verification | Evidence |
|---|---|---|---|---|
| E21-S1 | Event set: ack → retrieval → thinking* → progress* → provisional → final/error (+ping) | ✅ | L-live | AG-S1 capture |
| E21-S2 | GL-A7 amendment implemented: provisional display-only, final authoritative, no_citations replaces provisional | ✅ | L-live | AG-S2 |
| E21-S3 | V1 clients unaffected: `/ask.json`, old UI, gates still work | ✅ | L-unit+L-live | AG-S4 |
| E21-S4 | Idle ping ≥1/10 s; event coalescing for reasoning bursts | ✅ | L-live | AG-S5 |

## E22 — Agent Studio page ✅

| ID | Story | Status | Verification | Evidence |
|---|---|---|---|---|
| E22-S1 | Studio api `POST /api/llmwiki/ask` SSE proxy (LLMWIKI_GLUE_URL, server-side token, studio auth) | ✅ | L-live | AG-S3 |
| E22-S2 | `GET /api/llmwiki/health` passthrough | ✅ | L-live | page header shows glue SHA |
| E22-S3 | `/llmwiki` page: question + lang selector, thinking panel (collapsed, live count), two-state answer area, citations/issues/stale, elapsed timer | ✅ | L-live | browser + AG-S3 |
| E22-S4 | Provisional styling distinct; error removes provisional | ✅ | L-live | AG-S2 path |
| E22-S5 | Compose/env wiring (host-gateway reachability), web rebuild | ✅ | L-live | container rebuilt, page served |

## E23 — Acceptance & regression ✅

| ID | Story | Status | Verification | Evidence |
|---|---|---|---|---|
| E23-S1 | AG-S1 stream honesty capture | ✅ | L-live | eval/results/ag-s1 capture |
| E23-S2 | AG-S2 trust intact (redaction changes text; abstention path) | ✅ | L-live | capture + unit |
| E23-S3 | AG-S3 studio-path parity | ✅ | L-live | direct vs proxied event order equal |
| E23-S4 | AG-S4 V1 regression: unit suite + ag0/ag2/ag5/ag8 on streaming path | ✅ | L-live | all green |
