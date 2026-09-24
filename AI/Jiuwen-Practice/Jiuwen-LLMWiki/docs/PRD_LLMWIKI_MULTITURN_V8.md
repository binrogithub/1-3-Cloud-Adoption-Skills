# PRD V8 — Multi-turn conversation for the LLMWiki Ask page

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_MULTITURN_V8.md` · V8.0 · 2026-09-24 |
| Builds on | V2 (SSE ask) — delivered; V7 (cascade delete) — delivered |
| User request | 查找 Agent Studio 是否有多轮会话能力;输出多轮对话能力的 PRD,分解 EPIC,并实现 |

## 0. Investigation findings (what exists today)

| Layer | Multi-turn status |
|---|---|
| Agent Studio platform (`/agents/{id}/chat`) | **Has it**: stable session id `u-{user}/{bot}` per turn pair, state kept by the JiuwenSwarm bridge |
| LLMWiki glue | **Skeleton only**: `conversation_id` accepted, turns persisted (`runtime/conversations/*.json`), retrieval widened with the last-2 questions, `GET /conversations/{id}`, owner guard |
| LLMWiki model prompt | **No**: the model never sees prior answers — it cannot resolve "它/该模型/上文" follow-ups |
| LLMWiki front-end | **No**: `conversation_id` is never sent (every ask starts a fresh conversation), no thread UI, no 新会话, no restore |

So: the platform has multi-turn machinery for bot chat, but the LLMWiki ask experience is effectively single-turn end to end.

## 1. Summary

The Ask page becomes a **conversation thread**: turns accumulate visually, the
server keeps the conversation (already half-built), follow-up questions see the
prior turns — retrieval widens **and the model prompt carries the conversation**
— while every answer stays **mechanically grounded** exactly as today: prior
turns are context, never evidence; only `[W:slug]` citations of the retrieved
evidence pack count. One click starts a 新会话.

## 2. Requirements

### Glue (data plane)
- **R8-1 (P0)** `Wiki.ask(question, …, history=[{q,a},…])`: the last **3** turns
  (answers truncated to 800 chars each) travel into the prompt as a
  `CONVERSATION SO FAR (context only, NOT evidence)` block; the QUESTION stays
  the current turn alone.
- **R8-2 (P0)** Context-aware retrieval, all mechanical: candidates =
  BM25(question + prior questions) ∪ **cited pages of the prior answers**
  (`[W:slug]` extraction, +2 slots). Confidential filtering applies to the union.
- **R8-3 (P0)** `ask.jsonl` records `conversation_id` and `turn`; audit keeps
  `conversation=` (already present).
- **R8-4 (P0)** Single-turn invariant: no history → byte-identical prompt and
  retrieval as V2 (all existing tests must stay green).
- **R8-5 (P1)** `GET /conversations/{id}` unchanged (already returns turns);
  used by the UI for restore.

### UI (Ask page)
- **R8-6 (P0)** The page keeps the `conversation_id` from the SSE `ack`,
  sends it on every subsequent ask, and persists it in `localStorage`.
- **R8-7 (P0)** Thread rendering: past turns render as Q + verified-answer
  cards; the live turn streams below them; scroll anchors to the live turn.
- **R8-8 (P0)** 「新会话」button: clears the thread and the stored id — the next
  ask starts a fresh conversation server-side.
- **R8-9 (P1)** On mount, a stored id restores the thread via
  `GET /api/llmwiki/conversation/{id}` (new studio proxy route); 404 → start fresh.

### Guardrails (unchanged by design)
- Verification, URL-domain rules, confidential filtering, abstention, SSE v2
  protocol: **identical to V2**. A follow-up that the wiki cannot ground still
  answers `not_in_wiki` — history must never lower the grounding bar.

## 3. EPIC breakdown

- **EPIC-MT1 — Glue conversation core** (R8-1..R8-4): `history` param, prompt
  block, cited-page retrieval union, log fields; unit tests: prompt contains
  prior turns, retrieval union, no-history byte-identity, follow-up fake-model
  path.
- **EPIC-MT2 — Thread UI + proxy** (R8-6..R8-9): conversation_id round-trip,
  turns stack, 新会话, restore route.
- **EPIC-MT3 — Gates & E2E**: Playwright — pronoun follow-up grounded on the
  GLM-5.3 page, thread shows 2 turns, 新会话 resets, single-turn ask unchanged.

## 4. Acceptance gates

- **GL-MT1** After "GLM-5.3 是什么?" → "它支持多长的上下文?", the second answer
  is about GLM-5.3 (mentions 1M) with status `grounded` — not `abstained`/`no_claims`.
- **GL-MT2** `ask.jsonl` rows carry the same `conversation_id` with increasing
  `turn`.
- **GL-MT3** All pre-V8 tests green (single-turn invariant).
- **GL-MT4** Playwright: thread UI + 新会话 + restore; screenshots as evidence.

## 5. Evidence

`docs/evidence/live-2026-09-24/ui/42-mt-*.png`, unit tests in
`tests/test_extensions.py::MultiTurnTests`, full suite re-run.
