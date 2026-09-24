#!/usr/bin/env python3
"""Execute the 50 AI Native AutoOps prompts one by one through the real TUI."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "docs" / "jiuwen-autoops-ai-native-50-hard-test-cases.md"
LAUNCHER = ROOT / "scripts" / "Jiuwen_autoops_tui"
CHECKER = ROOT / "scripts" / "tui-history-completion-check.py"
CASE_RE = re.compile(r"^### AN-T(\d{2})：(.+)$", re.MULTILINE)
PROMPT_RE = re.compile(r"^\*\*用户输入：\*\*(.+)$", re.MULTILINE)
ENV_GAP_MARKERS = (
    "TARGET_UNSUPPORTED", "PROFILE_NOT_FOUND", "PATH_NOT_PUBLISHED",
    "not published", "unavailable", "inconclusive", "GAP_CAPABILITY",
)
BOUNDARY_MARKERS = (
    "PASS-BOUNDARY", "WAITING_APPROVAL", "PENDING_CONFIRMATION",
    "AUTHORIZATION_REQUIRED", "TARGET_UNSUPPORTED", "PROFILE_NOT_FOUND",
    "PATH_NOT_PUBLISHED",
    "Continuity Gap",
    "连续性缺口",
)


def parse_cases(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    matches = list(CASE_RE.finditer(text))
    cases: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():block_end]
        prompt_match = PROMPT_RE.search(block)
        if not prompt_match:
            raise ValueError(f"missing user input for AN-T{match.group(1)}")
        raw_prompt = prompt_match.group(1).strip()
        first_quote = raw_prompt.find("“")
        if first_quote >= 0:
            closing_quote = raw_prompt.find("”", first_quote + 1)
            if closing_quote < 0:
                raise ValueError(f"unclosed user input for AN-T{match.group(1)}")
            raw_prompt = raw_prompt[first_quote + 1:closing_quote]
        elif raw_prompt.endswith("。"):
            raw_prompt = raw_prompt[:-1]
        cases.append({"case_id": f"AN-T{match.group(1)}", "title": match.group(2).strip(),
                      "prompt": raw_prompt})
    if [case["case_id"] for case in cases] != [f"AN-T{number:02d}" for number in range(1, 51)]:
        raise ValueError("case document must contain AN-T01 through AN-T50 exactly once")
    return cases


def classify(history: Path, returncode: int, output: str) -> tuple[str, str]:
    if not history.is_file():
        return ("INCONCLUSIVE", "history_missing")
    history_text = history.read_text(encoding="utf-8", errors="replace")
    if returncode == 0:
        check = subprocess.run([sys.executable, str(CHECKER), str(history)],
                               text=True, capture_output=True, check=False)
        if check.returncode == 0:
            if any(marker in history_text or marker in output for marker in BOUNDARY_MARKERS):
                return ("PASS-BOUNDARY", "route_completed_with_boundary_signal")
            return ("PASS-ROUTE", "route_completed; business_fixture_not_evaluated")
    if any(marker.casefold() in (history_text + output).casefold() for marker in ENV_GAP_MARKERS):
        return ("BLOCKED_ENV", "runtime_or_published_capability_gap")
    if returncode == 124:
        return ("INCONCLUSIVE", "tui_timeout")
    return ("FAIL", "tui_or_history_completion_check_failed")


def run(args: argparse.Namespace) -> int:
    cases = parse_cases(args.cases_file)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    completed: dict[str, dict] = {}
    if args.results.exists():
        for line in args.results.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("case_id"), str):
                completed[row["case_id"]] = row
    with args.results.open("a", encoding="utf-8") as stream:
        for case in cases:
            if case["case_id"] in completed and not args.rerun_completed:
                continue
            session = f"autoops-ai-native-{case['case_id'].lower()}-{args.run_id}"
            history = Path(args.session_dir) / session / "history.jsonl"
            started = time.time()
            command = ["timeout", str(args.timeout_seconds), str(LAUNCHER), "--no-install",
                       "--once", "--session", session, case["prompt"]]
            process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                     check=False)
            output = (process.stdout + "\n" + process.stderr)[-4000:]
            result, reason = classify(history, process.returncode, output)
            row = {
                "case_id": case["case_id"], "title": case["title"],
                "prompt": case["prompt"], "session": session, "history": str(history),
                "returncode": process.returncode, "result": result, "reason": reason,
                "business_result": "NOT_EVALUATED_NO_FIXTURE",
                "started_at": started, "duration_seconds": round(time.time() - started, 3),
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"case_id": case["case_id"], "result": result,
                              "session": session}, ensure_ascii=False), flush=True)
            # A technical failure must be repaired before the next scenario.
            # Environment boundaries and business-fixture gaps are recorded and
            # may continue because they do not indicate a broken project path.
            if result == "FAIL":
                print(json.dumps({"status": "STOPPED_FOR_REPAIR", "case_id": case["case_id"],
                                  "results": str(args.results)}, ensure_ascii=False), flush=True)
                return 1
    rows = [completed[case["case_id"]] for case in cases if case["case_id"] in completed]
    with args.results.open(encoding="utf-8") as stream:
        rows = []
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("case_id"), str):
                completed[row["case_id"]] = row
        rows = [completed[case["case_id"]] for case in cases if case["case_id"] in completed]
    summary = {}
    for row in rows:
        summary[row["result"]] = summary.get(row["result"], 0) + 1
    print(json.dumps({"status": "COMPLETE" if len(rows) == 50 else "IN_PROGRESS",
                      "cases": len(rows), "summary": summary, "results": str(args.results)},
                     ensure_ascii=False))
    return 0 if len(rows) == 50 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 50 AI Native AutoOps TUI cases sequentially.")
    parser.add_argument("--cases-file", type=Path, default=CASES)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, default=Path("/root/.jiuwenswarm/agent/sessions"))
    parser.add_argument("--run-id", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--rerun-completed", action="store_true")
    args = parser.parse_args(argv)
    if not 30 <= args.timeout_seconds <= 900:
        parser.error("timeout_seconds must be from 30 through 900")
    try:
        return run(args)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
