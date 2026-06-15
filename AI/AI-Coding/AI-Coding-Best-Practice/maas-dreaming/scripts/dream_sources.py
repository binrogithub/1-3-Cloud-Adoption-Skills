#!/usr/bin/env python3
"""Trajectory source adapters for the review-only LLM dream path.

The adapters are intentionally conservative: every source is read-only, previews
are bounded, and unsupported/missing sources produce a typed no-trajectory result
instead of raising into the caller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PREVIEW_CHARS = 600
DEFAULT_MAX_BYTES = 200_000
DEFAULT_MAX_RECORDS = 200


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    timestamp: str
    role: str
    tool: str
    preview: str
    source_path: str
    project_match: bool


@dataclass(frozen=True)
class TrajectoryResult:
    adapter: str
    source_path: str
    records: list[EvidenceRecord]
    no_trajectory: bool = False
    reason: str = ""


_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,}]+"),
    re.compile(r"(?i)\b(authorization:\s*bearer)\s+[A-Za-z0-9._~+/-]+=*"),
]


def redact(text: str) -> str:
    """Redact obvious secrets before evidence is sent to an LLM prompt."""
    redacted = str(text)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)} [REDACTED]" if m.lastindex else "[REDACTED]", redacted)
    return redacted


def bounded_preview(value: Any, limit: int = DEFAULT_PREVIEW_CHARS) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = "" if value is None else str(value)
    compact = re.sub(r"\s+", " ", text).strip()
    text = redact(compact)
    if len(text) <= limit:
        return text
    suffix = " ...[truncated]"
    if text != compact and "[REDACTED]" not in text[: max(0, limit - len(suffix))]:
        suffix = " [REDACTED]" + suffix
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def _stable_id(source: Path, *parts: Any) -> str:
    basis = "|".join([str(source.resolve()), *(str(p) for p in parts)])
    return "ev-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _project_match(text: str, repo_root: Path | None) -> bool:
    if not repo_root:
        return False
    root = str(repo_root.resolve())
    return root in text or repo_root.name in text


def _record(
    source: Path,
    key: Any,
    timestamp: Any,
    role: Any,
    tool: Any,
    preview: Any,
    repo_root: Path | None,
    preview_chars: int,
) -> EvidenceRecord:
    full_text = bounded_preview(preview, max(preview_chars, len(str(preview)) + 32))
    preview_text = bounded_preview(preview, preview_chars)
    return EvidenceRecord(
        evidence_id=_stable_id(source, key),
        timestamp="" if timestamp is None else str(timestamp),
        role="" if role is None else str(role),
        tool="" if tool is None else str(tool),
        preview=preview_text,
        source_path=str(source),
        project_match=_project_match(full_text, repo_root),
    )


def _json_get(data: Any, *keys: str) -> Any:
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                return data[key]
    return None


def _text_from_json(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    for key in ("text", "content", "message", "input", "output"):
        if key in data:
            return data[key]
    if "state" in data:
        return data["state"]
    return data


def read_jsonl(path: Path, repo_root: Path | None, max_records: int, max_bytes: int, preview_chars: int) -> TrajectoryResult:
    records: list[EvidenceRecord] = []
    consumed = 0
    with path.open("rb") as raw:
        for idx, line in enumerate(raw, start=1):
            consumed += len(line)
            if consumed > max_bytes or len(records) >= max_records:
                break
            if not line.strip():
                continue
            try:
                obj = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            preview = _json_get(obj, "text", "content", "message", "input", "output") or obj
            records.append(
                _record(
                    path,
                    _json_get(obj, "id", "message_id", "session_id") or idx,
                    _json_get(obj, "time", "timestamp", "time_created", "created_at"),
                    _json_get(obj, "role", "actor"),
                    _json_get(obj, "tool", "name"),
                    preview,
                    repo_root,
                    preview_chars,
                )
            )
    return TrajectoryResult("jsonl", str(path), records)


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def read_sqlite(path: Path, repo_root: Path | None, max_records: int, max_bytes: int, preview_chars: int) -> TrajectoryResult:
    records: list[EvidenceRecord] = []
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = _sqlite_tables(conn)
        if {"message", "part"}.issubset(tables):
            query = """
                SELECT p.id, p.session_id, p.time_created, m.data, p.data
                FROM part p
                LEFT JOIN message m ON m.id = p.message_id
                ORDER BY COALESCE(p.time_created, ''), p.id
                LIMIT ?
            """
            consumed = 0
            for part_id, session_id, time_created, message_data, part_data in conn.execute(query, (max_records,)):
                message = _loads_json(message_data)
                part = _loads_json(part_data)
                consumed += len(str(part_data or ""))
                if consumed > max_bytes:
                    break
                records.append(
                    _record(
                        path,
                        f"{session_id}:{part_id}",
                        time_created,
                        _json_get(message, "role"),
                        _json_get(part, "tool"),
                        _text_from_json(part),
                        repo_root,
                        preview_chars,
                    )
                )
        elif "message" in tables:
            for idx, row in enumerate(conn.execute("SELECT id, session_id, time_created, data FROM message ORDER BY COALESCE(time_created, ''), id LIMIT ?", (max_records,)), start=1):
                msg_id, session_id, time_created, data_raw = row
                data = _loads_json(data_raw)
                records.append(_record(path, f"{session_id}:{msg_id or idx}", time_created, _json_get(data, "role"), "", _text_from_json(data), repo_root, preview_chars))
        else:
            return TrajectoryResult("sqlite", str(path), [], True, "sqlite source has no supported message/part tables")
    finally:
        conn.close()
    return TrajectoryResult("sqlite", str(path), records)


def _loads_json(raw: Any) -> Any:
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return {"text": str(raw)}


def read_markdown(path: Path, repo_root: Path | None, max_records: int, max_bytes: int, preview_chars: int) -> TrajectoryResult:
    text = path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
    chunks = _markdown_chunks(text)
    records = [
        _record(path, idx, "", "transcript", "", chunk, repo_root, preview_chars)
        for idx, chunk in enumerate(chunks[:max_records], start=1)
    ]
    return TrajectoryResult("markdown", str(path), records)


def _markdown_chunks(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s{0,3}#{1,6}\s+", line) and current:
            parts.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join(current).strip())
    return [p for p in parts if p]


def _claude_project_key(path: Path) -> str:
    return "-" + "-".join(part for part in path.resolve().parts if part != "/")


def _latest_first(paths: Iterable[Path]) -> list[Path]:
    existing = [path for path in paths if path.exists()]

    def key(path: Path) -> tuple[int, str]:
        try:
            return (-path.stat().st_mtime_ns, str(path))
        except OSError:
            return (0, str(path))

    return sorted(existing, key=key)


def discover_source(memory_dir: Path | None, repo_root: Path | None) -> Path | None:
    candidates: list[Path] = []
    if memory_dir:
        candidates.extend([
            memory_dir / "mimocode.db",
            memory_dir / "trajectory.db",
            memory_dir / "transcript.jsonl",
            memory_dir / "trajectory.jsonl",
            memory_dir / "transcript.md",
            memory_dir / "trajectory.md",
        ])
        candidates.extend(_latest_first(memory_dir.glob("*.jsonl")))
    if repo_root:
        project_dir = Path.home() / ".claude" / "projects" / _claude_project_key(repo_root)
        candidates.extend([
            project_dir / "mimocode.db",
            project_dir / "trajectory.jsonl",
            project_dir / "transcript.jsonl",
        ])
        candidates.extend(_latest_first(project_dir.glob("*.jsonl")))
    return next((p for p in candidates if p.exists()), None)


def load_trajectory(
    trajectory: str | os.PathLike[str] | None = None,
    memory_dir: str | os.PathLike[str] | None = None,
    repo_root: str | os.PathLike[str] | None = None,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
) -> TrajectoryResult:
    memory_path = Path(memory_dir).expanduser().resolve() if memory_dir else None
    repo_path = Path(repo_root).expanduser().resolve() if repo_root else None
    source = Path(trajectory).expanduser().resolve() if trajectory else discover_source(memory_path, repo_path)
    if not source:
        return TrajectoryResult("none", "", [], True, "no supported trajectory source found")
    if not source.exists():
        return TrajectoryResult("none", str(source), [], True, "trajectory source is missing")
    if source.is_dir():
        found = discover_source(source, repo_path)
        if not found:
            return TrajectoryResult("none", str(source), [], True, "trajectory directory has no supported source")
        source = found
    suffix = source.suffix.lower()
    try:
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            return read_sqlite(source, repo_path, max_records, max_bytes, preview_chars)
        if suffix == ".jsonl":
            return read_jsonl(source, repo_path, max_records, max_bytes, preview_chars)
        if suffix in {".md", ".markdown", ".txt"}:
            return read_markdown(source, repo_path, max_records, max_bytes, preview_chars)
    except sqlite3.Error as exc:
        return TrajectoryResult("sqlite", str(source), [], True, f"sqlite read failed: {exc}")
    except OSError as exc:
        return TrajectoryResult("none", str(source), [], True, f"trajectory read failed: {exc}")
    return TrajectoryResult("none", str(source), [], True, f"unsupported trajectory source type: {suffix or 'unknown'}")


def iter_prompt_lines(result: TrajectoryResult) -> Iterable[str]:
    yield f"adapter: {result.adapter}"
    yield f"source_path: {result.source_path or '(none)'}"
    if result.no_trajectory:
        yield f"status: no trajectory ({result.reason})"
        return
    for record in result.records:
        yield (
            f"- {record.evidence_id} | time={record.timestamp or 'unknown'} | "
            f"role={record.role or '-'} | tool={record.tool or '-'} | "
            f"project_match={str(record.project_match).lower()} | {record.preview}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview normalized dream trajectory evidence.")
    parser.add_argument("--trajectory")
    parser.add_argument("--memory-dir")
    parser.add_argument("--repo-root")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument("--preview-chars", type=int, default=DEFAULT_PREVIEW_CHARS)
    args = parser.parse_args(argv)
    result = load_trajectory(args.trajectory, args.memory_dir, args.repo_root, args.max_records, args.max_bytes, args.preview_chars)
    print("\n".join(iter_prompt_lines(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
