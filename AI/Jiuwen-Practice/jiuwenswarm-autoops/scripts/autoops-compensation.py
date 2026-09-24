#!/usr/bin/env python3
"""Inspect the published compensation directory without executing it."""
from __future__ import annotations

import argparse
import json

from autoops_compensation import resolve_compensation


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a published AutoOps compensation action.")
    parser.add_argument("--capability", required=True)
    args = parser.parse_args()
    result = resolve_compensation(args.capability)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"PUBLISHED", "NOT_PUBLISHED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
