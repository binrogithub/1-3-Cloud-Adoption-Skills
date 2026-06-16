# PRD v4: E2E Hardening Round 2

Date: 2026-06-15
Scope: Full E2E test of all SKILL.md-documented features, with careful output inspection

## Test Results Summary

| # | Feature | Result | Details |
|---|---------|--------|---------|
| 1 | dream-report (default) | PARTIAL | All sections present, but Signal Scan was 0 (fixed), report 37MB |
| 2 | dream-report --instructions | PASS | Steering Instructions section appears with correct content and position |
| 3 | dream-report --output-mode project-root | PASS | Report in .maas-dreaming/, POINTER.suggested.md created |
| 4 | code-index build + incremental | PASS | 86 files, 654 symbols, 945 edges; incremental 0.1s |
| 5 | git-history adapter | PASS | 142 commits, 101 coupling pairs |
| 6 | CodeQueries API (7 methods) | PARTIAL | 6/7 methods work; coupling() returns 0 for project-local paths |
| 7 | artifact export/import | PASS | 4.8:1 compression, round-trip preserves all data |
| 8 | Signal Scan (user role) | BUG→FIXED | Role extraction from nested message fixed; 5 hits found |
| 9 | Cold Start | PASS | Correct sections, correct order, instructions conditional |
| 10 | Edge extraction + Key Symbols | PARTIAL | 945 calls edges; 0 imports/extends (unresolvable targets) |
| 11 | --keep retention + DREAMS.md | PASS | Retention works, index is newest-first with signal summaries |

## Findings

### F1: JSONL role extraction broken (CRITICAL — fixed in this round)

**Severity:** Bug (P0)
**Symptom:** Signal Scan always returns 0 hits on real Claude Code JSONL trajectories
**Root cause:** `read_jsonl()` in `dream_sources.py` extracts role via `_json_get(obj, "role", "actor")` which only checks top-level keys. Claude Code JSONL nests role inside `obj.message.role` for `type=assistant` entries, and uses `type=user` as the role indicator for user messages.
**Fix applied:** Added fallback role extraction: check `obj.message.role`, then check `obj.type` for user/assistant values.
**Before:** All 85 records had `role=""`, Signal Scan = 0 hits
**After:** 24 user + 35 assistant records, Signal Scan = 5 hits (4 corrections, 1 preference)

### F2: Import/extends edges silently dropped (P1 gap)

**Severity:** Functional gap (P1)
**Symptom:** Edge table has 945 `calls` edges but 0 `imports` and 0 `extends` edges
**Root cause:** `_python_imports()` and `_python_calls_and_extends()` correctly generate import/extends EdgeInfo objects, but `index_all()` resolves target symbols by looking them up in the symbols table. Stdlib modules (`json`, `sqlite3`, `re`) and stdlib base classes (`RuntimeError`, `ValueError`) are never in the project's symbols table, so these edges are silently skipped.
**Impact:** SKILL.md documents `imports`, `extends`, `implements` as supported edge kinds, but none appear in the DB. The `callers()`/`callees()` API can't show import relationships.
**Proposed fix:** Two options:
  - (a) Insert unresolved edges with `target_id=NULL` and a `target_name` column — preserves the edge data even when target isn't in DB
  - (b) Only resolve edges where target exists in DB, but add a separate `unresolved_edges` table for import/extends tracking
  - Recommend (a) for simplicity; add `target_name` column to edges table, allow NULL `target_id`

### F3: Frequently Co-Changed Files section is 37MB of cross-project noise (P1)

**Severity:** Quality (P1)
**Symptom:** Report is 37MB; Frequently Co-Changed Files section contains 184,994 coupling pairs — all from sibling projects in the parent monorepo, zero from maas-dreaming itself
**Root cause:** `git_adapter.py` parses `git log` from the parent repo, so commit_files contains paths from all sibling projects. The coupling query doesn't scope to files within the current project.
**Impact:** Report is unusable for humans. The coupling section provides zero value for the target project.
**Proposed fix:** In `_section_coupling()` in `dream_agent_report.py`, filter coupling pairs to only include paths that are within or below the repo-root. Additionally, cap the number of coupling pairs displayed (e.g., top 20 by score).

### F4: CodeQueries.coupling() returns empty for project-local paths (P2)

**Severity:** Quality (P2)
**Symptom:** `cq.coupling("scripts/code_index.py")` returns 0 results
**Root cause:** Same as F3 — commit_files table contains parent-repo paths like `AI/AI-Coding/.../scripts/code_index.py`, but the query uses the local path `scripts/code_index.py`.
**Proposed fix:** In `git_adapter.py`, store paths relative to `--repo-root` rather than the git worktree root. Or in `coupling()`, try both the given path and any prefix-stripped version.

### F5: Report Evidence Preview includes full JSONL content (P2)

**Severity:** Quality (P2)
**Symptom:** Evidence Preview section dumps entire JSONL record content with minimal truncation
**Root cause:** Preview is bounded by `DEFAULT_PREVIEW_CHARS=600` per record, but with 85 records this still produces ~10KB of raw JSON in the report
**Impact:** Makes the report harder to read; the preview is meant to be a quick scan, not a full dump
**Proposed fix:** Reduce default preview chars or cap total Evidence Preview size. Consider showing only the first 10 records with a "N more..." summary.

### F6: Edge kinds all "calls" — no diversity (P2, depends on F2)

**Severity:** Documentation accuracy (P2)
**Symptom:** SKILL.md says edges include `calls`, `imports`, `extends`, `implements`, `references`, but only `calls` appears in practice
**Root cause:** Same as F2 — import/extends edges are generated but dropped during resolution
**Impact:** Misleading documentation; callers/callees API only shows call relationships
**Proposed fix:** Fix F2 first, then update SKILL.md to accurately reflect which edge kinds are currently populated

## Metrics

- Tests: 251/251 passing
- Code-index: 86 files, 654 symbols, 945 edges (all `calls`), 142 commits
- Signal Scan: 5 hits (4 corrections, 1 preference) — was 0 before F1 fix
- Report size: 37MB (should be <100KB)
- Key Symbols: 15 entries with real caller/callee counts
- Artifact compression: 4.8:1

## Priority Order

1. **F1** — Fixed in this round (role extraction)
2. **F3** — Coupling scope filter (makes report usable)
3. **F2** — Unresolved edge storage (makes import/extends edges visible)
4. **F4** — Coupling path resolution (makes coupling() API work)
5. **F5** — Evidence preview bounding (report readability)
6. **F6** — Documentation accuracy (depends on F2)
