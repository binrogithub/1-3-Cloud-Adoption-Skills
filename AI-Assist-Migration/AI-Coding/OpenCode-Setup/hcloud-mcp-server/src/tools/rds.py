from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_rds_instances",
        description="List RDS database instances",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("RDS", "ListInstances", p),
    ),
    ToolDefinition(
        name="hcloud_list_rds_flavors",
        description="List RDS instance flavor/spec options",
        params={
            "region": {"type": "string", "description": "Region"},
            "database_name": {"type": "string", "description": "DB engine: MySQL, PostgreSQL, SQLServer, MariaDB"},
            "version_name": {"type": "string", "description": "Database version filter"},
        },
        required=["region", "database_name"],
        build_command=lambda p: build_hcloud_command("RDS", "ListFlavors", p),
    ),
    ToolDefinition(
        name="hcloud_list_rds_storage_types",
        description="List supported RDS storage types per engine/version",
        params={
            "region": {"type": "string", "description": "Region"},
            "database_name": {"type": "string", "description": "DB engine: MySQL, PostgreSQL, SQLServer, MariaDB"},
            "version_name": {"type": "string", "description": "Database version (e.g. 5.7, 8.0)"},
        },
        required=["region", "database_name", "version_name"],
        build_command=lambda p: build_hcloud_command("RDS", "ListStorageTypes", p),
    ),
    ToolDefinition(
        name="hcloud_list_rds_datastores",
        description="List available RDS DB engine versions",
        params={
            "region": {"type": "string", "description": "Region"},
            "database_name": {"type": "string", "description": "DB engine: MySQL, PostgreSQL, SQLServer, MariaDB"},
        },
        required=["region", "database_name"],
        build_command=lambda p: build_hcloud_command("RDS", "ListDatastores", p),
    ),
    ToolDefinition(
        name="hcloud_list_rds_backups",
        description="List RDS backups",
        params={
            "region": {"type": "string", "description": "Region"},
            "instance_id": {"type": "string", "description": "RDS instance ID (required)"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region", "instance_id"],
        build_command=lambda p: build_hcloud_command("RDS", "ListBackups", p),
    ),
]
