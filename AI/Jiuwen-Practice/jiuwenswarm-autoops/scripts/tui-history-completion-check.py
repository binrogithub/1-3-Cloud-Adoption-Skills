#!/usr/bin/env python3
"""Validate that a TUI one-shot session completed its AutoOps turn.

This reads durable JiuwenSwarm history rather than terminal redraw output. It
also rejects exploratory tool calls that bypass the project-owned PM route.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ALLOWED_COMMANDS = (
    "autoops-project-manager.py",
    "autoops-context-register.py",
    "observability-investigate.py",
    "observability-correlate.py",
    "project-manager-orchestrator.py",
    "autoops-control.py",
    "autoops-task-control.py",
    "autoops-watch-policy.py",
    "verify-service-recovery.py",
    "verify-k8s-business.py",
    "k8s-inspect.py",
    "k8s-restore-replicas.py",
)
FORBIDDEN_TOOLS = {"read_file", "list_files", "grep", "glob", "terminal"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_READ_ROOTS = (PROJECT_ROOT / ".runtime", Path("/tmp/openjiuwen_bash_outputs"))
NATIVE_WORKFLOW_ASSET = str(PROJECT_ROOT / "swarmflow" / "ro05-parallel-observability-v1.py")
CSS_NATIVE_WORKFLOW_ASSET = str(PROJECT_ROOT / "swarmflow" / "css-autoscale-v1.py")


def is_published_asset_probe(command: str) -> bool:
    """Allow only a read-only existence check for the published workflow asset."""
    normalized = " ".join(command.split())
    return normalized in {
        f"ls -la {NATIVE_WORKFLOW_ASSET}",
        f"ls -l {NATIVE_WORKFLOW_ASSET}",
        f"test -f {NATIVE_WORKFLOW_ASSET}",
        f"ls -la {CSS_NATIVE_WORKFLOW_ASSET}",
        f"ls -l {CSS_NATIVE_WORKFLOW_ASSET}",
        f"test -f {CSS_NATIVE_WORKFLOW_ASSET}",
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ready": False, "error": "history path required"}))
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(json.dumps({"ready": False, "error": "history not found"}))
        return 1

    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    user_messages = [e for e in events if e.get("event_type") is None and e.get("role") == "user"]
    first_content = str(user_messages[0].get("content", "")) if user_messages else ""
    calls = [e for e in events if e.get("event_type") == "chat.tool_call"]
    results = [e for e in events if e.get("event_type") == "chat.tool_result"]
    operational = []
    forbidden = []
    unsafe_actions = []
    for event in calls:
        call = event.get("tool_call") or {}
        name = str(call.get("name", ""))
        arguments = str(call.get("arguments", ""))
        command_text = arguments
        if name == "bash":
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = None
            if isinstance(parsed_arguments, dict) and isinstance(parsed_arguments.get("command"), str):
                # TUI history stores both the executable command and a human
                # description. Security checks must inspect the executable
                # command only; descriptions often explain that --execute is
                # intentionally absent and must not be treated as arguments.
                command_text = parsed_arguments["command"]
        safe_skill_read = (
            name in {"read_file", "list_files", "glob"}
            and "skills" in arguments
            and ("SKILL.md" in arguments or "autoops-" in arguments)
        )
        safe_project_evidence_read = False
        if name == "read_file":
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = None
            evidence_path = parsed_arguments.get("file_path") if isinstance(parsed_arguments, dict) else None
            if isinstance(evidence_path, str):
                try:
                    resolved_path = Path(evidence_path).resolve()
                    safe_project_evidence_read = any(
                        resolved_path.is_relative_to(root.resolve()) for root in SAFE_READ_ROOTS
                    )
                except OSError:
                    safe_project_evidence_read = False
        if name in FORBIDDEN_TOOLS and not (safe_skill_read or safe_project_evidence_read):
            forbidden.append(name)
        if (name == "bash"
                and not any(command in command_text for command in ALLOWED_COMMANDS)
                and not is_published_asset_probe(command_text)):
            forbidden.append("bash:outside-autoops-route")
        if name == "bash" and any(command in command_text for command in ALLOWED_COMMANDS):
            operational.append(event)
            if "--execute" in command_text or "--mode auto" in command_text:
                unsafe_actions.append(command_text)
        if name == "swarmflow":
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = None
            asset = parsed_arguments.get("script_path") if isinstance(parsed_arguments, dict) else None
            if asset in {NATIVE_WORKFLOW_ASSET, CSS_NATIVE_WORKFLOW_ASSET}:
                operational.append(event)
            else:
                forbidden.append("swarmflow:outside-published-autoops-workflow")
    # The production bootstrap routes ordinary natural-language requests to
    # ProjectManager.  A prefix is an explicit test/launcher hint, not a user
    # requirement; only reject an unprefixed turn when it also failed to show
    # a project-owned operational route.
    if not first_content.startswith("#autoops-project-manager ") and not operational:
        forbidden.append("missing-project-manager-prefix")

    last_action_index = -1
    last_result_index = -1
    last_final_index = -1
    final_text = ""
    for index, event in enumerate(events):
        event_type = event.get("event_type")
        if event_type in {"chat.tool_call", "chat.tool_update", "chat.tool_result", "chat.final"}:
            last_action_index = index
        if event_type == "chat.tool_result":
            last_result_index = index
        if event_type == "chat.final" and str(event.get("content", "")).strip():
            last_final_index = index
            final_text = str(event.get("content", ""))

    continuity_boundary = any(marker in final_text for marker in
                              ("Continuity Gap", "连续性缺口", "Cannot Continue"))
    input_boundary = any(marker in final_text.casefold() for marker in
                         ("缺少 profile", "缺少 profile-ref", "missing profile",
                          "profile reference", "profile-ref is required",
                          "requires an explicit", "需要提供 profile"))

    normal_completion = bool(
        1 <= len(operational) <= 4
        and results
        and last_final_index >= last_result_index >= 0
        and last_final_index == last_action_index
    )
    boundary_completion = bool((continuity_boundary or input_boundary) and last_final_index >= 0)
    ready = bool((normal_completion or boundary_completion)
                 and not forbidden and not unsafe_actions)
    payload = {
        "ready": ready,
        "user_prefixed": first_content.startswith("#autoops-project-manager "),
        "operational_calls": len(operational),
        "tool_results": len(results),
        "last_final_index": last_final_index,
        "last_result_index": last_result_index,
        "last_action_index": last_action_index,
        "forbidden_tools": sorted(set(forbidden)),
        "unsafe_actions": len(unsafe_actions),
        "continuity_boundary": continuity_boundary,
        "input_boundary": input_boundary,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
