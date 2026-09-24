#!/usr/bin/env python3
from __future__ import annotations

"""Constrained Project Manager dispatcher for JiuwenSwarm AutoOps."""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from observability_env import load_observability_environment
from autoops_authorization import AuthorizationConsumed, consume_approval, load_approval
from autoops_context import resolve as resolve_context
from autoops_context import host_system_context
from autoops_intent import HOST_TARGETS, parse_request, is_host_system_request
from autoops_task_store import TaskStore
from autoops_task_store import lifecycle_status
from autoops_preauthorization import finalize_reservation, load_policy, reserve, validate_scope
from autoops_contract import autoops_plan, validate_route
from autoops_routing import is_netops_request, route_request
from css_config import load_profile, safe_profile_summary

ROOT = Path(__file__).resolve().parents[1]
_ACTIVE_TASK_ID: str | None = None
ACTION_MAP = ROOT / "config" / "project-manager-actions.json"
CAPABILITY_REGISTRY = ROOT / "config" / "capability-registry.json"
LOG_TERMS = ("log", "日志", "error", "exception", "crash", "incident", "异常", "调查", "investigate")
EVENT_TERMS = ("event", "事件", "history", "历史", "变更", "deploy", "发布")
METRIC_TERMS = ("metric", "metrics", "指标", "趋势", "trend", "latency", "延迟", "throughput", "吞吐", "cpu", "内存", "memory", "磁盘", "disk", "error rate", "错误率")
CORRELATION_TERMS = ("根因", "溯源", "关联", "联动", "为什么失败", "失败原因",
                     "root cause", "trace back", "correlate")
SERVICE_TERMS = ("service", "服务", "start", "启动", "ensure", "恢复", "修复")
K8S_TERMS = ("kubernetes", "kubectl", "deployment", "pod", "namespace", "workload", "hpa",
             "集群", "命名空间", "副本", "工作负载", "容器")
K8S_RESTORE_TERMS = ("restore replicas", "restore replica", "restore kubernetes", "restore deployment",
                     "scale deployment", "恢复副本", "恢复副本数", "恢复 kubernetes", "恢复 deployment", "扩容副本")
LOCAL_TARGETS = {"local", "test-host-01"}


def adapter_target(target: str | None) -> str:
    """Map only registered local aliases to the adapter's canonical target."""
    candidate = (target or "local").strip()
    return "local" if candidate in LOCAL_TARGETS else candidate


def published_capabilities() -> set[str]:
    try:
        return set(json.loads(CAPABILITY_REGISTRY.read_text(encoding="utf-8"))["capabilities"])
    except (KeyError, TypeError, json.JSONDecodeError, OSError):
        return set()


def emit(payload, code=0):
    if _ACTIVE_TASK_ID:
        store = TaskStore()
        try:
            store.record_result(_ACTIVE_TASK_ID, payload, code)
        finally:
            store.close()
    print(json.dumps(payload, ensure_ascii=False))
    return code


def classify(request, job, service, action, profile="service_up"):
    """Backward-compatible scalar view of the structured route."""
    routing = route_request(request, job=job, service=service, action=action, profile=profile)
    if (routing["selected_epics"] and routing["selected_epics"][:3] == ["E05", "E04", "E06"]
            and any(term in request.casefold() for term in CORRELATION_TERMS) and service):
        return "E05+E06", "observability-investigator"
    return routing["primary_epic"], routing["primary_role"]


def effective_window_minutes(request, explicit):
    """Return the parsed operator window, with 24 hours as the policy default."""
    return parse_request(request, explicit_minutes=explicit)["time"]["requested_minutes"]


def shared_observability_window(intent: dict, minutes: int) -> tuple[str, str]:
    """Create one exact interval for every E05/E04/E06 child query."""
    requested = intent.get("time", {})
    if requested.get("start") and requested.get("end"):
        start = datetime.fromisoformat(str(requested["start"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(requested["end"]).replace("Z", "+00:00"))
    else:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
    return (start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))


def annotate_adapter(adapter, intent, since_minutes):
    """Keep the normalized user scope and window beside adapter evidence."""
    if not isinstance(adapter, dict):
        adapter = {"status": "UNKNOWN", "result": adapter}
    window = adapter.setdefault("window", {})
    if isinstance(window, dict):
        window.setdefault("requested_minutes", since_minutes)
    adapter["autoops_request"] = {
        "scope": intent["scope"],
        "time": {"expression": intent["time"]["expression"],
                 "requested_minutes": since_minutes,
                 "source": intent["time"]["source"],
                 "timezone": intent["time"].get("timezone", "Asia/Shanghai"),
                 **({key: intent["time"][key] for key in ("start", "end")
                     if key in intent["time"]})},
        "mode": intent["mode"],
    }
    return adapter


def user_view(intent, target: str | None, adapter: dict | None = None) -> dict:
    scope = intent["scope"]["kind"]
    scope_name = "本机 Linux 系统日志" if scope == "host_system" else "已登记应用日志"
    adapter_status = adapter.get("status") if isinstance(adapter, dict) else None
    status_labels = {
        "empty": "evidence_insufficient", "inconclusive": "evidence_insufficient",
        "unavailable": "data_source_unavailable", "trace_incomplete": "partial_coverage",
        "no_anomaly": "no_anomaly", "trace_ready": "anomaly_trace_ready",
        "COMPLETED": "report_ready", "FAILED": "diagnosis_failed",
    }
    time_range = intent["time"].get("expression", "最近24小时")
    if intent["time"].get("start") and intent["time"].get("end"):
        time_range = f"{intent['time']['start']} 至 {intent['time']['end']}"
    return {
        "scope": scope_name,
        "target": target or intent["scope"].get("target_ref") or "待确定",
        "window": time_range,
        "mode": "只读诊断",
        "adapter_status": status_labels.get(adapter_status, adapter_status),
        "next_step": "查看调查报告" if adapter_status in {"ok", "trace_ready", "COMPLETED"}
        else "检查日志采集与数据源配置",
    }


def load_service_job(service, action, target=None):
    # Prefer the selected application's binding.  The legacy action map is a
    # compatibility fallback only when an operator explicitly enables it.
    try:
        bound = resolve_context(service=service, target=target, include_test=True)
        if bound.get("status") == "RESOLVED":
            action_binding = bound["context"].get("capabilities", {}).get(action, {})
            if isinstance(action_binding, dict) \
                    and action_binding.get("capability") == "host.ensure_service.v1" \
                    and isinstance(action_binding.get("job"), str) \
                    and action_binding["job"]:
                return action_binding["job"]
            # A resolved profile without this published action is a hard
            # boundary. Never fall through to a job for another service.
            return None
        if target:
            # An explicit target must be resolved against the same profile as
            # the action. Do not let the legacy table bypass target scope.
            return None
    except (TypeError, ValueError):
        pass
    if os.environ.get("AUTOOPS_ENABLE_LEGACY_ACTION_MAP") != "1":
        return None
    try:
        entries = json.loads(ACTION_MAP.read_text(encoding="utf-8"))["service_actions"]
        return entries[service][action]["job"]
    except (KeyError, TypeError, json.JSONDecodeError, OSError):
        return None


def load_k8s_action(cluster: str, workload: str) -> tuple[str | None, str | None]:
    try:
        config_path = Path(os.environ.get("AUTOOPS_KUBERNETES_WORKLOADS_FILE",
                                         str(ROOT / "config" / "kubernetes" / "workloads.json")))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        record = config["clusters"][cluster]["workloads"][workload]
        return record.get("restore_job"), record.get("service")
    except (KeyError, TypeError, json.JSONDecodeError, OSError):
        return None, None


def run_adapter(command, environment):
    environment = dict(environment)
    # Shell adapters may need Python for structured evidence handling. Keep
    # them on the interpreter that launched ProjectManager so a low-privilege
    # systemd account never resolves a root-only `python3` shim through PATH.
    environment["AUTOOPS_PYTHON_EXECUTABLE"] = sys.executable
    completed = subprocess.run(command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False)
    raw = completed.stdout.strip()
    try:
        result = json.loads(raw) if raw else {"status": "UNKNOWN", "error": "adapter returned no JSON"}
    except json.JSONDecodeError:
        result = {
            "status": "COMPLETED" if completed.returncode == 0 else "FAILED",
            "transcript": raw[-4000:],
        }
    return completed.returncode, result


def run_k8s_business_verifier(cluster: str, workload: str, task_id: str,
                              action_completed_at: float) -> tuple[int, dict]:
    """Run the independent E09 probe for a Kubernetes workload binding."""
    command = [sys.executable, str(ROOT / "scripts" / "verify-k8s-business.py"),
               "--cluster", cluster, "--workload", workload, "--task-id", task_id,
               "--action-completed-at", str(action_completed_at)]
    return run_adapter(command, os.environ.copy())


def execution_result_fields(adapter: dict, code: int) -> dict:
    """Project adapter status into the task-level lifecycle contract."""
    raw_status = str(adapter.get("status", "UNKNOWN")).upper()
    unknown_external_result = (
        raw_status == "UNKNOWN"
        and str(adapter.get("error_code", "")).upper() == "RESULT_UNKNOWN"
    )
    reconciliation_in_progress = bool(adapter.get("reconciliation")) \
        and raw_status in {"RUNNING", "WAITING", "UNKNOWN"}
    status_map = {
        "SUCCESS": "SUCCEEDED", "COMPLETED": "SUCCEEDED", "NO_CHANGE": "SUCCEEDED",
        "UNKNOWN": "RECONCILING" if unknown_external_result or reconciliation_in_progress
        else ("FAILED" if code else "RUNNING"),
        "RUNNING": "RECONCILING" if reconciliation_in_progress else "RUNNING",
        "WAITING": "RECONCILING" if reconciliation_in_progress else "RUNNING",
    }
    task_status = status_map.get(raw_status, raw_status)
    if task_status not in {"SUCCEEDED", "FAILED", "PARTIAL", "BLOCKED", "RUNNING",
                           "WAITING_APPROVAL", "RECONCILING"}:
        task_status = "FAILED" if code else "RUNNING"
    fields = {"status": task_status, "execution_status": raw_status}
    verification = adapter.get("business_verification_status")
    if verification is None:
        verification = adapter.get("verification_status")
    if verification is not None:
        fields["verification_status"] = verification
    if verification == "PASSED":
        fields["recovery_status"] = "recovered"
    elif verification in {"FAILED", "INCONCLUSIVE", "UNVERIFIED", "PENDING"}:
        fields["recovery_status"] = "unverified"
    return fields


def main(argv=None):
    parser = argparse.ArgumentParser(description="Route an AutoOps request through a least-privileged role.")
    parser.add_argument("--request", required=True)
    parser.add_argument("--application")
    parser.add_argument("--service")
    parser.add_argument("--log-path")
    parser.add_argument("--environment")
    parser.add_argument("--scope-id")
    parser.add_argument("--job")
    parser.add_argument("--cluster")
    parser.add_argument("--css-profile")
    parser.add_argument("--css-config-dir")
    parser.add_argument("--netops-pool", help="Exact NOLI/A10 pool name; never inferred from a service name.")
    parser.add_argument("--netops-incident-id", help="Exact incident ID from a NOLI board result.")
    parser.add_argument("--workload")
    parser.add_argument("--namespace")
    parser.add_argument("--target")
    parser.add_argument("--action", default="ensure")
    parser.add_argument("--since-minutes", type=int)
    # Keep one-shot TUI replies within the interactive output budget. Operators
    # can still request a larger bounded page explicitly (up to the published
    # adapter maximum), while the default avoids temp-file evidence scraping by
    # the model after a large machine-output response.
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--profile", default="service_up")
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--task-id")
    parser.add_argument("--actor-id", default=os.environ.get("AUTOOPS_ACTOR_ID"))
    parser.add_argument("--session-id", default=os.environ.get("AUTOOPS_SESSION_ID"))
    parser.add_argument("--idempotency-key")
    parser.add_argument("--execute", action="store_true", help="Explicitly submit an E01/E02 action.")
    parser.add_argument("--authorization-id", help="Operator-created, task-scoped approval reference.")
    parser.add_argument("--preauthorization-id", help="Published policy reference for an incident-scoped auto action.")
    parser.add_argument("--incident-id", help="Stable incident identity required by a preauthorized action.")
    parser.add_argument("--include-test-profiles", action="store_true",
                        help="Explicitly include visibility=test profiles for fixture runs.")
    parser.add_argument("--machine-output", action="store_true",
                        default=os.environ.get("AUTOOPS_MACHINE_OUTPUT") == "1",
                        help="Return the published adapter JSON without a nested language-model report.")
    args = parser.parse_args(argv)
    intent = parse_request(args.request, service=args.service, application=args.application,
                           target=args.target, log_path=args.log_path,
                           explicit_minutes=args.since_minutes)
    since_minutes = int(intent["time"]["requested_minutes"])
    # A host request is a complete scope by itself. A short follow-up such as
    # `local` must not be mistaken for a service name.
    if is_host_system_request(args.request, service=args.service,
                              application=args.application, log_path=args.log_path):
        if args.service and args.service.casefold() in HOST_TARGETS:
            args.target = args.target or "local"
            args.service = None
        args.target = args.target or "local"

    # An explicit Kubernetes cluster/workload is already a complete scope.
    # Do not resolve unrelated host ServiceProfiles and surface their ambiguity
    # beside an otherwise valid E03 request.
    explicit_k8s_scope = any(term in args.request.lower() for term in K8S_TERMS) \
        and bool(args.cluster or args.workload)
    context_result = None
    explicit_css_scope = bool(args.css_profile) or any(term in args.request.casefold()
                                                       for term in ("css", "opensearch", "elasticsearch", "数据节点", "搜索集群"))
    explicit_netops_scope = is_netops_request(args.request)
    if intent["scope"]["kind"] == "host_system":
        context_result = {"schema_version": 2, "status": "RESOLVED",
                          "context": host_system_context(target=args.target or "local"),
                          "invalid_profiles": [], "deduplicated_profiles": []}
    elif not explicit_k8s_scope and not explicit_css_scope and not explicit_netops_scope \
            and (args.application or args.log_path or not args.service):
        context_result = resolve_context(application=args.application, service=args.service,
                                         target=args.target, log_path=args.log_path,
                                         environment=args.environment, scope_id=args.scope_id,
                                         include_test=args.include_test_profiles)
        if context_result["status"] == "RESOLVED":
            context = context_result["context"]
            args.service = args.service or context["service"]
            args.target = args.target or context["target"]["name"]
            intent = parse_request(args.request, service=args.service, application=args.application,
                                   target=args.target, log_path=args.log_path,
                                   explicit_minutes=args.since_minutes)
        elif args.application or args.log_path:
            return emit({"task_id": None, "selected_epic": None, "selected_role": None,
                         "status": context_result["status"], "execution_mode": "inspect",
                         "context": context_result}, 2)

    task_id = args.task_id or f"pm-{uuid.uuid4().hex}"
    idempotency_key = args.idempotency_key or task_id
    routing = validate_route(route_request(args.request, job=args.job, service=args.service,
                                          action=args.action, profile=args.profile))
    epic, role = routing["primary_epic"], routing["primary_role"]
    result = {"task_id": task_id, "operation_id": idempotency_key,
              "selected_epic": epic, "selected_role": role,
              "intent": intent, "routing": routing,
              "execution_mode": "inspect" if epic and (epic.startswith("E") or epic in {"CSS", "NETOPS"}) else "none"}
    if routing.get("native_workflow"):
        result["native_workflow"] = routing["native_workflow"]
    result["user_view"] = user_view(intent, args.target)
    if context_result is not None:
        result["context"] = context_result
    store = TaskStore()
    task_payload = {"request": args.request, "context": context_result,
                    "service": args.service, "target": args.target,
                    "operation_id": idempotency_key}
    if args.actor_id:
        task_payload["actor_id"] = args.actor_id
    if args.session_id:
        task_payload["session_id"] = args.session_id
    store.upsert(task_id, task_id, task_payload, status="RECEIVED")
    store.event(task_id, "route.selected", {
        "selected_epic": epic,
        "selected_role": role,
        "selected_epics": routing["selected_epics"],
        "selected_roles": routing["selected_roles"],
        "selected_capabilities": routing["selected_capabilities"],
        "routing_reason": routing["routing_reason"],
    })
    store.close()
    global _ACTIVE_TASK_ID
    _ACTIVE_TASK_ID = task_id
    if not role:
        return emit({**result, "status": "UNSUPPORTED", "execution_mode": "none", "error": "Request does not match an AutoOps route."}, 2)

    if epic == "NETOPS":
        if routing["intent"] == "remediate" or args.execute:
            return emit({**result, "status": "UNSUPPORTED", "execution_mode": "blocked",
                         "capability": "netops.incidents.read.v1", "changed": False,
                         "error_code": "NETOPS_ACTION_NOT_PUBLISHED",
                         "error": "NetOps publishes only read-only NOLI incident investigation."}, 2)
        command = [sys.executable, str(ROOT / "scripts" / "netops-noli.py"),
                   "--window-minutes", str(since_minutes), "--limit", str(args.limit)]
        if args.netops_pool:
            command.extend(["--pool", args.netops_pool])
        if args.netops_incident_id:
            command.extend(["--incident-id", args.netops_incident_id])
        code, adapter = run_adapter(command, load_observability_environment())
        adapter_status = adapter.get("status", "UNKNOWN")
        next_step = {
            "NOT_CONFIGURED": "配置并部署 NOLI 数据源后重试",
            "AUTH_FAILED": "核对 NOLI 专用令牌",
            "UNAVAILABLE": "检查 NOLI 服务或网络连通性",
            "empty": "核对池名、事件 ID 与监控覆盖范围",
            "inconclusive": "检查 NOLI 覆盖、缺口和传感器状态",
            "partial": "结合覆盖缺口复核事件证据",
        }.get(adapter_status, "查看 NOLI 事件证据与覆盖范围")
        simulated = adapter.get("simulated") is True
        if simulated:
            next_step = "这是合成演示数据；不得描述为真实客户故障"
        return emit({**result, "status": adapter_status,
                     "execution_mode": "inspect", "capability": "netops.incidents.read.v1",
                     "user_view": {"scope": "固网合成模拟事件（非真实客户网络）" if simulated else "NOLI 网络事件",
                                   "target": args.netops_pool or args.netops_incident_id or "已配置 NOLI 实例",
                                   "window": intent["time"]["expression"], "mode": "只读调查",
                                   "adapter_status": adapter_status,
                                   "simulated": simulated,
                                   "next_step": next_step},
                     "adapter_result": adapter}, code)

    if epic == "CSS":
        if not args.css_profile:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect",
                         "capability": routing["selected_capabilities"][0],
                         "error_code": "CSS_PROFILE_REQUIRED",
                         "error": "Register AK, hidden SK, region, project_id and CSS cluster_id first, then pass --css-profile."}, 2)
        try:
            profile = load_profile(args.css_profile, args.css_config_dir)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return emit({**result, "status": "NOT_CONFIGURED", "execution_mode": "inspect",
                         "capability": routing["selected_capabilities"][0],
                         "error_code": "CSS_PROFILE_INVALID", "error": str(exc)}, 2)
        command_name = "plan" if routing["intent"] in {"remediate", "watch"} else "inspect"
        command = [sys.executable, str(ROOT / "scripts" / "css-auto.py"), command_name,
                   "--profile-id", args.css_profile]
        if args.css_config_dir:
            command.extend(["--config-dir", args.css_config_dir])
        environment = os.environ.copy()
        if args.css_config_dir:
            environment["AUTOOPS_CSS_CONFIG_DIR"] = args.css_config_dir
        code, adapter = run_adapter(command, environment)
        if len(routing["selected_epics"]) > 1:
            plan_steps = []
            previous = []
            for index, selected_epic in enumerate(routing["selected_epics"]):
                selected_role = routing["selected_roles"][index]
                capability = routing["selected_capabilities"][index]
                step_id = f"css-route-{index + 1}"
                effect = "write" if capability == "css.scale.v1" else "read"
                plan_steps.append({
                    "step_id": step_id, "role": selected_role,
                    "capability": capability, "invocation_kind": "project_route",
                    "effect": effect, "depends_on": list(previous),
                    "when": "always" if not previous else f"{previous[-1]}.status == SUCCEEDED",
                    "required": True, "timeout_seconds": 900,
                    "inputs": {"css_profile": args.css_profile, "request": args.request},
                    "expected_result": {"status": "SUBMITTED" if effect == "write" else "SUCCEEDED"},
                    **({"approval": "required"} if effect == "write" else {}),
                })
                previous.append(step_id)
            plan = autoops_plan(task_id=task_id, plan_revision=1, goal=args.request,
                                scope={"cluster_ref": args.css_profile}, steps=plan_steps,
                                status="WAITING_APPROVAL" if any(
                                    step["effect"] == "write" for step in plan_steps
                                ) else "PLANNED",
                                workflow_ref="css-autoscale-v1",
                                workflow_asset="swarmflow/css-autoscale-v1.py",
                                published_capabilities=published_capabilities() or None)
            plan_store = TaskStore()
            try:
                plan_store.record_plan(task_id, plan)
            finally:
                plan_store.close()
            return emit({**result, "status": "PLAN_READY", "execution_mode": "plan",
                         "capability": "css.plan.v1", "css_profile": safe_profile_summary(profile),
                         "adapter_result": adapter, "plan": plan,
                         "next_step": "Execute the published E01 action only after authorization and CSS reconciliation."}, code)
        return emit({**result, "status": adapter.get("status", "UNKNOWN") if isinstance(adapter, dict) else "UNKNOWN",
                     "execution_mode": "plan" if command_name == "plan" else "inspect",
                     "capability": routing["selected_capabilities"][0],
                     "css_profile": safe_profile_summary(profile),
                     "adapter_result": adapter}, code)

    # Direct CLI callers retain the deterministic compatibility path.  The
    # ProjectManager Skill routes complex TUI requests to the published native
    # workflow before this adapter is called; native expert nodes then invoke
    # this boundary once for their individual capability.
    composite_observability = routing["selected_epics"] == ["E05", "E04", "E06"]
    symptom_observability = routing["selected_epics"] == ["E05", "E04"] \
        and routing["intent"] == "diagnose"
    if routing["plan_kind"] == "multi" and routing["intent"] not in {"remediate"} \
            and not composite_observability and not symptom_observability:
        plan_steps = [{"step_id": f"route-{index + 1}", "epic": selected_epic,
                       "role": routing["selected_roles"][index],
                       "capability": routing["selected_capabilities"][index],
                       "invocation_kind": "project_route", "effect": "read",
                       "inputs": {"target": args.target or "local", "service": args.service},
                       "depends_on": [], "when": "always", "required": True,
                       "expected_result": {"status": "SUCCEEDED"}, "timeout_seconds": 600}
                      for index, selected_epic in enumerate(routing["selected_epics"])]
        plan = autoops_plan(task_id=task_id, plan_revision=1, goal=args.request,
                            scope={"target_ref": args.target or "local",
                                   "service_ref": args.service or "unspecified"},
                            steps=plan_steps,
                            published_capabilities=published_capabilities() or None)
        plan_store = TaskStore()
        try:
            plan_store.record_plan(task_id, plan)
        finally:
            plan_store.close()
        return emit({**result, "status": "PLAN_READY", "execution_mode": "plan",
                     "plan": plan,
                     "next_step": "RO-05 native expert orchestration is required to execute this multi-role plan."})

    if epic in {"E04", "E05", "E05+E06", "E06"} and args.target and args.target not in LOCAL_TARGETS:
        return emit({**result, "status": "UNAVAILABLE", "execution_mode": "inspect",
                     "error_code": "TARGET_UNSUPPORTED", "error": "remote target requires a configured host-scoped adapter.",
                     "target": args.target}, 1)

    if epic == "E03":
        if not args.cluster or not args.workload:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect",
                         "capability": "k8s.inspect.v1",
                         "error": "Kubernetes inspection requires a published --cluster and --workload."}, 2)
        restore_request = args.action == "restore" or any(term in args.request.lower() for term in K8S_RESTORE_TERMS)
        if not restore_request:
            command = [sys.executable, str(ROOT / "scripts" / "k8s-inspect.py"),
                       "--cluster", args.cluster, "--workload", args.workload]
            if args.namespace:
                command.extend(["--namespace", args.namespace])
            code, adapter = run_adapter(command, os.environ.copy())
            return emit({**result, "execution_mode": "inspect", "capability": "k8s.inspect.v1",
                         "user_view": {"scope": "已登记 Kubernetes 工作负载",
                                       "target": f"{args.cluster}/{args.workload}",
                                       "window": "当前资源状态", "mode": "只读检查",
                                       "adapter_status": adapter.get("status") if isinstance(adapter, dict) else "unknown",
                                       "next_step": "检查 Kubernetes 资源证据"},
                         "adapter_result": adapter}, code)
        if args.execute:
            if not args.target:
                return emit({**result, "status": "INPUT_ERROR", "execution_mode": "execute",
                             "capability": "k8s.restore_replicas.v1",
                             "error": "Kubernetes restore requires the published execution target."}, 2)
            job, service = load_k8s_action(args.cluster, args.workload)
            if not job or not service:
                return emit({**result, "status": "INPUT_ERROR", "execution_mode": "execute",
                             "capability": "k8s.restore_replicas.v1",
                             "error": "The Kubernetes restore action is not published for this workload."}, 2)
            args.service = args.service or service
        else:
            job, _ = load_k8s_action(args.cluster, args.workload)
            return emit({**result, "status": "PENDING_CONFIRMATION", "execution_mode": "dry-run",
                         "capability": "k8s.restore_replicas.v1", "job": job,
                         "cluster": args.cluster, "workload": args.workload,
                         "confirmation": "Rerun with --execute only after the published recovery action is approved."})

    if epic == "E05" and not composite_observability and not symptom_observability:
        if intent["scope"]["kind"] != "host_system" and not args.service:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect", "error": "Please specify an application or service for application logs."}, 2)
        if not 1 <= since_minutes <= 1440 or not 1 <= args.limit <= 200:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect", "error": "Use since-minutes 1..1440 and limit 1..200."}, 2)
        command = [str(ROOT / "scripts" / "log-investigate.sh")]
        if intent["scope"]["kind"] == "host_system":
            command.extend(["--scope", "host_system"])
        else:
            command.extend(["--service", args.service])
        command.extend(["--since-minutes", str(since_minutes), "--limit", str(args.limit)])
        if args.machine_output:
            command.append("--machine-output")
        code, adapter = run_adapter(command, load_observability_environment())
        annotated = annotate_adapter(adapter, intent, since_minutes)
        return emit({**result, "execution_mode": "inspect",
                     "user_view": user_view(intent, args.target, annotated),
                     "adapter_result": annotated}, code)

    if composite_observability or symptom_observability or epic == "E05+E06":
        if not args.service:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect", "error": "Combined observability investigation requires --service."}, 2)
        start_iso, end_iso = shared_observability_window(intent, since_minutes)
        command = [sys.executable, str(ROOT / "scripts" / "observability-investigate.py"),
                   "--task-id", task_id, "--service", args.service,
                   "--since-minutes", str(since_minutes),
                   "--limit", str(args.limit), "--target", adapter_target(args.target),
                   "--start", start_iso, "--end", end_iso]
        if symptom_observability:
            command.append("--continue-on-clean")
        code, adapter = run_adapter(command, load_observability_environment())
        annotated = annotate_adapter(adapter, intent, since_minutes)
        capabilities = ["logs.query.v2", "metrics.query.v1"] if symptom_observability else [
            "logs.query.v2", "metrics.query.v1", "events.search.v1",
        ]
        return emit({**result, "execution_mode": "inspect", "user_view": user_view(intent, args.target, annotated),
                     "capability": "observability.investigate.v1",
                     "capabilities": capabilities,
                     "adapter_result": annotated}, code)

    if epic == "E04":
        if not args.service:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect", "error": "E04 requires --service."}, 2)
        command = [sys.executable, str(ROOT / "scripts" / "prometheus-query.py"), "--service", args.service,
                   "--profile", args.profile, "--since-minutes", str(since_minutes), "--limit", str(args.limit)]
        code, adapter = run_adapter(command, load_observability_environment())
        annotated = annotate_adapter(adapter, intent, since_minutes)
        return emit({**result, "execution_mode": "inspect", "user_view": user_view(intent, args.target, annotated), "capability": "metrics.query.v1", "adapter_result": annotated}, code)

    if epic == "E06":
        if not args.service:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect", "error": "E06 requires --service."}, 2)
        command = [sys.executable, str(ROOT / "scripts" / "opensearch-events-query.py"), "--service", args.service,
                   "--since-minutes", str(since_minutes), "--limit", str(args.limit), "--offset", str(args.offset)]
        for keyword in args.keyword:
            command.extend(("--keyword", keyword))
        code, adapter = run_adapter(command, load_observability_environment())
        annotated = annotate_adapter(adapter, intent, since_minutes)
        return emit({**result, "execution_mode": "inspect", "user_view": user_view(intent, args.target, annotated), "capability": "events.search.v1", "adapter_result": annotated}, code)

    if epic == "E01":
        job = args.job
    elif epic == "E02":
        job = load_service_job(args.service, args.action, args.target)
    else:
        job, _ = load_k8s_action(args.cluster, args.workload)
    if not job:
        return emit({**result, "status": "INPUT_ERROR", "execution_mode": "execute", "error": "The requested action is not published."}, 2)
    if not args.target:
        return emit({**result, "status": "INPUT_ERROR", "execution_mode": "execute", "error": "E01 and E02 require --target."}, 2)
    if epic == "E01" and args.action == "inspect":
        command = [sys.executable, str(ROOT / "scripts" / "autoops-host-inspect.py"),
                   "--task-id", task_id, "--target", args.target]
        if not args.service:
            return emit({**result, "status": "INPUT_ERROR", "execution_mode": "inspect",
                         "capability": "host.inspect.v1",
                         "error": "Published host inspection requires a service profile."}, 2)
        command.extend(["--service", args.service])
        code, adapter = run_adapter(command, os.environ.copy())
        return emit({**result, "status": adapter.get("status", "FAILED"),
                     "execution_mode": "inspect", "capability": "host.inspect.v1",
                     "job": job, "target": args.target, "adapter_result": adapter}, code)
    if not args.execute:
        return emit({**result, "status": "PENDING_CONFIRMATION", "execution_mode": "dry-run", "job": job, "target": args.target, "confirmation": "Rerun with --execute to submit the allowlisted Rundeck job."})

    authorization_boundary = "task-scoped-approval"
    if args.preauthorization_id:
        policy_status, policy = load_policy(args.preauthorization_id)
        if policy_status != "PREAUTHORIZED":
            return emit({**result, "status": "AUTHORIZATION_DENIED", "execution_mode": "blocked",
                         "job": job, "target": args.target, "error_code": policy_status,
                         "error": policy["error"], "changed": False}, 0)
        capability = ("host.ensure_service.v1" if epic == "E02" else
                      "k8s.restore_replicas.v1" if epic == "E03" else "runbook.execute")
        scope_status, scope = validate_scope(policy, capability=capability, job=job,
                                             target=args.target, service=args.service or "")
        if scope_status != "PREAUTHORIZED":
            return emit({**result, "status": "AUTHORIZATION_DENIED", "execution_mode": "blocked",
                         "job": job, "target": args.target, "error_code": scope_status,
                         "error": scope["error"], "changed": False}, 0)
        incident_id = args.incident_id or task_id
        operation_id = args.idempotency_key or f"{incident_id}:{job}:{args.target}"
        reserve_status, reservation = reserve(policy, incident_id=incident_id, operation_id=operation_id)
        if reserve_status not in {"PREAUTHORIZED", "PREAUTHORIZATION_ALREADY_RESERVED"}:
            return emit({**result, "status": "AUTHORIZATION_DENIED", "execution_mode": "blocked",
                         "job": job, "target": args.target, "error_code": reserve_status,
                         "error": reservation["error"], "changed": False}, 0)
        authorization_boundary = "published-preauthorization"
    else:
        approval_status, approval = load_approval(args.authorization_id, task_id=task_id, job=job, target=args.target)
        if approval_status != "APPROVED":
            return emit({**result, "status": "PENDING_CONFIRMATION" if approval_status == "AUTHORIZATION_REQUIRED" else "AUTHORIZATION_DENIED",
                         "execution_mode": "blocked", "job": job, "target": args.target,
                         "error_code": approval_status, "error": approval["error"], "changed": False}, 0)
        try:
            consume_approval(args.authorization_id, approval)
        except (AuthorizationConsumed, OSError, json.JSONDecodeError):
            return emit({**result, "status": "AUTHORIZATION_DENIED", "execution_mode": "blocked",
                         "job": job, "target": args.target, "error_code": "AUTHORIZATION_CONSUMED",
                         "error": "The operator approval was already consumed by another request.", "changed": False}, 0)
    environment = os.environ.copy()
    environment["AUTOOPS_AUTHENTICATED_ROLE"] = "kubernetes-operator" if epic == "E03" else "runbook-operator"
    if epic == "E03":
        execution_command = [sys.executable, str(ROOT / "scripts" / "k8s-restore-replicas.py"),
                             "--cluster", args.cluster, "--workload", args.workload,
                             "--target", args.target, "--task-id", task_id,
                             "--idempotency-key", idempotency_key]
    else:
        execution_command = [sys.executable, str(ROOT / "scripts" / "runbook-execute.py"),
                             "--task-id", task_id, "--idempotency-key", idempotency_key,
                             "--job", job, "--target", args.target]
    code, adapter = run_adapter(execution_command, environment)
    business_verifier_invoked = False
    if epic == "E03" and code == 0 and isinstance(adapter, dict) \
            and "resource_verification_status" in adapter:
        business_verifier_invoked = True
        verification_code, verification = run_k8s_business_verifier(
            args.cluster, args.workload, task_id, time.time(),
        )
        adapter = dict(adapter)
        adapter["business_verification"] = verification
        adapter["business_verification_status"] = verification.get("verification_status", "INCONCLUSIVE")
        if verification_code != 0 or adapter["business_verification_status"] != "PASSED":
            adapter["status"] = "PARTIAL"
            code = 1
    if args.preauthorization_id:
        finalize_reservation(policy, incident_id=incident_id, operation_id=operation_id,
                             execution_status=(adapter or {}).get("status", "UNKNOWN"))
    boundary = (f"E03/kubernetes-operator/E01/{authorization_boundary}/E09/recovery-verifier"
                if epic == "E03" and business_verifier_invoked
                else f"E03/kubernetes-operator/E01/{authorization_boundary}"
                if epic == "E03" else f"E01/runbook-operator/{authorization_boundary}")
    return emit({**result, **execution_result_fields(adapter, code),
                 "execution_mode": "execute", "execution_boundary": boundary,
                 "job": job, "target": args.target, "adapter_result": adapter}, code)


if __name__ == "__main__":
    raise SystemExit(main())
