#!/usr/bin/env python3
"""Run the deterministic RO-14 release acceptance gate.

The gate validates the versioned route contract and reports which parts still
need real runtime evidence.  It deliberately does not infer native expert
execution from Markdown, unit tests, or a model's final message.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "config" / "acceptance" / "route-cases-v1.json"
DEFAULT_EVIDENCE = ROOT / "docs" / "evidence"
DEFAULT_JSON = DEFAULT_EVIDENCE / "ro-14-acceptance-20260914.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "ro14-release-acceptance.md"

REQUIRED_ARTIFACTS = (
    "scripts/autoops_contract.py",
    "scripts/autoops-capability-health.py",
    "config/workflow-registry.json",
    "scripts/autoops_routing.py",
    "scripts/autoops_project_manager.py",
    "scripts/autoops_task_store.py",
    "scripts/autoops-task-control.py",
    "scripts/autoops_watch.py",
    "scripts/autoops-watch-policy.py",
    "scripts/verify-service-recovery.py",
    "scripts/verify-k8s-business.py",
    "scripts/install-autoops-runtime.py",
    "scripts/install-jiuwenswarm-autoops-skills.py",
    "scripts/tui-autoops-e2e.sh",
    "scripts/ro14-real-tui-matrix.sh",
    "scripts/autoops-native-evidence.py",
    "scripts/autoops-native-performance.py",
    "swarmflow/service-recovery-v1.py",
    "swarmflow/ro00-readonly-validation.py",
    "swarmflow/ro05-parallel-observability-v1.py",
    "swarmflow/e03-kubernetes-validation-v1.py",
    "config/capability-registry.json",
    "config/ro00-compatibility-matrix.json",
    "config/acceptance/ro-14-tui-scenarios-v1.json",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(status: str, reason: str, evidence: list[str] | None = None,
          details: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "reason": reason}
    if evidence:
        result["evidence"] = evidence
    if details:
        result["details"] = details
    return result


def route_acceptance(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if payload.get("schema_version") != 1 or payload.get("suite") != "RO-14-01" or not isinstance(cases, list):
        return check("FAIL", "route case file has an invalid schema", [str(path)])
    failures: list[dict[str, Any]] = []
    ids: list[str] = []
    sys.path.insert(0, str(ROOT / "scripts"))
    from autoops_contract import validate_route
    from autoops_routing import route_request

    for case in cases:
        case_id = case.get("case_id")
        ids.append(case_id)
        try:
            actual = validate_route(route_request(case["request"], **case.get("kwargs", {})))
            expected = case["expected"]
            actual_excluded = sorted(item["candidate"] for item in actual["excluded_candidates"])
            expected_excluded = sorted(expected.get("excluded_candidates", []))
            if (actual["selected_epics"] != expected["selected_epics"]
                    or actual_excluded != expected_excluded):
                failures.append({"case_id": case_id, "expected": expected,
                                 "actual": {"selected_epics": actual["selected_epics"],
                                             "excluded_candidates": actual_excluded}})
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"case_id": case_id, "error": str(exc)})
    expected_ids = [f"R{number:02d}-{variant:02d}" for number in range(1, 15) for variant in range(1, 5)]
    if ids != expected_ids:
        return check("FAIL", "route case IDs are not the required R01-01 through R14-04 sequence",
                     [str(path)], {"count": len(cases), "ids": ids[:4] + ids[-4:]})
    if failures:
        return check("FAIL", "one or more fixed route expectations failed", [str(path)],
                     {"count": len(cases), "failures": failures})
    return check("PASS", "56 fixed route inputs matched their published capability expectations",
                 [str(path)], {"count": len(cases)})


def artifact_acceptance(source_root: Path) -> dict[str, Any]:
    missing = [relative for relative in REQUIRED_ARTIFACTS if not (source_root / relative).is_file()]
    if missing:
        return check("FAIL", "required project integration artifacts are missing", details={"missing": missing})
    return check("PASS", "project-owned contract, routing, lifecycle, watcher, verifier, installer and TUI artifacts exist",
                 details={"artifact_count": len(REQUIRED_ARTIFACTS)})


def evidence_records(evidence_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    if not evidence_root.is_dir():
        return records
    for path in sorted(evidence_root.glob("*.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("scenarios", "runs", "measurements"):
            values = payload.get(key)
            if isinstance(values, list) and all(isinstance(value, dict) for value in values):
                records.extend((path, value) for value in values)
                break
        else:
            records.append((path, payload))
    return records


def tui_acceptance(records: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        (path, row) for path, row in records
        if row.get("acceptance_scope") == "RO-14-02"
        and row.get("evidence_level") == "real-tui"
        and row.get("scenario_id")
        and row.get("run_id")
    ]
    keys = {(row["scenario_id"], row["run_id"]) for _, row in rows}
    passed = [row for _, row in rows if str(row.get("result", "")).upper() in {"PASS", "PASSED", "PASS-END-TO-END"}]
    if len(keys) == 36 and len(passed) == 36:
        return check("PASS", "all 36 RO-14 TUI runs have explicit real-TUI evidence",
                     sorted({str(path) for path, _ in rows}), {"runs": len(keys)})
    status = "BLOCKED" if not rows else "INCONCLUSIVE"
    return check(status, "RO-14 requires 12 TUI scenario classes x 3 real runs; existing evidence does not meet that schema",
                 sorted({str(path) for path, _ in rows}), {"qualified_runs": len(keys), "passed_runs": len(passed), "required_runs": 36})


def native_expert_acceptance(records: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    partial: list[tuple[Path, dict[str, Any]]] = []
    for path, row in records:
        if row.get("acceptance_scope") == "RO-14-03" and row.get("observed_experts"):
            partial.append((path, row))
        events = row.get("native_expert_events")
        if not isinstance(events, list):
            continue
        valid = [event for event in events if isinstance(event, dict) and all(
            isinstance(event.get(key), str) and event[key] for key in
            ("expert_role", "parent_run_id", "child_run_id", "tool_result")
        )]
        if len({event["expert_role"] for event in valid}) >= 2:
            candidates.append((path, row))
    if candidates:
        return check("PASS", "at least one evidence record contains two native experts with parent/child and tool results",
                     sorted({str(path) for path, _ in candidates}), {"records": len(candidates)})
    if partial:
        return check("INCONCLUSIVE", "a native workflow and expert node were observed, but two expert tool-result records are not available",
                     sorted({str(path) for path, _ in partial}),
                     {"partial_records": len(partial), "observed_experts": sum(len(row.get("observed_experts", [])) for _, row in partial)})
    return check("BLOCKED", "no structured native expert parent/child event evidence was found; Skill or Markdown presence is insufficient")


def measurement_acceptance(records: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        (path, row) for path, row in records
        if row.get("acceptance_scope") == "RO-14-04"
        and row.get("evidence_level") in {"real-tui", "native-runtime"}
        and row.get("scenario_id")
        and row.get("run_id")
        and all(key in row for key in ("model_seconds", "tool_seconds", "query_count", "first_ack_seconds", "quiet_gap_seconds"))
    ]
    if not rows:
        return check("BLOCKED", "no RO-14 performance evidence contains model/tool duration, query count, first acknowledgement and quiet interval")
    unique = {(str(row["scenario_id"]), str(row["run_id"])): (path, row) for path, row in rows}
    if len(unique) < 36:
        return check("INCONCLUSIVE", "RO-14 performance evidence requires at least 36 unique real runs with scenario and run IDs",
                     sorted({str(path) for path, _ in rows}),
                     {"qualified_runs": len(unique), "required_runs": 36})
    rows = list(unique.values())
    try:
        values = {key: [float(row[key]) for _, row in rows] for key in
                  ("model_seconds", "tool_seconds", "query_count", "first_ack_seconds", "quiet_gap_seconds")}
    except (TypeError, ValueError) as exc:
        return check("FAIL", f"RO-14 performance evidence contains a non-numeric measurement: {exc}")
    if any(value < 0 for data in values.values() for value in data):
        return check("FAIL", "RO-14 performance evidence contains a negative measurement")
    summary = {key: {"p50": round(statistics.median(data), 3),
                     "p95": round(sorted(data)[max(0, int(len(data) * 0.95) - 1)], 3),
                     "count": len(data)} for key, data in values.items()}
    summary["qualified_runs"] = len(unique)
    return check("PASS", "RO-14 performance fields are present for at least 36 unique real runs and summarized",
                 sorted({str(path) for path, _ in rows}), summary)


def build_report(cases_path: Path = DEFAULT_CASES, evidence_root: Path = DEFAULT_EVIDENCE,
                 source_root: Path = ROOT) -> dict[str, Any]:
    records = evidence_records(evidence_root)
    checks = {
        "RO-14-01-route-contract": route_acceptance(cases_path),
        "project-artifacts": artifact_acceptance(source_root),
        "RO-14-02-real-tui": tui_acceptance(records),
        "RO-14-03-native-experts": native_expert_acceptance(records),
        "RO-14-04-performance": measurement_acceptance(records),
    }
    statuses = [item["status"] for item in checks.values()]
    overall = "PASS" if all(status == "PASS" for status in statuses) else "INCOMPLETE"
    return {
        "schema_version": 1,
        "epic": "RO-14",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "checks": checks,
        "completion_rule": "RO-14 is complete only when every check is PASS; BLOCKED and INCONCLUSIVE remain open",
    }


def markdown(report: dict[str, Any]) -> str:
    lines = ["# RO-14 发布验收报告", "", f"总体状态：`{report['overall']}`", "",
             "本报告由 `scripts/autoops-epic-acceptance.py` 生成。它把固定路由回归、项目资产、真实 TUI、原生专家事件和性能证据分别判定；缺少外部运行证据不会被代码文件或模型文本替代。", "",
             "| 检查项 | 状态 | 结论 |", "|---|---|---|"]
    for name, item in report["checks"].items():
        lines.append(f"| {name} | `{item['status']}` | {item['reason']} |")
    lines.extend(["", "## 机器可读详情", "", "```json", json.dumps(report, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the RO-14 AutoOps acceptance gate")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.cases, args.evidence_root, ROOT)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown(report), encoding="utf-8")
        print(json.dumps({"status": report["overall"], "json": str(args.json_out),
                          "markdown": str(args.markdown_out)}, ensure_ascii=False))
        return 0 if report["overall"] == "PASS" else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
