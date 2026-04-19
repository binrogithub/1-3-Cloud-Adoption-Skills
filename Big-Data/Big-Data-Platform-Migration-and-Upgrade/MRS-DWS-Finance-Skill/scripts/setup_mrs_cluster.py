#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_mrs_cluster.py
Provision MRS cluster for financial risk control with Spark, Hive, HBase
"""

import sys
import time

# Huawei Cloud SDK
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkmrs.v1.region.mrs_region import MrsRegion
from huaweicloudsdkmrs.v1 import MrsClient
from huaweicloudsdkmrs.v1.model import CreateClusterReqV2

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

MRS_CLUSTER_NAME = "mrs-finance-risk"
MRS_VERSION = "MRS 3.1.5"    # LTS version with Spark 3.x
MRS_MASTER_FLAVOR = "c6.4xlarge.4.linux.mrs"
MRS_CORE_FLAVOR = "c6.4xlarge.4.linux.mrs"
MRS_MASTER_COUNT = 3         # HA: 3 master nodes
MRS_CORE_COUNT = 3           # Minimum for Spark HA

# ============================================================
# Authentication
# ============================================================
credentials = BasicCredentials(ak=AK, sk=SK, project_id=PROJECT_ID)
client = MrsClient.new_builder().with_credentials(credentials) \
    .with_region(MrsRegion.value_of(REGION)) \
    .build()

# ============================================================
# Create MRS Cluster
# ============================================================
print("=" * 60)
print("MRS Cluster Setup for Finance Risk Control")
print("=" * 60)

# Define components: Spark + Hive + HBase + ZooKeeper
cluster_request = CreateClusterReqV2(
    cluster_name=MRS_CLUSTER_NAME,
    cluster_version=MRS_VERSION,
    cluster_type="ANALYSIS",          # Analysis cluster (not streaming)
    master_node_num=MRS_MASTER_COUNT,
    core_node_num=MRS_CORE_COUNT,
    master_node_size=MRS_MASTER_FLAVOR,
    core_node_size=MRS_CORE_FLAVOR,
    vpc_id=VPC_ID,
    subnet_id=SUBNET_ID,
    security_group_id_default=SECURITY_GROUP_ID,
    volume_type="SSD",                # SSD for I/O intensive analysis
    volume_size=200,                  # 200 GB per node
    safe_mode="0",                    # Normal mode (not Kerberos)
    component_list=[
        {"component_name": "Spark"},
        {"component_name": "Hive"},
        {"component_name": "HBase"},
        {"component_name": "ZooKeeper"},
    ]
)

print(f"\nCreating MRS cluster: {MRS_CLUSTER_NAME}")
print(f"  Version: {MRS_VERSION}")
print(f"  Master nodes: {MRS_MASTER_COUNT} x {MRS_MASTER_FLAVOR}")
print(f"  Core nodes: {MRS_CORE_COUNT} x {MRS_CORE_FLAVOR}")
print(f"  Components: Spark, Hive, HBase, ZooKeeper")

try:
    response = client.create_cluster_v2(request=cluster_request)
    cluster_id = response.cluster_id
    print(f"\nCluster creation initiated: {cluster_id}")
except Exception as e:
    print(f"\nERROR: Failed to create MRS cluster: {e}")
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
        status = cluster_detail.cluster_detail.cluster_state
        print(f"  [{waited}s] Cluster status: {status}")
        if status == "running":
            print(f"\nMRS cluster is ready!")
            print(f"  Cluster ID: {cluster_id}")
            print(f"  Cluster Name: {MRS_CLUSTER_NAME}")
            break
        elif status in ["failed", "abnormal"]:
            print(f"\nERROR: Cluster entered state: {status}")
            sys.exit(1)
    except Exception as e:
        print(f"  [{waited}s] Error checking status: {e}")

if waited >= max_wait:
    print(f"\nERROR: Cluster did not become available within {max_wait}s")
    sys.exit(1)

print("\n" + "=" * 60)
print("MRS Cluster Setup Complete")
print("=" * 60)
print(f"Cluster ID: {cluster_id}")
print(f"Next steps:")
print(f"  1. Upload data to OBS: ./load_raw_data_to_obs.sh")
print(f"  2. Register Hive tables: ./register_hive_tables.sql")
print(f"  3. Run risk analysis: spark-submit spark_risk_analysis.py")
