#!/usr/bin/env python3
"""Resolve only administrator-published compensation actions."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "config" / "compensation-registry.json"
DEFAULT_CAPABILITIES = ROOT / "config" / "capability-registry.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_compensation(trigger_capability: str, *, registry_path: Path | None = None,
                         capability_path: Path | None = None) -> dict[str, Any]:
    """Return a bounded compensation decision without invoking any action."""
    registry_path = registry_path or Path(os.environ.get("AUTOOPS_COMPENSATION_REGISTRY", DEFAULT_REGISTRY))
    capability_path = capability_path or Path(os.environ.get("AUTOOPS_CAPABILITY_REGISTRY", DEFAULT_CAPABILITIES))
    try:
        entries = _read(registry_path).get("compensations", [])
        capabilities = _read(capability_path).get("capabilities", {})
    except (OSError, TypeError, json.JSONDecodeError):
        return {"status": "NOT_CONFIGURED", "error_code": "COMPENSATION_REGISTRY_UNAVAILABLE",
                "trigger_capability": trigger_capability}
    matches = [item for item in entries if isinstance(item, dict)
               and item.get("trigger_capability") == trigger_capability]
    published = [item for item in matches if item.get("status") == "PUBLISHED"]
    if not published:
        reason = matches[0].get("reason") if matches else "no compensation action is registered"
        return {"status": "NOT_PUBLISHED", "error_code": "COMPENSATION_NOT_PUBLISHED",
                "trigger_capability": trigger_capability, "reason": reason}
    if len(published) != 1:
        return {"status": "BLOCKED", "error_code": "COMPENSATION_AMBIGUOUS",
                "trigger_capability": trigger_capability,
                "candidate_ids": [item.get("id") for item in published]}
    action = published[0]
    capability = action.get("capability")
    definition = capabilities.get(capability) if isinstance(capabilities, dict) else None
    if not isinstance(capability, str) or not isinstance(definition, dict) \
            or definition.get("effect") != "write":
        return {"status": "BLOCKED", "error_code": "COMPENSATION_CAPABILITY_INVALID",
                "trigger_capability": trigger_capability, "compensation_id": action.get("id")}
    return {"status": "PUBLISHED", "trigger_capability": trigger_capability,
            "compensation_id": action.get("id"), "capability": capability,
            "effect": "write", "requires_new_authorization": True}
