"""P1-7 browser-verify exploration/verification separation — tests.

classify_spec_run: pass / flake / fail from the runner's JSON (a
fail-then-pass is a flake — suspicious, named, never silent). The
deterministic replay runs the pinned tree's playwright-core against a
file:// page: no model, no MCP, isolated profile per attempt.

Run:  python3 -m pytest tests/test_browser_spec.py -v
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_bv_t", _BIN / "bin" / "plan.py")

PIN = Path(os.environ.get("AI_DLC_PLAYWRIGHT_ROOT", "/opt/playwright-mcp"))
HAS_PIN = (PIN / "node_modules" / "playwright-core").is_dir() \
    and shutil.which("node") is not None


def _run(pages):
    return {"pages": [{"url": "p%s" % i, "attempts": a}
                      for i, a in enumerate(pages)]}


def test_first_attempt_pass_is_pass():
    c = plan.classify_spec_run(_run([[{"ok": True, "failures": []}]]))
    assert c["verdict"] == "pass"
    assert c["counts"] == {"pass": 1, "flake": 0, "fail": 0}


def test_fail_then_pass_is_flake_named_never_silent():
    c = plan.classify_spec_run(_run([
        [{"ok": False, "failures": ["selector missing: nav"]},
         {"ok": True, "failures": []}]]))
    assert c["verdict"] == "flake"
    assert c["pages"][0]["verdict"] == "flake"
    assert c["pages"][0]["failures"] == ["selector missing: nav"]


def test_two_fails_is_fail_with_trace():
    c = plan.classify_spec_run(_run([
        [{"ok": False, "failures": ["text missing"]},
         {"ok": False, "failures": ["text missing"]}]]))
    assert c["verdict"] == "fail"
    assert c["pages"][0]["trace"] is None or c["pages"][0]["trace"]


def test_mixed_pages_counts_each_kind():
    c = plan.classify_spec_run(_run([
        [{"ok": True, "failures": []}],
        [{"ok": False, "failures": ["x"]}, {"ok": True, "failures": []}],
        [{"ok": False, "failures": ["y"]},
         {"ok": False, "failures": ["y"]}]]))
    assert c["counts"] == {"pass": 1, "flake": 1, "fail": 1}
    assert c["verdict"] == "fail"


def test_missing_spec_refuses_with_the_shape(tmp_path, capsys):
    rc = plan.cmd_browser_spec_run(tmp_path / "nope.json", tmp_path,
                                   None)
    out = json.loads(capsys.readouterr().out)
    assert rc != 0 and out["refused"] is True
    assert "pages" in out["remedy"]


def test_unparseable_spec_refuses(tmp_path, capsys):
    p = tmp_path / "spec.json"
    p.write_text("{not json", encoding="utf-8")
    rc = plan.cmd_browser_spec_run(p, tmp_path, None)
    out = json.loads(capsys.readouterr().out)
    assert rc != 0 and out["refused"] is True


@pytest.mark.skipif(not HAS_PIN, reason="pinned playwright tree absent")
def test_deterministic_replay_on_a_real_page(tmp_path, capsys):
    # the acceptance: file:// page, real chromium from the pinned tree,
    # no model, no MCP — one pass and one genuine fail
    repo = tmp_path / "site"
    repo.mkdir()
    (repo / "index.html").write_text(
        "<html><head><title>Coffee Guide</title></head><body>"
        "<nav>nav</nav><h1>Coffee Guide</h1></body></html>",
        encoding="utf-8")
    task_dir = tmp_path / "td"
    task_dir.mkdir()
    spec = repo / "browser-verify" / "spec.json"
    spec.parent.mkdir()
    spec.write_text(json.dumps({"pages": [
        {"path": "index.html", "title": "Coffee Guide",
         "selectors": ["nav", "h1"], "texts": ["Coffee Guide"]},
        {"path": "index.html", "title": "Wrong Title",
         "selectors": []},
    ]}), encoding="utf-8")
    rc = plan.cmd_browser_spec_run(spec, repo, task_dir)
    out = json.loads(capsys.readouterr().out)
    verdicts = {p["page"]: p["verdict"] for p in out["pages"]}
    assert verdicts["index.html"] == "fail"      # the second entry fails
    assert out["counts"]["fail"] >= 1
    assert rc == 1
    assert (task_dir / "browser-spec-run.json").is_file()
    traces = list((task_dir).glob("*.zip")) + \
        list(task_dir.glob("browser-traces/*.zip"))
    assert traces, "a first-attempt failure must leave a trace"
