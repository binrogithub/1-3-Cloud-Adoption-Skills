# E4: Code Queries API

**Depends on:** E0, E1  
**Blocks:** E5, E6  
**Parallel with:** E6, E7 (after E1)  
**Estimate:** 1 day  
**PRD sections:** 5.1

## Goal

Provide a Python API over the code-index SQLite database that the dream report,
MCE CLI, and MCP tools can call to answer questions about project structure.
Each query is a method on `CodeQueries` that returns structured data (dicts/lists).

## Stories

### S4.1: CodeQueries class skeleton

Create `scripts/code_queries.py`:

```python
class CodeQueries:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()
```

**Acceptance:**
- Opens an existing code-index.db read-only
- Usable as context manager (`__enter__` / `__exit__`)

### S4.2: `overview()` — project summary

```python
def overview(self) -> dict:
    """Return high-level project metrics."""
    return {
        "total_files": ...,
        "total_symbols": ...,
        "total_edges": ...,
        "total_commits": ...,
        "languages": {"python": 42, "javascript": 12, ...},
        "top_files_by_symbols": [...],  # top 10
        "last_indexed": ...,
    }
```

- Aggregate queries: `COUNT(*)` on files/symbols/edges/commits
- Language distribution: `GROUP BY language`
- Top files: `ORDER BY symbol_count DESC LIMIT 10`
- Last indexed: `MAX(indexed_at)` from files

**Acceptance:**
- Returns all fields populated
- On empty DB: zeros everywhere, empty lists

### S4.3: `search(query, limit)` — FTS5 symbol search

```python
def search(self, query: str, limit: int = 20) -> list[dict]:
    """Full-text search across symbol names, signatures, and docstrings."""
```

- Use `symbols_fts` FTS5 table with `MATCH` query
- Return: symbol name, kind, file path, line, signature, snippet (highlight)
- Handle FTS5 special characters: escape `*`, `"`, parentheses in user input
- If query is empty or FTS returns nothing, fall back to LIKE search on name

**Acceptance:**
- `search("parse")` finds `parse_git_log`, `parse_frontmatter`, etc.
- `search("class CodeIndex")` finds the class definition
- Empty query returns empty list (not error)
- Special characters in query don't crash

### S4.4: `file_symbols(path)` — symbols in one file

```python
def file_symbols(self, path: str) -> list[dict]:
    """Return all symbols defined in a file, ordered by line."""
```

- JOIN symbols + files on file_id
- Return: name, kind, start_line, end_line, signature, visibility
- Ordered by start_line ASC

**Acceptance:**
- `file_symbols("scripts/dream.py")` returns functions/classes in line order
- Non-existent path returns empty list

### S4.5: `callers(symbol_name)` / `callees(symbol_name)` — call graph

```python
def callers(self, symbol_name: str) -> list[dict]:
    """Find all symbols that call the given symbol."""

def callees(self, symbol_name: str) -> list[dict]:
    """Find all symbols called by the given symbol."""
```

- Query edges table with kind='calls' / kind='imports'
- Match by `name` or `qualified_name` (fuzzy: name-only if qualified has no match)
- Return: caller/callee name, file, line, confidence

**Acceptance:**
- `callers("render_report")` shows who calls it
- `callees("index_all")` shows what it calls
- Unknown symbol returns empty list

### S4.6: `coupling(path, min_score)` — file coupling from git

```python
def coupling(self, path: str, min_score: float = 0.3) -> list[dict]:
    """Files frequently changed together with the given file."""
```

- Query edges with kind='file_changes_with' or query commit_files directly
- Return: coupled file path, co-commit count, Jaccard score
- Ordered by score DESC

**Acceptance:**
- Files that always change together have score near 1.0
- `min_score` filter works
- File with no coupling returns empty list

### S4.7: `changes_since(date)` — recent changes

```python
def changes_since(self, since: str) -> list[dict]:
    """Return commits and files changed since a date."""
```

- Query commits + commit_files WHERE date >= since
- Return: list of commits with nested file changes
- Date format: ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`)

**Acceptance:**
- Returns commits newer than the date
- Each commit includes file list with additions/deletions
- Future date returns empty list

## Definition of Done

- [ ] `code_queries.py` exists with all query methods
- [ ] `test_code_queries.py` with fixture DB covers: overview, search, file_symbols, callers, callees, coupling, changes_since
- [ ] Each method handles edge cases (empty DB, unknown paths, malformed input)
- [ ] FTS5 search handles special characters without crashing
