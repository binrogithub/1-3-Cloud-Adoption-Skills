# PRD V9 — Edit wiki pages online (web editor through the change-set write path)

| Field | Value |
|---|---|
| Document | `docs/PRD_LLMWIKI_WEB_EDIT_V9.md` · V9.0 · 2026-09-24 |
| Builds on | V4 (wiki master-detail browse) — delivered; V5/V7 (upload + delete) — delivered |
| User request | 增加在线通过网页修改 wiki 的能力,输出 PRD,实施 PRD |

## 1. Summary

The Wiki detail view gains an **editor**: ✏️ 编辑 opens a raw-text editor for
`compiled_truth`. Saving does **not** bypass any rule — the edit runs through the
same mechanical grounding checker as model compiles (every number/term/URL must be
backed by an `[S:source-id]` citation whose L1 snapshot actually contains it), is
recorded as a change set (D-5), and only then writes the page. Clean edits by a
contributor apply immediately; protected namespaces need a curator; failed edits
come back with a per-claim problem list and the page stays untouched.

## 2. Semantics

| Edit outcome | Result |
|---|---|
| Clean (zero grounding problems), non-protected slug, contributor+ | Change set `applied`; page truth updated; timeline note "manual web edit by \<actor\>"; `last_verified` = today; roster/detail refresh |
| Any grounding problem (uncited number/term, bad URL domain, unknown `[S:id]`) | Change set `invalid` with per-claim problems; page unchanged; editor shows the problem list |
| Protected namespace (`pricing/`, `compliance/`, `availability/`) | Requires curator role; contributors get a clear refusal before anything is written |
| `[S:id]` citing a source the page did not cite before | Allowed if that L1 snapshot exists; its id joins `page.sources` on apply |

Non-goals (v1): editing page titles/slug/type (truth text only, title optional);
structural edits (merge/split pages); drafts/locking (single-editor assumption);
model-assisted rewriting.

## 3. Requirements

### Glue (data plane)
- **R9-1 (P0)** `Wiki.edit_page(slug, compiled_truth, actor, title="")`: grounds the
  text against the texts of every `[S:id]` cited in it via the same
  `grounding.verify` used by compiles (S-prefix, terms, URL domains, synonyms);
  unknown citation ids are themselves problems.
- **R9-2 (P0)** One change set per edit attempt (`source.ref = web-edit:<slug>`),
  D-5 intact; applied edits write directly (like delete-cascade — `merge()` would
  pollute `sources` with a pseudo-id), with audit entries for both outcomes.
- **R9-3 (P0)** New permission `edit` at contributor level; protected slugs
  additionally require the `approve` (curator) permission.
- **R9-4 (P0)** `POST /pages/edit` `{slug, compiled_truth, title?}` →
  `{applied, problems: [{problem, unit}], changeset: {id, status}}`.

### UI (Wiki page)
- **R9-5 (P0)** ✏️ 编辑 in the detail header toggles an editor: monospace textarea
  with the raw truth, a citation hint (语句以 `[S:源id]` 结尾;不带引用的事实句会被拒),
  保存 / 取消.
- **R9-6 (P0)** Save result: applied → detail re-renders the new truth with a
  success note; problems → red list (claim + reason) under the textarea, page
  unchanged; protected/role refusal shown inline.

## 4. EPIC breakdown

- **EPIC-WE1 — Glue edit core** (R9-1..R9-4): edit_page + permission + endpoint; unit
  tests (apply path, grounding rejection, unknown cite, protected refusal, HTTP role).
- **EPIC-WE2 — Editor UI + proxy** (R9-5..R9-6): edit mode in LlmWikiBrowse, studio
  proxy route.
- **EPIC-WE3 — Gates & E2E**: Playwright — clean edit applies and renders; bad edit
  (uncited number) rejected with visible problem; page unchanged on failure.

## 5. Acceptance gates

- **GL-WE1** a cited-statement edit applies; truth/timeline/sources/audit updated (unit).
- **GL-WE2** an uncited "9999 TB" edit is refused with `not_in_cited`; page byte-identical (unit).
- **GL-WE3** contributor cannot edit `pricing/*`; curator can (HTTP).
- **GL-WE4** Playwright both UI paths; evidence screenshots; full suite green.
