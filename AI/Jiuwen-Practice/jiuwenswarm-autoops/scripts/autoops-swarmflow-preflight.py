#!/usr/bin/env python3
"""Validate project-owned prerequisites before registering the AutoOps SwarmFlow."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git_revision(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                            text=True, capture_output=True, check=False)
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else None


def _package_versions(runtime_python: str | None) -> dict[str, str]:
    if not runtime_python or not Path(runtime_python).is_file():
        return {}
    code = (
        "import importlib.metadata as m\n"
        "for name in ('jiuwenswarm', 'openjiuwen'):\n"
        "  try: print(name + '=' + m.version(name))\n"
        "  except m.PackageNotFoundError: pass\n"
    )
    result = subprocess.run([runtime_python, "-c", code], text=True,
                            capture_output=True, check=False)
    versions: dict[str, str] = {}
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            name, separator, version = line.partition("=")
            if separator and name and version:
                versions[name] = version
    return versions


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--jiuwenswarm-source", default="/root/src/jiuwenswarm")
    parser.add_argument("--runtime-python")
    args = parser.parse_args(argv)
    source = Path(args.jiuwenswarm_source)
    executable = Path(shutil.which("jiuwenswarm") or "")
    runtime_python = args.runtime_python
    if runtime_python is None and executable.is_file():
        first_line = executable.read_text(encoding="utf-8").splitlines()[0]
        if first_line.startswith("#!"):
            runtime_python = first_line[2:]
    required = {
        "workflow_asset": ROOT / "swarmflow" / "service-recovery-v1.py",
        "readonly_validation_workflow": ROOT / "swarmflow" / "ro00-readonly-validation.py",
        "parallel_observability_workflow": ROOT / "swarmflow" / "ro05-parallel-observability-v1.py",
        "capability_registry": ROOT / "config" / "capability-registry.json",
        "workflow_registry": ROOT / "config" / "workflow-registry.json",
        "compatibility_matrix": ROOT / "config" / "ro00-compatibility-matrix.json",
        "swarmflow_guide": source / "docs" / "en" / "TUISwarmFlowGuide.md",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    runtime_check = False
    if runtime_python and Path(runtime_python).is_file():
        check = subprocess.run([runtime_python, "-c", "import openjiuwen.agent_teams.workflow.engine.facade"], text=True, capture_output=True, check=False)
        runtime_check = check.returncode == 0
    if not runtime_check:
        missing.append("runtime_swarmflow_facade")
    matrix_path = required["compatibility_matrix"]
    matrix_valid = False
    if matrix_path.is_file():
        try:
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            contracts = matrix.get("contracts") if isinstance(matrix, dict) else None
            matrix_valid = (matrix.get("schema_version") == 1
                            and isinstance(contracts, list) and len(contracts) >= 3)
        except (OSError, json.JSONDecodeError, AttributeError):
            matrix_valid = False
    if not matrix_valid:
        missing.append("invalid_compatibility_matrix")
    payload = {
        "status": "READY" if not missing else "BLOCKED",
        "source": str(source),
        "runtime_python": runtime_python,
        "runtime_identifiers": {
            "source_revision": _git_revision(source),
            "runtime_packages": _package_versions(runtime_python),
            "workflow_asset_sha256": _sha256(required["readonly_validation_workflow"]),
            "compatibility_matrix_sha256": _sha256(matrix_path),
            "maas_model_configured": bool(os.environ.get("MODEL_NAME")),
        },
        "checks": {name: str(path) for name, path in required.items()},
        "missing": missing,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
