#!/usr/bin/env python3
"""Aggregate ~/.cursor-hybrid/route-audit.jsonl KPIs."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AUDIT_PATH  # noqa: E402


def main() -> int:
    if not AUDIT_PATH.exists():
        print(f"No audit log at {AUDIT_PATH}")
        return 0

    types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    total = 0
    for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        types[row.get("type", "?")] += 1
        statuses[str(row.get("result_status") or row.get("status") or "?")] += 1

    print(f"audit_file={AUDIT_PATH}")
    print(f"events={total}")
    print("by_type:")
    for k, v in types.most_common():
        print(f"  {k}: {v}")
    print("by_status:")
    for k, v in statuses.most_common():
        print(f"  {k}: {v}")

    escalations = statuses.get("needs_escalation", 0)
    successes = statuses.get("success", 0)
    denom = max(escalations + successes, 1)
    print(f"escalation_rate~={escalations / denom:.2%} (among success+escalation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
