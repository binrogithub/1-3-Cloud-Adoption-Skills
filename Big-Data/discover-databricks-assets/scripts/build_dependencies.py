#!/usr/bin/env python3
"""Build a best-effort dependency edge list from inventory artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


FIELDS = [
    "source_type", "source_id", "relation", "target_type", "target_id",
    "confidence", "evidence",
]


def edge(
    source_type: str,
    source_id: str,
    relation: str,
    target_type: str,
    target_id: str,
    confidence: str,
    evidence: str = "",
) -> dict[str, str]:
    return dict(zip(FIELDS, (source_type, source_id, relation, target_type, target_id, confidence, evidence)))


def task_kind(task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in (
        "notebook_task", "spark_python_task", "spark_jar_task", "pipeline_task",
        "sql_task", "dashboard_task", "dbt_task", "run_job_task", "python_wheel_task",
    ):
        if key in task:
            return key, task[key] or {}
    return "unknown", {}


def workload_edges(payload: dict[str, Any]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for job in payload.get("jobs") or []:
        job_id = str(job.get("job_id", ""))
        for task in (job.get("settings") or {}).get("tasks") or []:
            task_key = str(task.get("task_key", ""))
            task_id = f"{job_id}:{task_key}"
            edges.append(edge("JOB", job_id, "HAS_TASK", "JOB_TASK", task_id, "exact"))
            for dependency in task.get("depends_on") or []:
                target = f"{job_id}:{dependency.get('task_key', '')}"
                edges.append(edge("JOB_TASK", task_id, "DEPENDS_ON", "JOB_TASK", target, "exact"))
            kind, spec = task_kind(task)
            mappings = {
                "notebook_task": ("notebook_path", "WORKSPACE_NOTEBOOK", "USES_NOTEBOOK"),
                "spark_python_task": ("python_file", "PYTHON_FILE", "USES_FILE"),
                "spark_jar_task": ("main_class_name", "JAR_MAIN_CLASS", "USES_CLASS"),
                "pipeline_task": ("pipeline_id", "PIPELINE", "RUNS_PIPELINE"),
                "run_job_task": ("job_id", "JOB", "RUNS_JOB"),
                "dashboard_task": ("dashboard_id", "DASHBOARD", "REFRESHES_DASHBOARD"),
            }
            if kind in mappings:
                field, target_type, relation = mappings[kind]
                if spec.get(field) is not None:
                    edges.append(
                        edge("JOB_TASK", task_id, relation, target_type, str(spec[field]), "exact")
                    )
    for pipeline in payload.get("pipelines") or []:
        pipeline_id = str(pipeline.get("pipeline_id", ""))
        spec = pipeline.get("spec") or {}
        for library in spec.get("libraries") or []:
            for kind, value in library.items():
                if isinstance(value, dict):
                    target = str(value.get("path") or value.get("uri") or json.dumps(value, sort_keys=True))
                else:
                    target = str(value)
                edges.append(edge("PIPELINE", pipeline_id, "USES_LIBRARY", kind.upper(), target, "exact"))
        catalog = spec.get("catalog")
        schema = spec.get("target") or spec.get("schema")
        if catalog:
            edges.append(edge("PIPELINE", pipeline_id, "TARGETS", "CATALOG", str(catalog), "exact"))
        if schema:
            target = f"{catalog}.{schema}" if catalog else str(schema)
            edges.append(edge("PIPELINE", pipeline_id, "TARGETS", "SCHEMA", target, "exact"))
    return edges


def object_edges(path: Path) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    identifier = re.compile(r"`([^`]+)`\.`([^`]+)`\.`([^`]+)`")
    with path.open(encoding="utf-8", newline="") as handle:
        for obj in csv.DictReader(handle):
            full_name = obj.get("full_name", "")
            location = obj.get("storage_location", "")
            if location:
                edges.append(
                    edge(obj.get("object_type", "OBJECT"), full_name, "STORED_AT", "STORAGE_LOCATION", location, "exact")
                )
            if obj.get("object_type") != "VIEW":
                continue
            ddl = obj.get("ddl", "")
            for match in identifier.finditer(ddl):
                target = ".".join(match.groups())
                if target != full_name:
                    edges.append(
                        edge("VIEW", full_name, "REFERENCES", "DATA_OBJECT", target, "heuristic", match.group(0))
                    )
    return edges


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", type=Path, required=True)
    parser.add_argument("--workloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.workloads.read_text(encoding="utf-8"))
    edges = workload_edges(payload) + object_edges(args.objects)
    unique = {
        tuple(item[field] for field in FIELDS): item
        for item in edges
        if item["source_id"] and item["target_id"]
    }
    rows = sorted(unique.values(), key=lambda item: tuple(item[field] for field in FIELDS[:5]))
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} dependency edges to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
