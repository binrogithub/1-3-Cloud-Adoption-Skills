#!/usr/bin/env python3
"""Reset local Claude Code / Mem0-compatible memory for one project.

Dry-run by default. Apply mode backs up selected memory artifacts before
removing them. Native Claude parent workspace memory is refused unless the user
explicitly passes --allow-parent.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.project_scope import native_memory_dir_for, native_memory_relation, resolve_native_memory
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from project_scope import native_memory_dir_for, native_memory_relation, resolve_native_memory


RESET_DIR_NAMES = ("episodic", "semantic", "inbox", "working")
RESET_FILE_PATTERNS = ("*.md", "*.jsonl", "*.db", "*.sqlite", "*.sqlite3")


@dataclass(frozen=True)
class MemoryTarget:
    path: Path
    rel: Path


@dataclass(frozen=True)
class ResetPlan:
    repo_root: Path
    memory_dir: Path
    relation: str
    owner_root: Path | None
    targets: tuple[MemoryTarget, ...]
    backup_dir: Path
    exact_memory_dir: Path
    init_exact: bool


class ResetRefusal(RuntimeError):
    pass


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _classify_memory(memory_dir: Path, repo_root: Path, *, explicit: bool) -> tuple[str, Path | None]:
    relation = native_memory_relation(memory_dir, repo_root)
    if relation:
        return ("exact-native" if relation.exact else "parent-native"), relation.owner_root
    return ("explicit" if explicit else "native"), None


def resolve_memory_dir(repo_root: Path, memory_dir: Path | None) -> tuple[Path, str, Path | None]:
    repo_root = repo_root.expanduser().resolve()
    if memory_dir is None:
        resolved = resolve_native_memory(repo_root)
        relation = "exact-native" if resolved.exact else "parent-native"
        return resolved.memory_dir.resolve(), relation, resolved.owner_root

    memory_dir = memory_dir.expanduser().resolve()
    relation, owner_root = _classify_memory(memory_dir, repo_root, explicit=True)
    return memory_dir, relation, owner_root


def enumerate_targets(memory_dir: Path) -> tuple[MemoryTarget, ...]:
    seen: set[Path] = set()
    targets: list[MemoryTarget] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            return
        seen.add(resolved)
        targets.append(MemoryTarget(path=path, rel=path.relative_to(memory_dir)))

    for name in RESET_DIR_NAMES:
        add(memory_dir / name)
    for pattern in RESET_FILE_PATTERNS:
        for path in sorted(memory_dir.glob(pattern)):
            if path.name == ".reset-backups" or path.name == "memory-reset-backups":
                continue
            add(path)

    return tuple(sorted(targets, key=lambda target: str(target.rel)))


def build_plan(
    *,
    repo_root: Path,
    memory_dir: Path | None,
    backup_dir: Path | None,
    allow_parent: bool,
    init_exact: bool,
) -> ResetPlan:
    repo_root = repo_root.expanduser().resolve()
    memory_root, relation, owner_root = resolve_memory_dir(repo_root, memory_dir)
    exact_memory_dir = native_memory_dir_for(repo_root).resolve()

    if relation == "parent-native" and not allow_parent:
        owner = f" owned by {owner_root}" if owner_root else ""
        raise ResetRefusal(
            "refusing to clear inherited parent native memory"
            f"{owner}; pass --allow-parent only if you intend to clear that workspace memory"
        )
    if not memory_root.exists():
        if relation != "exact-native" or memory_dir is not None:
            raise ResetRefusal(f"memory directory does not exist: {memory_root}")
        targets: tuple[MemoryTarget, ...] = ()
    elif not memory_root.is_dir():
        raise ResetRefusal(f"memory path is not a directory: {memory_root}")
    else:
        targets = enumerate_targets(memory_root)

    backup_root = (
        backup_dir.expanduser().resolve()
        if backup_dir
        else memory_root.parent / "memory-reset-backups" / _timestamp()
    )
    if backup_root == memory_root or _is_relative_to(backup_root, memory_root):
        raise ResetRefusal("backup directory must be outside the active memory directory")

    return ResetPlan(
        repo_root=repo_root,
        memory_dir=memory_root,
        relation=relation,
        owner_root=owner_root,
        targets=targets,
        backup_dir=backup_root,
        exact_memory_dir=exact_memory_dir,
        init_exact=init_exact and relation in {"exact-native", "parent-native"},
    )


def backup_targets(plan: ResetPlan) -> None:
    plan.backup_dir.mkdir(parents=True, exist_ok=False)
    for target in plan.targets:
        dst = plan.backup_dir / target.rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if target.path.is_symlink():
            shutil.copy2(target.path, dst, follow_symlinks=False)
        elif target.path.is_dir():
            shutil.copytree(target.path, dst, symlinks=True)
        else:
            shutil.copy2(target.path, dst)


def remove_targets(targets: tuple[MemoryTarget, ...]) -> None:
    for target in targets:
        if target.path.is_symlink() or target.path.is_file():
            target.path.unlink()
        elif target.path.is_dir():
            shutil.rmtree(target.path)


def render_plan(plan: ResetPlan, *, apply: bool) -> str:
    title = "# reset-memory — APPLY" if apply else "# reset-memory — DRY RUN (use --apply to write)"
    owner = str(plan.owner_root) if plan.owner_root else "-"
    lines = [
        title,
        f"repo root        : {plan.repo_root}",
        f"memory root      : {plan.memory_dir}",
        f"memory relation  : {plan.relation}",
        f"owner root       : {owner}",
        f"backup dir       : {plan.backup_dir}",
        f"exact memory root: {plan.exact_memory_dir}",
        f"init exact root  : {'yes (on --apply)' if plan.init_exact else 'no'}",
        f"targets          : {len(plan.targets)}",
    ]
    for target in plan.targets:
        kind = "dir " if target.path.is_dir() and not target.path.is_symlink() else "file"
        lines.append(f"  - [{kind}] {target.rel}")
    if not plan.targets:
        lines.append("nothing to clear")
    elif not apply:
        lines.append("dry-run only; pass --apply to back up and remove these targets")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clear local project memory with backup and parent guards.")
    parser.add_argument("--repo-root", default=".", help="Current project root. Defaults to cwd.")
    parser.add_argument("--memory-dir", help="Memory directory to clear. Defaults to native Claude project memory.")
    parser.add_argument("--backup-dir", help="Backup destination. Defaults beside the memory directory.")
    parser.add_argument("--allow-parent", action="store_true", help="Allow clearing inherited parent Claude memory.")
    parser.add_argument("--init-exact", action=argparse.BooleanOptionalAction, default=True,
                        help="Create the exact current-project native memory directory after apply.")
    parser.add_argument("--apply", action="store_true", help="Actually back up and remove selected targets.")
    args = parser.parse_args(argv)

    try:
        plan = build_plan(
            repo_root=Path(args.repo_root),
            memory_dir=Path(args.memory_dir) if args.memory_dir else None,
            backup_dir=Path(args.backup_dir) if args.backup_dir else None,
            allow_parent=args.allow_parent,
            init_exact=args.init_exact,
        )
    except ResetRefusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(render_plan(plan, apply=args.apply))
    if not args.apply:
        return 0

    if plan.targets:
        backup_targets(plan)
        remove_targets(plan.targets)
        print(f"backed up and removed {len(plan.targets)} target(s)")
    else:
        print("no memory artifacts to remove")
    if plan.init_exact:
        plan.exact_memory_dir.mkdir(parents=True, exist_ok=True)
        print(f"initialized exact memory root: {plan.exact_memory_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
