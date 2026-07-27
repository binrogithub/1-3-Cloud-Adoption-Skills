#!/usr/bin/env python3
"""Run one execution brief against the delegate (MaaS / LiteLLM) endpoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import audit, chat_completion, is_under_root  # noqa: E402


SYSTEM = """You are an execution worker that edits files via JSON only.
Reply with ONLY valid JSON (no markdown fences):
{
  "status": "success" | "failed",
  "summary": "what you changed or why failed",
  "files_touched": ["relative/path", ...],
  "file_writes": [{"path": "relative/path", "content": "full new file text"}],
  "acceptance_met": true | false,
  "notes": "optional"
}
Rules:
- Prefer complete file contents in file_writes for every file you change.
- Paths must be relative to the project root provided in the brief.
- If you cannot meet acceptance, status=failed and acceptance_met=false.
- Do not wrap JSON in ``` fences."""


def load_brief(args: argparse.Namespace) -> dict[str, Any]:
    if args.brief_file:
        return json.loads(Path(args.brief_file).read_text(encoding="utf-8"))
    if args.brief:
        return json.loads(args.brief)
    raise SystemExit("Provide --brief or --brief-file")


def validate_brief(brief: dict[str, Any]) -> None:
    for key in ("goal", "files", "acceptance"):
        if key not in brief:
            raise SystemExit(f"brief missing required field: {key}")
    if not isinstance(brief["goal"], str) or not brief["goal"].strip():
        raise SystemExit("brief.goal must be a non-empty string")
    if not isinstance(brief["files"], list):
        raise SystemExit("brief.files must be an array")
    if any(not isinstance(item, str) for item in brief["files"]):
        raise SystemExit("brief.files entries must be strings")
    if not isinstance(brief["acceptance"], str) or not brief["acceptance"].strip():
        raise SystemExit("brief.acceptance must be a non-empty string")
    if "constraints" in brief and (
        not isinstance(brief["constraints"], list)
        or any(not isinstance(item, str) for item in brief["constraints"])
    ):
        raise SystemExit("brief.constraints must be an array of strings")
    if "context" in brief and not isinstance(brief["context"], str):
        raise SystemExit("brief.context must be a string")
    if "accept_cmd" in brief and not isinstance(brief["accept_cmd"], str):
        raise SystemExit("brief.accept_cmd must be a string")
    try:
        max_attempts = int(brief.get("max_attempts") or 2)
    except (TypeError, ValueError) as e:
        raise SystemExit("brief.max_attempts must be an integer") from e
    if not 1 <= max_attempts <= 5:
        raise SystemExit("brief.max_attempts must be between 1 and 5")


def _read_workspace_files(root: Path, files: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in files:
        path = (root / rel).resolve()
        if not is_under_root(path, root):
            continue
        if path.is_file():
            out[rel] = path.read_text(encoding="utf-8")
    return out


def _apply_file_writes(root: Path, writes: list[Any]) -> list[str]:
    touched: list[str] = []
    for item in writes or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        content = item.get("content")
        if not isinstance(rel, str) or not isinstance(content, str):
            continue
        path = (root / rel).resolve()
        if not is_under_root(path, root):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        touched.append(rel.replace("\\", "/"))
    return touched


def _strip_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    return text


def run_once(brief: dict[str, Any], attempt: int, root: Path) -> dict[str, Any]:
    workspace = _read_workspace_files(root, list(brief.get("files") or []))
    user = {
        "attempt": attempt,
        "project_root": str(root),
        "goal": brief["goal"],
        "files": brief.get("files", []),
        "workspace_files": workspace,
        "acceptance": brief["acceptance"],
        "constraints": brief.get("constraints", []),
        "context": brief.get("context", ""),
    }
    resp = chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        max_tokens=4096,
    )
    content = resp["choices"][0]["message"]["content"]
    text = _strip_json(content)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {
            "status": "failed",
            "summary": "delegate returned non-JSON",
            "files_touched": [],
            "acceptance_met": False,
            "notes": content[:1000],
            "raw": content,
        }

    writes = result.get("file_writes") or []
    if isinstance(writes, list) and writes:
        touched = _apply_file_writes(root, writes)
        result["files_touched"] = sorted(set((result.get("files_touched") or []) + touched))
        result["_wrote_files"] = touched

    result["_model"] = resp.get("_model")
    result["_attempt"] = attempt
    return result


def _run_accept_cmd(root: Path, cmd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output[-2000:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Delegate one execution brief to MaaS/LiteLLM")
    parser.add_argument("--brief", default=None, help="Brief JSON string")
    parser.add_argument("--brief-file", default=None, help="Path to brief JSON")
    parser.add_argument(
        "--root",
        default=None,
        help="Project root for file reads/writes (default: cwd)",
    )
    args = parser.parse_args()

    brief = load_brief(args)
    validate_brief(brief)
    root = Path(args.root or Path.cwd()).resolve()
    max_attempts = int(brief.get("max_attempts") or 2)
    accept_cmd = brief.get("accept_cmd")

    last: dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        try:
            last = run_once(brief, attempt, root)
        except Exception as e:  # noqa: BLE001
            last = {
                "status": "failed",
                "summary": str(e),
                "files_touched": [],
                "acceptance_met": False,
                "notes": "",
                "_attempt": attempt,
            }

        if accept_cmd and last.get("status") == "success":
            ok_cmd, cmd_out = _run_accept_cmd(root, str(accept_cmd))
            last["_accept_cmd_ok"] = ok_cmd
            last["_accept_cmd_output"] = cmd_out
            if not ok_cmd:
                last["status"] = "failed"
                last["acceptance_met"] = False
                last["summary"] = (last.get("summary") or "") + f" | accept_cmd failed: {cmd_out}"
            else:
                last["acceptance_met"] = True

        ok = last.get("status") == "success" and last.get("acceptance_met") is True
        audit(
            {
                "type": "delegate",
                "attempt": attempt,
                "goal": brief["goal"],
                "files": brief.get("files", []),
                "result_status": last.get("status"),
                "acceptance_met": last.get("acceptance_met"),
                "model": last.get("_model"),
                "wrote_files": last.get("_wrote_files") or [],
            }
        )
        if ok:
            out = {**last, "status": "success"}
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0

        brief = {
            **brief,
            "context": (brief.get("context") or "")
            + f"\nPrevious attempt {attempt} failed: {last.get('summary')}",
        }

    out = {
        **last,
        "status": "needs_escalation",
        "summary": last.get("summary") or "max attempts exhausted",
        "acceptance_met": False,
    }
    audit(
        {
            "type": "delegate",
            "attempt": max_attempts,
            "goal": brief["goal"],
            "result_status": "needs_escalation",
            "files": brief.get("files", []),
        }
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
