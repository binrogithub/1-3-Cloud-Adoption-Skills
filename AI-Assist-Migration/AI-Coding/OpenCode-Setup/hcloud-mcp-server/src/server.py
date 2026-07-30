import argparse
import asyncio
import json
import logging
import re
import shlex
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import ServerConfig, load_config
from .safety import is_destructive_command, is_obs_command, is_obs_destructive_command
from .executor import execute_command
from .tools.registry import ToolDefinition, collect_all_tools

logger = logging.getLogger(__name__)

DESTRUCTIVE_PATTERNS = [
    "Delete", "Remove", "Revoke", "Detach",
    "Disassociate", "Cancel", "Force",
]

CLI_TOOL_DESCRIPTION = """Huawei Cloud CLI (hcloud) terminal interface.

Navigate the CLI using --help to discover operations and parameters:
1. `--help` — list all available services
2. `<Service> --help` — list operations for a service (e.g., `IAM --help`)
3. `<Service> <Operation> --help` — show parameters for an operation (e.g., `IAM ListCustomPolicies --help`)
4. `<Service> <Operation> --param1=value1 --param2=value2` — execute an operation

The parameter format is always `--param=value` (equals sign required).
JSON output is forced automatically (`--cli-output=json`).

For destructive operations (Delete, Remove, Revoke, Detach, etc.), set confirm=true to execute. Without confirmation, the command runs in --dryrun mode first.

OBS (Object Storage Service) uses obsutil with a different format:
1. `obs help` — list all OBS commands
2. `obs help <command>` — show help for a specific command (e.g., `obs help ls`)
3. `obs <command> [args...] [options...]` — execute an OBS command
4. Use `--cli-region=<region>` to specify the region (translated to the OBS endpoint automatically)
5. OBS output is plain text (not JSON)
6. For OBS destructive commands that support dry-run (cp, mv, sync), the command runs with -dryRun unless confirmed
7. For OBS destructive commands without dry-run support (rm, abort, mb, chattri, bucketpolicy, lifecycle), you must set confirm=true to execute"""


def _is_obs_help(command: str) -> bool:
    if not is_obs_command(command):
        return False
    args = command.split()
    found_obs = False
    for arg in args:
        if not found_obs:
            if arg.lower() == "obs":
                found_obs = True
            continue
        if arg.startswith("-"):
            continue
        return arg == "help"
    return False


class HCloudMCPServer:
    def __init__(self, config: ServerConfig):
        self.config = config
        self.structured_tools = collect_all_tools()
        self.tool_map: dict[str, ToolDefinition] = {t.name: t for t in self.structured_tools}

        self.server = Server(
            name="hcloud-mcp-server",
            version="0.3.0",
            instructions=(
                "Huawei Cloud MCP Server. "
                "Use structured read-only tools (hcloud_list_servers, hcloud_list_vpcs, hcloud_list_flavors, "
                "hcloud_list_images, hcloud_obs_ls, etc.) for infrastructure discovery and planning. "
                "Use the hcloud_cli tool for any write operation or operations not covered by structured tools. "
                "For OBS, use hcloud_obs_ls, hcloud_obs_stat, hcloud_obs_cat for read access, "
                "or the generic hcloud_cli for write operations."
            ),
        )
        self._register_handlers()

    def _register_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            tools = [t.to_mcp_tool() for t in self.structured_tools]
            tools.append(Tool(
                name="hcloud_cli",
                description=CLI_TOOL_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "hcloud CLI arguments (everything after 'hcloud'). Examples: '--help', 'IAM --help', 'IAM ListCustomPolicies --help', 'IAM ListCustomPolicies', 'IAM DeleteCustomPolicy --role_id=abc123', 'obs help', 'obs help ls', 'obs ls --cli-region=la-north-2', 'obs rm obs://bucket/key'",
                        },
                        "confirm": {
                            "type": "boolean",
                            "default": False,
                            "description": "Set to true to execute destructive operations. If false (default), destructive commands run in --dryrun mode (or are refused for OBS commands without dry-run support).",
                        },
                    },
                    "required": ["command"],
                },
            ))
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name == "hcloud_cli":
                return await self._handle_cli_tool(arguments)
            if name in self.tool_map:
                return await self._handle_structured_tool(name, arguments)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_structured_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        tool_def = self.tool_map[name]
        command = tool_def.build(arguments)
        is_obs = tool_def.is_obs

        stdout, stderr, returncode = execute_command(
            command, self.config.execution
        )
        output = self._format_output(stdout, stderr, returncode, is_obs=is_obs)
        return [TextContent(type="text", text=output)]

    async def _handle_cli_tool(self, arguments: dict[str, Any]) -> list[TextContent]:
        command = arguments.get("command", "").strip()
        confirm = arguments.get("confirm", False)

        if not command:
            return [TextContent(type="text", text="Error: command is required. Try '--help' to get started.")]

        is_help = "--help" in command or _is_obs_help(command)
        obs_destructive, obs_supports_dryrun = is_obs_destructive_command(command)

        is_destructive = False
        if not is_help:
            if is_obs_command(command):
                is_destructive = obs_destructive
            else:
                for pattern in DESTRUCTIVE_PATTERNS:
                    if re.search(rf"\b{pattern}\b", command):
                        is_destructive = True
                        break

        if is_help or not is_destructive:
            stdout, stderr, returncode = execute_command(
                command, self.config.execution
            )
            output = self._format_output(stdout, stderr, returncode, is_obs=is_obs_command(command))
            if is_help and not is_obs_command(command):
                output = self._filter_help_versions(output)
            return [TextContent(type="text", text=output)]

        if is_obs_command(command):
            return self._execute_obs_command(command, confirm, obs_supports_dryrun)

        if is_destructive and not confirm:
            dryrun_command = command
            if "--dryrun" not in dryrun_command:
                dryrun_command = f"{dryrun_command} --dryrun"

            stdout, stderr, returncode = execute_command(
                dryrun_command, self.config.execution
            )
            output = self._format_output(stdout, stderr, returncode, is_obs=False)
            return [TextContent(type="text", text=(
                f"⚠️ DRY RUN — no changes made.\n"
                f"This is a destructive operation. Set confirm=true to execute for real.\n\n"
                f"{output}"
            ))]

        stdout, stderr, returncode = execute_command(
            command, self.config.execution
        )
        output = self._format_output(stdout, stderr, returncode, is_obs=False)
        return [TextContent(type="text", text=f"✅ Executed (confirmed destructive operation):\n\n{output}")]

    def _execute_obs_command(self, command: str, confirm: bool, supports_dryrun: bool) -> list[TextContent]:
        if not supports_dryrun:
            if not confirm:
                return [TextContent(type="text", text=(
                    f"⚠️ REFUSED — this OBS command does not support dry-run.\n"
                    f"This is a destructive operation. Set confirm=true to execute for real.\n"
                    f"Command: {command}"
                ))]
            stdout, stderr, returncode = execute_command(
                command, self.config.execution
            )
            output = self._format_output(stdout, stderr, returncode, is_obs=True)
            return [TextContent(type="text", text=f"✅ Executed (confirmed destructive OBS operation):\n\n{output}")]

        if not confirm:
            dryrun_command = command
            if "-dryRun" not in dryrun_command:
                dryrun_command = f"{dryrun_command} -dryRun"

            stdout, stderr, returncode = execute_command(
                dryrun_command, self.config.execution
            )
            output = self._format_output(stdout, stderr, returncode, is_obs=True)
            return [TextContent(type="text", text=(
                f"⚠️ DRY RUN — no changes made.\n"
                f"This is a destructive OBS operation. Set confirm=true to execute for real.\n\n"
                f"{output}"
            ))]

        stdout, stderr, returncode = execute_command(
            command, self.config.execution
        )
        output = self._format_output(stdout, stderr, returncode, is_obs=True)
        return [TextContent(type="text", text=f"✅ Executed (confirmed destructive OBS operation):\n\n{output}")]

    def _format_output(self, stdout: str, stderr: str, returncode: int, is_obs: bool = False) -> str:
        parts = []

        if stdout.strip():
            if is_obs:
                parts.append(stdout.strip())
            else:
                try:
                    data = json.loads(stdout.strip())
                    if isinstance(data, dict) and "error_code" in data:
                        parts.append(f"Error: {data.get('error_msg', 'Unknown error')}")
                        parts.append(f"Error code: {data.get('error_code')}")
                    else:
                        parts.append(json.dumps(data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    parts.append(stdout.strip())

        if stderr.strip() and returncode != 0:
            error_text = stderr.strip()
            if is_obs:
                parts.append(f"stderr: {error_text}")
            else:
                try:
                    error_data = json.loads(error_text)
                    if isinstance(error_data, dict) and "error_code" in error_data:
                        parts.append(f"Error: {error_data.get('error_msg', error_text)}")
                except json.JSONDecodeError:
                    if "error" in error_text.lower() or "failed" in error_text.lower():
                        parts.append(f"stderr: {error_text}")

        if not parts:
            if returncode == 0:
                parts.append("Operation completed successfully (no output).")
            else:
                parts.append(f"Command exited with code {returncode}.")
                if stderr.strip():
                    parts.append(stderr.strip())

        return "\n".join(parts)

    def _filter_help_versions(self, output: str) -> str:
        if "Available Operations:" not in output:
            return output

        lines = output.split("\n")
        before_ops = []
        operations = []
        after_ops = []
        in_operations = False
        operations_indent = ""

        for line in lines:
            if not in_operations and "Available Operations:" in line:
                in_operations = True
                before_ops.append(line)
                continue

            if not in_operations:
                before_ops.append(line)
                continue

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("Run `hcloud"):
                after_ops.append(line)
                in_operations = False
                continue

            if not operations_indent and (line.startswith(" ") or line.startswith("\t")):
                operations_indent = line[:len(line) - len(line.lstrip())]

            if stripped and (line.startswith(" ") or line.startswith("\t")):
                operations.append(stripped)
                continue

            after_ops.append(line)
            in_operations = False

        if not operations:
            return output

        filtered, hidden = self._deduplicate_operations(operations)

        result = list(before_ops)
        for op in filtered:
            result.append(f"{operations_indent}{op}")

        if hidden > 0:
            result.append(f"{operations_indent}... ({hidden} older version(s) hidden)")

        result.extend(after_ops)
        return "\n".join(result)

    @staticmethod
    def _deduplicate_operations(operations: list[str]) -> tuple[list[str], int]:
        slash_version_re = re.compile(r"^(.+)/(v(\d+))$")
        name_version_re = re.compile(r"^(.+?)(V(\d+))$")

        base_ops: dict[str, list[tuple[int, str]]] = {}
        op_to_base: dict[str, str] = {}

        for op in operations:
            m = slash_version_re.match(op)
            if m:
                base = m.group(1)
                ver_num = int(m.group(3))
                base_ops.setdefault(base, []).append((ver_num, op))
                op_to_base[op] = base
                continue

            m = name_version_re.match(op)
            if m:
                base = m.group(1)
                ver_num = int(m.group(3))
                if base in operations:
                    base_ops.setdefault(base, []).append((ver_num, op))
                    op_to_base[op] = base
                    continue

            base_ops.setdefault(op, []).append((0, op))
            op_to_base[op] = op

        keep = set()
        hidden = 0

        for base, entries in base_ops.items():
            if len(entries) <= 1:
                keep.add(entries[0][1])
            else:
                best = max(entries, key=lambda e: e[0])
                keep.add(best[1])
                hidden += len(entries) - 1

        result = [op for op in operations if op in keep]
        return result, hidden

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main():
    parser = argparse.ArgumentParser(description="Huawei Cloud MCP Server")
    parser.add_argument("--config", "-c", help="Path to config JSON file", default=None)
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    config = load_config(args.config)
    server = HCloudMCPServer(config)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
