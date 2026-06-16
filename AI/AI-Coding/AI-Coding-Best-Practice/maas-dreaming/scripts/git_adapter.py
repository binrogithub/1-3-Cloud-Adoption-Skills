#!/usr/bin/env python3
"""Git history adapter for maas-dreaming.

Reads `git log --numstat` output, populates commits/commit_files tables in
code-index.db, computes file-coupling Jaccard scores, and produces a
TrajectoryResult compatible with dream_sources.py.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GitFileChange:
    path: str
    change_type: str       # "modified" | "added" | "deleted" | "binary"
    additions: int
    deletions: int


@dataclass
class GitCommit:
    hash: str
    author: str
    date: str              # ISO-8601 author date
    message: str
    files: list[GitFileChange] = field(default_factory=list)


# ---------------------------------------------------------------------------
# S2.6: Helper: detect git repo
# ---------------------------------------------------------------------------

def _is_git_repo(path: Path) -> bool:
    """Return True if *path* is inside a git working tree."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ---------------------------------------------------------------------------
# S2.1: Git log parser
# ---------------------------------------------------------------------------

_COMMIT_PREFIX = "COMMIT|"


def parse_git_log(
    repo_root: Path,
    max_commits: int = 200,
    since_date: str | None = None,
) -> list[GitCommit]:
    """Parse git log --numstat into structured commit objects.

    Runs::

        git -C <repo> log --max-count=N \\
            --format='COMMIT|%H|%an|%aI|%s' \\
            --numstat [--since=DATE]

    File paths are made relative to *repo_root* (stripping any worktree
    prefix for sub-project repos inside a monorepo).

    Returns an empty list (rather than raising) for non-git directories or
    any subprocess failure.
    """
    repo_root = Path(repo_root).resolve()

    if not _is_git_repo(repo_root):
        return []

    # Compute the path prefix from worktree root to repo_root.
    # git log outputs paths relative to the worktree root; we want them
    # relative to repo_root so coupling queries match local paths.
    try:
        wt_result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        worktree_root = Path(wt_result.stdout.strip()).resolve() if wt_result.returncode == 0 else repo_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        worktree_root = repo_root

    # The prefix to strip: e.g. "AI/AI-Coding/AI-Coding-Best-Practice/maas-dreaming"
    if worktree_root != repo_root:
        try:
            path_prefix = str(repo_root.relative_to(worktree_root))
        except ValueError:
            path_prefix = ""
    else:
        path_prefix = ""

    cmd = [
        "git", "-C", str(repo_root),
        "log",
        f"--max-count={max_commits}",
        f"--format={_COMMIT_PREFIX}%H|%an|%aI|%s",
        "--numstat",
    ]
    if since_date:
        cmd.append(f"--since={since_date}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    if result.returncode != 0:
        return []

    commits = _parse_log_output(result.stdout)

    # Rebase file paths: strip the worktree→repo_root prefix
    if path_prefix:
        prefix_slash = path_prefix + "/"
        for commit in commits:
            rebased: list[GitFileChange] = []
            for fc in commit.files:
                if fc.path.startswith(prefix_slash):
                    rebased.append(GitFileChange(
                        path=fc.path[len(prefix_slash):],
                        change_type=fc.change_type,
                        additions=fc.additions,
                        deletions=fc.deletions,
                    ))
                elif fc.path == path_prefix:
                    # The path IS the project dir itself — skip (dir-level change)
                    pass
                # Files outside the project are silently dropped
            commit.files = rebased

    return commits


def _parse_log_output(raw: str) -> list[GitCommit]:
    """Parse the raw git log output into GitCommit objects."""
    commits: list[GitCommit] = []
    current: GitCommit | None = None

    for line in raw.splitlines():
        if line.startswith(_COMMIT_PREFIX):
            # Save previous commit
            if current is not None:
                commits.append(current)
            parts = line[len(_COMMIT_PREFIX):].split("|", 3)
            if len(parts) < 4:
                # Malformed header — skip
                current = None
                continue
            hash_, author, date, message = parts
            current = GitCommit(
                hash=hash_.strip(),
                author=author.strip(),
                date=date.strip(),
                message=message.strip(),
            )
        elif current is not None and line.strip():
            # numstat line: "<additions>\t<deletions>\t<path>"
            # Binary files use "-\t-\t<path>"
            fc = _parse_numstat_line(line)
            if fc is not None:
                current.files.append(fc)
        # Blank lines between commit header and numstat block — skip

    if current is not None:
        commits.append(current)

    return commits


def _parse_numstat_line(line: str) -> GitFileChange | None:
    """Parse a single numstat line into a GitFileChange."""
    parts = line.split("\t", 2)
    if len(parts) < 3:
        return None
    add_str, del_str, path = parts
    path = path.strip()
    if not path:
        return None

    # Rename detection: "old-name => new-name" or "{old => new}/suffix"
    # Use the path as-is; downstream consumers can handle rename notation.

    if add_str == "-" and del_str == "-":
        # Binary file
        return GitFileChange(path=path, change_type="binary", additions=0, deletions=0)

    try:
        additions = int(add_str)
        deletions = int(del_str)
    except ValueError:
        return None

    if additions > 0 and deletions == 0:
        change_type = "added"
    elif additions == 0 and deletions > 0:
        change_type = "deleted"
    else:
        change_type = "modified"

    return GitFileChange(
        path=path,
        change_type=change_type,
        additions=additions,
        deletions=deletions,
    )


# ---------------------------------------------------------------------------
# S2.2: Write commits to code-index.db
# ---------------------------------------------------------------------------

def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create commits/commit_files tables if they do not yet exist."""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commit_files (
            commit_id   INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
            file_path   TEXT NOT NULL,
            change_type TEXT,
            additions   INTEGER DEFAULT 0,
            deletions   INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_commit_files_path ON commit_files(file_path);"
    )
    conn.commit()


def write_git_history(conn: sqlite3.Connection, commits: list[GitCommit]) -> int:
    """Insert commits and their file-change records into *conn*.

    Uses INSERT OR IGNORE so re-runs are idempotent.  Returns the count of
    newly inserted commits (rows whose INSERT succeeded).
    """
    _ensure_tables(conn)

    new_count = 0
    for commit in commits:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO commits (hash, author, date, message, files_changed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (commit.hash, commit.author, commit.date, commit.message, len(commit.files)),
        )
        if cur.rowcount == 0:
            # Already existed — skip its files too
            continue
        new_count += 1
        commit_id = cur.lastrowid
        for fc in commit.files:
            conn.execute(
                """
                INSERT OR IGNORE INTO commit_files
                    (commit_id, file_path, change_type, additions, deletions)
                VALUES (?, ?, ?, ?, ?)
                """,
                (commit_id, fc.path, fc.change_type, fc.additions, fc.deletions),
            )
    conn.commit()
    return new_count


# ---------------------------------------------------------------------------
# S2.3: File coupling analysis
# ---------------------------------------------------------------------------

def compute_file_coupling(
    conn: sqlite3.Connection,
    min_co_commits: int = 3,
) -> list[dict[str, Any]]:
    """Return file pairs that co-changed in >= *min_co_commits* commits.

    Each result dict has keys:
      file_a, file_b, co_commits, jaccard

    Jaccard = |commits_both| / |commits_either|

    The result set is ordered by jaccard descending.
    """
    _ensure_tables(conn)

    # Self-join commit_files to find co-changed pairs within the same commit.
    # Use file_a < file_b to avoid duplicates.
    sql = """
        WITH pair_commits AS (
            SELECT
                cf1.file_path AS file_a,
                cf2.file_path AS file_b,
                cf1.commit_id
            FROM commit_files cf1
            JOIN commit_files cf2
                ON cf1.commit_id = cf2.commit_id
               AND cf1.file_path < cf2.file_path
        ),
        pair_counts AS (
            SELECT
                file_a,
                file_b,
                COUNT(*) AS co_commits
            FROM pair_commits
            GROUP BY file_a, file_b
            HAVING co_commits >= ?
        ),
        file_commit_counts AS (
            SELECT file_path, COUNT(DISTINCT commit_id) AS total_commits
            FROM commit_files
            GROUP BY file_path
        )
        SELECT
            pc.file_a,
            pc.file_b,
            pc.co_commits,
            CAST(pc.co_commits AS REAL) /
                (fca.total_commits + fcb.total_commits - pc.co_commits) AS jaccard
        FROM pair_counts pc
        JOIN file_commit_counts fca ON fca.file_path = pc.file_a
        JOIN file_commit_counts fcb ON fcb.file_path = pc.file_b
        ORDER BY jaccard DESC
    """
    rows = conn.execute(sql, (min_co_commits,)).fetchall()
    return [
        {
            "file_a": row[0],
            "file_b": row[1],
            "co_commits": row[2],
            "jaccard": float(row[3]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# S2.4: TrajectoryResult adapter
# ---------------------------------------------------------------------------

def read_git_history(
    repo_root: Path,
    max_commits: int = 200,
) -> list[dict[str, Any]]:
    """Return git commits as EvidenceRecord-compatible dicts.

    Each dict has the keys expected by dream_sources.load_trajectory when it
    handles the _GIT_SENTINEL:

        evidence_id  : "git-<short_hash>"
        timestamp    : ISO-8601 author date
        role         : "git"
        tool         : "commit"
        preview      : "<subject> | <N> files | +<A> -<D>"
        project_match: True  (all commits belong to the project)
    """
    repo_root = Path(repo_root).resolve()
    commits = parse_git_log(repo_root, max_commits=max_commits)

    records: list[dict[str, Any]] = []
    for commit in commits:
        total_add = sum(fc.additions for fc in commit.files)
        total_del = sum(fc.deletions for fc in commit.files)
        n_files = len(commit.files)
        subject = commit.message[:120]  # bounded
        preview = f"{subject} | {n_files} files | +{total_add} -{total_del}"

        records.append({
            "evidence_id": f"git-{commit.hash[:8]}",
            "timestamp": commit.date,
            "role": "git",
            "tool": "commit",
            "preview": preview,
            "project_match": True,
        })

    return records


# ---------------------------------------------------------------------------
# CLI __main__
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse git history and optionally store it in code-index.db."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Root of the git repository (default: current directory)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database.  When omitted, results are printed only.",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=200,
        help="Maximum number of commits to parse (default: 200)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include commits after this date (git --since format)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    commits = parse_git_log(repo_root, max_commits=args.max_commits, since_date=args.since)

    print(f"Parsed {len(commits)} commits from {repo_root}")

    if args.db:
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            new = write_git_history(conn, commits)
            print(f"Inserted {new} new commits into {db_path}")
            pairs = compute_file_coupling(conn)
            print(f"File coupling pairs (min_co_commits=3): {len(pairs)}")
            for p in pairs[:10]:
                print(
                    f"  {p['file_a']} <-> {p['file_b']}  "
                    f"co={p['co_commits']} jaccard={p['jaccard']:.3f}"
                )
        finally:
            conn.close()
    else:
        # Print sample records
        records = read_git_history(repo_root, max_commits=args.max_commits)
        for rec in records[:5]:
            print(
                f"  {rec['evidence_id']}  {rec['timestamp']}  {rec['preview'][:80]}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
