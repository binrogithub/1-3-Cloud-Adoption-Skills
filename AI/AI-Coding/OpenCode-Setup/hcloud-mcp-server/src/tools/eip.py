from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_public_ips",
        description="List elastic public IPs",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EIP", "ListPublicips/v3", p),
    ),
    ToolDefinition(
        name="hcloud_show_public_ip",
        description="Get details of a specific elastic public IP",
        params={
            "region": {"type": "string", "description": "Region"},
            "publicip_id": {"type": "string", "description": "Public IP ID"},
        },
        required=["region", "publicip_id"],
        build_command=lambda p: build_hcloud_command("EIP", "ShowPublicip/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_bandwidths",
        description="List bandwidths",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EIP", "ListBandwidths", p),
    ),
    ToolDefinition(
        name="hcloud_list_eip_quotas",
        description="List EIP resource quotas",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EIP", "ListQuotas", p),
    ),
]
