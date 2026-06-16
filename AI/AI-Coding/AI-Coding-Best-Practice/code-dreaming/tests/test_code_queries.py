"""Tests for scripts/code_queries.py — E4 Code Queries API."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

# Make scripts/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from code_index import CodeIndex  # noqa: E402
from code_queries import CodeQueries  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: indexed temp DB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def indexed_db(tmp_path_factory):
    """Create a temp DB indexed from the code-dreaming repo itself.

    Scope=module so we only pay the indexing cost once.  Returns the Path
    to the DB file.
    """
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "code-index.db"

    repo_root = ROOT  # index the code-dreaming repo

    with CodeIndex.open_or_create(db_path) as idx:
        idx.index_all(repo_root)

    # Inject a small set of synthetic commits so git-related tests work
    # without needing a live git repo.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        # Insert two synthetic commits
        conn.execute(
            "INSERT OR IGNORE INTO commits (hash, author, date, message, files_changed) "
            "VALUES (?, ?, ?, ?, ?)",
            ("aabbccdd11223344", "Test Author", "2025-01-10T12:00:00+00:00",
             "Initial commit", 2),
        )
        c1_id = conn.execute(
            "SELECT id FROM commits WHERE hash = ?", ("aabbccdd11223344",)
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO commit_files (commit_id, file_path, change_type, additions, deletions) "
            "VALUES (?, ?, ?, ?, ?)",
            (c1_id, "scripts/code_index.py", "modified", 10, 5),
        )
        conn.execute(
            "INSERT OR IGNORE INTO commit_files (commit_id, file_path, change_type, additions, deletions) "
            "VALUES (?, ?, ?, ?, ?)",
            (c1_id, "scripts/dream.py", "modified", 3, 1),
        )
        conn.execute(
            "INSERT OR IGNORE INTO commits (hash, author, date, message, files_changed) "
            "VALUES (?, ?, ?, ?, ?)",
            ("bbccdd1122334455", "Test Author", "2025-02-15T09:00:00+00:00",
             "Add git adapter", 2),
        )
        c2_id = conn.execute(
            "SELECT id FROM commits WHERE hash = ?", ("bbccdd1122334455",)
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO commit_files (commit_id, file_path, change_type, additions, deletions) "
            "VALUES (?, ?, ?, ?, ?)",
            (c2_id, "scripts/code_index.py", "modified", 20, 2),
        )
        conn.execute(
            "INSERT OR IGNORE INTO commit_files (commit_id, file_path, change_type, additions, deletions) "
            "VALUES (?, ?, ?, ?, ?)",
            (c2_id, "scripts/git_adapter.py", "added", 50, 0),
        )
        conn.commit()
    finally:
        conn.close()

    return db_path


# ---------------------------------------------------------------------------
# Helper fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def cq(indexed_db):
    """Open a CodeQueries instance over the indexed DB."""
    with CodeQueries(indexed_db) as q:
        yield q


# ---------------------------------------------------------------------------
# S4.1: context manager / lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_context_manager_opens_and_closes(self, indexed_db):
        with CodeQueries(indexed_db) as cq:
            assert cq._conn is not None
        assert cq._conn is None

    def test_explicit_close(self, indexed_db):
        cq = CodeQueries(indexed_db)
        cq.close()
        assert cq._conn is None

    def test_nonexistent_db_returns_empty_not_crash(self, tmp_path):
        """Opening a missing DB must not raise; queries return empty."""
        missing = tmp_path / "no_such.db"
        with CodeQueries(missing) as cq:
            ov = cq.overview()
        assert ov["total_files"] == 0

    def test_double_close_is_safe(self, indexed_db):
        cq = CodeQueries(indexed_db)
        cq.close()
        cq.close()  # must not raise


# ---------------------------------------------------------------------------
# S4.2: overview()
# ---------------------------------------------------------------------------

class TestOverview:
    REQUIRED_KEYS = {
        "total_files",
        "total_symbols",
        "total_edges",
        "total_commits",
        "languages",
        "symbol_kinds",
        "top_files_by_symbols",
        "last_indexed",
    }

    def test_returns_all_required_keys(self, cq):
        ov = cq.overview()
        assert self.REQUIRED_KEYS == set(ov.keys())

    def test_total_files_positive(self, cq):
        ov = cq.overview()
        assert ov["total_files"] > 0

    def test_total_symbols_positive(self, cq):
        ov = cq.overview()
        assert ov["total_symbols"] > 0

    def test_total_commits_positive(self, cq):
        """We injected 2 synthetic commits, so must be >= 2."""
        ov = cq.overview()
        assert ov["total_commits"] >= 2

    def test_languages_is_dict(self, cq):
        ov = cq.overview()
        assert isinstance(ov["languages"], dict)

    def test_languages_contains_python(self, cq):
        ov = cq.overview()
        assert "python" in ov["languages"]
        assert ov["languages"]["python"] > 0

    def test_symbol_kinds_is_dict(self, cq):
        ov = cq.overview()
        assert isinstance(ov["symbol_kinds"], dict)

    def test_top_files_is_list(self, cq):
        ov = cq.overview()
        assert isinstance(ov["top_files_by_symbols"], list)

    def test_top_files_have_required_keys(self, cq):
        ov = cq.overview()
        if ov["top_files_by_symbols"]:
            entry = ov["top_files_by_symbols"][0]
            assert "path" in entry
            assert "symbol_count" in entry

    def test_top_files_at_most_10(self, cq):
        ov = cq.overview()
        assert len(ov["top_files_by_symbols"]) <= 10

    def test_top_files_ordered_desc(self, cq):
        ov = cq.overview()
        counts = [f["symbol_count"] for f in ov["top_files_by_symbols"]]
        assert counts == sorted(counts, reverse=True)

    def test_last_indexed_not_none(self, cq):
        ov = cq.overview()
        assert ov["last_indexed"] is not None

    def test_empty_db_returns_zeros(self, tmp_path):
        """An empty (schema-only) DB should return zeros everywhere."""
        db_path = tmp_path / "empty.db"
        # Create schema but insert nothing
        conn = sqlite3.connect(str(db_path))
        from code_index import create_schema
        create_schema(conn)
        conn.close()

        with CodeQueries(db_path) as cq:
            ov = cq.overview()

        assert ov["total_files"] == 0
        assert ov["total_symbols"] == 0
        assert ov["total_edges"] == 0
        assert ov["total_commits"] == 0
        assert ov["languages"] == {}
        assert ov["top_files_by_symbols"] == []


# ---------------------------------------------------------------------------
# S4.3: search()
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_returns_list(self, cq):
        results = cq.search("parse")
        assert isinstance(results, list)

    def test_search_finds_known_function(self, cq):
        """'parse_git_log' should be discoverable."""
        results = cq.search("parse_git_log")
        names = [r["name"] for r in results]
        assert "parse_git_log" in names

    def test_search_empty_query_returns_empty(self, cq):
        assert cq.search("") == []
        assert cq.search("   ") == []

    def test_search_special_chars_no_crash(self, cq):
        """FTS5 special chars must not raise."""
        for special in ['*', '"quoted"', '(parens)', 'a^b', 'foo:bar']:
            result = cq.search(special)
            assert isinstance(result, list)

    def test_search_limit_respected(self, cq):
        results = cq.search("def", limit=5)
        assert len(results) <= 5

    def test_search_result_has_expected_keys(self, cq):
        results = cq.search("parse")
        if results:
            r = results[0]
            for key in ("name", "kind", "file_path", "start_line"):
                assert key in r, f"Missing key: {key}"

    def test_search_unknown_returns_empty(self, cq):
        results = cq.search("xyzzy_this_cannot_exist_12345")
        assert results == []

    def test_search_class_keyword(self, cq):
        """Searching for 'CodeIndex' should find the class."""
        results = cq.search("CodeIndex")
        names = [r["name"] for r in results]
        assert "CodeIndex" in names


# ---------------------------------------------------------------------------
# S4.4: file_symbols()
# ---------------------------------------------------------------------------

class TestFileSymbols:
    def test_returns_list(self, cq):
        result = cq.file_symbols("scripts/code_index.py")
        assert isinstance(result, list)

    def test_nonexistent_path_returns_empty(self, cq):
        assert cq.file_symbols("no/such/file.py") == []

    def test_symbols_ordered_by_start_line(self, cq):
        result = cq.file_symbols("scripts/code_index.py")
        if len(result) >= 2:
            lines = [r["start_line"] for r in result]
            assert lines == sorted(lines)

    def test_symbols_have_required_keys(self, cq):
        result = cq.file_symbols("scripts/code_index.py")
        if result:
            for key in ("name", "kind", "start_line", "end_line"):
                assert key in result[0], f"Missing key: {key}"

    def test_known_symbols_present(self, cq):
        """CodeIndex class and create_schema function must appear."""
        result = cq.file_symbols("scripts/code_index.py")
        names = [r["name"] for r in result]
        assert "CodeIndex" in names
        assert "create_schema" in names

    def test_git_adapter_symbols(self, cq):
        result = cq.file_symbols("scripts/git_adapter.py")
        names = [r["name"] for r in result]
        assert "parse_git_log" in names


# ---------------------------------------------------------------------------
# S4.5: callers() / callees()
# ---------------------------------------------------------------------------

class TestCallGraph:
    def test_callers_unknown_returns_empty(self, cq):
        assert cq.callers("xyzzy_unknown_symbol_99999") == []

    def test_callees_unknown_returns_empty(self, cq):
        assert cq.callees("xyzzy_unknown_symbol_99999") == []

    def test_callers_returns_list(self, cq):
        # Even for a real symbol, we expect a list (may be empty if no edges)
        result = cq.callers("create_schema")
        assert isinstance(result, list)

    def test_callees_returns_list(self, cq):
        result = cq.callees("index_all")
        assert isinstance(result, list)

    def test_callers_result_keys(self, cq):
        # Use any known symbol that might have edges
        result = cq.callers("create_schema")
        if result:
            for key in ("caller_name", "file_path", "edge_kind"):
                assert key in result[0]

    def test_callees_result_keys(self, cq):
        result = cq.callees("index_all")
        if result:
            for key in ("callee_name", "file_path", "edge_kind"):
                assert key in result[0]


# ---------------------------------------------------------------------------
# S4.6: coupling()
# ---------------------------------------------------------------------------

class TestCoupling:
    def test_coupling_returns_list(self, cq):
        result = cq.coupling("scripts/code_index.py")
        assert isinstance(result, list)

    def test_coupling_no_match_returns_empty(self, cq):
        result = cq.coupling("totally/unknown/path.py")
        assert result == []

    def test_coupling_has_required_keys(self, cq):
        result = cq.coupling("scripts/code_index.py", min_score=0.0)
        if result:
            for key in ("file_path", "co_commits", "jaccard"):
                assert key in result[0]

    def test_coupling_ordered_by_score_desc(self, cq):
        result = cq.coupling("scripts/code_index.py", min_score=0.0)
        if len(result) >= 2:
            scores = [r["jaccard"] for r in result]
            assert scores == sorted(scores, reverse=True)

    def test_coupling_min_score_filter(self, cq):
        result = cq.coupling("scripts/code_index.py", min_score=0.5)
        for r in result:
            assert r["jaccard"] >= 0.5

    def test_coupling_jaccard_between_0_and_1(self, cq):
        result = cq.coupling("scripts/code_index.py", min_score=0.0)
        for r in result:
            assert 0.0 <= r["jaccard"] <= 1.0

    def test_coupling_known_pair(self, cq):
        """code_index.py and dream.py co-changed in synthetic commit 1."""
        # dream.py co-changed with code_index.py in one commit
        result = cq.coupling("scripts/code_index.py", min_score=0.0)
        coupled_paths = [r["file_path"] for r in result]
        # At least one of our injected co-partners should appear
        assert any(
            p in coupled_paths
            for p in ("scripts/dream.py", "scripts/git_adapter.py")
        )


# ---------------------------------------------------------------------------
# S4.7: changes_since()
# ---------------------------------------------------------------------------

class TestChangesSince:
    def test_future_date_returns_empty(self, cq):
        result = cq.changes_since("2099-01-01")
        assert result == []

    def test_returns_list(self, cq):
        result = cq.changes_since("2020-01-01")
        assert isinstance(result, list)

    def test_commits_have_required_keys(self, cq):
        result = cq.changes_since("2020-01-01")
        if result:
            for key in ("hash", "author", "date", "message", "files"):
                assert key in result[0]

    def test_files_is_list(self, cq):
        result = cq.changes_since("2020-01-01")
        if result:
            assert isinstance(result[0]["files"], list)

    def test_file_entries_have_keys(self, cq):
        result = cq.changes_since("2020-01-01")
        for commit in result:
            for f in commit["files"]:
                for key in ("file_path", "change_type", "additions", "deletions"):
                    assert key in f

    def test_synthetic_commits_visible(self, cq):
        """Both injected commits should appear after 2025-01-01."""
        result = cq.changes_since("2025-01-01T00:00:00")
        hashes = [c["hash"] for c in result]
        assert "aabbccdd11223344" in hashes
        assert "bbccdd1122334455" in hashes

    def test_since_filters_older_commits(self, cq):
        """After 2025-02-01, only the Feb commit should appear."""
        result = cq.changes_since("2025-02-01T00:00:00")
        hashes = [c["hash"] for c in result]
        assert "bbccdd1122334455" in hashes
        assert "aabbccdd11223344" not in hashes

    def test_malformed_date_returns_empty_or_list(self, cq):
        """A nonsense date string must not crash; empty result is fine."""
        try:
            result = cq.changes_since("not-a-date")
            assert isinstance(result, list)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"changes_since raised on bad date: {exc}")
