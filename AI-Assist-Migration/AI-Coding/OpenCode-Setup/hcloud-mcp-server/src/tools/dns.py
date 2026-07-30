from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_dns_zones",
        description="List DNS zones",
        params={
            "region": {"type": "string", "description": "Region"},
            "type": {"type": "string", "description": "Zone type: public or private", "enum": ["public", "private"]},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("DNS", "ListPublicZones" if p.get("type") != "private" else "ListPrivateZones", {k: v for k, v in p.items() if k != "type"}),
    ),
    ToolDefinition(
        name="hcloud_show_dns_zone",
        description="Get details of a specific DNS zone",
        params={
            "region": {"type": "string", "description": "Region"},
            "zone_id": {"type": "string", "description": "Zone ID"},
            "zone_type": {"type": "string", "description": "Zone type: public or private", "enum": ["public", "private"], "default": "public"},
        },
        required=["region", "zone_id"],
        build_command=lambda p: build_hcloud_command("DNS", "ShowPublicZone" if p.get("zone_type") != "private" else "ShowPrivateZone", {k: v for k, v in p.items() if k != "zone_type"}),
    ),
    ToolDefinition(
        name="hcloud_list_dns_recordsets",
        description="List DNS record sets in a zone",
        params={
            "region": {"type": "string", "description": "Region"},
            "zone_id": {"type": "string", "description": "Zone ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region", "zone_id"],
        build_command=lambda p: build_hcloud_command("DNS", "ListRecordSetsByZone", p),
    ),
]
