"""Shared pytest configuration.

Isolates tests from the production env file (/etc/claude-code-proxy/maas.env).

The adapter's loadEnvFile() reads ENV_FILE (defaulting to that path) and injects
production values — e.g. MAAS_TOOL_ARG_MODE=enforce — into test subprocesses that
inherit os.environ.  This silently flips tests that expect the "observe" default
into enforce mode, causing spurious failures (PRD RELEASE_V10 A2).

Setting ENV_FILE to an empty file here makes loadEnvFile() a no-op for every
adapter subprocess, so tests control MAAS_TOOL_ARG_MODE exclusively via extra_env.
Tests that need a specific env file can still set ENV_FILE in extra_env to override.
"""
from __future__ import annotations

import os
import tempfile

# Create an empty file — loadEnvFile() will read zero lines and set nothing.
# Using a real empty file (not /dev/null) avoids any fs.existsSync ambiguity.
_empty = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False)
_empty.close()
os.environ.setdefault("ENV_FILE", _empty.name)
