"""Project-scope helpers for native Claude memory directories."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NativeMemoryResolution:
    memory_dir: Path
    exact: bool
    owner_root: Path


@dataclass(frozen=True)
class ProjectScope:
    repo_root: Path
    phrases: tuple[str, ...]


def claude_project_key(path: Path) -> str:
    return "-" + "-".join(part for part in path.resolve().parts if part != "/")


def native_memory_dir_for(path: Path) -> Path:
    return Path.home() / ".claude" / "projects" / claude_project_key(path) / "memory"


def resolve_native_memory(start: Path | None = None) -> NativeMemoryResolution:
    start = (start or Path.cwd()).resolve()
    exact_memory = native_memory_dir_for(start)
    for candidate in (start, *start.parents):
        memory_dir = native_memory_dir_for(candidate)
        if memory_dir.exists():
            return NativeMemoryResolution(memory_dir, memory_dir == exact_memory, candidate)
    return NativeMemoryResolution(exact_memory, True, start)


def native_memory_relation(memory_dir: Path, repo_root: Path) -> NativeMemoryResolution | None:
    """Return native-memory ownership if memory_dir maps to repo_root or a parent."""
    memory_dir = memory_dir.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    exact_memory = native_memory_dir_for(repo_root).resolve()
    for candidate in (repo_root, *repo_root.parents):
        candidate_memory = native_memory_dir_for(candidate).resolve()
        if memory_dir == candidate_memory:
            return NativeMemoryResolution(candidate_memory, candidate_memory == exact_memory, candidate)
    return None


def _first_heading(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return ""


def _frontmatter_name(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "name":
            return value.strip().strip("\"'")
    return ""


def _pyproject_name(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(?m)^\s*name\s*=\s*[\"']([^\"']+)[\"']", text)
    return m.group(1).strip() if m else ""


def _variants(value: str) -> set[str]:
    value = value.strip().lower()
    if not value:
        return set()
    variants = {value}
    if "-" in value:
        variants.add(value.replace("-", " "))
    if "_" in value:
        variants.add(value.replace("_", " "))
    return {v for v in variants if len(v) >= 4}


def project_scope(repo_root: Path) -> ProjectScope:
    repo_root = repo_root.expanduser().resolve()
    phrases: set[str] = set()
    for value in (
        repo_root.name,
        _pyproject_name(repo_root / "pyproject.toml"),
        _frontmatter_name(repo_root / "SKILL.md"),
        _first_heading(repo_root / "README.md"),
    ):
        phrases.update(_variants(value))
    return ProjectScope(repo_root, tuple(sorted(phrases, key=lambda s: (-len(s), s))))


def should_apply_scope_filter(mode: str, *, inherited_parent_memory: bool) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    if mode != "auto":
        raise ValueError("scope filter mode must be auto, on, or off")
    return inherited_parent_memory


def memory_matches_project(text: str, scope: ProjectScope) -> bool:
    normalized = text.lower()
    if str(scope.repo_root).lower() in normalized:
        return True
    return any(phrase in normalized for phrase in scope.phrases)
