"""Small bounded history store used by the CSS watcher and policy engine."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def append_sample(path: str | Path, sample: dict[str, Any], *, limit: int = 500) -> list[dict[str, Any]]:
    destination = Path(path)
    if destination.is_symlink():
        raise ValueError(f"history must not be a symlink: {destination}")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"history must be a regular file: {destination}")
    values: list[dict[str, Any]] = []
    if destination.exists():
        loaded = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("CSS history must be a JSON array")
        values = [item for item in loaded if isinstance(item, dict)]
    values.append(dict(sample))
    values = values[-max(1, limit):]
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with open(handle, "w", encoding="utf-8", closefd=True) as stream:
            json.dump(values, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
        Path(temporary).replace(destination)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()
    return values


def load_samples(path: str | Path, *, limit: int = 500) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"history must be a regular file: {source}")
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("CSS history must be a JSON array")
    return [item for item in loaded if isinstance(item, dict)][-max(1, limit):]
