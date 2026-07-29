from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_users",
        description="List IAM users",
        params={
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "ListUsersV5", p),
    ),
    ToolDefinition(
        name="hcloud_show_user",
        description="Get details of a specific IAM user",
        params={
            "user_id": {"type": "string", "description": "User ID"},
        },
        required=["user_id"],
        build_command=lambda p: build_hcloud_command("IAM", "ShowUserV5", p),
    ),
    ToolDefinition(
        name="hcloud_list_groups",
        description="List IAM user groups",
        params={
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "ListGroupsV5", p),
    ),
    ToolDefinition(
        name="hcloud_list_policies",
        description="List IAM policies (system and custom)",
        params={
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "ListPoliciesV5", p),
    ),
    ToolDefinition(
        name="hcloud_list_user_policies",
        description="List policies attached to an IAM user",
        params={
            "user_id": {"type": "string", "description": "User ID"},
        },
        required=["user_id"],
        build_command=lambda p: build_hcloud_command("IAM", "ListAttachedUserPoliciesV5", p),
    ),
    ToolDefinition(
        name="hcloud_list_agencies",
        description="List IAM agencies (trust relationships)",
        params={},
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "ListAgenciesV5", p),
    ),
    ToolDefinition(
        name="hcloud_list_projects",
        description="List IAM projects",
        params={},
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "KeystoneListProjects", p),
    ),
    ToolDefinition(
        name="hcloud_list_domains",
        description="List authenticated IAM domains",
        params={},
        required=[],
        build_command=lambda p: build_hcloud_command("IAM", "KeystoneListAuthDomains", p),
    ),
]
