#!/usr/bin/env python3
"""Inventory Databricks platform, governance, compute, and workspace-code assets."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any


FIELDS = [
    "asset_type", "asset_id", "parent_id", "name", "full_name", "owner",
    "path", "location", "state", "format", "properties_json", "raw_metadata_json",
]


def compact(value: Any) -> str:
    return "" if value in (None, "", [], {}) else json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


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
        url = self.host + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
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

    def list_all(
        self, path: str, key: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        output: list[dict[str, Any]] = []
        while True:
            payload = self.get(path, query)
            output.extend(payload.get(key) or [])
            token = payload.get("next_page_token")
            if not token:
                return output
            query["page_token"] = str(token)


def row(asset_type: str, obj: dict[str, Any], **overrides: str) -> dict[str, str]:
    result = {field: "" for field in FIELDS}
    result.update(
        {
            "asset_type": asset_type,
            "asset_id": str(
                obj.get("id") or obj.get("object_id") or obj.get("catalog_id")
                or obj.get("schema_id") or obj.get("volume_id") or obj.get("warehouse_id")
                or obj.get("cluster_id") or obj.get("instance_pool_id") or obj.get("policy_id") or ""
            ),
            "name": str(obj.get("name") or obj.get("cluster_name") or obj.get("instance_pool_name") or ""),
            "full_name": str(obj.get("full_name") or ""),
            "owner": str(obj.get("owner") or obj.get("creator_user_name") or ""),
            "path": str(obj.get("path") or ""),
            "location": str(obj.get("storage_location") or obj.get("url") or ""),
            "state": str(obj.get("state") or ""),
            "format": str(obj.get("format") or obj.get("object_type") or ""),
            "raw_metadata_json": compact(obj),
        }
    )
    result.update(overrides)
    return result


def safe_list(
    api: Api,
    warnings: list[str],
    path: str,
    key: str,
    params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    try:
        return api.list_all(path, key, params)
    except RuntimeError as exc:
        warnings.append(str(exc))
        return []


def inventory_unity_catalog(api: Api, warnings: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    catalogs = safe_list(api, warnings, "/api/2.1/unity-catalog/catalogs", "catalogs")
    for catalog in catalogs:
        catalog_name = str(catalog.get("name", ""))
        rows.append(row("CATALOG", catalog))
        schemas = safe_list(
            api, warnings, "/api/2.1/unity-catalog/schemas", "schemas", {"catalog_name": catalog_name}
        )
        for schema in schemas:
            schema_name = str(schema.get("name", ""))
            rows.append(row("SCHEMA", schema, parent_id=catalog_name))
            volumes = safe_list(
                api,
                warnings,
                "/api/2.1/unity-catalog/volumes",
                "volumes",
                {"catalog_name": catalog_name, "schema_name": schema_name},
            )
            for volume in volumes:
                rows.append(
                    row(
                        "VOLUME",
                        volume,
                        parent_id=f"{catalog_name}.{schema_name}",
                        path=f"/Volumes/{catalog_name}/{schema_name}/{volume.get('name', '')}",
                        format=str(volume.get("volume_type", "")),
                    )
                )
    for path, key, kind in (
        ("/api/2.1/unity-catalog/external-locations", "external_locations", "EXTERNAL_LOCATION"),
        ("/api/2.1/unity-catalog/storage-credentials", "storage_credentials", "STORAGE_CREDENTIAL"),
        ("/api/2.1/unity-catalog/connections", "connections", "CONNECTION"),
    ):
        for obj in safe_list(api, warnings, path, key):
            rows.append(row(kind, obj))
    return rows


def inventory_compute(api: Api, warnings: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    endpoints = (
        ("/api/2.0/sql/warehouses", "warehouses", "SQL_WAREHOUSE"),
        ("/api/2.0/clusters/list", "clusters", "CLUSTER"),
        ("/api/2.0/instance-pools/list", "instance_pools", "INSTANCE_POOL"),
        ("/api/2.0/policies/clusters/list", "policies", "CLUSTER_POLICY"),
        ("/api/2.0/repos", "repos", "REPO"),
        ("/api/2.0/secrets/scopes/list", "scopes", "SECRET_SCOPE"),
    )
    for path, key, kind in endpoints:
        for obj in safe_list(api, warnings, path, key):
            if kind == "SECRET_SCOPE":
                # Scope names and ACL mode are inventory metadata; secret keys/values are never requested.
                obj = {k: v for k, v in obj.items() if k in {"name", "backend_type", "keyvault_metadata"}}
            rows.append(row(kind, obj))
    return rows


def inventory_workspace(api: Api, warnings: list[str], max_objects: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    directories: deque[str] = deque(["/"])
    seen: set[str] = set()
    while directories and len(rows) < max_objects:
        directory = directories.popleft()
        if directory in seen:
            continue
        seen.add(directory)
        try:
            objects = api.get("/api/2.0/workspace/list", {"path": directory}).get("objects") or []
        except RuntimeError as exc:
            warnings.append(str(exc))
            continue
        for obj in objects:
            kind = str(obj.get("object_type") or "WORKSPACE_OBJECT")
            rows.append(row(f"WORKSPACE_{kind}", obj, parent_id=directory))
            if kind == "DIRECTORY" and obj.get("path") not in seen:
                directories.append(str(obj["path"]))
            if len(rows) >= max_objects:
                warnings.append(f"Workspace object scan stopped at --max-workspace-objects={max_objects}")
                break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, default=Path("f_credentials.env"))
    parser.add_argument("--output", type=Path, default=Path("databricks_platform_inventory.csv"))
    parser.add_argument("--warnings", type=Path, default=Path("databricks_inventory_warnings.json"))
    parser.add_argument("--max-workspace-objects", type=int, default=100000)
    args = parser.parse_args()
    host, token = read_credentials(args.credentials)
    api = Api(host, token)
    warnings: list[str] = []
    rows = inventory_unity_catalog(api, warnings)
    rows.extend(inventory_compute(api, warnings))
    rows.extend(inventory_workspace(api, warnings, args.max_workspace_objects))
    rows.sort(key=lambda value: (value["asset_type"], value["full_name"], value["path"], value["name"]))
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    args.warnings.write_text(json.dumps(warnings, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"Warnings: {len(warnings)} (see {args.warnings})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
