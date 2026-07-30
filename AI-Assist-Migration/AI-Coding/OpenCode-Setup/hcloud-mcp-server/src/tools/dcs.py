from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_dcs_instances",
        description="List DCS (Redis) instances",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DCS", "ListInstances", p),
    ),
    ToolDefinition(
        name="hcloud_show_dcs_instance",
        description="Get details of a specific DCS (Redis) instance",
        params={
            "region": {"type": "string", "description": "Region"},
            "instance_id": {"type": "string", "description": "Instance ID"},
        },
        required=["region", "instance_id"],
        build_command=lambda p: build_hcloud_command("DCS", "ShowInstance", p),
    ),
    ToolDefinition(
        name="hcloud_list_dcs_flavors",
        description="List available DCS (Redis) instance flavors/specs",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DCS", "ListFlavors", p),
    ),
    ToolDefinition(
        name="hcloud_list_dcs_available_zones",
        description="List available availability zones for DCS (Redis)",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DCS", "ListAvailableZones", p),
    ),
]
