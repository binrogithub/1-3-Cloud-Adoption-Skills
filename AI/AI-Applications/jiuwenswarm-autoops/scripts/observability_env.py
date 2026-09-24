#!/usr/bin/env python3
"""Load only declared observability variables from ignored local env files."""
from __future__ import annotations

import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEPLOYMENT_CONFIG_DIR = Path("/etc/jiuwenswarm-autoops")
ALLOWED = {
    "PROMETHEUS_BASE_URL", "PROMETHEUS_BEARER_TOKEN", "PROMETHEUS_TIMEOUT_SECONDS", "PROMETHEUS_VERIFY_TLS",
    "OPENSEARCH_BASE_URL", "OPENSEARCH_API_KEY", "OPENSEARCH_BEARER_TOKEN", "OPENSEARCH_USERNAME",
    "OPENSEARCH_PASSWORD", "OPENSEARCH_TIMEOUT_SECONDS", "OPENSEARCH_VERIFY_TLS",
    "LOKI_BASE_URL", "LOKI_TENANT_ID", "LOKI_BEARER_TOKEN", "LOKI_SERVICE_LABEL", "LOKI_TIMEOUT_SECONDS",
    "NOLI_BASE_URL", "NOLI_BEARER_TOKEN", "NOLI_TIMEOUT_SECONDS",
    "AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES", "AUTOOPS_LOCAL_JOURNAL_FALLBACK",
}


def load_file(environment: dict[str, str], path: Path) -> None:
    try:
        if not path.is_file() or path.is_symlink():
            return
        content = path.read_text(encoding="utf-8")
    except OSError:
        # Customer configuration is optional. A missing or unreadable local
        # file must not turn a read-only investigation into a process crash.
        return
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED:
            continue
        try:
            values = shlex.split(raw_value, comments=False, posix=True)
        except ValueError:
            continue
        if len(values) == 1:
            environment[key] = values[0]


def load_observability_environment(environment: dict[str, str] | None = None) -> dict[str, str]:
    provided = dict(os.environ if environment is None else environment)
    loaded: dict[str, str] = {}
    configured_dir = provided.get("JIUWENSWARM_AUTOOPS_CONFIG_DIR")
    if configured_dir:
        config_dirs = [Path(configured_dir)]
    else:
        # Installed deployments keep customer configuration outside the
        # checkout. Load the repository-local development fallback first so
        # the installed customer configuration wins when both exist.
        config_dirs = [ROOT / "config" / "local", DEFAULT_DEPLOYMENT_CONFIG_DIR]
    for local in config_dirs:
        for name in ("prometheus.env", "opensearch.env", "loki.env", "noli.env"):
            load_file(loaded, local / name)
    # Process environment is the explicit runtime override. This keeps
    # temporary test endpoints and operator supplied credentials from being
    # silently replaced by a stale local env file.
    loaded.update(provided)
    return loaded
