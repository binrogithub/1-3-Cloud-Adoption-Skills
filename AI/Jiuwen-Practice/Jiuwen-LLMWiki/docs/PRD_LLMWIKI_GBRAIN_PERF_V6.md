# PRD V6 — gbrain retrieval performance: persistent MCP transport

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_GBRAIN_PERF_V6.md` · V6.0 · 2026-09-24 |
| User request | 搜索 gbrain 最佳实践,提升 jiuwenswarm(glue)调用 gbrain 检索性能;输出 PRD 后实施 |
| Baseline measured | CLI per-call ≈ 0.5–0.7 s regardless of operation (bench 2026-09-24: list 0.52, search 0.59, query 0.62, get 0.57) — the cost is process cold-start, not retrieval |
| Best practice found | gbrain's own recommended pattern for local agents is a **persistent `gbrain serve`** (stdio MCP); MCP tool catalog maps 1:1 to our ops: `search` (cheap hybrid, no LLM expansion) / `get_page` / `put_page` / `list_pages` |
| Probe measured | handshake 0.34 s once; **search 0.16 s; get_page 0.02 s** via stdio MCP on the live brain |

## 1. Summary

Every glue→gbrain operation today spawns a fresh `gbrain` CLI process (~0.55 s of
bun+DB-pool cold start). V6 adds a **persistent MCP stdio transport**: the glue web
process keeps one `gbrain serve` child alive and speaks JSON-RPC to it, cutting
per-operation overhead ~10–25×. The CLI path stays as the fallback backend; nothing
about retrieval semantics, mirroring, or the write path changes.

## 2. Requirements

- **R6-1 (P0)** `llmwiki/gbrain_client.py`: a thread-safe MCP stdio client —
  spawns `gbrain serve` with the brain env, performs the `initialize` handshake
  once, multiplexes `tools/call` (search / get_page / put_page / list_pages) with
  matching JSON-RPC ids, auto-respawns a dead child, and never lets a UI callback
  kill the process.
- **R6-2 (P0)** `GBrainStore` gains `backend = "gbrain-mcp"`: search + slugs-list +
  put go over MCP; page READS come from the local mirror first (the glue is the
  sole writer, so the mirror is always current and reads cost ~0), falling back to
  MCP `get_page` only for pages that exist solely in gbrain. Writes still mirror
  (D-6) and still `--force`-free via `put_page`. `backend = "gbrain"` (CLI) remains
  the default and unchanged.
- **R6-3 (P0)** Process lifetime: the serve child belongs to the web process; a
  dead child is respawned lazily on the next call; a spawn failure falls back to
  one CLI attempt and reports `StoreError` like today.
- **R6-4 (P0)** Budget: the retrieval leg of one ask (hybrid search + evidence for
  top-6 pages) SHALL drop from ≈1.8–2.2 s (CLI, parallel gets) to ≤0.5 s (MCP);
  `eval/gbrain_bench.py` prints both paths side by side against the live brain.
- **R6-5 (P1)** `put_page` over MCP preserves mirror + audit semantics; auto-link
  extraction differences (remote writes don't extract edges inline) are acceptable —
  LLMWiki sets links explicitly in page markdown.

## 3. Acceptance gates

| Gate | Method | Bar |
|---|---|---|
| AG-M1 | `eval/gbrain_bench.py` live | MCP path ≥3× faster than CLI path on the retrieval leg |
| AG-M2 | Unit: fake MCP server (replaying the probed shapes) | search/get/put/list round-trips parse; dead-child respawn works |
| AG-M3 | Live ask after switching the runtime config to `gbrain-mcp` | grounded answer, citations unchanged vs CLI backend |
| AG-M4 | Regression: full suite (78 + new) green; ag0 canary PASS | green |

## 4. Risks

| # | Risk | Mitigation |
|---|---|---|
| RK-M1 | Protocol drift on gbrain upgrade | shapes pinned by unit fakes from the live probe; AG-M3 canary re-run on upgrade (RK-2 discipline) |
| RK-M2 | Long-lived child leaks/locks | single-writer lock around request/response; lazy respawn; child dies with the web process (no orphan: stderr devnull, terminate on atexit) |
| RK-M3 | Read-from-mirror staleness vs manual gbrain writes | E4-S5 union list unchanged — brain-only pages still fetched via MCP `get_page` |
