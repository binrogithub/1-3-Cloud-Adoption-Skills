#!/usr/bin/env python3
"""Importable session-aware core for the legacy ``delegate`` CLI.

The executable remains the stable JSON interface.  This module is the API used
by ``maas-delegate`` and workflow code so they can supply a Claude Code session
without changing the legacy command-line contract.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True


_ENGINE_NAME = "_claude_maas_delegate_engine"


def _engine():
    loaded = sys.modules.get(_ENGINE_NAME)
    if loaded is not None:
        return loaded
    path = Path(__file__).with_name("delegate")
    loader = importlib.machinery.SourceFileLoader(_ENGINE_NAME, str(path))
    spec = importlib.util.spec_from_loader(_ENGINE_NAME, loader)
    if spec is None:
        raise RuntimeError("could not load delegate engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_ENGINE_NAME] = module
    loader.exec_module(module)
    return module


def run(brief: Any, *, cwd: str | None = None, client_bin: str = "claude-maas",
        timeout: float = 600.0, claude_session_id: str | None = None,
        resume: bool = False, audit_context: dict | None = None) -> dict:
    """Run a validated delegation with optional caller-owned session context."""
    return _engine().run(
        brief,
        cwd=cwd,
        client_bin=client_bin,
        timeout=timeout,
        claude_session_id=claude_session_id,
        resume=resume,
        audit_context=audit_context,
    )


def set_client_factory(factory) -> None:
    """Forward the legacy test hook for callers that inject a client."""
    _engine().set_client_factory(factory)


def validate_brief(brief: Any) -> list[str]:
    """Validate a brief without side effects.

    Returns a list of human-readable error strings (empty == valid).
    This performs the same schema and write-op-scope checks as ``run`` but
    without launching a client, writing audit, or touching any session state.
    Callers that manage sessions (e.g. ``maas-delegate``) should call this
    *before* acquiring a session so an invalid brief cannot poison the
    session registry.
    """
    engine = _engine()
    try:
        schema = engine._load_schema()
    except Exception as exc:
        return [f"schema load error: {exc}"]
    errors = engine._validate_brief(brief, schema)
    if errors:
        return errors
    # Write-op scope check (mirrors the check in delegate.run).
    task_type = brief.get("task_type")
    scope = brief.get("scope", [])
    if task_type in engine.WRITE_OP_TYPES and not scope:
        return ["write-op task type requires a non-empty scope"]
    return []
