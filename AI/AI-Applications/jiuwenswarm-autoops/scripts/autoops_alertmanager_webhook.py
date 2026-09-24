#!/usr/bin/env python3
"""Receive Alertmanager webhooks and persist bounded AutoOps events.

This is an ingress adapter only.  It validates and durably appends each alert
to the watcher event stream.  It never calls ProjectManager or an operational
tool while handling the HTTP request.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / ".runtime" / "autoops-watch" / "events.jsonl"
MAX_BODY = 1_000_000
MAX_ALERTS = 100


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_alert(alert: dict[str, Any]) -> dict[str, Any]:
    labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
    annotations = alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
    status = str(alert.get("status", "firing")).strip().lower()
    if status not in {"firing", "resolved"}:
        raise ValueError("alert status must be firing or resolved")
    starts_at = str(alert.get("startsAt", "")).strip()
    if not starts_at:
        raise ValueError("alert startsAt is required")
    try:
        parsed_starts_at = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("alert startsAt must be an ISO-8601 timestamp") from exc
    if parsed_starts_at.tzinfo is None:
        raise ValueError("alert startsAt must include a timezone")
    service = labels.get("service") or labels.get("service_name") or labels.get("job") or ""
    target = labels.get("target") or labels.get("instance") or ""
    source_digest = hashlib.sha256(canonical(alert).encode("utf-8")).hexdigest()
    # Alertmanager can redeliver the same alert without a message ID.  The
    # digest is a delivery identity; startsAt remains part of incident identity
    # in the watcher, so a later recurrence is not swallowed.
    return {
        "id": "am-" + source_digest,
        "source": "alertmanager",
        "status": status,
        "alertname": str(labels.get("alertname", "alert")),
        "service": str(service),
        "target": str(target),
        "scope_id": str(labels.get("scope_id", labels.get("tenant", ""))),
        "starts_at": starts_at,
        "ends_at": str(alert.get("endsAt", "")),
        "labels": {str(key): str(value) for key, value in labels.items()},
        "annotations": {str(key): str(value) for key, value in annotations.items()},
    }


def parse_payload(body: bytes) -> list[dict[str, Any]]:
    if len(body) > MAX_BODY:
        raise ValueError("webhook body exceeds 1000000 bytes")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("webhook body must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
        raise ValueError("webhook payload must contain an alerts array")
    if len(payload["alerts"]) > MAX_ALERTS:
        raise ValueError("webhook contains too many alerts")
    alerts = []
    for alert in payload["alerts"]:
        if not isinstance(alert, dict):
            raise ValueError("each alert must be an object")
        alerts.append(normalize_alert(alert))
    return alerts


def append_events(events_file: Path, events: list[dict[str, Any]]) -> None:
    events_file.parent.mkdir(parents=True, exist_ok=True)
    with events_file.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            for event in events:
                stream.write(canonical(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def authorize(headers: dict[str, str]) -> bool:
    expected = os.environ.get("ALERTMANAGER_WEBHOOK_TOKEN", "")
    if not expected:
        return True
    supplied = headers.get("Authorization", "")
    prefix = "Bearer "
    return supplied.startswith(prefix) and hmac.compare_digest(supplied[len(prefix):], expected)


class Handler(BaseHTTPRequestHandler):
    events_file: Path = DEFAULT_EVENTS

    def do_POST(self) -> None:
        if self.path != "/alertmanager/webhook":
            self.send_error(404)
            return
        if not authorize({key: value for key, value in self.headers.items()}):
            self.send_error(401)
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_BODY:
                raise ValueError("invalid content length")
            events = parse_payload(self.rfile.read(length))
            append_events(self.events_file, events)
        except (ValueError, OSError) as exc:
            self.send_error(400, str(exc))
            return
        body = json.dumps({"status": "accepted", "accepted": len(events)}, ensure_ascii=False).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Receive Alertmanager events for AutoOps.")
    parser.add_argument("--events-file", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--body-file", type=Path, help="Validate and append one webhook body, then exit.")
    parser.add_argument("--listen", default="127.0.0.1:19002")
    args = parser.parse_args(argv)
    try:
        if args.body_file:
            body = args.body_file.read_bytes()
            events = parse_payload(body)
            append_events(args.events_file, events)
            print(json.dumps({"status": "accepted", "accepted": len(events)}, ensure_ascii=False))
            return 0
        host, separator, port_text = args.listen.rpartition(":")
        if not separator or not host or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ValueError("--listen must be HOST:PORT")
        Handler.events_file = args.events_file
        server = ThreadingHTTPServer((host, int(port_text)), Handler)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
