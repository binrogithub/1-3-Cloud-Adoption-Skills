#!/usr/bin/env python3
"""Resume the single guarded CSS 24-hour run after host or process recovery."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from css_run_state import digest  # noqa: E402


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular JSON file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def select_run_args(argv: Sequence[str], *, profile_id: str, config_dir: Path,
                    plan_path: Path, state_dir: Path, duration_seconds: int) -> list[str]:
    plan = read_json(plan_path)
    business_digest = None
    business_value = plan.get("business_config_file")
    if business_value:
        business_path = Path(str(business_value))
        if not business_path.is_absolute():
            business_path = plan_path.parent / business_path
        business_digest = digest(read_json(business_path))
    expected_digest = digest({"plan": plan, "duration_seconds": duration_seconds,
                              "business_config_digest": business_digest})
    matching: list[tuple[Path, dict]] = []
    incompatible_running: list[str] = []
    terminal: list[str] = []
    for checkpoint in state_dir.glob("*.checkpoint.json"):
        try:
            value = read_json(checkpoint)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if value.get("profile_id") != profile_id:
            continue
        if value.get("status") == "RUNNING":
            if value.get("plan_digest") == expected_digest and int(value.get("duration_seconds", 0)) == duration_seconds:
                matching.append((checkpoint, value))
            else:
                incompatible_running.append(checkpoint.name)
        else:
            terminal.append(checkpoint.name)
    if incompatible_running:
        raise ValueError("an unfinished run exists with an incompatible plan")
    if len(matching) > 1:
        raise ValueError("multiple resumable runs exist; inspect state before starting")
    options = [item for item in argv if item != "--new-run" and not item.startswith("--resume-run-id=")]
    if "--resume-run-id" in options:
        index = options.index("--resume-run-id")
        del options[index:index + 2]
    if matching:
        return [*options, "--resume-run-id", str(matching[0][1]["run_id"])]
    if terminal:
        raise ValueError("a terminal run already exists; refusing to restart pressure automatically")
    return [*options, "--new-run"]


def main(argv: Sequence[str] | None = None) -> int:
    actual = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, required=True)
    args, _ = parser.parse_known_args(actual)
    try:
        selected = select_run_args(actual, profile_id=args.profile_id,
                                   config_dir=args.config_dir, plan_path=args.plan,
                                   state_dir=args.state_dir,
                                   duration_seconds=args.duration_seconds)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "RESUME_BLOCKED", "error": str(exc),
                          "secrets_included": False}, ensure_ascii=False))
        return 2
    os.execv(sys.executable, [sys.executable, str(ROOT / "scripts" / "css-24h-pressure.py"), *selected])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
