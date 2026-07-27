#!/usr/bin/env python3
"""Create ~/.cursor-hybrid runtime, persist DELEGATE_*, write memory + rule."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BIN_DIR,
    DEFAULT_CODE_ROUTE,
    DEFAULT_ROUTE_PRIORITY,
    ENV_PATH,
    HYBRID_DIR,
    MEMORY_PATH,
    SKILL_ROOT,
    USER_HOOKS_DIR,
    USER_HOOKS_JSON,
    USER_RULE_PATH,
    ensure_hybrid_dir,
    install_user_global_hooks,
    load_env,
    save_env,
    write_memory_file,
    write_user_rule_from_policy,
)


def write_launchers() -> None:
    scripts = ["delegate.py", "workflow.py", "verify.py", "route_stats.py", "preprocess_doc.py"]
    for name in scripts:
        src = SKILL_ROOT / "scripts" / name
        cmd = BIN_DIR / name.replace(".py", ".cmd")
        cmd.write_text(
            "@echo off\r\n"
            f'python "{src}" %*\r\n',
            encoding="utf-8",
        )
        sh = BIN_DIR / name.replace(".py", "")
        sh.write_text(
            "#!/usr/bin/env bash\n"
            f'exec python3 "{src}" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        try:
            sh.chmod(0o755)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Install cursor-maas-delegate-router runtime")
    parser.add_argument("--base-url", default=None, help="DELEGATE_API_BASE")
    parser.add_argument("--api-key", default=None, help="DELEGATE_API_KEY")
    parser.add_argument("--model", default=None, help="DELEGATE_MODEL")
    parser.add_argument(
        "--skip-memory",
        action="store_true",
        help="Do not write ~/.cursor/memory or alwaysApply rule",
    )
    parser.add_argument(
        "--with-hook",
        action="store_true",
        default=True,
        help="Register beforeSubmitPrompt hook (default: on)",
    )
    parser.add_argument(
        "--skip-hook",
        action="store_true",
        help="Do not register beforeSubmitPrompt hook",
    )
    args = parser.parse_args()
    if args.skip_hook:
        args.with_hook = False

    ensure_hybrid_dir()
    env = load_env()
    if args.base_url:
        env["DELEGATE_API_BASE"] = args.base_url.rstrip("/")
    if args.api_key:
        env["DELEGATE_API_KEY"] = args.api_key
    if args.model:
        env["DELEGATE_MODEL"] = args.model

    # Durable routing defaults: MaaS GLM for code execution, above Cursor routing.
    env["CODE_EXECUTION_ROUTE"] = env.get("CODE_EXECUTION_ROUTE") or DEFAULT_CODE_ROUTE
    env["ROUTE_PRIORITY"] = env.get("ROUTE_PRIORITY") or DEFAULT_ROUTE_PRIORITY

    if not env.get("DELEGATE_API_KEY"):
        print(
            "WARN: DELEGATE_API_KEY not set. Re-run with --api-key or export env, then install again.",
            file=sys.stderr,
        )

    save_env(env)
    write_launchers()

    if not args.skip_memory:
        mem = write_memory_file()
        rule = write_user_rule_from_policy()
        print(f"Memory written (USER-GLOBAL): {mem}")
        print(f"Rule written (USER-GLOBAL): {rule}")
        print(
            "Route default: CODE_EXECUTION_ROUTE=maas_glm "
            "(USER-GLOBAL — all Cursor workspaces)"
        )

    if args.with_hook:
        hooks_path = install_user_global_hooks()
        print(f"Hooks registered (USER-GLOBAL): {hooks_path}")
        print(f"Hook scripts: {USER_HOOKS_DIR}")
        print("Events: sessionStart + beforeSubmitPrompt")

    print(f"Installed runtime: {HYBRID_DIR}")
    print(f"Env file: {ENV_PATH}")
    print(f"Launchers: {BIN_DIR}")
    print(f"base={env.get('DELEGATE_API_BASE')} model={env.get('DELEGATE_MODEL')}")
    print(f"code_route={env.get('CODE_EXECUTION_ROUTE')} priority={env.get('ROUTE_PRIORITY')}")
    if not args.skip_memory:
        print(f"memory={MEMORY_PATH}")
        print(f"rule={USER_RULE_PATH}")
    if args.with_hook:
        print(f"hooks={USER_HOOKS_JSON}")
    print("INSTALL OK — scope=USER-GLOBAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
