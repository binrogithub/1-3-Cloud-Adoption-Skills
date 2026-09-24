# PRD V3 — LLMWiki sidebar: browse the wiki and the raw L1 sources

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_SIDEBAR_V3.md` · V3.0 · 2026-09-24 |
| Builds on | PRD V2 (Agent Studio page, streaming, thinking) — delivered |
| User request | 前端页面加一个左侧边栏,用于显示 LLMWiki、原始文档;查找开源 LLMwiki 类似项目的前端,复用该代码 |
| Repos | glue `/root/HuaweiCloudLatam_LLMWiki` · studio `/mnt/Latam_AI_Workbench` |

## 1. Summary

The `/llmwiki` page today is ask-only: users cannot see what the wiki knows or where
its facts came from. V3 adds a **left sidebar** with two sections — **Wiki**(L2 pages,
grouped by namespace) and **原始文档 / Sources**(L1 immutable snapshots) — and read-only
detail views in the main area. Clicking a wiki page shows its compiled truth (rendered
markdown, same renderer as answers); clicking a source shows its metadata and raw text.
This turns the trust story visible: every cited fact is two clicks from its evidence.

## 2. Open-source reuse decision (the user asked for it)

| Project | License | Verdict |
|---|---|---|
| [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) ★20k — the Karpathy-style LLM Wiki desktop app (TS/React) | **GPL-3.0** | **UX blueprint only, zero code copied** — GPL would contaminate the studio app. Its layout concept (left nav over pages+sources, filter on top) informs ours. |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) (React+Tailwind) | **MIT** | **Code reused**: the `Sidebar/SearchBox` interaction (debounced filter, reset-on-select event, magnifier affordance) is lifted and adapted; attribution kept in the component header. |
| chaitin/PandaWiki (AGPL-3.0), inkeep/open-knowledge (GPL-3.0), Tencent/WeKnora (custom) | — | rejected for code reuse (license) |

Net: interaction patterns from the GPL reference, working code from the MIT one,
both re-expressed in the studio's design tokens (surface/hover/subtle/accent).

## 3. Requirements

Priority P0 = this delivery.

### Data plane (glue + studio api)
- **R3-1 (P0)** glue `GET /source?id=<16-hex>` returns `{meta, text}` — the L1
  snapshot record plus its extracted text. Unknown id → 404. (List endpoint `/sources`
  already exists; `/pages?slug=` already exists.)
- **R3-2 (P0)** studio api proxies `GET /api/llmwiki/pages`, `GET /api/llmwiki/sources`,
  `GET /api/llmwiki/source?id=` to the glue with the server-side glue token; studio
  session required (existing pattern).
- **R3-3 (P0)** confidential sources keep their licence visible in the list; the raw
  text of a `confidential` source is only proxied for curator-or-above glue tokens
  (the studio proxy token is contributor: it lists, and the glue enforces).

### Sidebar UI
- **R3-4 (P0)** Two-pane layout: fixed ~280px left sidebar (collapsible to a rail)
  + main area. The ask flow keeps working unchanged in the main area.
- **R3-5 (P0)** Sidebar sections:
  - filter box on top (AnythingLLM pattern: ~300 ms debounce, filters both sections,
    clear on selection);
  - **Wiki**: pages grouped by namespace with per-group counts, groups collapsible,
    active page highlighted;
  - **原始文档**: sources as rows (ref basename, kind, licence chip, date), filtered
    by the same box.
- **R3-6 (P0)** Main-area views: wiki page detail (title, meta line
  `last_verified · sources · stale badge`, compiled truth + timeline via the markdown
  renderer) and source detail (metadata table, licence chip, raw text preview).
- **R3-7 (P1)** Linking: citations in answers (`services/obs`) become clickable to
  open that page in the sidebar view. Deferred to keep V3 shippable.

### Non-goals
Editing pages/sources from the studio (change-set review stays on the glue UI);
uploading sources; sidebar drag-resize.

## 4. Acceptance gates

| Gate | Method | Bar |
|---|---|---|
| AG-B1 | Playwright: sidebar renders both sections with real counts | groups = namespaces present; sources ≥ 3 |
| AG-B2 | Playwright: click a wiki page | detail shows rendered markdown + meta line |
| AG-B3 | Playwright: click a source | metadata + raw text visible |
| AG-B4 | Playwright: filter box narrows both lists; clear restores | typed filter reduces rows; select resets |
| AG-B5 | Unit: glue `/source` detail (known + unknown id) | 200 with text; 404 unknown |
| AG-B6 | Regression: ask flow + 72-test suite + ag8 | unchanged, green |

## 5. Risks

| # | Risk | Mitigation |
|---|---|---|
| RK-B1 | License contamination via "reuse" | GPL project = patterns only; MIT code carries attribution; recorded in §2 |
| RK-B2 | Sidebar data grows (5k pages) | V3 loads list metadata only; paging deferred (P2), filter is client-side over slugs |
| RK-B3 | Confidential text exposure | glue enforces role on source text (R3-3); studio token is contributor |
