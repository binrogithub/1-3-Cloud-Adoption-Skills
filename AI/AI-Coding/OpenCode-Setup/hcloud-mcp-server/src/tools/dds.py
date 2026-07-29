from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_dds_instances",
        description="List DDS (MongoDB) instances",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DDS", "ListInstances", p),
    ),
    ToolDefinition(
        name="hcloud_list_dds_flavors",
        description="List available DDS (MongoDB) instance flavors/specs",
        params={
            "region": {"type": "string", "description": "Region"},
            "engine": {"type": "string", "description": "Database engine"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DDS", "ListFlavors", p),
    ),
    ToolDefinition(
        name="hcloud_list_dds_storage_types",
        description="List available DDS (MongoDB) storage types",
        params={
            "region": {"type": "string", "description": "Region"},
            "engine": {"type": "string", "description": "Database engine"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DDS", "ListStorageType", p),
    ),
]
