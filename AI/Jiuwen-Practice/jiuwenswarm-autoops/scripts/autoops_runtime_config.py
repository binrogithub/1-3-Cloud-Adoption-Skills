#!/usr/bin/env python3
"""Resolve one AutoOps deployment instance for every project entry point.

The module is deliberately small and dependency free.  It keeps the project
glue from choosing a state directory from the caller's current working
directory, while still allowing explicit paths for isolated tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL_ROOT = Path("/opt/Jiuwenswarm_AutoOps")
DEFAULT_CONFIG_ROOT = Path("/etc/jiuwenswarm-autoops")
DEFAULT_STATE_ROOT = Path("/var/lib/jiuwenswarm-autoops")
RUNTIME_FILE = "runtime.json"


def _path(value: str | os.PathLike[str] | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(value).expanduser().resolve()


def _read_runtime(path: Path) -> dict[str, Any] | None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink AutoOps runtime configuration: {path}")
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read AutoOps runtime configuration: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid AutoOps runtime configuration: {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"AutoOps runtime configuration must be an object: {path}")
    if value.get("schema_version") not in {1, 2}:
        raise ValueError(f"unsupported AutoOps runtime configuration schema: {path}")
    return value


def _installed_runtime() -> dict[str, Any] | None:
    """Find a persisted instance without using cwd.

    A source checkout is only considered when explicit development mode is
    requested.  This prevents an installed command launched from ``/root``
    from silently creating a second checkout-local state database.
    """
    configured = _path(os.environ.get("JIUWENSWARM_AUTOOPS_RUNTIME_FILE"))
    if configured:
        value = _read_runtime(configured)
        if value is None:
            raise ValueError(f"invalid AutoOps runtime configuration: {configured}")
        return value
    for candidate in (
        DEFAULT_CONFIG_ROOT / RUNTIME_FILE,
        PROJECT_ROOT / RUNTIME_FILE,
        PROJECT_ROOT / "config" / RUNTIME_FILE,
    ):
        value = _read_runtime(candidate)
        if value is not None:
            return value
    if os.environ.get("AUTOOPS_DEV_MODE") == "1":
        return None
    # Existing source tests and explicit AUTOOPS_STATE_DB callers remain
    # isolated without opting the installed runtime into checkout state.
    if os.environ.get("AUTOOPS_STATE_DB") or os.environ.get("AUTOOPS_WATCH_STATE_DIR"):
        return None
    if PROJECT_ROOT != DEFAULT_INSTALL_ROOT and (PROJECT_ROOT / ".runtime").is_dir():
        return None
    return None


def resolve_runtime(*, install_root: Path | None = None,
                    config_root: Path | None = None,
                    state_root: Path | None = None,
                    state_db: Path | None = None,
                    watch_state_dir: Path | None = None,
                    events_file: Path | None = None,
                    outbox_file: Path | None = None,
                    require_persisted: bool = False) -> dict[str, Any]:
    """Return normalized paths and the stable instance identifier."""
    persisted = _installed_runtime()
    explicit_state = any(value is not None for value in
                         (install_root, config_root, state_root, state_db,
                          watch_state_dir, events_file, outbox_file))
    env_state_db = _path(os.environ.get("AUTOOPS_STATE_DB"))
    env_watch = _path(os.environ.get("AUTOOPS_WATCH_STATE_DIR"))
    env_events = _path(os.environ.get("AUTOOPS_EVENTS_FILE"))
    env_outbox = _path(os.environ.get("AUTOOPS_OUTBOX_FILE"))
    if require_persisted and persisted is None and not explicit_state and not env_state_db and not env_watch:
        raise ValueError("installed AutoOps runtime configuration is missing")
    base_install = _path(install_root) or _path(os.environ.get("AUTOOPS_INSTALL_ROOT"))
    base_config = _path(config_root) or _path(os.environ.get("AUTOOPS_CONFIG_ROOT"))
    base_state = _path(state_root) or _path(os.environ.get("AUTOOPS_STATE_ROOT"))
    if persisted:
        base_install = base_install or _path(persisted.get("install_root"))
        base_config = base_config or _path(persisted.get("config_root"))
        base_state = base_state or _path(persisted.get("state_root"))
    base_install = base_install or (PROJECT_ROOT if os.environ.get("AUTOOPS_DEV_MODE") == "1" else DEFAULT_INSTALL_ROOT)
    base_config = base_config or DEFAULT_CONFIG_ROOT
    base_state = base_state or DEFAULT_STATE_ROOT
    resolved_db = _path(state_db) or env_state_db or _path((persisted or {}).get("state_db"))
    resolved_watch = _path(watch_state_dir) or env_watch or _path((persisted or {}).get("watch_state_dir"))
    resolved_events = _path(events_file) or env_events or _path((persisted or {}).get("events_file"))
    resolved_outbox = _path(outbox_file) or env_outbox or _path((persisted or {}).get("outbox_file"))
    state = base_state
    values = {
        "schema_version": 1,
        "instance_id": str((persisted or {}).get("instance_id") or base_state),
        "install_root": str(base_install),
        "config_root": str(base_config),
        "state_root": str(state),
        "state_db": str(resolved_db or state / "autoops-state.db"),
        "watch_state_dir": str(resolved_watch or state / "watch"),
        "events_file": str(resolved_events or state / "events.jsonl"),
        "outbox_file": str(resolved_outbox or state / "notifications.jsonl"),
        "deployment_mode": str((persisted or {}).get("deployment_mode", "development" if os.environ.get("AUTOOPS_DEV_MODE") == "1" else "installed")),
    }
    return values


def runtime_environment(runtime: dict[str, Any]) -> dict[str, str]:
    """Return safe path variables for child project processes."""
    return {
        "AUTOOPS_INSTALL_ROOT": str(runtime["install_root"]),
        "AUTOOPS_CONFIG_ROOT": str(runtime["config_root"]),
        "AUTOOPS_STATE_ROOT": str(runtime["state_root"]),
        "AUTOOPS_STATE_DB": str(runtime["state_db"]),
        "AUTOOPS_WATCH_STATE_DIR": str(runtime["watch_state_dir"]),
        "AUTOOPS_EVENTS_FILE": str(runtime["events_file"]),
        "AUTOOPS_OUTBOX_FILE": str(runtime["outbox_file"]),
        "JIUWENSWARM_AUTOOPS_CONFIG_DIR": str(runtime["config_root"]),
    }


def write_runtime(path: Path, runtime: dict[str, Any]) -> None:
    """Atomically write the non-secret deployment instance descriptor."""
    if path.is_symlink():
        raise ValueError(f"refusing symlink runtime configuration: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o640)
    temporary.replace(path)
