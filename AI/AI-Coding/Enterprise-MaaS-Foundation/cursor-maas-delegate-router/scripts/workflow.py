#!/usr/bin/env python3
"""Fan-out multiple disjoint briefs with a concurrency governor."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SKILL_ROOT, audit  # noqa: E402

DELEGATE = SKILL_ROOT / "scripts" / "delegate.py"


def load_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if args.manifest_file:
        return json.loads(Path(args.manifest_file).read_text(encoding="utf-8"))
    if args.manifest:
        return json.loads(args.manifest)
    raise SystemExit("Provide --manifest or --manifest-file")


def assert_disjoint(items: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    for item in items:
        item_id = item.get("id") or item.get("goal", "")[:40]
        for f in item.get("files") or []:
            key = str(Path(f)).replace("\\", "/").lower()
            if key in seen:
                raise SystemExit(
                    f"Overlapping file scope refused: {f!r} in {item_id!r} and {seen[key]!r}"
                )
            seen[key] = item_id


def run_item(item: dict[str, Any]) -> dict[str, Any]:
    brief = {
        "goal": item["goal"],
        "files": item.get("files", []),
        "acceptance": item["acceptance"],
        "constraints": item.get("constraints", []),
        "context": item.get("context", ""),
        "max_attempts": item.get("max_attempts", 2),
    }
    proc = subprocess.run(
        [sys.executable, str(DELEGATE), "--brief", json.dumps(brief, ensure_ascii=False)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        result = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        result = {
            "status": "failed",
            "summary": proc.stderr or proc.stdout or "empty delegate output",
            "acceptance_met": False,
        }
    result["id"] = item.get("id")
    result["exit_code"] = proc.returncode
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--manifest-file", default=None)
    args = parser.parse_args()

    manifest = load_manifest(args)
    items = manifest.get("items") or []
    if not items:
        raise SystemExit("manifest.items empty")
    assert_disjoint(items)

    workflow_id = manifest.get("workflow_id") or str(uuid.uuid4())
    concurrency = int(manifest.get("concurrency") or 3)

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(run_item, item): item for item in items}
        for fut in as_completed(futures):
            results.append(fut.result())

    success = [r for r in results if r.get("status") == "success"]
    escalated = [r for r in results if r.get("status") == "needs_escalation"]
    failed = [r for r in results if r.get("status") not in ("success", "needs_escalation")]
    remainder_ratio = (len(escalated) + len(failed)) / max(len(results), 1)

    out = {
        "workflow_id": workflow_id,
        "total": len(results),
        "success": len(success),
        "needs_escalation": len(escalated),
        "failed": len(failed),
        "remainder_ratio": round(remainder_ratio, 3),
        "abort_reclassify_premium": remainder_ratio > 0.30,
        "results": results,
    }
    audit({"type": "workflow", **{k: out[k] for k in out if k != "results"}})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out["abort_reclassify_premium"]:
        return 3
    if escalated or failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
