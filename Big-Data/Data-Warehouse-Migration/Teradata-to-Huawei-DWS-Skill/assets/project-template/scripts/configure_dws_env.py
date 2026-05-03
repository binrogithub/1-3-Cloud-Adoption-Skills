#!/usr/bin/env python3
"""Generate config/dws.env for the DWS migration scripts.

With AK/SK in the environment, the script discovers a DWS cluster endpoint.
Without AK/SK, it writes a local template that can be filled manually.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import stat
import sys
from pathlib import Path
from typing import Any, Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdws.v2 import DwsClient, ListClustersRequest
from huaweicloudsdkdws.v2.region.dws_region import DwsRegion


DEFAULT_PROJECT_ID = "89a76cc1484440b38810ecb9e3b5c0d7"
DEFAULT_REGION = "la-south-2"
DEFAULT_CLUSTER_NAME = "dws-finance-demo-min3"
DEFAULT_OUTPUT = "config/dws.env"
DEFAULT_DB_USER = "dbadmin"
DEFAULT_DB_PORT = 8000
DEFAULT_DB = "postgres"


def first_attr(obj: Any, names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def credentials(project_id: str) -> Optional[BasicCredentials]:
    ak = os.getenv("CLOUD_SDK_AK") or os.getenv("AK")
    sk = os.getenv("CLOUD_SDK_SK") or os.getenv("SK")
    if not ak or not sk:
        return None
    return BasicCredentials(ak, sk, project_id)


def q(value: str) -> str:
    return shlex.quote(value)


def read_generated_password(cluster_name: str) -> Optional[str]:
    path = Path(".secrets") / f"{cluster_name}.env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^DWS_DB_PASSWORD=(.*)$", line.strip())
        if match:
            return shlex.split(match.group(1))[0] if match.group(1) else None
    return None


def endpoint_from_cluster(cluster: Any, prefer_public: bool) -> tuple[str, int]:
    port = int(first_attr(cluster, ("port",), DEFAULT_DB_PORT) or DEFAULT_DB_PORT)

    public_endpoints = first_attr(cluster, ("public_endpoints",), []) or []
    endpoints = first_attr(cluster, ("endpoints",), []) or []

    endpoint_groups = [public_endpoints, endpoints] if prefer_public else [endpoints, public_endpoints]
    for group in endpoint_groups:
        for endpoint in group:
            connect_info = first_attr(endpoint, ("public_connect_info", "connect_info"), "")
            if connect_info:
                host = connect_info.split(",")[0].strip()
                if ":" in host and not host.startswith("["):
                    host_part, port_part = host.rsplit(":", 1)
                    return host_part, int(port_part)
                return host, port

    raise RuntimeError("Cluster has no endpoint yet. It may still be creating or has no reachable endpoint.")


def discover_cluster(project_id: str, region: str, cluster_name: str) -> Any:
    auth = credentials(project_id)
    if not auth:
        return None
    client = DwsClient.new_builder().with_credentials(auth).with_region(DwsRegion.value_of(region)).build()
    response = client.list_clusters(ListClustersRequest())
    for cluster in getattr(response, "clusters", None) or []:
        if first_attr(cluster, ("name",), "") == cluster_name:
            return cluster
    raise RuntimeError(f"DWS cluster not found: {cluster_name}")


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"{key}={q(value)}" for key, value in values.items()) + "\n"
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure config/dws.env for DWS migration.")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--cluster-name", default=DEFAULT_CLUSTER_NAME)
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--database", default=os.getenv("DWS_DATABASE", DEFAULT_DB))
    parser.add_argument("--user", default=os.getenv("DWS_USER", DEFAULT_DB_USER))
    parser.add_argument("--password", default=os.getenv("DWS_PASSWORD") or os.getenv("DWS_DB_PASSWORD"))
    parser.add_argument("--prefer-public", action="store_true")
    args = parser.parse_args()

    cluster = discover_cluster(args.project_id, args.region, args.cluster_name)
    if cluster:
        host, port = endpoint_from_cluster(cluster, args.prefer_public)
        user = first_attr(cluster, ("user_name",), args.user) or args.user
        status = first_attr(cluster, ("status",), "")
    else:
        host = os.getenv("DWS_HOST", "replace-with-dws-endpoint")
        port = int(os.getenv("DWS_PORT", DEFAULT_DB_PORT))
        user = args.user
        status = "not-discovered"

    password = args.password or read_generated_password(args.cluster_name) or "replace-with-dws-admin-password"
    values = {
        "DWS_HOST": host,
        "DWS_PORT": str(port),
        "DWS_DATABASE": args.database,
        "DWS_USER": user,
        "DWS_PASSWORD": password,
        "DWS_SSLMODE": os.getenv("DWS_SSLMODE", "prefer"),
        "DWS_SQL_CLIENT": os.getenv("DWS_SQL_CLIENT", "docker"),
        "DWS_SQL_CLIENT_IMAGE": os.getenv("DWS_SQL_CLIENT_IMAGE", "citusdata/citus:12.1"),
    }
    write_env(args.output, values)
    print(f"Wrote {args.output} with 0600 permissions.")
    print(f"cluster_name={args.cluster_name}")
    print(f"cluster_status={status}")
    print(f"dws_host={host}")
    print(f"dws_port={port}")
    if password.startswith("replace-with-"):
        print("DWS password is still a placeholder; update DWS_PASSWORD before migration.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except exceptions.ClientRequestException as exc:
        print(f"Huawei Cloud API error: status={exc.status_code} request_id={exc.request_id} code={exc.error_code}", file=sys.stderr)
        print(exc.error_msg, file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

