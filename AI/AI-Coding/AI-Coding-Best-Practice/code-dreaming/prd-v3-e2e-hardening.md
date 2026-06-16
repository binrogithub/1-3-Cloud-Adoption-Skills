# PRD v3: code-dreaming E2E Hardening & SKILL.md Completeness

**Status:** Draft
**Author:** AI-assisted (E2E test findings)
**Date:** 2026-06-15
**Supersedes:** Fixes and gaps discovered after E2E testing of v2 implementation

---

## 1. Problem Statement

### 1.1 E2E Test Results Summary

After implementing all E0–E9 epics, a systematic end-to-end test of every feature
revealed **1 bug**, **1 functional gap**, **4 quality issues**, and **9 documentation
gaps in SKILL.md**. The core pipeline works, but several features are degraded or
undocumented.

### 1.2 Findings

| # | Severity | Finding | Impact |
|---|----------|---------|--------|
| F1 | **Bug (fixed)** | `SCANNABLE_ROLES` missing `user` — Signal Scan returns 0 hits on real Claude Code JSONL trajectories (role=`user` not `human`) | Signal Scan useless on real data |
| F2 | **P0 Gap** | Tree-sitter edge extraction not implemented — `edges` table always 0 rows | callers/callees/Key Symbols section all empty |
| F3 | **P1** | Coupling section includes `.gitkeep` and other noise files | Frequently Co-Changed Files section misleading |
| F4 | **P1** | Cold-start report: Steering Instructions inserted inside "How to Get Started" section | Layout confusing |
| F5 | **P2** | `CodeQueries.overview()` returns `last_indexed` as epoch int, not ISO string | API inconsistency (report converts, but direct API callers see raw int) |
| F6 | **Doc** | SKILL.md Operations table missing: `code_index.py`, `git_adapter.py`, `code_queries.py`, `artifact export/import`, cold-start behavior, code-index report sections, `--db` flag, `user` role support, edges=0 status | Users cannot discover or use new features |

---

## 2. Fix Specifications

### 2.1 F1: SCANNABLE_ROLES — ALREADY FIXED

Three call sites changed from `frozenset({"human", "assistant"})` to
`frozenset({"human", "user", "assistant"})`:

- `scripts/dream_signals.py:20` — `SCANNABLE_ROLES` constant
- `scripts/dream_agent_report.py:89` — `report_summary()` call
- `scripts/dream_agent_report.py:577` — `render_report()` signal scan call

**Status:** Fixed. 251/251 tests pass.

### 2.2 F2: Tree-Sitter Edge Extraction

**Current state:** `code_index.py` Stage 2 extracts symbols (functions, classes,
methods, etc.) but does NOT extract edges (calls, imports, extends, implements,
references). The `edges` table is always empty.

**Target:** Implement edge extraction for Python and JavaScript/TypeScript via
tree-sitter AST queries. This is the most impactful gap — without edges:

- `CodeQueries.callers()` / `callees()` always return `[]`
- `Key Symbols` section in dream report is skipped (requires edges > 0)
- Call graph analysis is unavailable

**Implementation approach:**

```
Stage 2b: Edge Extraction (new, after symbol extraction)
    For each parsed file:
        1. Query AST for call expressions:
           - Python: call nodes -> resolve to symbol name
           - JS/TS: call/member-expression nodes -> resolve
        2. Query AST for import/require statements:
           - Map imported names to file-local symbols
        3. Query AST for class extends/implements:
           - Map to symbol names in other files
        4. Resolve symbol names to symbol IDs:
           - Pass 1: exact name match within file
           - Pass 2: qualified name match across files
           - Pass 3: heuristic (receiver type inference for method calls)
        5. Insert into edges table with:
           - kind: calls | imports | extends | implements | references
           - confidence: 1.0 (exact) | 0.8 (receiver) | 0.5 (heuristic)
           - line: call site line number
```

**Edge kinds to extract (v1):**

| Kind | Source | Languages | Confidence |
|------|--------|-----------|------------|
| `calls` | function/method call expressions | Python, JS, TS | 1.0 (direct) / 0.8 (receiver) |
| `imports` | import/require/from statements | Python, JS, TS | 1.0 |
| `extends` | class inheritance | Python, JS, TS | 1.0 |
| `implements` | interface implementation | Python (ABC), TS | 1.0 |
| `references` | name usage not covered above | Python, JS, TS | 0.5 |

**Acceptance criteria:**
- After indexing the code-dreaming project, `edges` table has > 0 rows
- `CodeQueries.callers("render_report")` returns at least 1 caller
- `CodeQueries.callees("render_report")` returns at least 1 callee
- Dream report `Key Symbols` section appears when edges exist
- Existing 251 tests still pass
- New test: `test_code_index.py` includes edge extraction test

### 2.3 F3: Coupling Noise Filter

**Current state:** `_section_coupling()` in `dream_agent_report.py` shows all
coupling pairs from `CodeQueries.coupling()`, including `.gitkeep` files and
other non-source noise.

**Fix:**

1. Add a `_NOISE_EXTENSIONS` / `_NOISE_PATTERNS` filter in `_section_coupling()`:
   - Skip files ending in `.gitkeep`, `.keep`, `.empty`
   - Skip files with no extension that are 0 bytes
   - Apply filter to both sides of coupling pairs
2. Raise default `min_score` from 0.3 to 0.4 in the coupling section call
   (0.3 admits too many weak pairs)

**Acceptance:**
- `.gitkeep` files never appear in Frequently Co-Changed Files section
- Pairs with Jaccard < 0.4 are excluded from the report

### 2.4 F4: Cold-Start Steering Instructions Layout

**Current state:** In `_cold_start_report()`, the Steering Instructions block is
inserted after the "How to Get Started" header but before the git/non-git
conditional content. This produces:

```markdown
## How to Get Started

## Steering Instructions    <-- wrong position

...actual getting started content...
```

**Fix:** Move the Steering Instructions block to appear after the Status section
and before the How to Get Started section.

**Acceptance:**
- Cold-start report with `--instructions` shows sections in order:
  Status → Steering Instructions → How to Get Started → Next Steps

### 2.5 F5: CodeQueries.overview() last_indexed Type

**Current state:** `overview()` returns `last_indexed` as a Unix epoch float
(e.g., `1781528355.0`). The dream report converts it to ISO, but direct API
callers get the raw number.

**Fix:** Convert inside `overview()` before returning. If the value is a float/int
that looks like a Unix timestamp (> 1e9), convert to ISO 8601 string.

**Acceptance:**
- `CodeQueries.overview()["last_indexed"]` returns ISO 8601 string like
  `"2026-06-15T12:54:35Z"` instead of `1781528355.0`

---

## 3. SKILL.md Completeness Requirements

### 3.1 Missing Operations Table Entries

The Operations table in SKILL.md must be extended with these rows:

| Op | Command | Notes |
|----|---------|-------|
| **code-index** (build/update) | `python3 BASE/scripts/code_index.py --repo-root REPO [--db PATH] [--languages PY,JS,...] [--max-commits N]` | Creates or incrementally updates SQLite code-index DB |
| **git-history** (parse & store) | `python3 BASE/scripts/git_adapter.py --repo-root REPO [--db PATH] [--max-commits N] [--since DATE]` | Parses git log, writes commits + file coupling to DB |
| **code-query** (Python API) | `from scripts.code_queries import CodeQueries; cq = CodeQueries(db_path)` | overview/search/file_symbols/callers/callees/coupling/changes_since |
| **artifact export** | `python3 -m mce.cli artifact export [--db PATH] [--output PATH.zst]` | Compresses DB to zstd for git sharing |
| **artifact import** | `python3 -m mce.cli artifact import [--input PATH.zst] [--db PATH]` | Decompresses zstd artifact to working DB |

### 3.2 Missing Behavioral Documentation

| Topic | What to Document |
|-------|-----------------|
| Cold-start behavior | When no trajectory AND no code-index exist, report returns Cold Start guidance with "How to Get Started" section |
| Code-index enhanced report sections | When code-index DB exists, dream report includes: Project Overview, Key Symbols (if edges > 0), Frequently Co-Changed Files, Recent Activity |
| `--db` flag | `dream_agent_report.py --db PATH` overrides default DB location |
| `user` role support | Signal Scan supports `human`, `user`, and `assistant` roles for cross-platform trajectory compatibility |
| Auto-index on first run | When no DB exists but source files are present, dream report auto-triggers `code_index.py` |
| edges=0 current status | Tree-sitter currently extracts symbols only; edge extraction (calls/imports/extends) is in progress. callers/callees/Key Symbols require edges. |

### 3.3 SKILL.md Section Updates

**Update "Default `/code-dreaming` behavior" section** to include:

```
Step 0 (auto): If no code-index DB exists and source files are present,
    auto-run code_index.py to build the initial index.

Step 1: Generate dream report (existing command, now enhanced):
    python3 BASE/scripts/dream_agent_report.py --repo-root REPO

    Report sections (when code-index DB exists):
    - Project Overview (files, symbols, languages, commits)
    - Key Symbols (top 15 by caller+callee count, requires edges)
    - Frequently Co-Changed Files (Jaccard coupling from git history)
    - Recent Activity (commits and file changes in last 7 days)
    - Signal Scan (corrections/preferences/decisions/recurring)
    - Evidence Preview
    - Candidates

    Report sections (cold start, no trajectory and no DB):
    - Status: "fresh project or first run"
    - How to Get Started: indexing instructions
    - Next Steps
```

**Update "Output location & team sharing" section** to add artifact commands.

**Add new "Code Index & Queries" section** with:

- What the code index is (SQLite knowledge graph)
- How to build it (`code_index.py`)
- How to query it (`CodeQueries` API)
- Supported languages and graceful degradation
- Incremental behavior
- Team sharing via artifact export/import

---

## 4. Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| Signal Scan hits on real Claude Code JSONL | 0 (broken) | Correct counts |
| `edges` table rows (code-dreaming project) | 0 | > 0 |
| `callers("render_report")` result | `[]` | At least 1 caller |
| Key Symbols section in dream report | Absent | Present |
| `.gitkeep` in coupling section | Present | Absent |
| SKILL.md Operations table coverage | 6 ops (old only) | 11 ops (all) |
| SKILL.md behavioral docs | Missing 6 topics | All documented |
| `overview()["last_indexed"]` type | `float` | ISO 8601 `str` |

---

## 5. Implementation Priority

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| P0 | F2: Edge extraction | 2d | Enables callers/callees/Key Symbols |
| P0 | F6: SKILL.md completeness | 0.5d | Users can discover and use all features |
| P1 | F3: Coupling noise filter | 0.5d | Report quality |
| P1 | F4: Cold-start layout | 0.25d | Report readability |
| P2 | F5: overview() type fix | 0.25d | API consistency |

**Total estimated effort: ~3.5 days**
