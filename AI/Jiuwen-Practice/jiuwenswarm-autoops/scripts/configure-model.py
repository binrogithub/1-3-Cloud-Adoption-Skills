#!/usr/bin/env python3
"""Interactively configure the shared JiuwenSwarm MaaS dotenv file."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import pwd
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_BASE = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
MODEL_KEYS = ("API_BASE", "API_KEY", "MODEL_NAME", "MODEL_PROVIDER")


def default_env_file() -> Path:
    username = os.environ.get("SUDO_USER") or getpass.getuser()
    try:
        home = Path(pwd.getpwnam(username).pw_dir)
    except KeyError:
        home = Path.home()
    return home / ".jiuwenswarm" / "config" / ".env"


def existing_values(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file() or path.is_symlink():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*(?:export\s+)?(API_BASE|API_KEY|MODEL_NAME|MODEL_PROVIDER)\s*=\s*(.*)$", line)
        if not match:
            continue
        key, raw = match.groups()
        raw = raw.strip()
        try:
            value = json.loads(raw) if raw.startswith('"') else raw.strip("'\"")
        except json.JSONDecodeError:
            continue
        if isinstance(value, str):
            values[key] = value
    return values


def merged_content(old: str, values: dict[str, str]) -> str:
    lines = []
    seen = set()
    for line in old.splitlines():
        match = re.match(r"\s*(?:export\s+)?(API_BASE|API_KEY|MODEL_NAME|MODEL_PROVIDER)\s*=", line)
        if match:
            key = match.group(1)
            if key in seen:
                continue
            lines.append(f"{key}={json.dumps(values[key])}")
            seen.add(key)
        else:
            lines.append(line)
    for key in MODEL_KEYS:
        if key not in seen:
            lines.append(f"{key}={json.dumps(values[key])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=default_env_file(),
                        help="JiuwenSwarm's shared config/.env (preserves other upstream settings)")
    parser.add_argument("--force", action="store_true", help="skip confirmation before updating model fields")
    args = parser.parse_args()
    destination = args.env_file.expanduser()
    if destination.is_symlink():
        parser.error(f"refusing to overwrite symlink model configuration: {destination}")
    missing_directories = []
    cursor = destination.parent
    while not cursor.exists():
        missing_directories.append(cursor)
        cursor = cursor.parent
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    sudo_user = os.environ.get("SUDO_USER")
    target_account = pwd.getpwnam(sudo_user) if sudo_user and os.geteuid() == 0 else None
    if target_account:
        for created in missing_directories:
            os.chown(created, target_account.pw_uid, target_account.pw_gid)
    current = existing_values(destination)
    if destination.exists() and not args.force:
        answer = input(f"Update model settings in {destination}? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Existing model configuration preserved.")
            return 0

    base_default = current.get("API_BASE") or DEFAULT_BASE
    model_default = current.get("MODEL_NAME") or DEFAULT_MODEL
    base = input(f"MaaS API base URL [{base_default}]: ").strip() or base_default
    model = input(f"Model name [{model_default}]: ").strip() or model_default
    api_key = getpass.getpass("MaaS API key (hidden; Enter keeps the current key): ").strip()
    api_key = api_key or current.get("API_KEY", "")
    if not api_key:
        parser.error("MaaS API key cannot be empty")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        parser.error("API_BASE must be an HTTPS URL without embedded credentials")
    if not re.fullmatch(r"[A-Za-z0-9._:/+-]+", model):
        parser.error("MODEL_NAME contains unsupported characters")
    if any(char in api_key for char in "\r\n\x00"):
        parser.error("API_KEY cannot contain a newline or NUL byte")

    values = {"API_BASE": base.rstrip("/"), "API_KEY": api_key,
              "MODEL_NAME": model, "MODEL_PROVIDER": "OpenAI"}
    old_content = destination.read_text(encoding="utf-8") if destination.exists() else ""
    content = merged_content(old_content, values)
    fd, temporary_name = tempfile.mkstemp(prefix=".jiuwenswarm-env.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
        if target_account:
            os.chown(destination, target_account.pw_uid, target_account.pw_gid)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"JiuwenSwarm model configuration saved: {destination} (mode 0600; unrelated settings preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
