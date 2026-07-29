from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_images",
        description="List available IMS images (essential for finding image_ref for ECS/CCE/AS)",
        params={
            "region": {"type": "string", "description": "Region"},
            "imagetype": {"type": "string", "description": "Filter by type: gold (public), private, shared, market"},
            "os_type": {"type": "string", "description": "Filter by OS type: Linux, Windows, Other"},
            "platform": {"type": "string", "description": "Filter by OS platform: Ubuntu, CentOS, Debian, EulerOS, etc."},
            "status": {"type": "string", "description": "Filter by status: active, queued, saving, deleted, killed"},
            "architecture": {"type": "string", "description": "Filter by architecture: x86 or arm"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("IMS", "ListImages", p, param_mapping={
            "imagetype": "--__imagetype",
            "os_type": "--__os_type",
            "platform": "--__platform",
        }),
    ),
    ToolDefinition(
        name="hcloud_show_image",
        description="Get details of a specific IMS image (min_ram, min_disk, status)",
        params={
            "region": {"type": "string", "description": "Region"},
            "image_id": {"type": "string", "description": "Image ID"},
        },
        required=["region", "image_id"],
        build_command=lambda p: build_hcloud_command("IMS", "GlanceShowImage", p),
    ),
    ToolDefinition(
        name="hcloud_list_os_versions",
        description="List available IMS OS versions (key for image selection)",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("IMS", "ListOsVersions", p),
    ),
    ToolDefinition(
        name="hcloud_show_image_quotas",
        description="Show IMS image resource quotas",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("IMS", "ShowImageQuota", p),
    ),
]
