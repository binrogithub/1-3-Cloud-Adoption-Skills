# E5: Enhanced Dream Report

**Depends on:** E1, E2, E3, E4  
**Blocks:** E6, E8  
**Estimate:** 1.5 days  
**PRD sections:** 5.3, 5.4, 6.1

## Goal

Transform `dream_agent_report.py` from a trajectory-only report into a
project-aware dream report that integrates code-index insights, git history,
and fixed signal classification. This is the critical-path epic — it produces
the user-visible output of `/code-dreaming`.

## Stories

### S5.1: Cold-start gate

Add a cold-start detection check at the top of `render_report()`:

```python
def render_report(trajectory, repo_root, code_index_path):
    has_trajectory = trajectory and not trajectory.no_trajectory
    has_code_index = code_index_path and code_index_path.exists()

    if not has_trajectory and not has_code_index:
        return _cold_start_report(repo_root)
    # ...
```

`_cold_start_report(repo_root)`:
- Check if repo_root is a git repo
- If yes: suggest running `python3 scripts/code_index.py --repo-root .`
- If no: explain that code-dreaming needs either code or session data
- Return a helpful report instead of empty output

**Acceptance:**
- Fresh project with no `.jsonl` and no code-index.db: gets cold-start guidance
- Fresh project after running code_index.py: gets a real report
- Existing project with `.jsonl`: existing behavior unchanged

### S5.2: Auto-index on first run

When `render_report()` detects no code-index.db but the directory has source
files, automatically trigger an index:

```python
if not has_code_index and _has_source_files(repo_root):
    from code_index import CodeIndex
    idx = CodeIndex.open_or_create(default_db_path(repo_root))
    result = idx.index_all(repo_root)
    idx.close()
    has_code_index = True
```

- Only trigger on first run (when DB doesn't exist)
- Log: `"First run: indexing project (N files)..."`
- Timeout: 30 seconds max (abort gracefully if exceeded)

**Acceptance:**
- `/code-dreaming` on a fresh project auto-creates code-index.db
- Report includes code-index data without manual setup
- Existing code-index.db is reused, not rebuilt

### S5.3: Project overview section

Add a "Project Overview" section to the dream report using `CodeQueries.overview()`:

```markdown
## Project Overview

- **66 files** across 3 languages (Python: 52, YAML: 8, Markdown: 6)
- **312 symbols** (143 functions, 18 classes, 89 methods, 62 other)
- **89 cross-reference edges** (42 imports, 31 calls, 16 type refs)
- **142 commits** by 2 authors over 45 days
- Last indexed: 2026-06-15T10:30:00Z
```

**Acceptance:**
- Overview section appears in report when code-index.db exists
- Metrics match actual project state
- Graceful when code-index is empty or missing (section omitted)

### S5.4: Key symbols section

Add a "Key Symbols" section listing the most connected/important symbols:

```markdown
## Key Symbols

| Symbol | Kind | File | Callers | Callees |
|--------|------|------|---------|---------|
| `CodeIndex.index_all` | method | code_index.py:142 | 3 | 8 |
| `render_report` | function | dream_agent_report.py:45 | 2 | 12 |
| `scan_records` | function | dream_signals.py:18 | 4 | 2 |
```

- Rank by: `callers_count + callees_count` (most connected = most important)
- Show top 15 symbols
- Include file path and line number

**Acceptance:**
- Table appears with correct caller/callee counts
- Symbols are sorted by connectivity
- Links to file:line format

### S5.5: File coupling insights

Add a "Frequently Co-Changed Files" section from git coupling data:

```markdown
## Frequently Co-Changed Files

- `dream.py` <-> `dream_signals.py` (score: 0.82, 14 co-commits)
- `mce/cli.py` <-> `mce/executor.py` (score: 0.71, 9 co-commits)
```

- Use `CodeQueries.coupling()` for each high-traffic file
- Only show pairs with Jaccard score >= 0.3
- Deduplicate: show each pair once

**Acceptance:**
- Coupling pairs shown when git history is indexed
- Scores are plausible (0.0 to 1.0)
- Section omitted when no coupling data exists

### S5.6: Recent activity summary

Add a "Recent Activity" section from git history:

```markdown
## Recent Activity (last 7 days)

- 8 commits, 12 files changed
- Most active: `scripts/dream.py` (4 commits, +120 -45)
- New files: `epics/E0-schema-foundation.md`, `prd-v2-project-knowledge-engine.md`
```

- Use `CodeQueries.changes_since()` with 7-day lookback
- Summarize: commit count, file count, most active files, new files
- If no recent activity: "No commits in the last 7 days."

**Acceptance:**
- Activity section appears with correct counts
- Most-active file is correct
- Handles zero-activity period gracefully

### S5.7: Integrate signal scan with role filter

Update the signal scanning call in `render_report()` to use the fixed
`scan_records()` with role filtering (from E3):

```python
# Before
signals = scan_records(trajectory.records)

# After
signals = scan_records(trajectory.records, require_role={"human", "assistant"})
```

- Ensure the fixed patterns from E3 are used
- No self-referential signals in the output

**Acceptance:**
- Signal section no longer contains false positives from skill description
- Legitimate corrections still detected
- Works correctly when trajectory is None (code-index-only mode)

### S5.8: Report structure and formatting

Restructure the full report output order:

```markdown
# Dream Report: {project_name}
Generated: {timestamp}

## Project Overview          (S5.3 — from code index)
## Key Symbols               (S5.4 — from code index)
## Frequently Co-Changed     (S5.5 — from git coupling)
## Recent Activity           (S5.6 — from git history)
## Session Signals           (existing — with E3 fixes)
## Memory Health             (existing — dedup, stale, conflicts)
## Recommendations           (existing + new recommendations)
```

- Each section is independently optional (present only if data exists)
- Minimum viable report: at least one section must have content
- Header includes project name (derived from repo root directory name)

**Acceptance:**
- Full report has all applicable sections in order
- Code-index-only report (no trajectory): overview + symbols + coupling + activity
- Trajectory-only report (no code index): signals + memory health
- Both present: all sections

## Definition of Done

- [ ] `dream_agent_report.py` produces useful output on fresh projects
- [ ] Cold-start gate prevents empty reports
- [ ] Auto-index creates code-index.db on first run
- [ ] 4 new sections: overview, key symbols, coupling, recent activity
- [ ] Signal scan uses role filter (no false positives)
- [ ] Report structure is clean and sections are independently optional
- [ ] Tests cover: cold-start, auto-index, each section, combined report
