# E6: CLI & Integration

**Depends on:** E1, E4  
**Blocks:** E9  
**Parallel with:** E7, E8  
**Estimate:** 1 day  
**PRD sections:** 7.1, 7.2

## Goal

Wire code-index capabilities into the existing MCE CLI (`mce/cli.py`) and
execution engine (`mce/executor.py`) so that `mce retrieve`, `mce run`, and
the MCP tool surface can access project structure queries.

## Stories

### S6.1: Add `index` subcommand to mce/cli.py

Add `mce index` as a new CLI subcommand:

```
mce index [--repo-root .] [--db .maas-dreaming/code-index.db]
          [--max-files 5000] [--languages python,javascript]
```

- Delegates to `CodeIndex.open_or_create()` + `index_all()`
- Prints summary: `"Indexed 66 files, 312 symbols, 89 edges (3.2s)"`
- Incremental by default (only re-indexes changed files)

**Acceptance:**
- `mce index` creates or updates code-index.db
- Summary output shows correct counts
- Second run shows 0 changes

### S6.2: Add `query` subcommand to mce/cli.py

Add `mce query` with sub-actions:

```
mce query overview
mce query search "parse_git"
mce query file-symbols scripts/dream.py
mce query callers render_report
mce query callees index_all
mce query coupling scripts/dream.py
mce query changes-since 2026-06-01
```

- Each action delegates to the corresponding `CodeQueries` method
- Output is human-readable by default, `--json` flag for machine output
- Reads DB from default location or `--db` flag

**Acceptance:**
- `mce query overview` prints project summary
- `mce query search "parse"` shows matching symbols
- `--json` flag outputs valid JSON
- Missing DB: helpful error message

### S6.3: Add `code-index` execution plan to mce/executor.py

Create a new execution plan `code-index` in `mce/executor.py`:

```python
PLANS = {
    "dream-writeback": ...,  # existing
    "code-index": {
        "steps": [
            {"action": "index", "label": "Index project files"},
            {"action": "git-history", "label": "Index git history"},
        ],
    },
}
```

- `mce run code-index` executes both indexing steps in sequence
- Reuses `CodeIndex.index_all()` and `git_adapter.write_git_history()`
- Prints step-by-step progress

**Acceptance:**
- `mce run code-index` indexes files and git history
- Steps execute in order with progress output
- Failure in one step: error message, other steps still attempted

### S6.4: Integrate code-index into mce/retrieve.py

Extend `mce retrieve` to search code-index alongside Mem0:

```python
def retrieve(query, db_path=None, mem0_config=None):
    results = []

    # Existing: Mem0 / FTS5 memory search
    if mem0_config:
        results.extend(search_mem0(query, mem0_config))

    # NEW: code-index symbol search
    if db_path and db_path.exists():
        from code_queries import CodeQueries
        with CodeQueries(db_path) as cq:
            results.extend(cq.search(query))

    return rank_and_dedup(results)
```

- Code-index results are interleaved with memory results
- Deduplication: if a symbol name appears in both memory and code-index,
  prefer code-index (it's authoritative for current state)
- Source field distinguishes results: `source="code-index"` vs `source="mem0"`

**Acceptance:**
- `mce retrieve "parse"` returns both memory and code-index hits
- Code-index results have `source="code-index"`
- Works when only one source is available (Mem0 only or code-index only)
- No results: "No matches found." (not error)

### S6.5: Update `/maas-dreaming` skill entry point

Modify the main skill dispatch in `SKILL.md` and `scripts/dream_agent_report.py`
so that the default `/maas-dreaming` invocation:

1. Auto-creates code-index.db if missing (delegates to S5.2)
2. Runs incremental index update
3. Generates enhanced dream report (delegates to E5)

No new CLI flags needed — the enhanced behavior is the new default.

**Acceptance:**
- `/maas-dreaming` on a fresh project: auto-indexes, produces full report
- `/maas-dreaming` on a project with existing DB: incremental update, full report
- Existing behavior for trajectory-based dreaming preserved

## Definition of Done

- [ ] `mce index` subcommand works
- [ ] `mce query` with all sub-actions works
- [ ] `mce run code-index` plan executes indexing pipeline
- [ ] `mce retrieve` searches code-index alongside Mem0
- [ ] `/maas-dreaming` default path produces useful output on fresh projects
- [ ] Tests cover new CLI subcommands and integration points
