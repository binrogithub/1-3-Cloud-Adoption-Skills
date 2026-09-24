"""Acceptance tests for the pre-dispatch MaaS key check in dispatch_role().

  - maas_key_missing() mirrors install.sh's maas_key_present() — same env
    file convention ($AI_DLC_ENV_FILE or ~/.jiuwenswarm/config/.env), same
    non-empty API_KEY= line check.
  - dispatch_role() calls maas_key_missing() after masked_surface_refusal
    and before git_status_paths; when the key is missing it returns the
    same early-return shape as masked_surface_refusal with EXIT_INCONCLUSIVE
    and never invokes the client subprocess.

Run:  python3 -m pytest tests/test_dispatch_maas_key.py -v
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_maas_key_test_mod", _BIN / "plan.py")


# ── maas_key_missing() unit tests ───────────────────────────────


def test_maas_key_missing_when_file_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(tmp_path / "nope.env"))
    assert plan.maas_key_missing() is True


def test_maas_key_missing_when_api_key_empty(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=\nOTHER=thing\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))
    assert plan.maas_key_missing() is True


def test_maas_key_missing_when_api_key_whitespace_only(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=   \n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))
    assert plan.maas_key_missing() is True


def test_maas_key_missing_when_no_api_key_line(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=thing\nFOO=bar\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))
    assert plan.maas_key_missing() is True


def test_maas_key_present_when_api_key_nonempty(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=sk-test-12345\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))
    assert plan.maas_key_missing() is False


def test_maas_key_present_with_other_lines_around(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nBASE_URL=https://gw\nAPI_KEY=real-key\n",
                        encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))
    assert plan.maas_key_missing() is False


# ── dispatch_role() integration: key missing stops before subprocess ────


def _seed_git_repo(repo: Path):
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email",
                    "test@test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name",
                    "test"], check=True)
    (repo / "README").write_text("init\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"],
                   check=True)


def test_dispatch_role_stops_when_maas_key_missing(tmp_path, monkeypatch):
    """Key missing → dispatch_role returns early with EXIT_INCONCLUSIVE,
    the client subprocess is never invoked."""
    repo = tmp_path / "repo"
    _seed_git_repo(repo)
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))

    # sentinel: if subprocess.run is called, the test fails
    run_mock = mock.Mock(side_effect=AssertionError(
        "subprocess.run was invoked — the client should never start when "
        "the MaaS key is missing"))
    monkeypatch.setattr(plan.subprocess, "run", run_mock)

    result, code = plan.dispatch_role(
        change="test-change", role="work", pkg={}, repo=repo,
        prompt="do something", task_dir=task_dir, mode="plan",
        timeout=60)

    assert code == plan.EXIT_INCONCLUSIVE
    assert result["stopped"] == "before dispatch — the client was never invoked"
    assert "MaaS API_KEY" in result["error"]
    assert result["remedy"] == "./install.sh --setup-maas-key"
    assert result["artifact"] == "work"
    assert result["change"] == "test-change"
    run_mock.assert_not_called()


def test_dispatch_role_proceeds_when_maas_key_present(tmp_path, monkeypatch):
    """Key present → dispatch_role does NOT early-return on the MaaS
    check; it proceeds past it toward the subprocess call (which we
    intercept to avoid a real gateway invocation)."""
    repo = tmp_path / "repo"
    _seed_git_repo(repo)
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=sk-real-key\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_ENV_FILE", str(env_file))

    # Intercept subprocess.run: the fact that it's called means we got
    # past the MaaS check.  Return a dummy successful process result so
    # dispatch_role can continue without a real gateway.
    def _fake_run(cmd, **kwargs):
        # Write an empty JSONL stream (no frames) so evidence file exists
        if "stdout" in kwargs and hasattr(kwargs["stdout"], "write"):
            kwargs["stdout"].write("")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(plan.subprocess, "run", _fake_run)

    result, code = plan.dispatch_role(
        change="test-change", role="work", pkg={}, repo=repo,
        prompt="do something", task_dir=task_dir, mode="plan",
        timeout=60)

    # The key point: we did NOT stop with the MaaS error.  Whatever
    # happened next (the dispatch ran with an empty frame stream), the
    # result must not carry the MaaS early-return signature.
    assert result.get("stopped") != "before dispatch — the client was never invoked" \
        or "MaaS API_KEY" not in result.get("error", "")
    assert "MaaS API_KEY not configured" not in result.get("error", "")
