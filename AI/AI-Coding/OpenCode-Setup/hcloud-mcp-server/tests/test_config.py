import json
import os
import pytest
from unittest.mock import patch

from src.config import load_config, ServerConfig, ExecutionConfig


def test_default_config():
    cfg = load_config()
    assert cfg.execution.timeout_seconds == 120
    assert cfg.execution.cli_output == "json"
    assert cfg.execution.hcloud_binary == "hcloud"


def test_config_from_file(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "execution": {"timeout_seconds": 60, "hcloud_binary": "/usr/local/bin/hcloud"},
    }))

    cfg = load_config(str(config_file))
    assert cfg.execution.timeout_seconds == 60
    assert cfg.execution.hcloud_binary == "/usr/local/bin/hcloud"
