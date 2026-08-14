#!/usr/bin/env python3
"""Export Databricks jobs, tasks, job clusters, and pipelines to CSV and JSON."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


FIELDS = [
    "record_type",
    "object_id",
    "parent_id",
    "name",
    "task_key",
    "task_type",
    "creator",
    "run_as",
    "state",
    "health",
    "schedule_or_trigger_json",
    "source_paths",
    "compute_reference",
    "dependencies_json",
    "libraries_json",
    "parameters_json",
    "configuration_json",
    "created_time",
    "updated_time",
    "tags_json",
    "full_definition_json",
]

TASK_TYPES = (
    "notebook_task",
    "spark_python_task",
    "spark_jar_task",
    "spark_submit_task",
    "pipeline_task",
    "python_wheel_task",
    "sql_task",
    "dashboard_task",
    "dbt_task",
    "run_job_task",
    "condition_task",
    "for_each_task",
    "clean_rooms_notebook_task",
)

SENSITIVE_KEY = re.compile(
    r"(^|[_-])(password|passwd|secret|token|private[_-]?key|client[_-]?secret|access[_-]?key)($|[_-])",
    re.IGNORECASE,
)


def redact_sensitive(value: Any) -> Any:
    """Redact embedded credential values while preserving secret-reference strings."""
    if isinstance(value, dict):
        return {
            key: "<redacted>" if SENSITIVE_KEY.search(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def compact(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def read_credentials(path: Path) -> tuple[str, str]:
    env_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    env_token = os.environ.get("DATABRICKS_TOKEN", "")
    if env_host and env_token:
        return env_host, env_token
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    host = next((line.rstrip("/") for line in lines if line.startswith("https://")), "")
    token = next((line for line in lines if line.startswith("dapi")), "")
    if not host or not token:
        raise ValueError(f"Could not find a Databricks HTTPS URL and PAT in {path}")
    return host, token


class Api:
    def __init__(self, host: str, token: str) -> None:
        self.host = host
        self.token = token

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.host}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
        )
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                if exc.code in {429, 500, 502, 503, 504} and attempt < 5:
                    retry_after = exc.headers.get("Retry-After")
                    delay = min(60.0, float(retry_after) if retry_after else 2.0 ** attempt)
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt < 5:
                    time.sleep(min(30.0, 2.0 ** attempt))
                    continue
                raise RuntimeError(f"GET {path} failed: {exc.reason}") from exc
        raise AssertionError("unreachable")

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        params = {"limit": "25", "expand_tasks": "true"}
        while True:
            payload = self.get("/api/2.1/jobs/list", params)
            jobs.extend(payload.get("jobs") or [])
            token = payload.get("next_page_token")
            if not token:
                return jobs
            params["page_token"] = str(token)

    def list_pipelines(self) -> list[dict[str, Any]]:
        pipelines: list[dict[str, Any]] = []
        params = {"max_results": "25"}
        while True:
            payload = self.get("/api/2.0/pipelines", params)
            pipelines.extend(payload.get("statuses") or [])
            token = payload.get("next_page_token")
            if not token:
                return pipelines
            params["page_token"] = str(token)


def blank_row() -> dict[str, str]:
    return {field: "" for field in FIELDS}


def schedule(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        key: settings[key]
        for key in ("schedule", "trigger", "continuous")
        if settings.get(key) is not None
    }


def task_type(task: dict[str, Any]) -> str:
    return next((key for key in TASK_TYPES if key in task), "unknown")


def task_sources(task: dict[str, Any], kind: str) -> list[str]:
    spec = task.get(kind) or {}
    paths: list[str] = []
    for key in (
        "notebook_path",
        "python_file",
        "jar_uri",
        "file",
        "project_directory",
        "schema",
        "query_id",
        "dashboard_id",
        "alert_id",
    ):
        if spec.get(key):
            paths.append(str(spec[key]))
    if kind == "pipeline_task" and spec.get("pipeline_id"):
        paths.append(f"pipeline_id:{spec['pipeline_id']}")
    if kind == "run_job_task" and spec.get("job_id"):
        paths.append(f"job_id:{spec['job_id']}")
    return paths


def task_compute(task: dict[str, Any]) -> str:
    if task.get("existing_cluster_id"):
        return f"existing_cluster_id:{task['existing_cluster_id']}"
    if task.get("job_cluster_key"):
        return f"job_cluster_key:{task['job_cluster_key']}"
    if task.get("new_cluster"):
        return "new_cluster:" + compact(task["new_cluster"])
    sql_task = task.get("sql_task") or {}
    warehouse_id = sql_task.get("warehouse_id")
    if warehouse_id:
        return f"warehouse_id:{warehouse_id}"
    if task.get("environment_key"):
        return f"environment_key:{task['environment_key']}"
    return ""


def job_rows(job: dict[str, Any]) -> list[dict[str, str]]:
    settings = job.get("settings") or {}
    job_id = str(job.get("job_id", ""))
    parent = blank_row()
    parent.update(
        {
            "record_type": "JOB",
            "object_id": job_id,
            "name": str(settings.get("name", "")),
            "creator": str(job.get("creator_user_name", "")),
            "run_as": str(job.get("run_as_user_name", "")),
            "state": str(settings.get("pause_status", "")),
            "schedule_or_trigger_json": compact(schedule(settings)),
            "compute_reference": compact(settings.get("job_clusters")),
            "parameters_json": compact(settings.get("parameters")),
            "configuration_json": compact(
                {
                    key: settings.get(key)
                    for key in (
                        "format",
                        "max_concurrent_runs",
                        "timeout_seconds",
                        "queue",
                        "email_notifications",
                        "webhook_notifications",
                        "notification_settings",
                        "environments",
                        "deployment",
                    )
                    if settings.get(key) is not None
                }
            ),
            "created_time": str(job.get("created_time", "")),
            "tags_json": compact(settings.get("tags")),
            "full_definition_json": compact(job),
        }
    )
    rows = [parent]
    for task in settings.get("tasks") or []:
        kind = task_type(task)
        row = blank_row()
        row.update(
            {
                "record_type": "JOB_TASK",
                "object_id": f"{job_id}:{task.get('task_key', '')}",
                "parent_id": job_id,
                "name": str(settings.get("name", "")),
                "task_key": str(task.get("task_key", "")),
                "task_type": kind,
                "creator": str(job.get("creator_user_name", "")),
                "run_as": str(job.get("run_as_user_name", "")),
                "source_paths": "\n".join(task_sources(task, kind)),
                "compute_reference": task_compute(task),
                "dependencies_json": compact(task.get("depends_on")),
                "libraries_json": compact(task.get("libraries")),
                "parameters_json": compact((task.get(kind) or {}).get("parameters")),
                "configuration_json": compact(
                    {
                        key: task.get(key)
                        for key in (
                            "timeout_seconds",
                            "max_retries",
                            "min_retry_interval_millis",
                            "retry_on_timeout",
                            "run_if",
                            "email_notifications",
                            "notification_settings",
                            "health",
                        )
                        if task.get(key) is not None
                    }
                ),
                "full_definition_json": compact(task),
            }
        )
        rows.append(row)
    for cluster in settings.get("job_clusters") or []:
        key = str(cluster.get("job_cluster_key", ""))
        row = blank_row()
        row.update(
            {
                "record_type": "JOB_CLUSTER",
                "object_id": f"{job_id}:{key}",
                "parent_id": job_id,
                "name": str(settings.get("name", "")),
                "task_key": key,
                "creator": str(job.get("creator_user_name", "")),
                "run_as": str(job.get("run_as_user_name", "")),
                "compute_reference": key,
                "configuration_json": compact(cluster.get("new_cluster")),
                "full_definition_json": compact(cluster),
            }
        )
        rows.append(row)
    return rows


def pipeline_sources(spec: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for library in spec.get("libraries") or []:
        for kind, value in library.items():
            if isinstance(value, dict):
                path = value.get("path") or value.get("uri")
                paths.append(f"{kind}:{path}" if path else f"{kind}:{compact(value)}")
            else:
                paths.append(f"{kind}:{value}")
    return paths


def pipeline_row(pipeline: dict[str, Any]) -> dict[str, str]:
    spec = pipeline.get("spec") or {}
    pipeline_id = str(pipeline.get("pipeline_id", ""))
    row = blank_row()
    row.update(
        {
            "record_type": "PIPELINE",
            "object_id": pipeline_id,
            "name": str(pipeline.get("name") or spec.get("name") or ""),
            "creator": str(pipeline.get("creator_user_name", "")),
            "run_as": str(pipeline.get("run_as_user_name", "")),
            "state": str(pipeline.get("state", "")),
            "health": str(pipeline.get("health", "")),
            "schedule_or_trigger_json": compact(spec.get("trigger")),
            "source_paths": "\n".join(pipeline_sources(spec)),
            "compute_reference": compact(
                {"clusters": spec.get("clusters"), "serverless": spec.get("serverless")}
            ),
            "libraries_json": compact(spec.get("libraries")),
            "configuration_json": compact(
                {
                    key: spec.get(key)
                    for key in (
                        "catalog",
                        "target",
                        "schema",
                        "storage",
                        "configuration",
                        "continuous",
                        "development",
                        "photon",
                        "edition",
                        "channel",
                        "allow_duplicate_names",
                        "notifications",
                    )
                    if spec.get(key) is not None
                }
            ),
            "created_time": str(pipeline.get("creation_time", "")),
            "updated_time": str(pipeline.get("last_modified", "")),
            "full_definition_json": compact(pipeline),
        }
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, default=Path("f_credentials.env"))
    parser.add_argument(
        "--csv-output", type=Path, default=Path("databricks_jobs_pipelines_inventory.csv")
    )
    parser.add_argument(
        "--json-output", type=Path, default=Path("databricks_jobs_pipelines_inventory.json")
    )
    args = parser.parse_args()
    host, token = read_credentials(args.credentials)
    api = Api(host, token)

    job_summaries = api.list_jobs()
    jobs = [
        redact_sensitive(api.get("/api/2.1/jobs/get", {"job_id": str(item["job_id"])}))
        for item in job_summaries
    ]
    pipeline_summaries = api.list_pipelines()
    pipelines = [
        redact_sensitive(api.get(f"/api/2.0/pipelines/{item['pipeline_id']}"))
        for item in pipeline_summaries
    ]

    rows: list[dict[str, str]] = []
    for job in jobs:
        rows.extend(job_rows(job))
    rows.extend(pipeline_row(pipeline) for pipeline in pipelines)
    rows.sort(key=lambda row: (row["record_type"], row["name"], row["object_id"]))
    with args.csv_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    args.json_output.write_text(
        json.dumps({"jobs": jobs, "pipelines": pipelines}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["record_type"]] = counts.get(row["record_type"], 0) + 1
    print(f"Wrote {len(rows)} CSV rows to {args.csv_output}")
    print(f"Wrote {len(jobs)} jobs and {len(pipelines)} pipelines to {args.json_output}")
    print("Counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
