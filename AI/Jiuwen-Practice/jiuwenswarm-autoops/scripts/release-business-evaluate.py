#!/usr/bin/env python3
"""Evaluate release business evidence without trusting chat text."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "acceptance" / "release-ao50-v1.json"


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"release evidence must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"release evidence must be a JSON object: {path}")
    return value


def read_results(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"results must be a regular file: {path}")
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("case_id"), str):
            rows.append(value)
    return rows


def dimension_status(row: dict[str, Any], field: str, *, default: str = "INCONCLUSIVE") -> str:
    value = row.get(field, default)
    normalized = str(value).upper()
    return normalized if normalized in {"PASS", "NOT_REQUIRED", "FAIL", "INCONCLUSIVE", "BLOCKED"} else "INCONCLUSIVE"


def evaluate_rows(rows: list[dict[str, Any]], manifest: dict[str, Any], artifact_sha256: str) -> dict[str, Any]:
    expected = [str(item.get("case_id")) for item in manifest.get("cases", []) if isinstance(item, dict)]
    by_case: dict[str, list[dict[str, Any]]] = {}
    stale = []
    for row in rows:
        if row.get("artifact_sha256") != artifact_sha256:
            stale.append(row.get("case_id"))
            continue
        by_case.setdefault(str(row["case_id"]), []).append(row)
    current = {case_id: values[-1] for case_id, values in by_case.items()}
    missing = [case_id for case_id in expected if case_id not in current]
    duplicates = [case_id for case_id, values in by_case.items() if len(values) > 1]
    history_failures = [case_id for case_id, values in by_case.items()
                        if any(str(value.get("business_status", "")).upper() in {"FAIL", "FAILED"}
                               for value in values)]
    route_failed = [case_id for case_id, row in current.items()
                    if row.get("result") != "PASS_TUI_ROUTE"
                    or not bool(row.get("checker", {}).get("ready"))]
    business_missing = [case_id for case_id, row in current.items()
                        if str(row.get("business_status", "")).upper() in {
                            "", "NOT_EVALUATED", "NOT_EVALUATED_FIXTURE_REQUIRED"}]
    business_failed = [case_id for case_id, row in current.items()
                       if str(row.get("business_status", "")).upper() in {"FAIL", "FAILED", "BLOCKED"}]
    dimensions: dict[str, dict[str, Any]] = {}
    for label, field in (("native_dispatch", "native_dispatch_status"),
                         ("diagnosis", "diagnosis_status"),
                         ("action", "action_status"),
                         ("verification", "verification_status")):
        values = {case_id: dimension_status(row, field) for case_id, row in current.items()}
        failed = [case_id for case_id, status in values.items() if status in {"FAIL", "BLOCKED", "INCONCLUSIVE"}]
        dimensions[label] = {"status": "PASS" if not failed else "NO_GO", "failed": failed}
    reasons = []
    if missing:
        reasons.append("case_missing")
    if stale:
        reasons.append("artifact_mismatch")
    if route_failed:
        reasons.append("tui_route_failed")
    if business_missing:
        reasons.append("business_evidence_missing")
    if business_failed:
        reasons.append("business_assertion_failed")
    if duplicates:
        reasons.append("duplicate_current_attempt")
    if history_failures:
        reasons.append("historical_failure_present")
    if any(item["status"] != "PASS" for item in dimensions.values()):
        reasons.append("evidence_dimension_incomplete")
    return {
        "schema_version": 1,
        "artifact_sha256": artifact_sha256,
        "expected_cases": len(expected),
        "current_cases": len(current),
        "missing": missing,
        "stale": sorted(set(str(item) for item in stale if item)),
        "duplicate_current_attempt": sorted(set(duplicates)),
        "historical_failures": sorted(set(history_failures)),
        "route": {"status": "PASS" if not route_failed and len(current) == len(expected) else "NO_GO",
                  "failed": route_failed},
        "business": {"status": "PASS" if not business_missing and not business_failed else "NO_GO",
                     "missing": business_missing, "failed": business_failed},
        "dimensions": dimensions,
        "reasons": sorted(set(reasons)),
        "status": "GO" if not reasons and len(current) == len(expected) else "NO_GO",
    }


def evaluate(results_path: Path, manifest_path: Path, artifact_sha256: str) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    if manifest.get("kind") != "AutoOpsReleaseAcceptanceCaseManifest":
        raise ValueError("invalid release case manifest")
    return evaluate_rows(read_results(results_path), manifest, artifact_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate AO50 business evidence by independent dimensions.")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--artifact-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.results, args.manifest, args.artifact_sha256)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 1, "status": "NO_GO", "reasons": ["input_error"], "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
