# PRD V11 — ChatGPT-style conversation layout for the Ask page

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_CHAT_UI_V11.md` · V11.0 · 2026-09-24 |
| Builds on | V4 (centered composer) + V8 (multi-turn threads) — both delivered |
| User request | 学习 ChatGPT 的多轮对话格式,对话后输入框在下面;搜索业界模拟 ChatGPT 对话的开源前端项目,复用代码,优化当前页面,不破坏已有功能 |

## 0. Survey (what the industry does, what we reuse)

| Project | License | Reused here |
|---|---|---|
| **ChatGPT-Next-Web (NextChat)** | MIT | **Code**: textarea auto-grow approach, IME-safe Enter-to-send (composition events + isComposing), smart scroll-to-bottom with detach-when-scrolled-up — copied/adapted with attribution (`apps/web/ATTRIBUTIONS.md`) |
| **LobeChat** (lobehub) | MIT (core) | **Pattern only**: bottom-pinned composer, user bubble right / assistant full-width, message list scroll area |
| chatbot-ui (McKay Wrigley) | MIT | Pattern reference only (no code) |

Today's Ask page anchors the composer at the **top** once a conversation starts
(V4 "composer as anchor"); ChatGPT/LobeChat/NextChat all put the **input at the
bottom** with messages scrolling above — the muscle memory users expect.

## 1. Requirements

### Layout
- **R11-1 (P0)** Active conversation = message list (scroll area) on top,
  **composer pinned at the bottom**; idle hero (centered) unchanged.
- **R11-2 (P0)** User turns render as right-aligned bubbles; assistant answers
  keep the existing verified-card look (status pill, citations, redactions).
- **R11-3 (P0)** The live turn shows the current user bubble + the existing
  streaming states (live strip / thinking / provisional) above the composer.

### Composer
- **R11-4 (P0)** Auto-growing textarea (1–~5 rows, capped), Enter sends /
  Shift+Enter newline, **IME-safe** (Chinese/Japanese composition never
  mis-fires send) — adapted from NextChat with attribution.
- **R11-5 (P0)** Language select + Ask button + all existing `data-testid`s
  (`ask-input`, `ask-button`, `turn-*`, `new-conversation`, …) unchanged, so no
  existing E2E breaks.

### Scrolling
- **R11-6 (P0)** Smart auto-scroll (NextChat pattern): follow the stream while
  the user is pinned to the bottom; detach when they scroll up; jump to bottom
  when a new turn starts.

### Non-goals / invariants
- **R11-7 (P0)** No behavioral change: SSE v2 protocol, conversation_id
  round-trip, restore-on-reload, 新会话, examples, multi-turn grounding — all
  byte-identical logic; this PRD is layout + input ergonomics only.
- License hygiene: copied fragments carry in-code attribution; the NextChat MIT
  license text is preserved in `apps/web/ATTRIBUTIONS.md`.

## 2. EPIC breakdown

- **EPIC-CU1 — Composer**: bottom pin, auto-grow, IME-safe Enter (R11-1/4).
- **EPIC-CU2 — Thread**: user bubbles, assistant cards, live-turn section,
  smart scroll (R11-2/3/6).
- **EPIC-CU3 — Gates & E2E**: Playwright regression — 2-turn conversation with
  pronoun follow-up, composer visible at bottom while streaming, restore,
  新会话, all prior testids still work.

## 3. Acceptance gates

- **GL-CU1** during streaming the composer is visible at the viewport bottom
  (bounding-box check) — no manual scroll needed to type.
- **GL-CU2** Enter sends, Shift+Enter inserts a newline; a composing IME Enter
  does not send (synthetic composition events).
- **GL-CU3** full V8 regression green (multi-turn, restore, 新会话) on the new
  layout; suite untouched and green.

## 4. Evidence

`docs/evidence/live-2026-09-24/ui/46-chatui-*.png`, Playwright transcript,
`apps/web/ATTRIBUTIONS.md`.
