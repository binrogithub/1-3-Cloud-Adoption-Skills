# E1: Tree-Sitter Indexer

**Depends on:** E0  
**Blocks:** E4, E5, E6, E7, E8  
**Estimate:** 1.5 days  
**PRD sections:** 3.3, 3.4, 3.5

## Goal

Implement the 4-stage indexing pipeline that walks a project directory, parses
source files with tree-sitter, extracts symbols and edges, and stores them in
the SQLite knowledge graph. Incremental by default.

## Stories

### S1.1: File walker with git-first discovery

Add `walk_files(repo_root)` to `code_index.py`:

- Prefer `git ls-files` when inside a git repo (respects all .gitignore levels)
- Fall back to `os.walk()` with `IGNORED_DIRS` filter for non-git projects
- `IGNORED_DIRS` reuses the existing set from `scan_to_dream.py`:
  `.git`, `.hg`, `node_modules`, `vendor`, `build`, `dist`, `__pycache__`,
  `.venv`, `.mypy_cache`, `.pytest_cache`
- Skip binary files (check by suffix, then by null-byte sniff)
- Return `list[Path]` of text files relative to repo root

**Acceptance:**
- On a git repo, `git ls-files` is used and `.gitignore`d files are excluded
- On a non-git directory, `os.walk` is used with IGNORED_DIRS
- Binary files (`.pyc`, `.png`, `.exe`) are skipped
- Returns relative paths

### S1.2: Incremental fingerprinting

Add `classify_files(conn, repo_root, file_paths)` to `code_index.py`:

```python
def classify_files(conn, repo_root, file_paths):
    """Classify files as added/changed/deleted/unchanged.

    Fast-pass: stat() for size + mtime_ns. If both match the files table, skip.
    Slow-pass: if either differs, compute sha256 and compare content_sha256.
    """
    -> {"added": [...], "changed": [...], "deleted": [...], "unchanged": [...]}
```

- Read existing fingerprints from `files` table in one query
- For each file: `stat()` -> compare `(size_bytes, mtime_ns)`
- Only compute `sha256` when stat differs (handles `touch` without edit)
- Files in DB but not on disk -> `deleted`
- Files on disk but not in DB -> `added`

**Acceptance:**
- First run: all files classified as `added`
- Second run (no changes): all files classified as `unchanged`, sha256 never computed
- After editing one file: only that file is `changed`
- After deleting a file: it appears in `deleted`

### S1.3: Language detection and grammar loading

Add `LANGUAGE_MAP` dict and `load_grammar(language)`:

```python
LANGUAGE_MAP = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp",
    ".rb": "ruby", ".php": "php",
    ".sh": "bash", ".bash": "bash",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".json": "json",
    ".md": "markdown",
}
```

- `detect_language(path) -> str | None` from extension
- `load_grammar(language) -> tree_sitter.Language | None` — lazy, cached per language
- Graceful degradation: if grammar import fails, log warning once, return None
- Files without grammar get indexed as text-only (files table, no symbols/edges)

**Acceptance:**
- `detect_language("foo.py")` returns `"python"`
- `load_grammar("python")` returns a `Language` object (when installed)
- `load_grammar("unknown")` returns `None` without crashing
- Warning logged once per missing language per run

### S1.4: Symbol extraction from AST

Add `extract_symbols(tree, source_bytes, language, file_id)`:

- Walk the tree-sitter AST
- Extract node types per language:
  - Python: `function_definition`, `class_definition`, `decorated_definition`
  - JS/TS: `function_declaration`, `class_declaration`, `arrow_function`,
    `method_definition`, `interface_declaration`, `type_alias_declaration`
  - Go: `function_declaration`, `method_declaration`, `type_declaration`
  - Generic fallback for other languages: top-level definitions only
- For each symbol, extract: name, kind, start_line, end_line, signature (first line),
  docstring (immediately preceding comment or first string in body)
- Build `qualified_name` as `"module.ClassName.method_name"` by walking parent chain
- Per-file timeout: 10s base + 10s per 100KB

**Acceptance:**
- Python file with 3 functions and 1 class -> 4 symbols + methods inside class
- Each symbol has name, kind, lines, signature
- Docstrings extracted where present
- Timeout on pathological files (not crash)

### S1.5: Edge extraction (imports, calls)

Add `extract_edges(tree, source_bytes, language, file_symbols, all_symbol_names)`:

- **Import edges:** parse import statements per language
  - Python: `import_statement`, `import_from_statement`
  - JS/TS: `import_statement`, `require` calls
  - Go: `import_declaration`
- **Call edges:** `call_expression` nodes -> match callee name against known symbols
  - Resolution pass 1: import-based (follow import to find target symbol)
  - Resolution pass 2: name-matching within file scope and imported scope
- Unresolved calls: skip silently (v1 simplicity, no `unresolved_refs` table)
- Confidence: 1.0 for exact match, 0.8 for receiver-method, 0.5 for name-only

**Acceptance:**
- `from foo import bar` in file A + `def bar()` in file B -> import edge A->B
- `bar()` call in file A after importing bar -> call edge
- Unknown calls silently skipped

### S1.6: Full index pipeline (`index_all`)

Wire stages 1-4 together in `CodeIndex.index_all(repo_root)`:

```python
def index_all(self, repo_root: Path, max_files: int = 5000) -> IndexResult:
    """Full or incremental index of the project."""
    files = walk_files(repo_root)
    classified = classify_files(self.conn, repo_root, files)

    # Delete removed files (CASCADE cleans symbols + edges)
    for path in classified["deleted"]:
        self.conn.execute("DELETE FROM files WHERE path = ?", (path,))

    # Parse added + changed files
    to_parse = classified["added"] + classified["changed"]
    for path in to_parse:
        # ... parse, extract symbols, extract edges, write to DB

    # Update project_metadata
    # VACUUM if >20% churn

    return IndexResult(
        added=len(classified["added"]),
        changed=len(classified["changed"]),
        deleted=len(classified["deleted"]),
        unchanged=len(classified["unchanged"]),
        symbols=total_symbols,
        edges=total_edges,
        duration_ms=elapsed,
    )
```

**Acceptance:**
- Full index of code-dreaming itself (66 files) completes in <10 seconds
- `IndexResult` has correct counts
- Second run with no changes: 0 added, 0 changed, 0 deleted, all unchanged
- Edit one file -> only that file re-parsed, correct symbol/edge counts

### S1.7: CLI entry point

Add `main()` with argparse:

```
python3 scripts/code_index.py --repo-root . --db .code-dreaming/code-index.db
    [--max-files 5000] [--max-commits 200] [--languages python,javascript]
```

- Creates `.code-dreaming/` directory if needed
- Prints human-readable summary: `"Indexed 66 files, 312 symbols, 89 edges (3.2s)"`
- Exit code 0 on success

**Acceptance:**
- `python3 scripts/code_index.py --repo-root . --db /tmp/test.db` works
- Output includes file/symbol/edge counts and duration
- DB file created at specified path

## Definition of Done

- [ ] `code_index.py` implements full 4-stage pipeline
- [ ] `test_code_index.py` covers: schema creation, walk, classify, parse, index_all, incremental
- [ ] Index of code-dreaming repo completes in <10s
- [ ] Incremental run after no changes completes in <200ms
- [ ] Graceful degradation when tree-sitter grammar missing
