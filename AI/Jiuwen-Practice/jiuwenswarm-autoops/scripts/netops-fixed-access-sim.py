#!/usr/bin/env python3
"""Loopback-only synthetic NOLI API for fixed-access NetOps demonstrations.

This development fixture contains no customer data and exposes only the two
read-only endpoints consumed by scripts/netops-noli.py.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

SIM_EVENT_OPENED_AT = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=5)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def scenario_payload(name: str) -> tuple[list[dict], list[dict], float, int, bool]:
    scenarios = {
        "pon_degradation": {
            "group": {"id": "scl-ftth-zone-07", "title": "Santiago FTTH Zone 07", "status": "critical",
                      "sensors": [
                          {"id": "olt-scl-01-pon-0/1/7", "name": "OLT PON receive power", "status": "critical",
                           "value": -29.4, "unit": "dBm", "threshold": -27.0},
                          {"id": "ont-offline-scl-zone-07", "name": "ONT offline ratio", "status": "critical",
                           "value": 0.31, "unit": "ratio", "threshold": 0.05},
                          {"id": "ftth-loss-scl-zone-07", "name": "Access packet loss", "status": "warning",
                           "value": 8.7, "unit": "%", "threshold": 2.0},
                      ]},
            "incident": {"id": "pon|SCL-FTTH-ZONE-07#2026-09-24T09:15:00Z",
                         "key": "pon|SCL-FTTH-ZONE-07", "label": "SCL-FTTH-ZONE-07",
                         "severity": "critical", "open": True, "opened_at": "2026-09-24T09:15:00Z",
                         "closed_at": None, "alerts": 3,
                         "sensors": [{"id": "olt-scl-01-pon-0/1/7", "name": "OLT-01 PON 0/1/7"},
                                     {"id": "ont-offline-scl-zone-07", "name": "ONT offline ratio"},
                                     {"id": "ftth-loss-scl-zone-07", "name": "FTTH packet loss"}],
                         "timeline": [
                             {"at": "2026-09-24T09:15:00Z", "message": "PON receive power fell to -29.4 dBm; synthetic data."},
                             {"at": "2026-09-24T09:17:00Z", "message": "ONT offline ratio rose to 31%; synthetic data."},
                             {"at": "2026-09-24T09:18:00Z", "message": "Packet loss reached 8.7%; synthetic data."}],
                         "findings": [{"summary": "Likely optical degradation on OLT-01 PON 0/1/7; 31% of zone ONTs are offline."},
                                      {"summary": "Correlated packet loss supports an access-side incident; customer impact is simulated."}],
                         "recommendation": {"kind": "inspect", "summary": "Check optical path, connector contamination, splitter loss, and recent field work. No action was executed."}},
        },
        "bng_auth_failure": {
            "group": {"id": "scl-broadband-auth", "title": "Santiago broadband authentication", "status": "critical",
                      "sensors": [
                          {"id": "bng-scl-01-pppoe-fail", "name": "PPPoE authentication failure ratio", "status": "critical",
                           "value": 0.42, "unit": "ratio", "threshold": 0.05},
                          {"id": "radius-scl-timeout", "name": "RADIUS timeout ratio", "status": "critical",
                           "value": 0.27, "unit": "ratio", "threshold": 0.02},
                          {"id": "bng-scl-01-session-setup", "name": "BNG session setup p95", "status": "warning",
                           "value": 8.2, "unit": "s", "threshold": 3.0},
                      ]},
            "incident": {"id": "service|SCL-BNG-01#2026-09-24T09:22:00Z",
                         "key": "service|SCL-BNG-01", "label": "SCL-BNG-01", "severity": "critical",
                         "open": True, "opened_at": "2026-09-24T09:22:00Z", "closed_at": None, "alerts": 3,
                         "sensors": [{"id": "bng-scl-01-pppoe-fail", "name": "PPPoE failures"},
                                     {"id": "radius-scl-timeout", "name": "RADIUS timeout"}],
                         "timeline": [{"at": "2026-09-24T09:22:00Z", "message": "Synthetic RADIUS and PPPoE failures increased."}],
                         "findings": [{"summary": "BNG authentication failures correlate with RADIUS timeouts."}],
                         "recommendation": {"kind": "inspect", "summary": "Check RADIUS reachability, pool saturation, and recent policy changes; no remediation executed."}},
        },
        "fiber_cut": {
            "group": {"id": "scl-ftth-zone-12", "title": "Santiago FTTH Zone 12", "status": "critical",
                      "sensors": [
                          {"id": "olt-scl-02-pon-1/2/3", "name": "OLT PON optical signal", "status": "critical",
                           "value": -40.0, "unit": "dBm", "threshold": -27.0},
                          {"id": "ont-offline-scl-zone-12", "name": "ONT offline ratio", "status": "critical",
                           "value": 0.94, "unit": "ratio", "threshold": 0.05},
                          {"id": "access-loss-scl-zone-12", "name": "Access packet loss", "status": "critical",
                           "value": 100.0, "unit": "%", "threshold": 2.0},
                      ]},
            "incident": {"id": "pon|SCL-FTTH-ZONE-12#2026-09-24T09:30:00Z",
                         "key": "pon|SCL-FTTH-ZONE-12", "label": "SCL-FTTH-ZONE-12", "severity": "critical",
                         "open": True, "opened_at": "2026-09-24T09:30:00Z", "closed_at": None, "alerts": 3,
                         "sensors": [{"id": "olt-scl-02-pon-1/2/3", "name": "OLT-02 PON 1/2/3"},
                                     {"id": "ont-offline-scl-zone-12", "name": "ONT offline ratio"}],
                         "timeline": [{"at": "2026-09-24T09:30:00Z", "message": "Synthetic PON signal loss and ONT outage."}],
                         "findings": [{"summary": "Fiber cut or severe optical path failure is plausible; field confirmation is required."}],
                         "recommendation": {"kind": "inspect", "summary": "Check OLT optics, feeder fiber, and splitter path. This simulation does not page field teams or execute repair."}},
        },
        "dhcp_exhaustion": {
            "group": {"id": "scl-broadband-ip-pool", "title": "Santiago broadband address assignment", "status": "warning",
                      "sensors": [
                          {"id": "dhcp-scl-pool-util", "name": "DHCP pool utilization", "status": "critical",
                           "value": 0.98, "unit": "ratio", "threshold": 0.90},
                          {"id": "dhcp-scl-discover-timeout", "name": "DHCP discover timeout ratio", "status": "warning",
                           "value": 0.14, "unit": "ratio", "threshold": 0.03},
                      ]},
            "incident": {"id": "service|SCL-DHCP-POOL-04#2026-09-24T09:36:00Z",
                         "key": "service|SCL-DHCP-POOL-04", "label": "SCL-DHCP-POOL-04", "severity": "warning",
                         "open": True, "opened_at": "2026-09-24T09:36:00Z", "closed_at": None, "alerts": 2,
                         "sensors": [{"id": "dhcp-scl-pool-util", "name": "DHCP utilization"},
                                     {"id": "dhcp-scl-discover-timeout", "name": "DHCP timeouts"}],
                         "timeline": [{"at": "2026-09-24T09:36:00Z", "message": "Synthetic address pool pressure crossed the threshold."}],
                         "findings": [{"summary": "Address pool capacity is near exhaustion and timeouts are increasing."}],
                         "recommendation": {"kind": "inspect", "summary": "Check lease churn, pool sizing, and relay health; no configuration was changed."}},
        },
        "clean": {
            "group": {"id": "scl-ftth-zone-07", "title": "Santiago FTTH Zone 07", "status": "ok",
                      "sensors": [{"id": "olt-scl-01-pon-0/1/7", "name": "OLT PON receive power", "status": "ok",
                                   "value": -20.0, "unit": "dBm", "threshold": -27.0}]},
            "incident": None,
        },
        "data_gap": {
            "group": {"id": "scl-ftth-zone-07", "title": "Santiago FTTH Zone 07", "status": "nodata",
                      "sensors": [{"id": "olt-scl-01-pon-0/1/7", "name": "OLT PON receive power", "status": "nodata"}]},
            "incident": None,
        },
    }
    selected = scenarios[name]
    group = selected["group"]
    incident = selected["incident"]
    if incident:
        opened = SIM_EVENT_OPENED_AT
        opened_at = opened.isoformat().replace("+00:00", "Z")
        incident["id"] = f"{incident['key']}#{opened_at}"
        incident["opened_at"] = opened_at
        for offset, entry in enumerate(incident.get("timeline", [])):
            entry["at"] = (opened + timedelta(minutes=offset + 1)).isoformat().replace("+00:00", "Z")
    incidents = [incident] if incident else []
    coverage, gaps = (62.5, 3) if name == "data_gap" else (100.0, 0)
    index_available = name != "data_gap"
    return [group], incidents, coverage, gaps, index_available


class Handler(BaseHTTPRequestHandler):
    server_version = "FixedAccessNoliSimulator/1"
    sys_version = ""

    def log_message(self, _format, *_args):
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        expected = os.environ.get("NETOPS_SIM_TOKEN", "")
        provided = self.headers.get("Authorization", "")
        if not expected or not hmac.compare_digest(provided, f"Bearer {expected}"):
            self.send_json(401, {"detail": "unauthorized"})
            return
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        scenario = os.environ.get("NETOPS_SIM_SCENARIO", "pon_degradation")
        if parsed.path == "/api/noc/board":
            window = query.get("window", ["8h"])[0]
            if not isinstance(window, str) or not re.fullmatch(r"[1-9][0-9]{0,3}[mhd]", window):
                self.send_json(400, {"detail": "invalid window"})
                return
            groups, incidents, coverage, gaps, index_available = scenario_payload(scenario)
            self.send_json(200, {"window": window, "generated_at": now_iso(),
                                 "simulation": True, "data_origin": "synthetic_fixed_access_scenario",
                                 "index_available": index_available,
                                 "sensors_total": sum(len(group["sensors"]) for group in groups),
                                 "coverage_pct": coverage, "gap_count": gaps,
                                 "groups": groups, "incidents": incidents})
            return
        if parsed.path == "/api/noc/incident":
            keys = query.get("key", [])
            window = query.get("window", ["8h"])[0]
            if not keys or not isinstance(window, str) or not re.fullmatch(r"[1-9][0-9]{0,3}[mhd]", window):
                self.send_json(400, {"detail": "key and valid window are required"})
                return
            _groups, incidents, _coverage, _gaps, _available = scenario_payload(scenario)
            row = next((item for item in incidents if keys[0] in {item["id"], item["key"]}), None)
            if row is None:
                self.send_json(404, {"detail": "incident not found"})
                return
            self.send_json(200, {field: row.get(field) for field in
                                 ("agent", "timeline", "findings", "recommendation")})
            return
        self.send_json(404, {"detail": "not found"})

    def do_POST(self):
        self.send_json(405, {"detail": "simulation is read-only"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve synthetic fixed-access NOLI-compatible data on loopback.")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1",))
    parser.add_argument("--port", type=int, default=19003)
    parser.add_argument("--scenario", choices=("pon_degradation", "bng_auth_failure", "fiber_cut",
                                                "dhcp_exhaustion", "clean", "data_gap"),
                        default=os.environ.get("NETOPS_SIM_SCENARIO", "pon_degradation"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")
    if not os.environ.get("NETOPS_SIM_TOKEN"):
        parser.error("NETOPS_SIM_TOKEN must be set through the service environment")
    os.environ["NETOPS_SIM_SCENARIO"] = args.scenario
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"fixed-access simulator ready at http://{args.host}:{args.port} scenario={args.scenario}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
