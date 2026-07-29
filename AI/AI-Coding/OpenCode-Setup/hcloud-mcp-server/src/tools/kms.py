from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_kms_keys",
        description="List KMS encryption keys",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("KMS", "ListKeys", p),
    ),
    ToolDefinition(
        name="hcloud_list_kms_key_detail",
        description="Get details of a specific KMS key (state, creation date, etc.)",
        params={
            "region": {"type": "string", "description": "Region"},
            "key_id": {"type": "string", "description": "KMS key ID"},
        },
        required=["region", "key_id"],
        build_command=lambda p: build_hcloud_command("KMS", "ListKeyDetail", p),
    ),
]
