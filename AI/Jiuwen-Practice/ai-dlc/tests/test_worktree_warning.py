"""Finding #2 (AB-lab E2E, 2026-09-08): the plane keys specs trees,
records and task state by the exact repo path — init on the main
checkout while working in a linked worktree stranded work twice
(colombia, AB-lab). init now states the contract when --repo is a
linked worktree.

Run:  python3 -m pytest tests/test_worktree_warning.py -v
"""
import importlib.util
import json
import subprocess
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_wt_warn_t", _BIN / "bin" / "report.py")


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    return tmp_path


def test_main_checkout_gets_no_warning(tmp_path, capsys):
    repo = _repo(tmp_path)
    td = tmp_path / ".ai-dlc" / "tasks" / "w1"
    assert report.cmd_init(td, repo, "inline", "w1", None) == 0
    capsys.readouterr()
    st = json.loads((td / "state.json").read_text(encoding="utf-8"))
    assert "repo_identity_note" not in st


def test_linked_worktree_gets_the_warning(tmp_path, capsys):
    repo = _repo(tmp_path)
    wt = tmp_path.parent / (tmp_path.name + "-wt")
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q",
                    str(wt), "-b", "task/w"], check=True)
    td = tmp_path / ".ai-dlc" / "tasks" / "w2"
    assert report.cmd_init(td, wt, "inline", "w2", None) == 0
    out = json.loads(capsys.readouterr().out)
    assert "repo_identity_warning" in out
    assert "linked worktree" in out["repo_identity_warning"]
    assert str(wt) in out["repo_identity_warning"]
    st = json.loads((td / "state.json").read_text(encoding="utf-8"))
    assert "repo_identity_note" in st
    subprocess.run(["git", "-C", str(repo), "worktree", "remove",
                    "--force", str(wt)], check=True)


def test_init_on_the_task_branch_warns_about_base(tmp_path, capsys):
    # 02-static-site finding #5: init after committing on the task
    # branch measures nothing (base==head)
    import subprocess
    repo = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q",
                    "-b", "task/late"], check=True)
    (repo / "a.txt").write_text("work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(repo), "commit", "-q", "-m", "w"],
                   check=True)
    td = tmp_path / ".ai-dlc" / "tasks" / "late"
    report.cmd_init(td, repo, "planned", "late", "late")
    out = json.loads(capsys.readouterr().out)
    assert "base_warning" in out
    assert "measures nothing" in out["base_warning"]


def test_session_scaffolding_is_excluded(tmp_path):
    # 02-static-site finding #6
    assert report.excluded(".agent_history/x.jsonl")
    assert report.excluded("coding_memory/mem.json")
    assert report.excluded("prompt_attachment/README.md")
    assert not report.excluded("style.css")
