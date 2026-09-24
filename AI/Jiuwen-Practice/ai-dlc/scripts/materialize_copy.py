#!/usr/bin/env python3.12
"""Deterministic material copy for the design-materialize dispatch.

Invoked BY the jiuwenswarm session (the session is the actor that
touches OpenDesign — the coding agent never calls OpenDesign
directly). The plane verifies the frames, cross-checks this script's
JSON report against the standing files, and signs the manifest.

Copies assets/, references/, example.html and styles.css into dest,
honoring the caps; prints a JSON report of what landed.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template-dir", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--max-files", type=int, default=40)
    ap.add_argument("--max-bytes", type=int, default=24 * 1024 * 1024)
    a = ap.parse_args()
    tdir, dest = a.template_dir, a.dest
    dest.mkdir(parents=True, exist_ok=True)
    picked: list = []
    for rel in ("assets", "references"):
        d = tdir / rel
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file() and f.name != ".od-intent.json":
                    picked.append(f)
    for name in ("example.html", "styles.css"):
        f = tdir / name
        if f.is_file():
            picked.append(f)
    files = []
    total = 0
    for f in picked:
        if len(files) >= a.max_files:
            break
        size = f.stat().st_size
        if total + size > a.max_bytes:
            continue
        target = dest / f.relative_to(tdir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        files.append({"path": f.relative_to(tdir).as_posix(),
                      "bytes": size})
        total += size
    print(json.dumps({"copied": files, "total_bytes": total}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
