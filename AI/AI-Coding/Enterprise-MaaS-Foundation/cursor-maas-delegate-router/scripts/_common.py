#!/usr/bin/env python3
"""Shared helpers for cursor-maas-delegate-router scripts."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
HYBRID_DIR = HOME / ".cursor-hybrid"
ENV_PATH = HYBRID_DIR / "env.json"
AUDIT_PATH = HYBRID_DIR / "route-audit.jsonl"
BIN_DIR = HYBRID_DIR / "bin"
CURSOR_DIR = HOME / ".cursor"
MEMORY_DIR = CURSOR_DIR / "memory"
MEMORY_PATH = MEMORY_DIR / "maas-delegate-router.md"
USER_RULE_PATH = CURSOR_DIR / "rules" / "maas-delegate-router.mdc"
USER_HOOKS_JSON = CURSOR_DIR / "hooks.json"
USER_HOOKS_DIR = CURSOR_DIR / "hooks"
# Installed copies under ~/.cursor/hooks/ (user-global; paths relative in hooks.json)
USER_HOOK_ROUTE = USER_HOOKS_DIR / "maas-route-hint.py"
USER_HOOK_SESSION = USER_HOOKS_DIR / "maas-session-start.py"
SKILL_ROOT = Path(__file__).resolve().parents[1]
POLICY_ASSET = SKILL_ROOT / "assets" / "orchestrator-policy.md"
MEMORY_ASSET = SKILL_ROOT / "assets" / "orchestrator-memory.md"
HOOK_ASSET_ROUTE = SKILL_ROOT / "assets" / "hooks" / "route_hint.py"
HOOK_ASSET_SESSION = SKILL_ROOT / "assets" / "hooks" / "maas-session-start.py"
# Back-compat alias
HOOK_SCRIPT = HOOK_ASSET_ROUTE

MARKER_BEGIN = "<!-- maas-delegate-router:begin -->"
MARKER_END = "<!-- maas-delegate-router:end -->"
MEMORY_MARKER_BEGIN = "<!-- maas-delegate-router-memory:begin -->"
MEMORY_MARKER_END = "<!-- maas-delegate-router-memory:end -->"

# Default to CN-Hong Kong OpenAI-compatible endpoint (Guiyang keys often 401 here).
DEFAULT_BASE = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
DEFAULT_MODEL = "glm-5.1"
DEFAULT_CODE_ROUTE = "maas_glm"
DEFAULT_ROUTE_PRIORITY = "maas_over_cursor"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_hybrid_dir() -> None:
    HYBRID_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if not AUDIT_PATH.exists():
        AUDIT_PATH.touch()


def load_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if ENV_PATH.exists():
        try:
            loaded = json.loads(ENV_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({str(k): str(v) for k, v in loaded.items() if v is not None})
        except json.JSONDecodeError:
            pass
    # Process env wins
    for key in (
        "DELEGATE_API_BASE",
        "DELEGATE_API_KEY",
        "DELEGATE_MODEL",
        "VERIFY_SSL",
        "CODE_EXECUTION_ROUTE",
        "ROUTE_PRIORITY",
    ):
        if os.environ.get(key):
            data[key] = os.environ[key]
    # Aliases from huawei skill
    if not data.get("DELEGATE_API_KEY"):
        for alt in ("HUAWEI_MAAS_API_KEY", "MAAS_API_KEY"):
            if os.environ.get(alt):
                data["DELEGATE_API_KEY"] = os.environ[alt]
                break
    if not data.get("DELEGATE_API_BASE") and os.environ.get("HUAWEI_MAAS_API_BASE"):
        data["DELEGATE_API_BASE"] = os.environ["HUAWEI_MAAS_API_BASE"]
    if not data.get("DELEGATE_MODEL") and os.environ.get("HUAWEI_MAAS_MODEL"):
        data["DELEGATE_MODEL"] = os.environ["HUAWEI_MAAS_MODEL"]
    data.setdefault("DELEGATE_API_BASE", DEFAULT_BASE)
    data.setdefault("DELEGATE_MODEL", DEFAULT_MODEL)
    data.setdefault("VERIFY_SSL", "1")
    data.setdefault("CODE_EXECUTION_ROUTE", DEFAULT_CODE_ROUTE)
    data.setdefault("ROUTE_PRIORITY", DEFAULT_ROUTE_PRIORITY)
    return data


def save_env(data: dict[str, str]) -> None:
    ensure_hybrid_dir()
    ENV_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def audit(event: dict[str, Any]) -> None:
    ensure_hybrid_dir()
    row = {"ts": utc_now(), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def chat_completion(
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> dict[str, Any]:
    env = load_env()
    api_key = env.get("DELEGATE_API_KEY")
    if not api_key:
        raise RuntimeError("DELEGATE_API_KEY missing (env or ~/.cursor-hybrid/env.json)")

    base = env["DELEGATE_API_BASE"].rstrip("/")
    model = env["DELEGATE_MODEL"]
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    verify_ssl = env.get("VERIFY_SSL", "1") not in ("0", "false", "False")
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err[:1500]}") from e

    parsed = json.loads(body)
    parsed["_http_status"] = status
    parsed["_model"] = model
    return parsed


def read_policy_text() -> str:
    return POLICY_ASSET.read_text(encoding="utf-8").strip() + "\n"


def read_memory_text() -> str:
    return MEMORY_ASSET.read_text(encoding="utf-8").strip() + "\n"


def write_memory_file(path: Path | None = None) -> Path:
    """Persist durable routing memory under ~/.cursor/memory/."""
    target = path or MEMORY_PATH
    block = read_memory_text()
    upsert_marked_block(
        target,
        block,
        frontmatter=None,
        begin=MEMORY_MARKER_BEGIN,
        end=MEMORY_MARKER_END,
    )
    return target


def write_user_rule_from_policy(path: Path | None = None) -> Path:
    """Write alwaysApply orchestrator rule (memory + policy pair) — user-global by default."""
    target = path or USER_RULE_PATH
    frontmatter = (
        "---\n"
        "description: "
        "USER-GLOBAL: code execution via Huawei MaaS GLM (all workspaces)\n"
        "alwaysApply: true\n"
        "---\n"
    )
    memory = read_memory_text().rstrip() + "\n\n"
    policy = read_policy_text()
    text_path = target
    text_path.parent.mkdir(parents=True, exist_ok=True)
    body = memory + policy
    text_path.write_text(frontmatter + body, encoding="utf-8")
    return text_path


def _is_our_hook_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    meta = entry.get("metadata") or {}
    if meta.get("id") in ("maas-delegate-router", "maas-session-start"):
        return True
    cmd = str(entry.get("command", ""))
    return "maas-route-hint" in cmd or "maas-session-start" in cmd or "route_hint" in cmd


def install_user_global_hooks() -> Path:
    """Install hook scripts + ~/.cursor/hooks.json (applies to ALL workspaces)."""
    USER_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    USER_HOOK_ROUTE.write_text(HOOK_ASSET_ROUTE.read_text(encoding="utf-8"), encoding="utf-8")
    USER_HOOK_SESSION.write_text(
        HOOK_ASSET_SESSION.read_text(encoding="utf-8"), encoding="utf-8"
    )

    if USER_HOOKS_JSON.exists():
        data = json.loads(USER_HOOKS_JSON.read_text(encoding="utf-8"))
    else:
        data = {"version": 1, "hooks": {}}

    data.setdefault("version", 1)
    data.setdefault("hooks", {})
    hooks = data["hooks"]

    # Relative to ~/.cursor/ per Cursor user-hook docs
    submit_cmd = "python ./hooks/maas-route-hint.py"
    session_cmd = "python ./hooks/maas-session-start.py"

    before = [e for e in (hooks.get("beforeSubmitPrompt") or []) if not _is_our_hook_entry(e)]
    before.append(
        {
            "command": submit_cmd,
            "metadata": {"id": "maas-delegate-router"},
        }
    )
    hooks["beforeSubmitPrompt"] = before

    sessions = [e for e in (hooks.get("sessionStart") or []) if not _is_our_hook_entry(e)]
    sessions.append(
        {
            "command": session_cmd,
            "metadata": {"id": "maas-session-start"},
        }
    )
    hooks["sessionStart"] = sessions

    data["hooks"] = hooks
    USER_HOOKS_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return USER_HOOKS_JSON


def strip_user_global_hooks() -> bool:
    """Remove our entries from ~/.cursor/hooks.json; keep other hooks."""
    if not USER_HOOKS_JSON.exists():
        return False
    data = json.loads(USER_HOOKS_JSON.read_text(encoding="utf-8"))
    hooks = data.get("hooks") or {}
    changed = False
    for key in ("beforeSubmitPrompt", "sessionStart"):
        entries = hooks.get(key) or []
        new_entries = [e for e in entries if not _is_our_hook_entry(e)]
        if len(new_entries) != len(entries):
            changed = True
        hooks[key] = new_entries
    if changed:
        data["hooks"] = hooks
        USER_HOOKS_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for path in (USER_HOOK_ROUTE, USER_HOOK_SESSION):
        if path.exists():
            path.unlink(missing_ok=True)
            changed = True
    return changed


def upsert_marked_block(
    path: Path,
    block: str,
    *,
    frontmatter: str | None = None,
    begin: str = MARKER_BEGIN,
    end: str = MARKER_END,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = frontmatter or ""

    if begin in text and end in text:
        pre = text.split(begin, 1)[0]
        post = text.split(end, 1)[1]
        text = pre + block.rstrip() + "\n" + post.lstrip("\n")
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text = text + "\n" + block.rstrip() + "\n"

    path.write_text(text, encoding="utf-8")


def remove_marked_block(
    path: Path,
    *,
    begin: str = MARKER_BEGIN,
    end: str = MARKER_END,
) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if begin not in text or end not in text:
        return False
    pre = text.split(begin, 1)[0]
    post = text.split(end, 1)[1]
    path.write_text((pre + post.lstrip("\n")).rstrip() + "\n", encoding="utf-8")
    return True
