#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
example_discover_resources.py
Discover Huawei Cloud resources needed for MRS and DWS cluster creation.
This script queries VPC, Subnet, Security Group, DWS node types,
datastore versions, and availability zones.

Usage:
    python example_discover_resources.py

Requirements:
    pip install huaweicloudsdkcore huaweicloudsdkvpc huaweicloudsdkdws
"""

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.http.http_config import HttpConfig

# ============================================================
# Configuration (replace placeholders before running)
# ============================================================
AK = "<ak>"
SK = "<sk>"
REGION = "<region>"           # e.g. la-north-2
PROJECT_ID = "<project_id>"


def create_credentials():
    """Create basic credentials with timeout config."""
    credentials = BasicCredentials(ak=AK, sk=SK, project_id=PROJECT_ID)
    config = HttpConfig.get_default_config()
    config.timeout = 60
    return credentials, config


def discover_network_resources():
    """Discover VPC, Subnet, and Security Group resources."""
    from huaweicloudsdkvpc.v2.region.vpc_region import VpcRegion
    from huaweicloudsdkvpc.v2 import VpcClient, ListVpcsRequest, ListSubnetsRequest
    from huaweicloudsdkvpc.v3.region.vpc_region import VpcRegion as VpcRegionV3
    from huaweicloudsdkvpc.v3 import VpcClient as VpcClientV3, ListSecurityGroupsRequest

    credentials, config = create_credentials()

    # VPC V2 client
    vpc_client = VpcClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(VpcRegion.value_of(REGION)) \
        .with_http_config(config) \
        .build()

    # VPC V3 client (for security groups)
    vpc_client_v3 = VpcClientV3.new_builder() \
        .with_credentials(credentials) \
        .with_region(VpcRegionV3.value_of(REGION)) \
        .with_http_config(config) \
        .build()

    print("=" * 60)
    print("Network Resource Discovery")
    print("=" * 60)

    # Query VPCs
    print("\n1. VPCs:")
    vpcs = vpc_client.list_vpcs(ListVpcsRequest()).vpcs
    for vpc in (vpcs or []):
        print(f"   - ID: {vpc.id}, Name: {vpc.name}, CIDR: {vpc.cidr}")

    if not vpcs:
        print("   No VPCs found. Create a VPC first.")
        return None, None, None

    selected_vpc = vpcs[0]
    vpc_id = selected_vpc.id

    # Query Subnets
    print(f"\n2. Subnets (VPC: {vpc_id}):")
    subnets = vpc_client.list_subnets(ListSubnetsRequest(vpc_id=vpc_id)).subnets
    for subnet in (subnets or []):
        print(f"   - ID: {subnet.id}, Name: {subnet.name}, CIDR: {subnet.cidr}")

    if not subnets:
        print("   No subnets found.")
        return vpc_id, None, None

    selected_subnet = subnets[0]
    subnet_id = selected_subnet.id

    # Query Security Groups
    print("\n3. Security Groups:")
    sgs = vpc_client_v3.list_security_groups(ListSecurityGroupsRequest()).security_groups
    for sg in (sgs or []):
        print(f"   - ID: {sg.id}, Name: {sg.name}")

    if not sgs:
        print("   No security groups found.")
        return vpc_id, subnet_id, None

    selected_sg = sgs[0]
    sg_id = selected_sg.id

    print(f"\nSelected: VPC={vpc_id}, Subnet={subnet_id}, SG={sg_id}")
    return vpc_id, subnet_id, sg_id


def discover_dws_specs():
    """Discover DWS node types, datastore versions, and availability zones."""
    from huaweicloudsdkdws.v2.region.dws_region import DwsRegion
    from huaweicloudsdkdws.v2 import DwsClient, ListNodeTypesRequest
    from huaweicloudsdkdws.v2 import ListAvailabilityZonesRequest

    credentials, config = create_credentials()

    client = DwsClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(DwsRegion.value_of(REGION)) \
        .with_http_config(config) \
        .build()

    print("\n" + "=" * 60)
    print("DWS Specification Discovery")
    print("=" * 60)

    # Query Node Types
    print("\n1. Node Types:")
    try:
        response = client.list_node_types(ListNodeTypesRequest())
        if hasattr(response, 'node_types'):
            for nt in response.node_types:
                type_name = getattr(nt, 'type_name', 'N/A')
                print(f"\n   Flavor: {type_name}")
                if hasattr(nt, 'datastores') and nt.datastores:
                    for ds in nt.datastores:
                        version = getattr(ds, 'version', 'N/A')
                        print(f"     Version: {version}")
                        if hasattr(ds, 'attachments') and ds.attachments:
                            for att in ds.attachments:
                                min_cn = getattr(att, 'min_cn', 'N/A')
                                max_cn = getattr(att, 'max_cn', 'N/A')
                                print(f"       CN range: {min_cn} - {max_cn}")
    except Exception as e:
        print(f"   Error: {str(e)[:200]}")

    # Query Availability Zones
    print("\n2. Availability Zones:")
    try:
        response = client.list_availability_zones(ListAvailabilityZonesRequest())
        print(f"   {response}")
    except Exception as e:
        print(f"   Error: {str(e)[:200]}")


if __name__ == "__main__":
    print("Huawei Cloud Resource Discovery for MRS-DWS Finance Skill")
    print()

    # Discover network resources
    vpc_id, subnet_id, sg_id = discover_network_resources()

    # Discover DWS specifications
    discover_dws_specs()

    print("\n" + "=" * 60)
    print("Discovery Complete")
    print("=" * 60)
    print("\nUse the discovered resource IDs in:")
    print("  - scripts/setup_mrs_cluster.py")
    print("  - scripts/setup_dws_cluster.py")
