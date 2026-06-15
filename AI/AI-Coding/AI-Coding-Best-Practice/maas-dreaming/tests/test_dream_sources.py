import json
import os
import sqlite3
from pathlib import Path

from scripts.dream_sources import load_trajectory


def test_sqlite_adapter_emits_stable_bounded_redacted_evidence(tmp_path):
    db = tmp_path / "mimocode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE session (id TEXT, directory TEXT)")
    conn.execute("CREATE TABLE message (id TEXT, session_id TEXT, time_created TEXT, data TEXT)")
    conn.execute("CREATE TABLE part (id TEXT, message_id TEXT, session_id TEXT, time_created TEXT, data TEXT)")
    conn.execute("INSERT INTO session VALUES (?, ?)", ("ses_1", str(tmp_path)))
    conn.execute("INSERT INTO message VALUES (?, ?, ?, ?)", ("msg_1", "ses_1", "2026-06-14T01:00:00Z", json.dumps({"role": "assistant"})))
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
        ("part_1", "msg_1", "ses_1", "2026-06-14T01:00:01Z", json.dumps({"type": "text", "text": f"Use {tmp_path}/app.py with token=sk-abcdefghijklmnopqrstuvwxyz"})),
    )
    conn.commit()
    conn.close()

    result = load_trajectory(db, repo_root=tmp_path, preview_chars=80)

    assert result.adapter == "sqlite"
    assert not result.no_trajectory
    assert len(result.records) == 1
    record = result.records[0]
    assert record.evidence_id.startswith("ev-")
    assert record.role == "assistant"
    assert record.project_match is True
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in record.preview
    assert "[REDACTED]" in record.preview
    assert len(record.preview) <= 80


def test_jsonl_adapter_tolerates_common_fields_and_redacts(tmp_path):
    src = tmp_path / "transcript.jsonl"
    src.write_text(
        "\n".join(
            [
                json.dumps({"session_id": "s1", "time": "2026-06-14", "role": "user", "text": "remember this workflow"}),
                json.dumps({"session_id": "s1", "tool": "bash", "input": "Authorization: Bearer abcdefghijklmnop"}),
            ]
        ),
        encoding="utf-8",
    )

    result = load_trajectory(src, repo_root=tmp_path)

    assert result.adapter == "jsonl"
    assert [r.role for r in result.records] == ["user", ""]
    assert result.records[1].tool == "bash"
    assert "Bearer abcdefghijklmnop" not in result.records[1].preview


def test_markdown_adapter_splits_transcript(tmp_path):
    src = tmp_path / "trajectory.md"
    src.write_text("# Session one\nUser: decide A\n## Tool\nOutput B\n", encoding="utf-8")

    result = load_trajectory(src, repo_root=tmp_path)

    assert result.adapter == "markdown"
    assert len(result.records) == 2
    assert result.records[0].role == "transcript"
    assert "Session one" in result.records[0].preview


def test_missing_source_returns_typed_no_trajectory(tmp_path):
    result = load_trajectory(tmp_path / "missing.jsonl", memory_dir=tmp_path, repo_root=tmp_path)

    assert result.no_trajectory is True
    assert result.adapter == "none"
    assert "missing" in result.reason


def test_discovery_returns_no_trajectory_for_unknown_layout(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()

    result = load_trajectory(memory_dir=memory, repo_root=tmp_path)

    assert result.no_trajectory is True
    assert result.records == []


def test_discovery_finds_latest_claude_uuid_jsonl_for_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "workspace" / "maas-dreaming"
    repo.mkdir(parents=True)
    key = "-" + "-".join(part for part in repo.resolve().parts if part != "/")
    project_dir = tmp_path / ".claude" / "projects" / key
    project_dir.mkdir(parents=True)
    older = project_dir / "11111111-1111-1111-1111-111111111111.jsonl"
    newer = project_dir / "22222222-2222-2222-2222-222222222222.jsonl"
    older.write_text(json.dumps({"session_id": "old", "role": "user", "text": "old session"}) + "\n", encoding="utf-8")
    newer.write_text(json.dumps({"session_id": "new", "role": "user", "text": "new session"}) + "\n", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    result = load_trajectory(memory_dir=tmp_path / "missing-memory", repo_root=repo)

    assert result.adapter == "jsonl"
    assert result.source_path == str(newer)
    assert result.records[0].preview == "new session"
