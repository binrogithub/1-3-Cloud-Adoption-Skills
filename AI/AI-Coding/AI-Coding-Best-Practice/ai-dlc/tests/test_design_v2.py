"""Acceptance tests for the v2 design architecture (M1-M6).

The v2 architecture turns design from "an action on finished code" into
"a product that code must conform to."  Four phases: D0 SELECT → D1
SPECIFY → D2 BUILD → D3 VERIFY.  These tests exercise the plan.py and
report.py functions that implement each phase, mocking the plane/design
sessions so the tests are pure unit tests with tmp_path isolation.

Run:  python3 -m pytest tests/test_design_v2.py -v
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ── load plan.py and report.py as modules ───────────────────────────
_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_test_mod", _BIN / "plan.py")
report = _load("report_test_mod", _BIN / "report.py")


# ── helpers ─────────────────────────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return r.stdout


def _seed_repo(repo: Path) -> str:
    """Init a git repo with one empty seed commit; return the seed SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    return _git(repo, "rev-parse", "HEAD").strip()


def _state(task_dir: Path, repo: Path, base: str,
           change_id: str = "c1", route: str = "inline") -> Path:
    """Write a minimal state.json for a task."""
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": route, "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso()}
    sp = task_dir / "state.json"
    report.save_json(sp, st)
    return sp


def _make_opendesign_root(root: Path, n: int = 1) -> Path:
    """Create a fake OpenDesign root with n SKILL.md candidates."""
    skills = root / "skills"
    skills.mkdir(parents=True)
    for i in range(n):
        d = skills / f"skill-{i}"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: Skill %d\nod.mode: prototype\nod.surface: web\n"
            "category: web\n---\n# Skill %d\n" % (i, i),
            encoding="utf-8")
    return root


def _assistant_frames(text: str) -> list:
    """Build a frames list with one assistant text message."""
    return [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    })]


def _ok_session_out(frames: list | None = None) -> dict:
    # run_plane_session's real contract: frames live INSIDE the dict
    # (out["frames"]), and the second return value is an int exit code
    # — never the frames list itself. A mock that returned
    # (dict, frames_list) here would silently match the exact caller
    # bug this fixture exists to catch (cmd_design_select once did
    # `out, frames = run_plane_session(...)`, treating the int as
    # frames — TypeError: 'int' object is not reversible).
    return {"timed_out": False, "round_complete": True,
            "interrupted": False, "client_rc": 0, "frames": frames or []}


# ═══ M1 — D0 SELECT produces a design_selection record ═════════════

class TestM1DesignSelect:
    """M1: cmd_design_select writes state.json.design_selection."""

    def test_positive_selection_record(self, tmp_path, monkeypatch, capsys):
        """D0 SELECT writes design_selection with chosen, reason,
        skill_sha256, shortlist."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")  # web surface
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        od_root = _make_opendesign_root(tmp_path / "opendesign", n=1)
        skill_path = str(od_root / "skills" / "skill-0" / "SKILL.md")
        expected_sha = hashlib.sha256(
            Path(skill_path).read_bytes()).hexdigest()

        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od_root))

        def fake_session(change, verb, prompt, repo, task_dir, mode, timeout):
            return _ok_session_out(frames=_assistant_frames(skill_path)), 0

        monkeypatch.setattr(plan, "run_plane_session", fake_session)

        rc = plan.cmd_design_select("c1", repo, task_dir)
        capsys.readouterr()  # swallow stdout

        state = report.load_json(task_dir / "state.json", {})
        sel = state.get("design_selection")
        assert sel is not None, "design_selection record was not written"
        assert sel["chosen"] == skill_path
        assert sel["skill_sha256"] == expected_sha
        assert "reason" in sel and sel["reason"]
        assert "shortlist" in sel and len(sel["shortlist"]) >= 1
        assert sel["degraded"] is False
        assert sel["eligible"] >= 1

    def test_negative_no_candidates_no_record(self, tmp_path, monkeypatch,
                                              capsys):
        """When candidates are exhausted, no design_selection is written
        and degraded is not set (the function returns an error)."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        # empty OpenDesign root — no candidates
        od_root = tmp_path / "opendesign"
        od_root.mkdir()
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od_root))

        rc = plan.cmd_design_select("c1", repo, task_dir)
        capsys.readouterr()

        assert rc == 1, "exhausted candidates should return error exit"
        state = report.load_json(task_dir / "state.json", {})
        assert "design_selection" not in state, \
            "no design_selection should be written when candidates exhausted"

    def test_negative_degraded_on_timeout(self, tmp_path, monkeypatch,
                                          capsys):
        """When the 120s session times out, degraded=true and the
        top-scored candidate is used as fallback."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        od_root = _make_opendesign_root(tmp_path / "opendesign", n=1)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od_root))

        def fake_timeout(change, verb, prompt, repo, task_dir, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "client_rc": None, "frames": []}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake_timeout)

        rc = plan.cmd_design_select("c1", repo, task_dir)
        capsys.readouterr()

        state = report.load_json(task_dir / "state.json", {})
        sel = state.get("design_selection")
        assert sel is not None, "degraded selection should still be written"
        assert sel["degraded"] is True
        assert "degraded" in sel["reason"]


# ═══ M2 — D1 SPECIFY produces 5 design artifacts ═══════════════════

class TestM2DesignSpecify:
    """M2: cmd_design_specify produces design/tokens.css + tokens.json +
    components.md + pages.md + assets.md."""

    _ARTIFACTS = ("tokens.css", "tokens.json", "components.md",
                  "pages.md", "assets.md")

    def test_positive_five_artifacts(self, tmp_path, monkeypatch, capsys):
        """After D1 SPECIFY, all 5 design artifacts exist and are non-empty."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        sp = _state(task_dir, repo, base)

        skill_path = str(tmp_path / "SKILL.md")
        Path(skill_path).write_text("# skill")
        report.save_json(sp, {
            **report.load_json(sp, {}),
            "design_selection": {"chosen": skill_path,
                                 "skill_sha256": "abc",
                                 "skill_name": "test"}})

        design_dir = repo / "design"

        def fake_design_session(change, prompt, repo, task_dir, mode, timeout):
            # simulate the session writing the 5 artifacts
            design_dir.mkdir(exist_ok=True)
            (design_dir / "tokens.css").write_text(":root{--c:#fff;}\n")
            (design_dir / "tokens.json").write_text('{"color":"#fff"}\n')
            (design_dir / "components.md").write_text("## Button\n")
            (design_dir / "pages.md").write_text("# Home\n")
            (design_dir / "assets.md").write_text("# Assets\n")
            return _ok_session_out(), []

        monkeypatch.setattr(plan, "run_design_session", fake_design_session)

        rc = plan.cmd_design_specify("c1", repo, task_dir)
        capsys.readouterr()

        for name in self._ARTIFACTS:
            p = design_dir / name
            assert p.is_file(), f"{name} was not created"
            assert p.stat().st_size > 0, f"{name} is empty"

        state = report.load_json(task_dir / "state.json", {})
        assert state["design_spec"]["all_written"] is True

    def test_negative_timeout_no_partial(self, tmp_path, monkeypatch, capsys):
        """D1 failure (session timeout) → no partial artifacts, failure
        recorded."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        sp = _state(task_dir, repo, base)

        skill_path = str(tmp_path / "SKILL.md")
        Path(skill_path).write_text("# skill")
        report.save_json(sp, {
            **report.load_json(sp, {}),
            "design_selection": {"chosen": skill_path,
                                 "skill_sha256": "abc",
                                 "skill_name": "test"}})

        design_dir = repo / "design"

        def fake_timeout(change, prompt, repo, task_dir, mode, timeout):
            # session times out before writing anything
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "client_rc": None}, []

        monkeypatch.setattr(plan, "run_design_session", fake_timeout)

        rc = plan.cmd_design_specify("c1", repo, task_dir)
        capsys.readouterr()

        assert rc == plan.EXIT_INCONCLUSIVE
        # no partial artifacts
        for name in self._ARTIFACTS:
            assert not (design_dir / name).exists(), \
                f"{name} should not exist on timeout"
        # no design_spec recorded
        state = report.load_json(task_dir / "state.json", {})
        assert "design_spec" not in state, \
            "no design_spec should be recorded on timeout"


# ═══ M3 — D3 VERIFY six checks are product-side ═════════════════════

class TestM3DesignVerify:
    """M3: cmd_design_verify runs six mechanical checks against the
    filesystem, not frames."""

    def _setup_spec(self, repo, task_dir, skill_sha="abc"):
        """Write design artifacts + state with design_selection/spec."""
        design_dir = repo / "design"
        design_dir.mkdir(exist_ok=True)
        (design_dir / "tokens.css").write_text(
            ":root{\n--color-primary:#1a73e8;\n--space-md:16px;\n}\n")
        (design_dir / "tokens.json").write_text(
            '{"color":{"primary":"#1a73e8"},"space":{"md":"16px"}}\n')
        (design_dir / "components.md").write_text("## Button\n## Card\n")
        (design_dir / "pages.md").write_text("# Home page\n")
        (design_dir / "assets.md").write_text("# Assets\n")
        report.save_json(task_dir / "state.json", {
            "task_id": "c1", "change_id": "c1", "base_sha": "x",
            "repo": str(repo.resolve()), "route": "inline",
            "design_selection": {"chosen": "x", "skill_sha256": skill_sha},
            "design_spec": {"skill_sha256": skill_sha},
        })

    def test_positive_tokens_used(self, tmp_path, capsys):
        """tokens_used=true when all page colors come from tokens.css."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="match")
        # page uses only token colors
        (repo / "index.html").write_text(
            '<div style="color:#1a73e8;padding:16px;">hi</div>')

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert out["design_state"] == "design_verified"
        checks = out["checks"]
        assert checks["tokens_used"]["pass"] is True
        assert checks["tokens_json_valid"]["pass"] is True
        assert checks["skill_sha_match"]["pass"] is True
        assert checks["no_placeholder"]["pass"] is True
        assert checks["design_artifacts_exist"]["pass"] is True
        assert checks["components_conform"]["pass"] is True

    def test_negative_tokens_used_rogue_color(self, tmp_path, capsys):
        """tokens_used=false when a page has a color not in tokens.css."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="match")
        # page uses a rogue color not in tokens
        (repo / "index.html").write_text(
            '<div style="color:#deadbeef;">hi</div>')

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert out["design_state"] == "design_nonconforming"
        assert out["checks"]["tokens_used"]["pass"] is False
        assert out["checks"]["tokens_used"]["rogue_count"] >= 1

    def test_no_placeholder_catches_lorem(self, tmp_path, capsys):
        """no_placeholder=false when lorem ipsum appears in a page."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="match")
        (repo / "index.html").write_text(
            '<p>lorem ipsum dolor sit amet</p>')

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert out["checks"]["no_placeholder"]["pass"] is False
        assert out["checks"]["no_placeholder"]["hit_count"] >= 1

    def test_no_placeholder_catches_todo_fixme(self, tmp_path, capsys):
        """no_placeholder=false when TODO or FIXME appears."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="match")
        (repo / "app.js").write_text("// TODO: implement this\n// FIXME: bug")

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert out["checks"]["no_placeholder"]["pass"] is False
        assert out["checks"]["no_placeholder"]["hit_count"] >= 2

    def test_skill_sha_match(self, tmp_path, capsys):
        """skill_sha_match compares sha256 of design_selection vs design_spec."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="abc123")
        (repo / "index.html").write_text("<div>hi</div>")

        # mismatch: design_spec has a different sha
        st = report.load_json(task_dir / "state.json", {})
        st["design_spec"]["skill_sha256"] = "different"
        report.save_json(task_dir / "state.json", st)

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert out["checks"]["skill_sha_match"]["pass"] is False

    def test_tokens_json_valid(self, tmp_path, capsys):
        """tokens_json_valid parses JSON; invalid JSON fails."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True)
        self._setup_spec(repo, task_dir, skill_sha="match")
        # corrupt tokens.json
        (repo / "design" / "tokens.json").write_text("{invalid json}")

        rc = plan.cmd_design_verify("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert out["checks"]["tokens_json_valid"]["pass"] is False


# ═══ M4 — design/ counts as product files ═══════════════════════════

class TestM4DesignProductFiles:
    """M4: design/ files count toward landed_files/landed_bytes and are
    NOT in PRODUCT_EXCLUDES."""

    def test_positive_design_not_excluded(self):
        """design/ files are not excluded by PRODUCT_EXCLUDES."""
        for f in ("design/tokens.css", "design/tokens.json",
                  "design/components.md", "design/pages.md",
                  "design/assets.md"):
            assert not report.excluded(f), \
                f"{f} is excluded by PRODUCT_EXCLUDES — design/ must count"

    def test_positive_design_in_landed_files(self, tmp_path, capsys):
        """deliver report includes design/ files in landed_files count."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base, change_id="nav")

        # write a design file + a web file and commit
        (repo / "design").mkdir()
        (repo / "design" / "tokens.css").write_text(":root{--c:#fff;}")
        (repo / "index.html").write_text("<html>nav</html>")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work")

        # set up records so spec_valid is True
        os.environ["AI_DLC_RECORDS"] = str(tmp_path / "records")
        os.environ["AI_DLC_VERDICT_KEY"] = str(tmp_path / "verdict.key")
        Path(tmp_path / "verdict.key").parent.mkdir(parents=True,
                                                    exist_ok=True)
        (tmp_path / "verdict.key").write_bytes(os.urandom(32))
        report.write_record("nav", "verdict", {
            "verb": "validate", "argv": ["validate", "nav", "--strict",
                                         "--json"],
            "rc": 0, "stdout": "", "sha256": hashlib.sha256(b"").hexdigest(),
            "change": "nav", "ts": report.now_iso(), "session": "fixture"})

        # merge gate approval
        gates_dir = task_dir / "gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        report.save_json(gates_dir / "gate-merge.answer.json", {
            "decision": "approve", "rationale": "looks good",
            "approver": "tester", "ts": report.now_iso()})

        rc = report.cmd_deliver(task_dir, repo, "working",
                                no_design=True, no_design_by="tester",
                                no_design_why="test")
        out = json.loads(capsys.readouterr().out)

        assert out["landed_files"] >= 2, \
            "design/ files should count toward landed_files"
        assert "design/tokens.css" in out["files"] or \
            out["landed_files"] >= 2
        assert out["landed_bytes"] > 0

    def test_negative_design_not_in_excludes(self):
        """No PRODUCT_EXCLUDES pattern matches design/ paths."""
        for pat in report.PRODUCT_EXCLUDES:
            assert "design" not in pat, \
                f"PRODUCT_EXCLUDES pattern '{pat}' mentions design — " \
                "design/ must NOT be excluded"


# ═══ M5 — Six states (design_unspecified vs design_nonconforming) ═══

class TestM5DesignStates:
    """M5: design_unspecified (no spec) vs design_nonconforming (spec
    exists, pages don't match) — split from design_unverified."""

    def test_positive_unspecified_no_spec(self, tmp_path):
        """No spec → design_unspecified."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)
        # a web file so surface is applicable
        (repo / "index.html").write_text("<html></html>")

        dv = report.design_validation(task_dir, repo,
                                      report.load_json(task_dir / "state.json",
                                                       {}),
                                      ["index.html"])
        assert dv["design_state"] == "design_unspecified"

    def test_positive_nonconforming_spec_exists_checks_fail(self, tmp_path,
                                                            capsys):
        """Spec exists but non-conforming → design_nonconforming."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)
        (repo / "index.html").write_text(
            '<div style="color:#badcolor;">hi</div>')

        # create design artifacts (spec exists)
        design_dir = repo / "design"
        design_dir.mkdir()
        (design_dir / "tokens.css").write_text(":root{--c:#fff;}\n")
        (design_dir / "tokens.json").write_text('{"c":"#fff"}\n')
        (design_dir / "components.md").write_text("## Btn\n")
        (design_dir / "pages.md").write_text("# Home\n")
        (design_dir / "assets.md").write_text("# A\n")

        # run D3 verify to produce design_verification in state
        report.save_json(task_dir / "state.json", {
            **report.load_json(task_dir / "state.json", {}),
            "design_selection": {"chosen": "x", "skill_sha256": "s"},
            "design_spec": {"skill_sha256": "s"},
        })
        plan.cmd_design_verify("c1", repo, task_dir)
        capsys.readouterr()

        dv = report.design_validation(task_dir, repo,
                                      report.load_json(task_dir / "state.json",
                                                       {}),
                                      ["index.html"])
        assert dv["design_state"] == "design_nonconforming"

    def test_negative_unverified_legacy_only(self, tmp_path):
        """design_unverified is not used for new v2 changes — it is a
        legacy fallback for v1 signed records with no product-side
        artifacts.  With product-side artifacts present, the state is
        never design_unverified."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")

        # product-side artifacts exist
        design_dir = repo / "design"
        design_dir.mkdir()
        (design_dir / "tokens.css").write_text(":root{--c:#fff;}\n")
        (design_dir / "tokens.json").write_text('{"c":"#fff"}\n')
        (design_dir / "components.md").write_text("## B\n")
        (design_dir / "pages.md").write_text("# P\n")
        (design_dir / "assets.md").write_text("# A\n")

        dv = report.design_validation(task_dir, repo,
                                      report.load_json(task_dir / "state.json",
                                                       {}),
                                      ["index.html"])
        assert dv["design_state"] != "design_unverified", \
            "with product-side artifacts, design_unverified must not be " \
            "returned — it is legacy fallback only"


# ═══ M6 — Design state never hard-blocks merge ══════════════════════

class TestM6DesignNoBlock:
    """M6: design state is visible information, never a gate.  delivered
    is a conjunction of head_advanced + landed_files + spec_valid +
    merge_approved — design_state is NOT in that conjunction."""

    def _setup_deliver(self, tmp_path, spec_valid=True, merge_approved=True):
        """Set up a full deliver scenario with controllable spec/merge."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base, change_id="nav")

        # land work (web file + design file)
        (repo / "index.html").write_text("<html>nav</html>")
        (repo / "design").mkdir()
        (repo / "design" / "tokens.css").write_text(":root{--c:#fff;}")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work")

        # records
        os.environ["AI_DLC_RECORDS"] = str(tmp_path / "records")
        os.environ["AI_DLC_VERDICT_KEY"] = str(tmp_path / "verdict.key")
        (tmp_path / "verdict.key").write_bytes(os.urandom(32))
        report.write_record("nav", "verdict", {
            "verb": "validate", "argv": ["validate", "nav", "--strict",
                                         "--json"],
            "rc": 0 if spec_valid else 1,
            "stdout": "" if spec_valid else "fail",
            "sha256": hashlib.sha256(
                (b"" if spec_valid else b"fail")).hexdigest(),
            "change": "nav", "ts": report.now_iso(), "session": "fixture"})

        # merge gate
        gates_dir = task_dir / "gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        if merge_approved:
            report.save_json(gates_dir / "gate-merge.answer.json", {
                "decision": "approve", "rationale": "ok",
                "approver": "tester", "ts": report.now_iso()})
        return repo, task_dir

    def test_positive_delivered_with_nonconforming(self, tmp_path, capsys):
        """delivered=true is possible even with design_nonconforming."""
        repo, task_dir = self._setup_deliver(tmp_path, spec_valid=True,
                                             merge_approved=True)

        # make design non-conforming: artifacts exist but D3 checks fail
        # (tokens.css has #fff but index.html uses a rogue color)
        (repo / "index.html").write_text(
            '<html style="color:#deadbeef;">x</html>')
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "rogue color")

        # run D3 verify to establish nonconforming in state.json
        report.save_json(task_dir / "state.json", {
            **report.load_json(task_dir / "state.json", {}),
            "design_selection": {"chosen": "x", "skill_sha256": "s"},
            "design_spec": {"skill_sha256": "s"},
        })
        plan.cmd_design_verify("nav", repo, task_dir)
        capsys.readouterr()

        # prevent design auto-dispatch by pre-recording an attempt;
        # do NOT pass no_design (that would record a skip → design_declined)
        report.save_json(task_dir / "planning.json", {
            "design_auto": {"rc": 0, "attempts": 1, "state": "complete",
                            "outcome": "design_nonconforming"}})

        rc = report.cmd_deliver(task_dir, repo, "working")
        out = json.loads(capsys.readouterr().out)

        assert out["delivered"] is True, \
            "delivered should be true even with design_nonconforming"
        assert out["design"]["design_state"] == "design_nonconforming"

    def test_negative_not_delivered_not_design_caused(self, tmp_path,
                                                      capsys):
        """delivered=false is NOT caused solely by design state — it
        requires a real gate failure (no merge approval, invalid spec,
        or no landed work)."""
        repo, task_dir = self._setup_deliver(tmp_path, spec_valid=True,
                                             merge_approved=False)

        # design artifacts exist but that alone must not cause
        # delivered=false — the cause is no merge approval.
        # Keep file count below route threshold (4): index.html +
        # design/tokens.css = 2 files.
        # Prevent auto-dispatch; do not pass no_design.
        report.save_json(task_dir / "planning.json", {
            "design_auto": {"rc": 0, "attempts": 1, "state": "complete",
                            "outcome": "design_unspecified"}})

        rc = report.cmd_deliver(task_dir, repo, "working")
        out = json.loads(capsys.readouterr().out)

        assert out["delivered"] is False
        # the cause is no merge approval, not design state
        assert "merge" in str(out).lower() or \
            out.get("merge_approved") is False or \
            not out.get("gates", [])
        # design state is surfaced as information, not as the blocker
        assert "design" in out


# ═══ Single-token trigger must not double-count ═══════════════════════

class TestScoreCandidateSingleTokenTrigger:
    """Regression: a single-token trigger's "phrase" is the token itself,
    so rule 1 (phrase match, 12×idf) and rule 2 (token match, 5×idf) would
    fire on the same hit, double-counting it as 17×idf instead of 5×idf.
    The fix gates rule 1 behind len(tokens) >= 2."""

    def test_single_token_trigger_no_phrase_bonus(self):
        """A candidate whose only trigger is a single token 'landing'
        should score exactly 5×idf('landing') from rule 2 — NOT
        17×idf (12 phrase + 5 token).  Verified by comparing against a
        candidate with no triggers but the same token in its name, which
        can only ever get 5×idf from rule 3."""
        idf = {"landing": 3.0}
        query_text = "build a landing page for an ai solutions company"
        change_kw = {
            "query_tokens": plan._tokenize_query(query_text),
            "text": query_text,
            "keywords": set(),
            "surface_hint": "web",
        }

        # Candidate A: single-token trigger 'landing'
        cand_trigger = {
            "triggers": ["landing"],
            "name": "", "dir": "", "description": "",
            "scenario": "", "category": "", "platform": "",
        }
        # Candidate B: no triggers, but 'landing' appears in name
        cand_name = {
            "triggers": [],
            "name": "landing", "dir": "", "description": "",
            "scenario": "", "category": "", "platform": "",
        }

        score_trigger = plan._score_candidate(cand_trigger, change_kw, idf)
        score_name = plan._score_candidate(cand_name, change_kw, idf)

        expected = 5.0 * idf["landing"]  # 15.0 — rule 2 only

        assert score_trigger == pytest.approx(expected), (
            f"single-token trigger scored {score_trigger}, expected "
            f"{expected} (5×idf only).  If it were {17.0 * idf['landing']}, "
            f"rule 1 phrase bonus is still double-counting.")
        assert score_name == pytest.approx(expected), (
            f"name-token candidate scored {score_name}, expected {expected}")
        # The two candidates should be tied — both get exactly one 5×idf
        assert score_trigger == pytest.approx(score_name), (
            f"single-token trigger ({score_trigger}) should not outrank "
            f"a plain name match ({score_name}) — that gap is the "
            f"double-count bug.")

    def test_multi_token_trigger_still_gets_phrase_bonus(self):
        """A multi-token trigger appearing verbatim in the query should
        still get the full 12×idf/tok phrase bonus — the fix must not
        suppress legitimate phrase matches."""
        idf = {"saas": 2.0, "landing": 3.0}
        query_text = "build a saas landing page for a startup"
        change_kw = {
            "query_tokens": plan._tokenize_query(query_text),
            "text": query_text,
            "keywords": set(),
            "surface_hint": "web",
        }

        cand = {
            "triggers": ["saas landing"],
            "name": "", "dir": "", "description": "",
            "scenario": "", "category": "", "platform": "",
        }
        score = plan._score_candidate(cand, change_kw, idf)

        # Rule 1: "saas landing" verbatim → 12×idf(saas) + 12×idf(landing)
        # Rule 2: trigger tokens {saas, landing} both in query → 5×idf each
        expected = (12.0 * idf["saas"] + 12.0 * idf["landing"]
                    + 5.0 * idf["saas"] + 5.0 * idf["landing"])
        assert score == pytest.approx(expected), (
            f"multi-token trigger scored {score}, expected {expected} "
            f"(phrase 12×idf + token 5×idf for both tokens)")


# ═══ Narrow-aesthetic gate ═══════════════════════════════════════════

class TestNarrowAestheticGate:
    """When the top-scored candidate declares a specific od.audience or
    od.tone, it must not sail through the deterministic fast path even
    with a large margin — the 90s arbiter session is forced so the
    declared aesthetic gets checked against the change's context."""

    def test_narrow_aesthetic_forces_session(self, tmp_path, monkeypatch,
                                             capsys):
        """A narrow-aesthetic top1 with a big margin still goes through
        the arbiter session (method=judged), and the session's pick
        wins."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")  # web surface
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        # proposal containing "landing page" so the narrow candidate's
        # 2-token trigger phrase matches verbatim and it wins L1+L2.
        (task_dir / "proposal.md").write_text(
            "Build a landing page website for a product.\n",
            encoding="utf-8")

        od_root = tmp_path / "opendesign"
        skills = od_root / "skills"
        skills.mkdir(parents=True)

        # narrow-aesthetic candidate — declares audience/tone, trigger
        # "landing page" matches the proposal verbatim → highest score.
        narrow_dir = skills / "atelier-zero"
        narrow_dir.mkdir()
        narrow_skill = narrow_dir / "SKILL.md"
        narrow_skill.write_text(
            "---\n"
            "name: Atelier Zero\n"
            "od.mode: template\n"
            "od.surface: web\n"
            "category: web\n"
            "triggers:\n"
            "  - landing page\n"
            "od.audience: founders, design studios\n"
            "od.tone: editorial, restrained, premium\n"
            "description: An editorial collage landing template.\n"
            "---\n# Atelier Zero\n", encoding="utf-8")

        # generic candidate — no audience/tone, trigger "website" scores
        # lower (single-token, no phrase bonus).
        generic_dir = skills / "generic-web"
        generic_dir.mkdir()
        generic_skill = generic_dir / "SKILL.md"
        generic_skill.write_text(
            "---\n"
            "name: Generic Web\n"
            "od.mode: prototype\n"
            "od.surface: web\n"
            "category: web\n"
            "triggers:\n"
            "  - website\n"
            "description: A generic website prototype.\n"
            "---\n# Generic Web\n", encoding="utf-8")

        # 8 dummy candidates to inflate N so IDF is non-zero
        # (log(N/(1+freq)) > 0 requires N > 1+freq).
        for i in range(8):
            d = skills / f"dummy-{i}"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\nname: Dummy %d\nod.mode: prototype\nod.surface: web\n"
                "category: web\n---\n# Dummy %d\n" % (i, i),
                encoding="utf-8")

        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od_root))

        generic_path = str(generic_skill)

        captured_prompt = {}

        def fake_session(change, verb, prompt, repo, task_dir, mode, timeout):
            captured_prompt["text"] = prompt
            return _ok_session_out(frames=_assistant_frames(generic_path)), 0

        monkeypatch.setattr(plan, "run_plane_session", fake_session)

        rc = plan.cmd_design_select("c1", repo, task_dir)
        capsys.readouterr()

        state = report.load_json(task_dir / "state.json", {})
        sel = state.get("design_selection")
        assert sel is not None, "design_selection record was not written"

        # The gate fired → method is judged, not deterministic.
        assert sel["method"] == "judged", (
            f"expected method=judged (gate should force session), "
            f"got method={sel['method']}")
        # The gate flag is recorded.
        assert sel["narrow_aesthetic_gate"] is True, (
            "narrow_aesthetic_gate should be True when top1 declares "
            "audience or tone")
        # The session's pick (generic, non-narrow) was adopted.
        assert sel["chosen"] == generic_path, (
            f"expected chosen={generic_path}, got {sel['chosen']}")
        # The prompt included the narrow candidate's audience/tone so the
        # arbiter could see them.
        prompt_text = captured_prompt.get("text", "")
        assert "founders, design studios" in prompt_text, (
            "arbiter prompt must include the narrow candidate's audience")
        assert "editorial, restrained, premium" in prompt_text, (
            "arbiter prompt must include the narrow candidate's tone")

    def test_degraded_fallback_skips_flagged_candidate(self, tmp_path,
                                                       monkeypatch, capsys):
        """When the arbiter session times out and the top-scored
        candidate self-describes as a standalone component, the
        degraded fallback must skip it and pick the next unflagged
        candidate — not blindly fall back to best."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")  # web surface
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        # proposal containing "pricing page" so the standalone
        # candidate's 2-token trigger phrase matches verbatim and it
        # wins L1+L2.
        (task_dir / "proposal.md").write_text(
            "Build a pricing page for a SaaS product.\n",
            encoding="utf-8")

        od_root = tmp_path / "opendesign"
        skills = od_root / "skills"
        skills.mkdir(parents=True)

        # standalone candidate — description says "standalone", trigger
        # "pricing page" matches the proposal verbatim → highest score.
        standalone_dir = skills / "pricing-page"
        standalone_dir.mkdir()
        standalone_skill = standalone_dir / "SKILL.md"
        standalone_skill.write_text(
            "---\n"
            "name: Pricing Page\n"
            "od.mode: template\n"
            "od.surface: web\n"
            "category: web\n"
            "triggers:\n"
            "  - pricing page\n"
            "description: A standalone pricing page — plan tiers and FAQ.\n"
            "---\n# Pricing Page\n", encoding="utf-8")

        # generic candidate — no standalone, trigger "website" scores
        # lower (single-token, no phrase bonus).
        generic_dir = skills / "web-prototype"
        generic_dir.mkdir()
        generic_skill = generic_dir / "SKILL.md"
        generic_skill.write_text(
            "---\n"
            "name: Web Prototype\n"
            "od.mode: prototype\n"
            "od.surface: web\n"
            "category: web\n"
            "triggers:\n"
            "  - website\n"
            "description: A generic multi-section website prototype.\n"
            "---\n# Web Prototype\n", encoding="utf-8")

        # 8 dummy candidates to inflate N so IDF is non-zero.
        for i in range(8):
            d = skills / f"dummy-{i}"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\nname: Dummy %d\nod.mode: prototype\nod.surface: web\n"
                "category: web\n---\n# Dummy %d\n" % (i, i),
                encoding="utf-8")

        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od_root))

        generic_path = str(generic_skill)
        standalone_path = str(standalone_skill)

        def fake_timeout(change, verb, prompt, repo, task_dir, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "client_rc": None, "frames": []}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake_timeout)

        rc = plan.cmd_design_select("c1", repo, task_dir)
        capsys.readouterr()

        state = report.load_json(task_dir / "state.json", {})
        sel = state.get("design_selection")
        assert sel is not None, "design_selection record was not written"

        # The session timed out → degraded.
        assert sel["method"] == "degraded", (
            f"expected method=degraded, got method={sel['method']}")
        # The gate fired (standalone top1).
        assert sel["narrow_aesthetic_gate"] is True, (
            "narrow_aesthetic_gate should be True when top1 self-describes "
            "as standalone")
        # The fallback skipped the flagged standalone candidate and picked
        # the next unflagged one.
        assert sel["chosen"] == generic_path, (
            f"expected chosen={generic_path} (unflagged fallback), "
            f"got chosen={sel['chosen']}")
        assert sel["chosen"] != standalone_path, (
            "degraded fallback must not pick the flagged standalone candidate")
        # The reason names both the skipped and the chosen candidate.
        reason = sel["reason"]
        assert "Pricing Page" in reason, (
            f"reason should name the skipped candidate, got: {reason}")
        assert "Web Prototype" in reason, (
            f"reason should name the chosen candidate, got: {reason}")


# ═══ Negation-clause filtering ═════════════════════════════════════════

class TestNegatedTokens:
    """A proposal clause led by a negation particle ('not a slide deck')
    excludes X, so X must not be credited as positive query signal."""

    def test_negated_tokens_strips_excluded_clause(self):
        """'not a slide deck, not an internal admin dashboard' yields
        dashboard/deck/slide/internal/admin as negated tokens."""
        text = ("web surface — not a slide deck, "
                "not an internal admin dashboard.")
        neg = plan._negated_tokens(text)
        for tok in ("dashboard", "deck", "slide", "internal", "admin"):
            assert tok in neg, f"{tok!r} should be recognized as negated"

    def test_extract_change_keywords_excludes_negated_dashboard(self,
                                                                tmp_path):
        """A proposal.md containing the exclusion phrase must produce
        query_tokens without 'dashboard'."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")  # web surface
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        (task_dir / "proposal.md").write_text(
            "Build a marketing website for a country-b restaurant.\n"
            "Web surface — not a slide deck, "
            "not an internal admin dashboard.\n",
            encoding="utf-8")

        change_kw = plan._extract_change_keywords("c1", repo, task_dir)
        assert "dashboard" not in change_kw["query_tokens"], (
            "'dashboard' is inside a negated clause and must not appear "
            "in query_tokens")


# ═══ Negation-clause coverage: rule-1 substring + Chinese ══════════════

class TestNegationClauseCoverage:
    """a7ce907 covered rule 2-5 (token-level) negation filtering but left
    rule 1 (verbatim substring on change_kw['text']) and Chinese negation
    markers uncovered.  These tests pin the §1/§2 fixes."""

    def test_clause_is_negated_english(self):
        assert plan._clause_is_negated("not a public marketing page") is True

    def test_clause_is_negated_chinese(self):
        assert plan._clause_is_negated("不需要后台管理面板") is True

    def test_clause_is_negated_no_bare_bu_overtrigger(self):
        """Bare '不' must NOT trigger — '不错的选择' is not an exclusion."""
        assert plan._clause_is_negated("不错的选择") is False

    def test_strip_negated_clauses_removes_phrase_keeps_rest(self):
        out = plan._strip_negated_clauses(
            "Admin-only, not a public marketing page.")
        assert "marketing page" not in out, (
            "the negated clause's phrase must be stripped from the "
            "rule-1 substring text")
        assert "Admin-only" in out, (
            "the non-negated clause must be preserved")

    def test_extract_change_keywords_strips_chinese_negated_phrase(self,
                                                                   tmp_path):
        """A proposal.md with Chinese exclusion clauses '不需要后台管理面板,
        不是仪表盘' must produce a text field without '仪表盘' as a
        substring (rule-1 verbatim match must not see it)."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")  # web surface
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        (task_dir / "proposal.md").write_text(
            "为一个中文跨境电商品牌设计一个商业网站,展示产品分类、促销活动"
            "和购物车入口。面向消费者的前台页面,不需要后台管理面板,不是仪表盘。\n",
            encoding="utf-8")

        change_kw = plan._extract_change_keywords("c1", repo, task_dir)
        assert "仪表盘" not in change_kw["text"], (
            "'仪表盘' is inside a Chinese negated clause and must not "
            "appear in the rule-1 substring text field")


# ── _needs_arbitration: widget signal & self-contained non-signal ──────
# See the widget-scope PRD §2/§3.
# 'widget' is a precise narrow-scope signal (a small UI fragment, not a
# page); 'self-contained' is intentionally NOT a trigger — it describes a
# single-file delivery form, not functional scope, and would mis-flag the
# web-prototype fallback template and other legitimate candidates.

def test_needs_arbitration_widget_description_is_flagged():
    cand = {"description": "A floating chat widget for customer support."}
    assert plan._needs_arbitration(cand) is True


def test_needs_arbitration_self_contained_is_not_flagged():
    cand = {
        "description": (
            "General-purpose desktop web prototype. Single self-contained "
            "HTML file built by copying the seed template."
        )
    }
    assert plan._needs_arbitration(cand) is False


# ── soft-wrapped negation clauses ───────────────────────────────────────
# Real incident: a hand-wrapped proposal.md line "...not an\ninternal
# admin dashboard." split "not an" and "internal admin dashboard" into
# two clauses (\n was a hard clause boundary), so the negation particle
# never reached the noun it was meant to exclude — 'dashboard' leaked
# through as positive signal and D0 SELECT picked the Dashboard design
# system for a trilingual MaaS marketing site.

class TestSoftWrapNegation:
    def test_normalize_soft_wraps_joins_single_newline(self):
        out = plan._normalize_soft_wraps("not an\ninternal admin dashboard.")
        assert "\n" not in out
        assert "not an internal admin dashboard." in out

    def test_normalize_soft_wraps_preserves_paragraph_break(self):
        out = plan._normalize_soft_wraps("first paragraph\n\nsecond paragraph")
        assert "\n\n" in out

    def test_negated_tokens_survives_soft_wrap(self):
        text = "Web surface, not a slide deck, not an\ninternal admin dashboard."
        neg = plan._negated_tokens(text)
        for tok in ("dashboard", "internal", "admin"):
            assert tok in neg, (
                f"{tok!r} should be negated even though the clause was "
                f"split across a soft line-wrap")

    def test_extract_change_keywords_survives_soft_wrap(self, tmp_path):
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "index.html").write_text("<html></html>")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        _state(task_dir, repo, base)

        (task_dir / "proposal.md").write_text(
            "A marketing site. Web surface, not a slide deck, not an\n"
            "internal admin dashboard.\n",
            encoding="utf-8")

        change_kw = plan._extract_change_keywords("c1", repo, task_dir)
        assert "dashboard" not in change_kw["query_tokens"]
        assert "dashboard" not in change_kw["text"]

