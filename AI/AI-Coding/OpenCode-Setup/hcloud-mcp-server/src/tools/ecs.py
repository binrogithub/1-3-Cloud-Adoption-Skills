from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_servers",
        description="List ECS cloud servers with optional filters",
        params={
            "region": {"type": "string", "description": "Region"},
            "name": {"type": "string", "description": "Filter by server name (fuzzy match)"},
            "status": {"type": "string", "description": "Filter by status: ACTIVE, SHUTOFF, ERROR, BUILD, etc."},
            "flavor_id": {"type": "string", "description": "Filter by flavor ID"},
            "limit": {"type": "integer", "description": "Max number of results"},
            "offset": {"type": "integer", "description": "Offset for pagination"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ECS", "ListServersDetails", p),
    ),
    ToolDefinition(
        name="hcloud_show_server",
        description="Get details of a specific ECS server",
        params={
            "region": {"type": "string", "description": "Region"},
            "server_id": {"type": "string", "description": "Server ID"},
        },
        required=["region", "server_id"],
        build_command=lambda p: build_hcloud_command("ECS", "ShowServer", p),
    ),
    ToolDefinition(
        name="hcloud_list_flavors",
        description="List available ECS instance flavors/specs",
        params={
            "region": {"type": "string", "description": "Region"},
            "availability_zone": {"type": "string", "description": "Filter by availability zone"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ECS", "ListFlavors", p),
    ),
    ToolDefinition(
        name="hcloud_list_availability_zones",
        description="List availability zones for ECS",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ECS", "NovaListAvailabilityZones", p),
    ),
    ToolDefinition(
        name="hcloud_list_server_interfaces",
        description="List network interfaces attached to an ECS server",
        params={
            "region": {"type": "string", "description": "Region"},
            "server_id": {"type": "string", "description": "Server ID"},
        },
        required=["region", "server_id"],
        build_command=lambda p: build_hcloud_command("ECS", "ListServerInterfaces", p),
    ),
    ToolDefinition(
        name="hcloud_list_server_block_devices",
        description="List block devices (volumes) attached to an ECS server",
        params={
            "region": {"type": "string", "description": "Region"},
            "server_id": {"type": "string", "description": "Server ID"},
        },
        required=["region", "server_id"],
        build_command=lambda p: build_hcloud_command("ECS", "ListServerBlockDevices", p),
    ),
    ToolDefinition(
        name="hcloud_list_keypairs",
        description="List SSH key pairs",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ECS", "NovaListKeypairs", p),
    ),
    ToolDefinition(
        name="hcloud_show_server_limits",
        description="Show ECS quota/limits for the tenant",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ECS", "ShowServerLimits", p),
    ),
]
