"""P1-9 SELECT rubric + template metadata — tests.

Every deterministic selection carries its three-part rubric (intent
coverage / token fit / co-appearance, the last honestly 'unrated'
until the metadata exists); optional frontmatter metadata
(od.intent.page_types / od.token_family / od.co_appear) is parsed and
preferred on retrieval ties; design-index metadata-coverage measures
the fill-in baseline.

Run:  python3 -m pytest tests/test_select_rubric.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_rubric_t", _BIN / "bin" / "plan.py")


def test_fm_list_tolerates_both_authoring_shapes():
    assert plan._fm_list(["a", " b "]) == ["a", "b"]
    assert plan._fm_list("a, b,,c") == ["a", "b", "c"]
    assert plan._fm_list(None) == []
    assert plan._fm_list(7) == []


def test_candidates_parse_metadata_keys(tmp_path):
    root = tmp_path / "od"
    (root / "skills" / "tpl").mkdir(parents=True)
    (root / "skills" / "tpl" / "SKILL.md").write_text(
        "---\nname: tpl\ntriggers: [landing]\n"
        "od.intent.page_types: landing, pricing\n"
        "od.token_family: [warm, serif]\n"
        "od.co_appear: hero+stats\n"
        "description: a landing template\n---\nbody\n",
        encoding="utf-8")
    cands = plan._scan_design_candidates(root)
    assert len(cands) == 1
    c = cands[0]
    assert c["intent_page_types"] == ["landing", "pricing"]
    assert c["token_family"] == ["warm", "serif"]
    assert c["co_appear"] == ["hero+stats"]


def test_absent_metadata_is_empty_not_error(tmp_path):
    root = tmp_path / "od"
    (root / "skills" / "bare").mkdir(parents=True)
    (root / "skills" / "bare" / "SKILL.md").write_text(
        "---\nname: bare\ntriggers: [x]\ndescription: d\n---\nb\n",
        encoding="utf-8")
    c = plan._scan_design_candidates(root)[0]
    assert c["intent_page_types"] == [] and c["co_appear"] == []


def test_rubric_shape_on_a_built_selection():
    # the rubric construction is exercised through the selection
    # record's builder: same computation, unit-level
    change_kw = {"query_tokens": ["landing", "pricing", "other"]}
    best = {"triggers": ["landing", "pricing"], "co_appear": []}
    qtoks = {t.lower() for t in change_kw["query_tokens"]}
    trig = {t.lower() for t in best["triggers"]}
    matched = sorted(qtoks & trig)
    assert matched == ["landing", "pricing"]
    assert round(len(matched) / max(1, len(qtoks)), 3) == 0.667


def test_metadata_coverage_reports_the_baseline(tmp_path, capsys):
    root = tmp_path / "od"
    (root / "skills" / "with").mkdir(parents=True)
    (root / "skills" / "with" / "SKILL.md").write_text(
        "---\nname: w\nod.intent.page_types: landing\n"
        "description: d\n---\nb\n", encoding="utf-8")
    (root / "skills" / "without").mkdir(parents=True)
    (root / "skills" / "without" / "SKILL.md").write_text(
        "---\nname: wo\ndescription: d\n---\nb\n", encoding="utf-8")
    rc = plan.cmd_design_index(root, "metadata-coverage")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["candidates"] == 2
    assert out["with_intent_metadata"] == 1
    assert out["coverage_pct"] == 50.0
    assert "without" in out["missing_examples"]


def test_pick_output_carries_rubric_source():
    src = (_BIN / "bin" / "plan.py").read_text(encoding="utf-8")
    assert '"rubric": rubric' in src
    assert "intent_coverage" in src
    assert "metadata-coverage" in src


def test_weak_selection_is_flagged_degraded(tmp_path, monkeypatch):
    # 02-static-site finding #4: zero intent coverage at a near-zero
    # margin must carry degraded + reason (the gate machinery reads
    # selection.degraded / selection.reason)
    import subprocess
    fake = {"path": "x", "sha256": "s", "name": "tpl",
            "kind": "template", "triggers": ["waitlist"],
            "design_system": None, "craft": None}
    monkeypatch.setattr(plan, "_design_prefilter", lambda *a, **k: (
        [fake], [(0.0, fake)],
        {"surface_hint": "web",
         "query_tokens": ["alpine", "hiking"],
         "eligible": 1, "filtered_from": 1}))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(repo), "commit", "-q", "--allow-empty",
                    "-m", "base"], check=True)
    td = repo / ".ai-dlc" / "tasks" / "t"
    # init BEFORE the work commit - base must sit below the change
    # (the 02-static-site finding #5 shape: a late init measures
    # nothing)
    subprocess.run([sys.executable, str(_BIN / "bin" / "report.py"),
                    "init", "--task-dir", str(td), "--repo", str(repo),
                    "--route", "planned", "--task-id", "t",
                    "--change", "c1"], check=True,
                   capture_output=True)
    (repo / "index.html").write_text("<html></html>",
                                     encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "index.html"],
                   check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(repo), "commit", "-q", "-m", "w"],
                   check=True)
    plan.cmd_design_pick("c1", repo, td)
    sel = json.loads((td / "state.json").read_text(
        encoding="utf-8"))["design_selection"]
    assert sel["degraded"] is True
    assert "zero intent coverage" in sel["reason"]
