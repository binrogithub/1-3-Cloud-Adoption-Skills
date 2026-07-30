from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mcp.types import Tool


@dataclass
class ToolDefinition:
    name: str
    description: str
    params: dict[str, dict[str, Any]]
    build_command: Callable[[dict[str, Any]], str]
    required: list[str] = field(default_factory=list)
    is_obs: bool = False

    def to_mcp_tool(self) -> Tool:
        properties: dict[str, Any] = {}
        for pname, pdef in self.params.items():
            prop: dict[str, Any] = {"type": pdef.get("type", "string")}
            if "description" in pdef:
                prop["description"] = pdef["description"]
            if "enum" in pdef:
                prop["enum"] = pdef["enum"]
            if "items" in pdef:
                prop["items"] = pdef["items"]
            if "default" in pdef:
                prop["default"] = pdef["default"]
            properties[pname] = prop

        return Tool(
            name=self.name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": self.required,
            },
        )

    def build(self, arguments: dict[str, Any]) -> str:
        return self.build_command(arguments)


def build_hcloud_command(
    service: str,
    operation: str,
    args: dict[str, Any],
    param_mapping: dict[str, str] | None = None,
) -> str:
    parts = [service, operation]

    mapping = param_mapping or {}

    for key, value in args.items():
        if value is None:
            continue

        if key == "region":
            parts.append(f"--cli-region={value}")
            continue

        cli_key = mapping.get(key, f"--{key}")

        if isinstance(value, bool):
            parts.append(f"{cli_key}={'true' if value else 'false'}")
        elif isinstance(value, list):
            parts.append(f"{cli_key}={','.join(str(v) for v in value)}")
        else:
            parts.append(f"{cli_key}={value}")

    return " ".join(parts)


def build_obs_command(
    subcommand: str,
    args: list[str],
    region: str | None = None,
) -> str:
    parts = ["obs", subcommand]
    parts.extend(args)

    if region:
        parts.append(f"--cli-region={region}")

    return " ".join(parts)


def collect_all_tools() -> list[ToolDefinition]:
    from .ecs import TOOLS as ecs_tools
    from .vpc import TOOLS as vpc_tools
    from .eip import TOOLS as eip_tools
    from .evs import TOOLS as evs_tools
    from .iam import TOOLS as iam_tools
    from .elb import TOOLS as elb_tools
    from .rds import TOOLS as rds_tools
    from .cce import TOOLS as cce_tools
    from .as_ import TOOLS as as_tools
    from .obs import TOOLS as obs_tools
    from .dns import TOOLS as dns_tools
    from .kms import TOOLS as kms_tools
    from .ces import TOOLS as ces_tools
    from .ims import TOOLS as ims_tools
    from .nat import TOOLS as nat_tools
    from .dcs import TOOLS as dcs_tools
    from .dds import TOOLS as dds_tools
    from .smn import TOOLS as smn_tools

    all_tools: list[ToolDefinition] = []
    all_tools.extend(ecs_tools)
    all_tools.extend(vpc_tools)
    all_tools.extend(eip_tools)
    all_tools.extend(evs_tools)
    all_tools.extend(iam_tools)
    all_tools.extend(elb_tools)
    all_tools.extend(rds_tools)
    all_tools.extend(cce_tools)
    all_tools.extend(as_tools)
    all_tools.extend(obs_tools)
    all_tools.extend(dns_tools)
    all_tools.extend(kms_tools)
    all_tools.extend(ces_tools)
    all_tools.extend(ims_tools)
    all_tools.extend(nat_tools)
    all_tools.extend(dcs_tools)
    all_tools.extend(dds_tools)
    all_tools.extend(smn_tools)
    return all_tools
