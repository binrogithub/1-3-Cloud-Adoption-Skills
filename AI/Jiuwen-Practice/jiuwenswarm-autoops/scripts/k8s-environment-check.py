#!/usr/bin/env python3
"""Run a read-only Kubernetes prerequisite check for E03.

The check reports availability without exposing kubeconfig contents or tokens.
It never reads Kubernetes resources when the published cluster is disabled and
never performs a write operation.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("AUTOOPS_KUBERNETES_WORKLOADS_FILE",
                            str(ROOT / "config" / "kubernetes" / "workloads.json")))
sys.path.insert(0, str(ROOT / "scripts"))
from autoops_rundeck_config import job_registry, load_rundeck_environment


def emit(payload: dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def load_cluster(name: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        document = json.loads(CONFIG.read_text(encoding="utf-8"))
        cluster = document["clusters"][name]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None, "PUBLISHED_CLUSTER_NOT_FOUND"
    if not isinstance(cluster, dict):
        return None, "PUBLISHED_CLUSTER_INVALID"
    return cluster, None


def kubectl_path() -> str | None:
    configured = os.environ.get("AUTOOPS_KUBECTL")
    if configured:
        return configured if Path(configured).is_file() and os.access(configured, os.X_OK) else None
    project_binary = Path("/opt/JiuwenSwarm/bin/kubectl")
    if project_binary.is_file() and os.access(project_binary, os.X_OK):
        return str(project_binary)
    return shutil.which("kubectl")


def kubeconfig_path(cluster: dict[str, Any]) -> tuple[str | None, str]:
    variable = cluster.get("kubeconfig_env")
    if isinstance(variable, str) and variable and os.environ.get(variable):
        return os.environ[variable], variable
    if os.environ.get("KUBECONFIG"):
        return os.environ["KUBECONFIG"], "KUBECONFIG"
    default = Path.home() / ".kube" / "config"
    return str(default), "default"


def command_env(cluster: dict[str, Any], path: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    variable = cluster.get("kubeconfig_env")
    if path and variable and variable != "default":
        environment["KUBECONFIG"] = path
    return environment


def run(binary: str, arguments: list[str], environment: dict[str, str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run([binary, *arguments], text=True, capture_output=True,
                                check=False, env=environment, timeout=15)
    except subprocess.TimeoutExpired:
        return 124, "", "command timed out"
    except OSError as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout, result.stderr.strip()


def recovery_job_check(cluster: dict[str, Any]) -> dict[str, Any]:
    jobs = sorted({workload.get("restore_job") for workload in cluster.get("workloads", {}).values()
                   if isinstance(workload, dict) and isinstance(workload.get("restore_job"), str)
                   and workload.get("restore_job")})
    if not jobs:
        return {"status": "BLOCKED", "error_code": "RESTORE_ACTION_NOT_PUBLISHED", "required_jobs": []}
    environment: dict[str, str] = {}
    try:
        load_rundeck_environment(environment)
        registry = job_registry(ROOT, environment)
        document = json.loads(registry.read_text(encoding="utf-8"))
        registered = {item.get("name") for item in document.get("jobs", [])
                      if isinstance(item, dict) and isinstance(item.get("name"), str)}
    except (OSError, ValueError, json.JSONDecodeError, AttributeError, TypeError):
        return {"status": "BLOCKED", "error_code": "RUNDECK_REGISTRY_UNAVAILABLE",
                "required_jobs": jobs}
    missing = [job for job in jobs if job not in registered]
    if missing:
        return {"status": "BLOCKED", "error_code": "RUNDECK_JOB_NOT_REGISTERED",
                "required_jobs": jobs, "missing_jobs": missing}
    return {"status": "PASS", "required_jobs": jobs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check E03 Kubernetes prerequisites without writes.")
    parser.add_argument("--cluster", required=True, help="Published cluster name")
    parser.add_argument("--require-recovery", action="store_true",
                        help="Fail unless every published restore Job is in the protected Rundeck registry")
    args = parser.parse_args(argv)

    cluster, error = load_cluster(args.cluster)
    if error:
        return emit({"source": "kubernetes", "status": "invalid", "error_code": error,
                     "cluster": args.cluster}, 2)

    binary = kubectl_path()
    binary_check = {"available": bool(binary), "path": binary}
    result: dict[str, Any] = {
        "schema_version": 1,
        "source": "kubernetes",
        "cluster": args.cluster,
        "context": cluster.get("context"),
        "published_enabled": cluster.get("enabled") is True,
        "kubectl": binary_check,
        "write_attempted": False,
        "checks": [],
    }
    if not binary:
        result["status"] = "UNAVAILABLE"
        result["error_code"] = "KUBECTL_NOT_AVAILABLE"
        result["next_step"] = "安装或配置项目支持的 kubectl 客户端"
        return emit(result, 1)

    version_code, version_out, version_err = run(binary, ["version", "--client", "--output=json"], os.environ.copy())
    version: dict[str, Any] | None = None
    if version_code == 0:
        try:
            raw = json.loads(version_out)
            version = raw.get("clientVersion") if isinstance(raw, dict) else None
        except json.JSONDecodeError:
            version = None
    result["kubectl"]["client_version"] = version
    result["checks"].append({"name": "kubectl_client", "status": "PASS" if version else "FAIL",
                              "error": version_err or (None if version else "invalid version response")})

    config_path, config_source = kubeconfig_path(cluster)
    config_exists = any(Path(item).is_file() for item in config_path.split(os.pathsep)) if config_path else False
    result["kubeconfig"] = {"source": config_source, "configured": bool(config_path), "file_present": config_exists}

    if cluster.get("enabled") is not True:
        result["status"] = "UNAVAILABLE"
        result["error_code"] = "CLUSTER_NOT_ENABLED"
        result["next_step"] = "填写并审核 workloads.json 后，将目标 cluster enabled 设置为 true"
        result["checks"].append({"name": "published_cluster", "status": "BLOCKED",
                                  "reason": "published cluster is disabled; API was not contacted"})
        return emit(result, 1)

    environment = command_env(cluster, config_path if config_exists else None)
    context = cluster.get("context")
    context_args = ["--context", str(context)] if context else []
    contexts_code, contexts_out, contexts_err = run(binary,
                                                      [*context_args, "config", "get-contexts", "-o", "name"],
                                                      environment)
    contexts = [line.strip() for line in contexts_out.splitlines() if line.strip()]
    context_present = bool(context) and str(context) in contexts
    result["contexts"] = {"count": len(contexts), "selected_present": context_present}
    result["checks"].append({"name": "kubeconfig_context", "status": "PASS" if context_present else "FAIL",
                              "error": contexts_err or (None if context_present else "published context not found")})
    if not config_exists:
        result["status"] = "UNAVAILABLE"
        result["error_code"] = "KUBECONFIG_NOT_AVAILABLE"
        result["next_step"] = "通过 AUTOOPS_KUBECONFIG 提供已审核的 kubeconfig 文件"
        return emit(result, 1)
    if not context_present:
        result["status"] = "UNAVAILABLE"
        result["error_code"] = "KUBERNETES_CONTEXT_NOT_FOUND"
        result["next_step"] = "将已审核的集群 context 注册到 workloads.json"
        return emit(result, 1)

    api_code, api_out, api_err = run(binary, [*context_args, "get", "--raw=/version"], environment)
    try:
        api_payload = json.loads(api_out) if api_code == 0 else None
    except json.JSONDecodeError:
        api_payload = None
    api_ok = api_code == 0 and isinstance(api_payload, dict)
    result["api"] = {"reachable": api_ok,
                      "server_version": api_payload.get("gitVersion") if api_ok else None}
    result["checks"].append({"name": "kubernetes_api", "status": "PASS" if api_ok else "FAIL",
                              "error": api_err or (None if api_ok else "invalid API response")})
    if not api_ok:
        result["status"] = "UNAVAILABLE"
        result["error_code"] = "KUBERNETES_API_UNREACHABLE"
        result["next_step"] = "检查 context、网络和 Kubernetes API 权限"
        return emit(result, 1)

    result["recovery"] = recovery_job_check(cluster)
    if args.require_recovery and result["recovery"]["status"] != "PASS":
        result["status"] = "UNAVAILABLE"
        result["error_code"] = result["recovery"]["error_code"]
        result["next_step"] = "在受控 Rundeck 项目发布 workloads.json 要求的固定恢复 Job"
        return emit(result, 1)
    result["status"] = "READY"
    result["next_step"] = "可执行 E03 只读 inspect；写操作仍需固定 Job、授权和验证"
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
