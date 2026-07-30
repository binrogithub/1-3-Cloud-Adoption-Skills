from .registry import ToolDefinition, build_obs_command

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hcloud_obs_ls",
        description="List OBS buckets or objects in a bucket",
        params={
            "region": {"type": "string", "description": "Region"},
            "bucket": {"type": "string", "description": "Bucket name (omit to list all buckets)"},
            "prefix": {"type": "string", "description": "Object key prefix filter"},
            "limit": {"type": "integer", "description": "Max results"},
            "brief": {"type": "boolean", "description": "Show brief output", "default": False},
        },
        required=["region"],
        is_obs=True,
        build_command=lambda p: build_obs_command(
            "ls",
            _build_obs_ls_args(p),
            p.get("region"),
        ),
    ),
    ToolDefinition(
        name="hcloud_obs_stat",
        description="Show properties of an OBS bucket or object",
        params={
            "region": {"type": "string", "description": "Region"},
            "bucket": {"type": "string", "description": "Bucket name"},
            "key": {"type": "string", "description": "Object key (omit for bucket properties)"},
        },
        required=["region", "bucket"],
        is_obs=True,
        build_command=lambda p: build_obs_command(
            "stat",
            _build_obs_stat_args(p),
            p.get("region"),
        ),
    ),
    ToolDefinition(
        name="hcloud_obs_cat",
        description="View content of a text object in OBS",
        params={
            "region": {"type": "string", "description": "Region"},
            "bucket": {"type": "string", "description": "Bucket name"},
            "key": {"type": "string", "description": "Object key"},
        },
        required=["region", "bucket", "key"],
        is_obs=True,
        build_command=lambda p: build_obs_command(
            "cat",
            [f"obs://{p['bucket']}/{p['key']}"],
            p.get("region"),
        ),
    ),
]


def _build_obs_ls_args(p: dict) -> list[str]:
    args = []
    bucket = p.get("bucket")
    prefix = p.get("prefix")
    limit = p.get("limit")
    brief = p.get("brief", False)

    if bucket:
        target = f"obs://{bucket}"
        if prefix:
            target = f"{target}/{prefix}"
        args.append(target)
    if limit:
        args.append(f"-limit={limit}")
    if brief:
        args.append("-s")
    return args


def _build_obs_stat_args(p: dict) -> list[str]:
    args = []
    bucket = p.get("bucket", "")
    key = p.get("key")
    target = f"obs://{bucket}"
    if key:
        target = f"{target}/{key}"
    args.append(target)
    return args
