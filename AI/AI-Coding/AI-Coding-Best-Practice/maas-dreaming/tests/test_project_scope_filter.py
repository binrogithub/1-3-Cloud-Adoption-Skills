import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dream  # noqa: E402
from project_scope import claude_project_key, project_scope, memory_matches_project  # noqa: E402


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# maas-dreaming\n", encoding="utf-8")
    (path / "SKILL.md").write_text("---\nname: maas-dreaming\n---\n", encoding="utf-8")
    (path / "pyproject.toml").write_text('[project]\nname = "maas-dreaming"\n', encoding="utf-8")
    return path


def _native_memory(home: Path, owner: Path) -> Path:
    memory = home / ".claude" / "projects" / claude_project_key(owner) / "memory"
    memory.mkdir(parents=True)
    return memory


def test_project_scope_matches_repo_identity(tmp_path):
    repo = _repo(tmp_path / "maas-dreaming")
    scope = project_scope(repo)

    assert memory_matches_project("Notes about maas-dreaming skill behavior", scope)
    assert not memory_matches_project("Notes about claude-code-huawei-maas production state", scope)


def test_dream_auto_skips_parent_workspace_foreign_memory(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    (memory / "claude-glm-production-state.md").write_text(
        "# claude-glm production state\n\nclaude-code-huawei-maas deployment chain.\n",
        encoding="utf-8",
    )

    rc = dream.main(["--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "scope filter     : auto (on)" in out
    assert "out-of-scope skipped: 1" in out
    assert "kept (-> index)  : 0" in out
    assert "[OUT-OF-SCOPE] claude-glm-production-state.md" in out


def test_dream_scope_filter_off_preserves_parent_workspace_behavior(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    (memory / "claude-glm-production-state.md").write_text(
        "# claude-glm production state\n\nclaude-code-huawei-maas deployment chain.\n",
        encoding="utf-8",
    )

    rc = dream.main(["--repo-root", str(repo), "--scope-filter", "off"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "scope filter     : off (off)" in out
    assert "out-of-scope skipped: 0" in out
    assert "kept (-> index)  : 1" in out


def test_dream_explicit_memory_dir_does_not_filter_by_default(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = tmp_path / "explicit-memory"
    memory.mkdir()
    (memory / "foreign.md").write_text("# claude-glm\n\nOther project.\n", encoding="utf-8")

    rc = dream.main(["--memory-dir", str(memory), "--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "scope filter     : auto (off)" in out
    assert "out-of-scope skipped: 0" in out
    assert "kept (-> index)  : 1" in out


def test_dream_explicit_parent_native_memory_still_filters_auto(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    (memory / "claude-glm-production-state.md").write_text(
        "# claude-glm production state\n\nclaude-code-huawei-maas deployment chain.\n",
        encoding="utf-8",
    )

    rc = dream.main(["--memory-dir", str(memory), "--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "scope filter     : auto (on)" in out
    assert "out-of-scope skipped: 1" in out
    assert "kept (-> index)  : 0" in out


def test_dream_exact_native_memory_does_not_filter_by_default(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = _native_memory(home, repo)
    (memory / "foreign.md").write_text("# claude-glm\n\nOther project.\n", encoding="utf-8")

    rc = dream.main(["--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "scope filter     : auto (off)" in out
    assert "out-of-scope skipped: 0" in out
    assert "kept (-> index)  : 1" in out
