#!/usr/bin/env python3
"""Exa MCP headersHelper — emit the x-api-key auth header for Claude Code.

Invoked by Claude Code when connecting to the exa-search HTTP MCP. Validates the
calling context and the key file, then prints exactly one JSON object to stdout:

    {"x-api-key": "<value>"}

Fail-closed contract (PRD §7, G-EXA1, G-EXA5):
  * CLAUDE_CODE_MCP_SERVER_NAME must equal "exa-search".
  * CLAUDE_CODE_MCP_SERVER_URL must be HTTPS, host mcp.exa.ai, path /mcp, and
    its tool query must be exactly web_search_exa,web_fetch_exa.
  * The key file must be a regular file, non-symlink, owned by the current
    user, mode exactly 0600, and contain a single non-empty line.
  * On any failure: exit non-zero, print a stable error code to stderr, and
    NEVER print the key value to stdout or stderr.
  * No network access, no file writes, no caching. Completes in <10s.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlsplit

# Fixed contract — no path parameters accepted (PRD §7).
EXPECTED_SERVER = "exa-search"
EXPECTED_HOST = "mcp.exa.ai"
EXPECTED_PATH = "/mcp"
EXPECTED_SCHEME = "https"
EXPECTED_TOOLS = "web_search_exa,web_fetch_exa"
ALLOWED_TOOLS = frozenset(EXPECTED_TOOLS.split(","))

# Stable error codes (never include the key, URL query, or env snapshot).
E_SERVER = "ERR_EXA_SERVER_NAME"
E_URL = "ERR_EXA_URL"
E_TOOLS = "ERR_EXA_TOOLS"
E_KEY_MISSING = "ERR_EXA_KEY_MISSING"
E_KEY_TYPE = "ERR_EXA_KEY_TYPE"
E_KEY_SYMLINK = "ERR_EXA_KEY_SYMLINK"
E_KEY_OWNER = "ERR_EXA_KEY_OWNER"
E_KEY_MODE = "ERR_EXA_KEY_MODE"
E_KEY_EMPTY = "ERR_EXA_KEY_EMPTY"
E_KEY_MULTILINE = "ERR_EXA_KEY_MULTILINE"


def _fail(code: str) -> NoReturn:
    sys.stderr.write(code + "\n")
    sys.exit(1)


def _key_path() -> Path:
    return Path.home() / ".config" / "claude-maas" / "exa-api-key"


def _validate_server() -> None:
    name = os.environ.get("CLAUDE_CODE_MCP_SERVER_NAME", "")
    if name != EXPECTED_SERVER:
        _fail(E_SERVER)


def _validate_url() -> None:
    url = os.environ.get("CLAUDE_CODE_MCP_SERVER_URL", "")
    if not url:
        _fail(E_URL)
    try:
        parts = urlsplit(url)
    except ValueError:
        _fail(E_URL)
    if (parts.scheme or "").lower() != EXPECTED_SCHEME:
        _fail(E_URL)
    if (parts.hostname or "").lower() != EXPECTED_HOST:
        _fail(E_URL)
    if parts.path != EXPECTED_PATH:
        _fail(E_URL)
    # Validate the tool query exactly matches the allowlist.
    query = parts.query or ""
    # Parse tools=... from the query string manually (avoid importing parse_qs
    # edge cases with commas).
    tools_value = ""
    for pair in query.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k == "tools":
                tools_value = v
    if not tools_value:
        _fail(E_TOOLS)
    requested = frozenset(t for t in tools_value.split(",") if t)
    if requested != ALLOWED_TOOLS:
        _fail(E_TOOLS)


def _validate_key_file() -> str:
    path = _key_path()
    # Use lstat to detect symlinks without following.
    try:
        st = os.lstat(path)
    except OSError:
        _fail(E_KEY_MISSING)
    # Must be a regular file, not a symlink.
    if stat.S_ISLNK(st.st_mode):
        _fail(E_KEY_SYMLINK)
    if not stat.S_ISREG(st.st_mode):
        _fail(E_KEY_TYPE)
    # Must be owned by the current user.
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        _fail(E_KEY_OWNER)
    # Mode must be exactly 0600.
    if (st.st_mode & 0o777) != 0o600:
        _fail(E_KEY_MODE)
    # Read content — single non-empty line.
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        _fail(E_KEY_MISSING)
    lines = content.splitlines()
    if not lines or not lines[0].strip():
        _fail(E_KEY_EMPTY)
    if len(lines) > 1:
        _fail(E_KEY_MULTILINE)
    value = lines[0]
    if not value.strip():
        _fail(E_KEY_EMPTY)
    return value


def main() -> None:
    _validate_server()
    _validate_url()
    key = _validate_key_file()
    # Emit exactly one JSON object. The key goes only to this controlled stdout
    # consumed by Claude Code — never to stderr, logs, or files.
    sys.stdout.write(json.dumps({"x-api-key": key}))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
