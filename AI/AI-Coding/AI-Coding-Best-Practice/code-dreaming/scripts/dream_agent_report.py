#!/usr/bin/env python3
"""Host-agent-entry dream report helper.

This helper is intentionally non-LLM: it discovers bounded trajectory evidence
and writes a review-only report scaffold for the agent process that invoked the
skill. The skill caller can then summarize or amend the report without spawning
a nested LLM process.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the skill root is on sys.path so `from scripts.*` works when this
# script is invoked by absolute path from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from scripts.dream_llm import default_memory_dir
    from scripts.dream_signals import class_counts, scan_records
    from scripts.dream_sources import TrajectoryResult, load_trajectory, redact
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from dream_llm import default_memory_dir
    from dream_signals import class_counts, scan_records
    from dream_sources import TrajectoryResult, load_trajectory, redact

# ---------------------------------------------------------------------------
# Guarded imports for code-index integration (E5)
# ---------------------------------------------------------------------------
try:
    try:
        from scripts.code_index import CodeIndex
        from scripts.code_queries import CodeQueries
    except ModuleNotFoundError:
        from code_index import CodeIndex  # type: ignore[no-redef]
        from code_queries import CodeQueries  # type: ignore[no-redef]
    _CODE_INDEX_AVAILABLE = True
except Exception:  # noqa: BLE001
    _CODE_INDEX_AVAILABLE = False

logger = logging.getLogger(__name__)

# Match the official Anthropic Dreams `instructions` length limit.
MAX_INSTRUCTIONS_CHARS = 4096

# Project-root output mode writes here so it never clobbers a repo's own memory/.
PROJECT_ROOT_DIRNAME = ".code-dreaming"
INDEX_FILE = "DREAMS.md"
POINTER_FILE = "POINTER.suggested.md"
REPORT_GLOB = "dream-agent-*.report.md"
DEFAULT_KEEP = 20

_INDEX_ENTRY_RE = re.compile(r"^- \[[^\]]+\]\(inbox/([^)]+)\)")

# Source file extensions that indicate a real project worth indexing
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".c", ".h", ".cpp",
    ".sh", ".bash",
}


def normalize_instructions(raw: str | None) -> str:
    """Bound and secret-redact free-text steering instructions."""
    if not raw:
        return ""
    return redact(raw.strip())[:MAX_INSTRUCTIONS_CHARS]


def resolve_base_dir(output_mode: str, out_dir: str | None, memory_dir: Path,
                     repo_root: Path) -> Path:
    """Resolve the artifact base dir: out-dir > project-root > native memory."""
    if out_dir:
        return Path(out_dir).expanduser().resolve()
    if output_mode == "project-root":
        return repo_root / PROJECT_ROOT_DIRNAME
    return memory_dir


def report_summary(trajectory: TrajectoryResult, max_records: int) -> str:
    """One-line index summary for a report (deterministic, no secrets)."""
    if trajectory.no_trajectory:
        return f"adapter={trajectory.adapter} records=0 (no trajectory)"
    counts = class_counts(scan_records(trajectory.records, limit=max_records,
                                       require_role=frozenset({"human", "user", "assistant"})))
    signal = " ".join(f"{name}={counts[name]}" for name in counts)
    return (f"adapter={trajectory.adapter} records={len(trajectory.records)} "
            f"signals: {signal}")


def _existing_index_entries(index_path: Path, inbox: Path) -> list[str]:
    """Parse prior index entries, keeping only those whose report still exists."""
    if not index_path.exists():
        return []
    kept: list[str] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        match = _INDEX_ENTRY_RE.match(line)
        if match and (inbox / match.group(1)).exists():
            kept.append(line)
    return kept


def update_index(base_dir: Path, report_path: Path, summary: str, keep: int) -> Path:
    """Rebuild the skill-owned DREAMS.md index newest-first and apply retention."""
    inbox = base_dir / "inbox"
    index_path = base_dir / INDEX_FILE
    name = report_path.name
    new_entry = f"- [{name}](inbox/{name}) — {summary}"
    prior = [e for e in _existing_index_entries(index_path, inbox)
             if not e.startswith(f"- [{name}](")]
    entries = [new_entry, *prior]

    if keep and keep > 0 and len(entries) > keep:
        for stale in entries[keep:]:
            match = _INDEX_ENTRY_RE.match(stale)
            if match:
                target = inbox / match.group(1)
                if target.name.startswith("dream-agent-") and target.exists():
                    target.unlink()
        entries = entries[:keep]

    header = [
        f"# code-dreaming — consolidated dream reports ({INDEX_FILE})",
        "",
        "> Review-only, generated by code-dreaming. Commit this directory to share"
        " dream findings across the team.",
        "> Never auto-applied to CLAUDE.md or MEMORY.md.",
        "",
    ]
    index_path.write_text("\n".join(header + entries) + "\n", encoding="utf-8")
    return index_path


def write_pointer(base_dir: Path) -> Path:
    """Emit a governance-safe CLAUDE.md pointer suggestion (never auto-applied)."""
    pointer_path = base_dir / POINTER_FILE
    rel = base_dir.name if base_dir.name else str(base_dir)
    pointer_path.write_text(
        "# Suggested CLAUDE.md pointer (paste once, reviewed via PR)\n\n"
        "code-dreaming never edits CLAUDE.md. To make these shared dream reports\n"
        "auto-discoverable by every teammate's next session, add one line to the\n"
        "repo CLAUDE.md:\n\n"
        f"> See `{rel}/{INDEX_FILE}` for consolidated, review-only dream memory.\n",
        encoding="utf-8",
    )
    return pointer_path


# ---------------------------------------------------------------------------
# E5 helper: default DB path
# ---------------------------------------------------------------------------

def default_db_path(repo_root: Path) -> Path:
    """Return the conventional code-index DB path for repo_root."""
    return Path(repo_root) / PROJECT_ROOT_DIRNAME / "code-index.db"


# ---------------------------------------------------------------------------
# E5 helper: detect whether the directory has source files worth indexing
# ---------------------------------------------------------------------------

def _has_source_files(repo_root: Path) -> bool:
    """Return True if repo_root contains at least one source file."""
    repo_root = Path(repo_root)
    for dirpath, dirnames, filenames in os.walk(str(repo_root)):
        # Prune directories that should not be scanned
        dirnames[:] = [
            d for d in dirnames
            if d not in {".git", ".hg", "node_modules", "vendor", "build",
                         "dist", "__pycache__", ".venv", ".code-dreaming",
                         ".mypy_cache", ".pytest_cache"}
        ]
        for fname in filenames:
            if Path(fname).suffix.lower() in _SOURCE_EXTENSIONS:
                return True
    return False


# ---------------------------------------------------------------------------
# E5 helper: cold-start report
# ---------------------------------------------------------------------------

def _cold_start_report(repo_root: Path, instructions: str = "") -> str:
    """Return a helpful guidance report when no trajectory or code-index exists."""
    repo_root = Path(repo_root)
    is_git = (repo_root / ".git").exists()

    lines = [
        "# Dream Report: Cold Start",
        "",
        f"Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Status",
        "",
        "No trajectory evidence and no code-index database were found.",
        "This is a fresh project or first run.",
        "",
    ]

    if instructions:
        lines.extend([
            "## Steering Instructions",
            "",
            "- The caller steered this run. Apply the following when summarizing"
            " durable findings:",
            "",
            f"> {instructions}",
            "",
        ])

    lines.extend([
        "## How to Get Started",
        "",
    ])

    if is_git:
        lines.extend([
            "This directory is a git repository. Run the code indexer to build",
            "the initial project knowledge base:",
            "",
            "```",
            "python3 scripts/code_index.py --repo-root .",
            "```",
            "",
            "After indexing, run `/code-dreaming` again to get a full dream report",
            "with project overview, key symbols, coupling insights, and recent activity.",
            "",
        ])
    else:
        lines.extend([
            "code-dreaming works best with either:",
            "",
            "1. **Session trajectory** — start a Claude Code session and run",
            "   `/code-dreaming` after working for a while.",
            "2. **Code index** — run `python3 scripts/code_index.py --repo-root .`",
            "   to build a structural index of the project.",
            "",
            "If you have session data in a `.jsonl` file, pass it with `--trajectory`.",
            "",
        ])

    lines.extend([
        "## Next Steps",
        "",
        "- Index the project: `python3 scripts/code_index.py --repo-root .`",
        "- Then re-run the dream report to see full analysis.",
    ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# E5 section helpers
# ---------------------------------------------------------------------------

def _section_overview(cq: "CodeQueries") -> list[str]:
    """Build the Project Overview section from CodeQueries.overview()."""
    try:
        ov = cq.overview()
    except Exception:  # noqa: BLE001
        return []

    total_files = ov.get("total_files", 0)
    total_symbols = ov.get("total_symbols", 0)
    total_edges = ov.get("total_edges", 0)
    total_commits = ov.get("total_commits", 0)
    languages = ov.get("languages", {})
    symbol_kinds = ov.get("symbol_kinds", {})
    last_indexed = ov.get("last_indexed")

    # Nothing worth showing if the DB is completely empty
    if total_files == 0 and total_symbols == 0:
        return []

    lines = ["## Project Overview", ""]

    # Files + languages
    lang_detail = ", ".join(f"{lang}: {cnt}" for lang, cnt in languages.items())
    lang_str = f" ({lang_detail})" if lang_detail else ""
    lines.append(f"- **{total_files} files** across {len(languages)} language(s){lang_str}")

    # Symbols
    kind_detail = ", ".join(f"{k}: {v}" for k, v in symbol_kinds.items())
    kind_str = f" ({kind_detail})" if kind_detail else ""
    lines.append(f"- **{total_symbols} symbols**{kind_str}")

    # Edges
    lines.append(f"- **{total_edges} cross-reference edges**")

    # Commits
    if total_commits:
        lines.append(f"- **{total_commits} commits** recorded")

    # Last indexed — convert epoch int to ISO if needed
    if last_indexed:
        try:
            ts = float(last_indexed)
            last_indexed = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            pass  # keep as-is if it's already a string
        lines.append(f"- Last indexed: {last_indexed}")

    lines.append("")
    return lines


def _section_key_symbols(cq: "CodeQueries") -> list[str]:
    """Build the Key Symbols section: top 15 by caller+callee edge count."""
    try:
        # Pull all symbols with their file paths and line numbers
        rows = cq._conn.execute(
            """
            SELECT
                s.name,
                s.kind,
                f.path AS file_path,
                s.start_line,
                (SELECT COUNT(*) FROM edges e WHERE e.target_id = s.id) AS callers_count,
                (SELECT COUNT(*) FROM edges e WHERE e.source_id = s.id) AS callees_count
            FROM symbols s
            JOIN files f ON f.id = s.file_id
            ORDER BY (callers_count + callees_count) DESC
            LIMIT 15
            """
        ).fetchall()
    except Exception:  # noqa: BLE001
        return []

    if not rows:
        return []

    # Only include rows with at least one edge connection to avoid noise
    rows = [r for r in rows if (r["callers_count"] + r["callees_count"]) > 0]
    if not rows:
        return []

    lines = [
        "## Key Symbols",
        "",
        "| Symbol | Kind | File | Callers | Callees |",
        "|--------|------|------|---------|---------|",
    ]
    for row in rows:
        file_ref = f"{row['file_path']}:{row['start_line']}"
        lines.append(
            f"| `{row['name']}` | {row['kind']} | {file_ref} "
            f"| {row['callers_count']} | {row['callees_count']} |"
        )
    lines.append("")
    return lines


_NOISE_FILENAMES = frozenset({".gitkeep", ".keep", ".empty", ".gitmodules"})


def _is_noise_path(path: str) -> bool:
    name = Path(path).name
    if name in _NOISE_FILENAMES:
        return True
    if not Path(path).suffix:
        return True
    return False


_MAX_COUPLING_PAIRS = 20


def _section_coupling(cq: "CodeQueries", repo_root: Path | None = None) -> list[str]:
    """Build the Frequently Co-Changed Files section from coupling data.

    Only includes paths within *repo_root* (if given) and caps at
    _MAX_COUPLING_PAIRS to avoid monorepo noise.
    """
    # Determine project-local prefix for filtering
    project_prefix: str | None = None
    if repo_root is not None:
        project_prefix = repo_root.name

    try:
        # Get all files that appear in commit_files
        file_rows = cq._conn.execute(
            """
            SELECT DISTINCT file_path FROM commit_files
            ORDER BY file_path
            """
        ).fetchall()
    except Exception:  # noqa: BLE001
        return []

    if not file_rows:
        return []

    def _in_project(path: str) -> bool:
        if project_prefix is None:
            return True
        # Path is within the project if it starts with the project dir name
        # or doesn't contain a path separator (top-level file)
        if path.startswith(project_prefix + "/") or path.startswith(project_prefix + "\\"):
            return True
        # Also accept paths that don't cross into sibling projects
        # (no AI/ or other top-level sibling dirs)
        first_part = path.split("/")[0].split("\\")[0]
        if first_part == project_prefix:
            return True
        # Paths without a sibling-project prefix are local
        if "/" not in path and "\\" not in path:
            return True
        return False

    seen_pairs: set[frozenset[str]] = set()
    coupling_lines: list[str] = []

    for frow in file_rows:
        if len(coupling_lines) >= _MAX_COUPLING_PAIRS:
            break
        path = frow["file_path"]
        if _is_noise_path(path) or not _in_project(path):
            continue
        try:
            pairs = cq.coupling(path, min_score=0.4)
        except Exception:  # noqa: BLE001
            continue
        for pair in pairs:
            if len(coupling_lines) >= _MAX_COUPLING_PAIRS:
                break
            if _is_noise_path(pair["file_path"]) or not _in_project(pair["file_path"]):
                continue
            key = frozenset([path, pair["file_path"]])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            coupling_lines.append(
                f"- `{path}` <-> `{pair['file_path']}` "
                f"(score: {pair['jaccard']:.2f}, {pair['co_commits']} co-commits)"
            )

    if not coupling_lines:
        return []

    lines = ["## Frequently Co-Changed Files", ""]
    lines.extend(coupling_lines)
    lines.append("")
    return lines


def _section_recent_activity(cq: "CodeQueries", days: int = 7) -> list[str]:
    """Build the Recent Activity section from git history."""
    since_dt = datetime.now(tz=timezone.utc) - timedelta(days=days)
    since_str = since_dt.strftime("%Y-%m-%d")

    try:
        commits = cq.changes_since(since_str)
    except Exception:  # noqa: BLE001
        commits = []

    lines = [f"## Recent Activity (last {days} days)", ""]

    if not commits:
        lines.append(f"- No commits in the last {days} days.")
        lines.append("")
        return lines

    # Aggregate per-file activity
    file_commits: dict[str, int] = {}
    file_additions: dict[str, int] = {}
    file_deletions: dict[str, int] = {}
    new_files: list[str] = []

    for commit in commits:
        for finfo in commit.get("files", []):
            fp = finfo["file_path"]
            file_commits[fp] = file_commits.get(fp, 0) + 1
            file_additions[fp] = file_additions.get(fp, 0) + (finfo.get("additions") or 0)
            file_deletions[fp] = file_deletions.get(fp, 0) + (finfo.get("deletions") or 0)
            if finfo.get("change_type") == "A" and fp not in new_files:
                new_files.append(fp)

    total_files_changed = len(file_commits)
    lines.append(f"- {len(commits)} commit(s), {total_files_changed} file(s) changed")

    if file_commits:
        most_active = max(file_commits, key=lambda f: file_commits[f])
        adds = file_additions.get(most_active, 0)
        dels = file_deletions.get(most_active, 0)
        lines.append(
            f"- Most active: `{most_active}` "
            f"({file_commits[most_active]} commit(s), +{adds} -{dels})"
        )

    if new_files:
        new_str = ", ".join(f"`{f}`" for f in new_files[:5])
        if len(new_files) > 5:
            new_str += f" (+{len(new_files) - 5} more)"
        lines.append(f"- New files: {new_str}")

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Main render function (E5 enhanced)
# ---------------------------------------------------------------------------

def render_report(
    repo_root: Path,
    trajectory: TrajectoryResult | None = None,
    max_records: int = 20,
    instructions: str = "",
    code_index_db: Path | None = None,
) -> str:
    """Render a dream report combining code-index insights and trajectory signals.

    Parameters
    ----------
    repo_root:
        Root directory of the project being dreamed.
    trajectory:
        Loaded trajectory evidence. May be None when invoked in code-index-only mode.
    max_records:
        Maximum evidence records to process.
    instructions:
        Optional steering instructions from the caller.
    code_index_db:
        Path to the code-index SQLite database. When None the conventional
        ``<repo_root>/.code-dreaming/code-index.db`` path is used.
    """
    repo_root = Path(repo_root)

    has_trajectory = trajectory is not None and not trajectory.no_trajectory

    # Resolve code-index DB path
    if code_index_db is None:
        code_index_db = default_db_path(repo_root)
    has_code_index = _CODE_INDEX_AVAILABLE and code_index_db.exists() and code_index_db.stat().st_size > 0

    # S5.1: Cold-start gate
    if not has_trajectory and not has_code_index:
        return _cold_start_report(repo_root, instructions)

    # S5.2: Auto-index on first run (no DB but source files exist)
    if _CODE_INDEX_AVAILABLE and not has_code_index and _has_source_files(repo_root):
        try:
            t0 = time.monotonic()
            logger.info("First run: indexing project...")
            idx = CodeIndex.open_or_create(code_index_db)
            result = idx.index_all(repo_root)
            idx.close()
            elapsed = time.monotonic() - t0
            logger.info("First run: indexed %s in %.1fs", result, elapsed)
            has_code_index = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto-index failed: %s", exc)

    # Build report sections
    lines: list[str] = []

    # S5.8: Header
    project_name = repo_root.name or str(repo_root)
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.extend([
        f"# Dream Report: {project_name}",
        "",
        f"Generated: {ts}",
        "",
        f"- repo_root: `{repo_root}`",
        "- mode: `host-agent-entry`",
    ])

    if trajectory is not None:
        lines.extend([
            f"- trajectory_adapter: `{trajectory.adapter}`",
            f"- source_path: `{trajectory.source_path or '(none)'}`",
            f"- evidence_records: {len(trajectory.records)}",
        ])

    lines.append("")

    # Steering instructions section
    if instructions:
        lines.extend([
            "## Steering Instructions",
            "",
            "- The caller steered this run. Apply the following when summarizing"
            " durable findings:",
            "",
            f"> {instructions}",
            "",
        ])

    # S5.3–5.6: Code-index sections
    if has_code_index and _CODE_INDEX_AVAILABLE:
        try:
            with CodeQueries(code_index_db) as cq:
                lines.extend(_section_overview(cq))
                lines.extend(_section_key_symbols(cq))
                lines.extend(_section_coupling(cq, repo_root=repo_root))
                lines.extend(_section_recent_activity(cq))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Code-index sections failed: %s", exc)

    # Existing trajectory sections
    if trajectory is not None:
        lines.extend(["## Summary", ""])
        if trajectory.no_trajectory:
            lines.append(f"- No trajectory evidence was available: {trajectory.reason}.")
        else:
            lines.append("- Trajectory evidence was discovered and bounded for host-agent review.")
            lines.append("- No memory, CLAUDE.md, AGENTS.md, or global memory file was edited.")
        lines.extend(["", "## Evidence Preview", ""])
        for record in trajectory.records[:max_records]:
            lines.append(
                f"- {record.evidence_id} | time={record.timestamp or 'unknown'} | "
                f"role={record.role or '-'} | tool={record.tool or '-'} | "
                f"project_match={str(record.project_match).lower()} | {record.preview}"
            )
        if not trajectory.records:
            lines.append("- No evidence records.")

        # S5.7: Signal scan with role filter
        if not trajectory.no_trajectory:
            lines.extend(["", "## Signal Scan", ""])
            hits = scan_records(
                trajectory.records,
                limit=max_records,
                require_role=frozenset({"human", "user", "assistant"}),
            )
            counts = class_counts(hits)
            lines.append(
                "- Deterministic taxonomy over bounded evidence (review-only, "
                "no memory written): "
                + ", ".join(f"{name}={counts[name]}" for name in counts)
                + "."
            )
            if hits:
                lines.append("")
                for hit in hits:
                    lines.append(
                        f"- [{hit.signal_class}] {hit.evidence_id} | "
                        f"role={hit.role} | time={hit.timestamp} | {hit.preview}"
                    )
            else:
                lines.append("- No corrections/preferences/decisions/recurring signals matched.")

    lines.extend([
        "",
        "## Candidates",
        "",
        "- Review-only scaffold. The invoking host agent should add any durable candidates it can justify from the evidence.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a host-agent-entry dreaming summary report.")
    parser.add_argument("--memory-dir")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--trajectory")
    parser.add_argument(
        "--instructions",
        default=os.environ.get("MCE_DREAM_INSTRUCTIONS"),
        help="Optional free-text steering for this run (<=4096 chars, secret-redacted).",
    )
    parser.add_argument(
        "--output-mode",
        choices=("native", "project-root"),
        default="native",
        help="native (default, ~/.claude memory) or project-root (<repo>/.code-dreaming, git-shareable).",
    )
    parser.add_argument(
        "--out-dir",
        help="Explicit artifact base dir (e.g. ./memory). Overrides --output-mode.",
    )
    parser.add_argument(
        "--keep", type=int, default=DEFAULT_KEEP,
        help="Retain this many newest reports (0 = unlimited). Default 20.",
    )
    parser.add_argument("--max-bytes", type=int, default=200_000)
    parser.add_argument("--max-records", type=int, default=20)
    # E5: new CLI flags
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the code-index SQLite database (default: <repo-root>/.code-dreaming/code-index.db).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve()
    memory_dir = Path(args.memory_dir).expanduser().resolve() if args.memory_dir else default_memory_dir(repo_root)
    memory_dir.mkdir(parents=True, exist_ok=True)
    # Trajectory evidence always comes from the native memory root, even when the
    # report is written elsewhere, so discovery/dedup stay keyed on native memory.
    trajectory = load_trajectory(args.trajectory, memory_dir, repo_root, max_bytes=args.max_bytes)
    instructions = normalize_instructions(args.instructions)

    # Resolve code-index DB path from CLI flag
    code_index_db: Path | None = None
    if args.db:
        code_index_db = Path(args.db).expanduser().resolve()

    shared = bool(args.out_dir) or args.output_mode != "native"
    base_dir = resolve_base_dir(args.output_mode, args.out_dir, memory_dir, repo_root)
    inbox = base_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_path = inbox / f"dream-agent-{stamp}.report.md"
    report_path.write_text(
        render_report(repo_root, trajectory, args.max_records, instructions, code_index_db),
        encoding="utf-8",
    )

    index_path = update_index(
        base_dir, report_path, report_summary(trajectory, args.max_records), args.keep,
    )
    if shared:
        write_pointer(base_dir)

    print(report_path)
    print(f"index: {index_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
