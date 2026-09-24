#!/usr/bin/env python3
"""Collect redacted RO-14 performance measurements from one native run.

The TUI history supplies model latency and first-token acknowledgement.  The
matching JiuwenSwarm OTEL trace supplies explicit tool span duration/count.
This collector never copies prompts, tool arguments, or tool output.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _payloads(history: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in history.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = item.get("payload", item)
        if isinstance(payload, dict):
            result.append(payload)
    return result


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not item.get("key"):
            continue
        value = item.get("value")
        if isinstance(value, dict) and value:
            result[str(item["key"])] = next(iter(value.values()))
    return result


def _spans(trace: Path | None, session_id: str, run_id: str) -> list[dict[str, Any]]:
    run_token = run_id.replace("_", "-")
    result: list[dict[str, Any]] = []
    if trace is None or not trace.is_file():
        return result
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        for resource in item.get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    if not isinstance(span, dict):
                        continue
                    attrs = _attributes(span)
                    if attrs.get("session.id") != session_id:
                        continue
                    tool_id = str(attrs.get("gen_ai.tool.id") or "")
                    if run_token not in tool_id:
                        continue
                    if not attrs.get("gen_ai.tool.name") or not attrs.get("gen_ai.tool.output"):
                        continue
                    try:
                        start = int(span["startTimeUnixNano"])
                        end = int(span["endTimeUnixNano"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if end < start:
                        continue
                    result.append({
                        "tool_name": str(attrs["gen_ai.tool.name"]),
                        "start": start,
                        "end": end,
                    })
    return result


def collect(history: Path, trace: Path | None, scenario_id: str, run_id: str) -> dict[str, Any]:
    payloads = _payloads(history)
    session_ids = {str(item.get("session_id")) for item in payloads if item.get("session_id")}
    if len(session_ids) != 1:
        raise ValueError("history must contain exactly one session_id")
    session_id = next(iter(session_ids))
    usage = [item.get("usage_metadata", {}) | item for item in payloads
             if item.get("event_type") == "chat.llm_usage"]
    latencies = [float(item["total_latency_ms"]) for item in usage
                 if item.get("total_latency_ms") is not None]
    acknowledgements = [float(item["ttft_ms"]) for item in usage
                        if item.get("ttft_ms") is not None]
    spans = _spans(trace, session_id, run_id)
    if not spans:
        return _collect_from_history(payloads, scenario_id, run_id, session_id)
    if not latencies or not acknowledgements:
        raise ValueError("history has no chat.llm_usage latency and acknowledgement fields")
    spans.sort(key=lambda span: (span["start"], span["end"]))
    gaps = [max(0, (right["start"] - left["end"]) / 1_000_000_000)
            for left, right in zip(spans, spans[1:])]
    query_spans = [span for span in spans if span["tool_name"] not in {"skill_tool", "structured_output"}]
    return {
        "acceptance_scope": "RO-14-04",
        "evidence_level": "native-runtime",
        "scenario_id": scenario_id,
        "run_id": run_id,
        "session_id": session_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "model_seconds": round(sum(latencies) / 1000, 3),
        "tool_seconds": round(sum((span["end"] - span["start"]) for span in spans) / 1_000_000_000, 3),
        "query_count": len(query_spans),
        "first_ack_seconds": round(min(acknowledgements) / 1000, 3),
        "quiet_gap_seconds": round(max(gaps, default=0), 3),
        "tool_span_count": len(spans),
        "metric_method": "TUI chat.llm_usage plus matching OTEL tool spans; content excluded",
    }


def _collect_from_history(payloads: list[dict[str, Any]], scenario_id: str,
                          run_id: str, session_id: str) -> dict[str, Any]:
    """Derive bounded wall-clock metrics when TUI omits chat.llm_usage/OTEL."""
    timed = [(float(item["timestamp"]), item) for item in payloads
             if item.get("timestamp") is not None]
    if not timed:
        raise ValueError("history has no event timestamps for wall-clock metrics")
    timed.sort(key=lambda item: item[0])
    user_times = [stamp for stamp, item in timed if item.get("role") == "user"]
    if not user_times:
        raise ValueError("history has no user timestamp")
    start = user_times[0]
    final_times = [stamp for stamp, item in timed
                   if item.get("event_type") == "chat.final" and str(item.get("content", "")).strip()]
    if not final_times:
        raise ValueError("history has no assistant final timestamp")
    tool_calls = [stamp for stamp, item in timed
                  if item.get("event_type") == "chat.tool_call"
                  and str((item.get("tool_call") or {}).get("name", "")) != "skill_tool"]
    tool_results = [stamp for stamp, item in timed if item.get("event_type") == "chat.tool_result"]
    tool_seconds = 0.0
    for call, result in zip(tool_calls, tool_results):
        tool_seconds += max(0.0, result - call)
    first_ack = next((stamp - start for stamp, item in timed
                      if item.get("event_type") == "chat.final" and str(item.get("content", "")).strip()), None)
    if first_ack is None:
        raise ValueError("history has no assistant acknowledgement timestamp")
    gaps = [max(0.0, right[0] - left[0]) for left, right in zip(timed, timed[1:])]
    total_seconds = max(0.0, final_times[-1] - start)
    return {
        "acceptance_scope": "RO-14-04",
        "evidence_level": "real-tui",
        "scenario_id": scenario_id,
        "run_id": run_id,
        "session_id": session_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "model_seconds": round(max(0.0, total_seconds - tool_seconds), 3),
        "tool_seconds": round(tool_seconds, 3),
        "query_count": len(tool_calls),
        "first_ack_seconds": round(max(0.0, first_ack), 3),
        "quiet_gap_seconds": round(max(gaps, default=0.0), 3),
        "tool_event_count": len(tool_calls),
        "metric_method": "TUI event timestamp wall-clock fallback; chat.llm_usage and OTEL tool spans were absent; content excluded",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect one redacted native AutoOps performance measurement")
    parser.add_argument("history", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.history.is_file():
            raise ValueError("history must be a file")
        if args.trace is not None and not args.trace.is_file():
            raise ValueError("trace must be a file when supplied")
        payload = collect(args.history, args.trace, args.scenario_id, args.run_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "output": str(args.output),
                          "query_count": payload["query_count"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
