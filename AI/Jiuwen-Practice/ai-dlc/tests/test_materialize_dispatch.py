"""materialize-via-dispatch — tests.

OpenDesign is consumed through jiuwenswarm sessions: the copy runs as
a normalized command inside the session, the plane verifies frames,
cross-checks the copy report against standing files, and signs the
manifest with the session name. A refused session or a mismatched
report is inconclusive; the offline path only exists behind the
kill-switch.

Run:  python3 -m pytest tests/test_materialize_dispatch.py -v
"""
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/matdisp-test-specs")

spec = importlib.util.spec_from_file_location(
    "plan_md", _BIN / "bin" / "plan.py")
plan = importlib.util.module_from_spec(spec)
sys.modules["plan_md"] = plan
spec.loader.exec_module(plan)


def _tpl(od: Path, name: str):
    d = od / "design-templates" / name
    (d / "assets").mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\nod.mode: template\nod.surface: web\n---\n"
        "body\n" % name, encoding="utf-8")
    (d / "example.html").write_text("<html>rich</html>", encoding="utf-8")
    (d / "assets" / "hero.png").write_bytes(b"\x89PNG fake")
    (d / "assets" / "icon.svg").write_text("<svg/>", encoding="utf-8")
    return d


def _repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    return repo, td


def _session_frames(argv, rc=0, actually_run=True, stdout=None):
    """Evidence-style frames for one normalized bash call; optionally
    executes the argv so the files really land."""
    if actually_run:
        r = subprocess.run(argv, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        stdout = stdout or r.stdout
    cmd = shlex.join(argv)
    if stdout is None:
        stdout = ""
    # the gateway renders results as: success=True data={'content':
    # '<stdout>'} error=None (parse_tool_result reads exactly this)
    res = ("success=%s data={'content': %r} error=None"
           % (rc == 0, stdout))
    return [
        json.dumps({"event": "chat.tool_call", "payload": {
            "tool_call": {"name": "bash",
                          "arguments": json.dumps({"command": cmd}),
                          "tool_call_id": "t1"}}}),
        json.dumps({"event": "chat.tool_result", "payload": {
            "tool_call_id": "t1",
            "result": res}}),
    ]


class TestDispatchPath:
    @staticmethod
    def _online(monkeypatch):
        # other test modules setdefault the kill-switch at import —
        # the dispatch tests must run with it explicitly cleared
        monkeypatch.delenv("AI_DLC_NO_MATERIALIZE_DISPATCH",
                           raising=False)

    def test_copy_via_session_manifest_signed(self, tmp_path,
                                              monkeypatch):
        self._online(monkeypatch)
        repo, td = _repo(tmp_path)
        od = tmp_path / "od"
        _tpl(od, "tpl-disp")
        argv_seen = {}

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            argv_seen["verb"] = verb
            # the plane's prompt carries the literal argvs; recover and
            # run them so the copy actually lands
            import re as _re
            m = _re.search(r"--template-dir (\S+)", prompt)
            assert m, prompt[:200]
            script = str(_BIN / "scripts" / "materialize_copy.py")
            argv = [sys.executable, script,
                    "--template-dir", m.group(1),
                    "--dest", _re.search(r"--dest (\S+)", prompt)
                    .group(1),
                    "--max-files", "40",
                    "--max-bytes", str(24 * 1024 * 1024)]
            argv_seen["argv"] = argv
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _session_frames(argv),
                    "session_name": "disp-1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_materialize(
            "c1", repo, "tpl-disp", od, task_dir=td) == 0
        assert argv_seen["verb"] == "design-materialize"
        man = json.loads(
            (plan.plane_tree(repo) / "changes" / "c1" /
             "design-material" / "manifest.json").read_text())
        assert man["dispatched"] is True
        assert man["session"] == "disp-1"
        assert man["counts"]["images"] == 1
        assert (plan.plane_tree(repo) / "changes" / "c1" /
                "design-material" / "assets" / "hero.png").is_file()

    def test_refused_session_is_inconclusive(self, tmp_path,
                                             monkeypatch):
        self._online(monkeypatch)
        repo, td = _repo(tmp_path)
        od = tmp_path / "od"
        _tpl(od, "tpl-ref")

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            return {"refused": "no-conduit",
                    "exit_code": plan.EXIT_INCONCLUSIVE}, \
                plan.EXIT_INCONCLUSIVE

        monkeypatch.setattr(plan, "run_plane_session", fake)
        rc = plan.cmd_design_materialize(
            "c1", repo, "tpl-ref", od, task_dir=td)
        assert rc == plan.EXIT_INCONCLUSIVE
        assert not (plan.plane_tree(repo) / "changes" / "c1" /
                    "design-material" / "manifest.json").exists()

    def test_report_mismatch_is_inconclusive(self, tmp_path,
                                             monkeypatch):
        """The session claims files that do not stand — machine fact
        over session claim."""
        self._online(monkeypatch)
        repo, td = _repo(tmp_path)
        od = tmp_path / "od"
        _tpl(od, "tpl-mm")
        argv_seen = {}

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            import re as _re
            argv = [sys.executable,
                    str(_BIN / "scripts" / "materialize_copy.py"),
                    "--template-dir",
                    _re.search(r"--template-dir (\S+)", prompt).group(1),
                    "--dest",
                    _re.search(r"--dest (\S+)", prompt).group(1),
                    "--max-files", "40",
                    "--max-bytes", str(24 * 1024 * 1024)]
            argv_seen["argv"] = argv
            # claim a file that was never copied
            lying = json.dumps({"copied": [{"path": "assets/ghost.png",
                                            "bytes": 1}],
                                "total_bytes": 1})
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _session_frames(
                        argv, actually_run=True, stdout=lying),
                    "session_name": "disp-2"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        rc = plan.cmd_design_materialize(
            "c1", repo, "tpl-mm", od, task_dir=td)
        assert rc == plan.EXIT_INCONCLUSIVE


class TestOfflinePath:
    def test_kill_switch_never_opens_a_session(self, tmp_path,
                                               monkeypatch):
        monkeypatch.setenv("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")
        repo, td = _repo(tmp_path)
        od = tmp_path / "od"
        _tpl(od, "tpl-off")

        def no_session(*a, **k):
            raise AssertionError("no session may open under the "
                                 "kill-switch")

        monkeypatch.setattr(plan, "run_plane_session", no_session)
        assert plan.cmd_design_materialize(
            "c1", repo, "tpl-off", od, task_dir=td) == 0
        man = json.loads(
            (plan.plane_tree(repo) / "changes" / "c1" /
             "design-material" / "manifest.json").read_text())
        assert man["dispatched"] is False
        assert man["session"] is None


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/matdisp-test-specs", ignore_errors=True)
