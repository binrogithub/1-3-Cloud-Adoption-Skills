# E11: SKILL.md Completeness & Documentation Gaps

**Depends on:** E10 (edges — need to document edges status)
**Blocks:** nothing
**Estimate:** 0.5 day
**PRD sections:** 3.1, 3.2, 3.3

## Goal

Fix all 9 documentation gaps discovered in E2E testing. SKILL.md must be the
single source of truth for every feature a user can invoke.

## Stories

### S11.1: Add missing Operations table entries

Add these rows to the Operations table in SKILL.md:

| Op | Command |
|----|---------|
| **code-index** (build/update) | `python3 BASE/scripts/code_index.py --repo-root REPO [--db PATH] [--languages PY,JS,...] [--max-commits N]` |
| **git-history** (parse & store) | `python3 BASE/scripts/git_adapter.py --repo-root REPO [--db PATH] [--max-commits N] [--since DATE]` |
| **code-query** (Python API) | `from scripts.code_queries import CodeQueries` — overview/search/file_symbols/callers/callees/coupling/changes_since |
| **artifact export** | `python3 -m mce.cli artifact export [--db PATH] [--output PATH.zst]` |
| **artifact import** | `python3 -m mce.cli artifact import [--input PATH.zst] [--db PATH]` |

**Acceptance:**
- Every CLI command that a user can invoke is listed in the Operations table
- Each entry has the full command syntax with all common flags

### S11.2: Document cold-start behavior

Add to SKILL.md after the Default behavior section:

```markdown
## Cold Start (first run on a new project)

When no trajectory evidence AND no code-index database exist, the dream report
returns a Cold Start guidance document instead of a normal report:

- **Status**: "No trajectory evidence and no code-index database were found"
- **How to Get Started**: instructions to index the project or start a session
- **Next Steps**: concrete commands to run

If `--instructions` is provided, a Steering Instructions section appears
between Status and How to Get Started.

Auto-index: When source files exist but no DB, the report auto-triggers
`code_index.py` to build the initial index before generating the report.
```

**Acceptance:**
- SKILL.md describes cold-start behavior
- Mentions auto-index trigger

### S11.3: Document code-index enhanced report sections

Add to SKILL.md under Default behavior or a new section:

```markdown
## Code-Index Enhanced Report

When a code-index database exists (`.maas-dreaming/code-index.db`), the dream
report includes these additional sections:

| Section | Source | Content |
|---------|--------|---------|
| Project Overview | `CodeQueries.overview()` | File count, language breakdown, symbol count, commit count, last indexed |
| Key Symbols | `edges` table | Top 15 symbols by caller+callee count (requires edges > 0) |
| Frequently Co-Changed Files | `CodeQueries.coupling()` | File pairs with Jaccard similarity ≥ 0.4 from git co-change history |
| Recent Activity | `CodeQueries.changes_since()` | Commits and file changes in the last 7 days |

Use `--db PATH` to override the default DB location.
```

**Acceptance:**
- All 4 code-index sections documented
- `--db` flag documented
- Key Symbols dependency on edges noted

### S11.4: Document role compatibility and edges status

Add notes to SKILL.md:

**In Signal Scan section:**
```markdown
Signal Scan supports `human`, `user`, and `assistant` roles for cross-platform
trajectory compatibility (Claude Code uses `user`, the original design used `human`).
```

**In Code Index section or a Known Limitations subsection:**
```markdown
**Current status:** Tree-sitter extracts symbols (functions, classes, methods) and
file metadata. Edge extraction (calls, imports, extends, implements) is implemented
for Python and JavaScript/TypeScript. The `callers()`/`callees()` API and Key
Symbols report section require edges to be present.
```

**Acceptance:**
- `user` role support documented
- edges status documented with impact on dependent features

### S11.5: Add Code Index & Queries section

Add a new top-level section to SKILL.md:

```markdown
## Code Index & Queries

### Building the Index
```bash
python3 scripts/code_index.py --repo-root . --db .maas-dreaming/code-index.db
```

First run: full tree-sitter parse + git log. Subsequent runs: incremental
(only changed files re-parsed). Typical: 500 files in 2-5s first run, <200ms
incremental.

### Querying the Index
```python
from scripts.code_queries import CodeQueries

with CodeQueries(".maas-dreaming/code-index.db") as cq:
    cq.overview()          # project metrics
    cq.search("dream")     # FTS5 symbol search
    cq.file_symbols(path)  # all symbols in a file
    cq.callers("func")     # who calls this function
    cq.callees("func")     # what this function calls
    cq.coupling(path)      # frequently co-changed files
    cq.changes_since(date) # recent commit activity
```

### Supported Languages
Python, JavaScript, TypeScript (P0). Go, Rust, Java, C, C++ (P1, install
additional grammars). Graceful degradation: missing grammar → file indexed
as text-only (path + size + hash, no symbols/edges).

### Team Sharing
```bash
python3 -m mce.cli artifact export --db .maas-dreaming/code-index.db
# Commit .maas-dreaming/code-index.db.zst + artifact.json
python3 -m mce.cli artifact import --input code-index.db.zst
```
```

**Acceptance:**
- New section covers build, query, languages, and sharing
- All code examples are syntactically valid
- Links to existing Operations table entries

## Definition of Done

- [ ] Operations table has all 11 entries (6 old + 5 new)
- [ ] Cold-start behavior documented
- [ ] Code-index enhanced report sections documented
- [ ] `user` role and edges status documented
- [ ] Code Index & Queries section added
- [ ] `--db` flag documented in dream-report entry
- [ ] All commands in SKILL.md verified executable
