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


def validate_manifest(manifest: dict[str, Any]) -> None:
    items = manifest.get("items") or []
    if not isinstance(items, list) or not items:
        raise SystemExit("manifest.items empty")
    try:
        concurrency = int(manifest.get("concurrency") or 3)
    except (TypeError, ValueError) as e:
        raise SystemExit("manifest.concurrency must be an integer") from e
    if not 1 <= concurrency <= 16:
        raise SystemExit("manifest.concurrency must be between 1 and 16")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise SystemExit(f"manifest.items[{idx}] must be an object")
        for key in ("goal", "files", "acceptance"):
            if key not in item:
                raise SystemExit(f"manifest.items[{idx}] missing required field: {key}")
        if not isinstance(item["goal"], str) or not item["goal"].strip():
            raise SystemExit(f"manifest.items[{idx}].goal must be a non-empty string")
        if not isinstance(item["files"], list) or any(
            not isinstance(path, str) for path in item["files"]
        ):
            raise SystemExit(f"manifest.items[{idx}].files must be an array of strings")
        if not isinstance(item["acceptance"], str) or not item["acceptance"].strip():
            raise SystemExit(f"manifest.items[{idx}].acceptance must be a non-empty string")
        try:
            max_attempts = int(item.get("max_attempts") or 2)
        except (TypeError, ValueError) as e:
            raise SystemExit(f"manifest.items[{idx}].max_attempts must be an integer") from e
        if not 1 <= max_attempts <= 5:
            raise SystemExit(f"manifest.items[{idx}].max_attempts must be between 1 and 5")


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


def summarize_results(
    *,
    workflow_id: str,
    total_items: int,
    results: list[dict[str, Any]],
    aborted: bool,
) -> dict[str, Any]:
    success = [r for r in results if r.get("status") == "success"]
    escalated = [r for r in results if r.get("status") == "needs_escalation"]
    failed = [r for r in results if r.get("status") not in ("success", "needs_escalation")]
    remainder_ratio = (len(escalated) + len(failed)) / max(total_items, 1)
    return {
        "workflow_id": workflow_id,
        "total": len(results),
        "total_items": total_items,
        "success": len(success),
        "needs_escalation": len(escalated),
        "failed": len(failed),
        "remainder_ratio": round(remainder_ratio, 3),
        "abort_reclassify_premium": aborted or remainder_ratio > 0.30,
        "results": results,
    }


def execute_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    items = manifest["items"]
    assert_disjoint(items)

    workflow_id = manifest.get("workflow_id") or str(uuid.uuid4())
    concurrency = int(manifest.get("concurrency") or 3)
    total_items = len(items)
    results: list[dict[str, Any]] = []
    next_index = 0
    aborted = False

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        while next_index < total_items and len(futures) < concurrency:
            item = items[next_index]
            futures[pool.submit(run_item, item)] = item
            next_index += 1

        while futures:
            for fut in as_completed(list(futures)):
                futures.pop(fut)
                results.append(fut.result())

                remainder_count = len(
                    [r for r in results if r.get("status") != "success"]
                )
                if remainder_count / max(total_items, 1) > 0.30:
                    aborted = True
                    break

                while next_index < total_items and len(futures) < concurrency:
                    item = items[next_index]
                    futures[pool.submit(run_item, item)] = item
                    next_index += 1
                break
            if aborted:
                for fut in futures:
                    fut.cancel()
                break

    return summarize_results(
        workflow_id=workflow_id,
        total_items=total_items,
        results=results,
        aborted=aborted,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--manifest-file", default=None)
    args = parser.parse_args()

    out = execute_manifest(load_manifest(args))
    audit({"type": "workflow", **{k: out[k] for k in out if k != "results"}})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out["abort_reclassify_premium"]:
        return 3
    if escalated or failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
