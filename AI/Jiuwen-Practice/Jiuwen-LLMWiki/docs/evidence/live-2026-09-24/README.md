# Live verification evidence — 2026-09-24 (host 247, AI-DLC task epic-impl-v1)

All runs used the dedicated instance (:20001, code mode, role `llmwiki`, glm-5.2 via
MaaS), gbrain 0.53 on llmwiki_pg, TEI e5-small embeddings, through the worktree code
(git b142d7e + fixes).

| Story | Evidence in this directory / runtime |
|---|---|
| E5-S9 multilingual asks + abstention | `golden-run.log` (AG-1 interim 8/9 + 3/3), ask log `runtime/logs/ask.jsonl` |
| E7-S9 live compile | change sets 20260923192905 (obs, pending→applied), 20260923193437 (regions, 4 pages), 20260923193950 (compliance; the first attempt 20260923193711 was correctly marked **invalid** by GR-6 because the source wrapped a term across lines — fixed the matcher, recompiled) |
| E7-S8 file-back | change set 20260923200618 → `faq/what-is-the-maximum-size-of-a-single` |
| E2-S4 zero tools | `e2s4-raw-code-mode.jsonl` — exactly one tool_call (`Agent`); the role declined the file-listing request and answered cited |
| E13 gates | `gates-run.log` (ag0/ag2/ag3/ag6), `eval/results/*.jsonl` |
| E9-S6 backup + restore | `runtime/backups/` + restore-test stdout in session log (9 pages / 18 chunks / 9 mirror files) |
| E9-S8 budget | resource_check: containers 43 MiB + instance 969 MiB + web 24 MiB ≈ 1.0 GiB (budget 4), neighbours keep 7.5 GiB |
| E11 web | `web-server.log`; authz checks: anonymous approve 403, curator token applied (audit entries in `runtime/logs/audit.jsonl`) |

Known-benign observations recorded for follow-up: gbrain injects a `<!-- timeline -->`
marker into page bodies it returns (cosmetic; parser ignores), and `gbrain list` shows
the lint-report `_meta` page (expected: `_meta/` is glue-written per SCHEMA.md).

## UI verification (2026-09-24, Playwright headless Chromium, ui/ directory)

- Live E2E (real model): thinking streaming at t+14s → amber provisional at t+32s →
  verified final at t+37s; citation chip rendered; no console errors (`ui/1..4-*.png`).
- Deterministic render test (SSE mocked with rich markdown): heading/bold/inline-code/
  table(3 rows)/list/link/[W:slug] sup chips all rendered as HTML; zero raw `**` or
  `|---|` artifacts (`ui/6-rich-markdown.png`). VERDICT: PASS.
- Note: model output is nondeterministic — one live run returned a single-sentence
  answer with nothing to render; the mock isolates rendering from model variance.

## Sidebar verification (2026-09-24, PRD V3, ui/11-13-*.png)

AG-B1..B4+B6 PASS in-browser: 5 namespace groups, 10 wiki items, 6 sources;
page detail renders markdown with 7 citation chips; source detail shows 841 chars
of raw L1 text; filter "obs" narrows 10->2 and clears on select; ask flow intact.
AG-B5 unit: /source detail (200/404/403 paths) in the 72-test suite.
Perf fix found by the gates: /pages cost one gbrain CLI call per slug (8.7 s first
hit) -> parallel fetch + 60 s cache (invalidated on approve/reject/lint-write).
Also: citation chips in answers now open the page (R3-7 delivered early).

## Upload & auto-refresh (2026-09-24, PRD V5, ui/20-21-*.png)

AG-P1/P2 unit (77-test suite): public doc auto-applies (upload-autoflow actor,
cache invalidated); pricing upload stays pending (protected); rejections
403/400/415/422 with nothing half-ingested. AG-P3 live: EVS note uploaded through
the 原始文档 page → real model compile (40 s) → auto-applied `services/evs` →
sources roster 6→7 → banner chip deep-links the new wiki page. Ops notes:
api needed python-multipart (uv.lock updated); glue restart raced a stale listener.

## Delete flow (2026-09-24 follow-up, ui/22-23-*.png)

DELETE /source?id= (contributor): uncited source removed — files dropped, its
pending change sets auto-rejected ("source deleted"), audit recorded; cited
source → 409 naming the citing pages; unknown → 404. Live roundtrip: internal
upload → pending (27 s) → deleted (rows 10→9, "已删除 <sid>"); public upload →
applied (51 s, concepts/block-storage-snapshot-retention) → delete refused with
the citing page named. 78 tests green. Bugs fixed en route: glue was serving
stale code without do_DELETE (HTML error page); api proxy needed r.json() guard.

## gbrain MCP transport (2026-09-24, PRD V6)

Best practice per gbrain docs: local agents keep one `gbrain serve` (stdio MCP)
alive. Probe: handshake 0.34s once; search 0.16s / get_page 0.02s vs CLI 0.6s
per call (cold start dominates the CLI). AG-M1 live bench (eval/gbrain_bench.py,
4 rounds, search + top-6 evidence): CLI median 3.89s vs MCP median 0.14s —
27.8x, bar >=3x PASS. Runtime switched to backend="gbrain-mcp"; ag0/ag2 canaries
PASS on the new transport; 81 tests green (fake MCP replays the probed shapes;
dead-child respawn covered — found and fixed a re-entrant-lock deadlock and
stream-death retry on the way).

## UI A/B latency (2026-09-24, Playwright, eval/ui_latency.py, 3 rounds each)

Same question through the real browser, only the store backend flipped:
- retrieval leg (click -> "evidence: N page(s)"): MCP median 0.30s vs CLI median 2.38s
  (CLI round1 9.81s = cold gbrain+pg warm-up); ~8x in-UI, consistent with the
  27.8x backend bench once UI polling granularity (250ms) and non-retrieval
  overheads are included.
- first thinking: MCP ~3.9s vs CLI ~6.2-13.4s; final: MCP 22-28s vs CLI 27-34s.
Verdict: the speedup is real and user-visible; backend restored to gbrain-mcp.

## gbrain dream mode (2026-09-24, E8-S5 propose-only, ui/24-25-*.png)

Was NOT enabled. Deployed as deploy/gbrain-dream.sh + llmwiki-gbrain-dream.timer
(03:30 nightly; lint 02:30 / backup 01:30 timers and the web unit enabled too).
Propose-only invariant: unify-types with apply=false (job #1 completed, proposal
only), by-mention link extraction (0 writes here — no entity pages), report
written to _meta/dream-report-<date> via the glue. Playwright verdict PASS:
three sentinel pages byte-identical before/after the cycle (D-5 intact), dream
report visible in the sidebar _meta group.

## Thinking off + dream authorized to write (2026-09-24, ui/26-27-*.png)

MaaS empirics: only `chat_template_kwargs.enable_thinking=false` disables
deepseek reasoning (enable_thinking / thinking.type / reasoning.* all ignored;
reasoning_effort 422s). First attempt as a top-level model kwarg broke the
OpenAI SDK (TypeError) — the working channel is `model_config_obj.extra_body`
in the dedicated instance config (and install_instance.py regen). Verified:
CLI chat 0 reasoning events, PONG correct; ag0 PASS; UI ask 20-26s (was 22-28
with thinking; the visible-thinking panel now stays empty by design).
Dream upgraded per Robin's authorization: unify-types apply:true + link
extraction write metadata; compiled-truth tripwire (sha256 of sentinel pages,
before/after, recorded in the _meta/dream-report page) = UNCHANGED. Found+fixed
en route: MCP put_page needed force:true (revision_conflict), matching the CLI
template. Playwright DREAM-APPLY VERDICT: PASS.

## Content conflict reconcile — newest wins (2026-09-24, Robin authorization, ui/29-32-*.png)

E2E: two public notes uploaded via the UI (Jan: "OBS available in LA-Santiago";
Sep 2026-09-20: "not available") -> recompiled after the synonym fix -> approved
by Robin -> lint flags the availability conflict -> dream reconcile resolves it:
loser (services/obs) now carries the winner's statement with the WINNING
STATEMENT's citation (Sep note ac7573891f0cd4bd); contradiction count 0; ask
"Is OBS available in LA-Santiago?" -> "No. ... not available in LA-Santiago
[W:services/obs]" grounded, no stale claim. Fixes found by this pass: term
SYNONYMS now ground claims/detector/holder-matching via the glossary map
(full title ~ abbreviation — three call sites), reconcile winner-citation
extraction, list-default bug, and llmwiki-web unit missing
LLMWIKI_BIND_EXTRA. 85 tests green; ag0 PASS. (Playwright string checks that
read DOM meta-lines produced two false FAILs; authoritative checks above PASS.)
