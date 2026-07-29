from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_volumes",
        description="List EVS disk volumes",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EVS", "ListVolumes", p),
    ),
    ToolDefinition(
        name="hcloud_show_volume",
        description="Get details of a specific EVS volume",
        params={
            "region": {"type": "string", "description": "Region"},
            "volume_id": {"type": "string", "description": "Volume ID"},
        },
        required=["region", "volume_id"],
        build_command=lambda p: build_hcloud_command("EVS", "ShowVolume", p),
    ),
    ToolDefinition(
        name="hcloud_list_snapshots",
        description="List EVS volume snapshots",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EVS", "ListSnapshots", p),
    ),
    ToolDefinition(
        name="hcloud_show_snapshot",
        description="Get details of a specific EVS snapshot",
        params={
            "region": {"type": "string", "description": "Region"},
            "snapshot_id": {"type": "string", "description": "Snapshot ID"},
        },
        required=["region", "snapshot_id"],
        build_command=lambda p: build_hcloud_command("EVS", "ShowSnapshot", p),
    ),
    ToolDefinition(
        name="hcloud_list_volume_types",
        description="List available EVS volume types",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("EVS", "CinderListVolumeTypes", p),
    ),
]
