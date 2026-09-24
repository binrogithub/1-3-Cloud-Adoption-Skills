# EPIC Breakdown — gbrain retrieval performance V6

Source PRD: `docs/PRD_LLMWIKI_GBRAIN_PERF_V6.md` · V6.0 · 2026-09-24.

| Epic | Title | Status | Stories ✅/🟡/⬜ |
|---|---|---|---|
| E60 | MCP stdio client | ✅ | 3 / 0 / 0 |
| E61 | Store transport + bench | ✅ | 4 / 0 / 0 |
| E62 | Acceptance & switch-over | ✅ | 3 / 0 / 0 |

## E60 — MCP stdio client ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E60-S1 | Handshake (initialize + initialized), thread-safe tools/call with id matching | ✅ | L-unit (fake MCP) |
| E60-S2 | Lazy respawn on dead child; atexit terminate | ✅ | L-unit |
| E60-S3 | Ops: search / get_page / put_page / list_pages, parsing the probed shapes | ✅ | L-unit |

## E61 — Store transport + bench ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E61-S1 | `backend="gbrain-mcp"`: search/list/put via MCP | ✅ | L-unit + L-live |
| E61-S2 | Reads: mirror first, MCP get_page for brain-only pages (E4-S5 union intact) | ✅ | L-unit |
| E61-S3 | CLI backend untouched (default) | ✅ | 78 legacy tests green |
| E61-S4 | `eval/gbrain_bench.py` side-by-side harness | ✅ | L-live |

## E62 — Acceptance & switch-over ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E62-S1 | AG-M1 bench ≥3× on retrieval leg | ✅ | L-live |
| E62-S2 | AG-M2 unit gates (fake MCP) | ✅ | L-unit |
| E62-S3 | AG-M3/M4 live switch-over + regression | ✅ | L-live |
