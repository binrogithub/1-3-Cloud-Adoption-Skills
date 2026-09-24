#!/usr/bin/env python3
"""Create and restore an instance backup without copying SQLite WAL files.

This is project glue for upgrade recovery. It snapshots customer configuration,
managed units, the install manifest, and the task ledger. External executions
are recorded data and are never re-submitted by restore.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from autoops_runtime_config import resolve_runtime


SCHEMA_VERSION = 1
SYSTEMD_PREFIX = "jiuwenswarm-autoops-"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"backup path must be a regular file: {path}")


def files_under(root: Path, *, predicate=None) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"backup root must be a directory: {root}")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"backup tree contains a symlink: {path}")
        if path.is_file() and (predicate is None or predicate(path)):
            files.append(path)
    return files


def sqlite_backup(source: Path, destination: Path) -> bool:
    """Use SQLite's consistent backup API; never copy -wal or -shm files."""
    if not source.exists():
        return False
    regular(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source, timeout=10)
    destination_connection = sqlite3.connect(destination, timeout=10)
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()
    return True


def task_store_backup(source: Path, destination: Path) -> bool:
    """Named adapter for TaskStore callers and upgrade tooling."""
    return sqlite_backup(source, destination)


def _record(path: Path, backup_root: Path, target: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "backup_path": str(path.relative_to(backup_root)),
        "target_path": str(target),
        "sha256": sha256_file(path),
        "mode": format(stat.st_mode & 0o7777, "04o"),
        "ownership": {"uid": stat.st_uid, "gid": stat.st_gid},
    }


def _manifest_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    return hashlib.sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def create_backup(*, output: Path, install_root: Path, config_root: Path,
                  state_root: Path, systemd_root: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"backup output already exists: {output}")
    if output.is_symlink():
        raise ValueError(f"refusing symlink backup output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        config_target = temporary / "config"
        systemd_target = temporary / "systemd"
        install_target = temporary / "install"
        config_target.mkdir()
        systemd_target.mkdir()
        install_target.mkdir()
        records: list[dict[str, Any]] = []
        for source in files_under(config_root):
            destination = config_target / source.relative_to(config_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            records.append(_record(destination, temporary, config_root / source.relative_to(config_root)))
        for source in files_under(systemd_root, predicate=lambda p: p.name.startswith(SYSTEMD_PREFIX)):
            destination = systemd_target / source.name
            shutil.copy2(source, destination)
            records.append(_record(destination, temporary, systemd_root / source.name))
        manifest_source = install_root / "autoops-install-manifest.json"
        if manifest_source.exists():
            regular(manifest_source)
            destination = install_target / manifest_source.name
            shutil.copy2(manifest_source, destination)
            records.append(_record(destination, temporary, manifest_source))
        state_destination = temporary / "state" / "autoops-state.db"
        state_present = sqlite_backup(state_root / "autoops-state.db", state_destination)
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "created_at": int(time.time()),
            "roots": {"install": str(install_root), "config": str(config_root),
                      "state": str(state_root), "systemd": str(systemd_root)},
            "state_db": {"present": state_present, "backup_path": "state/autoops-state.db"},
            "files": sorted(records, key=lambda item: (item["target_path"], item["backup_path"])),
            "restore_policy": {
                "requires_stopped_writers": True,
                "external_actions_replayed": False,
                "ownership_restored": False,
            },
        }
        payload["manifest_sha256"] = _manifest_digest(payload)
        (temporary / "backup-manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, output)
        return {"status": "READY", "backup": str(output), "manifest_sha256": payload["manifest_sha256"],
                "file_count": len(records), "state_db_present": state_present}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def load_backup(backup: Path) -> dict[str, Any]:
    manifest = backup / "backup-manifest.json"
    regular(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported or invalid backup manifest: {manifest}")
    if payload.get("manifest_sha256") != _manifest_digest(payload):
        raise ValueError(f"backup manifest hash mismatch: {manifest}")
    if not isinstance(payload.get("files"), list) or not isinstance(payload.get("state_db"), dict):
        raise ValueError(f"backup manifest is incomplete: {manifest}")
    return payload


def restore_backup(*, backup: Path, assume_stopped: bool, dry_run: bool) -> dict[str, Any]:
    payload = load_backup(backup.resolve())
    if not assume_stopped and not dry_run:
        raise ValueError("restore requires --assume-stopped after stopping AutoOps writers")
    checked = 0
    if dry_run:
        return {"status": "DRY_RUN", "manifest_sha256": payload["manifest_sha256"],
                "file_count": len(payload["files"]), "state_db_present": payload["state_db"].get("present", False)}
    for item in payload["files"]:
        if not isinstance(item, dict):
            raise ValueError("backup file record is invalid")
        source = backup / str(item["backup_path"])
        target = Path(str(item["target_path"]))
        regular(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.autoops-restore.tmp")
        shutil.copy2(source, temporary)
        if sha256_file(temporary) != item["sha256"]:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"backup file hash mismatch: {source}")
        os.chmod(temporary, int(str(item["mode"]), 8))
        os.replace(temporary, target)
        checked += 1
    if payload["state_db"].get("present"):
        source = backup / str(payload["state_db"]["backup_path"])
        destination = Path(str(payload["roots"]["state"])) / "autoops-state.db"
        sqlite_backup(source, destination)
    return {"status": "RESTORED", "manifest_sha256": payload["manifest_sha256"],
            "file_count": checked, "state_db_restored": bool(payload["state_db"].get("present")),
            "external_actions_replayed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup or restore one AutoOps instance.")
    parser.add_argument("command", choices=("create", "restore"))
    parser.add_argument("--output", type=Path, help="new backup directory for create")
    parser.add_argument("--backup", type=Path, help="existing backup directory for restore")
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--config-root", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--systemd-root", type=Path)
    parser.add_argument("--assume-stopped", action="store_true",
                        help="confirm AutoOps writers are stopped before restore")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        runtime = resolve_runtime(install_root=args.install_root, config_root=args.config_root,
                                  state_root=args.state_root,
                                  state_db=(args.state_root / "autoops-state.db") if args.state_root else None)
        install_root = Path(runtime["install_root"])
        config_root = Path(runtime["config_root"])
        state_root = Path(runtime["state_root"])
        systemd_root = args.systemd_root or Path(os.environ.get("AUTOOPS_SYSTEMD_ROOT", "/etc/systemd/system"))
        if args.command == "create":
            if not args.output:
                raise ValueError("create requires --output")
            result = create_backup(output=args.output, install_root=install_root,
                                   config_root=config_root, state_root=state_root,
                                   systemd_root=systemd_root)
        else:
            if not args.backup:
                raise ValueError("restore requires --backup")
            result = restore_backup(backup=args.backup, assume_stopped=args.assume_stopped,
                                    dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
