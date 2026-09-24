"""d1-settle-window — tests.

A design session's round can complete before its file writes land;
the mechanical artifact check waits for the writes to settle first
(all expected files present, total size stable across two probes) —
the check is still the judge, it just no longer runs early.

Run:  python3 -m pytest tests/test_d1_settle.py -v
"""
import importlib.util
import sys
import threading
import time
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_sw", _BIN / "bin" / "plan.py")
report = _load("report_sw", _BIN / "bin" / "report.py")


def _late_writer(paths: list[Path], delay: float):
    def run():
        time.sleep(delay)
        for f in paths:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("real content, landed late\n", encoding="utf-8")
    t = threading.Thread(target=run)
    t.start()
    return t


class TestSettleHelper:
    def test_waits_for_late_write(self, tmp_path):
        f = tmp_path / "design" / "pages.md"
        _late_writer([f], 0.3)
        plan._settle_artifacts([f], settle_seconds=3.0, poll=0.05)
        assert f.is_file(), "settle must outlast the late write"

    def test_returns_when_never_written(self, tmp_path):
        f = tmp_path / "nope.md"
        t0 = time.monotonic()
        plan._settle_artifacts([f], settle_seconds=0.3, poll=0.1)
        assert time.monotonic() - t0 < 2
        assert not f.exists(), "the window never fabricates a file"

    def test_stable_existing_files_return_fast(self, tmp_path):
        f = tmp_path / "ok.md"
        f.write_text("already here\n")
        t0 = time.monotonic()
        plan._settle_artifacts([f], settle_seconds=30.0, poll=0.05)
        assert time.monotonic() - t0 < 5, "no needless waiting"


class TestSpecifyIntegration:
    def test_specify_survives_late_writes(self, tmp_path, monkeypatch):
        """The round completes, the five artifacts land 0.3s later —
        the specify command must still report all_written."""
        monkeypatch.setattr(plan, "SETTLE_SECONDS", 5.0)
        monkeypatch.setattr(plan, "SETTLE_POLL", 0.05)
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        td = repo / ".ai-dlc" / "tasks" / "c1"
        td.mkdir(parents=True)
        skill = tmp_path / "tpl" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: web-prototype\n---\nbody\n")
        report.save_json(td / "state.json", {
            "task_id": "c1", "route": "inline", "stage": "WORK",
            "design_selection": {"chosen": str(skill),
                                 "skill_name": "web-prototype"}})
        names = ("tokens.css", "tokens.json", "components.md",
                 "pages.md", "assets.md")
        _late_writer([repo / "design" / n for n in names], 0.3)

        def fake(change, prompt, repo_, td_, mode, timeout, generation=1):
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "session_name": "design-c1-001"}, []

        monkeypatch.setattr(plan, "run_design_session", fake)
        assert plan.cmd_design_specify("c1", repo, td) == 0
        st = report.load_json(td / "state.json", {})
        assert st["design_spec"]["all_written"] is True
