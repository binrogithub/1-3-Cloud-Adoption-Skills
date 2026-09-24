# EPIC Breakdown — LLMWiki sidebar V3

Source PRD: `docs/PRD_LLMWIKI_SIDEBAR_V3.md` · V3.0 · 2026-09-24.
Marks: ✅ done · 🟡 partial · ⬜ not started. Verification: L-live / L-unit / L-none.

| Epic | Title | Status | Stories ✅/🟡/⬜ |
|---|---|---|---|
| E30 | Sidebar data plane | ✅ | 3 / 0 / 0 |
| E31 | Sidebar UI + detail views | ✅ | 4 / 0 / 1 |
| E32 | Acceptance & regression | ✅ | 3 / 0 / 0 |

## E30 — Sidebar data plane ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E30-S1 | glue `GET /source?id=` detail (meta+text, 404 unknown) | ✅ | L-unit (AG-B5) |
| E30-S2 | studio api proxies pages/sources/source (+auth, glue token server-side) | ✅ | L-live (AG-B1..B3) |
| E30-S3 | confidential text gating re-checked on the detail path | ✅ | L-unit (permission test) |

## E31 — Sidebar UI + detail views ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E31-S1 | two-pane layout, collapsible 280px sidebar, ask flow intact | ✅ | L-live |
| E31-S2 | filter box (AnythingLLM MIT pattern, debounce+reset, attribution kept) | ✅ | L-live (AG-B4) |
| E31-S3 | Wiki section: namespace groups + counts + active highlight; page detail view (markdown + meta + timeline) | ✅ | L-live (AG-B2) |
| E31-S4 | Sources section: rows with kind/licence/date; source detail view (meta table + raw text) | ✅ | L-live (AG-B3) |
| E31-S5 | citations clickable → opens page (P1, R3-7) | ⬜ | deferred by PRD |

## E32 — Acceptance & regression ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E32-S1 | AG-B1..B4 Playwright gates | ✅ | L-live (screenshots ui/11-*.png) |
| E32-S2 | AG-B5 unit gate | ✅ | L-unit |
| E32-S3 | AG-B6 regression (ask flow, 72 tests, ag8) | ✅ | L-live |
