#!/usr/bin/env python3
"""Decide whether CSS stability evidence is sufficient for release.

The gate is intentionally conservative.  Local fixtures can prove code
behavior, but they cannot satisfy the real-business or 24-hour requirements.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = ("css-50-e2e.json", "soak.json", "efficiency.json", "tui.json",
                  "install.json", "real-validation.json")


def _load(directory: Path, name: str, reasons: list[str]) -> dict[str, Any]:
    path = directory / name
    if not path.is_file() or path.is_symlink():
        reasons.append(f"evidence_missing:{name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append(f"evidence_invalid:{name}")
        return {}
    if not isinstance(value, dict):
        reasons.append(f"evidence_not_object:{name}")
        return {}
    return value


def canonical_case_id(item: dict[str, Any]) -> str:
    value = str(item.get("case_id") or item.get("id") or "")
    if value.startswith("CSS50-"):
        suffix = value.split("-", 1)[1]
        if suffix.isdigit():
            return f"CSS-S{int(suffix):02d}"
    return value


def check(directory: Path) -> dict[str, Any]:
    reasons: list[str] = []
    evidence = {name: _load(directory, name, reasons) for name in REQUIRED_FILES}
    # Prefer a completed real-write run when it exists.  The original
    # fixture/read-only report may intentionally contain SKIPPED S49/S50 and
    # must not mask a later factual real control-plane run.
    real_e2e_path = directory / "css-50-real-writes.json"
    if real_e2e_path.is_file() and not real_e2e_path.is_symlink():
        e2e = _load(directory, "css-50-real-writes.json", reasons)
        e2e_source = "css-50-real-writes.json"
    else:
        e2e = evidence["css-50-e2e.json"]
        e2e_source = "css-50-e2e.json"
    cases = e2e.get("results")
    if not isinstance(cases, list) or len(cases) != 50:
        reasons.append("css_50_case_count_not_50")
        cases = cases if isinstance(cases, list) else []
    ids = [canonical_case_id(item) for item in cases if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        reasons.append("css_50_case_ids_not_unique")
    if any(item.get("status") in {"FAIL", "UNKNOWN", "NOT_READY", "SKIPPED", "BLOCKED"}
           for item in cases if isinstance(item, dict)):
        reasons.append("css_50_unresolved_case")
    required_business = {"CSS-S49", "CSS-S50"}
    by_id = {canonical_case_id(item): item for item in cases if isinstance(item, dict)}
    for case_id in sorted(required_business):
        item = by_id.get(case_id)
        if not item:
            reasons.append(f"real_business_case_missing:{case_id}")
            continue
        if item.get("status") != "PASS":
            reasons.append(f"real_business_case_not_pass:{case_id}")
        if item.get("execution_level") != "REAL_BUSINESS":
            reasons.append(f"real_business_level_missing:{case_id}")
        if item.get("business_verification") not in {"PASS", "PASSED", "SUCCEEDED"}:
            reasons.append(f"business_verification_missing:{case_id}")
    soak = evidence["soak.json"]
    if soak.get("status") != "PASS":
        reasons.append("local_soak_not_pass")
    efficiency = evidence["efficiency.json"]
    try:
        reduction = float(efficiency.get("reduction_ratio"))
    except (TypeError, ValueError):
        reduction = 0
    if efficiency.get("status") != "PASS" or reduction < 0.5:
        reasons.append("collection_efficiency_below_50_percent")
    if evidence["tui.json"].get("status") != "PASS":
        reasons.append("tui_role_chain_not_pass")
    if evidence["install.json"].get("status") != "PASS":
        reasons.append("clean_install_not_pass")
    real = evidence["real-validation.json"]
    try:
        wall_clock_hours = float(real.get("wall_clock_hours"))
    except (TypeError, ValueError):
        wall_clock_hours = 0
    if real.get("status") != "PASS" or wall_clock_hours < 24:
        reasons.append("real_24h_evidence_missing")
    if real.get("business_verification") not in {"PASS", "PASSED", "SUCCEEDED"}:
        reasons.append("real_business_verification_missing")
    if real.get("cleanup") is not True:
        reasons.append("real_cleanup_not_confirmed")
    return {
        "schema_version": 1, "status": "READY" if not reasons else "NOT_READY",
        "evidence_dir": str(directory), "case_count": len(cases),
        "canonical_case_count": len(set(ids)), "reduction_ratio": reduction,
        "e2e_source": e2e_source, "wall_clock_hours": wall_clock_hours,
        "reasons": sorted(set(reasons)),
        "release_decision": "READY" if not reasons else "NOT_READY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate CSS stability evidence for release.")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = check(args.evidence_dir)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 1, "status": "NOT_READY", "reasons": ["gate_input_error"], "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
