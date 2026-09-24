#!/usr/bin/env python3
"""Validate durable TUI evidence for the CSS multi-role execution chain."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ROLES = ("project-manager", "css_auto", "runbook-operator", "recovery-verifier")


def _walk(value: Any, key: str = ""):
    if isinstance(value, dict):
        for name, child in value.items():
            yield name, child
            yield from _walk(child, name)
    elif isinstance(value, list):
        for child in value:
            yield key, child
            yield from _walk(child, key)


def check_history(path: Path, required_roles: tuple[str, ...] = DEFAULT_ROLES) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        return {"status": "NOT_READY", "reasons": ["history_missing"], "observed_roles": []}
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    observed: set[str] = set()
    tool_result_events = [event for event in events
                          if event.get("event_type") == "chat.tool_result"]
    tool_results = [index for index, event in enumerate(events)
                    if event.get("event_type") == "chat.tool_result"]
    tool_calls = [event for event in events if event.get("event_type") == "chat.tool_call"]
    # Count only explicit tool selections and structured role fields in
    # operational results. Skill text, user prose, and assistant narration
    # often mention roles that were never run.
    for event in tool_calls:
        call = event.get("tool_call", {})
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        if isinstance(name, str) and name in required_roles:
            observed.add(name)
        if "autoops-project-manager.py" in json.dumps(call, ensure_ascii=False).casefold():
            observed.add("project-manager")
    for event in tool_result_events:
        if event.get("tool_name") == "skill_tool":
            continue
        result = event.get("result")
        structured_result = result
        if isinstance(result, str):
            try:
                structured_result = json.loads(result)
            except json.JSONDecodeError:
                decoder = json.JSONDecoder()
                for offset, char in enumerate(result):
                    if char != "{":
                        continue
                    try:
                        structured_result, _ = decoder.raw_decode(result[offset:])
                        break
                    except json.JSONDecodeError:
                        continue
        for name, value in _walk(structured_result):
            if name in {"selected_role", "role", "role_id", "agent", "primary_role"} and isinstance(value, str):
                observed.add(value)
            if name in {"selected_roles", "roles"} and isinstance(value, list):
                observed.update(str(item) for item in value if isinstance(item, str))
        if isinstance(result, str):
            # Some shell adapters wrap machine JSON in a short text result.
            match = re.search(r"[\"']selected_role[\"']\s*:\s*[\"']([a-z0-9_-]+)", result, re.IGNORECASE)
            if match:
                observed.add(match.group(1))
    missing = [role for role in required_roles if role not in observed]
    serialized = json.dumps(events, ensure_ascii=False).casefold()
    native_workflow_called = any(
        event.get("tool_call", {}).get("name") == "swarmflow"
        for event in tool_calls if isinstance(event.get("tool_call"), dict)
    )
    workflow_wait_failed = native_workflow_called and any(
        event.get("tool_name") == "async_task_output"
        and re.search(r"task\s+['\"]?[^\n'\"]+['\"]?\s+not found", str(event.get("result", "")), re.IGNORECASE)
        for event in tool_result_events
    )
    native_workflow_failed = native_workflow_called and any(
        term in serialized
        for term in ('"status": "failed"', "status=failed", "workflow returned `status=failed`")
    )
    final_indexes = [index for index, event in enumerate(events)
                     if event.get("event_type") == "chat.final"
                     or event.get("role") == "assistant" and event.get("content")]
    final_after_tools = bool(tool_results and final_indexes and final_indexes[-1] > tool_results[-1])
    operational_calls = sum(
        any(term in json.dumps(event, ensure_ascii=False).casefold()
            for term in ("css", "runbook", "recovery", "project-manager"))
        for event in tool_calls
    )
    reasons = []
    project_manager_route_seen = "project-manager" in observed or any(
        isinstance(event.get("tool_call"), dict)
        and "autoops-project-manager.py" in json.dumps(event["tool_call"], ensure_ascii=False).casefold()
        for event in tool_calls
    )
    if not project_manager_route_seen:
        reasons.append("project_manager_route_missing")
    if missing:
        reasons.append("role_evidence_missing")
    if not tool_results:
        reasons.append("tool_result_missing")
    if not final_after_tools:
        reasons.append("final_after_last_tool_result_missing")
    if operational_calls == 0:
        reasons.append("operational_tool_call_missing")
    if workflow_wait_failed:
        reasons.append("native_workflow_wait_failed")
    if native_workflow_failed:
        reasons.append("native_workflow_failed")
    return {
        "schema_version": 1, "status": "PASS" if not reasons else "NOT_READY",
        "history": str(path), "event_count": len(events),
        "observed_roles": sorted(observed), "required_roles": list(required_roles),
        "missing_roles": missing, "operational_calls": operational_calls,
        "final_after_tools": final_after_tools, "native_workflow_called": native_workflow_called,
        "reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check CSS role-chain evidence from a JiuwenSwarm TUI history.")
    parser.add_argument("history", type=Path)
    parser.add_argument("--required-role", action="append", dest="roles")
    args = parser.parse_args(argv)
    try:
        result = check_history(args.history, tuple(args.roles or DEFAULT_ROLES))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "NOT_READY", "reasons": ["history_invalid"], "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
