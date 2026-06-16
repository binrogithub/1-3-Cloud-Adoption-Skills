# PRD v2: code-dreaming as Project Knowledge Continuous Maintenance Engine

**Status:** Draft  
**Author:** AI-assisted  
**Date:** 2026-06-15  
**Supersedes:** Current SKILL.md (memory-only dreaming)

---

## 1. Problem Statement

### 1.1 Current State

code-dreaming is a memory hygiene skill that deduplicates, validates, and
compresses *existing* Claude Code / Mem0 memory files. Its data sources are:

- Claude Code session `.jsonl` transcripts (conversation logs)
- Pre-existing structured memory files (`memory/episodic/*.md`)

It **does not** scan source code, read git history, or analyze project structure.
On a project with no prior memory artifacts — even one with 66 source files and
142 git commits — the skill produces zero actionable output.

### 1.2 Target State

Transform code-dreaming into a **two-layer project knowledge engine**:

| Layer | Source | Engine | Output |
|-------|--------|--------|--------|
| L1: Code Structure Index | Source files + git history | Deterministic (tree-sitter AST + git log) | SQLite knowledge graph |
| L2: Knowledge Accumulation | L1 diffs + conversation trajectory + existing memory | LLM-assisted (host agent) | Structured memory files |

**Key property:** A brand-new session on any project can invoke `/code-dreaming`
once and get a useful project knowledge snapshot. Subsequent runs are
incremental — only changed files are re-analyzed, and new knowledge merges into
the existing knowledge base.

### 1.3 Design Principles

1. **No runtime dependencies beyond Python stdlib + tree-sitter.** The skill
   must work on air-gapped machines with no npm/Node.js/Rust toolchain.
2. **Vendored, not integrated.** CodeGraph-inspired code is copied and adapted
   into Python, not installed as an npm package. The skill remains a
   self-contained directory.
3. **Incremental by default.** First run does a full scan; subsequent runs use a
   manifest (size + mtime + content hash) to process only changed files.
4. **Deterministic L1, LLM-assisted L2.** Code structure indexing is pure
   computation — no LLM calls. Knowledge synthesis (summaries, architecture
   descriptions) uses the host agent.
5. **Governance preserved.** Never auto-edit `CLAUDE.md` or `AGENTS.md`. All
   proposed changes go to `inbox/` for human review.
6. **Backward compatible.** Existing memory-only dreaming continues to work.
   The code index is an additive layer.

---

## 2. Architecture Overview

```
/code-dreaming (default invocation)
    |
    v
[Phase 0: Cold-Start Gate]
    |--- No code index AND no memory AND no multi-session trajectory?
    |       --> Fast-path: run Phase 1 (code index), skip Phase 2
    |
    v
[Phase 1: Code Structure Index] .............. DETERMINISTIC, NO LLM
    |--- scripts/code_index.py
    |       tree-sitter parse -> SQLite graph
    |       git log adapter -> commit trajectory
    |       Incremental: manifest-based (size+mtime+sha256)
    |       Output: .code-dreaming/code-index.db
    |
    v
[Phase 2: Dream Report + Maintenance] ........ EXISTING + ENHANCED
    |--- scripts/dream_agent_report.py (enhanced)
    |       Now reads code-index.db as an additional trajectory source
    |       Signal scan filters by role (fixes false positives)
    |       Cold-start message when no real signals exist
    |
    |--- scripts/dream.py (existing, unchanged)
    |       dedup / stale-path / L3 index / conflict detection
    |       Automatically invoked in dry-run when memory files exist
    |
    v
[Phase 3: Host Agent Synthesis] .............. LLM (HOST AGENT)
    |--- The host agent that loaded the skill reads the report
    |    and code-index summary to produce durable memory candidates
    |
    v
[Output Artifacts]
    .code-dreaming/code-index.db ........... SQLite knowledge graph
    .code-dreaming/code-index.manifest.json  Incremental fingerprints
    .code-dreaming/DREAMS.md ............... Report index
    memory/inbox/dream-agent-*.report.md ... Dream report
    memory/inbox/conflict-*.md ............. Conflict candidates
    memory/inbox/claude-md.proposed.patch ... CLAUDE.md patch proposal
```

---

## 3. Layer 1: Code Structure Index (`scripts/code_index.py`)

### 3.1 Capability Summary

A new Python module that builds a SQLite knowledge graph from source code and
git history. Inspired by CodeGraph's architecture but implemented in Python
with `py-tree-sitter` — no Node.js dependency.

### 3.2 Data Model (SQLite Schema)

Design informed by CodeGraph (MIT, `nodes`/`edges`/`files` tables with FTS5)
and codebase-memory-mcp (MIT, 13 node labels, 20+ edge types, Cypher engine).
Simplified for Python stdlib sqlite3; no Cypher engine in v1.

```sql
-- pragma: WAL mode for concurrent reads during dream report generation
PRAGMA journal_mode = WAL;

-- Schema version for future migrations
CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  INTEGER NOT NULL,
    description TEXT
);

-- File registry with incremental fingerprints
-- (CodeGraph pattern: size + mtime fast-pass, content hash on mismatch)
CREATE TABLE files (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,     -- relative to repo root
    language    TEXT,                      -- detected from extension
    size_bytes  INTEGER NOT NULL,
    mtime_ns    INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,          -- for incremental detection
    node_count  INTEGER DEFAULT 0,        -- symbols in this file
    indexed_at  REAL NOT NULL,            -- unix timestamp
    errors      TEXT                       -- parse errors if any
);

-- Symbols extracted by tree-sitter
-- kind values aligned with CodeGraph NodeKind:
--   file, module, class, struct, interface, trait, function, method,
--   property, field, variable, constant, enum, enum_member, type_alias,
--   namespace, import, export, route, component
CREATE TABLE symbols (
    id          INTEGER PRIMARY KEY,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    qualified_name TEXT,                  -- e.g. "module.ClassName.method_name"
    kind        TEXT NOT NULL,
    start_line  INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    signature   TEXT,                     -- function signature / class declaration
    docstring   TEXT,                     -- extracted doc comment (first 500 chars)
    visibility  TEXT,                     -- public|private|protected|internal
    is_exported INTEGER DEFAULT 0,
    is_async    INTEGER DEFAULT 0,
    decorators  TEXT                      -- JSON array of decorator names
);

-- Relationships between symbols
-- kind values aligned with CodeGraph EdgeKind:
--   contains, calls, imports, exports, extends, implements,
--   references, type_of, returns, instantiates, overrides, decorates
-- Plus codebase-memory-mcp additions:
--   similar_to (MinHash/Jaccard), tests, file_changes_with (git coupling)
CREATE TABLE edges (
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_id   INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,        -- 1.0=exact, 0.8=receiver, 0.5=fuzzy
    line        INTEGER,                  -- call site line number
    metadata    TEXT                       -- JSON blob for extra context
);

-- Git commit history (bounded)
CREATE TABLE commits (
    id          INTEGER PRIMARY KEY,
    hash        TEXT UNIQUE NOT NULL,
    author      TEXT,
    date        TEXT,                     -- ISO 8601
    message     TEXT,                     -- first line only
    files_changed INTEGER
);

-- Files changed per commit (for coupling analysis)
CREATE TABLE commit_files (
    commit_id   INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    file_path   TEXT NOT NULL,
    change_type TEXT,                     -- A(dd) M(odify) D(elete) R(ename)
    additions   INTEGER DEFAULT 0,
    deletions   INTEGER DEFAULT 0
);

-- Full-text search over symbols (content-sync triggers like CodeGraph)
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name, qualified_name, signature, docstring,
    content=symbols, content_rowid=id
);

-- Keep FTS in sync on INSERT/DELETE/UPDATE (CodeGraph pattern)
CREATE TRIGGER symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
    VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
END;
CREATE TRIGGER symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
END;
CREATE TRIGGER symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
    INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
    VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
END;

-- Project metadata key-value store
CREATE TABLE project_metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  INTEGER NOT NULL
);

-- Indexes
CREATE INDEX idx_files_language ON files(language);
CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_kind ON symbols(kind);
CREATE INDEX idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_kind ON edges(kind);
CREATE INDEX idx_commit_files_path ON commit_files(file_path);
```

### 3.3 Indexing Pipeline (4-stage, CodeGraph-inspired)

```
Stage 1: Walk & Fingerprint
    Prefer `git ls-files` when available (respects .gitignore at all
    levels); fall back to os.walk() with IGNORED_DIRS for non-git projects.
    (CodeGraph pattern: git-first discovery.)

    For each text file: stat() for (size, mtime_ns).
    Fast-pass: if size AND mtime_ns match the `files` table row, skip.
    Slow-pass: if either differs, compute sha256 and compare.
    (CodeGraph's 3-layer reconciliation: stat -> hash -> reindex.)

    Classify files into: added, changed, deleted, unchanged.

Stage 2: Parse (tree-sitter)
    For each added/changed file:
        Detect language from extension (LANGUAGE_MAP dict).
        Load py-tree-sitter grammar (lazy, cached per language).
        Parse AST -> extract nodes (functions, classes, methods, etc.)
        Extract edges: imports, calls, extends/implements.
        Per-file timeout: 10s base + 10s per 100KB (CodeGraph pattern).

    For deleted files: DELETE FROM files WHERE path=? (CASCADE cleans
    symbols + edges automatically).

    Reference resolution (simplified from CodeGraph's 3-pass):
    Pass 1: import-based resolution (ES6/Python/Java patterns).
    Pass 2: name-matching within file and imported scope.
    Unresolved references logged but not stored (v1 simplicity).

Stage 3: Git History
    git log --format='%H|%an|%aI|%s' --numstat -N
    Parse into commits + commit_files tables.
    Bounded: default last 200 commits (configurable --max-commits).
    Incremental: only fetch commits newer than latest in DB.

    Derive file_changes_with edges: files that change together in
    >3 commits get an edge with Jaccard confidence score.
    (Inspired by codebase-memory-mcp's FILE_CHANGES_WITH edges.)

Stage 4: Reconcile & Compact
    Update project_metadata: file_count, symbol_count, edge_count,
    language_breakdown, last_indexed_at, index_mode (full/incremental).
    VACUUM if significant churn (>20% of files changed).
    Print summary: "Indexed N files, M symbols, K edges (Xms)"
```

### 3.4 Tree-Sitter Language Support

Bundled via `py-tree-sitter` + language grammars installed as Python wheels:

| Priority | Languages | Grammar Package |
|----------|-----------|-----------------|
| P0 (ship) | Python, JavaScript, TypeScript, Go, Rust, Java, C, C++ | `tree-sitter-python`, etc. |
| P1 (fast-follow) | Ruby, PHP, C#, Kotlin, Swift, Scala | same pattern |
| P2 (on-demand) | Shell/Bash, SQL, YAML, TOML, Markdown | structural, not full AST |

Installation: `pip install tree-sitter tree-sitter-python tree-sitter-javascript ...`

Graceful degradation: if a grammar is not installed, the file is indexed as
text-only (path + size + hash in `files`, no symbols/edges). A warning is
emitted once per missing language per run.

### 3.5 Incremental Sync

Identical pattern to CodeGraph's reconciliation and the existing
`scan_to_dream.py` manifest:

```python
def needs_reindex(path: Path, manifest_row: dict | None) -> bool:
    stat = path.stat()
    if manifest_row is None:
        return True  # new file
    if stat.st_size != manifest_row["size_bytes"]:
        return True  # size changed
    if stat.st_mtime_ns != manifest_row["mtime_ns"]:
        # mtime changed -> check content hash (handles touch without edit)
        return sha256(path) != manifest_row["content_sha256"]
    return False  # fingerprint match -> skip
```

First run: full scan. Typical project (500 files) completes in 2-5 seconds.
Incremental run after editing 3 files: <200ms.

### 3.6 Query Interface

The code index exposes a Python API consumed by `dream_agent_report.py` and
the host agent:

```python
from scripts.code_index import CodeIndex

idx = CodeIndex(".code-dreaming/code-index.db")

# Project overview (for cold-start report)
overview = idx.project_overview()
# -> {files: 66, languages: {Python: 40, Shell: 8, ...},
#     symbols: 312, top_modules: [...], recent_commits: [...]}

# Symbol lookup
idx.find_symbol("dream_agent_report")
# -> [{name, kind, file, line, signature, callers, callees}]

# File coupling (from git history)
idx.coupled_files("scripts/dream.py")
# -> [("scripts/dream_signals.py", 0.85), ("tests/test_dream.py", 0.72)]

# What changed since last dream?
idx.changes_since(last_dream_timestamp)
# -> {added: [...], modified: [...], deleted: [...],
#     new_commits: [...], affected_symbols: [...]}

# Full-text search over symbols
idx.search("trajectory adapter")
# -> ranked list of matching symbols with context
```

### 3.7 Output Location

```
<repo>/.code-dreaming/
    code-index.db           # SQLite knowledge graph
    code-index.db.zst       # Optional: zstd-compressed snapshot for git sharing
    .gitignore              # Ignore code-index.db (binary); track .zst if sharing
```

The `.code-dreaming/` directory follows the existing `--output-mode project-root`
pattern. The DB is local and regenerable; teams can optionally share the
compressed snapshot via git (codebase-memory-mcp pattern):

```
.code-dreaming/
    code-index.db           # Working SQLite (gitignored)
    code-index.db.zst       # zstd-compressed snapshot (git-tracked, optional)
    artifact.json           # Metadata: schema version, git commit, counts
    .gitignore              # code-index.db (binary), *.db-wal, *.db-shm
    .gitattributes          # code-index.db.zst merge=ours binary
```

**Team bootstrap flow** (from codebase-memory-mcp):
1. Developer A runs `/code-dreaming` -> full index -> exports `code-index.db.zst`
2. Commits `.code-dreaming/` directory
3. Developer B clones -> `/code-dreaming` detects artifact -> decompresses ->
   runs incremental delta to catch local changes
4. Near-instant onboarding instead of full re-index

---

## 4. Layer 1b: Git History Adapter (`scripts/git_adapter.py`)

### 4.1 Purpose

A trajectory source adapter that reads `git log` and produces evidence records
compatible with the existing `dream_sources.py` framework. This gives the dream
report access to project history without requiring prior Claude Code sessions.

### 4.2 Implementation

```python
def read_git_history(
    repo_root: Path,
    max_commits: int = 200,
    since_date: str | None = None,
) -> TrajectoryResult:
    """Read git log as dream trajectory evidence."""
    cmd = ["git", "-C", str(repo_root), "log",
           f"--max-count={max_commits}",
           "--format=%H|%an|%aI|%s",
           "--numstat"]
    if since_date:
        cmd.append(f"--since={since_date}")
    # Parse output into EvidenceRecord instances
    # Each commit becomes one record with:
    #   evidence_id = "git-" + short_hash
    #   timestamp = author date
    #   role = "git"
    #   tool = "commit"
    #   preview = "subject | N files | +A -D"
    #   project_match = True (always, it's this repo's own history)
```

### 4.3 Integration Point

`dream_sources.py` `discover_source()` gains a new fallback: when no `.jsonl`
or `.db` trajectory exists, try `read_git_history()`. This means the dream
report always has *something* to analyze on any git repo.

Priority order (unchanged for existing sources, git added as fallback):
1. Explicit `--trajectory` path
2. `mimocode.db` / `trajectory.db`
3. `*.jsonl` session transcripts
4. **`git log` (new fallback)**

---

## 5. Enhanced Dream Report (`dream_agent_report.py` v2)

### 5.1 Changes to Default `/code-dreaming` Behavior

The default invocation now runs a **three-phase pipeline**:

```
Step 1: Code index (deterministic)
    python3 scripts/code_index.py --repo-root REPO --db .code-dreaming/code-index.db

Step 2: Dream report (enhanced)
    python3 scripts/dream_agent_report.py --repo-root REPO --code-index .code-dreaming/code-index.db

Step 3: Dream maintenance (if memory exists, dry-run)
    python3 scripts/dream.py --memory-dir DIR --repo-root REPO
```

Step 1 is always run; it creates or incrementally updates the code index.
Step 2 is always run; it now includes code-index data in the report.
Step 3 is run only when `memory/episodic/*.md` files exist.

### 5.2 Enhanced Report Sections

The dream report gains new sections from the code index:

```markdown
# Dreaming Summary Report

## Project Overview (from code index)
- files: 66 (Python: 40, Shell: 8, YAML: 4, ...)
- symbols: 312 (functions: 180, classes: 42, methods: 90)
- git: 142 commits, 5 contributors, active since 2025-11-20
- last indexed: 2026-06-15T18:32:00Z (incremental, 3 files changed)

## Changes Since Last Dream
- Modified: scripts/dream_agent_report.py (+45 -12)
- Modified: scripts/dream_signals.py (+8 -3)
- Added: scripts/code_index.py (new file, 450 lines)
- 12 new commits since last dream

## Signal Scan (trajectory + git)
- corrections=0, preferences=1, decisions=2, recurring=0
  (signal scan now filters by role; system attachments excluded)

## Evidence Preview
  (existing, plus git commit evidence when no session trajectory)

## Code Structure Highlights
- Entry points: scripts/dream_agent_report.py:main, mce/cli.py:main
- Most-coupled files: dream.py <-> dream_signals.py (0.85)
- Largest modules: dream.py (758 lines), dream_llm.py (350 lines)

## Candidates
- Review-only scaffold. Host agent adds durable candidates.
```

### 5.3 Signal Scan Fixes

`dream_signals.py` `scan_records()` gains a role filter:

```python
def scan_records(records, limit=20, require_role=("user",)):
    """Only classify records from meaningful roles."""
    for record in records:
        role = getattr(record, "role", "") or ""
        if require_role and role not in require_role:
            continue  # skip system/attachment/metadata records
        ...
```

This eliminates the false-positive correction from the skill's own description.

### 5.4 Cold-Start Gate

When all three conditions hold:
- No existing memory files (`MEMORY.md` / `memory/episodic/*.md`)
- No multi-session trajectory (only current session or no `.jsonl`)
- No code index exists yet

The report includes a clear message and immediately triggers Phase 1 (code
index) so the user gets something useful on first run:

```
First run detected — building project knowledge index.
Scanning 66 files and 142 git commits...
Code index created: .code-dreaming/code-index.db (312 symbols, 142 commits)

Memory dreaming will become more valuable after several coding sessions
accumulate memory entries and trajectory data.
```

---

## 6. Integration with Existing Components

### 6.1 Unchanged Modules

| Module | Status |
|--------|--------|
| `scripts/dream.py` | Unchanged — dedup/stale-path/L3/conflict detection |
| `scripts/reset_memory.py` | Unchanged |
| `scripts/distill.py` | Unchanged |
| `scripts/dream_llm.py` | Unchanged |
| `mce/backbone.py` | Unchanged — Mem0 backbone wrapper |
| `mce/writeback.py` | Unchanged — verified candidate writeback |
| `mce/policy.py` | Unchanged |
| `mce/retrieve.py` | Enhanced — can search code-index.db in addition to memory FTS |
| `mce/executor.py` | Enhanced — new `code-index` plan |
| `mce/cli.py` | Enhanced — new `index` subcommand |

### 6.2 New Modules

| Module | Purpose | Lines (est.) |
|--------|---------|-------------|
| `scripts/code_index.py` | Tree-sitter indexer + SQLite graph + incremental sync | ~600 |
| `scripts/git_adapter.py` | Git history → TrajectoryResult adapter | ~150 |
| `scripts/code_queries.py` | Query API over code-index.db (overview, search, coupling) | ~200 |

### 6.3 Modified Modules

| Module | Change |
|--------|--------|
| `scripts/dream_agent_report.py` | Accept `--code-index`, render project overview + changes-since sections |
| `scripts/dream_signals.py` | Add `require_role` filter to `scan_records()` |
| `scripts/dream_sources.py` | Add git fallback to `discover_source()`, import `git_adapter` |
| `scripts/scan_to_dream.py` | Can read from code-index.db instead of walking the filesystem |
| `SKILL.md` | Updated default behavior, new operations table entries |

### 6.4 New Operations Table

| Op | Command |
|----|---------|
| **code-index** (build/update) | `python3 scripts/code_index.py --repo-root REPO [--db PATH] [--languages PY,JS,...] [--max-commits N]` |
| code-query (search) | `python3 scripts/code_queries.py --db PATH --query "..." [--kind symbol\|file\|commit]` |
| code-overview (project summary) | `python3 scripts/code_queries.py --db PATH --overview` |
| code-changes (since last dream) | `python3 scripts/code_queries.py --db PATH --changes-since TIMESTAMP` |
| code-coupling (file coupling) | `python3 scripts/code_queries.py --db PATH --coupling PATH` |

### 6.5 CLI Integration

```bash
# New subcommand
python -m mce.cli index --repo-root . [--db .code-dreaming/code-index.db]

# Existing subcommands unchanged
python -m mce.cli dream ...
python -m mce.cli distill ...
python -m mce.cli retrieve --query "..." --max-items 5
python -m mce.cli capture --text "..." --org acme
python -m mce.cli writeback ...
```

---

## 7. Incremental Dreaming Lifecycle

### 7.1 First Run (Cold Start)

```
User: /code-dreaming

1. code_index.py: Full scan
   - Walk all files -> parse with tree-sitter -> symbols + edges
   - git log --max-count=200 -> commits + commit_files
   - Write code-index.db + manifest
   - Output: "Indexed 66 files, 312 symbols, 142 commits"

2. dream_agent_report.py: Report with code-index data
   - Project overview from code-index.db
   - Git history as trajectory evidence (fallback, no .jsonl)
   - Signal scan on git commits (role="git", filtered)
   - Candidates section: host agent synthesizes

3. Host agent: Summarize
   - "Project is a Python skill with 12 scripts, 12 test files..."
   - Write initial memory candidates if justified
```

### 7.2 Subsequent Run (Incremental)

```
User: /code-dreaming

1. code_index.py: Incremental update
   - Read manifest from code-index.db
   - Walk files: compare (size, mtime_ns) -> sha256 only if needed
   - Re-parse only 3 changed files
   - git log --since=<last_indexed> -> 5 new commits
   - Output: "Updated 3 files, 5 new commits (2ms)"

2. dream_agent_report.py: Report with changes-since
   - "Changes since last dream" section shows diffs
   - Session trajectory + git trajectory merged
   - Memory maintenance (dream.py dry-run) included if memory exists

3. Host agent: Merge into knowledge
   - New findings merged into existing memory
   - Stale entries updated based on code changes
```

### 7.3 Nightly (Automated)

```bash
# bin/dream-nightly.sh (enhanced)
code_index.py --repo-root . --db .code-dreaming/code-index.db
dream.py --memory-dir DIR --repo-root . [--apply]
dream_agent_report.py --repo-root . --code-index .code-dreaming/code-index.db
# Optionally: dream-llm.sh for LLM synthesis
```

---

## 8. Dependencies

### 8.1 Required (P0)

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `tree-sitter` | >=0.23 | AST parsing runtime | MIT |
| `tree-sitter-python` | >=0.23 | Python grammar | MIT |
| `tree-sitter-javascript` | >=0.23 | JS/JSX grammar | MIT |
| `tree-sitter-typescript` | >=0.23 | TS/TSX grammar | MIT |

All other code uses Python stdlib only (sqlite3, subprocess, hashlib, pathlib,
re, json, os).

### 8.2 Optional (P1)

Additional tree-sitter grammars: `tree-sitter-go`, `tree-sitter-rust`,
`tree-sitter-java`, `tree-sitter-c`, `tree-sitter-cpp`.

### 8.3 Existing Dependencies (Unchanged)

- `mem0` (vendored, Apache-2.0) — for Mem0 backbone writeback
- `yaml` — for mem0.config.yaml parsing
- `qdrant-client` — for vector store (optional)

### 8.4 No New Runtime Dependencies

- No Node.js / npm (unlike CodeGraph)
- No Rust toolchain (unlike codebase-memory-mcp / opencode-codebase-index)
- No external database servers (SQLite is stdlib)
- No API keys for L1 indexing (tree-sitter is local-only)

---

## 9. File Layout (After Implementation)

```
code-dreaming/
    SKILL.md                    # Updated
    AGENTS.md                   # Updated
    README.md
    runbook.md                  # Updated with code-index ops
    pyproject.toml              # Updated with tree-sitter deps

    scripts/
        code_index.py           # NEW: tree-sitter indexer + SQLite graph
        git_adapter.py          # NEW: git log -> TrajectoryResult
        code_queries.py         # NEW: query API over code-index.db
        dream_agent_report.py   # MODIFIED: code-index integration
        dream_signals.py        # MODIFIED: role filter
        dream_sources.py        # MODIFIED: git fallback
        dream.py                # UNCHANGED
        dream_llm.py            # UNCHANGED
        distill.py              # UNCHANGED
        reset_memory.py         # UNCHANGED
        scan_to_dream.py        # MODIFIED: can read from code-index.db
        should_run.py           # UNCHANGED
        build_skill.py          # UNCHANGED
        project_scope.py        # UNCHANGED

    mce/
        __init__.py             # UNCHANGED
        backbone.py             # UNCHANGED
        cli.py                  # MODIFIED: add `index` subcommand
        executor.py             # MODIFIED: add `code-index` plan
        policy.py               # UNCHANGED
        retrieve.py             # MODIFIED: search code-index.db
        writeback.py            # UNCHANGED

    assets/
        mem0.config.yaml        # UNCHANGED
        schemas/                # UNCHANGED
        tree-sitter/            # NEW: grammar installation helper
            install_grammars.py

    tests/
        test_code_index.py      # NEW
        test_git_adapter.py     # NEW
        test_code_queries.py    # NEW
        test_dream_agent_report.py  # UPDATED
        test_dream_signals.py       # UPDATED
        ... (existing tests unchanged)

    upstream/maas-code/         # UNCHANGED
    bin/                        # dream-nightly.sh updated
```

---

## 10. SKILL.md Changes (Default Behavior)

The default `/code-dreaming` section in SKILL.md changes to:

```markdown
## Default `/code-dreaming` behavior

The default `/code-dreaming` invocation runs a three-phase pipeline:

1. **Code index** (deterministic, no LLM):
   ```bash
   python3 BASE/scripts/code_index.py --repo-root REPO --db REPO/.code-dreaming/code-index.db
   ```
   Creates or incrementally updates the project code structure index. First run
   does a full tree-sitter parse + git log; subsequent runs only process changed
   files.

2. **Dream report** (deterministic + host-agent synthesis):
   ```bash
   python3 BASE/scripts/dream_agent_report.py --repo-root REPO --code-index REPO/.code-dreaming/code-index.db
   ```
   Generates a bounded report scaffold that now includes project overview, code
   structure highlights, and changes since last dream — in addition to the
   existing trajectory signal scan.

3. **Dream maintenance** (deterministic, only when memory exists):
   ```bash
   python3 BASE/scripts/dream.py --memory-dir DIR --repo-root REPO
   ```
   Runs dedup, stale-path validation, L3 compression, and conflict detection
   against existing memory files. Dry-run by default.

The host agent then reads the report and synthesizes durable memory candidates.
```

---

## 11. Governance & Safety

### 11.1 Preserved Invariants

- `CLAUDE.md` and `AGENTS.md` are **never** auto-edited
- All proposed changes go to `inbox/` as review artifacts
- Memory writes are ADD-only, scoped, and secret-filtered
- Dry-run by default for all destructive operations

### 11.2 Code Index Safety

- The code index is **read-only** with respect to source files — it never
  modifies code
- Git operations are read-only (`git log`, `git diff` — no `git checkout`,
  `git reset`, etc.)
- Tree-sitter parsing is sandboxed (pure computation, no execution)
- The `.code-dreaming/` directory is clearly separated from project source
- Secret redaction applies to code-index content previews

### 11.3 Incremental Safety

- Manifest fingerprints use SHA-256 content hashes (not just mtime) to prevent
  false-positive cache hits
- Deleted files are CASCADE-removed from the knowledge graph
- The manifest is stored inside the SQLite DB (single source of truth)
- `VACUUM` is throttled to prevent excessive disk I/O

---

## 12. Implementation Plan

### Phase 1: Core Code Index (P0, ~3 days)

1. `scripts/code_index.py` — tree-sitter indexer + SQLite schema + incremental sync
2. `scripts/git_adapter.py` — git log parser + TrajectoryResult integration
3. `scripts/code_queries.py` — overview, search, coupling, changes-since
4. `tests/test_code_index.py`, `tests/test_git_adapter.py`, `tests/test_code_queries.py`
5. `assets/tree-sitter/install_grammars.py` — helper to install language grammars

### Phase 2: Report Enhancement (P0, ~2 days)

1. `dream_agent_report.py` — accept `--code-index`, render new sections
2. `dream_signals.py` — add `require_role` filter
3. `dream_sources.py` — add git fallback to `discover_source()`
4. Cold-start gate with user-friendly messaging
5. Update existing tests

### Phase 3: Integration (P1, ~2 days)

1. `mce/cli.py` — add `index` subcommand
2. `mce/executor.py` — add `code-index` plan
3. `mce/retrieve.py` — search code-index.db in addition to memory FTS
4. `SKILL.md` — update default behavior and operations table
5. `bin/dream-nightly.sh` — add code-index step
6. `runbook.md` — update with code-index operations

### Phase 4: Polish (P2, ~1 day)

1. `scan_to_dream.py` — optional read from code-index.db
2. `.code-dreaming/.gitignore` generation
3. Optional zstd snapshot for team sharing
4. Performance benchmarks and tuning

---

## 13. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| First-run actionable output on fresh project | 0 findings | Project overview + code structure + git history |
| Signal scan false positives | 1 (skill self-description) | 0 |
| Incremental run time (after initial index) | N/A | <500ms for <10 changed files |
| Full index time (500-file project) | N/A | <5 seconds |
| Memory files required for useful output | Yes (>0 episodic entries) | No (code index provides baseline) |

---

## 14. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `py-tree-sitter` grammar quality varies by language | Medium | Low | Graceful degradation to text-only indexing |
| Large repos (>10k files) slow on first scan | Medium | Medium | Configurable `--max-files`, ignore patterns, progress output |
| Git history parsing edge cases (merge commits, rebases) | Low | Low | Use `--first-parent` for linear history; fallback to basic parsing |
| SQLite locking on concurrent access | Low | Low | WAL mode; code-index.db is single-writer |
| Tree-sitter pip install fails on some platforms | Medium | Medium | `install_grammars.py` with clear error messages; text-only fallback |

---

## 15. Upstream Attribution & Licensing

All new code is original Python, but the design draws heavily from three MIT-
licensed projects. Attribution is required in source file headers and the
skill's LICENSE file.

| Upstream | License | What We Reuse | How |
|----------|---------|---------------|-----|
| [CodeGraph](https://github.com/colbymchenry/codegraph) (MIT) | Schema design (nodes/edges/files tables, FTS5 triggers), 4-stage pipeline architecture, incremental reconciliation (size+mtime+hash), NodeKind/EdgeKind enums | Reimplement in Python; no code copied |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) (MIT) | Edge type taxonomy (20+ types including `file_changes_with`, `similar_to`, `tests`), zstd artifact sharing pattern, adaptive polling concept | Reimplement in Python; no code copied |
| [MiMo Code / OpenCode](https://github.com/nicepkg/opencode) (MIT) | Dream/distill prompt design, memory reconcile fingerprinting, auto-dream scheduling gates, FTS5 search with BM25 score floor | Already vendored in `upstream/maas-code/` |
| [Mem0](https://github.com/mem0ai/mem0) (Apache-2.0) | Memory backbone (vector + BM25 + entity retrieval), extract->update pipeline | Already vendored in `vendor/mem0/` |

New files must include:

```python
# Design informed by CodeGraph (MIT, github.com/colbymchenry/codegraph)
# and codebase-memory-mcp (MIT, github.com/DeusData/codebase-memory-mcp).
# Schema and pipeline patterns reimplemented in Python; no source code copied.
```

---

## 16. Non-Goals

- **Real-time file watching** — unlike CodeGraph's MCP server, code-dreaming is
  on-demand or nightly, not a persistent daemon. The incremental manifest
  provides the same benefit without a watcher.
- **MCP server for code queries** — the code index is consumed internally by the
  dream pipeline, not exposed as an MCP tool. If MCP integration is wanted later,
  it can be added as a thin wrapper over `code_queries.py`.
- **LLM-generated code descriptions** — L1 is deterministic. LLM synthesis
  happens in L2 (the host agent's turn), not in the indexer.
- **Cross-repo indexing** — the code index is per-project. Cross-project
  knowledge lives in Mem0 global memory.
- **Replacing CodeGraph/codebase-memory-mcp** — those are MCP servers for
  real-time agent use. This is a batch indexer for the dream pipeline. They
  can coexist.
