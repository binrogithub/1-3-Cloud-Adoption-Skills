"""SQLite-backed code structure index for code-dreaming.

Design informed by CodeGraph (MIT, github.com/colbymchenry/codegraph)
and codebase-memory-mcp (MIT, github.com/DeusData/codebase-memory-mcp).
Schema and pipeline patterns reimplemented in Python; no source code copied.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Current schema version — increment when DDL changes.
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# DDL helpers
# ---------------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, triggers, and FTS on *conn*.

    Executes in a single transaction.  Safe to call on a fresh ``:memory:``
    database or on a new on-disk file.  Sets WAL journal mode and enables
    foreign-key enforcement before running any DDL.

    Acceptance criteria (from E0 epic):
    - All tables/indexes/triggers created
    - ``schema_version`` row version=1 inserted
    - ``PRAGMA journal_mode = WAL`` set
    """
    # WAL mode and foreign keys are connection-level pragmas — set before the
    # transaction so they apply for the lifetime of the connection.
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:  # single transaction for all DDL
        # ------------------------------------------------------------------ #
        # Schema version tracking
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  INTEGER NOT NULL,
                description TEXT
            );
        """)

        # ------------------------------------------------------------------ #
        # File registry
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id             INTEGER PRIMARY KEY,
                path           TEXT UNIQUE NOT NULL,
                language       TEXT,
                size_bytes     INTEGER NOT NULL,
                mtime_ns       INTEGER NOT NULL,
                content_sha256 TEXT NOT NULL,
                node_count     INTEGER DEFAULT 0,
                indexed_at     REAL NOT NULL,
                errors         TEXT
            );
        """)

        # ------------------------------------------------------------------ #
        # Symbols extracted by tree-sitter
        # kind values: file, module, class, struct, interface, trait, function,
        #   method, property, field, variable, constant, enum, enum_member,
        #   type_alias, namespace, import, export, route, component
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                id             INTEGER PRIMARY KEY,
                file_id        INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                name           TEXT NOT NULL,
                qualified_name TEXT,
                kind           TEXT NOT NULL,
                start_line     INTEGER NOT NULL,
                end_line       INTEGER NOT NULL,
                signature      TEXT,
                docstring      TEXT,
                visibility     TEXT,
                is_exported    INTEGER DEFAULT 0,
                is_async       INTEGER DEFAULT 0,
                decorators     TEXT
            );
        """)

        # ------------------------------------------------------------------ #
        # Relationships between symbols
        # kind values: contains, calls, imports, exports, extends, implements,
        #   references, type_of, returns, instantiates, overrides, decorates,
        #   similar_to, tests, file_changes_with
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id          INTEGER PRIMARY KEY,
                source_id   INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
                target_id   INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
                target_name TEXT,
                kind        TEXT NOT NULL,
                confidence  REAL DEFAULT 1.0,
                line        INTEGER,
                metadata   TEXT
            );
        """)

        # ------------------------------------------------------------------ #
        # Git commit history (bounded)
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS commits (
                id            INTEGER PRIMARY KEY,
                hash          TEXT UNIQUE NOT NULL,
                author        TEXT,
                date          TEXT,
                message       TEXT,
                files_changed INTEGER
            );
        """)

        # ------------------------------------------------------------------ #
        # Files changed per commit
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS commit_files (
                commit_id   INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
                file_path   TEXT NOT NULL,
                change_type TEXT,
                additions   INTEGER DEFAULT 0,
                deletions   INTEGER DEFAULT 0
            );
        """)

        # ------------------------------------------------------------------ #
        # FTS5 virtual table over symbols (content-sync)
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
                name, qualified_name, signature, docstring,
                content=symbols, content_rowid=id
            );
        """)

        # ------------------------------------------------------------------ #
        # FTS sync triggers (INSERT / DELETE / UPDATE)
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS symbols_ai
            AFTER INSERT ON symbols BEGIN
                INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
                VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
            END;
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS symbols_ad
            AFTER DELETE ON symbols BEGIN
                INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
                VALUES ('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
            END;
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS symbols_au
            AFTER UPDATE ON symbols BEGIN
                INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
                VALUES ('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
                INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
                VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
            END;
        """)

        # ------------------------------------------------------------------ #
        # Project metadata key-value store
        # ------------------------------------------------------------------ #
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_metadata (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
        """)

        # ------------------------------------------------------------------ #
        # Indexes
        # ------------------------------------------------------------------ #
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_language       ON files(language);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file         ON symbols(file_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name         ON symbols(name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_kind         ON symbols(kind);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_qualified    ON symbols(qualified_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source         ON edges(source_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target         ON edges(target_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_kind           ON edges(kind);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_commit_files_path    ON commit_files(file_path);")

        # ------------------------------------------------------------------ #
        # Seed schema version row
        # ------------------------------------------------------------------ #
        conn.execute("""
            INSERT OR IGNORE INTO schema_version (version, applied_at, description)
            VALUES (?, ?, ?);
        """, (SCHEMA_VERSION, int(time.time()), "Initial schema — E0 foundation"))


# ---------------------------------------------------------------------------
# CodeIndex class
# ---------------------------------------------------------------------------

class CodeIndex:
    """Thin wrapper around the SQLite code-structure database.

    Typical usage::

        with CodeIndex.open_or_create(Path(".code-dreaming/code-index.db")) as idx:
            print(idx.schema_version())
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def open_or_create(cls, db_path: Path) -> "CodeIndex":
        """Open an existing DB or create a new one with the current schema.

        On creation:
        - WAL journal mode is set
        - Full schema DDL is executed
        - Schema version 1 is seeded

        On open of an existing DB:
        - WAL journal mode is set
        - ``_migrate()`` is called to apply any pending migrations
        """
        instance = cls(db_path)

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        is_new = not db_path.exists() or db_path.stat().st_size == 0

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        instance._conn = conn

        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")

        if is_new:
            create_schema(conn)
        else:
            instance._migrate()

        return instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "CodeIndex":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def schema_version(self) -> int:
        """Return the highest schema version recorded in ``schema_version``."""
        self._require_open()
        row = self._conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        """Apply pending migrations to bring the DB up to the current version.

        v1 is the initial version; there are no migrations to apply yet.
        Future schema changes increment ``SCHEMA_VERSION`` and add a branch
        here.
        """
        self._require_open()
        current = self.schema_version()

        if current == 0:
            # DB exists but schema_version table is missing — recreate schema
            # (handles the edge case of a DB created outside this module).
            create_schema(self._conn)
            return

        # Placeholder: add migration branches here as SCHEMA_VERSION grows.
        if current < 2:
            # v2: add target_name column to edges for unresolved import/extends edges
            try:
                self._conn.execute("ALTER TABLE edges ADD COLUMN target_name TEXT;")
            except sqlite3.OperationalError:
                pass  # column already exists
            # Allow target_id to be NULL (for unresolved edges)
            # SQLite doesn't support ALTER COLUMN, but since we defined it
            # with REFERENCES it may already allow NULL. Re-create if needed.
            try:
                self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target_name ON edges(target_name);")
            except sqlite3.OperationalError:
                pass
            self._conn.execute(
                "INSERT INTO schema_version VALUES (2, ?, 'Add target_name to edges for unresolved targets')",
                (int(time.time()),)
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    def set_metadata(self, key: str, value: str) -> None:
        """Upsert a key-value pair in ``project_metadata``."""
        self._require_open()
        with self._conn:
            self._conn.execute("""
                INSERT INTO project_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                               updated_at=excluded.updated_at;
            """, (key, value, int(time.time())))

    def get_metadata(self, key: str) -> str | None:
        """Return the stored value for *key*, or ``None`` if absent."""
        self._require_open()
        row = self._conn.execute(
            "SELECT value FROM project_metadata WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if self._conn is None:
            raise RuntimeError(
                "CodeIndex connection is closed. "
                "Use open_or_create() or the context manager."
            )

    @property
    def conn(self) -> sqlite3.Connection:
        self._require_open()
        return self._conn  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # S7.1: Artifact export
    # ------------------------------------------------------------------

    def export_artifact(self, output_path: Path | None = None) -> dict:
        """Export code-index.db as a zstd-compressed artifact.

        Checkpoints WAL, compresses the DB with zstandard (level 3) or
        gzip as fallback, writes the .zst file, and writes artifact.json
        alongside with metadata.

        Returns the metadata dict.
        """
        self._require_open()

        if output_path is None:
            output_path = self._db_path.parent / (self._db_path.name + ".zst")
        output_path = Path(output_path)

        # Checkpoint WAL so the DB file is fully consistent on disk
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        db_bytes = self._db_path.read_bytes()
        uncompressed_size = len(db_bytes)

        # Compress with zstandard (level 3 — fast, ~3:1 on SQLite)
        try:
            import zstandard as zstd  # type: ignore[import]

            cctx = zstd.ZstdCompressor(level=3)
            compressed_bytes = cctx.compress(db_bytes)
            ext = ".zst"
        except ImportError:
            logger.warning("zstandard not installed; falling back to gzip")
            compressed_bytes = gzip.compress(db_bytes, compresslevel=6)
            ext = ".gz"
            # Rename output_path if it was .zst default
            if output_path.suffix == ".zst":
                output_path = output_path.with_suffix(".gz")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(compressed_bytes)
        compressed_size = len(compressed_bytes)

        # Count files and symbols for metadata
        files_count = self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols_count = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]

        # Current git commit (best-effort)
        git_commit = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self._db_path.parent),
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:  # noqa: BLE001
            pass

        metadata = {
            "schema_version": self.schema_version(),
            "files_count": files_count,
            "symbols_count": symbols_count,
            "compressed_size": compressed_size,
            "uncompressed_size": uncompressed_size,
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": git_commit,
        }

        artifact_json_path = output_path.parent / "artifact.json"
        artifact_json_path.write_text(json.dumps(metadata, indent=2) + "\n")

        logger.info(
            "Artifact exported: %s (%.1f:1 ratio)", output_path,
            uncompressed_size / compressed_size if compressed_size else 0,
        )
        return metadata

    # ------------------------------------------------------------------
    # S7.2: Artifact import
    # ------------------------------------------------------------------

    @classmethod
    def import_artifact(cls, artifact_path: Path, db_path: Path) -> "CodeIndex":
        """Import a zstd- or gzip-compressed code-index artifact.

        Decompresses *artifact_path* to *db_path*, verifies schema version,
        and returns an open CodeIndex instance.

        If an existing DB at *db_path* is newer (by last_indexed_at), the
        import is skipped and the existing DB is opened instead.
        """
        artifact_path = Path(artifact_path)
        db_path = Path(db_path)

        compressed_bytes = artifact_path.read_bytes()

        # Detect compression format
        suffix = artifact_path.suffix.lower()
        if suffix == ".zst":
            try:
                import zstandard as zstd  # type: ignore[import]
                dctx = zstd.ZstdDecompressor()
                db_bytes = dctx.decompress(compressed_bytes)
            except ImportError as exc:
                raise RuntimeError(
                    "zstandard is required to import .zst artifacts. "
                    "Run: pip install zstandard"
                ) from exc
        elif suffix in (".gz", ".gzip"):
            db_bytes = gzip.decompress(compressed_bytes)
        else:
            raise ValueError(
                f"Unsupported artifact extension: {suffix!r}. "
                "Expected .zst or .gz"
            )

        # Check if an existing DB is newer — skip import if so
        artifact_json_path = artifact_path.parent / "artifact.json"
        if db_path.exists() and db_path.stat().st_size > 0:
            try:
                existing = cls.open_or_create(db_path)
                existing_ts_str = existing.get_metadata("last_indexed_at")
                existing.close()
                if existing_ts_str:
                    existing_ts = int(existing_ts_str)
                    artifact_ts: int | None = None
                    if artifact_json_path.exists():
                        try:
                            aj = json.loads(artifact_json_path.read_text())
                            created_at = aj.get("created_at", "")
                            if created_at:
                                dt = datetime.datetime.strptime(
                                    created_at, "%Y-%m-%dT%H:%M:%SZ"
                                )
                                artifact_ts = int(dt.replace(
                                    tzinfo=datetime.timezone.utc
                                ).timestamp())
                        except Exception:  # noqa: BLE001
                            pass
                    if artifact_ts is not None and existing_ts >= artifact_ts:
                        logger.info(
                            "Existing DB at %s is newer than artifact; skipping import.",
                            db_path,
                        )
                        return cls.open_or_create(db_path)
            except Exception:  # noqa: BLE001
                pass  # Proceed with import if existing DB is unreadable

        # Write DB bytes to destination
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(db_bytes)

        # Open and verify schema version
        instance = cls.open_or_create(db_path)
        imported_version = instance.schema_version()
        if imported_version != SCHEMA_VERSION:
            instance.close()
            raise RuntimeError(
                f"Schema version mismatch: artifact has version {imported_version}, "
                f"but this code expects version {SCHEMA_VERSION}. "
                "Re-export the artifact with the current code."
            )

        logger.info("Artifact imported from %s to %s", artifact_path, db_path)
        return instance

    def index_all(self, repo_root: Path, max_files: int = 5000) -> "IndexResult":
        """Full or incremental index of the project (S1.6)."""
        self._require_open()
        repo_root = Path(repo_root).resolve()
        t0 = time.monotonic()

        all_files = walk_files(repo_root)
        if len(all_files) > max_files:
            logger.warning(
                "walk_files returned %d files; capping at %d", len(all_files), max_files
            )
            all_files = all_files[:max_files]

        classified = classify_files(self.conn, repo_root, all_files)

        # Remove deleted files — CASCADE cleans up symbols + edges
        with self.conn:
            for rel in classified["deleted"]:
                self.conn.execute("DELETE FROM files WHERE path = ?", (str(rel),))

        to_parse = classified["added"] + classified["changed"]
        total_symbols = 0
        total_edges = 0

        for rel in to_parse:
            abs_path = repo_root / rel
            language = detect_language(abs_path)

            try:
                source_bytes = abs_path.read_bytes()
            except OSError:
                continue

            stat = abs_path.stat()
            sha256 = hashlib.sha256(source_bytes).hexdigest()

            with self.conn:
                # Remove stale record (handles changed files)
                self.conn.execute("DELETE FROM files WHERE path = ?", (str(rel),))
                self.conn.execute(
                    """
                    INSERT INTO files
                        (path, language, size_bytes, mtime_ns, content_sha256, node_count, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(rel),
                        language,
                        stat.st_size,
                        stat.st_mtime_ns,
                        sha256,
                        0,
                        time.time(),
                    ),
                )
                file_id = self.conn.execute(
                    "SELECT id FROM files WHERE path = ?", (str(rel),)
                ).fetchone()[0]

            grammar = load_grammar(language) if language else None

            file_symbols: list[SymbolInfo] = []
            file_edges: list[EdgeInfo] = []

            if grammar is not None:
                try:
                    from tree_sitter import Parser as TSParser

                    parser = TSParser(grammar)
                    tree = parser.parse(source_bytes)
                    file_symbols = extract_symbols(tree, source_bytes, language or "")
                    file_edges = extract_edges(tree, source_bytes, language or "")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Parse error for %s: %s", rel, exc)

            # Write symbols
            sym_id_map: dict[str, int] = {}
            with self.conn:
                for sym in file_symbols:
                    cur = self.conn.execute(
                        """
                        INSERT INTO symbols
                            (file_id, name, qualified_name, kind,
                             start_line, end_line, signature, docstring)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            file_id,
                            sym.name,
                            sym.qualified_name,
                            sym.kind,
                            sym.start_line,
                            sym.end_line,
                            sym.signature,
                            sym.docstring,
                        ),
                    )
                    sym_id_map[sym.qualified_name or sym.name] = cur.lastrowid  # type: ignore[assignment]

                self.conn.execute(
                    "UPDATE files SET node_count = ? WHERE id = ?",
                    (len(file_symbols), file_id),
                )

            total_symbols += len(file_symbols)

            # Write edges (best-effort: keep unresolved with target_name)
            edge_count = 0
            with self.conn:
                for edge in file_edges:
                    # Resolve source: <module> means file-level, otherwise look up symbol
                    if edge.source_name == "<module>":
                        # File-level edge (imports) — use first symbol in file as proxy,
                        # or skip if no symbols. This connects the file to its imports.
                        src_id = next(iter(sym_id_map.values()), None)
                        if src_id is None:
                            continue
                    else:
                        src_id = sym_id_map.get(edge.source_name)
                        if src_id is None:
                            # Try by name alone (not qualified)
                            row = self.conn.execute(
                                "SELECT id FROM symbols WHERE name = ? AND file_id = ? LIMIT 1",
                                (edge.source_name, file_id),
                            ).fetchone()
                            if row is None:
                                continue
                            src_id = row[0]

                    # Look up target in DB by name or qualified_name
                    row = self.conn.execute(
                        "SELECT id FROM symbols WHERE name = ? OR qualified_name = ? LIMIT 1",
                        (edge.target_name, edge.target_name),
                    ).fetchone()
                    if row is not None:
                        tgt_id = row[0]
                        tgt_name = None
                    else:
                        # Unresolved target (e.g. stdlib import) — keep the edge
                        tgt_id = None
                        tgt_name = edge.target_name
                    self.conn.execute(
                        """
                        INSERT INTO edges (source_id, target_id, target_name, kind, confidence, line)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (src_id, tgt_id, tgt_name, edge.kind, edge.confidence, edge.line),
                    )
                    edge_count += 1
            total_edges += edge_count

        # VACUUM if >20% churn
        total_known = len(to_parse) + len(classified["unchanged"])
        if total_known > 0 and len(classified["deleted"]) / total_known > 0.2:
            self.conn.execute("VACUUM")

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Update project_metadata
        self.set_metadata("last_indexed_at", str(int(time.time())))
        self.set_metadata("last_indexed_repo_root", str(repo_root))

        return IndexResult(
            added=len(classified["added"]),
            changed=len(classified["changed"]),
            deleted=len(classified["deleted"]),
            unchanged=len(classified["unchanged"]),
            symbols=total_symbols,
            edges=total_edges,
            duration_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# S7.3: Git merge strategy setup
# ---------------------------------------------------------------------------

_GITATTRIBUTES_ENTRIES = [
    "code-index.db.zst merge=ours",
    "artifact.json merge=ours",
]

_GITIGNORE_ENTRIES = [
    ".code-dreaming/code-index.db",
    ".code-dreaming/code-index.db-wal",
    ".code-dreaming/code-index.db-shm",
]


def setup_git_merge_strategy(repo_root: Path) -> None:
    """Configure merge=ours for artifact files and update .gitignore.

    - Writes/updates ``.code-dreaming/.gitattributes`` with ``merge=ours``
      entries for ``code-index.db.zst`` and ``artifact.json``.
    - Appends ``.code-dreaming/code-index.db`` (and WAL/SHM sidecar files)
      to the root ``.gitignore`` so the raw DB stays local while the
      compressed artifact is committed.
    """
    repo_root = Path(repo_root).resolve()

    # --- .gitattributes ---
    ga_dir = repo_root / ".code-dreaming"
    ga_dir.mkdir(parents=True, exist_ok=True)
    ga_path = ga_dir / ".gitattributes"

    existing_ga = ga_path.read_text() if ga_path.exists() else ""
    lines_to_add = [
        entry for entry in _GITATTRIBUTES_ENTRIES if entry not in existing_ga
    ]
    if lines_to_add:
        with ga_path.open("a") as fh:
            if existing_ga and not existing_ga.endswith("\n"):
                fh.write("\n")
            for line in lines_to_add:
                fh.write(line + "\n")
        logger.info("Updated %s with merge=ours entries", ga_path)

    # --- .gitignore ---
    gi_path = repo_root / ".gitignore"
    existing_gi = gi_path.read_text() if gi_path.exists() else ""
    lines_to_add_gi = [
        entry for entry in _GITIGNORE_ENTRIES if entry not in existing_gi
    ]
    if lines_to_add_gi:
        with gi_path.open("a") as fh:
            if existing_gi and not existing_gi.endswith("\n"):
                fh.write("\n")
            for line in lines_to_add_gi:
                fh.write(line + "\n")
        logger.info("Updated %s with raw DB exclusions", gi_path)


# ---------------------------------------------------------------------------
# S1.1: File walker
# ---------------------------------------------------------------------------

# Directories to skip during os.walk fallback
IGNORED_DIRS = {
    ".git", ".hg", "node_modules", "vendor", "build", "dist",
    "__pycache__", ".venv", ".mypy_cache", ".pytest_cache",
    ".code-dreaming",
}

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd",
    ".so", ".dylib", ".dll", ".exe", ".bin", ".obj", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav",
    ".ttf", ".woff", ".woff2", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".db-wal", ".db-shm",  # SQLite WAL and shared-memory files
    ".parquet", ".pkl", ".pickle",
    ".lock",  # package lock files can be huge / binary-like
}


def _is_binary_by_extension(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def _is_binary_by_sniff(path: Path, sample: int = 8192) -> bool:
    """Return True if the file contains a null byte in the first *sample* bytes."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(sample)
        return b"\x00" in chunk
    except OSError:
        return True  # treat unreadable files as binary


def walk_files(repo_root: Path) -> list[Path]:
    """Return text-file paths relative to *repo_root*.

    Prefers ``git ls-files`` when inside a git repo; falls back to
    ``os.walk`` with IGNORED_DIRS filtering for non-git trees.
    Skips binary files by extension and null-byte sniff.
    """
    repo_root = Path(repo_root).resolve()

    paths: list[Path] = []

    # Try git ls-files first
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                p = Path(line)
                if _is_binary_by_extension(p):
                    continue
                abs_p = repo_root / p
                if not abs_p.is_file():
                    continue
                if _is_binary_by_sniff(abs_p):
                    continue
                paths.append(p)
            return paths
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback: os.walk
    for dirpath, dirnames, filenames in os.walk(str(repo_root)):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for fname in filenames:
            abs_p = Path(dirpath) / fname
            rel = abs_p.relative_to(repo_root)
            if _is_binary_by_extension(abs_p):
                continue
            if _is_binary_by_sniff(abs_p):
                continue
            paths.append(rel)

    return paths


# ---------------------------------------------------------------------------
# S1.2: Incremental fingerprinting
# ---------------------------------------------------------------------------

@dataclass
class FileClassification:
    added: list[Path] = field(default_factory=list)
    changed: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)


def classify_files(
    conn: sqlite3.Connection,
    repo_root: Path,
    file_paths: list[Path],
) -> dict[str, list[Path]]:
    """Classify *file_paths* as added/changed/deleted/unchanged.

    Fast-pass: compare ``(size_bytes, mtime_ns)`` against DB.
    Slow-pass (only when stat differs): compute sha256 and compare.
    """
    repo_root = Path(repo_root).resolve()

    # Load existing fingerprints from DB in one query
    rows = conn.execute(
        "SELECT path, size_bytes, mtime_ns, content_sha256 FROM files"
    ).fetchall()
    db_records: dict[str, dict[str, Any]] = {
        row[0]: {"size_bytes": row[1], "mtime_ns": row[2], "content_sha256": row[3]}
        for row in rows
    }

    disk_set = {str(p) for p in file_paths}

    result: dict[str, list[Path]] = {
        "added": [], "changed": [], "deleted": [], "unchanged": []
    }

    for rel in file_paths:
        key = str(rel)
        abs_p = repo_root / rel
        try:
            st = abs_p.stat()
        except OSError:
            # File disappeared between walk and classify
            continue

        if key not in db_records:
            result["added"].append(rel)
            continue

        rec = db_records[key]
        # Fast-pass: if stat matches, skip sha256
        if st.st_size == rec["size_bytes"] and st.st_mtime_ns == rec["mtime_ns"]:
            result["unchanged"].append(rel)
            continue

        # Slow-pass: stat differs — check actual content
        try:
            sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
        except OSError:
            result["changed"].append(rel)
            continue

        if sha == rec["content_sha256"]:
            result["unchanged"].append(rel)
        else:
            result["changed"].append(rel)

    # Files in DB but not on disk
    for key in db_records:
        if key not in disk_set:
            result["deleted"].append(Path(key))

    return result


# ---------------------------------------------------------------------------
# S1.3: Language detection and grammar loading
# ---------------------------------------------------------------------------

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp",
    ".rb": "ruby", ".php": "php",
    ".sh": "bash", ".bash": "bash",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".json": "json",
    ".md": "markdown",
}

_grammar_cache: dict[str, Any] = {}          # language -> Language | None
_grammar_warned: set[str] = set()            # languages already warned about


def detect_language(path: Path | str) -> str | None:
    """Return language name for *path* based on extension, or None."""
    return LANGUAGE_MAP.get(Path(path).suffix.lower())


def load_grammar(language: str) -> Any:
    """Return a ``tree_sitter.Language`` for *language*, or None.

    Results are cached per language.  Import errors are logged once.
    """
    if language in _grammar_cache:
        return _grammar_cache[language]

    result = None
    try:
        from tree_sitter import Language

        if language == "python":
            import tree_sitter_python as _m
            result = Language(_m.language())
        elif language == "javascript":
            import tree_sitter_javascript as _m  # type: ignore[no-redef]
            result = Language(_m.language())
        elif language == "typescript":
            import tree_sitter_typescript as _m  # type: ignore[no-redef]
            result = Language(_m.language_typescript())
        elif language == "tsx":
            import tree_sitter_typescript as _m  # type: ignore[no-redef]
            result = Language(_m.language_tsx())
        else:
            # Other languages not yet bundled — graceful degradation
            if language not in _grammar_warned:
                logger.warning("No grammar available for language: %s", language)
                _grammar_warned.add(language)
    except ImportError as exc:
        if language not in _grammar_warned:
            logger.warning("Cannot load grammar for %s: %s", language, exc)
            _grammar_warned.add(language)
    except Exception as exc:  # noqa: BLE001
        if language not in _grammar_warned:
            logger.warning("Unexpected error loading grammar for %s: %s", language, exc)
            _grammar_warned.add(language)

    _grammar_cache[language] = result
    return result


# ---------------------------------------------------------------------------
# S1.4: Symbol extraction
# ---------------------------------------------------------------------------

@dataclass
class SymbolInfo:
    name: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""


# Node types that represent named symbols per language
_SYMBOL_TYPES: dict[str, set[str]] = {
    "python": {
        "function_definition", "class_definition", "decorated_definition",
    },
    "javascript": {
        "function_declaration", "class_declaration", "arrow_function",
        "method_definition", "interface_declaration",
    },
    "typescript": {
        "function_declaration", "class_declaration", "arrow_function",
        "method_definition", "interface_declaration", "type_alias_declaration",
    },
    "tsx": {
        "function_declaration", "class_declaration", "arrow_function",
        "method_definition", "interface_declaration", "type_alias_declaration",
    },
    "go": {
        "function_declaration", "method_declaration", "type_declaration",
    },
}

_KIND_MAP: dict[str, str] = {
    "function_definition": "function",
    "function_declaration": "function",
    "method_definition": "method",
    "method_declaration": "method",
    "class_definition": "class",
    "class_declaration": "class",
    "decorated_definition": "function",  # refined below
    "arrow_function": "function",
    "interface_declaration": "interface",
    "type_alias_declaration": "type_alias",
    "type_declaration": "type_alias",
}


def _node_name(node: Any, source_bytes: bytes) -> str:
    """Extract the identifier name from a definition node."""
    for child in node.children:
        if child.type == "identifier":
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        if child.type == "type_identifier":
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        if child.type == "property_identifier":
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
    return "<anonymous>"


def _first_line(node: Any, source_bytes: bytes) -> str:
    """Return the first line of a node as its signature."""
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    return text.split("\n", 1)[0].strip()


def _docstring(node: Any, source_bytes: bytes, language: str) -> str:
    """Try to extract a docstring from the node body."""
    if language not in ("python", "javascript", "typescript", "tsx"):
        return ""
    for child in node.children:
        if child.type == "block":
            # JS/TS block — look for first comment or string
            for stmt in child.children:
                if stmt.type in ("comment", "string"):
                    text = source_bytes[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="replace")
                    return text.strip().strip('"\'').strip()
            break
        if child.type == "comment":
            text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            return text.strip().lstrip("#").strip()
    # Python: look for expression_statement > string inside block
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            raw = source_bytes[expr.start_byte:expr.end_byte].decode("utf-8", errors="replace")
                            # Strip delimiters
                            for delim in ('"""', "'''", '"', "'"):
                                if raw.startswith(delim) and raw.endswith(delim) and len(raw) > 2 * len(delim):
                                    return raw[len(delim):-len(delim)].strip()
                            return raw.strip('"\'').strip()
    return ""


def _walk_ast_for_symbols(
    node: Any,
    source_bytes: bytes,
    language: str,
    parent_names: list[str],
    symbols: list[SymbolInfo],
    target_types: set[str],
    parent_is_class: bool = False,
) -> None:
    """Recursively walk AST collecting symbols."""
    if node.type in target_types:
        # Unwrap decorated_definition
        actual_node = node
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    actual_node = child
                    break

        name = _node_name(actual_node, source_bytes)
        kind = _KIND_MAP.get(actual_node.type, "function")
        if actual_node.type in ("class_definition", "class_declaration"):
            kind = "class"
            this_is_class = True
        elif actual_node.type in ("method_definition", "method_declaration"):
            kind = "method"
            this_is_class = False
        elif actual_node.type in ("function_definition", "function_declaration"):
            # In Python, function_definition inside a class block is a method
            kind = "method" if parent_is_class else "function"
            this_is_class = False
        else:
            this_is_class = False

        qualified = ".".join(parent_names + [name]) if parent_names else name
        sig = _first_line(actual_node, source_bytes)
        doc = _docstring(actual_node, source_bytes, language)

        symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified,
            kind=kind,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            docstring=doc,
        ))

        # Recurse into body with updated parent stack
        for child in node.children:
            _walk_ast_for_symbols(
                child, source_bytes, language,
                parent_names + [name], symbols, target_types,
                parent_is_class=this_is_class,
            )
    else:
        # Track whether this block node is inside a class
        next_is_class = parent_is_class and node.type == "block"
        for child in node.children:
            _walk_ast_for_symbols(
                child, source_bytes, language,
                parent_names, symbols, target_types,
                parent_is_class=next_is_class,
            )


def extract_symbols(tree: Any, source_bytes: bytes, language: str) -> list[SymbolInfo]:
    """Walk *tree* and return SymbolInfo for each named definition."""
    target_types = _SYMBOL_TYPES.get(language, set())
    if not target_types:
        # Generic fallback: any top-level node with an identifier
        target_types = {
            "function_definition", "function_declaration",
            "class_definition", "class_declaration",
        }

    symbols: list[SymbolInfo] = []
    _walk_ast_for_symbols(
        tree.root_node, source_bytes, language, [], symbols, target_types
    )
    return symbols


# ---------------------------------------------------------------------------
# S1.5: Edge extraction (imports)
# ---------------------------------------------------------------------------

@dataclass
class EdgeInfo:
    source_name: str      # qualified name of symbol in this file (or file path)
    target_name: str      # name being imported/called
    kind: str             # "imports" | "calls"
    confidence: float = 1.0
    line: int = 0


def _python_imports(tree: Any, source_bytes: bytes) -> list[EdgeInfo]:
    """Extract import edges from a Python AST."""
    edges: list[EdgeInfo] = []
    for node in tree.root_node.children:
        if node.type == "import_statement":
            # import foo, bar
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    name = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                    name = name.split(" as ")[0].strip()
                    edges.append(EdgeInfo(
                        source_name="<module>",
                        target_name=name,
                        kind="imports",
                        confidence=1.0,
                        line=node.start_point[0] + 1,
                    ))
        elif node.type == "import_from_statement":
            # from foo import bar, baz
            children = node.children
            module = ""
            names: list[str] = []
            past_import_kw = False
            for child in children:
                if child.type == "from":
                    continue
                if child.type == "import":
                    past_import_kw = True
                    continue
                if not past_import_kw and child.type in ("dotted_name", "relative_import"):
                    module = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                elif past_import_kw:
                    if child.type == "import_list":
                        for sub in child.children:
                            if sub.type in ("identifier", "dotted_name", "aliased_import"):
                                text = source_bytes[sub.start_byte:sub.end_byte].decode("utf-8", errors="replace")
                                names.append(text.split(" as ")[0].strip())
                    elif child.type in ("identifier", "dotted_name", "aliased_import"):
                        text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        names.append(text.split(" as ")[0].strip())
            for n in names:
                target = f"{module}.{n}" if module else n
                edges.append(EdgeInfo(
                    source_name="<module>",
                    target_name=target,
                    kind="imports",
                    confidence=1.0,
                    line=node.start_point[0] + 1,
                ))
    return edges


def _python_calls_and_extends(tree: Any, source_bytes: bytes) -> list[EdgeInfo]:
    """Extract call and extends edges from a Python AST.

    Uses a stack to track the enclosing function/class so each call is
    attributed to its caller symbol.
    """
    edges: list[EdgeInfo] = []

    def _enclosing_name(stack: list[str]) -> str:
        return stack[-1] if stack else "<module>"

    def _walk(node: Any, name_stack: list[str]) -> None:
        # class Foo(Bar): -> extends edge (must run BEFORE the early return)
        if node.type == "class_definition":
            name = _node_name(node, source_bytes)
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type in ("identifier", "dotted_name", "attribute"):
                            base = source_bytes[arg.start_byte:arg.end_byte].decode("utf-8", errors="replace")
                            edges.append(EdgeInfo(
                                source_name=name,
                                target_name=base,
                                kind="extends",
                                confidence=1.0,
                                line=node.start_point[0] + 1,
                            ))

        # Track function/class entry
        if node.type in ("function_definition", "class_definition"):
            name = _node_name(node, source_bytes)
            new_stack = name_stack + [name]
            for child in node.children:
                _walk(child, new_stack)
            return
        if node.type == "decorated_definition":
            for child in node.children:
                _walk(child, name_stack)
            return

        # call expression: foo() or obj.method()
        if node.type == "call":
            callee = node.child_by_field_name("function")
            if callee is not None:
                callee_text = source_bytes[callee.start_byte:callee.end_byte].decode("utf-8", errors="replace")
                # For attribute calls (self.method, obj.method), extract the
                # method name after the last dot for resolution.
                simple_name = callee_text.rsplit(".", 1)[-1] if "." in callee_text else callee_text
                confidence = 0.8 if "." in callee_text else 1.0
                edges.append(EdgeInfo(
                    source_name=_enclosing_name(name_stack),
                    target_name=simple_name,
                    kind="calls",
                    confidence=confidence,
                    line=node.start_point[0] + 1,
                ))

        for child in node.children:
            _walk(child, name_stack)

    _walk(tree.root_node, [])
    return edges


def _js_imports(tree: Any, source_bytes: bytes) -> list[EdgeInfo]:
    """Extract import edges from a JS/TS AST."""
    edges: list[EdgeInfo] = []

    def _walk(node: Any) -> None:
        if node.type == "import_statement":
            src_child = None
            for child in node.children:
                if child.type == "string":
                    src_child = child
            if src_child:
                mod = source_bytes[src_child.start_byte:src_child.end_byte].decode("utf-8", errors="replace").strip("\"'")
                edges.append(EdgeInfo(
                    source_name="<module>",
                    target_name=mod,
                    kind="imports",
                    confidence=1.0,
                    line=node.start_point[0] + 1,
                ))
        for child in node.children:
            _walk(child)

    _walk(tree.root_node)
    return edges


def _js_calls_and_extends(tree: Any, source_bytes: bytes) -> list[EdgeInfo]:
    """Extract call and extends/implements edges from a JS/TS AST."""
    edges: list[EdgeInfo] = []

    def _enclosing_name(stack: list[str]) -> str:
        return stack[-1] if stack else "<module>"

    def _walk(node: Any, name_stack: list[str]) -> None:
        # Track function/class entry
        if node.type in ("function_declaration", "class_declaration", "method_definition"):
            name = _node_name(node, source_bytes)
            new_stack = name_stack + [name]
            for child in node.children:
                _walk(child, new_stack)
            return
        if node.type == "arrow_function":
            # Arrow functions are often anonymous — skip naming
            for child in node.children:
                _walk(child, name_stack)
            return

        # class Foo extends Bar / implements Bar
        if node.type == "class_declaration":
            name = _node_name(node, source_bytes)
            for child in node.children:
                if child.type == "class_heritage":
                    for hc in child.children:
                        if hc.type in ("identifier", "type_identifier"):
                            base = source_bytes[hc.start_byte:hc.end_byte].decode("utf-8", errors="replace")
                            kind = "extends"  # TS doesn't distinguish extends/implements in heritage_clause position easily
                            edges.append(EdgeInfo(
                                source_name=name,
                                target_name=base,
                                kind=kind,
                                confidence=1.0,
                                line=node.start_point[0] + 1,
                            ))

        # call expression: foo() or obj.method()
        if node.type == "call_expression":
            callee = node.child_by_field_name("function")
            if callee is not None:
                callee_text = source_bytes[callee.start_byte:callee.end_byte].decode("utf-8", errors="replace")
                simple_name = callee_text.rsplit(".", 1)[-1] if "." in callee_text else callee_text
                confidence = 0.8 if "." in callee_text else 1.0
                edges.append(EdgeInfo(
                    source_name=_enclosing_name(name_stack),
                    target_name=simple_name,
                    kind="calls",
                    confidence=confidence,
                    line=node.start_point[0] + 1,
                ))

        for child in node.children:
            _walk(child, name_stack)

    _walk(tree.root_node, [])
    return edges


def extract_edges(tree: Any, source_bytes: bytes, language: str) -> list[EdgeInfo]:
    """Extract import/call/extends edges from *tree*."""
    edges: list[EdgeInfo] = []
    if language == "python":
        edges.extend(_python_imports(tree, source_bytes))
        edges.extend(_python_calls_and_extends(tree, source_bytes))
    elif language in ("javascript", "typescript", "tsx"):
        edges.extend(_js_imports(tree, source_bytes))
        edges.extend(_js_calls_and_extends(tree, source_bytes))
    return edges


# ---------------------------------------------------------------------------
# S1.6: IndexResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class IndexResult:
    added: int
    changed: int
    deleted: int
    unchanged: int
    symbols: int
    edges: int
    duration_ms: int

    def __str__(self) -> str:
        total = self.added + self.changed + self.unchanged
        return (
            f"Indexed {total} files "
            f"(+{self.added} ~{self.changed} -{self.deleted} ={self.unchanged}), "
            f"{self.symbols} symbols, {self.edges} edges "
            f"({self.duration_ms / 1000:.1f}s)"
        )


# ---------------------------------------------------------------------------
# S1.7: CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Build or update the code-dreaming code structure index."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Root directory of the repository to index (default: current dir)",
    )
    parser.add_argument(
        "--db",
        default=".code-dreaming/code-index.db",
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=5000,
        help="Maximum number of files to index (default: 5000)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=200,
        help="Maximum number of git commits to store (default: 200, reserved)",
    )
    parser.add_argument(
        "--languages",
        default=None,
        help="Comma-separated list of languages to index (e.g. python,javascript)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = repo_root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with CodeIndex.open_or_create(db_path) as idx:
        result = idx.index_all(repo_root, max_files=args.max_files)

    print(str(result))


if __name__ == "__main__":
    main()
