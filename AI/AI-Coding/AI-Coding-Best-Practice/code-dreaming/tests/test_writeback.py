import json
import subprocess
import sys
from pathlib import Path

from mce.backbone import Scope
from mce.executor import run_plan
from mce.writeback import (
    load_candidates,
    parse_cumulative_memory,
    parse_report_candidates,
    writeback_from_memory,
)


ROOT = Path(__file__).resolve().parent.parent


class FakeBackbone:
    def __init__(self):
        self.capture_calls = []

    def capture(self, text, scope, **metadata):
        self.capture_calls.append({"text": text, "scope": scope, "metadata": metadata})
        return {"results": [{"id": f"mem-{len(self.capture_calls)}", "memory": text}]}


def _report(path: Path, lines: list[str]) -> Path:
    body = "\n".join(
        [
            "# Dream LLM Report",
            "",
            "## Candidates",
            *lines,
            "",
            "## LLM Output",
            "",
            "(mock)",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")
    return path


def test_parse_report_candidates_reads_status_scope_section_and_evidence(tmp_path):
    report = _report(
        tmp_path / "dream-llm.report.md",
        ["- status=verified; scope=project; section=Rules; evidence=ev-abc123; Always run pytest."],
    )

    candidates = parse_report_candidates(report)

    assert len(candidates) == 1
    assert candidates[0].status == "verified"
    assert candidates[0].scope_kind == "project"
    assert candidates[0].section == "Rules"
    assert candidates[0].evidence_ids == ("ev-abc123",)
    assert candidates[0].text == "Always run pytest."


def test_parse_cumulative_memory_marks_entries_without_evidence_unverified(tmp_path):
    path = tmp_path / "memory-md.cumulative.proposed.md"
    path.write_text("# Project memory\n\n## Rules\n- With evidence. [ev-abc]\n- Without evidence.\n", encoding="utf-8")

    candidates = parse_cumulative_memory(path)

    assert [c.status for c in candidates] == ["verified", "unverified"]


def test_writeback_review_mode_emits_audit_without_mem0_write(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; Review only writeback candidate."
    ])
    fake = FakeBackbone()

    summary = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme"),
        mode="review",
        source=report,
        backbone=fake,
    )

    assert summary.candidates == 1
    assert summary.written == 0
    assert fake.capture_calls == []
    rows = [json.loads(line) for line in Path(summary.audit_path).read_text(encoding="utf-8").splitlines()]
    assert rows[0]["action"] == "would_write"


def test_writeback_apply_writes_only_verified_candidates_and_audits_skips(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; Verified writeback candidate.",
        "- status=unverified; scope=project; section=Rules; evidence=-; Unverified candidate.",
        "- status=contradicted; scope=project; section=Rules; evidence=ev-2; Contradicted candidate.",
    ])
    fake = FakeBackbone()

    summary = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme", app="gateway"),
        mode="apply",
        source=report,
        backbone=fake,
    )

    assert summary.candidates == 3
    assert summary.written == 1
    assert summary.skipped == 2
    assert fake.capture_calls[0]["text"] == "Verified writeback candidate."
    assert fake.capture_calls[0]["metadata"]["source"] == "dream-writeback"
    assert fake.capture_calls[0]["metadata"]["section"] == "Rules"
    assert fake.capture_calls[0]["metadata"]["repo_root"] == str(tmp_path / "repo")
    rows = [json.loads(line) for line in Path(summary.audit_path).read_text(encoding="utf-8").splitlines()]
    assert [row["action"] for row in rows] == ["written", "skipped", "skipped"]


def test_writeback_apply_skips_duplicate_hash_from_prior_audit(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; Duplicate candidate."
    ])
    fake = FakeBackbone()

    first = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme"),
        mode="apply",
        source=report,
        backbone=fake,
    )
    second = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme"),
        mode="apply",
        source=report,
        backbone=fake,
    )

    assert first.written == 1
    assert second.written == 0
    assert second.skipped == 1
    assert len(fake.capture_calls) == 1


def test_writeback_global_candidate_requires_explicit_allow(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=global; section=Rules; evidence=ev-1; Global candidate."
    ])
    fake = FakeBackbone()

    blocked = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme"),
        mode="apply",
        source=report,
        backbone=fake,
    )
    allowed = writeback_from_memory(
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme", app="allowed"),
        mode="apply",
        source=report,
        allow_global=True,
        backbone=fake,
    )

    assert blocked.written == 0
    assert allowed.written == 1


def test_load_candidates_prefers_cumulative_memory(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; From report."
    ])
    (inbox / "memory-md.cumulative.proposed.md").write_text("# Project memory\n\n## Rules\n- From cumulative. [ev-2]\n", encoding="utf-8")

    candidates = load_candidates(memory)

    assert [c.text for c in candidates] == ["From cumulative. [ev-2]"]


def test_run_plan_delegates_dream_writeback(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; Plan candidate."
    ])
    fake = FakeBackbone()

    summary = run_plan(
        "dream-writeback",
        memory_dir=memory,
        repo_root=tmp_path / "repo",
        scope=Scope(org="acme"),
        mode="apply",
        source=report,
        backbone=fake,
    )

    assert summary.plan == "dream-writeback"
    assert summary.writeback["written"] == 1
    assert fake.capture_calls[0]["text"] == "Plan candidate."


def test_cli_writeback_review_smoke(tmp_path):
    memory = tmp_path / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True)
    report = _report(inbox / "dream-llm-1.report.md", [
        "- status=verified; scope=project; section=Rules; evidence=ev-1; CLI review candidate."
    ])

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mce.cli",
            "writeback",
            "--memory-dir",
            str(memory),
            "--repo-root",
            str(tmp_path / "repo"),
            "--org",
            "acme",
            "--source",
            str(report),
            "--mode",
            "review",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["mode"] == "review"
    assert payload["candidates"] == 1
    rows = [json.loads(line) for line in Path(payload["audit_path"]).read_text(encoding="utf-8").splitlines()]
    assert rows[0]["action"] == "would_write"

