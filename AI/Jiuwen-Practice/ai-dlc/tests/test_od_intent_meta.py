"""od-intent sidecar metadata (PRD v9 P0-A) — tests.

The sidecar is additive (upstream SKILL.md untouched), merged by the
candidate scanner, ignorable via AI_DLC_NO_INTENT_META (the eval A/B's
before-arm), and validated by `design-index metadata-validate`.

Run:  python3 -m pytest tests/test_od_intent_meta.py -v
"""
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

import importlib.util  # noqa: E402


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path: Path) -> Path:
    tdir = tmp_path / "design-templates" / "waitlist-x"
    tdir.mkdir(parents=True)
    (tdir / "SKILL.md").write_text(
        "---\nname: waitlist-x\ndescription: Pre-launch email capture.\n"
        "triggers:\n  - \"waitlist page\"\n  - \"email capture page\"\n"
        "---\nbody\n")
    (tdir / "example.html").write_text("<html></html>")
    return tdir.parent.parent


def _sidecar(tdir: Path, **over):
    meta = {"template": "waitlist-x",
            "intent_page_types": ["waitlist", "landing"],
            "token_family": ["email", "capture"],
            "co_appear": [],
            "locale": ["en"],
            "framework": ["html-css"]}
    meta.update(over)
    (tdir / ".od-intent.json").write_text(json.dumps(meta))


def test_scanner_merges_sidecar(tmp_path):
    root = _tree(tmp_path)
    tdir = root / "design-templates" / "waitlist-x"
    _sidecar(tdir)
    plan = _load("plan_od1", _BIN / "bin" / "plan.py")
    cands = plan._scan_design_candidates(root)
    c = [x for x in cands if x["dir"] == "waitlist-x"][0]
    assert "waitlist" in c["intent_page_types"]
    assert "landing" in c["intent_page_types"]
    assert "email" in c["token_family"]


def test_scanner_without_sidecar_has_no_intent(tmp_path):
    root = _tree(tmp_path)
    plan = _load("plan_od2", _BIN / "bin" / "plan.py")
    cands = plan._scan_design_candidates(root)
    c = [x for x in cands if x["dir"] == "waitlist-x"][0]
    assert not c.get("intent_page_types")


def test_env_flag_ignores_sidecar(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    _sidecar(root / "design-templates" / "waitlist-x")
    monkeypatch.setenv("AI_DLC_NO_INTENT_META", "1")
    plan = _load("plan_od3", _BIN / "bin" / "plan.py")
    cands = plan._scan_design_candidates(root)
    c = [x for x in cands if x["dir"] == "waitlist-x"][0]
    assert not c.get("intent_page_types")


def test_wrong_template_name_sidecar_ignored(tmp_path):
    root = _tree(tmp_path)
    _sidecar(root / "design-templates" / "waitlist-x",
             template="somebody-else")
    plan = _load("plan_od4", _BIN / "bin" / "plan.py")
    cands = plan._scan_design_candidates(root)
    c = [x for x in cands if x["dir"] == "waitlist-x"][0]
    assert not c.get("intent_page_types")


def test_metadata_validate_flags_bad_sidecar(tmp_path, capsys):
    root = _tree(tmp_path)
    tdir = root / "design-templates" / "waitlist-x"
    _sidecar(tdir)
    (tdir / ".od-intent.json").write_text(json.dumps(
        {"template": "waitlist-x", "intent_page_types": "landing"}))
    plan = _load("plan_od5", _BIN / "bin" / "plan.py")
    rc = plan.cmd_design_index(root, "metadata-validate")
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["invalid"] == 1


def test_metadata_validate_passes_good_sidecar(tmp_path, capsys):
    root = _tree(tmp_path)
    _sidecar(root / "design-templates" / "waitlist-x")
    plan = _load("plan_od6", _BIN / "bin" / "plan.py")
    rc = plan.cmd_design_index(root, "metadata-validate")
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["valid"] == 1 and out["invalid"] == 0


def test_filler_derives_from_frontmatter(tmp_path):
    root = _tree(tmp_path)
    fill = _load("fill_od", _BIN / "scripts" / "fill-od-intent.py")
    fm = fill._parse_frontmatter(
        (root / "design-templates" / "waitlist-x" / "SKILL.md")
        .read_text())
    meta = fill.derive(fm, "waitlist-x")
    assert "waitlist" in meta["intent_page_types"]
    assert meta["locale"] == ["en"]
    assert meta["framework"] == ["html-css"]
    assert meta["template"] == "waitlist-x"
