#!/usr/bin/env python3
"""Extract a redacted native SwarmFlow evidence record from runtime history.

This is an evidence adapter only.  It does not start a workflow, infer a
missing expert, or copy tool output.  A native workflow event must contain the
run and child agent; an explicit tool span from the matching JiuwenSwarm
trace is required before an expert is reported as tool-qualified.  The trace
fallback exists because the current TUI workflow event omits agent activity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _structured_outcome(value: Any) -> tuple[str, str | None]:
    """Return a redacted presence marker and digest for an agent outcome."""
    if isinstance(value, dict) and value:
        return "present", _digest(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value.strip()
        if parsed not in ({}, ""):
            return "present", _digest(parsed)
    return "absent", None


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not item.get("key"):
            continue
        value = item.get("value")
        if isinstance(value, dict) and value:
            attributes[str(item["key"])] = next(iter(value.values()))
    return attributes


def _trace_tool_events(trace: Path, parent_run_ids: set[str], experts_by_role: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Read only matching OTEL tool spans and retain hashes, never content."""
    events: list[dict[str, Any]] = []
    if trace is None or not trace.is_file():
        return events
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        for resource_span in payload.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    if not isinstance(span, dict):
                        continue
                    attributes = _attributes(span)
                    tool_name = str(attributes.get("gen_ai.tool.name") or "").strip()
                    tool_id = str(attributes.get("gen_ai.tool.id") or "").strip()
                    output = attributes.get("gen_ai.tool.output")
                    if not tool_name or not tool_id or output in (None, ""):
                        continue
                    matched_parent = next(
                        (parent for parent in parent_run_ids
                         if f"_{parent.replace('_', '-')}-" in tool_id), None
                    )
                    if not matched_parent:
                        continue
                    role = next(
                        (candidate for candidate in experts_by_role
                         if f"-{candidate}-" in tool_id), ""
                    )
                    if not role:
                        continue
                    events.append({
                        "expert_role": role,
                        "parent_run_id": matched_parent,
                        "child_run_id": experts_by_role[role][-1],
                        "phase": "trace",
                        "tool_name": tool_name,
                        "tool_result": "present",
                        "tool_result_digest": _digest(output),
                        "trace_span": span.get("name", "tool"),
                    })
    return events


def _trace_workflow_experts(trace: Path | None, session_id: str) -> tuple[set[str], dict[tuple[str, str], dict[str, Any]]]:
    """Recover workflow and expert identities from JiuwenSwarm OTEL progress spans.

    TUI history can contain only the launch/result frames while the background
    SwarmFlow details are emitted to OTEL.  The progress payload is structured
    runtime evidence, so it is safe to join it by session and keep only IDs,
    labels, status and hashes.
    """
    if trace is None or not trace.is_file():
        return set(), {}
    spans: list[dict[str, Any]] = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        for resource_span in payload.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    if not isinstance(span, dict):
                        continue
                    attrs = _attributes(span)
                    if (attrs.get("session.id") == session_id
                            or attrs.get("agentteam.session.id") == session_id
                            or attrs.get("agentteam.team.name") == f"team_{session_id}"):
                        spans.append(span)
    parents: set[str] = set()
    labels: set[str] = set()
    outcomes: dict[tuple[str, str], tuple[str, Any]] = {}
    for span in spans:
        attrs = _attributes(span)
        raw = attrs.get("langfuse.observation.input")
        if not isinstance(raw, str):
            continue
        try:
            observation = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(observation, dict):
            continue
        if observation.get("workflow_name") != "ro05-parallel-observability-v1":
            continue
        parent = str(observation.get("run_id") or "").strip()
        if not parent:
            continue
        parents.add(parent)
        label = str(observation.get("label") or "").strip()
        if label in {"log-investigator", "metrics-observer", "event-investigator"}:
            labels.add(label)
            if observation.get("kind") == "agent_completed":
                outcomes[(parent, label)] = (str(observation.get("phase") or ""), observation.get("outcome"))
    experts: dict[tuple[str, str], dict[str, Any]] = {}
    for parent in parents:
        normalized_parent = parent.replace("_", "-")
        for label in labels:
            child = next((str(_attributes(span).get("agentteam.agent.id") or "")
                          for span in spans
                          if str(_attributes(span).get("agentteam.agent.id") or "").startswith(
                              f"{normalized_parent}-{label}-")), "")
            if not child:
                continue
            phase, outcome = outcomes.get((parent, label), ("", None))
            outcome_status, outcome_digest = _structured_outcome(outcome)
            experts[(parent, child)] = {
                "parent_run_id": parent,
                "child_run_id": child,
                "expert_role": label,
                "phase": phase,
                "status": "completed" if outcome is not None else "unknown",
                "tool_activity_count": 0,
                "structured_result_status": outcome_status,
            }
            if outcome_digest:
                experts[(parent, child)]["structured_result_digest"] = outcome_digest
    return parents, experts


def _workflow(payload: dict[str, Any]) -> dict[str, Any] | None:
    # ``jiuwenswarm chat --jsonl`` wraps gateway frames as
    # {"type":"event", "payload": {...}} while TUI history stores the
    # payload directly.  Accept both transport shapes without retaining the
    # original frame or any model/tool content.
    nested = payload.get("payload")
    if isinstance(nested, dict):
        workflow = nested.get("workflow")
        if isinstance(workflow, dict):
            return workflow
    candidate = payload.get("workflow")
    if isinstance(candidate, dict):
        return candidate
    event = payload.get("event")
    if isinstance(event, dict) and isinstance(event.get("workflow"), dict):
        return event["workflow"]
    return None


def collect(history: Path, trace: Path | None = None,
            acceptance_scope: str = "RO-14-03") -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    team_events = 0
    workflow_events = 0
    workflow_run_ids: set[str] = set()
    observed_experts: dict[tuple[str, str], dict[str, Any]] = {}
    for line in history.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("event_type") == "team.member":
            team_events += 1
        workflow = _workflow(payload)
        if workflow is None:
            continue
        workflow_events += 1
        parent_run_id = str(workflow.get("id") or workflow.get("run_id") or "").strip()
        if not parent_run_id:
            continue
        workflow_run_ids.add(parent_run_id)
        for phase in workflow.get("phases", []):
            if not isinstance(phase, dict):
                continue
            parent_phase = str(phase.get("parent_phase") or phase.get("name") or "").strip()
            for agent in phase.get("agents", []):
                if not isinstance(agent, dict):
                    continue
                child_run_id = str(agent.get("id") or agent.get("agent_id") or "").strip()
                expert_role = str(agent.get("name") or agent.get("label") or "").strip()
                if not child_run_id or not expert_role:
                    continue
                outcome_status, outcome_digest = _structured_outcome(agent.get("outcome"))
                observed_experts[(parent_run_id, child_run_id)] = {
                    "parent_run_id": parent_run_id,
                    "child_run_id": child_run_id,
                    "expert_role": expert_role,
                    "phase": parent_phase,
                    "status": str(agent.get("status") or "unknown"),
                    "tool_activity_count": sum(
                        1 for activity in agent.get("activity", [])
                        if isinstance(activity, dict) and activity.get("type") in {"tool_call", "tool_result"}
                    ),
                    "structured_result_status": outcome_status,
                }
                if outcome_digest:
                    observed_experts[(parent_run_id, child_run_id)]["structured_result_digest"] = outcome_digest
                for activity in agent.get("activity", []):
                    if not isinstance(activity, dict) or activity.get("type") != "tool_result":
                        continue
                    tool_name = str(activity.get("tool_name") or "").strip()
                    preview = activity.get("tool_result_preview")
                    if not tool_name or preview in (None, ""):
                        continue
                    events.append({
                        "expert_role": expert_role,
                        "parent_run_id": parent_run_id,
                        "child_run_id": child_run_id,
                        "phase": parent_phase,
                        "tool_name": tool_name,
                        "tool_result": "present",
                        "tool_result_digest": _digest(preview),
                        "status": str(agent.get("status") or "unknown"),
                    })
    history_session_id = history.parent.name
    trace_workflow_ids, trace_experts = _trace_workflow_experts(trace, history_session_id)
    workflow_run_ids.update(trace_workflow_ids)
    for key, expert in trace_experts.items():
        observed_experts.setdefault(key, expert)
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        unique[(event["parent_run_id"], event["child_run_id"], event["tool_name"])] = event
    native_events = list(unique.values())
    experts_by_role: dict[str, list[str]] = {}
    for expert in observed_experts.values():
        role = expert.get("expert_role")
        child = expert.get("child_run_id")
        if role and child:
            experts_by_role.setdefault(role, []).append(child)
    trace_events = _trace_tool_events(trace, workflow_run_ids, experts_by_role)
    for event in trace_events:
        key = (event["parent_run_id"], event["child_run_id"], event["tool_name"])
        unique[key] = event
    native_events = list(unique.values())
    return {
        "schema_version": 1,
        "acceptance_scope": acceptance_scope,
        "evidence_level": "native-runtime",
        "source_history": str(history),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "workflow_event_count": workflow_events,
        "workflow_run_ids": sorted(workflow_run_ids),
        "team_event_count": team_events,
        "observed_experts": list(observed_experts.values()),
        "native_expert_events": native_events,
        "trace_tool_event_count": len(trace_events),
        "qualified_expert_count": len({event["expert_role"] for event in native_events}),
        "structured_expert_result_count": sum(
            1 for expert in observed_experts.values()
            if expert.get("structured_result_status") == "present"
        ),
        "status": "PASS" if len({event["expert_role"] for event in native_events}) >= 2 else "INCONCLUSIVE",
        "limitation": "Structured workflow outcomes prove an expert returned a result, but RO-14-03 PASS still requires explicit tool_result records. When TUI activity is empty, matching OTEL tool spans may supply that receipt; chat text and team.member alone are not tool evidence.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract native JiuwenSwarm expert evidence from history JSONL")
    parser.add_argument("history", type=Path)
    parser.add_argument("--trace", type=Path,
                        help="optional JiuwenSwarm OTEL JSONL trace for matching tool receipts")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acceptance-scope", default="RO-14-03",
                        help="acceptance scope label for the evidence record")
    args = parser.parse_args(argv)
    if not args.history.is_file():
        print(json.dumps({"status": "INPUT_ERROR", "error": f"history not found: {args.history}"}, ensure_ascii=False))
        return 2
    try:
        payload = collect(args.history, args.trace, args.acceptance_scope)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": payload["status"], "output": str(args.output),
                          "qualified_expert_count": payload["qualified_expert_count"]}, ensure_ascii=False))
        return 0 if payload["status"] == "PASS" else 1
    except OSError as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
