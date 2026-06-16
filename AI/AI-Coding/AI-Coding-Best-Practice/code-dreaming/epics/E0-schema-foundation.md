# E0: Schema & Foundation

**Depends on:** nothing  
**Blocks:** E1, E2, E4, E5, E6, E7, E8  
**Estimate:** 0.5 day  
**PRD sections:** 3.1, 3.2, 8.1

## Goal

Create the SQLite database schema, the `CodeIndex` class skeleton (open/create/
close/migrate), and add `tree-sitter` to `pyproject.toml`. This is the
foundation every other epic builds on.

## Stories

### S0.1: SQLite schema DDL

Create `scripts/code_index.py` with the full schema from PRD 3.2:

- `schema_version` table (migration tracking)
- `files` table (path, language, size, mtime_ns, content_sha256, indexed_at)
- `symbols` table (name, qualified_name, kind, lines, signature, docstring, visibility)
- `edges` table (source_id, target_id, kind, confidence, line, metadata)
- `commits` table (hash, author, date, message)
- `commit_files` table (commit_id, file_path, change_type, additions, deletions)
- `symbols_fts` FTS5 virtual table with sync triggers (ai/ad/au)
- `project_metadata` key-value store
- All indexes from PRD 3.2

The `create_schema(conn)` function executes all DDL in a single transaction.

**Acceptance:**
- `create_schema()` creates all tables, indexes, triggers, FTS on a fresh `:memory:` DB
- Schema version 1 is inserted into `schema_version`
- `PRAGMA journal_mode = WAL` is set

### S0.2: CodeIndex class skeleton

```python
class CodeIndex:
    def __init__(self, db_path: Path):
        ...

    @classmethod
    def open_or_create(cls, db_path: Path) -> "CodeIndex":
        """Open existing DB or create a new one with fresh schema."""

    def close(self):
        """Close the SQLite connection."""

    def schema_version(self) -> int:
        """Return current schema version."""

    def _migrate(self):
        """Apply pending migrations (for future schema changes)."""
```

**Acceptance:**
- `CodeIndex.open_or_create(path)` creates a new DB with schema when file doesn't exist
- `CodeIndex.open_or_create(path)` opens an existing DB and checks schema version
- `close()` cleanly closes the connection
- WAL mode is enabled on open

### S0.3: pyproject.toml dependencies

Add to `[project.dependencies]`:

```toml
tree-sitter >= 0.23
```

Add to `[project.optional-dependencies]`:

```toml
languages = [
    "tree-sitter-python >= 0.23",
    "tree-sitter-javascript >= 0.23",
    "tree-sitter-typescript >= 0.23",
]
```

**Acceptance:**
- `pip install -e .` succeeds
- `pip install -e ".[languages]"` installs tree-sitter grammars
- Existing tests still pass

### S0.4: Grammar installation helper

Create `assets/tree-sitter/install_grammars.py`:

```python
"""Install tree-sitter language grammars.

Usage: python3 install_grammars.py [--languages python,javascript,typescript]
       python3 install_grammars.py --all
"""
```

Maps language names to pip package names. Installs via subprocess.
Reports which grammars are available and which are missing.

**Acceptance:**
- `python3 install_grammars.py --languages python` installs `tree-sitter-python`
- `python3 install_grammars.py --check` lists installed vs missing grammars
- Exit code 0 when all requested grammars installed, 1 otherwise

## Definition of Done

- [ ] `code_index.py` exists with schema DDL + CodeIndex class skeleton
- [ ] `install_grammars.py` exists and can install/check grammars
- [ ] `pyproject.toml` updated with tree-sitter dependencies
- [ ] All existing tests pass (`pytest`)
- [ ] A test can create a CodeIndex, verify schema, and close it
