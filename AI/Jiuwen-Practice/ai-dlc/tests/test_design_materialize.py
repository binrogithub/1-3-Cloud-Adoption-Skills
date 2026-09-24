"""D1.5 MATERIALIZE (PRD v9 P1-B) — tests.

The chosen template's assets land in the change's design-material/
with a sha-pinned manifest; a re-run refuses to overwrite standing
material; unknown templates are refused by name.

Run:  python3 -m pytest tests/test_design_materialize.py -v
"""
import importlib.util
import json
import os
from pathlib import Path

import os as _os
_os.environ.setdefault("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/mat-test-specs")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture(tmp_path: Path) -> tuple:
    root = tmp_path / "od"
    tdir = root / "design-templates" / "tpl-x"
    (tdir / "assets").mkdir(parents=True)
    (tdir / "SKILL.md").write_text("---\nname: tpl-x\n---\nbody\n")
    (tdir / "assets" / "template.html").write_text("<html>x</html>")
    (tdir / "example.html").write_text("<html>e</html>")
    repo = tmp_path / "proj"
    repo.mkdir()
    return root, tdir, repo


def test_materialize_copies_with_manifest(tmp_path, capsys):
    root, tdir, repo = _fixture(tmp_path)
    plan = _load("plan_m1", _BIN / "bin" / "plan.py")
    rc = plan.cmd_design_materialize("ch1", repo, "tpl-x", root)
    assert rc == 0
    dest = plan.plane_tree(repo) / "changes" / "ch1" / "design-material"
    got = sorted(p.name for p in dest.rglob("*") if p.is_file())
    assert "manifest.json" in got and "template.html" in got \
        and "example.html" in got
    man = json.loads((dest / "manifest.json").read_text())
    assert man["template"] == "tpl-x"
    assert len(man["files"]) == 2
    assert all(f["sha256"] for f in man["files"])
    assert man["source_skill_sha256"]


def test_materialize_refuses_unknown_template(tmp_path):
    root, tdir, repo = _fixture(tmp_path)
    plan = _load("plan_m2", _BIN / "bin" / "plan.py")
    rc = plan.cmd_design_materialize("ch1", repo, "nope", root)
    assert rc == plan.EXIT_PACKAGE_INVALID


def test_materialize_refuses_overwrite(tmp_path):
    root, tdir, repo = _fixture(tmp_path)
    plan = _load("plan_m3", _BIN / "bin" / "plan.py")
    assert plan.cmd_design_materialize("ch1", repo, "tpl-x", root) == 0
    assert plan.cmd_design_materialize("ch1", repo, "tpl-x", root) \
        == plan.EXIT_PACKAGE_INVALID


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/mat-test-specs", ignore_errors=True)
