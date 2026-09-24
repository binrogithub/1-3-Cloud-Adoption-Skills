#!/usr/bin/env python3
"""Build a deterministic AutoOps glue artifact from a committed checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSET_MANIFEST = ROOT / "config" / "release" / "runtime-assets.json"
EXCLUDED_PARTS = {".git", ".runtime", "__pycache__", ".pytest_cache"}
EXCLUDED_PREFIXES = ("config/local", "docs/evidence", "tests/__pycache__")


def source_commit(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError("source is not a git checkout")
    return result.stdout.strip()


def is_dirty(root: Path) -> bool:
    result = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                            text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError("unable to inspect source worktree")
    return bool(result.stdout.strip())


def package_paths(root: Path) -> list[Path]:
    required = [
        root / "scripts", root / "skills", root / "runbooks", root / "swarmflow",
        root / "config", root / "components.env", root / "README.md",
    ]
    for path in required:
        if not path.exists() or path.is_symlink():
            raise ValueError(f"required release asset is missing or unsafe: {path}")
    paths: list[Path] = []
    for path in required:
        if path.is_file():
            paths.append(path)
            continue
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(root).as_posix()
            if any(part in EXCLUDED_PARTS for part in child.relative_to(root).parts):
                continue
            if any(relative == prefix or relative.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES):
                continue
            if child.is_symlink():
                raise ValueError(f"release tree contains symlink: {child}")
            if child.is_file():
                paths.append(child)
    return sorted(set(paths))


def build(root: Path, output: Path, *, commit: str | None = None,
          allow_dirty: bool = False) -> dict[str, Any]:
    if not allow_dirty and is_dirty(root):
        raise ValueError("refusing release build from a dirty worktree; use --allow-dirty for an unverified candidate")
    actual_commit = source_commit(root)
    if commit and commit != actual_commit:
        raise ValueError(f"requested commit {commit} is not checked out; actual HEAD is {actual_commit}")
    assets = package_paths(root)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{output.name}.", dir=output.parent, delete=False) as temporary:
        temporary_name = Path(temporary.name)
    try:
        with tarfile.open(temporary_name, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for path in assets:
                relative = path.relative_to(root).as_posix()
                info = archive.gettarinfo(str(path), arcname=f"Jiuwenswarm_AutoOps/{relative}")
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                info.mtime = 0
                if path.is_file():
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)
        os.replace(temporary_name, output)
    finally:
        if temporary_name.exists():
            temporary_name.unlink()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    build_manifest = output.with_name(output.name + ".manifest.json")
    manifest = {
        "schema_version": 1,
        "status": "candidate-unverified" if allow_dirty else "built",
        "source_commit": actual_commit,
        "dirty_source_allowed": allow_dirty,
        "artifact": str(output),
        "artifact_sha256": digest,
        "asset_count": len(assets),
        "assets": [path.relative_to(root).as_posix() for path in assets],
    }
    build_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic AutoOps release artifact.")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Build candidate-unverified from a dirty worktree; never a release gate pass.")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.source_root.resolve(), args.output,
                               commit=args.commit, allow_dirty=args.allow_dirty),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "NO_GO", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
