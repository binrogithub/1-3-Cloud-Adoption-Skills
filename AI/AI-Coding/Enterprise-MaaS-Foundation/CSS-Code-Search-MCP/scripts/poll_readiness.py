#!/usr/bin/env python3
"""Poll CSS and ECS until ready, discover endpoints, update state JSON.

Usage:
    python3 poll_readiness.py [state_json_path]

Defaults to the most recent css-search-*-state.json in the current directory.
Polls up to 20 minutes (CSS can take 10-15 min; ECS usually 2-3 min).

Required environment variables (same as provision_css_search.py):
  HWC_ACCESS_KEY_ID
  HWC_SECRET_ACCESS_KEY
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcss.v1 import CssClient, ListClustersDetailsRequest
from huaweicloudsdkcss.v1.region.css_region import CssRegion
from huaweicloudsdkecs.v2 import EcsClient, NovaShowServerRequest
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion

POLL_INTERVAL = 30
MAX_WAIT = 1200


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def find_latest_state() -> Path:
    candidates = sorted(Path(".").glob("css-search-*-state.json"))
    if not candidates:
        raise SystemExit("No css-search-*-state.json found in current directory. Pass path as argument.")
    return candidates[-1]


def make_clients(state: dict) -> tuple[EcsClient, CssClient]:
    ak = os.environ.get("HWC_ACCESS_KEY_ID", "")
    sk = os.environ.get("HWC_SECRET_ACCESS_KEY", "")
    if not ak or not sk:
        raise SystemExit("Set HWC_ACCESS_KEY_ID and HWC_SECRET_ACCESS_KEY")
    cred = BasicCredentials(ak, sk, state["project_id"])
    region = state["region"]
    return (
        EcsClient.new_builder().with_credentials(cred).with_region(EcsRegion.value_of(region)).build(),
        CssClient.new_builder().with_credentials(cred).with_region(CssRegion.value_of(region)).build(),
    )


def poll_css(css: CssClient, css_name: str) -> tuple[str, str]:
    """Poll ListClustersDetails until cluster has status '200'.
    Returns (cluster_id, endpoint) where endpoint is like '192.168.0.57:9200'.
    """
    start = time.time()
    while time.time() - start < MAX_WAIT:
        resp = css.list_clusters_details(ListClustersDetailsRequest())
        for cluster in (resp.clusters or []):
            if cluster.name == css_name:
                status = str(cluster.status)
                if status == "200" and cluster.endpoint:
                    return cluster.id, cluster.endpoint
                if status == "303":
                    reason = getattr(cluster, "failed_reason", "unknown")
                    raise RuntimeError(f"CSS cluster failed: {reason}")
                print(f"  CSS status: {status} (waiting for 200)...")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"CSS cluster '{css_name}' did not become ready within {MAX_WAIT}s")


def poll_ecs(ecs: EcsClient, ecs_id: str) -> tuple[str, str]:
    """Poll NovaShowServer until status is ACTIVE.
    Returns (public_ip, private_ip).
    """
    start = time.time()
    while time.time() - start < MAX_WAIT:
        resp = ecs.nova_show_server(NovaShowServerRequest(server_id=ecs_id))
        server = resp.server
        if server.status == "ACTIVE":
            public_ip = private_ip = ""
            for _net_name, addrs in (server.addresses or {}).items():
                for addr in (addrs if isinstance(addrs, list) else []):
                    stype = getattr(addr, "os_ext_ip_stype", "")
                    if stype == "floating":
                        public_ip = addr.addr
                    elif getattr(addr, "version", 0) == 4 and not addr.addr.startswith("10.42."):
                        if not public_ip:
                            public_ip = addr.addr
                    elif getattr(addr, "version", 0) == 4:
                        private_ip = addr.addr
            return public_ip, private_ip
        if server.status == "ERROR":
            raise RuntimeError(f"ECS {ecs_id} entered ERROR state")
        print(f"  ECS status: {server.status} (waiting for ACTIVE)...")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"ECS {ecs_id} did not become ACTIVE within {MAX_WAIT}s")


def main() -> None:
    state_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_state()
    state = load_state(state_path)
    ecs_client, css_client = make_clients(state)

    css_name = state["css"]["name"]
    ecs_id = state["ecs"]["id"]

    print(f"Polling CSS cluster '{css_name}' and ECS '{ecs_id}'...")
    print(f"  (interval: {POLL_INTERVAL}s, max wait: {MAX_WAIT}s)")

    cluster_id, css_endpoint = poll_css(css_client, css_name)
    print(f"CSS ready: {css_endpoint}")

    ecs_public_ip, ecs_private_ip = poll_ecs(ecs_client, ecs_id)
    print(f"ECS ready: public={ecs_public_ip}, private={ecs_private_ip}")

    state["css"].update({"id": cluster_id, "status": "200", "endpoint": css_endpoint})
    state["css_endpoint"] = f"http://{css_endpoint}"
    state["ecs_public_ip"] = ecs_public_ip
    state["ecs_private_ip"] = ecs_private_ip
    state["ecs"]["status"] = "ACTIVE"
    state.pop("notes", None)

    save_state(state_path, state)
    print(f"\nState updated: {state_path}")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
