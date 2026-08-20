#!/usr/bin/env python3
"""Export Databricks Unity Catalog objects and canonical DDL to CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


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

    def list_all(
        self,
        path: str,
        result_key: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        results: list[dict[str, Any]] = []
        while True:
            payload = self.get(path, query)
            results.extend(payload.get(result_key) or [])
            token = payload.get("next_page_token")
            if not token:
                return results
            query["page_token"] = token


def qi(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def qs(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def qualified(obj: dict[str, Any]) -> str:
    return ".".join(qi(str(obj[key])) for key in ("catalog_name", "schema_name", "name"))


def column_type(column: dict[str, Any]) -> str:
    if column.get("type_text"):
        return str(column["type_text"])
    if column.get("type_name"):
        return str(column["type_name"])
    if column.get("type_json"):
        try:
            parsed = json.loads(column["type_json"])
            return str(parsed.get("type") or parsed)
        except (TypeError, json.JSONDecodeError):
            return str(column["type_json"])
    return "STRING /* source type unavailable */"


def column_sql(column: dict[str, Any]) -> str:
    text = f"  {qi(str(column.get('name', 'unnamed')))} {column_type(column)}"
    if column.get("nullable") is False:
        text += " NOT NULL"
    if column.get("comment"):
        text += " COMMENT " + qs(str(column["comment"]))
    return text


def property_items(obj: dict[str, Any]) -> list[tuple[str, str]]:
    props = obj.get("properties")
    if isinstance(props, dict):
        return sorted((str(k), str(v)) for k, v in props.items())
    pairs = obj.get("properties_pairs") or []
    return sorted(
        (str(pair.get("key")), str(pair.get("value", "")))
        for pair in pairs
        if pair.get("key") is not None
    )


def table_ddl(obj: dict[str, Any]) -> tuple[str, str]:
    qname = qualified(obj)
    kind = str(obj.get("table_type") or "TABLE").upper()
    definition = obj.get("view_definition")
    if kind in {"VIEW", "MATERIALIZED_VIEW"}:
        keyword = "MATERIALIZED VIEW" if kind == "MATERIALIZED_VIEW" else "VIEW"
        if definition:
            return f"CREATE OR REPLACE {keyword} {qname} AS\n{definition};", "complete"
        return f"-- {keyword} definition unavailable for {qname}", "metadata_missing"

    columns = sorted(obj.get("columns") or [], key=lambda c: c.get("position", 0))
    parts = [f"CREATE TABLE {qname} (", ",\n".join(column_sql(c) for c in columns), ")"]
    data_format = obj.get("data_source_format")
    if data_format:
        parts.append(f"USING {data_format}")
    if kind == "EXTERNAL" and obj.get("storage_location"):
        parts.append("LOCATION " + qs(str(obj["storage_location"])))
    props = property_items(obj)
    if props:
        body = ",\n  ".join(f"{qs(k)} = {qs(v)}" for k, v in props)
        parts.append(f"TBLPROPERTIES (\n  {body}\n)")
    return "\n".join(parts) + ";", "complete" if columns else "metadata_missing"


def parameter_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("parameters", "params"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def parameter_sql(parameter: dict[str, Any], position: int) -> str:
    name = str(parameter.get("name") or parameter.get("parameter_name") or f"arg{position}")
    dtype = str(
        parameter.get("type_text")
        or parameter.get("full_data_type")
        or parameter.get("data_type")
        or parameter.get("type_name")
        or "STRING /* source type unavailable */"
    )
    text = f"{qi(name)} {dtype}"
    if parameter.get("parameter_default") is not None:
        text += " DEFAULT " + str(parameter["parameter_default"])
    elif parameter.get("default_value") is not None:
        text += " DEFAULT " + str(parameter["default_value"])
    if parameter.get("comment"):
        text += " COMMENT " + qs(str(parameter["comment"]))
    return text


def function_ddl(obj: dict[str, Any]) -> tuple[str, str]:
    qname = qualified(obj)
    inputs = parameter_list(obj.get("input_params"))
    args = ", ".join(parameter_sql(p, i + 1) for i, p in enumerate(inputs))
    returns = parameter_list(obj.get("return_params"))
    if returns:
        if len(returns) == 1 and not returns[0].get("name"):
            return_sql = column_type(returns[0])
        else:
            return_sql = "TABLE (" + ", ".join(parameter_sql(p, i + 1) for i, p in enumerate(returns)) + ")"
    else:
        return_sql = str(obj.get("full_data_type") or obj.get("data_type") or "STRING")
    body = obj.get("routine_definition")
    language = str(obj.get("external_language") or "SQL")
    if not body:
        return f"-- Function body unavailable for {qname}", "metadata_missing"
    ddl = f"CREATE OR REPLACE FUNCTION {qname}({args})\nRETURNS {return_sql}\nLANGUAGE {language}\nRETURN {body};"
    return ddl, "complete"


def row_for(obj: dict[str, Any], object_type: str, ddl: str, ddl_status: str) -> dict[str, str]:
    return {
        "object_type": object_type,
        "catalog": str(obj.get("catalog_name", "")),
        "schema": str(obj.get("schema_name", "")),
        "name": str(obj.get("name", "")),
        "full_name": str(obj.get("full_name", "")),
        "table_type": str(obj.get("table_type", "")),
        "data_source_format": str(obj.get("data_source_format", "")),
        "owner": str(obj.get("owner", "")),
        "comment": str(obj.get("comment", "")),
        "storage_location": str(obj.get("storage_location", "")),
        "ddl_status": ddl_status,
        "ddl": ddl,
    }


def export(api: Api, output: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    catalogs = api.list_all("/api/2.1/unity-catalog/catalogs", "catalogs")
    for catalog in catalogs:
        catalog_name = str(catalog["name"])
        try:
            schemas = api.list_all(
                "/api/2.1/unity-catalog/schemas", "schemas", {"catalog_name": catalog_name}
            )
        except RuntimeError as exc:
            warnings.append(str(exc))
            continue
        for schema in schemas:
            schema_name = str(schema["name"])
            params = {"catalog_name": catalog_name, "schema_name": schema_name}
            try:
                tables = api.list_all("/api/2.1/unity-catalog/tables", "tables", params)
                for obj in tables:
                    ddl, status = table_ddl(obj)
                    kind = str(obj.get("table_type") or "TABLE").upper()
                    object_type = "VIEW" if kind in {"VIEW", "MATERIALIZED_VIEW"} else "TABLE"
                    rows.append(row_for(obj, object_type, ddl, status))
            except RuntimeError as exc:
                warnings.append(str(exc))
            try:
                functions = api.list_all("/api/2.1/unity-catalog/functions", "functions", params)
                for obj in functions:
                    ddl, status = function_ddl(obj)
                    rows.append(row_for(obj, "FUNCTION", ddl, status))
            except RuntimeError as exc:
                warnings.append(str(exc))

    rows.sort(key=lambda r: (r["catalog"], r["schema"], r["object_type"], r["name"]))
    fields = [
        "object_type", "catalog", "schema", "name", "full_name", "table_type",
        "data_source_format", "owner", "comment", "storage_location", "ddl_status", "ddl",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, default=Path("f_credentials.env"))
    parser.add_argument("--output", type=Path, default=Path("databricks_objects_ddl.csv"))
    parser.add_argument("--warnings", type=Path)
    args = parser.parse_args()
    host, token = read_credentials(args.credentials)
    rows, warnings = export(Api(host, token), args.output)
    if args.warnings:
        args.warnings.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["object_type"]] = counts.get(row["object_type"], 0) + 1
    print(f"Wrote {len(rows)} rows to {args.output}")
    print("Counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"Incomplete DDL rows: {sum(row['ddl_status'] != 'complete' for row in rows)}")
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
