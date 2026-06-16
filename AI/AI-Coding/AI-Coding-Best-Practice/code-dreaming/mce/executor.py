"""Unified execution plans."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mce.backbone import Backbone, Scope
from mce.writeback import writeback_from_memory


@dataclass(frozen=True)
class ExecutionSummary:
    plan: str
    mode: str
    writeback: dict


def run_plan(
    plan: str,
    *,
    memory_dir: Path,
    repo_root: Path,
    scope: Scope,
    mode: str = "review",
    source: Path | None = None,
    config_path: Path | None = None,
    allow_global: bool = False,
    backbone: Backbone | None = None,
) -> ExecutionSummary:
    if plan != "dream-writeback":
        raise ValueError("supported plans: dream-writeback")
    writeback = writeback_from_memory(
        memory_dir=memory_dir,
        repo_root=repo_root,
        scope=scope,
        mode=mode,
        source=source,
        config_path=config_path,
        allow_global=allow_global,
        backbone=backbone,
    )
    return ExecutionSummary(plan=plan, mode=mode, writeback=asdict(writeback))


def summary_json(summary: ExecutionSummary) -> str:
    return json.dumps(asdict(summary), indent=2)

