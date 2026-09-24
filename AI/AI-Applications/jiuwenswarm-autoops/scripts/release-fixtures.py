#!/usr/bin/env python3
"""Manage an isolated observability truth fixture for release tests.

The fixture creates uniquely named application data and a ground-truth file.
It does not install services or write to Loki, Prometheus, OpenSearch, or any
customer path. Real component queries can consume the declared identifiers
after an operator wires the fixture into those components.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from autoops_datasource_health import probe as probe_datasource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/release/fixtures/observability.json"
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,31}$")


def read_config(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"fixture config must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("fixture config schema_version 1 is required")
    for key in ("application_template", "service_template", "target_template", "scope_template"):
        if not isinstance(value.get(key), str) or "${RUN_ID}" not in value[key]:
            raise ValueError(f"fixture config template is invalid: {key}")
    return value


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run-id must be 3-32 lowercase letters, digits, or hyphens")
    return run_id


def identity(config: dict[str, Any], run_id: str) -> dict[str, str]:
    replace = lambda value: str(value).replace("${RUN_ID}", run_id)
    return {
        "run_id": run_id,
        "application": replace(config["application_template"]),
        "service": replace(config["service_template"]),
        "target": replace(config["target_template"]),
        "environment": str(config["environment"]),
        "scope_id": replace(config["scope_template"]),
        "loki_service_label": replace(config["service_template"]),
        "prometheus_job": replace(config["prometheus"]["job_template"]),
        "opensearch_index": replace(config["opensearch"]["index_template"]),
    }


def fixture_dir(work_dir: Path, run_id: str) -> Path:
    work_dir = work_dir.expanduser().resolve()
    if work_dir == Path("/") or Path("/root") in (work_dir, *work_dir.parents):
        raise ValueError("fixture work-dir must not be /root or a parent of /root")
    target = work_dir / f"fixture-{validate_run_id(run_id)}"
    if target.is_symlink():
        raise ValueError(f"refusing symlink fixture directory: {target}")
    return target


def regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"fixture path must be a regular file: {path}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"refusing symlink fixture file: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def setup(*, work_dir: Path, run_id: str, config_path: Path) -> dict[str, Any]:
    config = read_config(config_path)
    run_id = validate_run_id(run_id)
    target = fixture_dir(work_dir, run_id)
    if target.exists():
        manifest = target / "fixture-manifest.json"
        regular(manifest)
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        if existing.get("run_id") != run_id:
            raise ValueError(f"fixture directory belongs to another run: {target}")
        return {"status": "EXISTS", "run_id": run_id, "fixture_dir": str(target),
                "manifest": str(manifest), "ground_truth": str(target / "ground-truth.json")}
    target.mkdir(parents=True, exist_ok=False)
    ident = identity(config, run_id)
    (target / "logs").mkdir()
    (target / "metrics").mkdir()
    (target / "events").mkdir()
    created_at = int(time.time())
    truth = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": created_at,
        "identity": ident,
        "records": {
            "logs": [{"kind": "normal", "message": f"{ident['service']} request completed"}],
            "metrics": [{"name": "http_requests_total", "labels": {"job": ident["prometheus_job"]}, "value": 1}],
            "events": [{"event_type": "deploy", "service": ident["service"], "correlation_id": f"corr-{run_id}"}],
        },
    }
    (target / "logs/app.log").write_text(
        f"fixture_run_id={run_id} service={ident['service']} level=INFO request completed\n", encoding="utf-8")
    (target / "metrics/app.prom").write_text(
        f"# fixture_run_id={run_id}\nhttp_requests_total{{job=\"{ident['prometheus_job']}\"}} 1\n", encoding="utf-8")
    (target / "events/events.jsonl").write_text(
        json.dumps(truth["records"]["events"][0], ensure_ascii=False) + "\n", encoding="utf-8")
    write_json(target / "ground-truth.json", truth)
    manifest = {
        "schema_version": 1,
        "kind": "AutoOpsObservabilityFixtureManifest",
        "run_id": run_id,
        "fixture_dir": str(target),
        "identity": ident,
        "resources": ["logs/app.log", "metrics/app.prom", "events/events.jsonl", "ground-truth.json"],
        "cleanup_scope": str(target),
        "external_writes": False,
    }
    write_json(target / "fixture-manifest.json", manifest)
    return {"status": "CREATED", "run_id": run_id, "fixture_dir": str(target),
            "manifest": str(target / "fixture-manifest.json"), "ground_truth": str(target / "ground-truth.json")}


def inject(*, work_dir: Path, run_id: str, kind: str) -> dict[str, Any]:
    target = fixture_dir(work_dir, run_id)
    manifest_path = target / "fixture-manifest.json"
    truth_path = target / "ground-truth.json"
    regular(manifest_path)
    regular(truth_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != run_id or truth.get("run_id") != run_id:
        raise ValueError("fixture run identity mismatch")
    message = {"normal": "request completed", "anomaly": "database timeout", "change": "release applied", "unrelated": "other service event"}[kind]
    service = truth["identity"]["service"] if kind != "unrelated" else f"unrelated-{run_id}"
    record = {"kind": kind, "service": service, "message": message, "run_id": run_id}
    if kind in {"normal", "anomaly"}:
        with (target / "logs/app.log").open("a", encoding="utf-8") as stream:
            stream.write(f"fixture_run_id={run_id} service={service} level={'ERROR' if kind == 'anomaly' else 'INFO'} {message}\n")
        truth["records"]["logs"].append(record)
    elif kind == "change":
        with (target / "events/events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event_type": "change", **record}, ensure_ascii=False) + "\n")
        truth["records"]["events"].append(record)
    else:
        truth["records"]["events"].append(record)
    write_json(truth_path, truth)
    return {"status": "INJECTED", "run_id": run_id, "kind": kind, "ground_truth": str(truth_path)}


def check(*, work_dir: Path, run_id: str, endpoints: dict[str, str] | None = None) -> dict[str, Any]:
    target = fixture_dir(work_dir, run_id)
    manifest_path = target / "fixture-manifest.json"
    truth_path = target / "ground-truth.json"
    regular(manifest_path)
    regular(truth_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != run_id or truth.get("run_id") != run_id:
        raise ValueError("fixture run identity mismatch")
    missing = []
    for relative in manifest.get("resources", []):
        path = target / relative
        if not path.is_file() or path.is_symlink():
            missing.append(relative)
    datasource_checks = {}
    for source, url in (endpoints or {}).items():
        key = {"loki": "LOKI_BASE_URL", "prometheus": "PROMETHEUS_BASE_URL",
               "opensearch": "OPENSEARCH_BASE_URL"}[source]
        datasource_checks[source] = probe_datasource(source, {key: url})
    remote_failed = [source for source, result in datasource_checks.items()
                     if result.get("capability_ready") is not True]
    return {"status": "PASS" if not missing and not remote_failed else "FAIL", "run_id": run_id,
            "identity": truth["identity"], "record_counts": {key: len(value) for key, value in truth["records"].items()},
            "missing_resources": missing, "datasource_checks": datasource_checks,
            "datasource_failures": remote_failed, "truth": str(truth_path)}


def cleanup(*, work_dir: Path, run_id: str) -> dict[str, Any]:
    target = fixture_dir(work_dir, run_id)
    if not target.exists():
        return {"status": "ABSENT", "run_id": run_id, "fixture_dir": str(target)}
    manifest = target / "fixture-manifest.json"
    regular(manifest)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if value.get("run_id") != run_id or Path(value.get("cleanup_scope", "")).resolve() != target:
        raise ValueError("refusing cleanup outside the fixture run scope")
    shutil.rmtree(target)
    return {"status": "CLEANED", "run_id": run_id, "fixture_dir": str(target)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage an isolated AutoOps observability fixture.")
    parser.add_argument("action", choices=("setup", "check", "inject", "cleanup"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--work-dir", type=Path, default=Path("/var/tmp/jiuwenswarm-autoops-fixtures"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--kind", choices=("normal", "anomaly", "change", "unrelated"), default="anomaly")
    parser.add_argument("--loki-url")
    parser.add_argument("--prometheus-url")
    parser.add_argument("--opensearch-url")
    args = parser.parse_args(argv)
    try:
        if args.action == "setup":
            result = setup(work_dir=args.work_dir, run_id=args.run_id, config_path=args.config)
        elif args.action == "inject":
            result = inject(work_dir=args.work_dir, run_id=args.run_id, kind=args.kind)
        elif args.action == "check":
            endpoints = {key: value for key, value in {
                "loki": args.loki_url, "prometheus": args.prometheus_url,
                "opensearch": args.opensearch_url,
            }.items() if value}
            result = check(work_dir=args.work_dir, run_id=args.run_id, endpoints=endpoints)
        else:
            result = cleanup(work_dir=args.work_dir, run_id=args.run_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] in {"CREATED", "EXISTS", "INJECTED", "PASS", "CLEANED", "ABSENT"} else 1
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
