#!/usr/bin/env python3
"""Inspect one published Kubernetes workload using read-only kubectl calls."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("AUTOOPS_KUBERNETES_WORKLOADS_FILE",
                            str(ROOT / "config" / "kubernetes" / "workloads.json")))


def emit(payload: dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def load_workload(cluster_name: str, workload_id: str, namespace: str | None) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cluster = config["clusters"][cluster_name]
        workload = cluster["workloads"][workload_id]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None, "PUBLISHED_WORKLOAD_NOT_FOUND"
    if cluster.get("enabled") is not True:
        return None, "CLUSTER_NOT_ENABLED"
    if workload.get("kind") != "Deployment" or not workload.get("name") or not workload.get("selector"):
        return None, "PUBLISHED_WORKLOAD_INVALID"
    if namespace and namespace != workload.get("namespace"):
        return None, "NAMESPACE_NOT_PUBLISHED"
    return {"cluster": cluster, "workload": workload}, None


def kubectl_path() -> str | None:
    configured = os.environ.get("AUTOOPS_KUBECTL")
    if configured:
        return configured if os.path.isfile(configured) and os.access(configured, os.X_OK) else None
    project_binary = Path("/opt/JiuwenSwarm/bin/kubectl")
    if project_binary.is_file() and os.access(project_binary, os.X_OK):
        return str(project_binary)
    return shutil.which("kubectl")


def run_kubectl(binary: str, base_args: list[str], cluster: dict[str, Any]) -> tuple[int, Any, str]:
    command = [binary]
    context = cluster.get("context")
    if context:
        command.extend(["--context", str(context)])
    command.extend(base_args)
    env = os.environ.copy()
    kubeconfig_env = cluster.get("kubeconfig_env")
    if kubeconfig_env and env.get(kubeconfig_env):
        env["KUBECONFIG"] = env[kubeconfig_env]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, None, str(exc)
    if completed.returncode != 0:
        return completed.returncode, None, completed.stderr.strip()[-1000:] or "kubectl returned non-zero"
    try:
        return 0, json.loads(completed.stdout), ""
    except json.JSONDecodeError:
        return 1, None, "kubectl returned invalid JSON"


def deployment_summary(payload: dict[str, Any]) -> dict[str, Any]:
    spec = payload.get("spec", {})
    status = payload.get("status", {})
    return {
        "name": payload.get("metadata", {}).get("name"),
        "namespace": payload.get("metadata", {}).get("namespace"),
        "generation": payload.get("metadata", {}).get("generation"),
        "observed_generation": status.get("observedGeneration"),
        "desired_replicas": spec.get("replicas", 0),
        "ready_replicas": status.get("readyReplicas", 0),
        "updated_replicas": status.get("updatedReplicas", 0),
        "available_replicas": status.get("availableReplicas", 0),
    }


def pod_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in payload.get("items", []):
        status = item.get("status", {})
        conditions = {condition.get("type"): condition.get("status")
                      for condition in status.get("conditions", [])
                      if isinstance(condition, dict)}
        result.append({
            "name": item.get("metadata", {}).get("name"),
            "phase": status.get("phase"),
            "ready": conditions.get("Ready") == "True",
            "restart_count": sum(container.get("restartCount", 0)
                                  for container in status.get("containerStatuses", [])
                                  if isinstance(container, dict)),
        })
    return result


def event_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "type": item.get("type"),
        "reason": item.get("reason"),
        "message": item.get("message"),
        "last_timestamp": item.get("eventTime") or item.get("lastTimestamp") or item.get("metadata", {}).get("creationTimestamp"),
    } for item in payload.get("items", []) if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a published Kubernetes workload.")
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--workload", required=True, help="Published workload id, for example staging/orders/order-api")
    parser.add_argument("--namespace")
    args = parser.parse_args(argv)
    published, error_code = load_workload(args.cluster, args.workload, args.namespace)
    if error_code:
        return emit({"source": "kubernetes", "status": "unavailable" if error_code == "CLUSTER_NOT_ENABLED" else "invalid",
                     "error_code": error_code, "cluster": args.cluster, "workload": args.workload}, 1 if error_code == "CLUSTER_NOT_ENABLED" else 2)
    binary = kubectl_path()
    if not binary:
        return emit({"source": "kubernetes", "status": "unavailable", "error_code": "KUBECTL_NOT_AVAILABLE"}, 1)
    cluster = published["cluster"]
    workload = published["workload"]
    namespace = workload["namespace"]
    name = workload["name"]
    code, deployment, error = run_kubectl(binary, ["get", "deployment", name, "--namespace", namespace, "--output", "json"], cluster)
    if code or not isinstance(deployment, dict):
        return emit({"source": "kubernetes", "status": "unavailable", "error_code": "KUBERNETES_API_ERROR",
                     "error": error, "cluster": args.cluster, "namespace": namespace, "workload": args.workload}, 1)
    calls = [
        ("pods", ["get", "pods", "--namespace", namespace, "--selector", workload["selector"], "--output", "json"]),
        ("events", ["get", "events", "--namespace", namespace, "--field-selector", f"involvedObject.kind=Deployment,involvedObject.name={name}", "--output", "json"]),
        ("hpa", ["get", "hpa", "--namespace", namespace, "--output", "json"]),
    ]
    responses: dict[str, Any] = {}
    for label, command in calls:
        call_code, response, call_error = run_kubectl(binary, command, cluster)
        if call_code or not isinstance(response, dict):
            return emit({"source": "kubernetes", "status": "unavailable", "error_code": "KUBERNETES_API_ERROR",
                         "error": call_error, "failed_call": label, "cluster": args.cluster,
                         "namespace": namespace, "workload": args.workload}, 1)
        responses[label] = response
    hpa_conflicts = [item for item in responses["hpa"].get("items", [])
                     if item.get("spec", {}).get("scaleTargetRef", {}).get("kind") == "Deployment"
                     and item.get("spec", {}).get("scaleTargetRef", {}).get("name") == name]
    return emit({
        "schema_version": 1,
        "source": "kubernetes",
        "status": "ok",
        "capability": "k8s.inspect.v1",
        "cluster": args.cluster,
        "context": cluster.get("context"),
        "namespace": namespace,
        "workload": args.workload,
        "service": workload.get("service"),
        "baseline_replicas": workload.get("baseline_replicas"),
        "deployment": deployment_summary(deployment),
        "pods": pod_summary(responses["pods"]),
        "events": event_summary(responses["events"]),
        "hpa_conflicts": [{"name": item.get("metadata", {}).get("name"),
                           "min_replicas": item.get("spec", {}).get("minReplicas"),
                           "max_replicas": item.get("spec", {}).get("maxReplicas")}
                          for item in hpa_conflicts],
        "evidence_refs": [
            {"source": "kubernetes", "resource": f"Deployment/{name}", "namespace": namespace},
            {"source": "kubernetes", "resource": "Pod", "selector": workload["selector"], "namespace": namespace},
            {"source": "kubernetes", "resource": "Event", "namespace": namespace},
            {"source": "kubernetes", "resource": "HorizontalPodAutoscaler", "namespace": namespace},
        ],
    })


if __name__ == "__main__":
    raise SystemExit(main())
