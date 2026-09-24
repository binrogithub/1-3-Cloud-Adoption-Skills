#!/usr/bin/env python3
"""Structured intent-to-capability routing for the ProjectManager boundary.

This module is deliberately deterministic.  JiuwenSwarm/MaaS may provide the
rich language interpretation, but the project validates the resulting intent
against the published capability vocabulary before any adapter is called.
"""
from __future__ import annotations

import re
from typing import Any


CAPABILITIES = {
    "NETOPS": ("netops", "netops.incidents.read.v1"),
    "CSS": ("css_auto", "css.inspect.v1"),
    "E01": ("runbook-operator", "host.inspect.v1"),
    "E02": ("ansible-operator", "host.ensure_service.v1"),
    "E03": ("kubernetes-operator", "k8s.inspect.v1"),
    "E04": ("metrics-observer", "metrics.query.v1"),
    "E05": ("log-investigator", "logs.query.v2"),
    "E06": ("event-investigator", "events.search.v1"),
    "E09": ("recovery-verifier", "service.verify.v1"),
}

NATIVE_WORKFLOW_ROUTES = {
    "css": {
        "ref": "css-autoscale-v1",
        "asset": "swarmflow/css-autoscale-v1.py",
        "capabilities": ["css.inspect.v1", "css.plan.v1", "css.scale.v1",
                         "css.operation.status.v1", "css.verify.v1"],
    },
    "observability": {
        "ref": "ro05-parallel-observability-v1",
        "asset": "swarmflow/ro05-parallel-observability-v1.py",
        "capabilities": ["logs.query.v2", "metrics.query.v1", "events.search.v1"],
    },
}

_WORD = re.compile(r"[a-z0-9][a-z0-9._/-]*", re.IGNORECASE)
_K8S_WORDS = {"kubernetes", "kubectl", "k8s", "deployment", "deployments", "pod", "pods",
              "namespace", "namespaces", "workload", "workloads", "hpa", "cluster"}
_K8S_ZH = ("集群", "命名空间", "工作负载", "副本", "容器")
_LOG_WORDS = {"log", "logs", "logging", "journal", "journalctl", "loki",
              "exception", "crash", "panic", "failed", "failure", "error", "errors",
              "日志", "异常", "错误", "崩溃"}
_METRIC_WORDS = {"metric", "metrics", "prometheus", "latency", "throughput", "cpu",
                 "memory", "disk", "指标", "延迟", "吞吐", "内存", "磁盘", "错误率"}
_EVENT_WORDS = {"event", "events", "history", "release", "releases", "deploy",
                "audit", "opensearch", "事件", "历史", "发布", "变更", "审计"}
_CSS_WORDS = {"css", "opensearch", "elasticsearch", "ces", "cluster_id",
              "data-node", "data-nodes", "css_cluster"}
_NETOPS_WORDS = {"noli", "netops", "a10", "ftth", "pon", "olt", "ont", "bng", "bras",
                 "pppoe", "dslam", "onu"}
_NETOPS_PHRASES = ("网络运维", "网络日志", "网络告警", "负载均衡池", "负载均衡器",
                   "固网", "固定网络", "光接入", "光纤故障", "光猫", "宽带故障", "接入网",
                   "接入故障", "链路丢包", "光功率")
_SYMPTOMS = ("打不开", "不可用", "无法访问", "故障", "页面失败", "服务异常", "不通",
             "unavailable", "down", "outage", "not responding", "cannot access")
_VERIFY = ("验证", "校验", "确认恢复", "是否恢复", "恢复了吗", "verify", "validate",
           "check recovery", "health check", "健康检查")
_REMEDIATE = ("恢复", "修复", "重启", "扩容", "执行", "ensure", "remediate", "restart",
              "repair", "recover", "scale")
_DIAGNOSE = ("排查", "调查", "诊断", "找原因", "根因", "为什么", "investigate", "diagnose",
             "root cause", "troubleshoot")
_WATCH = ("值守", "持续关注", "长期运行", "watch", "monitor", "routine", "定时")
_RESUME = ("继续", "刚才的任务", "previous task", "resume")
_CANCEL = ("取消", "停止任务", "stop task", "cancel")
_NON_REMEDIATION = ("只读", "只检查", "不执行", "不要执行", "无需执行", "不做修改",
                    "不进行修改", "不修改", "read-only", "readonly", "without changes",
                    "do not execute", "no changes")


def _words(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _WORD.finditer(text)}


def _has_word(text: str, words: set[str]) -> bool:
    token_set = _words(text)
    return bool(token_set & words)


def _has_signal(text: str, words: set[str], phrases: tuple[str, ...] = ()) -> bool:
    """Match English tokens exactly and CJK terms as explicit phrases."""
    return _has_word(text, words) or _has_cjk_or_phrase(text, phrases)


def _has_cjk_or_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(phrase.casefold() in folded for phrase in phrases)


def _has_verification_signal(text: str) -> bool:
    """Recognize separated Chinese confirmation wording without matching all recovery requests."""
    return (_has_cjk_or_phrase(text, _VERIFY)
            or bool(re.search(r"确认.{0,24}恢复", text, re.IGNORECASE)))


def _has_remediation_signal(text: str) -> bool:
    """Recognize a requested write while respecting an explicit read-only guard."""
    if _has_cjk_or_phrase(text, _NON_REMEDIATION):
        return False
    return _has_cjk_or_phrase(text, _REMEDIATE)


def _negative_k8s(text: str) -> bool:
    """Recognize a nearby explicit exclusion without treating ``podcast`` as Pod."""
    folded = text.casefold()
    return bool(re.search(
        r"(?:不要|无需|不查|不检查|排除|without|exclude|do\s+not)\s*"
        r"(?:查询|检查|查看|查|use|inspect\s+)?\s*"
        r"(?:kubernetes|kubectl|deployment|pod\b|pods\b|集群|容器|工作负载)",
        folded,
    ))


def _active_k8s(text: str) -> bool:
    if _negative_k8s(text):
        return False
    return _has_word(text, _K8S_WORDS) or _has_cjk_or_phrase(text, _K8S_ZH)


def is_netops_request(text: str) -> bool:
    """Select NOLI only for explicit network vocabulary, not generic logs."""
    if _has_cjk_or_phrase(text, ("CSS 集群", "CSS集群", "数据节点", "集群扩容", "集群缩容")):
        return False
    return _has_word(text, _NETOPS_WORDS) or _has_cjk_or_phrase(text, _NETOPS_PHRASES)


def _has_k8s_remediation_request(text: str) -> bool:
    """Require an explicit replica/deployment action before overriding verify.

    A request such as “确认 Kubernetes 是否恢复” remains a read-only E09
    verification. “恢复副本并验证业务” is a recovery with a required E09
    postcondition, so E03 must remain the primary role.
    """
    if not _active_k8s(text) or not _has_remediation_signal(text):
        return False
    # The resource name may be between the action and “副本”, for example
    # “恢复 Kubernetes order-api Deployment 副本”. Keep the action before the
    # resource requirement so “确认副本是否恢复” remains verification only.
    return bool(re.search(
        r"(?:恢复|扩容|restore|scale).{0,80}(?:副本|replica(?:s)?|deployment)",
        text,
        re.IGNORECASE,
    ))


def route_request(request: str, *, job: str | None = None, service: str | None = None,
                  action: str = "ensure", profile: str = "service_up") -> dict[str, Any]:
    """Return a validated, explainable capability selection.

    The first role is retained as ``primary_*`` for backward-compatible CLI
    output.  ``selected_*`` is authoritative for planning and never removes a
    capability explicitly requested by the operator.
    """
    text = request.strip()
    folded = text.casefold()
    words = _words(text)
    selected: list[str] = []
    reasons: list[str] = []
    excluded: list[dict[str, str]] = []
    missing: list[str] = []

    def add(epic: str, reason: str) -> None:
        if epic not in selected:
            selected.append(epic)
            reasons.append(reason)

    intent = "investigate"
    if _has_cjk_or_phrase(text, _CANCEL):
        intent = "cancel"
    elif _has_cjk_or_phrase(text, _RESUME):
        intent = "resume"
    elif _has_cjk_or_phrase(text, _WATCH):
        intent = "watch"
    elif _has_k8s_remediation_request(text):
        intent = "remediate"
    elif _has_verification_signal(text):
        intent = "verify"
    elif (_has_remediation_signal(text)
          and not (job and (_has_word(text, {"check", "query", "inspect"})
                    or _has_cjk_or_phrase(text, ("检查", "查询", "查看", "核验"))))) \
            or action not in {"ensure", "inspect", "query"}:
        intent = "remediate"
    elif _has_cjk_or_phrase(text, _DIAGNOSE):
        intent = "diagnose"
    elif _has_word(text, {"check", "query", "show", "查看", "查询", "检查"}):
        intent = "inspect"

    netops = is_netops_request(text) and intent not in {"resume", "cancel"}
    css = (
        bool(words & _CSS_WORDS)
        or _has_cjk_or_phrase(text, ("华为云 CSS", "CSS 集群", "CSS集群", "搜索集群", "数据节点",
                                     "查询流量", "写入流量", "分片迁移", "集群扩容", "集群缩容"))
    ) and not bool(re.search(r"(?:网页|页面|样式).{0,12}css", folded)) and not netops
    k8s = _active_k8s(text) and not css
    metric_profile = profile in {"service_errors", "service_latency"}
    log_words_without_error = _LOG_WORDS - {"error", "errors", "错误", "异常"}
    explicit_log = (_has_signal(text, log_words_without_error, ("日志", "日志文件", "错误日志", "异常日志", "崩溃日志"))
                    or _has_cjk_or_phrase(text, ("error log", "error logs")))
    error_signal = _has_signal(text, {"error", "errors"}, ("错误", "异常"))
    logs = explicit_log or (error_signal and not metric_profile)
    metrics = (metric_profile
               or _has_signal(text, _METRIC_WORDS, ("指标", "延迟", "吞吐", "错误率", "内存", "磁盘")))
    events = _has_signal(text, _EVENT_WORDS, ("事件", "历史", "发布", "部署", "变更", "审计"))
    symptom = _has_cjk_or_phrase(text, _SYMPTOMS)
    correlation = _has_cjk_or_phrase(text, ("根因", "溯源", "相关性", "correlate", "root cause"))

    if _negative_k8s(text):
        excluded.append({"candidate": "E03", "reason": "operator explicitly excluded Kubernetes/Pod inspection"})
    if intent in {"resume", "cancel"}:
        if not service:
            missing.append("task_reference")
        add("E09", "resume/cancel requires task state and completion verification")
    elif intent == "verify":
        add("E09", "operator requested verification rather than a new recovery action")
        if k8s:
            add("E03", "verification includes the explicitly named Kubernetes resource")
    else:
        if css:
            add("CSS", "Huawei Cloud CSS cluster, traffic, capacity, or data-node operation was explicitly named")
        if job:
            add("E01", "an explicit published Runbook was supplied")
        if k8s:
            add("E03", "Kubernetes resource or cluster was explicitly named")
        if logs:
            add("E05", "log evidence was explicitly requested")
        if metrics:
            add("E04", "metric/profile evidence was explicitly requested")
        # A recovery command may mention the published service/job as its
        # target.  That noun does not request a separate change-history
        # investigation; explicit history/audit/correlation wording still does.
        event_request = events and (
            intent != "remediate"
            or _has_cjk_or_phrase(text, ("查询", "查看", "审计", "历史", "关联", "事件", "history", "audit"))
        )
        if event_request:
            add("E06", "event, release, history, or audit evidence was explicitly requested")
        if correlation:
            add("E05", "root-cause analysis needs a current log anchor")
            add("E04", "root-cause analysis needs impact/health metrics")
            add("E06", "root-cause analysis needs historical change evidence")
        if symptom and service and not selected:
            add("E05", "an application symptom needs current log evidence")
            add("E04", "an application symptom needs health/impact metrics")
        if intent == "remediate":
            if css:
                # CSS owns the bounded plan and hands a write to the fixed
                # E01 Runbook; do not misroute a managed CSS node operation
                # through host Ansible.
                add("E01", "CSS capacity changes are submitted only through the fixed E01 Runbook")
                add("E09", "CSS capacity changes require independent topology and business verification")
            elif k8s:
                add("E01", "Kubernetes recovery is submitted only through the published Runbook")
            else:
                add("E02", "service recovery is described by Ansible")
                add("E01", "E01 is the only published external action submitter")
            if not css:
                add("E09", "a remediation task must end with independent verification")

    if netops:
        # NOLI already correlates its own sensors, alerts and log backfill.
        # Do not create a second E04/E05/E06 plan from words in the same request.
        selected[:] = ["NETOPS"]
        reasons[:] = ["explicit NOLI/A10 network request uses the published read-only NetOps role"]
        missing[:] = []

    if not selected:
        if service is None and (symptom or intent in {"diagnose", "remediate"}):
            missing.append("application_or_service")
        else:
            missing.append("published_capability")

    primary = selected[0] if selected else None
    role = CAPABILITIES[primary][0] if primary else None
    capabilities = [CAPABILITIES[epic][1] for epic in selected]
    if css and intent in {"remediate", "watch"} and "CSS" in selected:
        capabilities[0] = "css.plan.v1"
    if css and intent == "remediate":
        for index, selected_epic in enumerate(selected):
            if selected_epic == "E01":
                capabilities[index] = "css.scale.v1"
            elif selected_epic == "E09":
                capabilities[index] = "css.verify.v1"
    if intent == "remediate" and primary == "E03":
        # E03's write capability replaces its read capability only when the
        # operator explicitly requested recovery and supplied its scope.
        capabilities[0] = "k8s.restore_replicas.v1"
    if primary == "E09":
        capabilities[0] = "service.verify.v1"

    native_workflow = None
    if css:
        native_workflow = dict(NATIVE_WORKFLOW_ROUTES["css"])
        native_workflow["reason"] = "registered Huawei Cloud CSS requests use the native css_auto specialist"
    if (service and intent in {"diagnose", "investigate"}
            and selected in (["E05", "E04"], ["E05", "E04", "E06"])):
        native_workflow = dict(NATIVE_WORKFLOW_ROUTES["observability"])
        native_workflow["reason"] = (
            "complex application diagnosis uses native parallel E05/E04 evidence collection; "
            "E06 is added only when the E05 result supports a replan"
        )

    return {
        "schema_version": 1,
        "intent": intent,
        "plan_kind": "multi" if len(selected) > 1 else "single" if selected else "none",
        "primary_epic": primary,
        "primary_role": role,
        "selected_epics": selected,
        "selected_roles": [CAPABILITIES[epic][0] for epic in selected],
        "selected_capabilities": capabilities,
        "routing_reason": reasons,
        "missing_inputs": list(dict.fromkeys(missing)),
        "excluded_candidates": excluded,
        "explicit_inputs": {"job": job, "service": service, "action": action, "profile": profile},
        "native_workflow": native_workflow,
    }
