"""Contract tests for scripts/verify-exa.sh — the Exa release verifier.

Offline gates (always run, no network):
  1. key-mode      — exa-api-key is a 0600 regular file
  2. helper        — exa-headers-helper.py exists and compiles
  3. plain-absent  — plain ~/.claude has no exa-search MCP or EXA_API_KEY
  4. isolated      — ~/.claude-maas/.claude.json has the exa-search HTTP entry
  5. tools         — exactly web_search_exa and web_fetch_exa allowed

Live gates (skipped in offline mode / when no key):
  6. mcp-health    — claude-maas sees exa-search Connected
  7. search        — a search canary returns an HTTPS source URL
  8. fetch         — a fetch canary returns page content
  9. model         — glm-5.2 only
  10. context      — contextWindow 1000000

The verifier reads the key from stdin and redacts it from all output.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-exa.sh"

KEY_VALUE = "test-exa-key-secret"
EXA_URL = "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
PERM_SEARCH = "mcp__exa-search__web_search_exa"
PERM_FETCH = "mcp__exa-search__web_fetch_exa"

OFFLINE_GATES = ["key-mode", "helper", "plain-absent", "isolated", "tools"]


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


def _make_installed_home(tmp_path: Path) -> Path:
    """A fake HOME with a correctly installed isolated Exa config."""
    home = tmp_path
    # Key file.
    kd = home / ".config" / "claude-maas"
    kd.mkdir(parents=True)
    (kd / "exa-api-key").write_text(KEY_VALUE + "\n")
    (kd / "exa-api-key").chmod(0o600)
    # Isolated profile.
    cm = home / ".claude-maas"
    cm.mkdir(parents=True)
    helper = str(ROOT / "scripts" / "exa-headers-helper.py")
    (cm / ".claude.json").write_text(json.dumps({
        "mcpServers": {
            "exa-search": {"type": "http", "url": EXA_URL, "headersHelper": helper},
        }
    }, indent=2))
    (cm / "settings.json").write_text(json.dumps({
        "permissions": {"allow": [PERM_SEARCH, PERM_FETCH]},
    }, indent=2))
    # Plain Claude with no Exa.
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".claude.json").write_text(json.dumps({"mcpServers": {}}))
    (home / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": []}}))
    return home


@pytest.fixture()
def run_verify(tmp_path: Path):
    home = _make_installed_home(tmp_path)
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(home)

    def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(VERIFY), *args],
            env=base_env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return _run


# ---------------------------------------------------------------------------
# Offline mode runs all offline gates and exits 0 on a clean install
# ---------------------------------------------------------------------------


def test_offline_mode_runs_all_gates(run_verify):
    result = run_verify("--offline", stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, result.stderr
    for gate in OFFLINE_GATES:
        assert gate in result.stdout, f"gate '{gate}' not reported"


def test_offline_mode_passes_on_clean_install(run_verify):
    result = run_verify("--offline", stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, result.stderr
    # Each offline gate should report PASS.
    for gate in OFFLINE_GATES:
        # The gate line or a PASS marker near it.
        assert gate in result.stdout


# ---------------------------------------------------------------------------
# Gate failures are reported
# ---------------------------------------------------------------------------


def test_fails_when_key_missing(tmp_path: Path):
    home = tmp_path
    cm = home / ".claude-maas"
    cm.mkdir(parents=True)
    (cm / ".claude.json").write_text(json.dumps({"mcpServers": {
        "exa-search": {"type": "http", "url": EXA_URL, "headersHelper": "/x"}
    }}))
    (cm / "settings.json").write_text(json.dumps({"permissions": {"allow": [PERM_SEARCH, PERM_FETCH]}}))
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".claude.json").write_text(json.dumps({"mcpServers": {}}))
    (home / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": []}}))
    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(VERIFY), "--offline"], env=env, input=KEY_VALUE + "\n",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "key-mode" in result.stdout


def test_fails_when_plain_has_exa(tmp_path: Path):
    home = _make_installed_home(tmp_path)
    # Inject legacy Exa into plain Claude.
    pj = home / ".claude" / ".claude.json"
    data = json.loads(pj.read_text())
    data["mcpServers"]["exa-search"] = {"command": "exa-mcp"}
    pj.write_text(json.dumps(data))
    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(VERIFY), "--offline"], env=env, input=KEY_VALUE + "\n",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "plain-absent" in result.stdout


def test_fails_when_isolated_missing(tmp_path: Path):
    home = _make_installed_home(tmp_path)
    # Remove the isolated exa-search entry.
    cj = home / ".claude-maas" / ".claude.json"
    data = json.loads(cj.read_text())
    del data["mcpServers"]["exa-search"]
    cj.write_text(json.dumps(data))
    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(VERIFY), "--offline"], env=env, input=KEY_VALUE + "\n",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "isolated" in result.stdout


def test_fails_when_wrong_tools(tmp_path: Path):
    home = _make_installed_home(tmp_path)
    # Add a prohibited tool permission.
    sj = home / ".claude-maas" / "settings.json"
    data = json.loads(sj.read_text())
    data["permissions"]["allow"].append("mcp__exa-search__exa_contents")
    sj.write_text(json.dumps(data))
    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(VERIFY), "--offline"], env=env, input=KEY_VALUE + "\n",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "tools" in result.stdout


# ---------------------------------------------------------------------------
# Key never leaks
# ---------------------------------------------------------------------------


def test_key_never_in_output(run_verify):
    result = run_verify("--offline", stdin=KEY_VALUE + "\n")
    combined = result.stdout + result.stderr
    assert KEY_VALUE not in combined


# ---------------------------------------------------------------------------
# No mode arg defaults to offline (safe, no network)
# ---------------------------------------------------------------------------


def test_default_is_offline(run_verify):
    result = run_verify(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, result.stderr
    for gate in OFFLINE_GATES:
        assert gate in result.stdout
