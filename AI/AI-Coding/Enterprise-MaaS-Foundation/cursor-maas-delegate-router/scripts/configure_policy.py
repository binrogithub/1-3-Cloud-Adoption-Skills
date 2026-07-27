#!/usr/bin/env python3
"""Install USER-GLOBAL memory, Rule, and hooks (all Cursor workspaces)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    HOOK_ASSET_ROUTE,
    HOOK_ASSET_SESSION,
    MEMORY_PATH,
    USER_HOOKS_DIR,
    USER_HOOKS_JSON,
    install_user_global_hooks,
    python_hook_command,
    write_memory_file,
    write_user_rule_from_policy,
)


def project_rule_path() -> Path:
    return Path.cwd() / ".cursor" / "rules" / "maas-delegate-router.mdc"


def project_memory_path() -> Path:
    return Path.cwd() / ".cursor" / "memory" / "maas-delegate-router.md"


def project_hooks_path() -> Path:
    return Path.cwd() / ".cursor" / "hooks.json"


def merge_project_hooks(hooks_path: Path) -> None:
    """Optional project overlay (not the default). Prefer user-global install."""
    proj_hooks = hooks_path.parent / "hooks"
    proj_hooks.mkdir(parents=True, exist_ok=True)
    route = proj_hooks / "maas-route-hint.py"
    session = proj_hooks / "maas-session-start.py"
    shutil.copyfile(HOOK_ASSET_ROUTE, route)
    shutil.copyfile(HOOK_ASSET_SESSION, session)

    if hooks_path.exists():
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    else:
        data = {"version": 1, "hooks": {}}
    data.setdefault("version", 1)
    data.setdefault("hooks", {})
    hooks = data["hooks"]

    def scrub(entries: list) -> list:
        return [
            e
            for e in entries
            if not (
                isinstance(e, dict)
                and (
                    (e.get("metadata") or {}).get("id")
                    in ("maas-delegate-router", "maas-session-start")
                    or "maas-route" in str(e.get("command", ""))
                    or "maas-session" in str(e.get("command", ""))
                )
            )
        ]

    hooks["beforeSubmitPrompt"] = scrub(hooks.get("beforeSubmitPrompt") or []) + [
        {
            "command": python_hook_command(".cursor/hooks/maas-route-hint.py"),
            "metadata": {"id": "maas-delegate-router"},
        }
    ]
    hooks["sessionStart"] = scrub(hooks.get("sessionStart") or []) + [
        {
            "command": python_hook_command(".cursor/hooks/maas-session-start.py"),
            "metadata": {"id": "maas-session-start"},
        }
    ]
    data["hooks"] = hooks
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure MaaS delegate routing (default: USER-GLOBAL for all workspaces)"
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help="Also write project-local .cursor/ overlay (still installs user-global unless --project-only)",
    )
    parser.add_argument(
        "--project-only",
        action="store_true",
        help="Write ONLY into cwd .cursor/ (not recommended; skips user-global)",
    )
    parser.add_argument(
        "--with-hook",
        action="store_true",
        default=True,
        help="Register hooks (default: on)",
    )
    parser.add_argument("--skip-hook", action="store_true", help="Skip hook registration")
    args = parser.parse_args()
    if args.skip_hook:
        args.with_hook = False

    if args.project_only:
        written_mem = write_memory_file(project_memory_path())
        written_rule = write_user_rule_from_policy(project_rule_path())
        print(f"Memory written (project-only): {written_mem}")
        print(f"Policy written (project-only): {written_rule}")
        if args.with_hook:
            merge_project_hooks(project_hooks_path())
            print(f"Hook registered (project-only): {project_hooks_path()}")
        print("CONFIGURE OK (project-only — not global)")
        return 0

    # Default: USER-GLOBAL — applies to every workspace
    written_mem = write_memory_file(MEMORY_PATH)
    written_rule = write_user_rule_from_policy()
    print(f"Memory written (USER-GLOBAL): {written_mem}")
    print(f"Policy written (USER-GLOBAL): {written_rule}")

    if args.with_hook:
        hooks_path = install_user_global_hooks()
        print(f"Hooks registered (USER-GLOBAL): {hooks_path}")
        print(f"Hook scripts dir: {USER_HOOKS_DIR}")
        print("Events: sessionStart + beforeSubmitPrompt (all workspaces)")

    if args.project:
        write_memory_file(project_memory_path())
        write_user_rule_from_policy(project_rule_path())
        if args.with_hook:
            merge_project_hooks(project_hooks_path())
        print("Also wrote project overlay under ./.cursor/")

    print("CONFIGURE OK — scope=USER-GLOBAL (affects all Cursor projects)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
