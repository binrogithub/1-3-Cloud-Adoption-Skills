#!/usr/bin/env python3
"""Copy the starter Enterprise RAG Agent Pack to a target folder."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def scaffold(target: Path, overwrite: bool = False) -> None:
    source = skill_root() / "assets" / "enterprise-rag-agent-pack"
    if not source.exists():
        raise FileNotFoundError(f"Missing template pack: {source}")
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise FileExistsError(f"Target is not empty: {target}. Use --overwrite to replace files.")
    if target.exists() and overwrite:
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Directory to create the pack in")
    parser.add_argument("--overwrite", action="store_true", help="Replace target if it exists")
    args = parser.parse_args()
    scaffold(args.target, args.overwrite)
    print(f"Created Enterprise RAG Agent Pack at {args.target}")


if __name__ == "__main__":
    main()
