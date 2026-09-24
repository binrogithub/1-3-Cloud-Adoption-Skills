# PRD V7 — Cascade delete: remove a source together with the content that cites it

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_DELETE_CASCADE_V7.md` · V7.0 · 2026-09-24 |
| Builds on | V5 (upload + delete guard) — delivered; V6 (dream reconcile) — delivered |
| User request | 删除时增加一个选项,实现连同被引用的内容一并删除 |

## 1. Summary

Today `DELETE /source` refuses a source that any wiki page cites (409, V5 delete
guard). V7 adds an explicit **cascade option**: delete the L1 snapshot **and
retract the content that depends on it**. Retraction is **statement-granular** —
only the sentences carrying `[S:<id>]` citations of the deleted source are
removed; sentences backed by other sources survive untouched. A page whose every
statement cites the deleted source is removed entirely. Every cascade goes
through a change set (D-5 invariant) and the audit log, exactly like a compile.

## 2. Semantics — what "连同被引用的内容一并删除" means

| Situation | Cascade result |
|---|---|
| Page cites the source in **some** statements | Those statements are deleted from `compiled_truth`; other statements stay; `sources` drops the id; a dated timeline note records the retraction |
| Page's **every** statement cites the source | The page itself is deleted (it no longer asserts anything) |
| Source uncited (no page references it) | Cascade ≡ plain delete (V5 path) |
| Pending change sets for that source | Rejected (source gone), as in V5 |
| Protected pages (`pricing/`, `compliance/`, `availability/`) | Cascade **is allowed** — it is a named human action, not an autoflow — but the UI must list them with a warning before confirming |

Non-goals (v1): re-running the model to re-verify survivors (kept statements were
already verified); retracting timeline history (append-only by design — the note
itself is the record); deleting L1 snapshots other than the requested one.

## 3. Requirements

### Data plane (glue)
- **R7-1 (P0)** `DELETE /source?id=<sid>&cascade=1` performs the cascade delete.
  Without `cascade`, behaviour is unchanged (409 + `pages` list), and the 409 body
  now advertises `"cascade_available": true` so clients can offer the option.
- **R7-2 (P0)** Statement retraction is mechanical and auditable: within each
  citing page, sentences containing `[S:<sid>]` are removed; paragraphs collapse;
  remaining text is byte-identical to before (no rewriting, no model call).
- **R7-3 (P0)** A page left with no statements is deleted from the store
  (files backend: unlink; gbrain backend: `gbrain delete <slug>` + mirror unlink).
- **R7-4 (P0)** One change set records the whole cascade: per-page entries carry
  the retracted `compiled_truth` (or `"deleted": true`), `statements_removed`,
  and the retraction timeline note; status `applied`, actor = the deleting user
  (`delete-cascade` when triggered by system flow). D-5 (change sets are the only
  write path) stays intact.
- **R7-5 (P0)** Response report: `{deleted, cascade: true, pages: [{slug, action:
  "retracted"|"page-deleted", statements_removed}], rejected_changesets}`.
  The plain-delete 200 response is unchanged (V5 clients keep working).
- **R7-6 (P0)** Atomicity: all page writes happen before the snapshot files are
  removed; a mid-flight failure leaves the source present (delete is the last
  irreversible step). Caches invalidate after the whole cascade.

### UI (原始文档 page)
- **R7-7 (P0)** 删除此源 stays a single click for uncited sources. When the
  server answers 409, the detail card shows a **cascade panel**: the affected
  page list (protected pages flagged ⚠), the statement-level consequence
  ("将删除 N 处引用语句;整页删除 M 个"), a confirm dialog, then
  `DELETE …&cascade=1`.
- **R7-8 (P0)** After a cascade the roster, detail view and Wiki page list all
  refresh without a server restart; the per-page outcome is shown as result chips.
- **R7-9 (P1)** The helper line under the source text is updated: cited sources
  can now be deleted via the cascade option.

## 4. Acceptance gates

- **GL-D1** statement surgery: a two-source page loses only the sentences citing
  the deleted source; survivors byte-identical; `sources` updated; timeline note
  appended (unit test).
- **GL-D2** fully-cited page disappears from the store and from `page_list()`
  (unit test).
- **GL-D3** guard intact: without `cascade` a cited source still 409s and the
  body advertises `cascade_available` (HTTP test).
- **GL-D4** audit + change set exist for every cascade; pending change sets for
  the source end `rejected` (unit test).
- **GL-D5** UI end-to-end (Playwright): cited source → cascade panel lists pages
  → confirm → source gone, citing page updated/deleted in the Wiki roster, no
  dangling citations afterwards.

## 5. Evidence

`docs/evidence/live-2026-09-24/ui/37-cascade-*.png`, unit tests in
`tests/test_extensions.py::SourceCascadeTests`, all prior gates re-run.
