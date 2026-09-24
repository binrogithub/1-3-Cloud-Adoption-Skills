#!/usr/bin/env python3
"""Check durable TUI reconnect continuity for one AutoOps session."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def values(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from values(item)
    elif isinstance(value, list):
        for item in value:
            yield from values(item)
    elif isinstance(value, str):
        yield value


def task_ids_in_text(value: str) -> list[str]:
    """Extract task IDs from both structured JSON and JiuwenSwarm text wrappers."""
    return [match.strip() for match in re.findall(r"(?:\\?\")task_id(?:\\?\")\s*:\s*(?:\\?\")([^\\\"]+)(?:\\?\")", value)
            if match.strip()]


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ready": False, "error": "history path required"}))
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(json.dumps({"ready": False, "error": "history not found"}))
        return 1
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    users = [event for event in events if event.get("role") == "user" and event.get("event_type") is None]
    user_indices = [index for index, event in enumerate(events)
                    if event.get("role") == "user" and event.get("event_type") is None]
    final_indices = [index for index, event in enumerate(events)
                     if event.get("event_type") == "chat.final" and str(event.get("content", "")).strip()]
    task_ids = []
    for event in events:
        for item in values(event):
            if isinstance(item, dict) and isinstance(item.get("task_id"), str) and item["task_id"].strip():
                task_ids.append(item["task_id"].strip())
            elif isinstance(item, str):
                task_ids.extend(task_ids_in_text(item))
    unique_task_ids = sorted(set(task_ids))
    ready = bool(
        len(users) >= 2
        and all(str(event.get("content", "")).startswith("#autoops-project-manager ") for event in users[:2])
        and len(final_indices) >= 2
        and final_indices[-1] > user_indices[1]
        and len(unique_task_ids) == 1
    )
    payload = {"ready": ready, "user_messages": len(users), "final_messages": len(final_indices),
               "final_after_reconnect": bool(user_indices and final_indices and final_indices[-1] > user_indices[1]),
               "task_ids": unique_task_ids}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
