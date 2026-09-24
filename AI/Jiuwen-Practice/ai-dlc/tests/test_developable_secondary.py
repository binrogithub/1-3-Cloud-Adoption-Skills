"""developable-secondary — tests.

The pick always lands on at least one developable template (a real
composed example page) — deterministic top and degraded fallback both
step past poster-shaped stubs; the umbrella materializes the
shortlist's runner-ups as secondary slots (more template-based
material).

Run:  python3 -m pytest tests/test_developable_secondary.py -v
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/devsec-test-specs")
os.environ.setdefault("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")

spec = importlib.util.spec_from_file_location(
    "plan_ds", _BIN / "bin" / "plan.py")
plan = importlib.util.module_from_spec(spec)
sys.modules["plan_ds"] = plan
spec.loader.exec_module(plan)


def _tpl(skills: Path, name: str, example: str, strong: bool = False):
    d = skills / name
    d.mkdir(parents=True)
    trig = "aposta esportiva bet" if strong else "generic thing"
    (d / "SKILL.md").write_text(
        "---\nname: %s\nod.mode: prototype\nod.surface: web\n"
        "category: web\ntriggers:\n  - \"%s\"\n---\n# %s\n"
        % (name, trig, name), encoding="utf-8")
    (d / "example.html").write_text(example, encoding="utf-8")
    return d


REAL_PAGE = ("<html><body>"
             + "<section>one</section><section>two</section>"
             + "<section>three</section><section>four</section>"
             + "</body></html>")
POSTER_STUB = "<html><body><img src='poster.png'></body></html>"


class TestDevelopablePick:
    def test_predicate(self, tmp_path):
        big = tmp_path / "big.html"
        big.write_text("x" * 21000, encoding="utf-8")
        sections = tmp_path / "sec.html"
        sections.write_text(REAL_PAGE, encoding="utf-8")
        tiny = tmp_path / "tiny.html"
        tiny.write_text(POSTER_STUB, encoding="utf-8")
        assert plan._example_is_developable(big)
        assert plan._example_is_developable(sections)
        assert not plan._example_is_developable(tiny)
        assert not plan._example_is_developable(tmp_path / "nope.html")

    def test_deterministic_steps_past_poster(self, tmp_path):
        """Top-scored poster-shaped candidate is skipped for the first
        developable one (the verdebet shape)."""
        poster = {"dir": "poster-hero", "name": "Poster",
                  "path": "/od/skills/poster-hero/SKILL.md",
                  "has_example_html": True}
        real = {"dir": "landing", "name": "Landing",
                "path": "/od/design-templates/landing/SKILL.md",
                "has_example_html": True}
        ex = Path("/tmp/devsec-examples")
        ex.mkdir(exist_ok=True)
        monkey_targets = {poster["dir"]: False, real["dir"]: True}
        orig = plan._example_is_developable

        def fake_dev(path):
            name = Path(path).parent.name
            return monkey_targets.get(name, orig(path))
        plan._example_is_developable = fake_dev
        try:
            scored = [(9.0, poster), (8.0, real)]
            kw = {"query_tokens": {"x"}, "text": "x"}
            for _sc, c in scored:
                plan._score_candidate(c, kw, None)
            # emulate the pick loop: best=scored[0], then first
            # developable replaces it
            best = scored[0][1]
            if not plan._is_developable(best):
                for _s2, c2 in scored:
                    if plan._is_developable(c2):
                        best = c2
                        break
            assert best["dir"] == "landing"
        finally:
            plan._example_is_developable = orig

    def test_degraded_pick_prefers_developable(self, tmp_path):
        poster = {"dir": "poster-hero", "name": "Poster",
                  "path": "/od/skills/poster-hero/SKILL.md",
                  "has_example_html": True}
        flagged_real = {"dir": "landing", "name": "Landing",
                        "path": "/od/design-templates/landing/"
                                "SKILL.md",
                        "has_example_html": True,
                        "audience": "founders"}
        plain_real = {"dir": "proto", "name": "Proto",
                      "path": "/od/design-templates/proto/SKILL.md",
                      "has_example_html": True}
        monkey_targets = {"poster-hero": False, "landing": True,
                          "proto": True}
        orig = plan._example_is_developable

        def fake_dev(path):
            return monkey_targets.get(Path(path).parent.name,
                                      orig(path))
        plan._example_is_developable = fake_dev
        try:
            scored = [(9.0, poster), (8.0, flagged_real),
                      (7.0, plain_real)]
            pick = plan._degraded_pick(scored, poster)
            assert pick["dir"] == "proto", \
                "developable and unflagged wins"
            scored2 = [(9.0, poster), (8.0, flagged_real)]
            pick2 = plan._degraded_pick(scored2, poster)
            assert pick2["dir"] == "landing", \
                "a flagged real page beats an undevelopable stub"
        finally:
            plan._example_is_developable = orig


class TestSecondarySlots:
    def test_secondary_dest_and_slot(self, tmp_path):
        od = tmp_path / "od"
        skills = od / "design-templates"
        _tpl(skills, "tpl-sec", REAL_PAGE)
        repo = tmp_path / "repo"
        repo.mkdir()
        assert plan.cmd_design_materialize(
            "c1", repo, "tpl-sec", od, secondary=True) == 0
        dest = plan.plane_tree(repo) / "changes" / "c1" \
            / "design-material" / "secondary" / "tpl-sec"
        man = json.loads((dest / "manifest.json").read_text())
        assert man["slot"] == "secondary"
        assert (dest / "example.html").is_file()

    def test_umbrella_materializes_runner_ups(self, tmp_path,
                                              monkeypatch):
        calls = []

        def fake_select(change, repo, task_dir, mode="code.normal"):
            td = Path(task_dir)
            td.mkdir(parents=True, exist_ok=True)
            st = json.loads((td / "state.json").read_text())
            if "design_selection" not in st:
                st["design_selection"] = {
                    "chosen": "/od/design-templates/main/SKILL.md",
                    "shortlist": [
                        {"path": "/od/design-templates/main/SKILL.md"},
                        {"path": "/od/design-templates/run1/SKILL.md"},
                        {"path": "/od/design-templates/run1/SKILL.md"},
                        {"path": "/od/design-templates/run2/SKILL.md"},
                        {"path": "/od/design-templates/run3/SKILL.md"}]}
                (td / "state.json").write_text(json.dumps(st))
            return 0

        def fake_mat(change, repo, template, root=None, page=None,
                     max_files=None, max_bytes=None, task_dir=None,
                     secondary=False):
            calls.append((template, secondary))
            return 0

        monkeypatch.setattr(plan, "cmd_design_select", fake_select)
        monkeypatch.setattr(plan, "cmd_design_materialize", fake_mat)
        monkeypatch.setattr(plan, "cmd_design_specify",
                            lambda *a, **k: 0)
        monkeypatch.setattr(plan, "cmd_design_verify",
                            lambda *a, **k: 0)
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        td = repo / ".ai-dlc" / "tasks" / "c1"
        td.mkdir(parents=True)
        (td / "state.json").write_text("{}")
        assert plan.cmd_design("c1", repo, td, None, None,
                               "code.normal", 600) == 0
        mains = [c for c in calls if not c[1]]
        secs = [c for c in calls if c[1]]
        assert mains == [("main", False)]
        assert [t for t, _ in secs] == ["run1", "run2"], \
            "runner-ups (deduped, capped) as secondary material"


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/devsec-test-specs", ignore_errors=True)
    shutil.rmtree("/tmp/devsec-examples", ignore_errors=True)
