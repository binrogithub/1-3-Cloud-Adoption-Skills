"""Load the protected, local Rundeck deployment configuration.

This project-owned helper deliberately parses a small ``KEY=value`` file rather
than sourcing it in a shell.  The TUI backend therefore receives credentials
without inheriting a developer's interactive shell environment.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


DEFAULT_ENV_FILE = Path.home() / ".config" / "jiuwenswarm-autoops" / "rundeck-e2e.env"
DEFAULT_JOB_REGISTRY = Path.home() / ".config" / "jiuwenswarm-autoops" / "rundeck-jobs.json"
ALLOWED_KEYS = {
    "RUNDECK_BASE_URL",
    "RUNDECK_API_TOKEN",
    "RUNDECK_PROJECT",
    "RUNDECK_HOST_BASIC_CHECK_JOB_ID",
    "RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID",
    "RUNDECK_TIMEOUT_SECONDS",
}


def _regular_private_file(path: Path) -> Path:
    path = path.expanduser()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"AutoOps Rundeck configuration must be a regular file: {path}")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError(f"AutoOps Rundeck configuration must not be group/world accessible: {path}")
    return path


def _value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_rundeck_environment(environment: dict[str, str] | None = None) -> dict[str, str]:
    """Fill missing allowed Rundeck settings from the protected local file."""
    destination = os.environ if environment is None else environment
    config_file = Path(destination.get("AUTOOPS_RUNDECK_ENV_FILE", str(DEFAULT_ENV_FILE)))
    try:
        config_file = _regular_private_file(config_file)
    except FileNotFoundError:
        return destination
    for raw in config_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in ALLOWED_KEYS and not destination.get(key):
            destination[key] = _value(value)
    return destination


def job_registry(project_root: Path, environment: dict[str, str] | None = None) -> Path:
    """Return a protected deployment registry when available, else the sample registry."""
    source = os.environ if environment is None else environment
    configured = source.get("RUNDECK_JOB_REGISTRY")
    candidate = Path(configured).expanduser() if configured else DEFAULT_JOB_REGISTRY
    try:
        return _regular_private_file(candidate)
    except FileNotFoundError:
        return project_root / "config" / "rundeck-jobs.json"
