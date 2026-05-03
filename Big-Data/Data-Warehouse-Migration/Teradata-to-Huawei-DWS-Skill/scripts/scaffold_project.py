#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import stat
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_DIR / "assets" / "project-template"


def copy_template(target: Path, overwrite: bool) -> None:
    if not TEMPLATE_DIR.exists():
        raise RuntimeError(f"Missing template directory: {TEMPLATE_DIR}")

    target.mkdir(parents=True, exist_ok=True)
    for source in TEMPLATE_DIR.rglob("*"):
        relative = source.relative_to(TEMPLATE_DIR)
        destination = target / relative
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if destination.exists() and not overwrite:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    for path in target.glob("scripts/*"):
        if path.is_file() and path.suffix in {".sh", ".py"}:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a Teradata-to-Huawei-DWS migration demo project.")
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    copy_template(args.target.resolve(), args.overwrite)
    print(f"Scaffolded Teradata-to-DWS project at {args.target.resolve()}")
    print("Next: ./scripts/start_source_cluster.sh && ./scripts/init_finance_demo.sh && ./scripts/run_reports.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

