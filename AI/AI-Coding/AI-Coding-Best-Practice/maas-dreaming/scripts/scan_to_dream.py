#!/usr/bin/env python3
"""Scan a directory into a Markdown dream source file.

This is glue for the LLM dream leg, not a replacement for MiMo dream. It turns a
plain directory tree into a bounded, redacted, Markdown trajectory-like file that
`bin/dream-llm.sh --trajectory` can read through the existing Markdown adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from scripts.dream_sources import redact
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from dream_sources import redact


DEFAULT_MAX_FILES = 200
DEFAULT_MAX_FILE_BYTES = 16_384
DEFAULT_MAX_TOTAL_BYTES = 200_000
IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", "__pycache__",
    "node_modules", "vendor", "build", "dist", ".venv", "venv",
}
TEXT_SUFFIXES = {
    ".cfg", ".css", ".csv", ".env", ".go", ".html", ".ini", ".java",
    ".js", ".json", ".jsonl", ".jsx", ".kt", ".md", ".py", ".rb", ".rs",
    ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    rel: str
    size: int
    mtime: float
    sha1: str
    preview: str
    truncated: bool
    status: str = "full"


@dataclass(frozen=True)
class ScanResult:
    files: list[ScannedFile]
    skipped_dirs: list[str]
    limits_hit: list[str]
    manifest_entries: dict[str, dict[str, Any]]
    mode: str = "full"
    added: int = 0
    changed: int = 0
    deleted: list[str] | None = None
    unchanged: int = 0


def fingerprint(size: int, mtime: float, sha1: str) -> str:
    # Mirrors MiMo reconcile.ts's size-mtime fingerprint, with sha1 appended for
    # directory-scan robustness when callers preserve mtimes across copies.
    return f"{size}-{mtime:.6f}-{sha1}"


def load_manifest(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def manifest_files(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = manifest.get("files")
    return files if isinstance(files, dict) else {}


def build_manifest(root: Path, result: ScanResult) -> dict[str, Any]:
    return {
        "kind": "dream-scan-manifest",
        "version": 1,
        "root": str(root.resolve()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": result.manifest_entries,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def looks_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    if not chunk:
        return True
    printable = sum(1 for b in chunk if b in b"\n\r\t" or 32 <= b <= 126)
    return printable / len(chunk) > 0.85


def iter_files(root: Path, include_hidden: bool = False):
    for dirpath, dirnames, filenames in os.walk(root):
        before = list(dirnames)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORED_DIRS and (include_hidden or not d.startswith("."))
        )
        for skipped in sorted(set(before) - set(dirnames)):
            yield Path(dirpath) / skipped
        for name in sorted(filenames):
            if not include_hidden and name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.is_file():
                yield path


def scan_directory(root: Path, max_files: int = DEFAULT_MAX_FILES,
                   max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
                   max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
                   include_hidden: bool = False,
                   since_manifest: dict[str, Any] | None = None) -> ScanResult:
    root = root.resolve()
    scanned: list[ScannedFile] = []
    skipped_dirs: list[str] = []
    limits_hit: list[str] = []
    current_manifest: dict[str, dict[str, Any]] = {}
    previous = manifest_files(since_manifest or {})
    current_seen: set[str] = set()
    added = 0
    changed = 0
    unchanged = 0
    consumed = 0
    for path in iter_files(root, include_hidden=include_hidden):
        if path.is_dir():
            skipped_dirs.append(path.relative_to(root).as_posix())
            continue
        if len(scanned) >= max_files or consumed >= max_total_bytes:
            limits_hit.append("max_files" if len(scanned) >= max_files else "max_total_bytes")
            break
        if not looks_text(path):
            continue
        try:
            data = path.read_bytes()
            stat = path.stat()
        except OSError:
            continue
        take = min(len(data), max_file_bytes, max_total_bytes - consumed)
        if take <= 0:
            break
        rel = path.relative_to(root).as_posix()
        sha1 = hashlib.sha1(data).hexdigest()
        fp = fingerprint(stat.st_size, stat.st_mtime, sha1)
        current_manifest[rel] = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "sha1": sha1,
            "fingerprint": fp,
        }
        current_seen.add(rel)
        old = previous.get(rel)
        old_fp = old.get("fingerprint") if isinstance(old, dict) else None
        if previous:
            if old_fp == fp:
                unchanged += 1
                continue
            if old:
                changed += 1
                status = "changed"
            else:
                added += 1
                status = "added"
        else:
            status = "full"
        consumed += take
        preview = data[:take].decode("utf-8", errors="replace")
        scanned.append(
            ScannedFile(
                path=path,
                rel=rel,
                size=stat.st_size,
                mtime=stat.st_mtime,
                sha1=sha1,
                preview=redact(preview),
                truncated=take < len(data),
                status=status,
            )
        )
    deleted = sorted(rel for rel in previous.keys() if rel not in current_seen)
    return ScanResult(
        scanned,
        skipped_dirs,
        limits_hit,
        current_manifest,
        mode="delta" if previous else "full",
        added=added,
        changed=changed,
        deleted=deleted,
        unchanged=unchanged,
    )


def render_dream_source(root: Path, result: ScanResult | list[ScannedFile]) -> str:
    if isinstance(result, list):  # Backward-compatible for tests/callers.
        files = result
        skipped_dirs: list[str] = []
        limits_hit: list[str] = []
    else:
        files = result.files
        skipped_dirs = result.skipped_dirs
        limits_hit = result.limits_hit
    deleted = result.deleted or [] if isinstance(result, ScanResult) else []
    lines = [
        "# Directory Dream Source",
        "",
        "This file is a generated trajectory-like source for MiMo dream.",
        "Use it with `bin/dream-llm.sh --trajectory <this-file>`.",
        "",
        f"- root: `{root.resolve()}`",
        f"- mode: {result.mode if isinstance(result, ScanResult) else 'full'}",
        f"- files_scanned: {len(files)}",
        f"- added: {result.added if isinstance(result, ScanResult) else 0}",
        f"- changed: {result.changed if isinstance(result, ScanResult) else 0}",
        f"- deleted: {len(deleted)}",
        f"- unchanged: {result.unchanged if isinstance(result, ScanResult) else 0}",
        f"- skipped_dirs: {', '.join(skipped_dirs) if skipped_dirs else '(none)'}",
        f"- limits_hit: {', '.join(limits_hit) if limits_hit else '(none)'}",
        f"- generated_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
    ]
    if deleted:
        lines.extend(["## Deleted files", ""])
        lines.extend(f"- {rel}" for rel in deleted)
        lines.append("")
    for item in files:
        lines.extend([
            f"## File: {item.rel}",
            "",
            f"- path: `{item.rel}`",
            f"- status: {item.status}",
            f"- size_bytes: {item.size}",
            f"- mtime: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(item.mtime))}",
            f"- sha1: `{item.sha1}`",
            f"- truncated: {str(item.truncated).lower()}",
            "",
            "```text",
            item.preview.rstrip(),
            "```",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scan a directory into a Markdown dream source file.")
    p.add_argument("directory", help="Directory to scan.")
    p.add_argument("--output", "-o", required=True, help="Markdown dream source file to write.")
    p.add_argument("--include-hidden", action="store_true", help="Include hidden files and directories.")
    p.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    p.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    p.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    p.add_argument("--since-manifest", help="Existing manifest; output only added/changed/deleted files.")
    p.add_argument("--write-manifest", help="Write the current scan manifest for the next run.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.directory).expanduser()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    output = Path(args.output).expanduser()
    previous = load_manifest(Path(args.since_manifest).expanduser()) if args.since_manifest else {}
    result = scan_directory(
        root,
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        include_hidden=args.include_hidden,
        since_manifest=previous,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dream_source(root, result), encoding="utf-8")
    if args.write_manifest:
        write_manifest(Path(args.write_manifest).expanduser(), build_manifest(root, result))
    print(f"wrote {output} ({len(result.files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
