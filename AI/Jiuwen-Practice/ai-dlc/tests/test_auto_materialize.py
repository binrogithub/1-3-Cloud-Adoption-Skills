"""design-auto-materialize — tests.

The v2 umbrella materializes the chosen template between D0 SELECT and
D1 SPECIFY, so the asset-forward material note is the default for
every design flow; templates without material or already-standing
material are not errors.

Run:  python3 -m pytest tests/test_auto_materialize.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_am", _BIN / "bin" / "plan.py")


def _rig(tmp_path, monkeypatch, chosen="/od/tpl-x/SKILL.md"):
    calls = []

    def fake_select(change, repo, task_dir, mode="code.normal"):
        calls.append("select")
        d = Path(task_dir)
        d.mkdir(parents=True, exist_ok=True)
        st = json.loads((d / "state.json").read_text())
        if "design_selection" not in st:
            st["design_selection"] = {"chosen": chosen}
            (d / "state.json").write_text(json.dumps(st))
        return 0

    def fake_materialize(change, repo, template, root=None, page=None,
                         max_files=None, max_bytes=None,
                         task_dir=None):
        calls.append(f"materialize:{template}")
        return 0

    def fake_specify(change, repo, task_dir, mode="code.normal",
                     timeout=600):
        calls.append("specify")
        return 0

    def fake_verify(change, repo, task_dir):
        calls.append("verify")
        return 0

    monkeypatch.setattr(plan, "cmd_design_select", fake_select)
    monkeypatch.setattr(plan, "cmd_design_materialize", fake_materialize)
    monkeypatch.setattr(plan, "cmd_design_specify", fake_specify)
    monkeypatch.setattr(plan, "cmd_design_verify", fake_verify)

    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    (td / "state.json").write_text("{}")
    return repo, td, calls


def test_umbrella_materializes_between_d0_and_d1(tmp_path,
                                                 monkeypatch):
    repo, td, calls = _rig(tmp_path, monkeypatch,
                           chosen="/od/tpl-x/SKILL.md")
    assert plan.cmd_design("c1", repo, td, None, None,
                           "code.normal", 600) == 0
    assert calls == ["select", "materialize:tpl-x", "specify", "verify"], \
        calls


def test_umbrella_survives_materialless_template(tmp_path, monkeypatch):
    repo, td, calls = _rig(tmp_path, monkeypatch)
    # a refused materialize (no material / already standing) must not
    # break the flow
    def refusing(change, repo, template, root=None, page=None,
                 max_files=None, max_bytes=None, task_dir=None):
        calls.append(f"refused:{template}")
        return plan.EXIT_PACKAGE_INVALID

    monkeypatch.setattr(plan, "cmd_design_materialize", refusing)
    assert plan.cmd_design("c1", repo, td, None, None,
                           "code.normal", 600) == 0
    assert calls == ["select", "refused:tpl-x", "specify", "verify"], calls
