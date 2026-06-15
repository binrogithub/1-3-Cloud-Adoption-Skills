"""Single entry point that dispatches to the reused scripts / glue.

    python -m mce.cli retrieve --query "routing fallback" --max-items 5
    python -m mce.cli capture  --text "<fact>" --org acme --app gateway --user dev
    python -m mce.cli writeback --memory-dir DIR --repo-root . --org acme --mode review
    python -m mce.cli run --plan dream-writeback --memory-dir DIR --repo-root . --org acme
    python -m mce.cli dream    [args passed through to scripts/dream.py]
    python -m mce.cli distill  [args passed through to scripts/distill.py]
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "retrieve":
        import argparse
        from mce.retrieve import retrieve_approved_context
        ap = argparse.ArgumentParser(prog="mce retrieve")
        ap.add_argument("--query", required=True)
        ap.add_argument("--max-items", type=int, default=5)
        ap.add_argument("--max-tokens", type=int, default=2000)
        ap.add_argument("--memory-dir", default=None)
        a = ap.parse_args(rest)
        md = Path(a.memory_dir) if a.memory_dir else None
        print(retrieve_approved_context(a.query, a.max_items, a.max_tokens, md))
        return 0
    if cmd == "capture":
        import argparse
        from mce.backbone import Backbone, Scope, PrivacyError
        ap = argparse.ArgumentParser(prog="mce capture")
        ap.add_argument("--text", required=True)
        ap.add_argument("--org", required=True)
        ap.add_argument("--app", default="")
        ap.add_argument("--user", default="")
        ap.add_argument("--run", default="")
        ap.add_argument("--config", default=str(ROOT / "assets" / "mem0.config.yaml"))
        a = ap.parse_args(rest)
        try:
            bb = Backbone.from_config(a.config)
        except ImportError:
            print("Mem0 not installed; capture needs the backbone. "
                  "Run: pip install -e vendor/mem0", file=sys.stderr)
            return 1
        try:
            bb.capture(a.text, Scope(org=a.org, app=a.app, user=a.user, run=a.run))
        except PrivacyError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        print("captured (ADD-only, scoped, secret-filtered).")
        return 0
    if cmd == "writeback":
        import argparse
        import json
        from dataclasses import asdict
        from mce.backbone import Scope
        from mce.writeback import writeback_from_memory
        ap = argparse.ArgumentParser(prog="mce writeback")
        ap.add_argument("--memory-dir", required=True)
        ap.add_argument("--repo-root", required=True)
        ap.add_argument("--org", required=True)
        ap.add_argument("--app", default="")
        ap.add_argument("--user", default="")
        ap.add_argument("--run", default="")
        ap.add_argument("--mode", choices=["review", "apply"], default="review")
        ap.add_argument("--source")
        ap.add_argument("--config", default=str(ROOT / "assets" / "mem0.config.yaml"))
        ap.add_argument("--allow-global", action="store_true")
        a = ap.parse_args(rest)
        summary = writeback_from_memory(
            memory_dir=Path(a.memory_dir),
            repo_root=Path(a.repo_root),
            scope=Scope(org=a.org, app=a.app, user=a.user, run=a.run),
            mode=a.mode,
            source=Path(a.source) if a.source else None,
            config_path=Path(a.config),
            allow_global=a.allow_global,
        )
        print(json.dumps(asdict(summary), indent=2))
        return 0
    if cmd == "run":
        import argparse
        from mce.backbone import Scope
        from mce.executor import run_plan, summary_json
        ap = argparse.ArgumentParser(prog="mce run")
        ap.add_argument("--plan", required=True, choices=["dream-writeback"])
        ap.add_argument("--memory-dir", required=True)
        ap.add_argument("--repo-root", required=True)
        ap.add_argument("--org", required=True)
        ap.add_argument("--app", default="")
        ap.add_argument("--user", default="")
        ap.add_argument("--run", default="")
        ap.add_argument("--mode", choices=["review", "apply"], default="review")
        ap.add_argument("--source")
        ap.add_argument("--config", default=str(ROOT / "assets" / "mem0.config.yaml"))
        ap.add_argument("--allow-global", action="store_true")
        a = ap.parse_args(rest)
        summary = run_plan(
            a.plan,
            memory_dir=Path(a.memory_dir),
            repo_root=Path(a.repo_root),
            scope=Scope(org=a.org, app=a.app, user=a.user, run=a.run),
            mode=a.mode,
            source=Path(a.source) if a.source else None,
            config_path=Path(a.config),
            allow_global=a.allow_global,
        )
        print(summary_json(summary))
        return 0
    if cmd in ("dream", "distill"):
        # delegate to the reused first-party scripts (ported MiMo design)
        sys.argv = [str(ROOT / "scripts" / f"{cmd}.py"), *rest]
        runpy.run_path(str(ROOT / "scripts" / f"{cmd}.py"), run_name="__main__")
        return 0
    print(f"unknown command: {cmd}\n{__doc__}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
