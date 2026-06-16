"""Single entry point that dispatches to the reused scripts / glue.

    python -m mce.cli retrieve --query "routing fallback" --max-items 5
    python -m mce.cli capture  --text "<fact>" --org acme --app gateway --user dev
    python -m mce.cli writeback --memory-dir DIR --repo-root . --org acme --mode review
    python -m mce.cli run --plan dream-writeback --memory-dir DIR --repo-root . --org acme
    python -m mce.cli dream    [args passed through to scripts/dream.py]
    python -m mce.cli distill  [args passed through to scripts/distill.py]
    python -m mce.cli artifact export [--db .code-dreaming/code-index.db]
                                      [--output .code-dreaming/code-index.db.zst]
    python -m mce.cli artifact import [--input .code-dreaming/code-index.db.zst]
                                      [--db .code-dreaming/code-index.db]
"""
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _cmd_artifact(rest: list) -> int:
    """Handle ``mce artifact export`` and ``mce artifact import``."""
    import argparse

    if not rest:
        print("Usage: mce artifact <export|import> [options]", file=sys.stderr)
        return 2

    subcmd, sub_rest = rest[0], rest[1:]

    # Ensure scripts/ is importable
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from code_index import CodeIndex  # type: ignore[import]

    if subcmd == "export":
        ap = argparse.ArgumentParser(prog="mce artifact export")
        ap.add_argument(
            "--db",
            default=".code-dreaming/code-index.db",
            help="Path to the SQLite code-index DB (default: .code-dreaming/code-index.db)",
        )
        ap.add_argument(
            "--output",
            default=None,
            help="Destination .zst file (default: <db>.zst alongside the DB)",
        )
        a = ap.parse_args(sub_rest)

        db_path = Path(a.db)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path

        if not db_path.exists():
            print(f"error: DB not found: {db_path}", file=sys.stderr)
            return 1

        output_path = Path(a.output) if a.output else None
        if output_path and not output_path.is_absolute():
            output_path = Path.cwd() / output_path

        t0 = time.monotonic()
        with CodeIndex.open_or_create(db_path) as idx:
            meta = idx.export_artifact(output_path)

        elapsed = time.monotonic() - t0
        ratio = meta["uncompressed_size"] / meta["compressed_size"] if meta["compressed_size"] else 0
        out_file = output_path or (db_path.parent / (db_path.name + ".zst"))
        print(
            f"Exported: {out_file}\n"
            f"  Files:       {meta['files_count']}\n"
            f"  Symbols:     {meta['symbols_count']}\n"
            f"  Uncompressed: {meta['uncompressed_size']:,} bytes\n"
            f"  Compressed:   {meta['compressed_size']:,} bytes\n"
            f"  Ratio:        {ratio:.1f}:1\n"
            f"  Time:         {elapsed:.2f}s\n"
            f"  artifact.json written alongside .zst"
        )
        return 0

    if subcmd == "import":
        ap = argparse.ArgumentParser(prog="mce artifact import")
        ap.add_argument(
            "--input",
            default=".code-dreaming/code-index.db.zst",
            help="Source .zst artifact (default: .code-dreaming/code-index.db.zst)",
        )
        ap.add_argument(
            "--db",
            default=".code-dreaming/code-index.db",
            help="Destination DB path (default: .code-dreaming/code-index.db)",
        )
        a = ap.parse_args(sub_rest)

        input_path = Path(a.input)
        if not input_path.is_absolute():
            input_path = Path.cwd() / input_path

        db_path = Path(a.db)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path

        if not input_path.exists():
            print(f"error: artifact not found: {input_path}", file=sys.stderr)
            return 1

        t0 = time.monotonic()
        idx = CodeIndex.import_artifact(input_path, db_path)
        files_count = idx.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols_count = idx.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        schema_ver = idx.schema_version()
        idx.close()
        elapsed = time.monotonic() - t0

        print(
            f"Imported: {db_path}\n"
            f"  Source:   {input_path}\n"
            f"  Schema:   v{schema_ver}\n"
            f"  Files:    {files_count}\n"
            f"  Symbols:  {symbols_count}\n"
            f"  Time:     {elapsed:.2f}s"
        )
        return 0

    print(f"unknown artifact subcommand: {subcmd!r}. Use export or import.", file=sys.stderr)
    return 2


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
    if cmd == "artifact":
        return _cmd_artifact(rest)
    print(f"unknown command: {cmd}\n{__doc__}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
