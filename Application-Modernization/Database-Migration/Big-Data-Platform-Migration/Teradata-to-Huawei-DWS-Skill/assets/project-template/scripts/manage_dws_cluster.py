#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdws.v2 import (
    DeleteClusterRequest,
    DeleteClusterRequestBody,
    DwsClient,
    ListClustersRequest,
    StartClusterRequest,
    StopClusterRequest,
)
from huaweicloudsdkdws.v2.region.dws_region import DwsRegion


DEFAULT_PROJECT_ID = "89a76cc1484440b38810ecb9e3b5c0d7"
DEFAULT_REGION = "la-south-2"
DEFAULT_CLUSTER_ID = "7b7c488b-4c50-468e-8a9a-793525039183"
DEFAULT_CLUSTER_NAME = "dws-finance-demo-min3"


def first_attr(obj: Any, names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def client(project_id: str, region: str) -> DwsClient:
    ak = os.getenv("CLOUD_SDK_AK") or os.getenv("AK")
    sk = os.getenv("CLOUD_SDK_SK") or os.getenv("SK")
    if not ak or not sk:
        raise RuntimeError("Missing AK/SK. Export CLOUD_SDK_AK/CLOUD_SDK_SK or AK/SK before running.")
    auth = BasicCredentials(ak, sk, project_id)
    return DwsClient.new_builder().with_credentials(auth).with_region(DwsRegion.value_of(region)).build()


def find_cluster(dws: DwsClient, cluster_id: Optional[str], cluster_name: Optional[str]) -> Any:
    response = dws.list_clusters(ListClustersRequest())
    clusters = getattr(response, "clusters", None) or []
    for cluster in clusters:
        cid = first_attr(cluster, ("id",), "")
        name = first_attr(cluster, ("name",), "")
        if cluster_id and cid == cluster_id:
            return cluster
        if cluster_name and name == cluster_name:
            return cluster
    raise RuntimeError(f"Cluster not found: id={cluster_id or '-'} name={cluster_name or '-'}")


def describe(cluster: Any) -> None:
    fields = [
        ("id", "id"),
        ("name", "name"),
        ("status", "status"),
        ("sub_status", "sub_status"),
        ("task_status", "task_status"),
        ("node_type", "node_type"),
        ("number_of_node", "number_of_node"),
        ("port", "port"),
        ("vpc_id", "vpc_id"),
        ("subnet_id", "subnet_id"),
        ("security_group_id", "security_group_id"),
        ("created", "created"),
        ("updated", "updated"),
    ]
    for label, attr in fields:
        print(f"{label}={first_attr(cluster, (attr,), '')}")
    endpoints = first_attr(cluster, ("endpoints",), []) or []
    public_endpoints = first_attr(cluster, ("public_endpoints",), []) or []
    for endpoint in endpoints:
        print(f"private_endpoint={first_attr(endpoint, ('connect_info',), '')}")
    for endpoint in public_endpoints:
        print(f"public_endpoint={first_attr(endpoint, ('public_connect_info',), '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the demo Huawei Cloud DWS cluster.")
    parser.add_argument("action", choices=["status", "start", "stop", "delete"])
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--cluster-id", default=os.getenv("DWS_CLUSTER_ID", DEFAULT_CLUSTER_ID))
    parser.add_argument("--cluster-name", default=os.getenv("DWS_CLUSTER_NAME", DEFAULT_CLUSTER_NAME))
    parser.add_argument("--yes", action="store_true", help="Required for delete.")
    parser.add_argument("--confirm-name", default="", help="For delete, must exactly match the cluster name.")
    parser.add_argument("--keep-last-manual-snapshot", action="store_true")
    args = parser.parse_args()

    dws = client(args.project_id, args.region)
    cluster = find_cluster(dws, args.cluster_id, args.cluster_name)
    cluster_id = first_attr(cluster, ("id",), args.cluster_id)
    cluster_name = first_attr(cluster, ("name",), args.cluster_name)

    if args.action == "status":
        describe(cluster)
        return 0

    if args.action == "start":
        response = dws.start_cluster(StartClusterRequest(cluster_id=cluster_id))
        print(f"Start request submitted: cluster_id={cluster_id} cluster_name={cluster_name}")
        print(response)
        return 0

    if args.action == "stop":
        response = dws.stop_cluster(StopClusterRequest(cluster_id=cluster_id))
        print(f"Stop request submitted: cluster_id={cluster_id} cluster_name={cluster_name}")
        print(response)
        return 0

    if args.action == "delete":
        if not args.yes or args.confirm_name != cluster_name:
            raise RuntimeError(
                "Delete requires --yes and --confirm-name matching the cluster name. "
                f"Expected --confirm-name {cluster_name!r}."
            )
        keep_snapshot = 1 if args.keep_last_manual_snapshot else 0
        response = dws.delete_cluster(
            DeleteClusterRequest(
                cluster_id=cluster_id,
                body=DeleteClusterRequestBody(keep_last_manual_snapshot=keep_snapshot),
            )
        )
        print(f"Delete request submitted: cluster_id={cluster_id} cluster_name={cluster_name}")
        print(response)
        return 0

    return 2


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

