from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_smn_topics",
        description="List SMN (Simple Message Notification) topics",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
            "offset": {"type": "integer", "description": "Pagination offset"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("SMN", "ListTopics", p),
    ),
    ToolDefinition(
        name="hcloud_list_smn_subscriptions",
        description="List SMN subscriptions",
        params={
            "region": {"type": "string", "description": "Region"},
            "topic_urn": {"type": "string", "description": "Filter by topic URN"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("SMN", "ListSubscriptions", p),
    ),
]
