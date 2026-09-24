"""design-auto-inwork-key — tests.

The designed_in_work short-circuit must read the selection schema the
select/pick flows actually write (chosen/skill_name — the panama-v2
finding: the old `skill` key matched neither and deliver re-ran the
whole design pipeline over committed artifacts), and a completed D1
(design_spec.all_written) short-circuits on its own.

Run:  python3 -m pytest tests/test_design_auto_inwork.py -v
"""
import importlib.util
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


report = _load("report_dai", _BIN / "bin" / "report.py")


def _rig(tmp_path, selection=None, design_spec=None, record_key="c1"):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "index.html").write_text("x" * 300, encoding="utf-8")
    state = {"change_id": record_key}
    if selection is not None:
        state["design_selection"] = selection
    if design_spec is not None:
        state["design_spec"] = design_spec
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    (td / "planning.json").write_text("{}")
    return repo, td, state


def test_select_schema_chosen_short_circuits(tmp_path):
    """The schema cmd_design_select writes ({chosen, skill_name}) must
    count as designed_in_work — the old `skill` key missed it and
    deliver re-dispatched the whole pipeline (panama-v2)."""
    repo, td, state = _rig(
        tmp_path,
        selection={"chosen": "/od/tpl/SKILL.md",
                   "skill_name": "tpl", "skill_sha256": "x"})
    due, why = report.design_auto_due(td, repo, state,
                                      ["index.html"], False)
    assert not due and why == "designed_in_work", (due, why)


def test_completed_d1_short_circuits(tmp_path):
    repo, td, state = _rig(
        tmp_path,
        selection={"chosen": "/od/tpl/SKILL.md"},
        design_spec={"all_written": True, "artifacts": {}})
    due, why = report.design_auto_due(td, repo, state,
                                      ["index.html"], False)
    assert not due and why == "designed_in_work", (due, why)


def test_no_design_no_selection_stays_due(tmp_path):
    repo, td, state = _rig(tmp_path)
    due, why = report.design_auto_due(td, repo, state,
                                      ["index.html"], False)
    assert due and why == "due", (due, why)


def test_selection_without_surface_content_falls_through(tmp_path):
    """A selection whose surface files are missing/thin is not
    in-work — the retrofit path stays available (A2's original intent,
    minus the schema miss)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "index.html").write_text("x", encoding="utf-8")  # thin
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    (td / "planning.json").write_text("{}")
    state = {"change_id": "c1",
             "design_selection": {"chosen": "/od/tpl/SKILL.md"},
             "design_spec": {"all_written": False}}
    due, why = report.design_auto_due(td, repo, state,
                                      ["index.html"], False)
    assert due and why == "due", (due, why)
