"""pool20 exec-gate finding — pytest usage-error fallback, tests.

A project whose pytest addopts name plugins the venv does not carry
kills the probe at rc 4 before any test runs; the gate retries once
with addopts cleared and records both attempts. The retry's verdict is
the gate's; a real test failure (rc 1) never triggers the fallback.

Run:  python3 -m pytest tests/test_exec_gate_fallback.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_fb", _BIN / "bin" / "report.py")


def _usage_err_plan() -> str:
    """A pytest probe that exits 4 unless the addopts-clearing flags
    ('-o addopts=') were appended — mimics a .pytest.ini naming an
    uninstalled plugin."""
    return json.dumps([{
        "name": "pytest",
        "cmd": [sys.executable, "-c",
                "import sys; sys.exit(4 if '-o' not in sys.argv "
                "else 0)"],
        "scope": "suite",
    }])


def test_usage_error_falls_back_and_passes(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", _usage_err_plan())
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "pass", gate["tools"][0]["output_tail"]
    tool = gate["tools"][0]
    assert tool["status"] == "pass" and tool["rc"] == 0
    assert tool["fallback"] == ("project addopts cleared after "
                                "usage error")
    assert "[retry with project addopts cleared]" in \
        "\n".join(tool["output_tail"])


def test_usage_error_fallback_still_failing_fails(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv(
        "AI_DLC_EXEC_TOOLS_JSON",
        json.dumps([{
            "name": "pytest",
            "cmd": [sys.executable, "-c", "import sys; sys.exit(4)"],
            "scope": "suite",
        }]))
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    tool = gate["tools"][0]
    assert tool["status"] == "fail" and tool["rc"] == 4
    assert gate["state"] == "fail"


def test_real_failure_never_triggers_fallback(tmp_path, monkeypatch):
    """rc 1 is a test failure, not a probe breakage — no retry."""
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv(
        "AI_DLC_EXEC_TOOLS_JSON",
        json.dumps([{
            "name": "pytest",
            "cmd": [sys.executable, "-c", "import sys; sys.exit(1)"],
            "scope": "suite",
        }]))
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    tool = gate["tools"][0]
    assert tool["status"] == "fail"
    assert "fallback" not in tool


def test_non_pytest_usage_error_untouched(tmp_path, monkeypatch):
    """The fallback is pytest's alone — another tool at rc 4 fails
    without a retry."""
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv(
        "AI_DLC_EXEC_TOOLS_JSON",
        json.dumps([{
            "name": "t-four", "scope": "suite",
            "cmd": [sys.executable, "-c", "import sys; sys.exit(4)"],
        }]))
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "fail"
    assert "fallback" not in gate["tools"][0]
