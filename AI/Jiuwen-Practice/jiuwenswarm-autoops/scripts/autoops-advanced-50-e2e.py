#!/usr/bin/env python3
"""Run the AO50 scenario inputs through the real AutoOps TUI.

This runner records the TUI/ProjectManager route separately from business
fixture acceptance. A scenario is not reported as a business PASS merely
because a chat turn completed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "docs" / "jiuwen-autoops-e2e-50-advanced-scenarios-20260915.md"
DEFAULT_MANIFEST = ROOT / "config" / "acceptance" / "release-ao50-v1.json"
LAUNCHER = ROOT / "scripts" / "Jiuwen_autoops_tui"
CHECKER = ROOT / "scripts" / "tui-history-completion-check.py"
CASE_RE = re.compile(r"^### AO50-(\d{2})：(.+)$", re.MULTILINE)
INPUT_RE = re.compile(r"^\*\*用户输入：\*\*(.+)$", re.MULTILINE)


def parse_cases(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    matches = list(CASE_RE.finditer(text))
    cases: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        prompt_match = INPUT_RE.search(block)
        if not prompt_match:
            raise ValueError(f"AO50-{match.group(1)} has no user input")
        raw = prompt_match.group(1).strip()
        # Some cases wrap the actual request inside scenario prose, e.g.
        # "重复安装前后分别输入：‘检查日志’". The TUI must receive only the
        # quoted operator request; otherwise it may interpret test instructions
        # as authorization to install, uninstall, or mutate project state.
        quoted = re.search(r"“([^”]*)”", raw)
        if quoted:
            raw = quoted.group(1).strip()
        elif raw.startswith("“"):
            raise ValueError(f"AO50-{match.group(1)} has an unclosed input")
        cases.append({"case_id": f"AO50-{match.group(1)}",
                      "title": match.group(2).strip(), "prompt": raw})
    expected = [f"AO50-{number:02d}" for number in range(1, 51)]
    if [case["case_id"] for case in cases] != expected:
        raise ValueError("scenario document must contain AO50-01 through AO50-50 exactly once")
    return cases


def load_release_manifest(path: Path, cases: list[dict[str, str]]) -> dict:
    """Validate that the business runner uses the source AO50 mapping verbatim."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"release case manifest must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("kind") != "AutoOpsReleaseAcceptanceCaseManifest" or value.get("case_count") != 50:
        raise ValueError("release case manifest must contain exactly 50 acceptance cases")
    entries = value.get("cases")
    if not isinstance(entries, list) or [item.get("case_id") for item in entries] != [item["case_id"] for item in cases]:
        raise ValueError("release case manifest IDs do not match AO50 source order")
    by_id = {item["case_id"]: item for item in entries}
    for case in cases:
        entry = by_id[case["case_id"]]
        if entry.get("title") != case["title"] or case["prompt"] not in entry.get("original_prompt", ""):
            raise ValueError(f"release case manifest changed source input: {case['case_id']}")
        for field in ("scope", "fixture_ref", "ground_truth_ref", "expected", "cleanup"):
            if not entry.get(field):
                raise ValueError(f"release case manifest missing {field}: {case['case_id']}")
    return value


def valid_artifact_sha(value: str | None) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def inspect_history(history: Path) -> dict:
    if not history.is_file():
        return {"history_exists": False, "checker": {"ready": False, "error": "history_missing"}}
    check = subprocess.run([sys.executable, str(CHECKER), str(history)],
                           text=True, capture_output=True, check=False)
    try:
        checker = json.loads(check.stdout)
    except json.JSONDecodeError:
        checker = {"ready": False, "error": "invalid_checker_output",
                   "checker_stderr": check.stderr[-500:]}
    return {"history_exists": True, "history_bytes": history.stat().st_size,
            "checker": checker}


def classify(returncode: int, details: dict) -> tuple[str, str]:
    checker = details.get("checker", {})
    if returncode == 0 and checker.get("ready") is True:
        return "PASS_TUI_ROUTE", "durable_history_and_project_route_completed"
    if checker.get("forbidden_tools") or checker.get("unsafe_actions"):
        return "FAIL_GUARDRAIL", "history_contains_forbidden_or_unsafe_tool_activity"
    if returncode == 124:
        return "TUI_TIMEOUT", "launcher_timeout_before_durable_completion"
    if not details.get("history_exists"):
        return "TUI_START_FAIL", "history_missing"
    return "TUI_FAIL", "launcher_or_history_completion_check_failed"


def run(args: argparse.Namespace) -> int:
    cases = parse_cases(args.cases_file)
    release_manifest = None
    artifact_sha = None
    if args.release_business:
        release_manifest = load_release_manifest(args.manifest, cases)
        artifact_sha = args.artifact_sha256
        if not valid_artifact_sha(artifact_sha):
            raise ValueError("--artifact-sha256 is required in release-business mode")
    if args.launcher.is_symlink() or not args.launcher.is_file() or not args.launcher.stat().st_mode & 0o111:
        raise ValueError(f"launcher must be an executable regular file: {args.launcher}")
    args.results.parent.mkdir(parents=True, exist_ok=True)
    completed: dict[str, dict] = {}
    if args.results.exists() and not args.rerun_completed:
        for line in args.results.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("case_id"), str) and (
                    not args.release_business or row.get("artifact_sha256") == artifact_sha):
                completed[row["case_id"]] = row

    selected = cases[args.start - 1:args.end]
    with args.results.open("a", encoding="utf-8") as stream:
        for case in selected:
            if case["case_id"] in completed and not args.rerun_completed:
                continue
            session = f"ao50-{case['case_id'].lower()}-{args.run_id}"
            history = Path(args.session_dir) / session / "history.jsonl"
            started = time.time()
            command = ["timeout", "--signal=TERM", str(args.timeout_seconds),
                       str(args.launcher), "--no-install", "--once", "--session", session,
                       case["prompt"]]
            process = subprocess.run(command, cwd=ROOT, text=True,
                                     capture_output=True, check=False)
            details = inspect_history(history)
            result, reason = classify(process.returncode, details)
            row = {
                "case_id": case["case_id"], "title": case["title"],
                "prompt": case["prompt"], "session": session,
                "history": str(history), "returncode": process.returncode,
                "result": result, "reason": reason,
                "business_status": "NOT_EVALUATED_FIXTURE_REQUIRED",
                "artifact_sha256": artifact_sha,
                "manifest": str(args.manifest) if args.release_business else None,
                "started_at": started,
                "duration_seconds": round(time.time() - started, 3),
                "checker": details.get("checker", {}),
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"case_id": case["case_id"], "result": result,
                              "session": session}, ensure_ascii=False), flush=True)
            if result not in {"PASS_TUI_ROUTE"}:
                print(json.dumps({"status": "STOPPED_FOR_REPAIR", "case_id": case["case_id"],
                                  "results": str(args.results)}, ensure_ascii=False), flush=True)
                return 1

    rows: dict[str, dict] = {}
    for line in args.results.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("case_id"), str):
            rows[row["case_id"]] = row
    summary: dict[str, int] = {}
    for case in cases:
        row = rows.get(case["case_id"])
        if row:
            summary[row["result"]] = summary.get(row["result"], 0) + 1
    print(json.dumps({"status": "COMPLETE" if len(rows) == 50 else "IN_PROGRESS",
                      "cases": len(rows), "summary": summary,
                      "results": str(args.results)}, ensure_ascii=False))
    return 0 if len(rows) == 50 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AO50 inputs through the real TUI.")
    parser.add_argument("--cases-file", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--release-business", action="store_true",
                        help="Require and validate the release AO50 manifest and artifact SHA")
    parser.add_argument("--artifact-sha256",
                        help="SHA-256 of the installed release artifact used for this run")
    parser.add_argument("--launcher", type=Path, default=LAUNCHER,
                        help="Installed AutoOps TUI launcher")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path,
                        default=Path("/root/.jiuwenswarm/agent/sessions"))
    parser.add_argument("--run-id", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=50)
    parser.add_argument("--rerun-completed", action="store_true")
    args = parser.parse_args(argv)
    if not 30 <= args.timeout_seconds <= 900:
        parser.error("timeout_seconds must be from 30 through 900")
    if not 1 <= args.start <= args.end <= 50:
        parser.error("start/end must be within 1..50")
    try:
        return run(args)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
