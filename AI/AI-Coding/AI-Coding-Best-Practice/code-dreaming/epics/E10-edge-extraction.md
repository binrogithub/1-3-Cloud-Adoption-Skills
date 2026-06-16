# E10: Tree-Sitter Edge Extraction

**Depends on:** E1 (tree-sitter indexer)
**Blocks:** E11 (SKILL.md — edges status), E12 (report quality — Key Symbols)
**Estimate:** 2 days
**PRD sections:** 2.2 (F2), 3.3 (Stage 2b)

## Goal

Implement edge extraction in `code_index.py` Stage 2 so that the `edges` table
populates with calls, imports, extends, implements, and references relationships.
This is the most impactful gap — without edges, callers/callees/Key Symbols are
all empty.

## Stories

### S10.1: Python call/import edge extraction

Add `_extract_python_edges(tree, file_id, symbols_map)` to `code_index.py`:

- Walk AST for `call` nodes → resolve callee name → look up in symbols_map
- Walk AST for `import_from` / `import` nodes → resolve imported names
- Walk AST for `class` definition `bases` → resolve parent class names
- For each resolved edge, insert into `edges` table with:
  - `kind`: `calls` | `imports` | `extends` | `references`
  - `confidence`: 1.0 (direct name match) | 0.8 (receiver-based) | 0.5 (heuristic)
  - `line`: source line number of the call/import site

**Symbol resolution strategy:**
1. Exact `name` match within same file (confidence 1.0)
2. Qualified name match across files (confidence 1.0)
3. Unqualified name match in imported modules (confidence 0.8)
4. Fallback: log unresolved, do not insert edge

**Acceptance:**
- After indexing code-dreaming project, `edges` table has > 0 rows
- `CodeQueries.callers("render_report")` returns at least 1 result
- `CodeQueries.callees("render_report")` returns at least 1 result
- New test in `test_code_index.py` verifies edge count for a known Python file

### S10.2: JavaScript/TypeScript call/import edge extraction

Add `_extract_js_edges(tree, file_id, symbols_map)` to `code_index.py`:

- Walk AST for `call_expression` nodes → resolve callee
- Walk AST for `import_statement` / `import_declaration` nodes
- Walk AST for `class` `heritage_clause` → extends/implements
- Same resolution and insertion strategy as S10.1

**Acceptance:**
- After indexing a JS/TS project, `edges` table has > 0 rows
- Import edges correctly link to imported symbols
- New test verifies JS edge extraction

### S10.3: Edge extraction integration into index_all()

Wire edge extraction into the existing `index_all()` pipeline:

```
Stage 2 (existing): Parse -> extract symbols
Stage 2b (new):     Parse -> extract edges (using symbols from Stage 2)
```

- Build `symbols_map: dict[str, list[int]]` after all symbols are inserted
  (name → list of symbol IDs, for resolution)
- Call `_extract_*_edges()` for each file based on language
- Batch-insert edges with `executemany()` for performance
- Log summary: "Extracted N edges (calls=X, imports=Y, extends=Z)"

**Acceptance:**
- `index_all()` returns edge count in its result string
- Incremental re-index correctly updates edges for changed files
- Existing 251 tests still pass
- Performance: edge extraction adds < 50% overhead to total index time

### S10.4: Key Symbols section activation in dream report

With edges now populated, verify that `_section_key_symbols()` in
`dream_agent_report.py` produces output:

- The section should show top 15 symbols by caller+callee count
- Table format: Symbol | Kind | File | Callers | Callees
- Only symbols with at least 1 edge connection are shown

**Acceptance:**
- Dream report on code-dreaming project includes `## Key Symbols` section
- Table has > 0 rows
- Symbols are ordered by total edge count descending

## Definition of Done

- [ ] `edges` table populated after indexing code-dreaming project
- [ ] `callers()` and `callees()` return non-empty results for known symbols
- [ ] Dream report `Key Symbols` section appears with data
- [ ] New tests for edge extraction in `test_code_index.py`
- [ ] All 251+ existing tests still pass
- [ ] Performance overhead < 50%
