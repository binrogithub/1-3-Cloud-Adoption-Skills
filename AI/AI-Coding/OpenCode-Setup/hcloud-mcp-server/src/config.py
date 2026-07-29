import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionConfig:
    timeout_seconds: int = 120
    cli_output: str = "json"
    hcloud_binary: str = "hcloud"
    obs_endpoint_template: str = "https://obs.{region}.myhuaweicloud.com"


@dataclass
class ServerConfig:
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


def load_config(config_path: Optional[str] = None) -> ServerConfig:
    cfg = ServerConfig()

    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            data = json.load(f)
        _merge_config(cfg, data)

    env_path = os.environ.get("HCLOUD_MCP_CONFIG")
    if env_path and os.path.exists(env_path):
        with open(env_path) as f:
            data = json.load(f)
        _merge_config(cfg, data)

    return cfg


def _merge_config(cfg: ServerConfig, data: dict):
    if "execution" in data:
        e = data["execution"]
        for k, v in e.items():
            if hasattr(cfg.execution, k):
                setattr(cfg.execution, k, v)
