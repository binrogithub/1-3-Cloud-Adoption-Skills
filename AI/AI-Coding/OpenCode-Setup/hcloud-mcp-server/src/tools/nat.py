from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_nat_gateways",
        description="List NAT gateways",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("NAT", "ListNatGateways", p),
    ),
    ToolDefinition(
        name="hcloud_show_nat_gateway",
        description="Get details of a specific NAT gateway",
        params={
            "region": {"type": "string", "description": "Region"},
            "nat_gateway_id": {"type": "string", "description": "NAT gateway ID"},
        },
        required=["region", "nat_gateway_id"],
        build_command=lambda p: build_hcloud_command("NAT", "ShowNatGateway", p),
    ),
    ToolDefinition(
        name="hcloud_list_nat_gateway_snat_rules",
        description="List SNAT rules on a NAT gateway",
        params={
            "region": {"type": "string", "description": "Region"},
            "nat_gateway_id": {"type": "string", "description": "NAT gateway ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("NAT", "ListNatGatewaySnatRules", p),
    ),
    ToolDefinition(
        name="hcloud_list_nat_gateway_dnat_rules",
        description="List DNAT rules on a NAT gateway",
        params={
            "region": {"type": "string", "description": "Region"},
            "nat_gateway_id": {"type": "string", "description": "NAT gateway ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("NAT", "ListNatGatewayDnatRules", p),
    ),
]
