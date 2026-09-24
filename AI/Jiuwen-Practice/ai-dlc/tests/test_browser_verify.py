"""Acceptance tests for the browser-verify role (G1, PRD
docs/prd-browser-verify-and-agent-bench.md).

Covers:
  - browser_verify_pin_state: four branches (healthy, missing root,
    missing pin file, digest mismatch) — each returning the same
    {ok, why, remedy, exit_code} shape understand_anything_pin_state uses.
  - cmd_browser_verify: not_applicable (no named page stands in the repo)
    and unavailable (pin not installed) — both non-blocking, exit 0.
    The real dispatch path needs a live gateway and is stubbed via
    monkeypatch where it would otherwise be reached.

Run:  python3 -m pytest tests/test_browser_verify.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_bv_test_mod", _BIN / "plan.py")
report = _load("report_bv_test_mod", _BIN / "report.py")


def _write_valid_pin(root: Path, tag: str = "1.0.0") -> None:
    """Write a healthy .aidlc-pin.json whose tree_sha256 is computed with
    the real digest function, so the pin and the check never drift."""
    pin = {"tag": tag, "sha": None,
           "sparse_paths": ["node_modules/@playwright/mcp"],
           "installed_at": "2026-09-06T00:00:00+00:00",
           "size_bytes": 100,
           "tree_sha256": plan.browser_verify_tree_digest(root)}
    report.save_json(root / ".aidlc-pin.json", pin)


def _healthy_root(tmp_path) -> Path:
    """A pin root with a minimal @playwright/mcp subtree and a valid pin."""
    root = tmp_path / "pw_root"
    pkg = root / "node_modules" / "@playwright" / "mcp"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text('{"name":"@playwright/mcp"}\n',
                                     encoding="utf-8")
    _write_valid_pin(root)
    return root


# ── browser_verify_pin_state ────────────────────────────────────────

class TestBrowserVerifyPinState:
    def test_healthy_pin_is_ok(self, tmp_path, monkeypatch):
        root = _healthy_root(tmp_path)
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)
        st = plan.browser_verify_pin_state()
        assert st["ok"] is True
        assert st["root"] == str(root)
        assert st["pin"]["tag"] == "1.0.0"
        assert st["pin"]["tree_sha256"]

    def test_missing_root_directory(self, tmp_path, monkeypatch):
        root = tmp_path / "no_such_root"
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)
        st = plan.browser_verify_pin_state()
        assert st["ok"] is False
        assert "why" in st and "remedy" in st
        assert st["exit_code"] == plan.EXIT_DESIGN_PIN
        assert "does not stand" in st["why"]

    def test_missing_pin_file(self, tmp_path, monkeypatch):
        root = tmp_path / "pw_root"
        pkg = root / "node_modules" / "@playwright" / "mcp"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "package.json").write_text('{}\n', encoding="utf-8")
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)
        st = plan.browser_verify_pin_state()
        assert st["ok"] is False
        assert "why" in st and "remedy" in st
        assert st["exit_code"] == plan.EXIT_DESIGN_PIN
        assert "no pin" in st["why"]

    def test_digest_mismatch(self, tmp_path, monkeypatch):
        root = _healthy_root(tmp_path)
        # tamper with a tracked file after the pin was written
        (root / "node_modules" / "@playwright" / "mcp" /
         "package.json").write_text('{"name":"@playwright/mcp","v":2}\n',
                                   encoding="utf-8")
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)
        st = plan.browser_verify_pin_state()
        assert st["ok"] is False
        assert "why" in st and "remedy" in st
        assert st["exit_code"] == plan.EXIT_DESIGN_PIN
        assert "measured_tree_sha256" in st
        assert "pinned_tree_sha256" in st
        assert st["measured_tree_sha256"] != st["pinned_tree_sha256"]


# ── cmd_browser_verify ──────────────────────────────────────────────

def _task_dir(repo: Path) -> Path:
    td = repo / ".ai-dlc" / "tasks" / "c1-planning"
    td.mkdir(parents=True, exist_ok=True)
    return td


class TestBrowserVerifyNotApplicable:
    def test_no_page_exists_is_a_noop(self, tmp_path, capsys):
        """None of --pages exist in the repo → not_applicable, no session
        dispatched (PRD §05 reverse gate)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "unrelated.txt").write_text("x", encoding="utf-8")
        td = _task_dir(repo)

        rc = plan.cmd_browser_verify("c1", repo, td,
                                     ["does-not-exist.html",
                                      "also-missing.html"])
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["browser_verify_state"] == "not_applicable"
        assert out["applicable"] is False
        assert not (repo / "browser-verify").exists()


class TestBrowserVerifyUnavailable:
    def test_pin_unavailable_is_not_an_error(self, tmp_path, monkeypatch,
                                             capsys):
        """Pin not installed → unavailable, exit 0, non-blocking (INV-39)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "index.html").write_text("<html></html>\n",
                                        encoding="utf-8")
        td = _task_dir(repo)

        monkeypatch.setattr(
            plan, "browser_verify_pin_state",
            lambda root=None: {"ok": False, "root": "/opt/playwright-mcp",
                               "pin": "/opt/playwright-mcp/.aidlc-pin.json",
                               "why": "the Playwright MCP tree does not "
                                      "stand at /opt/playwright-mcp",
                               "remedy": "scripts/install-browser-verify.sh",
                               "exit_code": plan.EXIT_DESIGN_PIN})

        rc = plan.cmd_browser_verify("c1", repo, td, ["index.html"])
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["browser_verify_state"] == "unavailable"
        assert out["applicable"] is True
        assert not (repo / "browser-verify").exists()


class TestBrowserVerifyDispatched:
    def test_session_writes_report_is_passed(self, tmp_path, monkeypatch,
                                             capsys):
        """Pin valid, dispatch (stubbed) writes browser-verify/report.md →
        passed, state.json and events.jsonl recorded.  The real dispatch
        needs a live gateway; run_browser_verify_session is stubbed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "index.html").write_text("<html></html>\n",
                                        encoding="utf-8")
        td = _task_dir(repo)
        root = _healthy_root(tmp_path)
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            report_dir = repo / "browser-verify"
            report_dir.mkdir(exist_ok=True)
            (report_dir / "report.md").write_text(
                "# browser-verify report\n\n| page | result |\n"
                "|---|---|\n| index.html | pass |\n", encoding="utf-8")
            return ({"session_name": f"browser-verify-{change}-001",
                     "round_complete": True, "interrupted": False,
                     "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_browser_verify_session",
                            fake_session)

        rc = plan.cmd_browser_verify("c1", repo, td, ["index.html"])
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["browser_verify_state"] == "passed"
        assert out["report_written"] is True

        state = report.load_json(td / "state.json", {})
        assert state["browser_verify"]["written"] is True
        assert state["browser_verify"]["browser_verify_state"] == "passed"

        events = (td / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "BROWSER_VERIFY_PASSED" in kinds

    def test_session_runs_but_no_report_is_failed(self, tmp_path,
                                                   monkeypatch, capsys):
        """Dispatch completes but writes no report → failed, recorded
        honestly."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "index.html").write_text("<html></html>\n",
                                        encoding="utf-8")
        td = _task_dir(repo)
        root = _healthy_root(tmp_path)
        monkeypatch.setattr(plan, "PLAYWRIGHT_MCP_ROOT", root)

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            return ({"session_name": f"browser-verify-{change}-001",
                     "round_complete": True, "interrupted": False,
                     "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_browser_verify_session",
                            fake_session)

        rc = plan.cmd_browser_verify("c1", repo, td, ["index.html"])
        out = json.loads(capsys.readouterr().out)

        assert rc != 0
        assert out["browser_verify_state"] == "failed"
        assert out["report_written"] is False

        events = (td / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "BROWSER_VERIFY_FAILED" in kinds
