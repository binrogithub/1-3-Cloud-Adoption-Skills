"""Tests for scripts/git_adapter.py — E2 Git History Adapter."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from scripts.git_adapter import (
    GitCommit,
    GitFileChange,
    _is_git_repo,
    _parse_log_output,
    compute_file_coupling,
    parse_git_log,
    read_git_history,
    write_git_history,
)


# ---------------------------------------------------------------------------
# Helper: build a minimal git repo in a temp directory
# ---------------------------------------------------------------------------

def _init_git_repo(path: Path) -> None:
    """Initialise a bare git repo with two commits and two files."""
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True, capture_output=True)

    # Commit 1: add alpha.py and beta.py
    (path / "alpha.py").write_text("x = 1\n")
    (path / "beta.py").write_text("y = 2\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "initial commit"], check=True, capture_output=True)

    # Commit 2: modify alpha.py and beta.py together (co-change)
    (path / "alpha.py").write_text("x = 1\nx += 1\n")
    (path / "beta.py").write_text("y = 2\ny += 1\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "bump both files"], check=True, capture_output=True)

    # Commit 3: add gamma.py alone
    (path / "gamma.py").write_text("z = 3\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "add gamma"], check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Test 1: parse_git_log returns commits with expected fields
# ---------------------------------------------------------------------------

def test_parse_git_log_returns_commits(tmp_path):
    _init_git_repo(tmp_path)
    commits = parse_git_log(tmp_path, max_commits=200)

    assert len(commits) == 3
    # Most recent commit first (git default order)
    assert commits[0].message == "add gamma"
    assert commits[2].message == "initial commit"

    # All commits must have required fields
    for c in commits:
        assert c.hash and len(c.hash) == 40
        assert c.author
        assert c.date  # ISO-8601
        assert c.message

    # "initial commit" added two files
    initial = commits[2]
    assert len(initial.files) == 2
    file_paths = {fc.path for fc in initial.files}
    assert "alpha.py" in file_paths
    assert "beta.py" in file_paths


# ---------------------------------------------------------------------------
# Test 2: non-git directory returns empty list gracefully
# ---------------------------------------------------------------------------

def test_parse_git_log_non_git_returns_empty(tmp_path):
    result = parse_git_log(tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# Test 3: write_git_history is idempotent (second run inserts 0 new commits)
# ---------------------------------------------------------------------------

def test_write_git_history_idempotent(tmp_path):
    _init_git_repo(tmp_path)
    commits = parse_git_log(tmp_path)

    conn = sqlite3.connect(":memory:")
    first_run = write_git_history(conn, commits)
    second_run = write_git_history(conn, commits)
    conn.close()

    assert first_run == 3
    assert second_run == 0


# ---------------------------------------------------------------------------
# Test 4: compute_file_coupling finds co-changed pairs with valid Jaccard
# ---------------------------------------------------------------------------

def test_compute_file_coupling_finds_pair(tmp_path):
    _init_git_repo(tmp_path)
    commits = parse_git_log(tmp_path)

    conn = sqlite3.connect(":memory:")
    write_git_history(conn, commits)

    # alpha.py and beta.py changed together in 2 out of 3 commits —
    # lower min_co_commits to 2 to ensure we see them.
    pairs = compute_file_coupling(conn, min_co_commits=2)
    conn.close()

    assert len(pairs) >= 1
    pair_files = {frozenset([p["file_a"], p["file_b"]]) for p in pairs}
    assert frozenset(["alpha.py", "beta.py"]) in pair_files

    for p in pairs:
        assert 0.0 < p["jaccard"] <= 1.0
        assert p["co_commits"] >= 2


# ---------------------------------------------------------------------------
# Test 5: read_git_history returns EvidenceRecord-compatible dicts
# ---------------------------------------------------------------------------

def test_read_git_history_returns_evidence_dicts(tmp_path):
    _init_git_repo(tmp_path)
    records = read_git_history(tmp_path, max_commits=200)

    assert len(records) == 3

    for rec in records:
        assert rec["evidence_id"].startswith("git-")
        assert len(rec["evidence_id"]) == 12   # "git-" + 8 hex chars
        assert rec["role"] == "git"
        assert rec["tool"] == "commit"
        assert rec["project_match"] is True
        assert "|" in rec["preview"]
        assert rec["timestamp"]  # non-empty ISO date

    # Preview format: "<subject> | <N> files | +<A> -<D>"
    add_gamma = next(r for r in records if "add gamma" in r["preview"])
    assert "1 files" in add_gamma["preview"]
