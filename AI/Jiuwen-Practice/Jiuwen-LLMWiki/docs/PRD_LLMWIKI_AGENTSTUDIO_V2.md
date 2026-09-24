# PRD V2 — LLMWiki in Agent Studio: streaming answers with visible thinking

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_AGENTSTUDIO_V2.md` |
| Version | V2.0 (2026-09-24) |
| Status | Draft for review; supersedes the *frontend* parts of PRD V1 §8.7/GL-A7 only |
| Repos | glue: `/root/HuaweiCloudLatam_LLMWiki` · studio: `/mnt/Latam_AI_Workbench` |
| Baseline | PRD V1 implemented (EPICS V1.1): 6/6 gates PASS, web :20080 SSE (ack→retrieval→final) |
| User request | 前端改用 OpenJiuwen 的 Agent Studio 开发；流式输出；显示模型思考内容 |

## 1. Summary

LLMWiki today answers in one shot: the glue waits for the role, verifies every claim,
then serves the final text. On the box, **Agent Studio** (`/mnt/Latam_AI_Workbench`,
Next.js + FastAPI + Caddy :8444) is the team's existing workspace with sessions,
auth and a bot-execution pattern (MVP-S2). V2 moves the LLMWiki experience into
Agent Studio and makes the ask **stream**: the user watches the model's thinking
tokens live, sees progress events, gets the role's raw answer the moment it lands
(clearly marked *unverified*), and the display transitions to the verified answer
when the claim checker finishes.

Measured facts this PRD builds on (2026-09-24, dedicated instance, deepseek-v4.1-flash):
the CLI event stream carries `chat.reasoning` (token-by-token thinking, 113 events in
a sample run), `chat.delta`, `chat.tool_call` / `chat.tool_update` / `chat.tool_result`,
`chat.usage_metadata`, `chat.final`. The role's answer arrives as one complete
`chat.tool_result`; per-token answer streaming therefore applies to thinking and to
the main agent's wrapper text, while the role answer appears atomically.

## 2. Problem, goals, non-goals

### Problems
- P1 60–90 s of dead air between click and answer; users cannot tell progress from failure.
- P2 The wiki's own UI (:20080) is a maintenance surface, not the workspace SAs live in.
- P3 Thinking is discarded; for a trust-critical tool, showing *how* the role reasons
  over the evidence pack is itself trust UX.

### Goals
- **G1 Studio-native**: LLMWiki lives inside Agent Studio behind its login; no second
  surface to remember for the ask flow.
- **G2 Live**: thinking tokens and pipeline progress stream in real time; no silent
  waits anywhere in the UX.
- **G3 Trust intact**: the *verified* answer remains the only authoritative text;
  provisional display is visually and semantically distinct and always resolved by a
  final verdict; thinking is progress, never evidence.
- **G4 Zero regression**: all V1 gates keep passing; the streaming path reuses the
  same verification, audit and RBAC code (no parallel truth pipeline).

### Non-goals
- Streaming the wiki *review* queue into the studio (stays on the glue UI for V2).
- Changing the role, the verifier's semantics, or the dedicated instance config.
- Multi-agent/team features; voice; i18n beyond EN/ES/PT answers.

## 3. Users and use cases

| Persona | UC |
|---|---|
| SA (studio user) | **UC-A1** ask in EN/ES/PT inside the studio, watch thinking, read the cited verified answer |
| Curator | **UC-A2** same ask flow; issues list shows exactly which claims were redacted and why |
| Platform admin | **UC-A3** studio routes to the glue on the host; health of both visible |

## 4. Architecture

```
 Agent Studio web (:8444 TLS via Caddy, Next.js)            glue (host, :20080)
 ┌──────────────────────────────┐   SSE proxy    ┌───────────────────────────────┐
 │ /llmwiki page                │ ─────────────► │ POST /ask  (SSE v2)           │
 │  thinking panel (live)       │  EventSource   │  thinking│progress│provisional │
 │  answer area (2-state)       │                │  final(verified)│ping│error   │
 └──────────────┬───────────────┘                │  + /health /pages …            │
                │ same-origin /api               └───────────────┬───────────────┘
 ┌──────────────▼───────────────┐                                 │ subprocess
 │ studio api (:8000, FastAPI)  │                                 ▼
 │  GET /api/llmwiki/ask (SSE)  │                    jiuwenswarm chat --jsonl
 │  LLMWIKI_GLUE_URL + token    │                    (dedicated instance :20001,
 └──────────────────────────────┘                     deepseek-v4.1-flash, code mode)
```

The existing jiuwen-bridge (:8090) is **not** used for LLMWiki: it targets the shared
instance's home and the workbench repo cwd; LLMWiki must keep its dedicated data dir
and its verification layer in the path (PRD V1 D-1/D-7).

## 5. Requirements

Priority P0 = this delivery; P1 = next.

### 5.1 Glue streaming protocol (SSE v2) — P0
- **R2-1** `POST /ask` emits, in order: `ack{question,lang,conversation_id}` →
  `retrieval{slugs,stale,filtered_confidential}` → zero or more
  `thinking{delta}` (verbatim `chat.reasoning` fragments, forwarded as they arrive) →
  zero or more `progress{stage,detail}` (dispatch, tool names, elapsed) →
  optional `provisional{text}` exactly once, the moment the role's `tool_result`
  lands (raw, unverified) → `final{answer,status,citations,stale,issues,elapsed_s}`
  or `error{error}`; `ping{elapsed_s}` at ≥10 s idle. Connection closes after
  terminal event.
- **R2-2** GL-A7 is amended for the display layer: unverified role output may be
  streamed as *provisional* UI state only. `final` remains the only authoritative
  text and always follows (or the stream errors). Provisional text is discarded, not
  archived: the ask log stores only the verified outcome (unchanged, GL-A9).
- **R2-3** Thinking deltas are never logged, never verified, never cited; the UI
  renders them in a collapsed-by-default "thinking" panel with a live token count.
- **R2-4** Event granularity: one SSE event per reasoning burst as emitted by the
  CLI; no client-side stitching required. Backpressure-safe: the glue may coalesce
  bursts that arrive within one scheduler tick.
- **R2-5** The CLI client (`jiuwen.run`) grows a streaming mode (`on_event`
  callback, line-at-a-time); the non-streaming behaviour and its exit-code mapping
  are unchanged. `RunResult` gains `reasoning: str`.

### 5.2 Studio integration — P0
- **R2-6** New page `/llmwiki` (App Router, client component, studio design tokens)
  with: question box + language selector (auto/EN/ES/PT), live thinking panel,
  two-state answer area (provisional → verified with status pill, citations,
  stale warnings, redacted-claim list), and an elapsed timer.
- **R2-7** Studio api route `GET/POST /api/llmwiki/ask` proxies the glue SSE
  verbatim (`LLMWIKI_GLUE_URL`, default `http://172.17.0.1:20080`) and attaches the
  glue token from `LLMWIKI_GLUE_TOKEN` (server-side only). Studio auth required.
- **R2-8** A `GET /api/llmwiki/health` passthrough lets the studio surface glue
  health (version, git SHA, gateway state) on the page header.
- **R2-9** Provisional rendering is visually distinct (muted, "verifying…" badge);
  on `final` it is replaced atomically. On `error` the provisional text is removed.

### 5.3 Compatibility & ops — P0
- **R2-10** The V1 minimal UI on :20080 keeps working (`/ask.json`, old page) — it
  simply ignores the new events. `eval/gates.py` is unaffected.
- **R2-11** The studio api container reaches the host glue via the docker bridge;
  the URL is config, never hard-coded to a network the ops team may change.
- **R2-12** No changes to JiuwenSwarm, the shared instance, or the bridge service.

## 6. Acceptance gates (V2)

| Gate | Method | Pass bar |
|---|---|---|
| **AG-S1 Stream honesty** | SSE capture of one live ask | `thinking` events arrive before `provisional`; `provisional` precedes `final`; `final.status` consistent with the ask log |
| **AG-S2 Trust intact** | Same capture + unit | provisional text ≠ final text when a claim is redacted; no_citations ask yields `final.answer` starting NOT_IN_WIKI, provisional discarded |
| **AG-S3 Studio path** | curl through studio api (auth) | SSE bytes identical in event order to the direct-glue capture (modulo ping) |
| **AG-S4 V1 regression** | Full unit suite + ag0/ag2/ag5/ag8 re-run | all green on the streaming code path |
| **AG-S5 Liveness** | Long ask via studio | ≥1 ping per 10 s idle gap; UI timer runs |

## 7. Risks

| # | Risk | Mitigation |
|---|---|---|
| RK-S1 | Thinking may echo source text incl. confidential page bodies | thinking is display-only, never stored (R2-3); confidential pages never enter the pack (GL-S2) so they cannot be echoed |
| RK-S2 | Studio rebuild disturbs neighbours | web container rebuild only; api change is additive; caddy untouched |
| RK-S3 | Model switch changes event shapes (RK-2 family) | event parsing stays in one module; AG-S4 canary re-run on every model change |
| RK-S4 | SSE through two proxies (caddy→api→glue) buffers | api proxy uses `StreamingResponse` with no compression on that route; AG-S3 catches it |

## 8. Milestones

| Milestone | Scope | Exit |
|---|---|---|
| M1 (this delivery) | Glue SSE v2 + streaming client + studio page + api proxy + gates AG-S1..S5 | all gates green, committed in both repos |
| M2 | Review-queue embedding, conversation history in studio, ES/PT UI chrome | PRD V3 |
