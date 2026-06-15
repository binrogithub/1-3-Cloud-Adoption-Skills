"""Write verified dream candidates into Mem0 with audit logging."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from mce.backbone import Backbone, PrivacyError, Scope
from mce.policy import WritebackCandidate, WritebackDecision, decide_writeback


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
CANDIDATE_RE = re.compile(
    r"^-\s+status=(?P<status>[^;]+);\s+scope=(?P<scope>[^;]+);\s+section=(?P<section>[^;]+);\s+evidence=(?P<evidence>[^;]+);\s+(?P<text>.+)$"
)
EV_RE = re.compile(r"\bev-[A-Za-z0-9]+\b")


@dataclass(frozen=True)
class WritebackSummary:
    audit_path: str
    mode: str
    candidates: int
    written: int
    skipped: int
    errors: int


def parse_report_candidates(path: Path) -> list[WritebackCandidate]:
    candidates: list[WritebackCandidate] = []
    if not path.exists():
        return candidates
    in_candidates = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "## Candidates":
            in_candidates = True
            continue
        if in_candidates and line.startswith("## "):
            break
        if not in_candidates:
            continue
        m = CANDIDATE_RE.match(line)
        if not m:
            continue
        evidence_blob = m.group("evidence")
        evidence_ids = tuple(EV_RE.findall(evidence_blob))
        candidates.append(
            WritebackCandidate(
                section=m.group("section").strip(),
                text=m.group("text").strip(),
                status=m.group("status").strip(),
                evidence_ids=evidence_ids,
                scope_kind=m.group("scope").strip(),
                source_path=str(path),
            )
        )
    return candidates


def parse_cumulative_memory(path: Path) -> list[WritebackCandidate]:
    candidates: list[WritebackCandidate] = []
    if not path.exists():
        return candidates
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        sm = SECTION_RE.match(line)
        if sm:
            section = sm.group(1).strip()
            continue
        if not section or not line.startswith("- "):
            continue
        text = line[2:].strip()
        evidence_ids = tuple(EV_RE.findall(text))
        status = "verified" if evidence_ids else "unverified"
        candidates.append(
            WritebackCandidate(
                section=section,
                text=text,
                status=status,
                evidence_ids=evidence_ids,
                source_path=str(path),
            )
        )
    return candidates


def latest_report(memory_dir: Path) -> Path | None:
    reports = sorted((memory_dir / "inbox").glob("dream-llm-*.report.md"))
    return reports[-1] if reports else None


def load_candidates(memory_dir: Path, source: Path | None = None) -> list[WritebackCandidate]:
    if source:
        if source.name.endswith(".report.md"):
            return parse_report_candidates(source)
        return parse_cumulative_memory(source)
    cumulative = memory_dir / "inbox" / "memory-md.cumulative.proposed.md"
    candidates = parse_cumulative_memory(cumulative)
    if candidates:
        return candidates
    report = latest_report(memory_dir)
    return parse_report_candidates(report) if report else []


def load_written_hashes(inbox: Path) -> set[str]:
    hashes: set[str] = set()
    for path in sorted(inbox.glob("writeback-*.jsonl")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if row.get("action") == "written" and row.get("candidate_hash"):
                hashes.add(str(row["candidate_hash"]))
    return hashes


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _decision_row(decision: WritebackDecision, *, mode: str, action: str, result=None, error: str = "") -> dict:
    row = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "action": action,
        "reason": decision.reason,
        "candidate_hash": decision.candidate_hash,
        "candidate": asdict(decision.candidate),
        "metadata": decision.metadata,
    }
    if result is not None:
        row["result"] = result
    if error:
        row["error"] = error
    return row


def writeback_candidates(
    candidates: Iterable[WritebackCandidate],
    *,
    memory_dir: Path,
    repo_root: Path,
    scope: Scope,
    mode: str = "review",
    config_path: Path | None = None,
    allow_global: bool = False,
    backbone: Backbone | None = None,
) -> WritebackSummary:
    if mode not in {"review", "apply"}:
        raise ValueError("mode must be review or apply")
    inbox = memory_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    audit_path = inbox / f"writeback-{_stamp()}.jsonl"
    seen_hashes = load_written_hashes(inbox)
    bb = backbone
    written = skipped = errors = total = 0

    with audit_path.open("w", encoding="utf-8") as audit:
        for candidate in candidates:
            total += 1
            decision = decide_writeback(candidate, scope, seen_hashes, allow_global=allow_global)
            metadata = dict(decision.metadata)
            metadata["repo_root"] = str(repo_root)
            decision = WritebackDecision(
                decision.candidate,
                decision.allowed,
                decision.action,
                decision.reason,
                decision.candidate_hash,
                metadata,
            )
            if not decision.allowed:
                skipped += 1
                audit.write(json.dumps(_decision_row(decision, mode=mode, action="skipped"), ensure_ascii=False) + "\n")
                continue
            if mode == "review":
                audit.write(json.dumps(_decision_row(decision, mode=mode, action="would_write"), ensure_ascii=False) + "\n")
                continue
            if bb is None:
                if config_path is None:
                    raise ValueError("config_path is required for apply mode when backbone is not injected")
                bb = Backbone.from_config(str(config_path))
            try:
                result = bb.capture(candidate.text, scope=scope, **metadata)
            except PrivacyError as exc:
                skipped += 1
                audit.write(json.dumps(_decision_row(decision, mode=mode, action="skipped", error=str(exc)), ensure_ascii=False) + "\n")
                continue
            except Exception as exc:  # pragma: no cover - defensive for real Mem0 backends
                errors += 1
                audit.write(json.dumps(_decision_row(decision, mode=mode, action="error", error=str(exc)), ensure_ascii=False) + "\n")
                continue
            written += 1
            seen_hashes.add(decision.candidate_hash)
            audit.write(json.dumps(_decision_row(decision, mode=mode, action="written", result=result), ensure_ascii=False) + "\n")

    return WritebackSummary(str(audit_path), mode, total, written, skipped, errors)


def writeback_from_memory(
    *,
    memory_dir: Path,
    repo_root: Path,
    scope: Scope,
    mode: str = "review",
    source: Path | None = None,
    config_path: Path | None = None,
    allow_global: bool = False,
    backbone: Backbone | None = None,
) -> WritebackSummary:
    candidates = load_candidates(memory_dir, source)
    return writeback_candidates(
        candidates,
        memory_dir=memory_dir,
        repo_root=repo_root,
        scope=scope,
        mode=mode,
        config_path=config_path,
        allow_global=allow_global,
        backbone=backbone,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Write verified dream candidates into Mem0 with audit logging.")
    p.add_argument("--memory-dir", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--org", required=True)
    p.add_argument("--app", default="")
    p.add_argument("--user", default="")
    p.add_argument("--run", default="")
    p.add_argument("--mode", choices=["review", "apply"], default="review")
    p.add_argument("--source", help="Optional dream report or cumulative proposed memory path.")
    p.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "assets" / "mem0.config.yaml"))
    p.add_argument("--allow-global", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = writeback_from_memory(
        memory_dir=Path(args.memory_dir),
        repo_root=Path(args.repo_root),
        scope=Scope(org=args.org, app=args.app, user=args.user, run=args.run),
        mode=args.mode,
        source=Path(args.source) if args.source else None,
        config_path=Path(args.config),
        allow_global=args.allow_global,
    )
    print(json.dumps(asdict(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

