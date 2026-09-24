"""P1-5 turn checkpoints — tests for the grok-build-ported mechanism.

`git stash create` pins the dirty region without touching the working
tree; the registry lives in the task dir; restore carries a
stash-or-abort guard and never clobbers a dirty tree blind. Ported per
Apache-2.0 §4(b) from xai-org/grok-build session/{checkpoint,git}.rs.

Run:  python3 -m pytest tests/test_checkpoints.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_checkpoints", _BIN / "bin" / "report.py")


def _commit(repo: Path, msg: str, *files: str) -> None:
    for f in files:
        subprocess.run(["git", "-C", str(repo), "add", f], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(repo), "commit", "-q", "-m", msg],
                   check=True)


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    _commit(tmp_path, "base", "a.txt")
    return tmp_path


def _td(repo: Path) -> Path:
    td = repo / ".ai-dlc" / "tasks" / "t12"
    td.mkdir(parents=True, exist_ok=True)
    return td


def test_three_checkpoints_across_turns(tmp_path, capsys):
    repo = _repo(tmp_path)
    td = _td(repo)
    report.cmd_checkpoint(td, repo, "turn one", False, None, None, False)
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    _commit(repo, "turn two", "a.txt")
    report.cmd_checkpoint(td, repo, "turn two", False, None, None, False)
    (repo / "a.txt").write_text("dirty\n", encoding="utf-8")  # uncommitted
    report.cmd_checkpoint(td, repo, "turn three", False, None, None, False)
    capsys.readouterr()
    cps = json.loads((td / "checkpoints.json").read_text(
        encoding="utf-8"))["checkpoints"]
    assert [c["seq"] for c in cps] == [1, 2, 3]
    assert cps[0]["dirty_commit"] is None          # clean tree
    assert cps[2]["dirty_commit"]                  # dirty region pinned
    assert cps[2]["dirty_count"] == 1


def test_dirty_tree_survives_a_checkpoint(tmp_path):
    # `git stash create` records the dirty region WITHOUT stashing it
    repo = _repo(tmp_path)
    td = _td(repo)
    (repo / "a.txt").write_text("dirty\n", encoding="utf-8")
    report.cmd_checkpoint(td, repo, "wip", False, None, None, False)
    assert (repo / "a.txt").read_text(encoding="utf-8") == "dirty\n"
    assert not json.loads(subprocess.run(
        ["git", "-C", str(repo), "stash", "list"],
        capture_output=True, text=True).stdout or "[]")  # nothing stashed


def test_show_diffs_consecutive_checkpoints(tmp_path, capsys):
    repo = _repo(tmp_path)
    td = _td(repo)
    report.cmd_checkpoint(td, repo, "one", False, None, None, False)
    (repo / "b.txt").write_text("new\n", encoding="utf-8")
    _commit(repo, "two", "b.txt")
    report.cmd_checkpoint(td, repo, "two", False, None, None, False)
    capsys.readouterr()
    assert report.cmd_checkpoint(td, repo, None, False, 2, None,
                                 False) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["from_seq"] == 1
    assert any("b.txt" in l for l in out["diff_stat"])


def test_restore_refuses_a_dirty_tree(tmp_path, capsys):
    repo = _repo(tmp_path)
    td = _td(repo)
    report.cmd_checkpoint(td, repo, "one", False, None, None, False)
    (repo / "a.txt").write_text("later work\n", encoding="utf-8")
    _commit(repo, "later", "a.txt")
    (repo / "a.txt").write_text("uncommitted\n", encoding="utf-8")
    rc = report.cmd_checkpoint(td, repo, None, False, None, 1, False)
    assert rc == 1
    err = capsys.readouterr().err
    assert "stash-or-abort" in err or "refuses" in err


def test_restore_with_stash_first_is_recorded(tmp_path, capsys):
    repo = _repo(tmp_path)
    td = _td(repo)
    report.cmd_checkpoint(td, repo, "one", False, None, None, False)
    (repo / "a.txt").write_text("later\n", encoding="utf-8")
    _commit(repo, "later", "a.txt")
    (repo / "a.txt").write_text("uncommitted\n", encoding="utf-8")
    assert report.cmd_checkpoint(td, repo, None, False, None, 1,
                                 True) == 0
    capsys.readouterr()
    assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
    cps = json.loads((td / "checkpoints.json").read_text(
        encoding="utf-8"))["checkpoints"]
    assert cps[0]["restore_stashes"]            # the stash is on record
    stash_list = subprocess.run(
        ["git", "-C", str(repo), "stash", "list"],
        capture_output=True, text=True).stdout
    assert "pre-restore of checkpoint 1" in stash_list


def test_events_are_written(tmp_path):
    repo = _repo(tmp_path)
    td = _td(repo)
    report.cmd_checkpoint(td, repo, "one", False, None, None, False)
    events = (td / "events.jsonl").read_text(encoding="utf-8")
    assert "CHECKPOINT_RECORDED" in events
