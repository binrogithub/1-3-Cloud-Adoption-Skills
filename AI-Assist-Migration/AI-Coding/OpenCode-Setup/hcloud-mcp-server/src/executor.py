import logging
import shlex
import subprocess
from typing import Any

from .config import ExecutionConfig

logger = logging.getLogger(__name__)


def _is_obs_command(args: list[str]) -> bool:
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg.lower() == "obs"
    return False


def _translate_obs_region(args: list[str], config: ExecutionConfig) -> list[str]:
    result = []
    region = None
    for arg in args:
        if arg.startswith("--cli-region="):
            region = arg.split("=", 1)[1]
        else:
            result.append(arg)

    if region:
        endpoint = config.obs_endpoint_template.format(region=region)
        result.append(f"-e={endpoint}")

    return result


def _build_full_command(command: str, config: ExecutionConfig) -> list[str]:
    cmd = [config.hcloud_binary]

    try:
        args = shlex.split(command)
    except ValueError:
        args = command.split()

    if _is_obs_command(args):
        args = _translate_obs_region(args, config)
        cmd.extend(args)
        return cmd

    cmd.extend(args)

    has_output_flag = any(
        arg.startswith("--cli-output") for arg in args
    )
    if not has_output_flag:
        cmd.append(f"--cli-output={config.cli_output}")

    return cmd


def execute_command(
    command: str,
    config: ExecutionConfig,
) -> tuple[str, str, int]:
    cmd = _build_full_command(command, config)
    logger.debug(f"Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {config.timeout_seconds}s", -1
    except FileNotFoundError:
        return "", f"hcloud binary not found: {config.hcloud_binary}", -1
