#!/usr/bin/env python3
"""User-global sessionStart: inject MaaS code-execution default into every Agent chat."""

from __future__ import annotations

import json
import sys

CONTEXT = """
[maas-route:global] USER-GLOBAL default for ALL workspaces:
Code execution → Huawei MaaS GLM via
  python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py
Hard stop: after UI/architecture planning, do NOT Write/StrReplace application
source (html/css/js/ts/py, including new/greenfield/Hello World pages). Write a
brief JSON, run delegate.py, then integrate results. User need not name any skill.
Premium stay: hard multi-system debug, security, incidents, vision/PDF until text,
needs_escalation. Do not set Override OpenAI Base URL on the orchestrator session.
""".strip()


def main() -> int:
    try:
        raw = sys.stdin.read()
        if raw.strip():
            json.loads(raw)
    except Exception:
        print(json.dumps({}))
        return 0

    print(
        json.dumps(
            {
                "continue": True,
                "additional_context": CONTEXT,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
