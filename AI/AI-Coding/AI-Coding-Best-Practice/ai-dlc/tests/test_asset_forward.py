"""asset-forward-design (PRD af) — tests.

AF1 manifest kinds/counts; caps flag-overridable; AF2 the specify
prompt consumes standing material (palette derives from the example
page, images listed by materialized path) and stays unchanged when no
material stands; AF4 tourism bridges exist.

Run:  python3 -m pytest tests/test_asset_forward.py -v
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import os as _os
_os.environ.setdefault("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/af-test-specs")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_af", _BIN / "bin" / "plan.py")
report = _load("report_af", _BIN / "bin" / "report.py")


def _tpl(od: Path, name: str, with_images: bool):
    d = od / "design-templates" / name
    (d / "assets").mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\nod.mode: template\nod.surface: web\n---\n"
        "body\n" % name, encoding="utf-8")
    (d / "example.html").write_text("<html>rich</html>", encoding="utf-8")
    (d / "styles.css").write_text("a{color:#fff}", encoding="utf-8")
    if with_images:
        (d / "assets" / "hero.png").write_bytes(b"\x89PNG fakedata")
        (d / "assets" / "icon.svg").write_text("<svg/>", encoding="utf-8")
    return d


def _repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    return repo, td


class TestAF1Manifest:
    def test_kinds_and_counts(self, tmp_path):
        od = tmp_path / "od"
        _tpl(od, "rich-x", with_images=True)
        repo, td = _repo(tmp_path)
        assert plan.cmd_design_materialize(
            "c1", repo, "rich-x", od) == 0
        dest = plan.plane_tree(repo) / "changes" / "c1" \
            / "design-material"
        man = json.loads((dest / "manifest.json").read_text())
        kinds = {f["path"]: f["kind"] for f in man["files"]}
        assert kinds["example.html"] == "html"
        assert kinds["assets/hero.png"] == "image"
        assert kinds["assets/icon.svg"] == "svg"
        assert man["counts"] == {"images": 1, "css": 1, "html": 1,
                                 "svg": 1, "other": 0}

    def test_caps_flag_override(self, tmp_path):
        od = tmp_path / "od"
        d = od / "design-templates" / "many-x"
        (d / "assets").mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: many-x\n---\nb\n",
                                    encoding="utf-8")
        for i in range(10):
            (d / "assets" / f"i{i}.png").write_bytes(b"x" * 10)
        repo, td = _repo(tmp_path)
        # cap 3 files via flag, though the default is far higher
        assert plan.cmd_design_materialize(
            "c1", repo, "many-x", od, max_files=3) == 0
        man = json.loads((plan.plane_tree(repo) / "changes" / "c1"
                          / "design-material" / "manifest.json")
                         .read_text())
        assert len(man["files"]) == 3


class TestAF2SpecifyPrompt:
    def _state(self, td, skill):
        report.save_json(td / "state.json", {
            "task_id": "c1", "route": "inline", "stage": "WORK",
            "design_selection": {"chosen": str(skill),
                                 "skill_name": "tpl",
                                 "skill_sha256": "x"}})

    def _fake_session(self, files_to_write):
        def fake(change, prompt, repo, task_dir, mode, timeout, generation=1):
            self.captured = prompt
            d = repo / "design"
            d.mkdir(exist_ok=True)
            for name, text in files_to_write.items():
                (d / name).write_text(text, encoding="utf-8")
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "session_name": "design-c1-001"}, []
        return fake

    def test_prompt_consumes_standing_material(self, tmp_path,
                                               monkeypatch):
        od = tmp_path / "od"
        tpl = _tpl(od, "rich-y", with_images=True)
        repo, td = _repo(tmp_path)
        self._state(td, tpl / "SKILL.md")
        assert plan.cmd_design_materialize(
            "c1", repo, "rich-y", od) == 0
        monkeypatch.setattr(plan, "run_design_session",
                            self._fake_session({
                                n: "content\n" for n in
                                ("tokens.css", "tokens.json",
                                 "components.md", "pages.md",
                                 "assets.md")}))
        assert plan.cmd_design_specify("c1", repo, td) == 0
        p = self.captured
        assert "example.html" in p and "MUST derive" in p, \
            "palette must derive from the materialized example"
        assert "assets/hero.png" in p, "images listed by material path"

    def test_prompt_plain_without_material(self, tmp_path, monkeypatch):
        od = tmp_path / "od"
        tpl = _tpl(od, "plain-y", with_images=False)
        repo, td = _repo(tmp_path)
        self._state(td, tpl / "SKILL.md")
        monkeypatch.setattr(plan, "run_design_session",
                            self._fake_session({
                                n: "content\n" for n in
                                ("tokens.css", "tokens.json",
                                 "components.md", "pages.md",
                                 "assets.md")}))
        assert plan.cmd_design_specify("c1", repo, td) == 0
        assert "MUST derive" not in self.captured


class TestAF4TourismBridges:
    def test_batch3_present_and_disciplined(self):
        data = json.loads(
            (_BIN / "scripts" / "od-synonyms.json").read_text())
        t = data["templates"]
        for term in ("旅游官网", "观光", "景点", "目的地"):
            assert term in t["open-design-landing"]
        # discipline: tourism words belong to the image-bearing
        # landing template only
        for name, terms in t.items():
            if name != "open-design-landing":
                joined = " ".join(terms)
                for owned in ("旅游", "观光", "景点", "目的地"):
                    assert owned not in joined, (name, owned)


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/af-test-specs", ignore_errors=True)
