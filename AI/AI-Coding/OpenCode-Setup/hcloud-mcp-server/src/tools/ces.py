from .registry import ToolDefinition, build_hcloud_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_list_alarms",
        description="List CES (Cloud Eye) alarms",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("CES", "ListAlarms", p),
    ),
    ToolDefinition(
        name="hcloud_list_alarm_rules",
        description="List CES alarm rules (v2 API, more complete)",
        params={
            "region": {"type": "string", "description": "Region"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("CES", "ListAlarmRules", p),
    ),
    ToolDefinition(
        name="hcloud_list_metrics",
        description="List CES (Cloud Eye) metrics",
        params={
            "region": {"type": "string", "description": "Region"},
            "namespace": {"type": "string", "description": "Metric namespace (e.g. SYS.ECS)"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        required=["region"],
        build_command=lambda p: build_hcloud_command("CES", "ListMetrics", p),
    ),
    ToolDefinition(
        name="hcloud_show_metric_data",
        description="Show CES (Cloud Eye) metric data points",
        params={
            "region": {"type": "string", "description": "Region"},
            "namespace": {"type": "string", "description": "Metric namespace (e.g. SYS.ECS)"},
            "metric_name": {"type": "string", "description": "Metric name (e.g. cpu_util)"},
            "dim_0": {"type": "string", "description": "Dimension 0 (e.g. instance_id,xxxx)"},
            "filter": {"type": "string", "description": "Aggregation method: average, variance, min, max, sum"},
            "period": {"type": "integer", "description": "Aggregation period in seconds (1, 60, 300, 1200, 3600, 14400, 86400)"},
            "from_": {"type": "integer", "description": "Start time (UNIX timestamp in ms)"},
            "to": {"type": "integer", "description": "End time (UNIX timestamp in ms)"},
        },
        required=["region", "namespace", "metric_name", "dim_0", "filter", "period", "from_", "to"],
        build_command=lambda p: build_hcloud_command("CES", "ShowMetricData", p, param_mapping={
            "dim_0": "--dim.0",
            "from_": "--from",
        }),
    ),
]
