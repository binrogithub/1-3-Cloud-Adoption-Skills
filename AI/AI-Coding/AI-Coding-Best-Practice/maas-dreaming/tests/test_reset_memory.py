import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import reset_memory  # noqa: E402
from project_scope import claude_project_key, native_memory_dir_for, resolve_native_memory  # noqa: E402


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# maas-dreaming\n", encoding="utf-8")
    return path


def _native_memory(home: Path, owner: Path) -> Path:
    memory = home / ".claude" / "projects" / claude_project_key(owner) / "memory"
    memory.mkdir(parents=True)
    return memory


def _seed_memory(memory: Path) -> None:
    (memory / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (memory / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (memory / "local.sqlite").write_text("sqlite", encoding="utf-8")
    (memory / "episodic").mkdir()
    (memory / "episodic" / "one.md").write_text("# One\n", encoding="utf-8")
    (memory / "semantic").mkdir()
    (memory / "semantic" / "dream-index.md").write_text("# Index\n", encoding="utf-8")
    (memory / "inbox").mkdir()
    (memory / "inbox" / "candidate.md").write_text("# Candidate\n", encoding="utf-8")
    (memory / "working").mkdir()
    (memory / "working" / "session.md").write_text("# Session\n", encoding="utf-8")


def test_exact_native_dry_run_does_not_delete(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = _native_memory(home, repo)
    _seed_memory(memory)

    rc = reset_memory.main(["--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "# reset-memory — DRY RUN" in out
    assert "memory relation  : exact-native" in out
    assert "targets          : 7" in out
    assert (memory / "MEMORY.md").exists()
    assert (memory / "episodic" / "one.md").exists()


def test_exact_native_apply_backs_up_and_deletes_targets(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = _native_memory(home, repo)
    _seed_memory(memory)
    backup = tmp_path / "backup"

    rc = reset_memory.main([
        "--repo-root",
        str(repo),
        "--backup-dir",
        str(backup),
        "--apply",
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "# reset-memory — APPLY" in out
    assert "backed up and removed 7 target(s)" in out
    assert not (memory / "MEMORY.md").exists()
    assert not (memory / "episodic").exists()
    assert (backup / "MEMORY.md").read_text(encoding="utf-8") == "# Memory\n"
    assert (backup / "episodic" / "one.md").read_text(encoding="utf-8") == "# One\n"


def test_parent_native_memory_refuses_without_allow_parent(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    _seed_memory(memory)

    rc = reset_memory.main(["--repo-root", str(repo)])

    assert rc == 2
    err = capsys.readouterr().err
    assert "refusing to clear inherited parent native memory" in err
    assert (memory / "MEMORY.md").exists()


def test_parent_native_memory_can_apply_with_allow_parent(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    _seed_memory(memory)
    backup = tmp_path / "backup"

    rc = reset_memory.main([
        "--repo-root",
        str(repo),
        "--backup-dir",
        str(backup),
        "--allow-parent",
        "--apply",
    ])

    assert rc == 0
    assert not (memory / "MEMORY.md").exists()
    assert (backup / "MEMORY.md").exists()
    exact = native_memory_dir_for(repo)
    assert exact.exists()
    resolved = resolve_native_memory(repo)
    assert resolved.exact is True
    assert resolved.memory_dir == exact


def test_parent_native_memory_can_apply_without_initializing_exact(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    repo = _repo(workspace / "AI" / "maas-dreaming")
    memory = _native_memory(home, workspace)
    _seed_memory(memory)
    backup = tmp_path / "backup"

    rc = reset_memory.main([
        "--repo-root",
        str(repo),
        "--backup-dir",
        str(backup),
        "--allow-parent",
        "--no-init-exact",
        "--apply",
    ])

    assert rc == 0
    assert not native_memory_dir_for(repo).exists()


def test_explicit_non_native_memory_can_be_cleared(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = tmp_path / "explicit-memory"
    memory.mkdir()
    _seed_memory(memory)
    backup = tmp_path / "backup"

    rc = reset_memory.main([
        "--repo-root",
        str(repo),
        "--memory-dir",
        str(memory),
        "--backup-dir",
        str(backup),
        "--apply",
    ])

    assert rc == 0
    assert not (memory / "semantic").exists()
    assert (backup / "semantic" / "dream-index.md").exists()


def test_backup_directory_inside_memory_is_rejected(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    memory = _native_memory(home, repo)
    _seed_memory(memory)

    rc = reset_memory.main([
        "--repo-root",
        str(repo),
        "--backup-dir",
        str(memory / ".reset-backups" / "now"),
        "--apply",
    ])

    assert rc == 2
    assert "backup directory must be outside" in capsys.readouterr().err
    assert (memory / "MEMORY.md").exists()


def test_missing_exact_native_memory_is_noop_and_can_initialize(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path / "repo" / "maas-dreaming")
    exact = native_memory_dir_for(repo)

    dry_rc = reset_memory.main(["--repo-root", str(repo)])
    assert dry_rc == 0
    assert "nothing to clear" in capsys.readouterr().out
    assert not exact.exists()

    apply_rc = reset_memory.main(["--repo-root", str(repo), "--apply"])
    assert apply_rc == 0
    out = capsys.readouterr().out
    assert "no memory artifacts to remove" in out
    assert "initialized exact memory root" in out
    assert exact.exists()
