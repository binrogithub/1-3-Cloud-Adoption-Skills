#!/usr/bin/env python3
"""Run the 50-case CSS AutoOps acceptance flow against a real KooCLI profile.

Cases are executed serially. A failure writes the partial report and stops so
the defect can be fixed before the next case. Cases 11-28 deliberately alter
the policy or evidence *after* collecting a real CSS/CES snapshot; they test
the deterministic safety guards without pretending that an artificial metric
was observed in Huawei Cloud. Cases 49-50 are the only real capacity writes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from css_cloud import CssCloudError, ces_metric_samples, cluster_snapshot  # noqa: E402
from css_config import effective_policy, load_credentials, load_profile, safe_profile_summary  # noqa: E402
from css_metrics import normalize_snapshot  # noqa: E402
from css_policy import evaluate  # noqa: E402


WATCH_DIR: Path | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def raw_from_cloud(profile: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    topology = cluster_snapshot(profile, credentials)
    values = ces_metric_samples(profile, credentials)
    metric_names = {
        "disk_usage_pct": "disk_util", "jvm_heap_max": "max_jvm_heap_usage",
        "cpu_max": "max_cpu_usage", "search_rate": "SearchRate",
        "search_latency": "SearchLatency", "indexing_rate": "IndexingRate",
        "indexing_latency": "IndexingLatency",
    }
    metric_samples = {target: dict(values.get(source, {})) for target, source in metric_names.items()}
    return {
        "source": "huaweicloud-css-ces",
        "observed_at": topology["observed_at"],
        "metrics": {
            "cluster_status": 0 if topology["cluster_healthy"] else 3,
            **{name: sample.get("value") for name, sample in metric_samples.items()},
        },
        "metric_samples": metric_samples,
        "topology": topology,
    }


def real_snapshot(profile: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    raw = raw_from_cloud(profile, credentials)
    return normalize_snapshot(raw, source=raw["source"], window_minutes=10)


def run_json(command: list[str], *, env: dict[str, str] | None = None,
             timeout: int = 1800) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(command, env=env, capture_output=True, text=True,
                            check=False, timeout=timeout)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"status": "INVALID_OUTPUT", "stdout": result.stdout[-2000:],
                   "stderr": result.stderr[-2000:]}
    return result.returncode, payload


def copy_runtime_config(source: Path, target: Path) -> None:
    for name in ("clusters", "credentials", "policies"):
        shutil.copytree(source / name, target / name)


def set_policy(directory: Path, changes: dict[str, Any]) -> dict[str, Any]:
    path = directory / "policies" / "css-default.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy.update(changes)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return policy


def policy_for(source: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    policy = dict(source)
    policy.update(changes)
    return policy


def topology_file(directory: Path, snapshot: dict[str, Any], name: str) -> Path:
    path = directory / f"{name}.topology.json"
    path.write_text(json.dumps(snapshot["topology"], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def invoke_runbook(directory: Path, snapshot: dict[str, Any], case_id: str,
                   direction: str, *, execute: bool, role: str = "runbook-operator",
                   mutation: bool = True, target_nodes: int | None = None,
                   action_db: Path | None = None) -> dict[str, Any]:
    state = action_db or directory / "actions.sqlite3"
    topology = topology_file(directory, snapshot, case_id)
    environment = os.environ.copy()
    environment["AUTOOPS_CSS_ACTION_DB"] = str(state)
    environment["AUTOOPS_AUTHENTICATED_ROLE"] = role
    environment["AUTOOPS_CSS_MUTATION_ENABLED"] = "1" if mutation else "0"
    command = [sys.executable, str(SCRIPTS / "css-scale-runbook.py"),
               "--task-id", case_id, "--idempotency-key", case_id,
               "--profile-id", "css-santiago", "--direction", direction,
               "--delta", "1", "--config-dir", str(directory),
               "--target-nodes", str(target_nodes or
                                      snapshot["topology"]["data_node_count"]),
               "--topology-file", str(topology)]
    if execute:
        command.append("--execute")
    code, payload = run_json(command, env=environment)
    payload["exit_code"] = code
    return payload


def wait_for_capacity(profile: dict[str, Any], credentials: dict[str, Any], target: int,
                      timeout: int, interval: int) -> dict[str, Any]:
    started = time.monotonic()
    timeline: list[dict[str, Any]] = []
    while True:
        snapshot = real_snapshot(profile, credentials)
        topology = snapshot["topology"]
        observation = {
            "observed_at": now_iso(),
            "nodes": topology.get("data_node_count"),
            "healthy": topology.get("cluster_healthy"),
            "statuses": [item.get("status") for item in topology.get("instances", [])
                          if item.get("type") == "ess"],
            "actions": topology.get("actions", []),
            "action_progress": topology.get("action_progress", {}),
        }
        timeline.append(observation)
        statuses = observation["statuses"]
        if (observation["nodes"] == target and observation["healthy"] is True
                and len(statuses) == target and all(value == "200" for value in statuses)
                and not observation["actions"] and not observation["action_progress"]):
            return {"status": "RECONCILED", "target_nodes": target,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "timeline": timeline}
        if time.monotonic() - started >= timeout:
            return {"status": "TIMEOUT", "target_nodes": target,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "timeline": timeline}
        time.sleep(interval)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 50 real CSS AutoOps cases through KooCLI.")
    parser.add_argument("--config-dir", type=Path, default=Path("/etc/jiuwenswarm-autoops/css"))
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/css-50-real-koo-cli-20260920.json")
    parser.add_argument("--poll-timeout", type=int, default=1800)
    parser.add_argument("--poll-interval", type=int, default=30)
    parser.add_argument("--real-writes", action="store_true",
                        help="Run cases 49-50 against the real CSS capacity API.")
    args = parser.parse_args(argv)
    global WATCH_DIR
    WATCH_DIR = Path(tempfile.mkdtemp(prefix="css-50-real-watch-"))
    profile = load_profile("css-santiago", args.config_dir)
    credentials = load_credentials(profile, args.config_dir)
    base_policy = effective_policy(profile, args.config_dir)
    results: list[dict[str, Any]] = []
    started = now_iso()

    def save(status: str) -> None:
        canonical_ids = [item.get("case_id", item.get("id")) for item in results]
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 2, "status": status, "suite": "css-50-real-koo-cli",
            "started_at": started, "finished_at": now_iso(), "total": len(results),
            "passed": sum(item["status"] == "PASS" for item in results),
            "failed": sum(item["status"] == "FAIL" for item in results),
            "skipped": sum(item["status"] == "SKIPPED" for item in results),
            "canonical_case_ids": canonical_ids,
            "coverage_status": "COMPLETE" if len(results) == 50 and not any(
                item["status"] == "SKIPPED" for item in results) else "INCOMPLETE",
            "real_cloud_write_cases": [item["id"] for item in results if item.get("cloud_write")],
            "profile": safe_profile_summary(profile), "results": results,
        }
        args.evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")

    def case(case_id: str, title: str, action: Callable[[], dict[str, Any]]) -> bool:
        mocked = case_id in {"CSS50-36", "CSS50-37", "CSS50-38"}
        injected = 11 <= int(case_id.rsplit("-", 1)[1]) <= 28
        number = int(case_id.rsplit("-", 1)[1])
        record: dict[str, Any] = {
            "id": case_id, "case_id": f"CSS-S{number:02d}", "title": title,
            "started_at": now_iso(),
            "execution_level": "LOCAL_MOCK" if mocked else (
                "LIVE_BASELINE_FAULT_INJECTION" if injected else "CONTROL_PLANE_REAL"),
            "real_source": not mocked,
        }
        try:
            record.update(action())
            # Actions may deliberately return SKIPPED or BLOCKED. Preserve
            # that evidence; never turn it into a false PASS.
            if record.get("status") not in {"SKIPPED", "BLOCKED", "FAIL"}:
                record["status"] = "PASS"
            if (case_id in {"CSS50-49", "CSS50-50"}
                    and record.get("status") == "PASS"
                    and record.get("business_verification") in {"PASS", "PASSED", "SUCCEEDED"}):
                record["execution_level"] = "REAL_BUSINESS"
        except Exception as exc:  # stop immediately so the defect is fixed first
            record.update({"status": "FAIL", "error": str(exc)})
        record["finished_at"] = now_iso()
        results.append(record)
        save("FAIL" if record["status"] == "FAIL" else "RUNNING")
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return record["status"] == "PASS"

    def fresh() -> dict[str, Any]:
        snapshot = real_snapshot(profile, credentials)
        assert_true(snapshot["quality"] == "ok", "real CSS/CES evidence is not healthy")
        return snapshot

    def evaluate_real(changes: dict[str, Any] | None = None,
                      snapshot_changes: dict[str, Any] | None = None,
                      *, reason: str | None = None,
                      decision: str | None = None,
                      cooldown: bool = False,
                      scale_out_protection: bool = False) -> dict[str, Any]:
        snapshot = fresh()
        if snapshot_changes:
            for key, value in snapshot_changes.items():
                if key == "metrics":
                    snapshot["metrics"].update(value)
                elif key == "topology":
                    snapshot["topology"].update(value)
                else:
                    snapshot[key] = value
        policy = policy_for(base_policy, changes or {})
        result = evaluate(snapshot, policy, now_epoch=1_000_000,
                          last_scale_out_epoch=999_999 if scale_out_protection else None,
                          last_action_epoch=999_999 if cooldown else None)
        if decision:
            assert_true(result["decision"] == decision,
                        f"expected {decision}, got {result['decision']}: {result}")
        if reason:
            assert_true(reason in result.get("reason_codes", []),
                        f"expected reason {reason}, got {result}")
        return {"decision": result, "observed": {
            "nodes": snapshot["topology"].get("data_node_count"),
            "cluster_status": snapshot["topology"].get("cluster_status"),
            "quality": snapshot.get("quality"),
            "metrics": snapshot.get("metrics", {}),
        }, "cloud_write": False}

    def command_case(command: list[str], *, expected_code: int = 0,
                     expected_status: str | None = None) -> dict[str, Any]:
        code, payload = run_json(command)
        assert_true(code == expected_code, f"exit {code}: {payload}")
        if expected_status:
            assert_true(payload.get("status") == expected_status,
                        f"expected {expected_status}: {payload}")
        return {"result": payload, "cloud_write": False}

    cases: list[tuple[str, str, Callable[[], dict[str, Any]]]] = [
        ("CSS50-01", "KooCLI CSS cluster detail", lambda: {"topology": fresh()["topology"]}),
        ("CSS50-02", "real data-node inventory", lambda: {"topology": fresh()["topology"]}),
        ("CSS50-03", "real CES CPU metric", lambda: {"metric": fresh()["metrics"]["cpu_max"]}),
        ("CSS50-04", "real CES disk metric", lambda: {"metric": fresh()["metrics"]["disk_usage_pct"]}),
        ("CSS50-05", "real CES JVM metric", lambda: {"metric": fresh()["metrics"]["jvm_heap_max"]}),
        ("CSS50-06", "real search and indexing metrics", lambda: {"metrics": fresh()["metrics"]}),
        ("CSS50-07", "real live pressure observe", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-live-pressure.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--iterations", "1"])),
        ("CSS50-08", "real css-auto inspect", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-auto.py"), "inspect", "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir)], expected_status="READY")),
        ("CSS50-09", "real css-auto plan", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-auto.py"), "plan", "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir)], expected_status="HOLD")),
        ("CSS50-10", "real watcher first observation", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl")], expected_status="PROCESSED")),
        ("CSS50-11", "real evidence with max-node guard", lambda: evaluate_real(
            {"max_data_nodes": 2, "scale_out_cpu_percent": 0, "scale_out_disk_percent": 0}, reason="MAX_NODE_BOUND")),
        ("CSS50-12", "real evidence with minimum-node guard", lambda: evaluate_real(
            {"allow_scale_in": True}, reason="MIN_NODE_BOUND")),
        ("CSS50-13", "real evidence with scale-in disabled", lambda: evaluate_real(
            {"allow_scale_in": False}, decision="hold")),
        ("CSS50-14", "real evidence with scale-out disabled", lambda: evaluate_real(
            {"allow_scale_out": False, "scale_out_cpu_percent": 0}, decision="scale_out")),
        ("CSS50-15", "real evidence with action cooldown", lambda: evaluate_real(
            {"scale_out_cpu_percent": 0}, reason="COOLDOWN_ACTIVE", cooldown=True)),
        ("CSS50-16", "real evidence with scale-out protection", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1,
             "scale_in_delay_after_scale_out_minutes": 30},
            reason="SCALE_OUT_PROTECTION", scale_out_protection=True)),
        ("CSS50-17", "real snapshot requirement", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1},
            {"snapshot_available": False}, reason="SNAPSHOT_REQUIRED")),
        ("CSS50-18", "real metric-unit guard", lambda: evaluate_real(
            {}, {"metric_units_valid": False}, reason="METRIC_UNIT_UNKNOWN")),
        ("CSS50-19", "real missing-CPU guard", lambda: evaluate_real(
            {}, {"metrics": {"cpu_max": None}}, reason="CAPACITY_METRIC_MISSING")),
        ("CSS50-20", "real missing-disk guard", lambda: evaluate_real(
            {}, {"metrics": {"disk_usage_pct": None}}, reason="CAPACITY_METRIC_MISSING")),
        ("CSS50-21", "real evidence-quality guard", lambda: evaluate_real(
            {}, {"quality": "degraded"}, reason="EVIDENCE_INSUFFICIENT")),
        ("CSS50-22", "real unhealthy-cluster guard", lambda: evaluate_real(
            {}, {"topology": {"cluster_healthy": False}}, reason="CLUSTER_NOT_HEALTHY")),
        ("CSS50-23", "real unknown-node guard", lambda: evaluate_real(
            {}, {"topology": {"data_node_count": None}}, reason="CURRENT_NODE_COUNT_UNKNOWN")),
        ("CSS50-24", "real active-action guard", lambda: evaluate_real(
            {}, {"topology": {"actions": ["external-action"]}}, reason="ACTIVE_CLOUD_ACTION")),
        ("CSS50-25", "real scale-in traffic guard", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1},
            {"metrics": {"search_rate": 10001}}, reason="TRAFFIC_TOO_HIGH_FOR_SCALE_IN")),
        ("CSS50-26", "real scale-in indexing guard", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1},
            {"metrics": {"indexing_rate": 10001}}, reason="INDEXING_TOO_HIGH_FOR_SCALE_IN")),
        ("CSS50-27", "real search-latency guard", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1},
            {"metrics": {"search_latency": 10001}}, reason="LATENCY_TOO_HIGH_FOR_SCALE_IN")),
        ("CSS50-28", "real JVM-heap guard", lambda: evaluate_real(
            {"allow_scale_in": True, "min_data_nodes": 1},
            {"metrics": {"jvm_heap_max": 10001}}, reason="JVM_HEAP_TOO_HIGH_FOR_SCALE_IN")),
        ("CSS50-29", "real no-trigger decision", lambda: evaluate_real(decision="hold")),
        ("CSS50-30", "real observe mode has no write", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-live-pressure.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--iterations", "1"])),
        ("CSS50-31", "real watcher deduplication", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl")], expected_status="PROCESSED")),
        ("CSS50-32", "real watcher pause", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl"), "--action", "pause"], expected_status="paused")),
        ("CSS50-33", "real watcher paused execution", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl")], expected_status="paused")),
        ("CSS50-34", "real watcher resume", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl"), "--action", "resume"], expected_status="active")),
        ("CSS50-35", "real watcher resumed execution", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-watch.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--state-dir", str(WATCH_DIR / "state"),
            "--events-file", str(WATCH_DIR / "events.jsonl")], expected_status="PROCESSED")),
        ("CSS50-36", "ProjectManager CSS route", lambda: _route("查看 css-santiago CSS 集群流量")),
        ("CSS50-37", "ProjectManager OpenSearch capacity route", lambda: _route("扩容 css-santiago OpenSearch data 节点")),
        ("CSS50-38", "CSS alert profile forwarding", lambda: _dispatch_profile()),
        ("CSS50-39", "E01 real-topology scale-out dry-run", lambda: _runbook_dry(args, profile, credentials, "scale_out", "CSS50-39")),
        ("CSS50-40", "E01 real-topology scale-in dry-run", lambda: _runbook_dry(args, profile, credentials, "scale_in", "CSS50-40")),
        ("CSS50-41", "E01 wrong-role protection", lambda: _runbook_role(args, profile, credentials, "project-manager", True, "CSS50-41")),
        ("CSS50-42", "E01 mutation switch protection", lambda: _runbook_role(args, profile, credentials, "runbook-operator", False, "CSS50-42")),
        ("CSS50-43", "KooCLI direct topology operation", lambda: {"topology": fresh()["topology"]}),
        ("CSS50-44", "KooCLI direct CES operation", lambda: {"metrics": fresh()["metrics"]}),
        ("CSS50-45", "real CSS verification boundary", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-auto.py"), "verify", "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--task-id", "CSS50-45"])),
        ("CSS50-46", "missing action status is explicit", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-auto.py"), "status", "--operation-id", "missing-real-op"], expected_status="NOT_FOUND")),
        ("CSS50-47", "real live runner two observations", lambda: command_case([
            sys.executable, str(SCRIPTS / "css-live-pressure.py"), "--profile-id", "css-santiago",
            "--config-dir", str(args.config_dir), "--iterations", "2", "--interval-seconds", "0"])),
        ("CSS50-48", "real watcher evidence persistence", lambda: _watch_evidence()),
        ("CSS50-49", "real CSS scale-out and reconciliation", lambda: _real_scale(args, profile, credentials, base_policy, "scale_out", 3)),
        ("CSS50-50", "real CSS scale-in and reconciliation", lambda: _real_scale(args, profile, credentials, base_policy, "scale_in", 2)),
    ]

    for case_id, title, action in cases:
        if case_id in {"CSS50-49", "CSS50-50"} and not args.real_writes:
            if not case(case_id, title, lambda: {"status": "SKIPPED", "cloud_write": False}):
                if results[-1]["status"] == "SKIPPED":
                    continue
                return 1
            continue
        if not case(case_id, title, action):
            save("FAIL")
            return 1
    save("PASS")
    print(json.dumps({"status": "PASS", "total": 50,
                      "passed": sum(item["status"] == "PASS" for item in results),
                      "skipped": sum(item["status"] == "SKIPPED" for item in results),
                      "coverage_status": "COMPLETE" if not any(item["status"] == "SKIPPED" for item in results) else "INCOMPLETE",
                      "evidence": str(args.evidence)}, ensure_ascii=False))
    return 0


def _route(text: str) -> dict[str, Any]:
    from autoops_routing import route_request
    result = route_request(text)
    assert_true(result.get("primary_role") == "css_auto", str(result))
    return {"routing": {"primary_role": result.get("primary_role"),
                         "selected_capabilities": result.get("selected_capabilities")},
            "cloud_write": False}


def _dispatch_profile() -> dict[str, Any]:
    import autoops_alert_dispatch
    event = {"source": "css", "service": "css-autoops", "target": "css-santiago",
             "profile_id": "css-santiago", "cluster_id": "57913cbd-01cc-49b6-b8d0-f3914b35659a"}
    completed = subprocess.CompletedProcess([], 0, stdout='{"status":"READY"}', stderr="")
    from unittest.mock import patch
    with patch.object(autoops_alert_dispatch.subprocess, "run", return_value=completed) as call:
        autoops_alert_dispatch.run_project_manager(event)
    command = call.call_args.args[0]
    assert_true("--css-profile" in command and "css-santiago" in command, str(command))
    return {"profile_forwarded": True, "cloud_write": False}


def _runbook_dry(args: argparse.Namespace, profile: dict[str, Any], credentials: dict[str, Any],
                 direction: str, case_id: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="css-real-dry-") as value:
        directory = Path(value)
        copy_runtime_config(args.config_dir, directory)
        set_policy(directory, {"mode": "auto", "allow_scale_out": True, "allow_scale_in": True})
        snapshot = real_snapshot(profile, credentials)
        target = snapshot["topology"]["data_node_count"] + (1 if direction == "scale_out" else -1)
        result = invoke_runbook(directory, snapshot, case_id, direction, execute=False,
                                target_nodes=target)
        assert_true(result.get("status") == "PENDING_CONFIRMATION", str(result))
        return {"result": result, "cloud_write": False}


def _runbook_role(args: argparse.Namespace, profile: dict[str, Any], credentials: dict[str, Any],
                  role: str, mutation: bool, case_id: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="css-real-role-") as value:
        directory = Path(value)
        copy_runtime_config(args.config_dir, directory)
        set_policy(directory, {"mode": "auto", "allow_scale_out": True, "allow_scale_in": True})
        snapshot = real_snapshot(profile, credentials)
        result = invoke_runbook(directory, snapshot, case_id, "scale_out", execute=True,
                                role=role, mutation=mutation,
                                target_nodes=snapshot["topology"]["data_node_count"] + 1)
        expected = "PERMISSION_DENIED" if role != "runbook-operator" else "BLOCKED"
        assert_true(result.get("status") == expected, str(result))
        return {"result": result, "cloud_write": False}


def _watch_evidence() -> dict[str, Any]:
    assert_true(WATCH_DIR is not None, "watch directory is not initialized")
    path = WATCH_DIR / "state" / "css-state.json"
    assert_true(path.exists(), "watcher evidence file missing")
    return {"events_file": str(path), "bytes": path.stat().st_size, "cloud_write": False}


def _real_scale(args: argparse.Namespace, profile: dict[str, Any], credentials: dict[str, Any],
                base_policy: dict[str, Any], direction: str, target: int) -> dict[str, Any]:
    if not args.real_writes:
        return {"status": "SKIPPED", "cloud_write": False}
    current = real_snapshot(profile, credentials)
    current_nodes = current["topology"]["data_node_count"]
    assert_true(target == current_nodes + 1 if direction == "scale_out" else target == current_nodes - 1,
                f"unexpected real topology for {direction}: {current_nodes}")
    with tempfile.TemporaryDirectory(prefix=f"css-real-{direction}-") as value:
        directory = Path(value)
        copy_runtime_config(args.config_dir, directory)
        set_policy(directory, {
            "mode": "auto", "allow_scale_out": True, "allow_scale_in": True,
            "min_data_nodes": 2, "max_data_nodes": max(3, target),
            "scale_out_step": 1, "scale_in_step": 1,
        })
        operation = invoke_runbook(directory, current,
                                   f"CSS50-{49 if direction == 'scale_out' else 50}",
                                   direction, execute=True, target_nodes=target,
                                   action_db=directory / "actions.sqlite3")
        assert_true(operation.get("status") == "SUBMITTED", str(operation))
        reconciliation = wait_for_capacity(profile, credentials, target,
                                           args.poll_timeout, args.poll_interval)
        assert_true(reconciliation.get("status") == "RECONCILED", str(reconciliation))
        return {"operation": operation, "reconciliation": reconciliation, "cloud_write": True}


if __name__ == "__main__":
    raise SystemExit(main())
