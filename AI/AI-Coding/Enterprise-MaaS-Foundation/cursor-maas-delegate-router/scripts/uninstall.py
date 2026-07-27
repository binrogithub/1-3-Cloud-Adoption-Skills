#!/usr/bin/env python3
"""Remove USER-GLOBAL policy/memory/hooks/bin. Optionally purge ~/.cursor-hybrid."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BIN_DIR,
    HOME,
    HYBRID_DIR,
    MEMORY_PATH,
    strip_user_global_hooks,
)

USER_RULE = HOME / ".cursor" / "rules" / "maas-delegate-router.mdc"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        action="store_true",
        help="Also remove project-local .cursor overlay in cwd",
    )
    parser.add_argument("--purge", action="store_true", help="Delete entire ~/.cursor-hybrid")
    args = parser.parse_args()

    removed_rule = False
    if USER_RULE.exists():
        USER_RULE.unlink(missing_ok=True)
        removed_rule = True

    removed_memory = False
    if MEMORY_PATH.exists():
        MEMORY_PATH.unlink(missing_ok=True)
        removed_memory = True
        try:
            MEMORY_PATH.parent.rmdir()
        except OSError:
            pass

    removed_hook = strip_user_global_hooks()

    if args.project:
        for p in (
            Path.cwd() / ".cursor" / "rules" / "maas-delegate-router.mdc",
            Path.cwd() / ".cursor" / "memory" / "maas-delegate-router.md",
            Path.cwd() / ".cursor" / "hooks" / "maas-route-hint.py",
            Path.cwd() / ".cursor" / "hooks" / "maas-session-start.py",
        ):
            if p.exists():
                p.unlink(missing_ok=True)
        # Leave project hooks.json entries — best-effort strip
        ph = Path.cwd() / ".cursor" / "hooks.json"
        if ph.exists():
            try:
                import json

                data = json.loads(ph.read_text(encoding="utf-8"))
                hooks = data.get("hooks") or {}
                for key in ("beforeSubmitPrompt", "sessionStart"):
                    hooks[key] = [
                        e
                        for e in (hooks.get(key) or [])
                        if not (
                            isinstance(e, dict)
                            and (
                                (e.get("metadata") or {}).get("id", "").startswith("maas-")
                                or "maas-" in str(e.get("command", ""))
                            )
                        )
                    ]
                data["hooks"] = hooks
                ph.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass

    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR, ignore_errors=True)

    if args.purge and HYBRID_DIR.exists():
        shutil.rmtree(HYBRID_DIR, ignore_errors=True)
        print(f"Purged {HYBRID_DIR}")
    else:
        print(f"Kept data dir {HYBRID_DIR} (use --purge to delete)")

    print(
        f"rule_removed={removed_rule} memory_removed={removed_memory} "
        f"hook_removed={removed_hook}"
    )
    print("UNINSTALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
