#!/usr/bin/env python3
"""Create a minimal 3-node Huawei Cloud DWS cluster for the finance demo.

Credentials are read only from environment variables:
  CLOUD_SDK_AK/CLOUD_SDK_SK or AK/SK

The script intentionally never prints credential values.
"""

from __future__ import annotations

import argparse
import os
import secrets
import stat
import string
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdws.v2 import (
    CreateClusterV2Request,
    DwsClient,
    ListClustersRequest,
    ListNodeTypesRequest,
    PublicIp,
    V2CreateCluster,
    V2CreateClusterReq,
    Volume,
)
from huaweicloudsdkdws.v2.region.dws_region import DwsRegion
from huaweicloudsdkvpc.v2 import (
    CreateSecurityGroupOption,
    CreateSecurityGroupRequest,
    CreateSecurityGroupRequestBody,
    CreateSecurityGroupRuleOption,
    CreateSecurityGroupRuleRequest,
    CreateSecurityGroupRuleRequestBody,
    CreateSubnetOption,
    CreateSubnetRequest,
    CreateSubnetRequestBody,
    CreateVpcOption,
    CreateVpcRequest,
    CreateVpcRequestBody,
    ListSecurityGroupsRequest,
    ListSubnetsRequest,
    ListVpcsRequest,
    VpcClient,
)
from huaweicloudsdkvpc.v2.region.vpc_region import VpcRegion


DEFAULT_PROJECT_ID = "89a76cc1484440b38810ecb9e3b5c0d7"
DEFAULT_REGION = "la-south-2"
DEFAULT_CLUSTER_NAME = "dws-finance-demo-min3"
DEFAULT_DB_USER = "dbadmin"
DEFAULT_DB_PORT = 8000
DEFAULT_VPC_NAME = "dws-finance-demo-vpc"
DEFAULT_SUBNET_NAME = "dws-finance-demo-subnet"
DEFAULT_SG_NAME = "dws-finance-demo-sg"
DEFAULT_VPC_CIDR = "192.168.80.0/20"
DEFAULT_SUBNET_CIDR = "192.168.80.0/24"
DEFAULT_GATEWAY = "192.168.80.1"


def first_attr(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def object_id(obj: Any) -> str:
    return str(first_attr(obj, ("id", "vpc_id", "subnet_id", "security_group_id")))


def object_name(obj: Any) -> str:
    return str(first_attr(obj, ("name",), ""))


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    # DWS password policies usually require mixed classes and special chars.
    return (
        "Pw1!"
        + "".join(secrets.choice(alphabet) for _ in range(length - 4))
    )


def require_credentials(project_id: str) -> BasicCredentials:
    ak = os.getenv("CLOUD_SDK_AK") or os.getenv("AK")
    sk = os.getenv("CLOUD_SDK_SK") or os.getenv("SK")
    if not ak or not sk:
        raise RuntimeError("Missing AK/SK. Export CLOUD_SDK_AK/CLOUD_SDK_SK or AK/SK before running.")
    return BasicCredentials(ak, sk, project_id)


def dws_client(credentials: BasicCredentials, region: str) -> DwsClient:
    return DwsClient.new_builder().with_credentials(credentials).with_region(DwsRegion.value_of(region)).build()


def vpc_client(credentials: BasicCredentials, region: str) -> VpcClient:
    return VpcClient.new_builder().with_credentials(credentials).with_region(VpcRegion.value_of(region)).build()


def list_items(response: Any, attr: str) -> list[Any]:
    value = getattr(response, attr, None)
    return list(value or [])


def find_by_name(items: Iterable[Any], name: str) -> Optional[Any]:
    for item in items:
        if object_name(item) == name:
            return item
    return None


def choose_node_type(client: DwsClient, preferred_flavor: Optional[str]) -> tuple[str, str, str, Optional[Volume], int]:
    response = client.list_node_types(ListNodeTypesRequest())
    node_types = list_items(response, "node_types")
    candidates = []

    for node_type in node_types:
        datastore_type = first_attr(node_type, ("datastore_type",), "")
        if datastore_type and datastore_type != "dws":
            continue

        normal_azs = [
            az
            for az in (first_attr(node_type, ("available_zones",), []) or [])
            if first_attr(az, ("status",), "") == "normal"
        ]
        if not normal_azs:
            continue

        datastores = first_attr(node_type, ("datastores",), []) or []
        stable_datastores = [
            ds for ds in datastores
            if first_attr(ds, ("role",), "STABLE") in ("STABLE", None, "")
        ] or datastores
        if not stable_datastores:
            continue

        spec_name = first_attr(node_type, ("spec_name",), "")
        if preferred_flavor and spec_name != preferred_flavor:
            continue

        datastore = sorted(stable_datastores, key=lambda ds: first_attr(ds, ("version",), ""), reverse=True)[0]
        volume = None
        elastic_specs = first_attr(node_type, ("elastic_volume_specs",), []) or []
        if elastic_specs:
            spec = sorted(elastic_specs, key=lambda item: int(first_attr(item, ("min_size",), 10**9)))[0]
            volume = Volume(
                volume=first_attr(spec, ("type",), "SSD"),
                capacity=int(first_attr(spec, ("min_size",), 100)),
            )

        candidates.append(
            (
                int(first_attr(node_type, ("vcpus",), 999999)),
                int(first_attr(node_type, ("ram",), 999999)),
                spec_name,
                first_attr(normal_azs[0], ("code",), ""),
                first_attr(datastore, ("version",), ""),
                volume,
                int(first_attr(first_attr(datastore, ("attachments",), None), ("min_cn",), 2) or 2),
            )
        )

    if not candidates:
        raise RuntimeError("No available DWS node type found in the target region.")

    _, _, flavor, az, version, volume, min_cn = sorted(candidates)[0]
    return flavor, az, version, volume, min_cn


def ensure_vpc(client: VpcClient, name: str, cidr: str, enterprise_project_id: Optional[str]) -> Any:
    existing = find_by_name(list_items(client.list_vpcs(ListVpcsRequest(limit=100)), "vpcs"), name)
    if existing:
        print(f"Using existing VPC: {name} ({object_id(existing)})")
        return existing

    request = CreateVpcRequest(
        body=CreateVpcRequestBody(
            vpc=CreateVpcOption(
                name=name,
                cidr=cidr,
                description="Finance DWS migration demo VPC",
                enterprise_project_id=enterprise_project_id,
            )
        )
    )
    response = client.create_vpc(request)
    vpc = response.vpc
    print(f"Created VPC: {name} ({object_id(vpc)})")
    return vpc


def ensure_subnet(client: VpcClient, name: str, vpc_id: str, cidr: str, gateway: str, az: str) -> Any:
    existing = find_by_name(list_items(client.list_subnets(ListSubnetsRequest(limit=100, vpc_id=vpc_id)), "subnets"), name)
    if existing:
        print(f"Using existing subnet: {name} ({object_id(existing)})")
        return existing

    request = CreateSubnetRequest(
        body=CreateSubnetRequestBody(
            subnet=CreateSubnetOption(
                name=name,
                cidr=cidr,
                vpc_id=vpc_id,
                gateway_ip=gateway,
                dhcp_enable=True,
                availability_zone=az,
            )
        )
    )
    response = client.create_subnet(request)
    subnet = response.subnet
    print(f"Created subnet: {name} ({object_id(subnet)})")
    return subnet


def ensure_security_group(client: VpcClient, name: str, vpc_id: str, enterprise_project_id: Optional[str]) -> Any:
    existing = find_by_name(
        list_items(client.list_security_groups(ListSecurityGroupsRequest(limit=100, vpc_id=vpc_id)), "security_groups"),
        name,
    )
    if existing:
        print(f"Using existing security group: {name} ({object_id(existing)})")
        return existing

    response = client.create_security_group(
        CreateSecurityGroupRequest(
            body=CreateSecurityGroupRequestBody(
                security_group=CreateSecurityGroupOption(
                    name=name,
                    vpc_id=vpc_id,
                    enterprise_project_id=enterprise_project_id,
                )
            )
        )
    )
    sg = response.security_group
    print(f"Created security group: {name} ({object_id(sg)})")

    # Allow DWS access only inside the demo subnet. Public access is disabled by default.
    client.create_security_group_rule(
        CreateSecurityGroupRuleRequest(
            body=CreateSecurityGroupRuleRequestBody(
                security_group_rule=CreateSecurityGroupRuleOption(
                    security_group_id=object_id(sg),
                    direction="ingress",
                    ethertype="IPv4",
                    protocol="tcp",
                    port_range_min=DEFAULT_DB_PORT,
                    port_range_max=DEFAULT_DB_PORT,
                    remote_ip_prefix=DEFAULT_SUBNET_CIDR,
                    description="Allow DWS SQL access from demo subnet",
                )
            )
        )
    )
    return sg


def existing_cluster(client: DwsClient, name: str) -> Optional[Any]:
    response = client.list_clusters(ListClustersRequest())
    for cluster in list_items(response, "clusters"):
        if object_name(cluster) == name:
            return cluster
    return None


def write_password_file(cluster_name: str, password: str) -> Path:
    secrets_dir = Path(".secrets")
    secrets_dir.mkdir(mode=0o700, exist_ok=True)
    path = secrets_dir / f"{cluster_name}.env"
    path.write_text(f"DWS_DB_PASSWORD='{password}'\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a minimal Huawei Cloud DWS demo cluster.")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--cluster-name", default=DEFAULT_CLUSTER_NAME)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER, help="DWS administrator username passed as db_name.")
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--node-count", type=int, default=3)
    parser.add_argument("--num-cn", type=int, default=None)
    parser.add_argument("--flavor", default=os.getenv("DWS_FLAVOR"))
    parser.add_argument("--vpc-name", default=DEFAULT_VPC_NAME)
    parser.add_argument("--subnet-name", default=DEFAULT_SUBNET_NAME)
    parser.add_argument("--security-group-name", default=DEFAULT_SG_NAME)
    parser.add_argument("--vpc-cidr", default=DEFAULT_VPC_CIDR)
    parser.add_argument("--subnet-cidr", default=DEFAULT_SUBNET_CIDR)
    parser.add_argument("--gateway-ip", default=DEFAULT_GATEWAY)
    parser.add_argument("--enterprise-project-id", default=os.getenv("ENTERPRISE_PROJECT_ID"))
    parser.add_argument("--public-ip", action="store_true", help="Auto-assign a public EIP to the DWS cluster.")
    args = parser.parse_args()

    if args.node_count < 3:
        raise RuntimeError("DWS standard clusters require at least 3 nodes.")

    credentials = require_credentials(args.project_id)
    dws = dws_client(credentials, args.region)
    vpc = vpc_client(credentials, args.region)

    cluster = existing_cluster(dws, args.cluster_name)
    if cluster:
        print(f"Cluster already exists: {args.cluster_name}")
        print(cluster)
        return 0

    flavor, az, datastore_version, volume, min_cn = choose_node_type(dws, args.flavor)
    if min_cn > args.node_count:
        raise RuntimeError(f"Selected DWS datastore requires at least {min_cn} CNs, above node_count={args.node_count}.")
    num_cn = args.num_cn or min_cn
    if num_cn < min_cn or num_cn > args.node_count:
        raise RuntimeError(f"num_cn must be between {min_cn} and node_count={args.node_count}.")

    selected_vpc = ensure_vpc(vpc, args.vpc_name, args.vpc_cidr, args.enterprise_project_id)
    selected_subnet = ensure_subnet(vpc, args.subnet_name, object_id(selected_vpc), args.subnet_cidr, args.gateway_ip, az)
    # Subnet creation can be eventually consistent.
    time.sleep(5)
    selected_sg = ensure_security_group(vpc, args.security_group_name, object_id(selected_vpc), args.enterprise_project_id)

    db_password = os.getenv("DWS_DB_PASSWORD")
    password_file = None
    if not db_password:
        db_password = generate_password()
        password_file = write_password_file(args.cluster_name, db_password)

    public_ip = PublicIp(public_bind_type="auto_assign", eip_id="") if args.public_ip else None
    body = V2CreateClusterReq(
        cluster=V2CreateCluster(
            name=args.cluster_name,
            flavor=flavor,
            num_cn=num_cn,
            num_node=args.node_count,
            db_name=args.db_user,
            db_password=db_password,
            db_port=args.db_port,
            availability_zones=[az],
            vpc_id=object_id(selected_vpc),
            subnet_id=object_id(selected_subnet),
            security_group_id=object_id(selected_sg),
            public_ip=public_ip,
            datastore_version=datastore_version,
            volume=volume,
            enterprise_project_id=args.enterprise_project_id,
        )
    )

    response = dws.create_cluster_v2(CreateClusterV2Request(body=body))
    print("Create request accepted.")
    print(f"cluster_name={args.cluster_name}")
    print(f"region={args.region}")
    print(f"project_id={args.project_id}")
    print(f"flavor={flavor}")
    print(f"nodes={args.node_count}")
    print(f"num_cn={num_cn}")
    print(f"az={az}")
    print(f"datastore_version={datastore_version}")
    print(f"vpc_id={object_id(selected_vpc)}")
    print(f"subnet_id={object_id(selected_subnet)}")
    print(f"security_group_id={object_id(selected_sg)}")
    if password_file:
        print(f"Generated DB password saved with 0600 permissions: {password_file}")
    print(response)
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
