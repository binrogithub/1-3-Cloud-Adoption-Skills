#!/usr/bin/env python3
"""Observe real CSS/CES pressure and optionally submit one real scale action.

This is a project-owned glue entry. It reads Huawei Cloud CSS topology and CES
metrics, evaluates the registered policy, and delegates the only mutation to
the fixed E01 ``css-scale-runbook.py`` adapter. Without ``--execute`` it never
calls a CSS write API. It does not generate synthetic business traffic.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from css_cloud import CssCloudError, ces_metric_samples, ces_metrics, cluster_snapshot
from css_capability import validate_plan
from css_config import effective_policy, load_credentials, load_profile, safe_profile_summary
from css_metrics import normalize_snapshot
from css_policy import evaluate
from css_collector import SnapshotCache, collect_snapshot
from css_reconcile import reconcile_action
from css_action_ledger import open_action_db, transition_status
from css_business_verification import evaluate_probe_window


ROOT = Path(__file__).resolve().parents[1]


def action_db_path(state_dir: Path) -> Path:
    """Use the shared runtime action ledger when the service config sets one."""
    return Path(os.environ.get("AUTOOPS_CSS_ACTION_DB") or (state_dir / "css-actions.sqlite3"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_error(error: Exception, credentials: dict[str, Any]) -> str:
    value = str(error)
    for key in ("access_key_id", "secret_access_key"):
        secret = credentials.get(key)
        if isinstance(secret, str) and secret:
            value = value.replace(secret, "<redacted>")
    return value


LIVE_CACHE = SnapshotCache(ttl_seconds=30)


def live_snapshot(profile: dict[str, Any], credentials: dict[str, Any], *, fresh: bool = False) -> dict[str, Any]:
    raw = collect_snapshot(profile, credentials, cluster_snapshot, ces_metric_samples,
                           cache=LIVE_CACHE, fresh=fresh)
    return normalize_snapshot(raw, source=raw["source"], window_minutes=10)


def probe_headers(path_value: str | None) -> dict[str, str]:
    if not path_value:
        return {}
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"probe headers file must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in value.items()):
        raise ValueError("probe headers file must contain string keys and values")
    return value


def load_business_config(path_value: str | None) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"business config must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("business config must be a JSON object")
    for field in ("headers_file", "body_file"):
        if value.get(field):
            candidate = Path(str(value[field]))
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            value[field] = str(candidate)
    if not str(value.get("probe_url", "")).startswith(("http://", "https://")):
        raise ValueError("business config requires an HTTP(S) probe_url")
    if not isinstance(value.get("expected_json"), dict) or not value["expected_json"]:
        raise ValueError("business config requires non-empty expected_json assertions")
    if str(value.get("method", "GET")).upper() not in {"GET", "POST"}:
        raise ValueError("business config method must be GET or POST")
    for key in ("minimum_samples", "stable_business_minutes", "sample_interval_seconds"):
        if int(value.get(key, 0)) < 1:
            raise ValueError(f"business config requires positive {key}")
    return value


def _json_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def probe(url: str | None, timeout: float, headers: dict[str, str] | None = None,
          tls_verify: bool = True, business_config: dict[str, Any] | None = None) -> dict[str, Any]:
    target = (business_config or {}).get("probe_url") or url
    if not target:
        return {"status": "UNVERIFIED", "reason_code": "BUSINESS_PROBE_NOT_CONFIGURED"}
    started = time.perf_counter()
    method = str((business_config or {}).get("method", "GET")).upper()
    body = None
    body_file = (business_config or {}).get("body_file")
    if body_file:
        path = Path(body_file)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"business probe body must be a regular file: {path}")
        body = path.read_bytes()
    request = urllib.request.Request(target, data=body if method == "POST" else None,
                                     headers=headers or {}, method=method)
    try:
        context = None if tls_verify else ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            assertions = (business_config or {}).get("expected_json")
            if not assertions:
                return {"status": "UNVERIFIED", "reason_code": "BUSINESS_SEMANTIC_ASSERTION_REQUIRED",
                        "http_status": response.status, "latency_ms": latency_ms}
            try:
                payload = json.loads(response.read(1024 * 1024).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            status_ok = response.status == int((business_config or {}).get("expected_status", 200))
            content_ok = isinstance(payload, dict) and all(
                _json_path(payload, str(key)) == expected for key, expected in assertions.items()
            )
            latency_ok = latency_ms <= float((business_config or {}).get("max_p95_latency_ms", float("inf")))
            passed = status_ok and content_ok and latency_ok
            return {"status": "PASSED" if passed else "FAILED",
                    "reason_code": None if passed else "BUSINESS_ASSERTION_FAILED",
                    "http_status": response.status, "content_assertions_passed": content_ok,
                    "latency_ms": latency_ms}
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {"status": "FAILED", "reason_code": "BUSINESS_PROBE_FAILED",
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def business_sample(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    headers_path = config.get("headers_file") or args.probe_headers_file
    headers = probe_headers(str(headers_path) if headers_path else None)
    sample = probe(config.get("probe_url"), float(config.get("timeout_seconds", args.probe_timeout)),
                   headers, bool(config.get("tls_verify", args.probe_tls_verify)), config)
    sample["observed_epoch"] = time.time()
    return sample


def collect_business_precheck(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    required_samples = int(config["minimum_samples"])
    required_span = int(config["stable_business_minutes"]) * 60
    interval = int(config["sample_interval_seconds"])
    deadline = time.monotonic() + required_span + interval * required_samples
    while True:
        samples.append(business_sample(args, config))
        result = evaluate_probe_window(samples, config)
        if result["status"] in {"PASSED", "DEGRADED"}:
            return {**result, "samples": samples}
        if time.monotonic() >= deadline:
            return {**result, "status": "UNVERIFIED", "samples": samples}
        time.sleep(interval)


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink evidence path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def invoke_runbook(args: argparse.Namespace, profile: dict[str, Any], action: dict[str, Any],
                   topology: dict[str, Any], operation_id: str,
                   business_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    args.state_dir.mkdir(parents=True, exist_ok=True)
    topology_path = args.state_dir / f"{operation_id}.topology.json"
    write_json(topology_path, topology)
    os.chmod(topology_path, 0o600)
    business_path = None
    if business_evidence is not None:
        business_path = args.state_dir / f"{operation_id}.business.json"
        write_json(business_path, business_evidence)
        os.chmod(business_path, 0o600)
    command = [sys.executable, str(ROOT / "scripts" / "css-scale-runbook.py"),
               "--task-id", operation_id, "--idempotency-key", operation_id,
               "--profile-id", args.profile_id, "--direction", action["decision"],
               "--delta", str(action["delta"]), "--target-nodes", str(action["target_nodes"]),
               "--topology-file", str(topology_path)]
    if business_path:
        command.extend(("--business-evidence-file", str(business_path)))
    if args.config_dir:
        command.extend(("--config-dir", str(args.config_dir)))
    environment = os.environ.copy()
    environment.setdefault("AUTOOPS_CSS_ACTION_DB", str(action_db_path(args.state_dir)))
    if args.execute:
        command.append("--execute")
        environment["AUTOOPS_AUTHENTICATED_ROLE"] = "runbook-operator"
        environment["AUTOOPS_CSS_MUTATION_ENABLED"] = "1"
    completed = subprocess.run(command, text=True, capture_output=True,
                               env=environment, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"status": "RUNBOOK_INVALID_OUTPUT", "exit_code": completed.returncode}
    if completed.returncode and payload.get("status") not in {"SUBMITTED", "RECONCILING", "BLOCKED"}:
        payload.setdefault("exit_code", completed.returncode)
    return payload


def persist_reconciliation(args: argparse.Namespace, operation_id: str,
                           target_status: str) -> dict[str, Any]:
    """Persist the live reconciliation before another action is admitted."""
    database = action_db_path(args.state_dir)
    connection = open_action_db(database)
    try:
        row = connection.execute(
            "SELECT status FROM css_actions WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"CSS action is missing from ledger: {operation_id}")
        current = str(row["status"])
        target = transition_status(current, target_status)
        timestamp = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "UPDATE css_actions SET status=?, reconciled_at=?, updated_at=? "
            "WHERE operation_id=?",
            (target, timestamp, timestamp, operation_id),
        )
        return {"status": "PERSISTED", "previous": current, "current": target}
    finally:
        connection.close()


def explicit_target_decision(snapshot: dict[str, Any], policy: dict[str, Any],
                             target_nodes: int, *, max_scale_in_step: int = 1,
                             business_verified: bool = False) -> dict[str, Any]:
    """Build a controlled wave target while retaining all provider guards."""
    topology = snapshot.get("topology", {})
    current = topology.get("data_node_count")
    if snapshot.get("quality") != "ok" or topology.get("cluster_healthy") is not True:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["EVIDENCE_INSUFFICIENT"], "delta": 0,
                "current_nodes": current, "target_nodes": target_nodes}
    if not isinstance(current, int) or current < 1:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["CURRENT_NODE_COUNT_UNKNOWN"], "delta": 0,
                "target_nodes": target_nodes}
    if current == target_nodes:
        return {"decision": "hold", "status": "AT_WAVE_TARGET",
                "reason_codes": ["WAVE_TARGET_REACHED"], "delta": 0,
                "current_nodes": current, "target_nodes": target_nodes}
    direction = "scale_out" if target_nodes > current else "scale_in"
    if direction == "scale_in" and not business_verified:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["BUSINESS_VERIFICATION_REQUIRED_FOR_SCALE_IN"],
                "delta": 0, "current_nodes": current, "target_nodes": target_nodes}
    requested_delta = abs(target_nodes - current)
    step_key = "scale_out_step" if direction == "scale_out" else "scale_in_step"
    policy_step = int(policy.get(step_key, requested_delta))
    if direction == "scale_in":
        policy_step = min(policy_step, max_scale_in_step)
    delta = min(requested_delta, policy_step)
    effective_target = current + delta if direction == "scale_out" else current - delta
    reasons = validate_plan(topology, policy, direction, delta, target_nodes=effective_target)
    if reasons:
        return {"decision": "hold", "status": "BLOCKED", "reason_codes": reasons,
                "delta": 0, "current_nodes": current, "target_nodes": target_nodes}
    allowed = policy.get("allow_scale_out" if direction == "scale_out" else "allow_scale_in", False)
    return {"decision": direction, "status": "PLANNED" if allowed else "RECOMMENDATION",
            "reason_codes": ["WAVE_TARGET_PRESSURE"], "current_nodes": current,
            "target_nodes": effective_target, "wave_target_nodes": target_nodes,
            "delta": delta}


def reconcile_until_settled(args: argparse.Namespace, profile: dict[str, Any],
                            credentials: dict[str, Any], action: dict[str, Any],
                            operation_id: str) -> dict[str, Any]:
    started = time.time()
    timeline = []
    business_config = load_business_config(args.business_config)
    business_samples: list[dict[str, Any]] = []
    while True:
        snapshot = live_snapshot(profile, credentials, fresh=True)
        if business_config:
            sample = business_sample(args, business_config)
            business_samples.append(sample)
            verification = evaluate_probe_window(business_samples, business_config)
        else:
            sample = probe(args.probe_url, args.probe_timeout,
                           probe_headers(args.probe_headers_file), args.probe_tls_verify)
            verification = {"status": "UNVERIFIED",
                             "reason_codes": [sample.get("reason_code", "BUSINESS_PROBE_NOT_CONFIGURED")]}
        result = reconcile_action(
            {"target_nodes": action["target_nodes"]}, snapshot["topology"], verification
        )
        timeline.append({"recorded_at": now_iso(), "reconciliation": result,
                         "verification": verification, "business_probe": sample,
                         "current_nodes": snapshot["topology"].get("data_node_count")})
        terminal = {"SUCCEEDED", "DEGRADED", "FAILED", "BLOCKED", "UNKNOWN"}
        if result["status"] in terminal or (result["status"] == "CAPACITY_READY" and not business_config):
            return {"status": result["status"], "timeline": timeline,
                    "elapsed_seconds": round(time.time() - started, 2),
                    "ledger": persist_reconciliation(args, operation_id, result["status"])}
        if time.time() - started >= args.reconcile_timeout:
            final_status = "CAPACITY_READY" if result["status"] == "CAPACITY_READY" else "UNKNOWN"
            persisted = persist_reconciliation(args, operation_id, final_status)
            return {"status": final_status, "reason_code": "BUSINESS_WINDOW_TIMEOUT" if final_status == "CAPACITY_READY" else "RECONCILIATION_TIMEOUT",
                    "timeline": timeline, "elapsed_seconds": round(time.time() - started, 2),
                    "ledger": persisted}
        interval = (int(business_config.get("sample_interval_seconds", args.reconcile_interval))
                    if business_config else args.reconcile_interval)
        time.sleep(interval)


def reconcile_persisted_operation(args: argparse.Namespace, profile: dict[str, Any],
                                 credentials: dict[str, Any], operation_id: str) -> dict[str, Any]:
    """Resume read-only reconciliation for one ledgered operation after restart."""
    database = action_db_path(args.state_dir)
    connection = open_action_db(database)
    try:
        row = connection.execute(
            "SELECT operation_id,target_nodes,status FROM css_actions WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError(f"CSS action is missing from ledger: {operation_id}")
    if str(row["status"]) in {"SUCCEEDED", "BLOCKED", "FAILED", "CANCELLED"}:
        return {"status": str(row["status"]), "operation_id": operation_id,
                "message": "Operation is already terminal; no cloud write was attempted."}
    result = reconcile_until_settled(
        args, profile, credentials, {"target_nodes": row["target_nodes"]}, operation_id
    )
    return {"operation_id": operation_id, "cloud_writes": False, **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read real CSS pressure and optionally scale through E01.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(".runtime/css-live-pressure"))
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--execute", action="store_true",
                        help="Allow the fixed E01 Runbook to submit a real CSS change.")
    parser.add_argument("--max-actions", type=int, default=1)
    parser.add_argument("--reconcile-timeout", type=int, default=1800)
    parser.add_argument("--reconcile-interval", type=int, default=30)
    parser.add_argument("--probe-url", help="Optional read-only business HTTP probe URL.")
    parser.add_argument("--probe-headers-file", help="Optional JSON headers for the business probe.")
    parser.add_argument("--business-config", help="Registered business probe assertions and stability SLOs.")
    parser.add_argument("--probe-tls-verify", action=argparse.BooleanOptionalAction, default=True,
                        help="Verify the business probe TLS certificate (default: true).")
    parser.add_argument("--probe-timeout", type=float, default=10)
    parser.add_argument("--target-nodes", type=int,
                        help="Controlled wave target; provider policy and Runbook guards still apply.")
    parser.add_argument("--max-scale-in-step", type=int, default=1,
                        help="Wave shrink step ceiling; defaults to one data node per action.")
    parser.add_argument("--reconcile-operation-id",
                        help="Resume read-only reconciliation of one existing ledger action.")
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.iterations > 1440:
        parser.error("--iterations must be 1..1440")
    if args.interval_seconds < 0 or args.reconcile_interval < 1 or args.reconcile_timeout < 1:
        parser.error("interval and timeout values are invalid")
    if args.max_actions < 0 or args.max_actions > 10:
        parser.error("--max-actions must be 0..10")
    if args.target_nodes is not None and not 1 <= args.target_nodes <= 100:
        parser.error("--target-nodes must be 1..100")
    if not 1 <= args.max_scale_in_step <= 10:
        parser.error("--max-scale-in-step must be 1..10")
    try:
        profile = load_profile(args.profile_id, args.config_dir)
        credentials = load_credentials(profile, args.config_dir)
        policy = effective_policy(profile, args.config_dir)
        business_config = load_business_config(args.business_config)
        if args.reconcile_operation_id:
            result = reconcile_persisted_operation(
                args, profile, credentials, args.reconcile_operation_id
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("status") in {"SUCCEEDED", "CAPACITY_READY", "DEGRADED"} else 1
        records: list[dict[str, Any]] = []
        submitted = 0
        for index in range(args.iterations):
            snapshot = live_snapshot(profile, credentials)
            business_precheck = None
            current_nodes = snapshot.get("topology", {}).get("data_node_count")
            is_scale_in = (args.target_nodes is not None and isinstance(current_nodes, int)
                           and args.target_nodes < current_nodes)
            if args.target_nodes is None:
                decision = evaluate(snapshot, policy)
                is_scale_in = decision.get("decision") == "scale_in"
            if is_scale_in:
                business_precheck = (collect_business_precheck(args, business_config)
                                     if business_config else {"status": "UNVERIFIED",
                                                              "reason_codes": ["BUSINESS_VERIFICATION_REQUIRED_FOR_SCALE_IN"]})
            business_verified = bool(business_precheck and business_precheck.get("status") == "PASSED")
            if args.target_nodes is not None:
                decision = explicit_target_decision(
                    snapshot, policy, args.target_nodes,
                    max_scale_in_step=min(args.max_scale_in_step,
                                          int((business_config or {}).get("max_scale_in_step", 1))),
                    business_verified=business_verified,
                )
            elif is_scale_in and not business_verified:
                decision = {"decision": "hold", "status": "BLOCKED",
                            "reason_codes": (business_precheck or {}).get("reason_codes", ["BUSINESS_VERIFICATION_REQUIRED_FOR_SCALE_IN"]),
                            "delta": 0, "current_nodes": current_nodes}
            record: dict[str, Any] = {
                "iteration": index + 1, "recorded_at": now_iso(),
                "snapshot": snapshot, "decision": decision,
                "execution": "observe_only",
            }
            if business_precheck is not None:
                record["business_precheck"] = {k: v for k, v in business_precheck.items() if k != "samples"}
            should_act = decision.get("decision") in {"scale_out", "scale_in"}
            if should_act and args.execute and submitted < args.max_actions:
                operation_id = f"css-live-{int(time.time())}-{uuid.uuid4().hex[:10]}"
                runbook = invoke_runbook(args, profile, decision,
                                         snapshot["topology"], operation_id,
                                         business_precheck if decision.get("decision") == "scale_in" else None)
                record["execution"] = "real_e01_runbook"
                record["operation_id"] = operation_id
                record["runbook"] = runbook
                submitted += int(runbook.get("status") == "SUBMITTED")
                if runbook.get("status") == "SUBMITTED":
                    record["reconciliation"] = reconcile_until_settled(
                        args, profile, credentials,
                        {"target_nodes": decision["target_nodes"]},
                        operation_id,
                    )
            records.append(record)
            if index + 1 < args.iterations and args.interval_seconds:
                time.sleep(args.interval_seconds)
        result = {
            "schema_version": 2, "status": "COMPLETED", "mode": "real_css_read_with_e01_boundary",
            "profile": safe_profile_summary(profile), "iterations": len(records),
            "submitted_actions": submitted, "records": records,
            "secrets_included": False,
            "real_write_enabled": bool(args.execute),
        }
        result["verification_summary"] = {
            "capacity_ready": sum(1 for row in records if row.get("reconciliation", {}).get("status") == "CAPACITY_READY"),
            "business_succeeded": sum(1 for row in records if row.get("reconciliation", {}).get("status") == "SUCCEEDED"),
            "business_unverified": sum(1 for row in records if row.get("reconciliation", {}).get("status") in {"CAPACITY_READY", "UNVERIFIED"}),
        }
        if args.evidence:
            write_json(args.evidence, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except CssCloudError as exc:
        payload = {"schema_version": 1, "status": "UNAVAILABLE",
                   "error_code": "CSS_DATASOURCE_UNAVAILABLE",
                   "error": safe_error(exc, locals().get("credentials", {})),
                   "secrets_included": False}
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc),
                          "secrets_included": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
