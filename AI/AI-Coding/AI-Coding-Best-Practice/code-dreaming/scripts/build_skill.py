#!/usr/bin/env python3
"""Build a clean code-dreaming skill bundle."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

INCLUDE_PATHS = [
    "SKILL.md",
    "agents",
    "assets",
    "bin",
    "mce",
    "prompts",
    "scripts",
    "upstream/maas-code",
    "pyproject.toml",
    "pytest.ini",
]

EXCLUDE_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "dist",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def ignore_runtime_noise(_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in EXCLUDE_NAMES:
            ignored.add(name)
            continue
        if any(name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
            ignored.add(name)
    return ignored


def copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore_runtime_noise)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(output: Path) -> None:
    output = output.expanduser().resolve()
    if output == ROOT:
        raise ValueError("refusing to build over the repository root")
    if ROOT in output.parents and output.relative_to(ROOT).parts[0] != "dist":
        raise ValueError("in-repo skill bundles must be written under dist/")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for rel in INCLUDE_PATHS:
        src = ROOT / rel
        if not src.exists():
            raise FileNotFoundError(f"required skill resource is missing: {rel}")
        copy_path(src, output / rel)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a clean code-dreaming skill bundle.")
    parser.add_argument("--output", default=str(ROOT / "dist" / "code-dreaming"), help="Bundle output directory.")
    args = parser.parse_args(argv)

    try:
        build(Path(args.output))
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 1
    print(Path(args.output).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
