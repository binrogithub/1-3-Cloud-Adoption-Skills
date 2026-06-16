# E7: Team Sharing & Artifact

**Depends on:** E1  
**Blocks:** E9  
**Parallel with:** E6, E8  
**Estimate:** 0.5 day  
**PRD sections:** 9.1, 9.2

## Goal

Enable teams to share the code-index.db via git so new team members get instant
project understanding without waiting for a full index build. Uses zstd
compression and git merge=ours strategy (pattern from codebase-memory-mcp).

## Stories

### S7.1: zstd export

Add `CodeIndex.export_artifact(output_path)` to `code_index.py`:

```python
def export_artifact(self, output_path: Path) -> dict:
    """Export code-index.db as a zstd-compressed artifact."""
```

- Checkpoint WAL first: `PRAGMA wal_checkpoint(TRUNCATE)`
- Compress DB file with zstd (level 3 — fast, ~3:1 ratio on SQLite)
- Write compressed bytes to `output_path` (e.g., `.maas-dreaming/code-index.db.zst`)
- Write `artifact.json` alongside with metadata:
  ```json
  {
    "schema_version": 1,
    "files_count": 66,
    "symbols_count": 312,
    "compressed_size": 45678,
    "uncompressed_size": 163840,
    "created_at": "2026-06-15T10:30:00Z",
    "git_commit": "abc1234"
  }
  ```
- Use Python `zstandard` library (add to pyproject.toml optional deps)

**Acceptance:**
- Export produces `.db.zst` + `artifact.json`
- Compressed file is significantly smaller than raw DB
- `artifact.json` has correct metadata

### S7.2: zstd import

Add `CodeIndex.import_artifact(artifact_path)` as a classmethod:

```python
@classmethod
def import_artifact(cls, artifact_path: Path, db_path: Path) -> "CodeIndex":
    """Import a zstd-compressed code-index artifact."""
```

- Decompress `.db.zst` to `db_path`
- Verify schema version matches
- Open and return a CodeIndex instance
- If existing DB is newer (by last_indexed timestamp), skip import

**Acceptance:**
- Import from `.db.zst` produces a working code-index.db
- Schema version mismatch: error with message
- Existing newer DB: skip with message

### S7.3: .gitattributes merge strategy

Add or update `.maas-dreaming/.gitattributes`:

```
code-index.db.zst merge=ours
artifact.json merge=ours
```

This ensures that on merge conflicts, the local version wins (team members
regenerate from their own repo state).

Create a setup helper:

```python
def setup_git_merge_strategy(repo_root: Path):
    """Configure merge=ours for artifact files."""
```

- Write `.gitattributes` if not present
- Append entries if `.gitattributes` exists but lacks them
- Add `.maas-dreaming/code-index.db` to `.gitignore` (raw DB stays local)

**Acceptance:**
- `.gitattributes` has merge=ours entries
- `.gitignore` excludes raw DB but NOT the compressed artifact
- Git merge of conflicting artifacts: local version wins

### S7.4: CLI commands for team sharing

Add `mce artifact export` and `mce artifact import`:

```
mce artifact export [--output .maas-dreaming/code-index.db.zst]
mce artifact import [--input .maas-dreaming/code-index.db.zst]
                    [--db .maas-dreaming/code-index.db]
```

- `export`: delegates to `CodeIndex.export_artifact()`
- `import`: delegates to `CodeIndex.import_artifact()`
- Human-readable output: compression ratio, file count, timing

**Acceptance:**
- Export + import round-trip: identical query results
- Import on first clone: instant project understanding
- CLI output shows compression ratio

## Definition of Done

- [ ] `export_artifact()` and `import_artifact()` methods work
- [ ] `.gitattributes` merge strategy configured
- [ ] `mce artifact export/import` CLI commands work
- [ ] Round-trip test: export -> import -> queries return same results
- [ ] `zstandard` added to pyproject.toml optional dependencies
