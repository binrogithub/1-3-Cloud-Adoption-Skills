from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_load_balancers",
        description="List ELB load balancers",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListLoadBalancers/v3", p),
    ),
    ToolDefinition(
        name="hcloud_show_load_balancer",
        description="Get details of a specific load balancer",
        params={
            "region": {"type": "string", "description": "Region"},
            "loadbalancer_id": {"type": "string", "description": "Load balancer ID"},
        },
        required=["region", "loadbalancer_id"],
        build_command=lambda p: build_hcloud_command("ELB", "ShowLoadBalancer/v3", p),
    ),
    ToolDefinition(
        name="hcloud_show_load_balancer_topology",
        description="Show load balancer topology tree (listeners, pools, members)",
        params={
            "region": {"type": "string", "description": "Region"},
            "loadbalancer_id": {"type": "string", "description": "Load balancer ID"},
        },
        required=["region", "loadbalancer_id"],
        build_command=lambda p: build_hcloud_command("ELB", "ShowLoadBalancerTopology", p),
    ),
    ToolDefinition(
        name="hcloud_list_listeners",
        description="List ELB listeners",
        params={
            "region": {"type": "string", "description": "Region"},
            "loadbalancer_id": {"type": "string", "description": "Filter by load balancer ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListListeners/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_pools",
        description="List ELB backend server groups (pools)",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListPools/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_members",
        description="List backend members in an ELB pool",
        params={
            "region": {"type": "string", "description": "Region"},
            "pool_id": {"type": "string", "description": "Pool ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region", "pool_id"],
        build_command=lambda p: build_hcloud_command("ELB", "ListMembers/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_health_monitors",
        description="List ELB health monitors",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListHealthMonitors/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_l7_policies",
        description="List ELB URL-based routing policies",
        params={
            "region": {"type": "string", "description": "Region"},
            "listener_id": {"type": "string", "description": "Filter by listener ID"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListL7Policies/v3", p),
    ),
    ToolDefinition(
        name="hcloud_list_elb_flavors",
        description="List available ELB flavor specifications",
        params={
            "region": {"type": "string", "description": "Region"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("ELB", "ListFlavors", p),
    ),
]
