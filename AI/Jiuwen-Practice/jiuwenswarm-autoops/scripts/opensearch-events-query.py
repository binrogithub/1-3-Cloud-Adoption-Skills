#!/usr/bin/env python3
"""Read-only OpenSearch event search with fixed index and field policy."""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from observability_contract import explicit_window, load_policy, result, validate_service, validate_window_limit, window


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def request_json(url: str, body: dict, timeout: int, headers: dict[str, str], verify_tls: bool) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    context = None if verify_tls else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError("OpenSearch authentication or authorization failure") from exc
        raise RuntimeError(f"OpenSearch HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("OpenSearch connection or timeout failure") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OpenSearch returned a non-object response")
    return payload


def build_query(service: str, start_iso: str, end_iso: str, timestamp_fields: list[str],
                target_fields: list[str], message_fields: list[str], keywords: list[str], limit: int,
                offset: int, source_includes: list[str]) -> dict:
    time_should = [{"range": {field: {"gte": start_iso, "lte": end_iso}}} for field in timestamp_fields]
    service_should = [{"term": {field: service}} for field in target_fields]
    filters = [{"bool": {"should": time_should, "minimum_should_match": 1}},
               {"bool": {"should": service_should, "minimum_should_match": 1}}]
    for keyword in keywords:
        filters.append({"multi_match": {"query": keyword, "fields": message_fields, "type": "best_fields"}})
    return {
        "from": offset,
        "size": limit,
        "track_total_hits": False,
        "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
        "_source": {"includes": source_includes},
        "query": {"bool": {"filter": filters}},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search configured OpenSearch event indices read-only.")
    parser.add_argument("--service", required=True)
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--since-minutes", type=int, default=60)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args(argv)

    try:
        policy = load_policy()
        defaults = policy["defaults"]
        search = policy["opensearch"]
        service = validate_service(args.service)
        max_window = int(search["max_window_minutes"])
        max_limit = min(int(search["max_hits"]), int(defaults["max_limit"]))
        validate_window_limit(args.since_minutes, args.limit, max_minutes=max_window, max_limit=max_limit)
        if not 0 <= args.offset <= 10000:
            raise ValueError("offset must be from 0 through 10000")
        keywords = [keyword.strip() for keyword in args.keyword if keyword.strip()]
        if len(keywords) > 5 or any(len(keyword) > 128 for keyword in keywords):
            raise ValueError("at most 5 keywords of 128 characters are allowed")
        base_url = os.environ.get("OPENSEARCH_BASE_URL", "")
        if not base_url:
            raise RuntimeError("OpenSearch datasource is not configured")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("OPENSEARCH_BASE_URL must be an HTTP(S) URL")
        start_epoch, end_epoch, start_iso, end_iso = explicit_window(args.start, args.end, args.since_minutes)
        if end_epoch - start_epoch > max_window * 60:
            raise ValueError(f"requested window cannot exceed {max_window} minutes")
        body = build_query(service, start_iso, end_iso, search["timestamp_fields"],
                           search["target_fields"], search["message_fields"], keywords,
                           args.limit, args.offset, search["source_includes"])
        index_path = ",".join(search["index_patterns"])
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        api_key = os.environ.get("OPENSEARCH_API_KEY", "")
        bearer = os.environ.get("OPENSEARCH_BEARER_TOKEN", "")
        username = os.environ.get("OPENSEARCH_USERNAME", "")
        password = os.environ.get("OPENSEARCH_PASSWORD", "")
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"
        elif bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        elif username or password:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        timeout = int(os.environ.get("OPENSEARCH_TIMEOUT_SECONDS", search["timeout_seconds"]))
        if not 1 <= timeout <= 60:
            raise ValueError("OPENSEARCH_TIMEOUT_SECONDS must be from 1 through 60")
        payload = request_json(f"{base_url.rstrip('/')}/{index_path}/_search", body, timeout, headers,
                               os.environ.get("OPENSEARCH_VERIFY_TLS", "1") != "0")
        hits = payload.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            raise RuntimeError("OpenSearch hits is not a list")
        items = []
        for hit in hits[:args.limit]:
            if isinstance(hit, dict):
                items.append({"index": hit.get("_index"), "id": hit.get("_id"), "source": hit.get("_source", {})})
        status = "empty" if not items else "ok"
        total = payload.get("hits", {}).get("total")
        total_hits = None
        if isinstance(total, dict):
            value = total.get("value")
            if isinstance(value, int) and value >= 0:
                total_hits = value
        elif isinstance(total, int) and total >= 0:
            total_hits = total
        # OpenSearch is queried with track_total_hits=False for bounded cost.
        # A full page therefore means that more events may exist; callers must
        # not treat this page as complete historical coverage.
        pagination_complete = len(items) < args.limit
        completed_at = datetime.fromtimestamp(time.time(), timezone.utc).isoformat().replace("+00:00", "Z")
        output = result(source="opensearch", status=status, service=service,
                        since_minutes=args.since_minutes, limit=args.limit, items=items,
                        material={"indices": search["index_patterns"], "body": body},
                        index_patterns=search["index_patterns"], keywords=keywords,
                        window={"start": start_iso, "end": end_iso,
                                "requested_minutes": args.since_minutes},
                        requested_window={"start": start_iso, "end": end_iso},
                        offset=args.offset, returned_count=len(items),
                        pagination_complete=pagination_complete,
                        total_hits=total_hits,
                        query_completed_at=completed_at)
        return emit(output)
    except (ValueError, KeyError, TypeError) as exc:
        return emit({"source": "opensearch", "status": "invalid", "error_code": "INVALID_INPUT", "error": str(exc)}, 2)
    except RuntimeError as exc:
        return emit({"source": "opensearch", "status": "unavailable", "error_code": "DATASOURCE_ERROR", "error": str(exc)}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
