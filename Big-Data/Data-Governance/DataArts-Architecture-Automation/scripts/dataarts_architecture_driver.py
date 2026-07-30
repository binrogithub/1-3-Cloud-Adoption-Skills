#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


IAM_ENDPOINT = "https://iam.myhuaweicloud.com"


CREATE_ENDPOINTS = {
    "model_workspaces": ("GET", "/design/workspaces", "POST", "/design/workspaces"),
    "directories": ("GET", "/design/directorys", "POST", "/design/directorys"),
    "subjects": ("GET", "/design/subjects", "POST", "/design/subjects", "v3"),
    "standards": ("GET", "/design/standards", "POST", "/design/standards"),
    "code_tables": ("GET", "/design/code-tables", "POST", "/design/code-tables"),
    "table_models": ("GET", "/design/table-model", "POST", "/design/table-model"),
    "dimensions": ("GET", "/design/dimensions", "POST", "/design/dimensions"),
    "summary_tables": ("GET", "/design/aggregation-logic-tables", "POST", "/design/aggregation-logic-tables"),
    "atomic_metrics": ("GET", "/design/atomic-indexs", "POST", "/design/atomic-indexs"),
    "derivative_metrics": ("GET", "/design/derivative-indexs", "POST", "/design/derivative-indexs"),
    "compound_metrics": ("GET", "/design/compound-metrics", "POST", "/design/compound-metrics"),
    "business_metrics": ("GET", "/design/biz-metrics", "POST", "/design/biz-metrics"),
}


ORDER = [
    "model_workspaces",
    "directories",
    "subjects",
    "standards",
    "code_tables",
    "table_models",
    "dimensions",
    "summary_tables",
    "atomic_metrics",
    "derivative_metrics",
    "compound_metrics",
    "business_metrics",
]


def read_credentials(path: str | None) -> dict[str, str]:
    values = {
        "domain": os.getenv("HUAWEICLOUD_DOMAIN"),
        "username": os.getenv("HUAWEICLOUD_USERNAME"),
        "password": os.getenv("HUAWEICLOUD_PASSWORD"),
    }
    if path and Path(path).exists():
        text = Path(path).read_text(encoding="utf-8")

        def grab(label: str) -> str | None:
            match = re.search(rf"^{re.escape(label)}\s*:\s*(.+?)\s*$", text, re.MULTILINE)
            return match.group(1).strip() if match else None

        values["domain"] = values["domain"] or grab("Huawei Cloud Account name")
        values["username"] = values["username"] or grab("Username")
        values["password"] = values["password"] or grab("password")
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise SystemExit(f"Missing credential fields: {', '.join(missing)}")
    return values


def request_json(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None):
    request_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            return resp.status, payload, resp.headers.get("X-Subject-Token")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload, None


def get_project_token(creds: dict[str, str], region: str) -> tuple[str, str]:
    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": creds["username"],
                        "password": creds["password"],
                        "domain": {"name": creds["domain"]},
                    }
                },
            },
            "scope": {"project": {"name": region}},
        }
    }
    status, payload, token = request_json("POST", f"{IAM_ENDPOINT}/v3/auth/tokens", body)
    if status >= 300 or not token:
        raise SystemExit(f"IAM token request failed: HTTP {status}: {json.dumps(payload, ensure_ascii=False)}")
    return token, payload["token"]["project"]["id"]


def dataarts_url(region: str, version: str, project_id: str, path: str, query: dict[str, Any] | None = None) -> str:
    url = f"https://dayu.{region}.myhuaweicloud.com/{version}/{project_id}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return url


def records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get("data", {}).get("value", payload.get("value", payload))
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("records", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def request_with_retry(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None):
    for attempt in range(5):
        status, payload, token = request_json(method, url, body, headers)
        if status != 429:
            return status, payload, token
        time.sleep(2 + attempt)
    return status, payload, token


def matches(item: dict[str, Any], match: dict[str, Any]) -> bool:
    return all(item.get(key) == value for key, value in match.items())


def ensure_object(config: dict[str, Any], kind: str, spec: dict[str, Any], headers: dict[str, str], project_id: str) -> dict[str, Any]:
    endpoint = CREATE_ENDPOINTS[kind]
    get_path, post_path = endpoint[1], endpoint[3]
    version = endpoint[4] if len(endpoint) > 4 else "v2"
    query = dict(spec.get("list_query") or {"limit": 100, "offset": 0})
    status, payload, _ = request_with_retry(
        "GET",
        dataarts_url(config["region"], version, project_id, get_path, query),
        headers=headers,
    )
    if status >= 300:
        return {"kind": kind, "match": spec.get("match"), "action": "list_failed", "status": status, "payload": payload}
    for item in records(payload):
        if matches(item, spec["match"]):
            return {"kind": kind, "match": spec["match"], "action": "skipped_existing", "id": item.get("id"), "read_back": True}

    status, payload, _ = request_with_retry(
        "POST",
        dataarts_url(config["region"], version, project_id, post_path),
        spec["body"],
        headers=headers,
    )
    if status >= 300:
        return {"kind": kind, "match": spec.get("match"), "action": "create_failed", "status": status, "payload": payload}
    value = payload.get("data", {}).get("value", {}) if isinstance(payload, dict) else {}
    return {"kind": kind, "match": spec["match"], "action": "created", "id": value.get("id"), "read_back": bool(value)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.dry_run:
        print(json.dumps({"dry_run": True, "order": ORDER, "counts": {k: len(config.get("objects", {}).get(k, [])) for k in ORDER}}, indent=2))
        return 0

    creds = read_credentials(config.get("credentials_file"))
    token, project_id = get_project_token(creds, config["region"])
    headers = {
        "X-Auth-Token": token,
        "Content-Type": "application/json;charset=UTF-8",
        "workspace": config["workspace_id"],
    }

    results = []
    for kind in ORDER:
        for spec in config.get("objects", {}).get(kind, []):
            results.append(ensure_object(config, kind, spec, headers, project_id))

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "scenario": config.get("scenario"),
        "project_id": project_id,
        "region": config["region"],
        "workspace_id": config["workspace_id"],
        "results": results,
        "summary": {
            "total": len(results),
            "created": sum(1 for item in results if item["action"] == "created"),
            "skipped_existing": sum(1 for item in results if item["action"] == "skipped_existing"),
            "failed": sum(1 for item in results if item["action"].endswith("_failed")),
        },
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
