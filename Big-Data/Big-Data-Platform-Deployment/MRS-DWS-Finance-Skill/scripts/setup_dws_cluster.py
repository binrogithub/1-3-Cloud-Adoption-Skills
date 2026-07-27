#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_dws_cluster.py
Provision DWS cluster for financial risk control data warehouse
"""

import sys
import time

# Huawei Cloud SDK
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdws.v2.region.dws_region import DwsRegion
from huaweicloudsdkdws.v2 import DwsClient
from huaweicloudsdkdws.v2.model import V2CreateClusterReq, Volume

# ============================================================
# Configuration (replace placeholders before running)
# ============================================================
AK = "<ak>"
SK = "<sk>"
PROJECT_ID = "<project_id>"
REGION = "<region>"           # e.g. la-north-2

VPC_ID = "<vpc_id>"
SUBNET_ID = "<subnet_id>"
SECURITY_GROUP_ID = "<security_group_id>"

DWS_CLUSTER_NAME = "dws-finance-risk"
DWS_FLAVOR = "dwsx2.xlarge"   # Minimal flavor for cost efficiency
DWS_NUM_CN = 3                 # Coordinator nodes (min for HA)
DWS_NUM_NODE = 3               # Data nodes (min for HA)
DWS_DB_NAME = "financedb"
DWS_DB_PASSWORD = "<db_password>"  # Must meet complexity requirements
DWS_DB_PORT = 8000
DWS_DATASTORE_VERSION = "9.1.0.223"
DWS_VOLUME_TYPE = "SSD"
DWS_VOLUME_CAPACITY = 100      # GB per node

# ============================================================
# Authentication
# ============================================================
credentials = BasicCredentials(ak=AK, sk=SK, project_id=PROJECT_ID)
client = DwsClient.new_builder().with_credentials(credentials) \
    .with_region(DwsRegion.value_of(REGION)) \
    .build()

# ============================================================
# Create DWS Cluster
# ============================================================
print("=" * 60)
print("DWS Cluster Setup for Finance Risk Control")
print("=" * 60)

cluster_request = V2CreateClusterReq(
    name=DWS_CLUSTER_NAME,
    flavor=DWS_FLAVOR,
    num_cn=DWS_NUM_CN,
    num_node=DWS_NUM_NODE,
    db_name=DWS_DB_NAME,
    db_password=DWS_DB_PASSWORD,
    db_port=DWS_DB_PORT,
    vpc_id=VPC_ID,
    subnet_id=SUBNET_ID,
    security_group_id=SECURITY_GROUP_ID,
    availability_zones=["<az>"],      # e.g. la-north-2a
    volume=Volume(volume=DWS_VOLUME_TYPE, capacity=DWS_VOLUME_CAPACITY),
    datastore_version=DWS_DATASTORE_VERSION
)

print(f"\nCreating DWS cluster: {DWS_CLUSTER_NAME}")
print(f"  Flavor: {DWS_FLAVOR}")
print(f"  CN nodes: {DWS_NUM_CN}")
print(f"  Data nodes: {DWS_NUM_NODE}")
print(f"  Datastore: {DWS_DATASTORE_VERSION}")
print(f"  Volume: {DWS_VOLUME_TYPE} {DWS_VOLUME_CAPACITY}GB")

try:
    response = client.create_cluster_v2(request=cluster_request)
    cluster_id = response.cluster.id
    print(f"\nCluster creation initiated: {cluster_id}")
except Exception as e:
    print(f"\nERROR: Failed to create DWS cluster: {e}")
    sys.exit(1)

# ============================================================
# Wait for cluster to become available
# ============================================================
print("\nWaiting for cluster to become available...")
max_wait = 1800  # 30 minutes
waited = 0
interval = 60

while waited < max_wait:
    time.sleep(interval)
    waited += interval
    try:
        cluster_detail = client.show_cluster_detail(cluster_id=cluster_id)
        status = cluster_detail.cluster.status
        print(f"  [{waited}s] Cluster status: {status}")
        if status == "AVAILABLE":
            # Extract connection info
            endpoints = cluster_detail.cluster.endpoints
            print(f"\nDWS cluster is ready!")
            print(f"  Cluster ID: {cluster_id}")
            if endpoints:
                print(f"  Endpoint: {endpoints[0].endpoint}")
                print(f"  Port: {endpoints[0].port}")
            break
        elif status in ["FAILED", "FROZEN"]:
            print(f"\nERROR: Cluster entered state: {status}")
            sys.exit(1)
    except Exception as e:
        print(f"  [{waited}s] Error checking status: {e}")

if waited >= max_wait:
    print(f"\nERROR: Cluster did not become available within {max_wait}s")
    sys.exit(1)

print("\n" + "=" * 60)
print("DWS Cluster Setup Complete")
print("=" * 60)
print(f"Cluster ID: {cluster_id}")
print(f"Next steps:")
print(f"  1. Create tables: gsql -f dws_create_tables.sql")
print(f"  2. Load data:     gsql -f dws_etl_load.sql")
print(f"  3. Generate reports: gsql -f dws_generate_reports.sql")
