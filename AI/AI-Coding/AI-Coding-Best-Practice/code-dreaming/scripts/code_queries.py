"""Code Queries API for code-dreaming — E4.

Provides a Python API over the code-index SQLite database for answering
questions about project structure: overviews, symbol search, call graphs,
file coupling, and commit history.


"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CodeQueries:
    """Read-only query API over a code-index.db database.

    Opens the database in URI read-only mode so it never mutates the index.
    Usable as a context manager::

        with CodeQueries(db_path) as cq:
            print(cq.overview())
    """

    def __init__(self, db_path: Path | str) -> None:
        db_path = Path(db_path)
        uri = f"file:{db_path}?mode=ro"
        try:
            self._conn = sqlite3.connect(uri, uri=True)
        except sqlite3.OperationalError:
            # DB may not exist yet — open an empty in-memory DB so callers
            # get empty results rather than an exception.
            self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> "CodeQueries":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # S4.2: overview()
    # ------------------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        """Return high-level project metrics.

        Returns all fields populated; on an empty DB returns zeros everywhere
        and empty lists.
        """
        conn = self._conn

        def _scalar(sql: str, params: tuple = ()) -> Any:
            try:
                row = conn.execute(sql, params).fetchone()
                return row[0] if row and row[0] is not None else 0
            except sqlite3.Error:
                return 0

        total_files = _scalar("SELECT COUNT(*) FROM files")
        total_symbols = _scalar("SELECT COUNT(*) FROM symbols")
        total_edges = _scalar("SELECT COUNT(*) FROM edges")
        total_commits = _scalar("SELECT COUNT(*) FROM commits")

        # Language distribution
        languages: dict[str, int] = {}
        try:
            rows = conn.execute(
                "SELECT language, COUNT(*) AS cnt FROM files "
                "WHERE language IS NOT NULL GROUP BY language ORDER BY cnt DESC"
            ).fetchall()
            for row in rows:
                languages[row["language"]] = row["cnt"]
        except sqlite3.Error:
            pass

        # Symbol kind distribution
        symbol_kinds: dict[str, int] = {}
        try:
            rows = conn.execute(
                "SELECT kind, COUNT(*) AS cnt FROM symbols "
                "GROUP BY kind ORDER BY cnt DESC"
            ).fetchall()
            for row in rows:
                symbol_kinds[row["kind"]] = row["cnt"]
        except sqlite3.Error:
            pass

        # Top 10 files by symbol count (node_count column)
        top_files: list[dict[str, Any]] = []
        try:
            rows = conn.execute(
                "SELECT path, language, node_count FROM files "
                "ORDER BY node_count DESC LIMIT 10"
            ).fetchall()
            for row in rows:
                top_files.append({
                    "path": row["path"],
                    "language": row["language"],
                    "symbol_count": row["node_count"],
                })
        except sqlite3.Error:
            pass

        # Last indexed timestamp
        last_indexed: str | None = None
        try:
            row = conn.execute(
                "SELECT MAX(indexed_at) AS ts FROM files"
            ).fetchone()
            if row and row["ts"] is not None:
                last_indexed = str(row["ts"])
        except sqlite3.Error:
            pass

        # Also try project_metadata for a richer last_indexed value
        try:
            row = conn.execute(
                "SELECT value FROM project_metadata WHERE key = 'last_indexed_at'"
            ).fetchone()
            if row:
                last_indexed = row["value"]
        except sqlite3.Error:
            pass

        # Convert epoch timestamps to ISO 8601
        if last_indexed:
            try:
                ts = float(last_indexed)
                if ts > 1e9:  # looks like Unix timestamp
                    last_indexed = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError):
                pass  # keep as-is if already a string

        return {
            "total_files": total_files,
            "total_symbols": total_symbols,
            "total_edges": total_edges,
            "total_commits": total_commits,
            "languages": languages,
            "symbol_kinds": symbol_kinds,
            "top_files_by_symbols": top_files,
            "last_indexed": last_indexed,
        }

    # ------------------------------------------------------------------
    # S4.3: search()
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_fts(query: str) -> str:
        """Escape FTS5 special characters so the query is treated literally."""
        # Escape double quotes by doubling them, then wrap each token.
        # Replace characters that are FTS5 operators/specials: * " ( ) ^ :
        escaped = re.sub(r'[*"()^:]+', " ", query)
        # Collapse whitespace
        tokens = escaped.split()
        if not tokens:
            return ""
        # Wrap each token in double quotes for phrase-literal matching
        return " ".join(f'"{tok}"' for tok in tokens)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search across symbol names, signatures, and docstrings.

        Uses FTS5 MATCH; falls back to LIKE if FTS errors or returns nothing.
        Empty query returns empty list.
        """
        if not query or not query.strip():
            return []

        conn = self._conn

        # Build the SELECT columns shared by both paths
        select = """
            SELECT
                s.id,
                s.name,
                s.kind,
                f.path   AS file_path,
                s.start_line,
                s.end_line,
                s.signature,
                s.docstring,
                s.qualified_name
            FROM symbols s
            JOIN files f ON f.id = s.file_id
        """

        fts_results: list[dict[str, Any]] = []
        escaped = self._escape_fts(query)

        if escaped:
            try:
                fts_sql = f"""
                    {select}
                    WHERE s.id IN (
                        SELECT rowid FROM symbols_fts WHERE symbols_fts MATCH ?
                    )
                    LIMIT ?
                """
                rows = conn.execute(fts_sql, (escaped, limit)).fetchall()
                fts_results = [dict(row) for row in rows]
            except sqlite3.Error:
                fts_results = []

        if fts_results:
            return fts_results

        # Fallback: LIKE search on name / qualified_name / signature
        like_pat = f"%{query}%"
        try:
            like_sql = f"""
                {select}
                WHERE s.name LIKE ?
                   OR s.qualified_name LIKE ?
                   OR s.signature LIKE ?
                LIMIT ?
            """
            rows = conn.execute(like_sql, (like_pat, like_pat, like_pat, limit)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # S4.4: file_symbols()
    # ------------------------------------------------------------------

    def file_symbols(self, path: str) -> list[dict[str, Any]]:
        """Return all symbols defined in a file, ordered by start_line.

        Non-existent path returns empty list.
        """
        try:
            rows = self._conn.execute(
                """
                SELECT
                    s.name,
                    s.qualified_name,
                    s.kind,
                    s.start_line,
                    s.end_line,
                    s.signature,
                    s.visibility,
                    s.is_exported,
                    s.is_async
                FROM symbols s
                JOIN files f ON f.id = s.file_id
                WHERE f.path = ?
                ORDER BY s.start_line ASC
                """,
                (path,),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # S4.5: callers() / callees()
    # ------------------------------------------------------------------

    def _resolve_symbol_ids(self, symbol_name: str) -> list[int]:
        """Return all symbol IDs matching name or qualified_name."""
        try:
            rows = self._conn.execute(
                "SELECT id FROM symbols WHERE name = ? OR qualified_name = ?",
                (symbol_name, symbol_name),
            ).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error:
            return []

    def callers(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find all symbols that call/import the given symbol.

        Queries edges where target matches the given symbol name or
        qualified_name.  Unknown symbol returns empty list.
        """
        target_ids = self._resolve_symbol_ids(symbol_name)
        if not target_ids:
            return []

        placeholders = ",".join("?" * len(target_ids))
        try:
            rows = self._conn.execute(
                f"""
                SELECT
                    src.name        AS caller_name,
                    src.qualified_name AS caller_qualified,
                    src.kind,
                    f.path          AS file_path,
                    e.line,
                    e.confidence,
                    e.kind          AS edge_kind
                FROM edges e
                JOIN symbols src ON src.id = e.source_id
                JOIN files f ON f.id = src.file_id
                WHERE e.target_id IN ({placeholders})
                ORDER BY f.path, e.line
                """,
                tuple(target_ids),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    def callees(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find all symbols called/imported by the given symbol.

        Queries edges where source matches the given symbol name or
        qualified_name.  Unknown symbol returns empty list.
        """
        source_ids = self._resolve_symbol_ids(symbol_name)
        if not source_ids:
            return []

        placeholders = ",".join("?" * len(source_ids))
        try:
            rows = self._conn.execute(
                f"""
                SELECT
                    tgt.name        AS callee_name,
                    tgt.qualified_name AS callee_qualified,
                    tgt.kind,
                    f.path          AS file_path,
                    e.line,
                    e.confidence,
                    e.kind          AS edge_kind
                FROM edges e
                JOIN symbols tgt ON tgt.id = e.target_id
                JOIN files f ON f.id = tgt.file_id
                WHERE e.source_id IN ({placeholders})
                ORDER BY f.path, e.line
                """,
                tuple(source_ids),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # S4.6: coupling()
    # ------------------------------------------------------------------

    def coupling(self, path: str, min_score: float = 0.3) -> list[dict[str, Any]]:
        """Files frequently changed together with the given file.

        Computes Jaccard similarity from commit_files co-occurrence.
        Returns list ordered by score DESC; empty list when no coupling.
        """
        try:
            sql = """
                WITH target_commits AS (
                    SELECT DISTINCT commit_id
                    FROM commit_files
                    WHERE file_path = ?
                ),
                co_changed AS (
                    SELECT
                        cf.file_path,
                        COUNT(*) AS co_commits
                    FROM commit_files cf
                    JOIN target_commits tc ON tc.commit_id = cf.commit_id
                    WHERE cf.file_path != ?
                    GROUP BY cf.file_path
                ),
                target_total AS (
                    SELECT COUNT(*) AS cnt FROM target_commits
                ),
                other_totals AS (
                    SELECT
                        file_path,
                        COUNT(DISTINCT commit_id) AS total_commits
                    FROM commit_files
                    WHERE file_path != ?
                    GROUP BY file_path
                )
                SELECT
                    cc.file_path,
                    cc.co_commits,
                    CAST(cc.co_commits AS REAL) /
                        (tt.cnt + ot.total_commits - cc.co_commits) AS jaccard
                FROM co_changed cc
                JOIN target_total tt
                JOIN other_totals ot ON ot.file_path = cc.file_path
                WHERE jaccard >= ?
                ORDER BY jaccard DESC
            """
            rows = self._conn.execute(sql, (path, path, path, min_score)).fetchall()
            return [
                {
                    "file_path": row["file_path"],
                    "co_commits": row["co_commits"],
                    "jaccard": float(row["jaccard"]),
                }
                for row in rows
            ]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # S4.7: changes_since()
    # ------------------------------------------------------------------

    def changes_since(self, since: str) -> list[dict[str, Any]]:
        """Return commits and files changed since a date (ISO 8601).

        Future date returns empty list.
        """
        try:
            commit_rows = self._conn.execute(
                """
                SELECT id, hash, author, date, message, files_changed
                FROM commits
                WHERE date >= ?
                ORDER BY date DESC
                """,
                (since,),
            ).fetchall()
        except sqlite3.Error:
            return []

        if not commit_rows:
            return []

        results: list[dict[str, Any]] = []
        for crow in commit_rows:
            commit_id = crow["id"]
            try:
                file_rows = self._conn.execute(
                    """
                    SELECT file_path, change_type, additions, deletions
                    FROM commit_files
                    WHERE commit_id = ?
                    ORDER BY file_path
                    """,
                    (commit_id,),
                ).fetchall()
                files = [dict(r) for r in file_rows]
            except sqlite3.Error:
                files = []

            results.append({
                "hash": crow["hash"],
                "author": crow["author"],
                "date": crow["date"],
                "message": crow["message"],
                "files_changed": crow["files_changed"],
                "files": files,
            })

        return results
