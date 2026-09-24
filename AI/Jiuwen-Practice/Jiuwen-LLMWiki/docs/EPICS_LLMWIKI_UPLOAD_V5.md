# EPIC Breakdown — Upload & auto-refresh V5

Source PRD: `docs/PRD_LLMWIKI_UPLOAD_V5.md` · V5.0 · 2026-09-24.

| Epic | Title | Status | Stories ✅/🟡/⬜ |
|---|---|---|---|
| E50 | Glue upload + auto-apply policy | ✅ | 4 / 0 / 0 |
| E51 | Studio proxy + upload UI | ✅ | 3 / 0 / 1 |
| E52 | Acceptance & regression | ✅ | 3 / 0 / 0 |

## E50 — Glue upload + auto-apply policy ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E50-S1 | `POST /upload` multipart (stdlib parser, size/type caps, contributor role, uploads dir, L1 ingest) | ✅ | L-unit (AG-P1/P2) |
| E50-S2 | Upload flow compiles + applies per §2 policy (`upload-autoflow` actor, audit record) | ✅ | L-unit |
| E50-S3 | Protected/conflicting/invalid stay pending | ✅ | L-unit (pricing case) |
| E50-S4 | Cache invalidation on application (V3 behaviour reused) | ✅ | L-unit |

## E51 — Studio proxy + upload UI ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E51-S1 | `POST /api/llmwiki/upload` multipart passthrough (server-side token) | ✅ | L-live (AG-P3) |
| E51-S2 | Upload area (file/kind/licence, live status, result banner with applied-page chips) | ✅ | L-live |
| E51-S3 | Roster refreshes in place after upload | ✅ | L-live |
| E51-S4 | Drag-and-drop (P1, R5-7) | ⬜ | deferred by PRD |

## E52 — Acceptance ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E52-S1 | AG-P1/P2 unit gates | ✅ | L-unit |
| E52-S2 | AG-P3 Playwright live upload | ✅ | L-live (ui/20-*.png) |
| E52-S3 | AG-P4 regression | ✅ | L-unit + L-live |
