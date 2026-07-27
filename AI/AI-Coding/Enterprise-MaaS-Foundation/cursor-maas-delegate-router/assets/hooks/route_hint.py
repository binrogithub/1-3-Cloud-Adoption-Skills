#!/usr/bin/env python3
"""User-global beforeSubmitPrompt: remind silent MaaS default (fail-open)."""

from __future__ import annotations

import json
import sys

HINT = (
    "[maas-route:global] SILENT DEFAULT (all workspaces): plan UI/architecture "
    "in chat if needed, then implement code ONLY via "
    "python ~/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py "
    "(Huawei MaaS GLM). Hard stop: do not Write/StrReplace app source "
    "(html/css/js/ts/py, including Hello World / greenfield) when a brief can "
    "be delegated. User need not name any skill."
)


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
                "agentMessage": HINT,
                "additional_context": HINT,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
