#!/usr/bin/env python3
"""Create a short-lived approval record from an operator-controlled shell."""
from __future__ import annotations

import argparse
import json
import secrets
import time
from pathlib import Path

from autoops_authorization import authorization_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="Approve one exact AutoOps write request.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--ttl-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    if args.ttl_seconds < 1 or args.ttl_seconds > 3600:
        parser.error("ttl-seconds must be between 1 and 3600")
    approval_id = f"approval-{secrets.token_urlsafe(24)}"
    directory = authorization_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{approval_id}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "status": "APPROVED",
        "authorization_id": approval_id,
        "task_id": args.task_id,
        "job": args.job,
        "target": args.target,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + args.ttl_seconds,
        "uses": 1,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)
    print(json.dumps({"status": "APPROVED", "authorization_id": approval_id, "expires_in": args.ttl_seconds}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
