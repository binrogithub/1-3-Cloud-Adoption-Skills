#!/usr/bin/env python3
"""Configuration loader module for DRS migration automation.

Automatically loads .env file from BASE_DIR if present.
.env file takes lower priority than existing environment variables.
"""

import os
import sys
from pathlib import Path

import yaml

DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(os.getenv("MIGRATION_BASE_DIR", str(DEFAULT_BASE_DIR)))
CONFIG_PATH = BASE_DIR / "configs" / "migration.yaml"
ENV_FILE_PATH = BASE_DIR / ".env"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
APPROVALS_DIR = BASE_DIR / "approvals"


def load_dotenv():
    """Load environment variables from .env file.

    Values in .env do NOT override existing environment variables.
    Lines starting with # are ignored. Empty lines are ignored.
    """
    if not ENV_FILE_PATH.exists():
        return
    with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove optional quotes
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            # Do NOT override existing environment variables
            if key and key not in os.environ:
                os.environ[key] = value


# Auto-load .env on module import
load_dotenv()

REQUIRED_ENV_VARS = [
    "HW_ACCESS_KEY",
    "HW_SECRET_KEY",
    "HW_PROJECT_ID",
    "HW_REGION",
    "SRC_DB_HOST",
    "SRC_DB_PORT",
    "SRC_DB_USER",
    "SRC_DB_PASSWORD",
    "TGT_DB_HOST",
    "TGT_DB_PORT",
    "TGT_DB_USER",
    "TGT_DB_PASSWORD",
]

OPTIONAL_ENV_VARS = ["DRY_RUN"]


def load_config():
    """Load migration configuration from YAML file."""
    if not CONFIG_PATH.exists():
        print(f"FATAL: Configuration file not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def get_env_var(var_name, required=True):
    """Read an environment variable.

    Args:
        var_name: Name of the environment variable.
        required: If True, raise an error when the variable is missing or empty.

    Returns:
        The value of the environment variable, or None if not required and missing.
    """
    value = os.getenv(var_name, "").strip()
    if required and not value:
        return None
    return value if value else None


def validate_env_vars():
    """Validate all required environment variables are set.

    Returns:
        tuple: (is_valid, missing_vars) where missing_vars is a list of missing variable names.
    """
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var, "").strip():
            missing.append(var)
    return len(missing) == 0, missing


def is_dry_run():
    """Check if running in dry-run mode.

    Returns:
        bool: True if DRY_RUN is set to 'true' (default), False otherwise.
    """
    return os.getenv("DRY_RUN", "true").strip().lower() != "false"


def get_source_db_config():
    """Get source database connection config from environment variables."""
    return {
        "host": get_env_var("SRC_DB_HOST"),
        "port": int(get_env_var("SRC_DB_PORT") or 3306),
        "user": get_env_var("SRC_DB_USER"),
        "password": get_env_var("SRC_DB_PASSWORD"),
    }


def get_target_db_config():
    """Get target database connection config from environment variables."""
    return {
        "host": get_env_var("TGT_DB_HOST"),
        "port": int(get_env_var("TGT_DB_PORT") or 3306),
        "user": get_env_var("TGT_DB_USER"),
        "password": get_env_var("TGT_DB_PASSWORD"),
    }


def get_huawei_cloud_config():
    """Get Huawei Cloud API config from environment variables."""
    return {
        "access_key": get_env_var("HW_ACCESS_KEY"),
        "secret_key": get_env_var("HW_SECRET_KEY"),
        "project_id": get_env_var("HW_PROJECT_ID"),
        "region": get_env_var("HW_REGION"),
    }


def ensure_dirs():
    """Ensure all required directories exist."""
    for d in [REPORTS_DIR, LOGS_DIR, APPROVALS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
