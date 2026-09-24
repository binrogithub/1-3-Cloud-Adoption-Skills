# PRD V5 — Upload raw documents from the page; wiki refreshes automatically

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_UPLOAD_V5.md` · V5.0 · 2026-09-24 |
| Builds on | V3 (sources page) + V4 (three-page UI) — both delivered |
| User request | 实现原始文档可以在页面上传,上传后自动刷新 wiki |

## 1. Summary

The 原始文档 page gains an **upload area**: pick a file (MD/TXT/HTML/PDF/CSV/JSON/YAML),
choose kind + licence, upload. The glue ingests it as an immutable L1 snapshot, runs
the **real compile** (role → mechanical validation), and — when the change set is
provably safe — **applies it immediately**, so the Wiki page shows the new pages on
the next visit. Unsafe change sets stay in the human review queue with a visible
explanation; nothing bypasses the change-set write path (PRD V1 D-5).

## 2. The auto-apply decision (amendment to FR-C4, made explicit)

The wiki's only write path remains the approved change set. V5 adds a scoped
auto-apply policy for the upload flow, on by default, with all of:

1. source licence = `public`;
2. change set `pending`, **zero** validation problems, **zero** conflicts;
3. none of its pages touch a **protected** namespace (`pricing/`, `compliance/`,
   `availability/`).

Anything else (internal/confidential licence, protected namespace, conflicts,
validation problems) stays `pending` for a curator — exactly as today. Every
auto-application is recorded in the change-set history and the audit log with the
actor `upload-autoflow`, so the shortcut is fully traceable. Curators can turn the
policy off with one config flag (`[review] auto_apply_uploads = false`).

## 3. Requirements

### Data plane (glue)
- **R5-1 (P0)** `POST /upload` accepts `multipart/form-data` with `file` (≤ 10 MiB,
  extension allow-list as ingest), `kind` (doc|price|quota|note), `licence`
  (public|internal|confidential), optional `lang`, `owner`. Contributor role
  required. The original bytes are stored under `runtime/uploads/` (sanitised
  basename) and ingested as an L1 snapshot whose `ref` points at that file.
- **R5-2 (P0)** The upload flow compiles the snapshot through the real pipeline and
  applies per §2. Response: `{source: meta, changeset: {id, status, pages,
  applied: [slugs]}, auto_applied: bool}`.
- **R5-3 (P0)** Rejections are explicit: empty/oversized/unsupported file, parser
  self-check failure (GL-C2), role failure — each a 4xx with a readable message;
  nothing is half-ingested.
- **R5-4 (P0)** Page-list and term caches invalidate on every application (already
  the V3 behaviour) so the Wiki page reads fresh without a server restart.

### UI (原始文档 page)
- **R5-5 (P0)** Upload area above the roster: file picker, kind/licence selects,
  upload button; disabled while working; live status line (uploading → compiling
  (30–90 s, model) → applying / awaiting review).
- **R5-6 (P0)** Result banner: on auto-apply, the applied page slugs as chips
  linking to `/llmwiki/wiki?slug=…`; otherwise a pending-review notice with the
  change-set id; the sources roster refreshes in place.
- **R5-7 (P1)** Drag-and-drop onto the roster. Deferred.

### Studio api
- **R5-8 (P0)** `POST /api/llmwiki/upload` streams the multipart body to the glue
  with the server-side token; studio session required.

## 4. Acceptance gates

| Gate | Method | Bar |
|---|---|---|
| AG-P1 | Unit: upload endpoint with a crafted multipart body (fake model) | public doc → auto_applied, page in store; pricing doc → pending |
| AG-P2 | Unit: rejections (empty, bad type, >size) | 4xx, nothing ingested |
| AG-P3 | Playwright live: upload through the UI on 247 | banner lists applied pages; sources roster +1; Wiki page shows the new page |
| AG-P4 | Regression: 72→N tests green, ask flow intact | green |

## 5. Risks

| # | Risk | Mitigation |
|---|---|---|
| RK-P1 | Auto-apply weakens human review | scoped to public + non-protected + clean validation (§2); actor recorded; one-flag off switch |
| RK-P2 | Malicious upload (huge/polyglot files) | size cap, extension allow-list, GL-C2 self-check, licence choice visible |
| RK-P3 | Compile latency in the UI | explicit live status with elapsed; the model call is the same one a curator would trigger later |
