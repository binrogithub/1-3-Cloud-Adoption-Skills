#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
example_create_dws_cluster.py
Create a minimal DWS cluster using the Huawei Cloud SDK V2 API.
This is a proven working example based on actual deployment experience.

Key learnings captured in this example:
- Must use V2CreateCluster (not V1) with CreateClusterV2Request
- datastore_version is REQUIRED (e.g. "9.1.0.223")
- Volume configuration is REQUIRED (type + capacity)
- num_cn must be within the flavor's supported range (typically 2-20)
- availability_zones must be a list (e.g. ["la-north-2a"])

Usage:
    python example_create_dws_cluster.py

Requirements:
    pip install huaweicloudsdkcore huaweicloudsdkdws
"""

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkdws.v2.region.dws_region import DwsRegion
from huaweicloudsdkdws.v2 import (
    DwsClient,
    CreateClusterV2Request,
    V2CreateClusterReq,
    V2CreateCluster,
    Volume
)

# ============================================================
# Configuration (replace placeholders before running)
# ============================================================
AK = "<ak>"
SK = "<sk>"
REGION = "<region>"           # e.g. la-north-2
PROJECT_ID = "<project_id>"

# Network resources (from example_discover_resources.py)
VPC_ID = "<vpc_id>"
SUBNET_ID = "<subnet_id>"
SECURITY_GROUP_ID = "<security_group_id>"

# DWS cluster configuration
CLUSTER_NAME = "dws-finance-risk"
FLAVOR = "dwsx2.xlarge"          # Minimal cost-efficient flavor
DATASTORE_VERSION = "9.1.0.223"  # Must match ListNodeTypes output
NUM_CN = 3                        # Coordinator nodes (min 2 for HA)
NUM_NODE = 3                      # Data nodes
DB_NAME = "financedb"
DB_PASSWORD = "<db_password>"     # Must meet complexity requirements
DB_PORT = 8000
DISK_TYPE = "SSD"                 # SSD or HIGH_IO
DISK_CAPACITY = 100               # GB per node (20-2000, step 10)
AZ = "<az>"                       # e.g. la-north-2a


def create_dws_client():
    """Create and return a DWS V2 client."""
    credentials = BasicCredentials(ak=AK, sk=SK, project_id=PROJECT_ID)
    config = HttpConfig.get_default_config()
    config.timeout = 300  # 5 min timeout for cluster creation

    client = DwsClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(DwsRegion.value_of(REGION)) \
        .with_http_config(config) \
        .build()
    return client


def create_cluster():
    """Create a DWS cluster with the V2 API."""
    print("=" * 60)
    print("DWS Cluster Creation Example")
    print("=" * 60)
    print(f"  Flavor: {FLAVOR}")
    print(f"  Version: {DATASTORE_VERSION}")
    print(f"  CN nodes: {NUM_CN}")
    print(f"  Data nodes: {NUM_NODE}")
    print(f"  Disk: {DISK_TYPE} {DISK_CAPACITY}GB")
    print(f"  AZ: {AZ}")

    client = create_dws_client()

    # Build the cluster specification
    cluster_spec = V2CreateCluster(
        name=CLUSTER_NAME,
        flavor=FLAVOR,
        num_cn=NUM_CN,
        num_node=NUM_NODE,
        db_name=DB_NAME,
        db_password=DB_PASSWORD,
        db_port=DB_PORT,
        vpc_id=VPC_ID,
        subnet_id=SUBNET_ID,
        security_group_id=SECURITY_GROUP_ID,
        availability_zones=[AZ],
        volume=Volume(volume=DISK_TYPE, capacity=DISK_CAPACITY),
        datastore_version=DATASTORE_VERSION
    )

    # Build the request
    request = CreateClusterV2Request()
    request.body = V2CreateClusterReq(cluster=cluster_spec)

    # Execute
    try:
        response = client.create_cluster_v2(request)
        cluster_id = response.cluster.id
        print(f"\nCluster creation initiated successfully!")
        print(f"  Cluster ID: {cluster_id}")
        return cluster_id
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return None


def wait_for_cluster_ready(cluster_id, max_wait=1800, interval=60):
    """Wait for the DWS cluster to become AVAILABLE."""
    import time
    from huaweicloudsdkdws.v2 import ShowClusterDetailRequest

    client = create_dws_client()
    print(f"\nWaiting for cluster {cluster_id} to become AVAILABLE...")

    waited = 0
    while waited < max_wait:
        time.sleep(interval)
        waited += interval

        try:
            request = ShowClusterDetailRequest(cluster_id=cluster_id)
            response = client.show_cluster_detail(request)
            status = response.cluster.status
            print(f"  [{waited}s] Status: {status}")

            if status == "AVAILABLE":
                endpoints = response.cluster.endpoints
                print(f"\nCluster is ready!")
                if endpoints:
                    print(f"  Endpoint: {endpoints[0].endpoint}")
                    print(f"  Port: {endpoints[0].port}")
                return True

            elif status in ("FAILED", "FROZEN"):
                print(f"\nERROR: Cluster entered state: {status}")
                return False

        except Exception as e:
            print(f"  [{waited}s] Error checking status: {str(e)[:100]}")

    print(f"\nERROR: Cluster not ready within {max_wait}s")
    return False


if __name__ == "__main__":
    cluster_id = create_cluster()

    if cluster_id:
        ready = wait_for_cluster_ready(cluster_id)
        if ready:
            print("\n" + "=" * 60)
            print("DWS Cluster Ready - Next Steps:")
            print("=" * 60)
            print(f"  1. gsql -h <endpoint> -p 8000 -U <user> -W <password> -d financedb")
            print(f"  2. gsql -f scripts/dws_create_tables.sql")
            print(f"  3. gsql -f scripts/dws_etl_load.sql")
            print(f"  4. gsql -f scripts/dws_generate_reports.sql")
