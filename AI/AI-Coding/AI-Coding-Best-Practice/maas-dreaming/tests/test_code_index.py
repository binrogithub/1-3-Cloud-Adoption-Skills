"""Tests for scripts/code_index.py — E1 Tree-Sitter Indexer."""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from pathlib import Path

import pytest

# Ensure the scripts directory is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from code_index import (  # noqa: E402
    LANGUAGE_MAP,
    CodeIndex,
    EdgeInfo,
    FileClassification,
    IndexResult,
    SymbolInfo,
    classify_files,
    create_schema,
    detect_language,
    extract_edges,
    extract_symbols,
    load_grammar,
    walk_files,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_conn():
    """Return an in-memory SQLite connection with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def tmp_repo(tmp_path: Path):
    """A small synthetic repo with a handful of Python files."""
    (tmp_path / "module_a.py").write_text(
        'def hello():\n    """Say hello."""\n    return "hi"\n\nclass MyClass:\n    def method(self):\n        pass\n'
    )
    (tmp_path / "module_b.py").write_text(
        "from module_a import hello\n\ndef goodbye():\n    hello()\n"
    )
    (tmp_path / "data.json").write_text('{"key": "value"}')
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (tmp_path / "compiled.pyc").write_bytes(b"\x00" * 16)
    return tmp_path


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------


class TestCreateSchema:
    def test_tables_created(self, mem_conn):
        tables = {
            row[0]
            for row in mem_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for name in ("files", "symbols", "edges", "schema_version", "project_metadata"):
            assert name in tables, f"Table '{name}' missing"

    def test_schema_version_seeded(self, mem_conn):
        row = mem_conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
        assert row[0] == 2

    def test_wal_mode(self, mem_conn):
        mode = mem_conn.execute("PRAGMA journal_mode").fetchone()[0]
        # :memory: always reports 'memory'; WAL only applies to on-disk DBs
        assert mode in ("wal", "memory")

    def test_foreign_keys_on(self, mem_conn):
        fk = mem_conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_idempotent(self, mem_conn):
        """Calling create_schema twice must not raise."""
        create_schema(mem_conn)  # second call
        row = mem_conn.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()[0]
        assert row == 1  # INSERT OR IGNORE


# ---------------------------------------------------------------------------
# walk_files
# ---------------------------------------------------------------------------


class TestWalkFiles:
    def test_returns_relative_paths(self, tmp_repo: Path):
        files = walk_files(tmp_repo)
        for f in files:
            assert not f.is_absolute(), f"Expected relative path, got {f}"

    def test_skips_binary_extensions(self, tmp_repo: Path):
        files = walk_files(tmp_repo)
        names = [f.name for f in files]
        assert "image.png" not in names
        assert "compiled.pyc" not in names

    def test_includes_text_files(self, tmp_repo: Path):
        files = walk_files(tmp_repo)
        names = [f.name for f in files]
        assert "module_a.py" in names
        assert "module_b.py" in names
        assert "data.json" in names

    def test_skips_ignored_dirs(self, tmp_repo: Path):
        pycache = tmp_repo / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("x = 1")
        files = walk_files(tmp_repo)
        paths_str = [str(f) for f in files]
        assert not any("__pycache__" in p for p in paths_str)

    def test_skips_null_byte_files(self, tmp_repo: Path):
        (tmp_repo / "binary_no_ext").write_bytes(b"looks like text\x00but has null")
        files = walk_files(tmp_repo)
        names = [f.name for f in files]
        assert "binary_no_ext" not in names

    def test_returns_list_of_paths(self, tmp_repo: Path):
        files = walk_files(tmp_repo)
        assert isinstance(files, list)
        assert all(isinstance(f, Path) for f in files)


# ---------------------------------------------------------------------------
# classify_files
# ---------------------------------------------------------------------------


class TestClassifyFiles:
    def test_first_run_all_added(self, mem_conn, tmp_repo: Path):
        files = walk_files(tmp_repo)
        result = classify_files(mem_conn, tmp_repo, files)
        assert len(result["added"]) == len(files)
        assert result["changed"] == []
        assert result["deleted"] == []
        assert result["unchanged"] == []

    def test_second_run_all_unchanged(self, mem_conn, tmp_repo: Path):
        """After inserting fingerprints, same files are unchanged."""
        files = walk_files(tmp_repo)
        # Seed the files table
        with mem_conn:
            for rel in files:
                abs_p = tmp_repo / rel
                st = abs_p.stat()
                sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
                mem_conn.execute(
                    """
                    INSERT INTO files (path, language, size_bytes, mtime_ns,
                                       content_sha256, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(rel), None, st.st_size, st.st_mtime_ns, sha, time.time()),
                )

        result = classify_files(mem_conn, tmp_repo, files)
        assert result["added"] == []
        assert result["changed"] == []
        assert result["deleted"] == []
        assert len(result["unchanged"]) == len(files)

    def test_edited_file_is_changed(self, mem_conn, tmp_repo: Path):
        """Editing a file changes its sha256 -> classified as changed."""
        target = tmp_repo / "module_a.py"
        files = walk_files(tmp_repo)

        # Seed with original stat + sha
        with mem_conn:
            for rel in files:
                abs_p = tmp_repo / rel
                st = abs_p.stat()
                sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
                mem_conn.execute(
                    """
                    INSERT INTO files (path, language, size_bytes, mtime_ns,
                                       content_sha256, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(rel), None, st.st_size, st.st_mtime_ns, sha, time.time()),
                )

        # Overwrite with new content (different size -> stat differs -> slow pass)
        target.write_text("# completely different\ndef new_func(): pass\n")

        result = classify_files(mem_conn, tmp_repo, files)
        changed_names = [p.name for p in result["changed"]]
        assert "module_a.py" in changed_names

    def test_deleted_file_appears_in_deleted(self, mem_conn, tmp_repo: Path):
        files = walk_files(tmp_repo)

        # Seed all files
        with mem_conn:
            for rel in files:
                abs_p = tmp_repo / rel
                st = abs_p.stat()
                sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
                mem_conn.execute(
                    """
                    INSERT INTO files (path, language, size_bytes, mtime_ns,
                                       content_sha256, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(rel), None, st.st_size, st.st_mtime_ns, sha, time.time()),
                )

        # Remove one file from disk; also remove from file_paths list passed
        (tmp_repo / "module_b.py").unlink()
        new_files = [f for f in files if f.name != "module_b.py"]

        result = classify_files(mem_conn, tmp_repo, new_files)
        deleted_names = [p.name for p in result["deleted"]]
        assert "module_b.py" in deleted_names

    def test_returns_correct_keys(self, mem_conn, tmp_repo: Path):
        files = walk_files(tmp_repo)
        result = classify_files(mem_conn, tmp_repo, files)
        assert set(result.keys()) == {"added", "changed", "deleted", "unchanged"}


# ---------------------------------------------------------------------------
# Language detection and grammar loading
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    def test_python_extensions(self):
        assert detect_language(Path("foo.py")) == "python"
        assert detect_language(Path("foo.pyi")) == "python"

    def test_js_extension(self):
        assert detect_language(Path("foo.js")) == "javascript"
        assert detect_language(Path("foo.jsx")) == "javascript"

    def test_ts_extension(self):
        assert detect_language(Path("foo.ts")) == "typescript"

    def test_tsx_extension(self):
        assert detect_language(Path("foo.tsx")) == "tsx"

    def test_unknown_extension(self):
        assert detect_language(Path("foo.xyz")) is None

    def test_case_insensitive(self):
        assert detect_language(Path("FOO.PY")) == "python"


class TestLoadGrammar:
    def test_python_grammar_loads(self):
        grammar = load_grammar("python")
        assert grammar is not None

    def test_javascript_grammar_loads(self):
        grammar = load_grammar("javascript")
        assert grammar is not None

    def test_typescript_grammar_loads(self):
        grammar = load_grammar("typescript")
        assert grammar is not None

    def test_unknown_returns_none(self):
        grammar = load_grammar("cobol")
        assert grammar is None

    def test_caches_result(self):
        g1 = load_grammar("python")
        g2 = load_grammar("python")
        assert g1 is g2  # same object from cache


# ---------------------------------------------------------------------------
# extract_symbols
# ---------------------------------------------------------------------------


class TestExtractSymbols:
    def _parse_python(self, source: str):
        from tree_sitter import Parser

        grammar = load_grammar("python")
        parser = Parser(grammar)
        src_bytes = source.encode()
        tree = parser.parse(src_bytes)
        return tree, src_bytes

    def test_extracts_functions(self):
        src = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        names = [s.name for s in symbols]
        assert "foo" in names
        assert "bar" in names

    def test_extracts_class(self):
        src = "class MyClass:\n    def method(self):\n        pass\n"
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        kinds = {s.name: s.kind for s in symbols}
        assert "MyClass" in kinds
        assert kinds["MyClass"] == "class"
        assert "method" in kinds
        assert kinds["method"] == "method"

    def test_qualified_names(self):
        src = "class Outer:\n    def inner(self):\n        pass\n"
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        qnames = [s.qualified_name for s in symbols]
        assert "Outer" in qnames
        assert "Outer.inner" in qnames

    def test_docstring_extracted(self):
        src = 'def documented():\n    """This is docs."""\n    pass\n'
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        assert len(symbols) >= 1
        sym = next(s for s in symbols if s.name == "documented")
        assert "This is docs" in sym.docstring

    def test_line_numbers(self):
        src = "\n\ndef late_func():\n    pass\n"
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        sym = next(s for s in symbols if s.name == "late_func")
        assert sym.start_line == 3

    def test_returns_list_of_symbol_info(self):
        src = "def simple(): pass\n"
        tree, src_bytes = self._parse_python(src)
        symbols = extract_symbols(tree, src_bytes, "python")
        assert isinstance(symbols, list)
        assert all(isinstance(s, SymbolInfo) for s in symbols)


# ---------------------------------------------------------------------------
# extract_edges
# ---------------------------------------------------------------------------


class TestExtractEdges:
    def _parse_python(self, source: str):
        from tree_sitter import Parser

        grammar = load_grammar("python")
        parser = Parser(grammar)
        src_bytes = source.encode()
        tree = parser.parse(src_bytes)
        return tree, src_bytes

    def test_import_statement(self):
        src = "import os\nimport sys\n"
        tree, src_bytes = self._parse_python(src)
        edges = extract_edges(tree, src_bytes, "python")
        target_names = [e.target_name for e in edges]
        assert "os" in target_names
        assert "sys" in target_names

    def test_from_import(self):
        src = "from pathlib import Path\n"
        tree, src_bytes = self._parse_python(src)
        edges = extract_edges(tree, src_bytes, "python")
        target_names = [e.target_name for e in edges]
        assert any("Path" in t for t in target_names)

    def test_edges_have_kind_imports(self):
        src = "import os\n"
        tree, src_bytes = self._parse_python(src)
        edges = extract_edges(tree, src_bytes, "python")
        assert all(e.kind == "imports" for e in edges)

    def test_returns_list_of_edge_info(self):
        src = "import os\n"
        tree, src_bytes = self._parse_python(src)
        edges = extract_edges(tree, src_bytes, "python")
        assert isinstance(edges, list)
        assert all(isinstance(e, EdgeInfo) for e in edges)

    def test_no_edges_on_empty_file(self):
        src = "x = 1\n"
        tree, src_bytes = self._parse_python(src)
        edges = extract_edges(tree, src_bytes, "python")
        assert edges == []


# ---------------------------------------------------------------------------
# index_all (full pipeline)
# ---------------------------------------------------------------------------


class TestIndexAll:
    def test_first_run_indexes_files(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("def alpha(): pass\n")
        (tmp_path / "b.py").write_text("def beta(): pass\n")

        db_path = tmp_path / "index.db"
        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)

        assert result.added >= 2
        assert result.changed == 0
        assert result.deleted == 0
        assert result.symbols >= 2

    def test_second_run_no_changes(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("def alpha(): pass\n")
        db_path = tmp_path / "index.db"

        with CodeIndex.open_or_create(db_path) as idx:
            idx.index_all(tmp_path)

        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)

        assert result.added == 0
        assert result.changed == 0
        assert result.deleted == 0
        assert result.unchanged >= 1

    def test_changed_file_re_indexed(self, tmp_path: Path):
        f = tmp_path / "a.py"
        f.write_text("def alpha(): pass\n")
        db_path = tmp_path / "index.db"

        with CodeIndex.open_or_create(db_path) as idx:
            idx.index_all(tmp_path)

        # Modify the file
        f.write_text("def alpha(): pass\ndef new_fn(): pass\n")

        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)

        assert result.changed == 1

    def test_deleted_file_removed(self, tmp_path: Path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("def alpha(): pass\n")
        f2.write_text("def beta(): pass\n")
        db_path = tmp_path / "index.db"

        with CodeIndex.open_or_create(db_path) as idx:
            idx.index_all(tmp_path)

        f2.unlink()

        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)

        assert result.deleted == 1

    def test_returns_index_result(self, tmp_path: Path):
        db_path = tmp_path / "index.db"
        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)
        assert isinstance(result, IndexResult)

    def test_duration_ms_positive(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n")
        db_path = tmp_path / "index.db"
        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)
        assert result.duration_ms >= 0

    def test_max_files_cap(self, tmp_path: Path):
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text(f"def fn{i}(): pass\n")
        db_path = tmp_path / "index.db"
        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path, max_files=3)
        # 3 files capped, rest skipped
        assert result.added <= 3

    def test_index_result_str(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        db_path = tmp_path / "index.db"
        with CodeIndex.open_or_create(db_path) as idx:
            result = idx.index_all(tmp_path)
        s = str(result)
        assert "files" in s
        assert "symbols" in s
