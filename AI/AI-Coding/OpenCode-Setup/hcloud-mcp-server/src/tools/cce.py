from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_cce_clusters",
        description="List CCE (Kubernetes) clusters",
        params={
            "region": {"type": "string", "description": "Region"},
            "status": {"type": "string", "description": "Cluster status filter (Available, Unavailable, Creating, Deleting, etc.)"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("CCE", "ListClusters", p),
    ),
    ToolDefinition(
        name="hcloud_show_cce_cluster",
        description="Get details of a specific CCE cluster",
        params={
            "region": {"type": "string", "description": "Region"},
            "cluster_id": {"type": "string", "description": "Cluster ID"},
        },
        required=["region", "cluster_id"],
        build_command=lambda p: build_hcloud_command("CCE", "ShowCluster", p),
    ),
    ToolDefinition(
        name="hcloud_list_cce_nodes",
        description="List nodes in a CCE cluster",
        params={
            "region": {"type": "string", "description": "Region"},
            "cluster_id": {"type": "string", "description": "Cluster ID"},
        },
        required=["region", "cluster_id"],
        build_command=lambda p: build_hcloud_command("CCE", "ListNodes", p),
    ),
    ToolDefinition(
        name="hcloud_list_node_pools",
        description="List node pools in a CCE cluster",
        params={
            "region": {"type": "string", "description": "Region"},
            "cluster_id": {"type": "string", "description": "Cluster ID"},
        },
        required=["region", "cluster_id"],
        build_command=lambda p: build_hcloud_command("CCE", "ListNodePools", p),
    ),
    ToolDefinition(
        name="hcloud_show_node_pool",
        description="Get details of a specific CCE node pool",
        params={
            "region": {"type": "string", "description": "Region"},
            "cluster_id": {"type": "string", "description": "Cluster ID"},
            "nodepool_id": {"type": "string", "description": "Node pool ID"},
        },
        required=["region", "cluster_id", "nodepool_id"],
        build_command=lambda p: build_hcloud_command("CCE", "ShowNodePool", p),
    ),
    ToolDefinition(
        name="hcloud_list_addon_instances",
        description="List installed add-ons in a CCE cluster",
        params={
            "region": {"type": "string", "description": "Region"},
            "cluster_id": {"type": "string", "description": "Cluster ID"},
        },
        required=["region", "cluster_id"],
        build_command=lambda p: build_hcloud_command("CCE", "ListAddonInstances", p),
    ),
]
