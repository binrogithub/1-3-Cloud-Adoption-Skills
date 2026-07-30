from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_scaling_groups",
        description="List AS (Auto Scaling) groups",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("AS", "ListScalingGroups", p),
    ),
    ToolDefinition(
        name="hcloud_show_scaling_group",
        description="Get details of a specific AS group",
        params={
            "region": {"type": "string", "description": "Region"},
            "scaling_group_id": {"type": "string", "description": "Scaling group ID"},
        },
        required=["region", "scaling_group_id"],
        build_command=lambda p: build_hcloud_command("AS", "ShowScalingGroup", p),
    ),
    ToolDefinition(
        name="hcloud_list_scaling_configs",
        description="List AS (Auto Scaling) configurations",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("AS", "ListScalingConfigs", p),
    ),
    ToolDefinition(
        name="hcloud_show_scaling_config",
        description="Get details of a specific AS configuration",
        params={
            "region": {"type": "string", "description": "Region"},
            "scaling_configuration_id": {"type": "string", "description": "Scaling configuration ID"},
        },
        required=["region", "scaling_configuration_id"],
        build_command=lambda p: build_hcloud_command("AS", "ShowScalingConfig", p),
    ),
    ToolDefinition(
        name="hcloud_list_scaling_policies",
        description="List AS (Auto Scaling) policies",
        params={
            "region": {"type": "string", "description": "Region"},
            "scaling_group_id": {"type": "string", "description": "Scaling group ID (required)"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region", "scaling_group_id"],
        build_command=lambda p: build_hcloud_command("AS", "ListScalingPolicies", p),
    ),
    ToolDefinition(
        name="hcloud_show_scaling_policy",
        description="Get details of a specific AS policy",
        params={
            "region": {"type": "string", "description": "Region"},
            "scaling_policy_id": {"type": "string", "description": "Scaling policy ID"},
        },
        required=["region", "scaling_policy_id"],
        build_command=lambda p: build_hcloud_command("AS", "ShowScalingPolicy", p),
    ),
    ToolDefinition(
        name="hcloud_list_scaling_instances",
        description="List instances currently in AS groups",
        params={
            "region": {"type": "string", "description": "Region"},
            "scaling_group_id": {"type": "string", "description": "Scaling group ID (required)"},
        },
        required=["region", "scaling_group_id"],
        build_command=lambda p: build_hcloud_command("AS", "ListScalingInstances", p),
    ),
]
