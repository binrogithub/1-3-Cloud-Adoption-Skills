from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mcp.types import Tool, ToolAnnotations


@dataclass
class ToolDefinition:
    name: str
    description: str
    params: dict[str, dict[str, Any]]
    build_command: Callable[[dict[str, Any]], str]
    required: list[str] = field(default_factory=list)
    is_obs: bool = False
    title: str | None = None
    is_destructive: bool = False

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

        annotations = ToolAnnotations(
            title=self.title or self.name,
            read_only_hint=True if not self.is_destructive else None,
            destructive_hint=True if self.is_destructive else None,
            idempotent_hint=True if not self.is_destructive else None,
            open_world_hint=True,
        )

        return Tool(
            name=self.name,
            title=self.title or self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": properties,
                "required": self.required,
            },
            annotations=annotations,
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
    from .vpn import TOOLS as vpn_tools
    from .drs import TOOLS as drs_tools
    from .swr import TOOLS as swr_tools
    from .oms import TOOLS as oms_tools
    from .sms import TOOLS as sms_tools
    from .cbr import TOOLS as cbr_tools
    from .cci import TOOLS as cci_tools
    from .mrs import TOOLS as mrs_tools
    from .dws import TOOLS as dws_tools
    from .gaussdb import TOOLS as gaussdb_tools
    from .er import TOOLS as er_tools
    from .cfw import TOOLS as cfw_tools
    from .codearts import TOOLS as codearts_tools
    from .dataarts import TOOLS as dataarts_tools
    from .organizations import TOOLS as organizations_tools
    from .lts import TOOLS as lts_tools
    from .bss import TOOLS as bss_tools

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
    all_tools.extend(vpn_tools)
    all_tools.extend(drs_tools)
    all_tools.extend(swr_tools)
    all_tools.extend(oms_tools)
    all_tools.extend(sms_tools)
    all_tools.extend(cbr_tools)
    all_tools.extend(cci_tools)
    all_tools.extend(mrs_tools)
    all_tools.extend(dws_tools)
    all_tools.extend(gaussdb_tools)
    all_tools.extend(er_tools)
    all_tools.extend(cfw_tools)
    all_tools.extend(codearts_tools)
    all_tools.extend(dataarts_tools)
    all_tools.extend(organizations_tools)
    all_tools.extend(lts_tools)
    all_tools.extend(bss_tools)
    return all_tools
