# EPIC Breakdown — LLMWiki UI V4 (designer-led redesign)

Source PRD: `docs/PRD_LLMWIKI_UI_V4.md` · V4.0 · 2026-09-24 · AI-DLC task `llmwiki-ui-v4`.

| Epic | Title | Status | Stories ✅/🟡/⬜ |
|---|---|---|---|
| E40 | Design pass (D0/D1) + page-spec extension | ✅ | 3 / 0 / 0 |
| E41 | Three-page build (D2) | ✅ | 6 / 0 / 0 |
| E42 | Acceptance & gates | ✅ | 4 / 0 / 0 |

## E40 — Design pass ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E40-S1 | D0 template selection from the index | ✅ | state.json `chat-history-s3` token base (studio palette, AA) |
| E40-S2 | D1 artifacts (tokens.css/json, components.md, pages.md, assets.md) | ✅ | `design/` five files present |
| E40-S3 | pages.md extended with the three LLMWiki page specs in the same format (D1 drifted to Login/Register — recorded RK-U1) | ✅ | pages.md §LLMWiki V4 |

## E41 — Build (D2) ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E41-S1 | Shared `LlmWikiNav` tab bar (Ask · Wiki · 原始文档), active accented, deep-link aware | ✅ | L-live (AG-U1) |
| E41-S2 | Ask page: centered conversation column, composer as anchor (R4-3), streaming stack carried over | ✅ | L-live (AG-U4) |
| E41-S3 | Wiki page: master-detail roster → detail (markdown, meta, timeline) | ✅ | L-live (AG-U1) |
| E41-S4 | 原始文档 page: master-detail roster → metadata + raw text | ✅ | L-live (AG-U1) |
| E41-S5 | Token purity: status pills/composer/rows all token-derived (R4-1/R4-2) | ✅ | L-live (AG-U3) |
| E41-S6 | Citation chips deep-link to `/llmwiki/wiki?slug=` | ✅ | L-live (AG-U1) |

## E42 — Acceptance ✅

| ID | Story | Status | Verification |
|---|---|---|---|
| E42-S1 | AG-U1 three routes + master-detail interaction | ✅ | L-live |
| E42-S2 | AG-U2 D3 mechanical verify | ✅ | design_verified |
| E42-S3 | AG-U3 computed-color token purity | ✅ | L-live |
| E42-S4 | AG-U4/U5 regression (streaming E2E + 72 tests + strict spec) | ✅ | L-live + L-unit |
