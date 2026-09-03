#!/usr/bin/env python3
"""Self-contained verifier for a built Claude-MaaS Skill release package.

Validates manifest/schema, exact file set, sizes, executable modes, SHA-256
hashes, expected entry points, and forbidden content/path patterns. Outputs
one JSON result and never echoes suspected secret values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


MANIFEST_SCHEMA_VERSION = 1

REQUIRED_ENTRY_POINTS = [
    "SKILL.md",
    "README.md",
    "VERSION",
    "MANIFEST.json",
    "SHA256SUMS",
    "scripts/install.sh",
    "scripts/uninstall.sh",
    "scripts/maas-delegate",
    "scripts/delegate",
    "scripts/configure-agents.py",
    "client/claude-maas",
    "client/claude-maas-setup.sh",
    "references/routing-policy.md",
    "references/brief-contract.md",
    "references/result-contract.md",
]

# Forbidden path patterns (relative paths that must not appear in the package).
FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"^\.git(/|$)"),
    re.compile(r"\.git$"),
    re.compile(r"__pycache__"),
    re.compile(r"\.pyc$"),
    re.compile(r"\.DS_Store$"),
    re.compile(r"\.env$"),
    re.compile(r"\.key$"),
    re.compile(r"\.sqlite$"),
    re.compile(r"\.sqlite3$"),
    re.compile(r"audit.*\.jsonl$"),
    re.compile(r"route-audit"),
    re.compile(r"state\.sqlite"),
    re.compile(r"\.bak"),
    re.compile(r"\.tmp$"),
    re.compile(r"\.swp$"),
]

# Forbidden content patterns (regexes applied to file content as text).
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # Anthropic-style key
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)anthropic[_-]?auth[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)maas[_-]?api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}"),
]

# Absolute home path pattern (e.g., /Users/someone or /home/someone).
ABSOLUTE_HOME_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_forbidden_paths(paths: list[str]) -> list[str]:
    issues = []
    for p in paths:
        for pat in FORBIDDEN_PATH_PATTERNS:
            if pat.search(p):
                issues.append(f"forbidden path pattern: {p}")
                break
    return issues


def _check_forbidden_content(root: Path, paths: list[str]) -> list[str]:
    issues = []
    for rel in paths:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                issues.append(f"suspected secret in {rel} (pattern not echoed)")
        if ABSOLUTE_HOME_RE.search(text):
            # Allow references to /Users/ or /home/ in documentation examples
            # only if they are clearly marked as examples. We flag any absolute
            # home path that looks like a real user directory.
            for match in ABSOLUTE_HOME_RE.finditer(text):
                fragment = match.group()
                # Skip common documentation placeholders.
                if "/Users/username/" in fragment or "/home/username/" in fragment:
                    continue
                issues.append(f"absolute home path in {rel}: {fragment}")
                break
    return issues


def verify(package: Path) -> dict:
    """Verify a Skill release package. Returns a result dict."""
    issues: list[str] = []

    if not package.is_dir():
        return {"status": "error", "summary": f"not a directory: {package}"}

    # Load manifest.
    manifest_path = package / "MANIFEST.json"
    if not manifest_path.is_file():
        return {"status": "error", "summary": "MANIFEST.json is missing"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "error", "summary": f"invalid MANIFEST.json: {exc}"}

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        issues.append(f"unexpected manifest schema_version: {manifest.get('schema_version')}")

    if manifest.get("product") != "claude-maas-delegate":
        issues.append(f"unexpected manifest product: {manifest.get('product')}")

    manifest_files = manifest.get("files", [])
    if not isinstance(manifest_files, list):
        return {"status": "error", "summary": "manifest files is not a list"}

    # Build expected file set from manifest.
    expected = {}
    for rec in manifest_files:
        rel = rec.get("path")
        if not rel:
            issues.append("manifest record missing path")
            continue
        expected[rel] = rec

    # Collect actual files.
    actual = set()
    for path in package.rglob("*"):
        if path.is_file():
            rel = path.relative_to(package).as_posix()
            actual.add(rel)

    # Check for missing files (in manifest but not on disk).
    for rel in sorted(set(expected) - actual):
        issues.append(f"missing file: {rel}")

    # Check for extra files (on disk but not in manifest).
    # MANIFEST.json and SHA256SUMS are metadata files that may not be listed
    # in the manifest's file records (they describe the manifest itself).
    METADATA_FILES = {"MANIFEST.json", "SHA256SUMS"}
    for rel in sorted(actual - set(expected) - METADATA_FILES):
        issues.append(f"extra file: {rel}")

    # Verify each manifest record against the actual file.
    for rel, rec in sorted(expected.items()):
        path = package / rel
        if not path.is_file():
            continue  # already reported as missing

        data = path.read_bytes()

        # Size.
        if rec.get("size") != len(data):
            issues.append(f"size mismatch: {rel}")

        # SHA-256.
        actual_hash = _sha256(data)
        if rec.get("sha256") != actual_hash:
            issues.append(f"hash mismatch: {rel}")

        # Executable bit.
        is_exec = bool(os.access(path, os.X_OK))
        if rec.get("executable") != is_exec:
            issues.append(f"executable mismatch: {rel} (manifest={rec.get('executable')}, actual={is_exec})")

    # Verify SHA256SUMS.
    shasums_path = package / "SHA256SUMS"
    if shasums_path.is_file():
        lines = shasums_path.read_text(encoding="utf-8").splitlines()
        sums = {}
        for line in lines:
            parts = line.split("  ", 1)
            if len(parts) == 2:
                sums[parts[1]] = parts[0]
        # Check sorted order.
        if lines != sorted(lines, key=lambda l: l.split("  ", 1)[1] if "  " in l else l):
            issues.append("SHA256SUMS is not sorted by path")
        # Check each hash matches.
        for rel, rec in expected.items():
            if rel not in sums:
                issues.append(f"SHA256SUMS entry missing: {rel}")
            elif sums[rel] != rec.get("sha256"):
                issues.append(f"SHA256SUMS hash mismatch: {rel}")
    else:
        issues.append("SHA256SUMS is missing")

    # Check required entry points.
    for ep in REQUIRED_ENTRY_POINTS:
        if not (package / ep).is_file():
            issues.append(f"required entry point missing: {ep}")

    # Check forbidden paths.
    issues.extend(_check_forbidden_paths(sorted(actual)))

    # Check forbidden content (secrets, absolute paths).
    issues.extend(_check_forbidden_content(package, sorted(actual)))

    # Check VERSION exists and is non-empty.
    version_path = package / "VERSION"
    if version_path.is_file():
        if not version_path.read_text(encoding="utf-8").strip():
            issues.append("VERSION is empty")
    else:
        issues.append("VERSION is missing")

    # Check no top-level loose markdown files other than SKILL.md and README.md.
    for path in package.iterdir():
        if path.is_file() and path.suffix == ".md" and path.name not in {"SKILL.md", "README.md"}:
            issues.append(f"unexpected top-level markdown: {path.name}")

    if issues:
        return {"status": "failure", "issues": issues}
    return {"status": "success", "files": len(actual)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="path to the Skill release package")
    args = parser.parse_args(argv)

    result = verify(args.package)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
