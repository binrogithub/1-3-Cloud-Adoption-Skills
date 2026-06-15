from pathlib import Path

from scripts.dream_sources import load_trajectory
from scripts.scan_to_dream import build_manifest, render_dream_source, scan_directory


def test_scan_directory_writes_redacted_bounded_dream_source(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("token=sk-abcdefghijklmnopqrstuvwxyz\nprint('ok')\n", encoding="utf-8")
    (root / "big.md").write_text("x" * 100, encoding="utf-8")
    (root / "vendor").mkdir()
    (root / "vendor" / "ignored.py").write_text("do not include", encoding="utf-8")
    (root / ".hidden").write_text("hide me", encoding="utf-8")

    result = scan_directory(root, max_file_bytes=12, max_total_bytes=80)
    output = render_dream_source(root, result)

    assert "Directory Dream Source" in output
    assert "app.py" in output
    assert "big.md" in output
    assert "vendor/ignored.py" not in output
    assert "skipped_dirs: vendor" in output
    assert ".hidden" not in output
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in output
    assert "[REDACTED]" in output
    assert "truncated: true" in output


def test_generated_dream_source_is_markdown_trajectory(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Rule\nAlways run tests.\n", encoding="utf-8")
    out = tmp_path / "dream-source.md"

    result = scan_directory(root)
    out.write_text(render_dream_source(root, result), encoding="utf-8")
    result = load_trajectory(out, repo_root=root)

    assert result.adapter == "markdown"
    assert not result.no_trajectory
    assert any("Always run tests" in record.preview for record in result.records)


def test_delta_scan_outputs_only_changes_but_manifest_keeps_all_current_files(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "same.md").write_text("same\n", encoding="utf-8")
    (root / "changed.md").write_text("before\n", encoding="utf-8")
    (root / "deleted.md").write_text("gone\n", encoding="utf-8")

    first = scan_directory(root)
    manifest = build_manifest(root, first)

    (root / "changed.md").write_text("after\n", encoding="utf-8")
    (root / "added.md").write_text("new\n", encoding="utf-8")
    (root / "deleted.md").unlink()

    second = scan_directory(root, since_manifest=manifest)
    output = render_dream_source(root, second)
    next_manifest = build_manifest(root, second)

    assert second.mode == "delta"
    assert second.added == 1
    assert second.changed == 1
    assert second.deleted == ["deleted.md"]
    assert second.unchanged == 1
    assert "## File: added.md" in output
    assert "- status: added" in output
    assert "## File: changed.md" in output
    assert "- status: changed" in output
    assert "## File: same.md" not in output
    assert "- deleted.md" in output
    assert set(next_manifest["files"]) == {"same.md", "changed.md", "added.md"}
