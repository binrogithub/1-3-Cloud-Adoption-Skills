from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_vpcs",
        description="List VPCs in the region",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
            "offset": {"type": "integer", "description": "Pagination offset"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ListVpcs/v3", p),
    ),
    ToolDefinition(
        name="hcloud_show_vpc",
        description="Get details of a specific VPC",
        params={
            "region": {"type": "string", "description": "Region"},
            "vpc_id": {"type": "string", "description": "VPC ID"},
        },
        required=["region", "vpc_id"],
        build_command=lambda p: build_hcloud_command("VPC", "ShowVpc/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_subnets",
        description="List subnets",
        params={
            "region": {"type": "string", "description": "Region"},
            "vpc_id": {"type": "string", "description": "Filter by VPC ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ListSubnets", p),
    ),
    ToolDefinition(
        name="hcloud_show_subnet",
        description="Get details of a specific subnet",
        params={
            "region": {"type": "string", "description": "Region"},
            "subnet_id": {"type": "string", "description": "Subnet ID"},
        },
        required=["region", "subnet_id"],
        build_command=lambda p: build_hcloud_command("VPC", "ShowSubnet", p),
    ),
    ToolDefinition(
        name="hcloud_list_security_groups",
        description="List security groups",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ListSecurityGroups/v3", p),
    ),
    ToolDefinition(
        name="hcloud_show_security_group",
        description="Get details of a specific security group",
        params={
            "region": {"type": "string", "description": "Region"},
            "security_group_id": {"type": "string", "description": "Security group ID"},
        },
        required=["region", "security_group_id"],
        build_command=lambda p: build_hcloud_command("VPC", "ShowSecurityGroup/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_security_group_rules",
        description="List security group rules",
        params={
            "region": {"type": "string", "description": "Region"},
            "security_group_id": {"type": "string", "description": "Filter by security group ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ListSecurityGroupRules/v3", p, param_mapping={
            "security_group_id": "--security_group_id.1",
        }),
    ),
    ToolDefinition(
        name="hcloud_list_route_tables",
        description="List route tables",
        params={
            "region": {"type": "string", "description": "Region"},
            "vpc_id": {"type": "string", "description": "Filter by VPC ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ListRouteTables", p),
    ),
    ToolDefinition(
        name="hcloud_show_quota",
        description="Show VPC resource quotas",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("VPC", "ShowQuota/v3", p),
    ),
]
