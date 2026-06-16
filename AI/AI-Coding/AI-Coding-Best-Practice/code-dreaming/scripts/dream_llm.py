#!/usr/bin/env python3
"""Review-only LLM dream runner.

This module renders the vendored dream prompt with bounded trajectory evidence,
invokes a local Claude-compatible command, and writes human-reviewable artifacts
under memory/inbox/. It never edits MEMORY.md, CLAUDE.md, AGENTS.md, or global
memory.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from scripts.dream_sources import EvidenceRecord, TrajectoryResult, iter_prompt_lines, load_trajectory
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from dream_sources import EvidenceRecord, TrajectoryResult, iter_prompt_lines, load_trajectory


SECTION_ORDER = [
    "Rules",
    "Architecture decisions",
    "Discovered durable knowledge",
    "Patterns",
    "Gotchas",
]

MAAS_CODE_DREAM_PROMPT = Path(__file__).resolve().parent.parent / "upstream" / "maas-code" / "opencode" / "src" / "agent" / "prompt" / "dream.txt"
MIMO_DREAM_PROMPT = Path(__file__).resolve().parent.parent / "vendor" / "mimo-code" / "opencode" / "src" / "agent" / "prompt" / "dream.txt"
LOCAL_DREAM_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "dream.txt"


@dataclass(frozen=True)
class Candidate:
    section: str
    text: str
    status: str
    evidence_ids: list[str]
    global_candidate: bool = False


def default_memory_dir(repo_root: Path) -> Path:
    key = "-" + "-".join(part for part in repo_root.resolve().parts if part != "/")
    return Path.home() / ".claude" / "projects" / key / "memory"


def dream_prompt_path() -> Path:
    """Prefer the renamed MiMo mirror; keep vendor/local copies as fallbacks.

    should stay a thin adapter around MiMo dream semantics. The
    upstream/maas-code mirror is a complete copy of MiMo Code with the directory
    name changed for this skill; vendor/mimo-code remains the source fallback.
    """
    for prompt in (MAAS_CODE_DREAM_PROMPT, MIMO_DREAM_PROMPT, LOCAL_DREAM_PROMPT):
        if prompt.exists():
            return prompt
    return LOCAL_DREAM_PROMPT


def render_prompt(prompt_path: Path, memory_dir: Path, repo_root: Path, trajectory: TrajectoryResult, max_days: int) -> str:
    base = prompt_path.read_text(encoding="utf-8")
    evidence = "\n".join(iter_prompt_lines(trajectory))
    return f"""{base}

---

# Runtime Override: Review-Only LLM Dream

The MiMo SQLite database path above is not authoritative for this run. Use the
resolved trajectory context below instead. Do not modify files directly. Return
proposed durable memory entries only; this runner will write review artifacts.

Memory root: {memory_dir}
Repo root: {repo_root}
Window: last {max_days} days when timestamps are available

The resolved trajectory context is sufficient source evidence. Do not claim a
file is inaccessible merely because it is outside the current process directory;
use the evidence ids and source paths shown below. You may mention that a path is
from the trajectory when direct filesystem access is not needed.
The current shell working directory is irrelevant to validation. The dream target
is the Repo root above plus the resolved trajectory context below; do not reject
trajectory files because they are absent from this runner's own repository.

Every proposed durable entry must include one of:
- verified: <evidence ids>
- repo-verified: <path/symbol evidence>
- unverified: <reason>
- contradicted: <evidence ids>

Use these MEMORY.md sections only: {", ".join("## " + s for s in SECTION_ORDER)}.
Convert relative dates to YYYY-MM-DD.

After any prose summary, emit machine-readable candidates as zero or more lines:

Candidate: section=<section> | <1-3 line memory entry> | verified: <evidence ids>
Candidate: section=<section> | <1-3 line memory entry> | repo-verified: <path/symbol evidence>
Candidate: section=<section> | <1-3 line memory entry> | unverified: <reason>
Candidate: section=<section> | <1-3 line memory entry> | contradicted: <evidence ids>

If no durable entries should be promoted, emit no Candidate lines.

## Resolved Trajectory Context

{evidence}
"""


def run_llm(claude_bin: str, prompt: str) -> str:
    executable = shutil.which(claude_bin) if os.sep not in claude_bin else claude_bin
    if not executable:
        raise RuntimeError(f"LLM binary not found: {claude_bin}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="dream-llm-", suffix=".prompt.md", delete=False) as tmp:
        tmp.write(prompt)
        prompt_file = Path(tmp.name)
    try:
        with prompt_file.open("r", encoding="utf-8") as stdin:
            proc = subprocess.run(
                [executable, "-p"],
                stdin=stdin,
                text=True,
                capture_output=True,
                check=False,
            )
    finally:
        prompt_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"LLM runner failed with exit code {proc.returncode}: {detail}")
    return proc.stdout.strip()


def parse_candidates(output: str, trajectory: TrajectoryResult) -> list[Candidate]:
    ids = {record.evidence_id for record in trajectory.records}
    candidates: list[Candidate] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not re.match(r"(?i)^[-*]?\s*(candidate|memory)\s*:", line):
            continue
        parsed = _parse_candidate_line(line)
        if not parsed:
            continue
        section, text, status, evidence_ids, global_candidate = parsed
        if trajectory.no_trajectory and status == "verified":
            status = "unverified"
            evidence_ids = []
            text = _ensure_unverified(text, "no trajectory evidence available")
        elif status == "verified":
            evidence_ids = [ev for ev in evidence_ids if ev in ids]
            if not evidence_ids:
                status = "unverified"
                text = _ensure_unverified(text, "referenced evidence ids were not found")
        elif status == "unverified":
            text = _ensure_unverified(text, "LLM marked unverified")
        candidates.append(Candidate(section, text, status, evidence_ids, global_candidate))
    if not candidates:
        candidates.extend(_parse_markdown_proposed_entries(output, ids))
    return candidates


def _parse_markdown_proposed_entries(output: str, valid_ids: set[str]) -> list[Candidate]:
    """Conservative fallback for real Claude/MiMo-style Markdown proposals.

    Only parse list items inside an explicit proposed MEMORY.md block. This keeps
    the earlier noise guard intact: generic analysis and summaries still do not
    become memory candidates.
    """
    candidates: list[Candidate] = []
    section: str | None = None
    in_proposed = False
    lines = output.splitlines()

    for idx, raw in enumerate(lines):
        line = raw.strip()
        if re.search(r"(?i)proposed\s+(?:durable\s+memory\s+entries|memory\.md|memory entries)", line):
            in_proposed = True
            continue
        if not in_proposed:
            continue
        if re.match(r"(?i)^#{1,3}\s*summary\b", line) or re.match(r"^-{3,}$", line):
            section = None
            continue
        sm = re.match(
            r"^(?:#{1,4}\s*)?(?:\*\*)?##\s+(Rules|Architecture decisions|Discovered durable knowledge|Patterns|Gotchas)(?:\*\*)?\s*$",
            line,
            re.IGNORECASE,
        )
        if sm:
            section = _clean_section(sm.group(1))
            continue
        if not section:
            continue
        item = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if not item:
            continue
        text = _clean_markdown_entry(item.group(1))
        if not text or re.match(r"(?i)^(verified|repo-verified|unverified|contradicted)\s*:", text):
            continue
        evidence_blob = line + " " + " ".join(lines[idx + 1: idx + 4])
        status, evidence_ids = _status_from_evidence_blob(evidence_blob, valid_ids)
        if status == "unverified":
            text = _ensure_unverified(text, "markdown proposal lacked validated evidence ids")
        candidates.append(Candidate(section, _normalize_dates(text), status, evidence_ids))
    return candidates


def _clean_markdown_entry(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()
    text = re.sub(r"\s+-\s+(?:verified|repo-verified|unverified|contradicted)\s*:.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\[(?:verified|repo-verified|unverified|contradicted)\s*:[^\]]+\]", "", text, flags=re.IGNORECASE).strip()
    return text


def _status_from_evidence_blob(blob: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    evidence_ids = [ev for ev in re.findall(r"ev-[A-Za-z0-9]+", blob) if ev in valid_ids]
    if re.search(r"(?i)\bcontradicted\s*:", blob):
        return "contradicted", evidence_ids
    if re.search(r"(?i)\bunverified\s*:", blob):
        return "unverified", []
    if re.search(r"(?i)\brepo-verified\s*:", blob):
        return "repo-verified", []
    if re.search(r"(?i)\b(?:verified|repo-verified)\s*:", blob) and evidence_ids:
        return "verified", evidence_ids
    return "unverified", []


def _parse_candidate_line(line: str) -> tuple[str, str, str, list[str], bool] | None:
    line = re.sub(r"^[-*]\s+", "", line)
    m = re.match(r"(?i)^(?:candidate|memory)\s*:\s*(?P<body>.+)$", line)
    body = m.group("body") if m else line
    section = "Discovered durable knowledge"
    sm = re.search(r"(?i)\bsection\s*=\s*([^|]+)", body)
    if sm:
        section = _clean_section(sm.group(1))
        body = (body[: sm.start()] + body[sm.end():]).strip(" |")
    global_candidate = bool(re.search(r"(?i)\bglobal\s*=\s*(1|true|yes)\b", body))
    body = re.sub(r"(?i)\bglobal\s*=\s*(1|true|yes)\b", "", body).strip(" |")
    status = "unverified"
    evidence_ids: list[str] = []
    repo_vm = re.search(r"(?i)\brepo-verified\s*:\s*([^|]+)", body)
    vm = re.search(r"(?i)(?<!repo-)\bverified\s*:\s*([A-Za-z0-9_,.\-\s]+)", body)
    cm = re.search(r"(?i)\bcontradicted\s*:\s*([A-Za-z0-9_,.\-\s]+)", body)
    um = re.search(r"(?i)\bunverified\s*:\s*([^|]+)", body)
    repo_evidence = ""
    if repo_vm:
        status = "repo-verified"
        repo_evidence = repo_vm.group(1).strip()
        body = (body[: repo_vm.start()] + body[repo_vm.end():]).strip(" |")
    elif vm:
        status = "verified"
        evidence_ids = re.findall(r"ev-[A-Za-z0-9]+", vm.group(1))
        body = (body[: vm.start()] + body[vm.end():]).strip(" |")
    elif cm:
        status = "contradicted"
        evidence_ids = re.findall(r"ev-[A-Za-z0-9]+", cm.group(1))
        body = (body[: cm.start()] + body[cm.end():]).strip(" |")
    elif um:
        status = "unverified"
        body = (body[: um.start()] + body[um.end():]).strip(" |")
    text = _normalize_dates(body.strip())
    if not text:
        return None
    if repo_evidence and "[repo-verified:" not in text.lower():
        text = f"{text} [repo-verified: {repo_evidence}]"
    return section, text, status, evidence_ids, global_candidate


def _clean_section(value: str) -> str:
    normalized = value.strip().strip("# ").strip()
    for allowed in SECTION_ORDER:
        if normalized.lower() == allowed.lower():
            return allowed
    return "Discovered durable knowledge"


def _normalize_dates(text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return re.sub(r"(?i)\b(today|yesterday|tomorrow)\b", today, text)


def _ensure_unverified(text: str, reason: str) -> str:
    if "[unverified]" in text.lower():
        return _normalize_dates(text)
    return f"{_normalize_dates(text)} [unverified: {reason}]"


def proposed_memory(memory_text: str, candidates: list[Candidate]) -> str:
    current = memory_text if memory_text.strip() else "# Project memory\n"
    if not current.endswith("\n"):
        current += "\n"
    additions: dict[str, list[str]] = {section: [] for section in SECTION_ORDER}
    for candidate in candidates:
        if candidate.status == "contradicted" or candidate.global_candidate:
            continue
        evidence = f" [{' '.join(candidate.evidence_ids)}]" if candidate.evidence_ids else ""
        additions[candidate.section].append(f"- {candidate.text}{evidence}")

    for section in SECTION_ORDER:
        if additions[section] and f"## {section}" not in current:
            current = current.rstrip() + f"\n\n## {section}\n"

    lines = current.splitlines()
    out: list[str] = []
    for idx, line in enumerate(lines):
        out.append(line)
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if not m:
            continue
        section = _clean_section(m.group(1))
        next_is_content = idx + 1 < len(lines) and lines[idx + 1].strip()
        for item in additions.get(section, []):
            if item not in current:
                if next_is_content and out[-1] != "":
                    pass
                out.append(item)
    return "\n".join(out).rstrip() + "\n"


def _diff_memory(original: str, proposed: str, fromfile: str = "a/MEMORY.md", tofile: str = "b/MEMORY.md") -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )


def proposed_global_memory(memory_text: str, candidates: list[Candidate]) -> str:
    global_candidates = [c for c in candidates if c.global_candidate and c.status != "contradicted"]
    current = memory_text if memory_text.strip() else "# Global memory\n"
    if not current.endswith("\n"):
        current += "\n"
    if not global_candidates:
        return current
    if "## Rules" not in current:
        current += "\n## Rules\n"
    additions = []
    for candidate in global_candidates:
        evidence = f" [{' '.join(candidate.evidence_ids)}]" if candidate.evidence_ids else ""
        item = f"- {candidate.text}{evidence}"
        if item not in current:
            additions.append(item)
    if additions:
        current = current.rstrip() + "\n" + "\n".join(additions) + "\n"
    return current


def write_artifacts(memory_dir: Path, repo_root: Path, trajectory: TrajectoryResult, output: str, candidates: list[Candidate]) -> Path:
    inbox = memory_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    memory_md = memory_dir / "MEMORY.md"
    original = memory_md.read_text(encoding="utf-8") if memory_md.exists() else ""
    proposed = proposed_memory(original, candidates)
    patch = _diff_memory(original, proposed)
    patch_path = inbox / f"memory-md.{stamp}.proposed.patch"
    patch_path.write_text(patch, encoding="utf-8")
    latest_patch_path = inbox / "memory-md.proposed.patch"
    latest_patch_path.write_text(patch, encoding="utf-8")

    cumulative_md_path = inbox / "memory-md.cumulative.proposed.md"
    cumulative_base = cumulative_md_path.read_text(encoding="utf-8") if cumulative_md_path.exists() else original
    cumulative_proposed = proposed_memory(cumulative_base, candidates)
    cumulative_md_path.write_text(cumulative_proposed, encoding="utf-8")
    cumulative_patch_path = inbox / "memory-md.cumulative.proposed.patch"
    cumulative_patch_path.write_text(_diff_memory(original, cumulative_proposed), encoding="utf-8")

    global_patch_path = None
    if any(c.global_candidate and c.status != "contradicted" for c in candidates):
        global_memory = memory_dir.parent / "global" / "MEMORY.md"
        global_original = global_memory.read_text(encoding="utf-8") if global_memory.exists() else ""
        global_proposed = proposed_global_memory(global_original, candidates)
        global_patch = _diff_memory(global_original, global_proposed, fromfile="a/global/MEMORY.md", tofile="b/global/MEMORY.md")
        global_patch_path = inbox / "global-memory.proposed.patch"
        global_patch_path.write_text(global_patch, encoding="utf-8")
    report_path = inbox / f"dream-llm-{stamp}.report.md"
    report_path.write_text(
        render_report(repo_root, trajectory, output, candidates, patch_path, cumulative_patch_path, global_patch_path),
        encoding="utf-8",
    )
    return report_path


def render_report(repo_root: Path, trajectory: TrajectoryResult, output: str, candidates: list[Candidate], patch_path: Path,
                  cumulative_patch_path: Path,
                  global_patch_path: Path | None = None) -> str:
    verified = sum(1 for c in candidates if c.status in {"verified", "repo-verified"})
    unverified = sum(1 for c in candidates if c.status == "unverified")
    contradicted = sum(1 for c in candidates if c.status == "contradicted")
    lines = [
        "# Dream LLM Report",
        "",
        f"- repo_root: `{repo_root}`",
        f"- trajectory_adapter: `{trajectory.adapter}`",
        f"- source_path: `{trajectory.source_path or '(none)'}`",
        f"- evidence_records: {len(trajectory.records)}",
        f"- verified_count: {verified}",
        f"- unverified_count: {unverified}",
        f"- contradicted_stale_count: {contradicted}",
        f"- proposed_patch_paths: `{patch_path}`",
        f"- cumulative_patch_path: `{cumulative_patch_path}`",
        f"- global_patch_path: `{global_patch_path}`" if global_patch_path else "- global_patch_path: `(none)`",
        "",
        "## Candidates",
    ]
    if not candidates:
        lines.append("- No proposed durable memory changes.")
    for candidate in candidates:
        evidence = ", ".join(candidate.evidence_ids) if candidate.evidence_ids else "-"
        scope = "global" if candidate.global_candidate else "project"
        lines.append(f"- status={candidate.status}; scope={scope}; section={candidate.section}; evidence={evidence}; {candidate.text}")
    lines.extend(["", "## LLM Output", "", output or "(empty)"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run review-only LLM memory dream.")
    parser.add_argument("--memory-dir")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--trajectory")
    parser.add_argument("--claude-bin")
    parser.add_argument("--max-days", type=int, default=7)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    args = parser.parse_args(argv)
    if not args.claude_bin:
        print("error: external LLM runner requires --claude-bin. Default /code-dreaming uses the host agent via dream_agent_report.py.", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).expanduser().resolve()
    explicit_memory_dir = bool(args.memory_dir)
    memory_dir = Path(args.memory_dir).expanduser().resolve() if explicit_memory_dir else default_memory_dir(repo_root)
    if not memory_dir.exists():
        if explicit_memory_dir:
            print(f"error: memory dir does not exist: {memory_dir}", file=sys.stderr)
            return 2
        memory_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = dream_prompt_path()
    trajectory = load_trajectory(args.trajectory, memory_dir, repo_root, max_bytes=args.max_bytes)
    prompt = render_prompt(prompt_path, memory_dir, repo_root, trajectory, args.max_days)
    try:
        output = run_llm(args.claude_bin, prompt)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    candidates = parse_candidates(output, trajectory)
    report_path = write_artifacts(memory_dir, repo_root, trajectory, output, candidates)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
