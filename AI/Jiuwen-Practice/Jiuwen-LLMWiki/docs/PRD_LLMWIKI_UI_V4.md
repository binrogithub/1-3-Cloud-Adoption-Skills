# PRD V4 — LLMWiki UI redesign: designer-led layout, one page per concern

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_UI_V4.md` · V4.0 · 2026-09-24 |
| Builds on | V2 (streaming ask in studio) + V3 (sidebar) — both delivered |
| User request | 调用 designer 优化页面排版;wiki 单独成页、左侧点击看详情;原始文档单独成页;提问框放到合理位置;选模版;先 PRD、再 EPIC、后实施 |
| AI-DLC task | `llmwiki-ui-v4` (studio repo, planned route, design pass D0/D1 executed) |
| Design system | `design/tokens.css` (studio's real palette: light neutral + indigo accent, AA contrast) |

## 1. Summary

V2/V3 crammed everything into one page (ask + sidebar + detail views) with ad-hoc
layout and off-system colors. V4 splits the surface into **three focused pages** —
Ask, Wiki, 原始文档 — under a shared tab navigation, all built strictly on the
studio's design tokens as selected and specified by the AI-DLC design pass
(D0 template: `chat-history-s3` token base; D1: `design/tokens.css` +
`components.md` conversation/roster component language).

## 2. Information architecture (the user's three asks)

| Route | Page | Layout | The ask it answers |
|---|---|---|---|
| `/llmwiki` | **Ask** | Centered conversation column (max 768px): page header + tab nav on top, composer (input + lang + Ask) as the primary control, answer stack below (live strip → thinking → provisional → verified) | "提问对话框放到合理的位置" — the dialog IS the page, properly centered, not squeezed beside a sidebar |
| `/llmwiki/wiki` | **Wiki browse** | Master-detail: left roster (namespace groups, counts, filter, active highlight, ~300px) · right detail (title, meta line, compiled truth rendered, timeline) | "wiki 单独做成页面,左边点击可以查看详细内容" |
| `/llmwiki/sources` | **原始文档** | Master-detail: left roster (ref, kind · licence · date) · right detail (metadata chips, raw text in a monospace block) | "原始文档做成一个单独页面" |

Shared: `LlmWikiNav` tab bar (Ask · Wiki · 原始文档) with the active tab accented;
citation chips in answers deep-link to `/llmwiki/wiki?slug=…`; glue status in the
header. All V2 streaming behavior (thinking/provisional/final, live strip) and V3
data (pages/sources/filter) carry over unchanged.

## 3. Design requirements (D2 must conform — enforced by D3 checks)

- **R4-1 (P0)** Every color/size/spacing comes from `design/tokens.css` (i.e. the
  studio Tailwind token classes). No raw palette classes (the V2/V3 amber/emerald/
  violet pills are replaced by token-derived status styling: accent family for
  good, danger family for errors, neutral for abstain).
- **R4-2 (P0)** Status pill semantics: `grounded`/`no_claims` → accent-soft on
  accent; `partially_verified` → danger-soft on danger (redaction happened);
  `abstained` → neutral; `error` → danger solid. One family per meaning.
- **R4-3 (P0)** Composer is the visual anchor of the Ask page: full-width input,
  40px control height, language selector inline, primary accent button; disabled
  state token-correct.
- **R4-4 (P0)** Rosters (wiki/sources lists) follow the components.md roster
  language: 40px rows, truncate with ellipsis, hover = surface-hover, active =
  accent-soft + accent text, group headers uppercase 11px subtle.
- **R4-5 (P0)** Detail panes are `surface` cards on `bg` with the studio's radius
  and border tokens; meta lines in `fg-subtle` 12px monospace where slugs/ids.
- **R4-6 (P1)** Responsive: 375px (nav collapses to row, master-detail stacks),
  768px+, 1440px (centered column). No horizontal scroll.
- **R4-7 (P0)** No placeholders (lorem/TODO/FIXME) — D3 fails them.

## 4. Acceptance gates

| Gate | Method | Bar |
|---|---|---|
| AG-U1 | Playwright: three routes render with the spec'd compositions | tabs navigate; wiki left-click loads right detail; sources likewise |
| AG-U2 | D3 mechanical verify (`plan.py design` verify stage) | `design_verified` (tokens_used, components_conform, no_placeholder, artifacts exist, tokens_json valid) |
| AG-U3 | Playwright: token purity spot-check | computed colors of pill/button/active-row resolve to token values |
| AG-U4 | Regression: streaming ask still works end to end on the new Ask page | ack→thinking→provisional→final; 72 glue tests green |
| AG-U5 | openjiuwen strict validation of the change spec | spec_valid |

## 5. Risks

| # | Risk | Mitigation |
|---|---|---|
| RK-U1 | D1 page spec drifted (designed Login/Register, not LLMWiki pages) | main session extends `pages.md` with the three page specs in the same format/token language before D2 (recorded in the file header); tokens/components artifacts are correct and are the binding system |
| RK-U2 | Deep-link from answer citations changes navigation shape | tabs read query params; back/forward works |
| RK-U3 | Container rebuild cycle | batch all page changes into one build |
