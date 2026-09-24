"""P1-2 dispatch policy gate — tests for the OpenBot-ported semantics.

deny first (never overruled by allow); broken rules fail closed and
name themselves; nothing else matches → default-deny; every decision,
allow included, is audited before anything runs.

Run:  python3 -m pytest tests/test_dispatch_policy.py -v
"""
import importlib.util
import json
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


plan = _load("plan_dispatch_policy", _BIN / "bin" / "plan.py")


@pytest.fixture(autouse=True)
def _default_config(monkeypatch, tmp_path):
    # no dispatch_policy section at all: the builtin roster governs
    cfg = tmp_path / "collapsed.config.yaml"
    cfg.write_text("review:\n  max_axes: 3\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_CONFIG", str(cfg))


def _config_with(monkeypatch, tmp_path, body: str):
    cfg = tmp_path / "collapsed.config.yaml"
    cfg.write_text(body, encoding="utf-8")
    monkeypatch.setenv("AI_DLC_CONFIG", str(cfg))


def test_builtin_roster_roles_are_allowed():
    for role in ("proposal", "specs", "design", "tasks",
                 "review-correctness", "review-security", "archiver"):
        assert dispatch_ok(role), role


def dispatch_ok(role: str) -> bool:
    return plan.dispatch_policy_decide(role)["decision"] == "allow"


def test_unknown_role_is_default_denied_with_the_allowlist_named():
    d = plan.dispatch_policy_decide("attacker-role")
    assert d["decision"] == "refuse"
    assert d["source"] == "default-deny"
    assert "review-*" in d["allowlist"]
    assert "permits nothing" in d["why"]


def test_deny_beats_allow(monkeypatch, tmp_path):
    _config_with(monkeypatch, tmp_path, (
        "dispatch_policy:\n"
        "  deny: review-*\n"
        "  allow: review-*, proposal\n"))
    d = plan.dispatch_policy_decide("review-correctness")
    assert d["decision"] == "refuse"
    assert d["rule"] == "review-*"
    assert d["source"] == "deny"


def test_allow_list_can_replace_the_builtin(monkeypatch, tmp_path):
    _config_with(monkeypatch, tmp_path, (
        "dispatch_policy:\n"
        "  allow: proposal\n"))
    assert dispatch_ok("proposal")
    assert plan.dispatch_policy_decide("design")["source"] == "default-deny"


def test_broken_rule_fails_closed_and_names_itself(monkeypatch, tmp_path):
    _config_with(monkeypatch, tmp_path, (
        "dispatch_policy:\n"
        "  deny: ,\n"))
    d = plan.dispatch_policy_decide("proposal")
    assert d["decision"] == "refuse"
    assert "broken" in d["source"]
    assert "fails closed" in d["why"]


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    return tmp_path


BRIEF = ("Objective: o.\nExpected output: e.\nTools: t.\nBoundary: b.\n")


def test_dispatch_role_refuses_denied_role_before_the_client(tmp_path,
                                                             monkeypatch):
    repo = _git_repo(tmp_path)
    monkeypatch.setenv("AI_DLC_CONFIG", str(
        tmp_path / "collapsed.config.yaml"))
    (tmp_path / "collapsed.config.yaml").write_text(
        "dispatch_policy:\n  deny: review-*\n", encoding="utf-8")

    def _no_client(cmd, **kw):
        raise AssertionError("the client was invoked on a denied role")
    monkeypatch.setattr(plan.subprocess, "run", _no_client)
    out, code = plan.dispatch_role("c1", "review-correctness", {}, repo,
                                   BRIEF, tmp_path, "code.normal", 60)
    assert code == plan.EXIT_ROLE_REJECTED
    assert out["refused"] == "policy"
    assert out["policy_rule"] == "review-*"
    assert out["stopped"].startswith("before dispatch")


def test_the_audit_trail_carries_allow_and_refuse(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    # a decision that allows, then one that refuses — both audited
    (tmp_path / "collapsed.config.yaml").write_text(
        "dispatch_policy:\n  deny: specs\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_CONFIG",
                       str(tmp_path / "collapsed.config.yaml"))

    def _no_client(cmd, **kw):
        raise AssertionError("the client was invoked")
    monkeypatch.setattr(plan.subprocess, "run", _no_client)
    # the allowed dispatch stops at the baseline (git_status_paths is
    # stubbed to fail) — AFTER the policy decision was audited, before
    # any client contact; the denied one stops at the gate itself
    monkeypatch.setattr(plan, "git_status_paths", lambda tree: None)
    plan.dispatch_role("c1", "proposal", {}, repo, BRIEF, tmp_path,
                       "code.normal", 60)   # allowed, stopped at baseline
    plan.dispatch_role("c1", "specs", {}, repo, BRIEF, tmp_path,
                       "code.normal", 60)   # denied at the gate
    rows = [json.loads(l) for l in
            (tmp_path / "dispatch-policy.jsonl").read_text(
                encoding="utf-8").splitlines()]
    by_role = {r["role"]: r for r in rows}
    assert by_role["proposal"]["decision"] == "allow"
    assert by_role["specs"]["decision"] == "refuse"
    assert by_role["specs"]["rule"] == "specs"


def test_first_hour_add_a_deny_and_confirm_refusal(monkeypatch, tmp_path):
    # OpenBot's install acceptance, ported: a deployment without a rule
    # that actually refuses has no governance
    (tmp_path / "collapsed.config.yaml").write_text(
        "dispatch_policy:\n  deny: design\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_CONFIG",
                       str(tmp_path / "collapsed.config.yaml"))
    d = plan.dispatch_policy_decide("design")
    assert d["decision"] == "refuse" and d["source"] == "deny"
