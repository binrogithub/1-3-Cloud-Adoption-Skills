# PRD V10 — Recompile a source document into wiki (no re-upload)

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_RECOMPILE_V10.md` · V10.0 · 2026-09-24 |
| Builds on | V5 (upload autoflow) — delivered; V9 (web edit) — delivered |
| User request | 实现把原始文档重新编译成 wiki 的功能,输出 PRD,之后再实现 |

## 1. Summary

The 原始文档 page gains a per-source **🔄 重新编译** action: it re-runs the real
compile pipeline (model → mechanical validation → change set) against the stored
L1 snapshot — **no re-upload, no dedup wall** — and applies the upload autoflow
policy. This is the recovery path when validation rules changed (e.g. a grounding
fix), when the model/prompt improved, or when the surrounding wiki grew and a
re-merge would land better.

## 2. Requirements

### Glue (data plane)
- **R10-1 (P0)** `POST /recompile {id}` — `compile` permission (contributor+).
  Unknown source → 404. Runs `Wiki.compile(id)` (the same pipeline as upload).
- **R10-2 (P0)** Auto-apply policy identical to V5 upload autoflow (public licence,
  pending, zero problems, zero conflicts, non-protected) — factored into one shared
  helper so the two flows can never drift. Failures audited (`recompile_autoflow_failed`).
- **R10-3 (P0)** Response mirrors the upload response: `{changeset: {id, status,
  pages, protected}, auto_applied, problems}`; every attempt audited (`recompile`).
- **R10-4 (P0)** Serialized per server (one compile at a time) — model calls are
  expensive and change sets are not concurrent-safe.
- **R10-5 (P1)** Deleted sources cannot be resurrected — the snapshot must exist.

### UI (原始文档 page)
- **R10-6 (P0)** 「🔄 重新编译」 in the source detail header; live `compiling… Ns`
  ticker; result reuses the upload result panel (已自动应用 + page chips / pending /
  problems); source list + wiki refresh afterwards.

## 3. EPIC breakdown

- **EPIC-RC1 — Glue recompile core** (R10-1..R10-5): endpoint + shared autoflow
  helper; HTTP tests (applies clean, surfaces problems, 404 unknown, audit rows).
- **EPIC-RC2 — UI + proxy** (R10-6): button/ticker/result; studio proxy route.
- **EPIC-RC3 — Gates & E2E**: Playwright recompiles a live source; wiki intact.

## 4. Acceptance gates

- **GL-RC1** clean public source recompiles and auto-applies over HTTP (unit).
- **GL-RC2** a compile whose output fails validation returns problems with
  `auto_applied: false` and writes nothing (unit).
- **GL-RC3** unknown id → 404; audit log carries `recompile` rows (unit).
- **GL-RC4** Playwright: recompile via the page UI; evidence screenshots; suite green.
