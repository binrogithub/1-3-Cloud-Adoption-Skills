#!/usr/bin/env python3
"""Provision CSS + ECS for code-search MCP from scratch.

Required environment variables:
  HWC_ACCESS_KEY_ID
  HWC_SECRET_ACCESS_KEY
  HWC_PROJECT_ID

Optional environment variables:
  HWC_REGION              default: la-north-2
  HWC_AZ                  default: <region>a
  HWC_ALLOWED_CIDR        default: auto-detect via api.ipify.org
  HWC_NAME_PREFIX         default: css-search-<UTC timestamp>
  HWC_VPC_ID              reuse existing VPC (requires HWC_SUBNET_ID)
  HWC_SUBNET_ID           reuse existing subnet
  HWC_STATE_PATH          default: ./<prefix>-state.json
  HWC_SSH_KEY_PATH        default: ~/.ssh/<prefix>
  HWC_CSS_VOLUME_TYPE     default: COMMON (falls back to HIGH on CSS.0065)
  HWC_ECS_FLAVOR          default: s6.xlarge.2
  HWC_ECS_IMAGE_ID        default: 67c29d17-33bd-43f0-a17b-ed2015798bb8
  HWC_REPO_URL            default: https://github.com/binrogithub/1-3-Cloud-Adoption-Skills
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcss.v1 import (
    CreateClusterBody,
    CreateClusterDatastoreBody,
    CreateClusterInstanceBody,
    CreateClusterInstanceNicsBody,
    CreateClusterInstanceVolumeBody,
    CreateClusterReq,
    CreateClusterRequest,
    CssClient,
)
from huaweicloudsdkcss.v1.region.css_region import CssRegion
from huaweicloudsdkecs.v2 import (
    CreatePostPaidServersRequest,
    CreatePostPaidServersRequestBody,
    EcsClient,
    NovaCreateKeypairOption,
    NovaCreateKeypairRequest,
    NovaCreateKeypairRequestBody,
    PostPaidServer,
    PostPaidServerEip,
    PostPaidServerEipBandwidth,
    PostPaidServerNic,
    PostPaidServerPublicip,
    PostPaidServerRootVolume,
    PostPaidServerSecurityGroup,
)
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkiam.v3.region.iam_region import IamRegion
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
    ShowSubnetRequest,
    VpcClient,
)
from huaweicloudsdkvpc.v2.region.vpc_region import VpcRegion


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value or ""


def public_cidr() -> str:
    configured = os.environ.get("HWC_ALLOWED_CIDR")
    if configured:
        return configured
    try:
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode("ascii").strip()
        return f"{ip}/32"
    except Exception:
        raise SystemExit("Set HWC_ALLOWED_CIDR; current public IP could not be discovered")


def make_context() -> dict:
    region = env("HWC_REGION", "la-north-2")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    prefix = env("HWC_NAME_PREFIX", f"css-search-{stamp}")
    return {
        "ak": env("HWC_ACCESS_KEY_ID", required=True),
        "sk": env("HWC_SECRET_ACCESS_KEY", required=True),
        "project_id": env("HWC_PROJECT_ID", required=True),
        "region": region,
        "az": env("HWC_AZ", f"{region}a"),
        "allowed_cidr": public_cidr(),
        "prefix": prefix,
        "existing_vpc_id": os.environ.get("HWC_VPC_ID"),
        "existing_subnet_id": os.environ.get("HWC_SUBNET_ID"),
        "state_path": Path(env("HWC_STATE_PATH", f"./{prefix}-state.json")).expanduser(),
        "ssh_key_path": Path(env("HWC_SSH_KEY_PATH", f"~/.ssh/{prefix}")).expanduser(),
        "css_volume_type": env("HWC_CSS_VOLUME_TYPE", "COMMON"),
        "ecs_flavor": env("HWC_ECS_FLAVOR", "s6.xlarge.2"),
        "ecs_image_id": env("HWC_ECS_IMAGE_ID", "67c29d17-33bd-43f0-a17b-ed2015798bb8"),
        "repo_url": env("HWC_REPO_URL", "https://github.com/binrogithub/1-3-Cloud-Adoption-Skills"),
    }


def clients(ctx: dict) -> tuple[VpcClient, EcsClient, CssClient]:
    cred = BasicCredentials(ctx["ak"], ctx["sk"], ctx["project_id"])
    return (
        VpcClient.new_builder().with_credentials(cred).with_region(VpcRegion.value_of(ctx["region"])).build(),
        EcsClient.new_builder().with_credentials(cred).with_region(EcsRegion.value_of(ctx["region"])).build(),
        CssClient.new_builder().with_credentials(cred).with_region(CssRegion.value_of(ctx["region"])).build(),
    )


def verify_project(ctx: dict) -> None:
    client = IamClient.new_builder().with_credentials(GlobalCredentials(ctx["ak"], ctx["sk"])).with_region(
        IamRegion.value_of("ap-southeast-1")
    ).build()
    resp = client.keystone_list_projects(KeystoneListProjectsRequest(name=ctx["region"]))
    projects = resp.projects or []
    if not any(p.id == ctx["project_id"] and p.enabled for p in projects):
        raise RuntimeError(f"Project {ctx['project_id']} for {ctx['region']} was not found or is disabled")


def ensure_keypair(ctx: dict, ecs: EcsClient) -> str:
    key_path = ctx["ssh_key_path"]
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not key_path.exists():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", ctx["prefix"]],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        key_path.chmod(0o600)
    public_key = key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()
    try:
        ecs.nova_create_keypair(
            NovaCreateKeypairRequest(
                body=NovaCreateKeypairRequestBody(
                    keypair=NovaCreateKeypairOption(name=ctx["prefix"], public_key=public_key)
                )
            )
        )
    except Exception as exc:
        if "already" not in str(exc).lower():
            raise
    return ctx["prefix"]


def add_rules(vpc: VpcClient, sg_id: str, cidr: str) -> None:
    for port in (22, 4000, 8788):
        vpc.create_security_group_rule(
            CreateSecurityGroupRuleRequest(
                body=CreateSecurityGroupRuleRequestBody(
                    security_group_rule=CreateSecurityGroupRuleOption(
                        security_group_id=sg_id,
                        direction="ingress",
                        ethertype="IPv4",
                        protocol="tcp",
                        port_range_min=port,
                        port_range_max=port,
                        remote_ip_prefix=cidr,
                    )
                )
            )
        )


def create_network(ctx: dict, vpc: VpcClient) -> dict:
    if bool(ctx["existing_vpc_id"]) != bool(ctx["existing_subnet_id"]):
        raise SystemExit("Set both HWC_VPC_ID and HWC_SUBNET_ID, or neither")
    if ctx["existing_vpc_id"]:
        subnet = vpc.show_subnet(ShowSubnetRequest(subnet_id=ctx["existing_subnet_id"])).subnet
        vpc_id = ctx["existing_vpc_id"]
    else:
        vpc_id = vpc.create_vpc(
            CreateVpcRequest(
                body=CreateVpcRequestBody(vpc=CreateVpcOption(name=f"{ctx['prefix']}-vpc", cidr="10.42.0.0/16"))
            )
        ).vpc.id
        subnet = vpc.create_subnet(
            CreateSubnetRequest(
                body=CreateSubnetRequestBody(
                    subnet=CreateSubnetOption(
                        name=f"{ctx['prefix']}-subnet",
                        cidr="10.42.1.0/24",
                        gateway_ip="10.42.1.1",
                        vpc_id=vpc_id,
                        availability_zone=ctx["az"],
                        dhcp_enable=True,
                        primary_dns="100.125.1.250",
                        secondary_dns="100.125.21.250",
                    )
                )
            )
        ).subnet
    sg = vpc.create_security_group(
        CreateSecurityGroupRequest(
            body=CreateSecurityGroupRequestBody(
                security_group=CreateSecurityGroupOption(name=f"{ctx['prefix']}-sg", vpc_id=vpc_id)
            )
        )
    ).security_group
    add_rules(vpc, sg.id, ctx["allowed_cidr"])
    return {
        "vpc_id": vpc_id,
        "subnet_id": subnet.id,
        "subnet_network_id": getattr(subnet, "neutron_network_id", None)
        or getattr(subnet, "neutron_subnet_id", None)
        or subnet.id,
        "security_group_id": sg.id,
        "reused_existing_vpc": bool(ctx["existing_vpc_id"]),
    }


def create_css(ctx: dict, css: CssClient, network: dict, volume_type: str) -> dict:
    body = CreateClusterReq(
        cluster=CreateClusterBody(
            name=f"{ctx['prefix']}-css",
            instance_num=1,
            datastore=CreateClusterDatastoreBody(type="elasticsearch", version="7.10.2"),
            instance=CreateClusterInstanceBody(
                flavor_ref="ess.spec-4u8g",
                volume=CreateClusterInstanceVolumeBody(volume_type=volume_type, size=40),
                nics=CreateClusterInstanceNicsBody(
                    vpc_id=network["vpc_id"],
                    net_id=network["subnet_id"],
                    security_group_id=network["security_group_id"],
                ),
                availability_zone=ctx["az"],
            ),
            https_enable=False,
            authority_enable=False,
        )
    )
    resp = css.create_cluster(CreateClusterRequest(body=body))
    cluster_data = json.loads(str(resp))
    cluster_id = cluster_data.get("cluster", {}).get("id", "")
    return {"name": f"{ctx['prefix']}-css", "id": cluster_id, "volume_type_used": volume_type}


def create_css_with_fallback(ctx: dict, css: CssClient, network: dict) -> dict:
    volume_type = ctx["css_volume_type"]
    try:
        print(f"Creating CSS cluster with {volume_type} disk...")
        return create_css(ctx, css, network, volume_type)
    except Exception as exc:
        err = str(exc)
        if "CSS.0065" in err or "disk has been sold out" in err.lower():
            fallback = "HIGH" if volume_type != "HIGH" else "COMMON"
            print(f"  {volume_type} disk sold out, retrying with {fallback}...")
            return create_css(ctx, css, network, fallback)
        raise


def create_ecs(ctx: dict, ecs: EcsClient, network: dict, key_name: str) -> dict:
    server = PostPaidServer(
        name=f"{ctx['prefix']}-ecs",
        image_ref=ctx["ecs_image_id"],
        flavor_ref=ctx["ecs_flavor"],
        vpcid=network["vpc_id"],
        nics=[PostPaidServerNic(subnet_id=network["subnet_network_id"])],
        security_groups=[PostPaidServerSecurityGroup(id=network["security_group_id"])],
        root_volume=PostPaidServerRootVolume(volumetype="SSD", size=100),
        publicip=PostPaidServerPublicip(
            eip=PostPaidServerEip(
                iptype="5_bgp",
                bandwidth=PostPaidServerEipBandwidth(size=5, sharetype="PER", chargemode="traffic"),
            ),
            delete_on_termination=True,
        ),
        availability_zone=ctx["az"],
        count=1,
        key_name=key_name,
        description="CSS Code Search MCP host",
    )
    resp = ecs.create_post_paid_servers(CreatePostPaidServersRequest(body=CreatePostPaidServersRequestBody(server=server)))
    resp_data = json.loads(str(resp))
    server_id = resp_data.get("serverIds", [""])[0]
    return {"id": server_id, "job_id": resp_data.get("job_id", "")}


def main() -> None:
    ctx = make_context()
    verify_project(ctx)
    vpc, ecs, css = clients(ctx)
    key_name = ensure_keypair(ctx, ecs)
    network = create_network(ctx, vpc)
    css_info = create_css_with_fallback(ctx, css, network)
    ecs_info = create_ecs(ctx, ecs, network, key_name)
    state = {
        "region": ctx["region"],
        "project_id": ctx["project_id"],
        "allowed_cidr": ctx["allowed_cidr"],
        "prefix": ctx["prefix"],
        "ssh_user": "root",
        "ssh_key_path": str(ctx["ssh_key_path"]),
        "repo_url": ctx["repo_url"],
        "network": network,
        "css": css_info,
        "ecs": ecs_info,
        "notes": "Run poll_readiness.py to discover css_endpoint and ecs_public_ip.",
    }
    ctx["state_path"].write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
