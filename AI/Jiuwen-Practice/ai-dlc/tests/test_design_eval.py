"""P1-C: offline design-selection eval (tests a).

run_design_eval ranks the fixture pool deterministically and reports
hit@1/@3 against golden; results land in evals/results/.

Run:  python3 -m pytest tests/test_design_eval.py -v
"""
import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "od" / "design-templates"
    root.mkdir(parents=True)
    for name, desc, sidecar in (
            ("blog-x", "Long form articles",
             '{"template": "blog-x", "intent_page_types": ["blog"],'
             ' "token_family": ["article"], "locale": ["en"],'
             ' "framework": ["html-css"], "co_appear": []}'),
            ("docs-y", "Documentation for developers", None),
            ("pricing-z", "Pricing table", None)):
        d = root / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\n---\nbody\n")
        if sidecar:
            (d / ".od-intent.json").write_text(sidecar)
    setp = tmp_path / "set.json"
    setp.write_text(json.dumps({"queries": [
        {"q": "blog articles", "golden": "blog-x"},
        {"q": "documentation developers", "golden": "docs-y"},
        {"q": "pricing table", "golden": "pricing-z"}]}))
    return root.parent, setp


def test_design_eval_reports_hits(tmp_path, capsys, monkeypatch):
    od_root, setp = _fixture(tmp_path)
    ev = _load("eval_d1", _BIN / "bin" / "eval.py")
    monkeypatch.setattr(ev, "DESIGN_SET_PATH", setp)
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path / "results")
    rc = ev.run_design_eval(od_root)
    assert rc == 0
    out = json.loads(capsys.readouterr().out.split("\nresults:")[0])
    assert out["queries"] == 3
    assert out["hit@1"] == 1.0 and out["hit@3"] == 1.0
