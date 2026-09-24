# PRD V12 — Conversation history sidebar

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_CONV_HISTORY_V12.md` · V12.0 · 2026-09-25 |
| Builds on | V8 (multi-turn threads) + V11 (ChatGPT layout) — delivered |
| User request | 增加历史记录,在左侧展示,输出 PRD,然后实施 |

## 1. Summary

The Ask page gains a **left sidebar listing past conversations** (ChatGPT-style):
title (first question snippet), turn count, last-activity time; click to reopen
the thread; per-item delete; the current conversation is highlighted; 新会话 stays.
Conversations already live server-side (`runtime/conversations/`) — this PRD adds
the missing list/delete endpoints and the UI.

## 2. Requirements

### Glue (data plane)
- **R12-1 (P0)** `GET /conversations` — the requesting identity's threads (own +
  anonymous-owned, matching the open-guard), newest-activity first, ≤ 50:
  `{conversations: [{id, title, turns, created_at, last_at}]}` where `title` is
  the first question truncated to 48 chars.
- **R12-2 (P0)** `DELETE /conversations/{id}` — same ownership guard; removes the
  thread file; 404 when unknown.
- **R12-3 (P1)** No changes to thread storage or the ask flow (V8/V11 semantics
  untouched); list is read-only over existing files.

### UI (Ask page)
- **R12-4 (P0)** Left sidebar (md+; hidden on narrow screens): 新会话 on top,
  history items below — title, turn count, relative time; active conversation
  highlighted; click reopens the thread at the bottom (V11 scroll behavior).
- **R12-5 (P0)** Per-item ✕ delete (confirm); deleting the open thread starts a
  fresh session.
- **R12-6 (P0)** The list refreshes when a NEW conversation gets its first turn
  (on final), and after deletes; reopening a thread updates localStorage so
  reload restores that thread.

## 3. EPIC breakdown

- **EPIC-H1 — Glue list/delete** (R12-1..R12-3): endpoints + HTTP tests.
- **EPIC-H2 — Sidebar UI + proxy** (R12-4..R12-6): sidebar component, switching,
  delete, refresh triggers; studio proxy routes.
- **EPIC-H3 — Gates & E2E**: Playwright — history lists past threads, switch,
  delete, new-ask appears, reload restores the chosen thread.

## 4. Acceptance gates

- **GL-H1** two-turn conversation appears with title/turns/last_at; owner guard
  filters other users' threads (unit).
- **GL-H2** delete removes the thread (detail 404 afterwards) (unit).
- **GL-H3** Playwright: sidebar shows prior conversations; click switches the
  rendered thread; ✕ deletes; a fresh ask lands in the list; reload restores the
  selected thread; V8/V11 regressions green.
