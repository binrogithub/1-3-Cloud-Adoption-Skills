"""D8 tests (PRD UPSTREAM_PROFILE_V1): bootstrap --profile.

  G4/G5: --profile derives every path (env file, client key, dest, service,
  client config dir); the default profile is byte-for-byte unchanged; a
  profile install generates an INDEPENDENT client key (cross-profile 401s);
  the systemd unit carries the identical hardening.

Runs bootstrap with --dry-run + an isolated root-side run for key checks.
No real systemd or production paths are touched.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"

MAAS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
KEY = "test-key-d8-0123456789"


def _run(env: dict, *args: str, isolate_service: bool = True) -> subprocess.CompletedProcess:
    """isolate_service: real (non-dry-run) installs get a nonexistent
    --service so deploy.sh can never restart the production unit on this
    host. Dry-run path-derivation tests pass isolate_service=False so the
    DERIVED service name is visible in the output."""
    argv = ["bash", str(BOOTSTRAP), "--maas-url", MAAS_URL]
    if isolate_service:
        argv += ["--service", "d8-test-no-unit.service"]
    argv += list(args)
    return subprocess.run(argv, input=KEY + "\n", env=env,
                          capture_output=True, text=True, timeout=120)


def _base_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
    env["HOME"] = str(home)
    return env


def test_profile_derives_all_paths(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run(
        _base_env(home),
        "--profile", "claude-glm", "--model", "glm-5.3", "--port", "3100",
        "--dry-run", isolate_service=False,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "/etc/claude-glm-proxy/maas.env" in out, out
    assert "/opt/claude-glm-proxy" in out
    assert "claude-glm-proxy.service" in out
    assert "/.config/claude-glm/config.json" in out
    # No doubled prefix.
    assert "claude-claude-glm" not in out


def test_default_profile_unchanged(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run(_base_env(home), "--dry-run", isolate_service=False)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "/etc/claude-code-proxy/maas.env" in out
    assert "/opt/claude-code-maas-proxy" in out
    assert "claude-code-maas-proxy.service" in out
    assert "/.config/claude-maas/config.json" in out


def test_profile_rejects_bad_names(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run(_base_env(home), "--profile", "../evil", "--dry-run")
    assert result.returncode == 1
    assert "--profile must match" in result.stderr


def test_profile_install_generates_independent_client_key(tmp_path):
    """G5: a profile install must generate its OWN client key at the derived
    path — not share the main profile's key."""
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "etc" / "claude-glm-proxy" / "maas.env"
    client_key = tmp_path / "etc" / "claude-glm-proxy" / "client.key"
    result = _run(
        _base_env(home),
        "--profile", "claude-glm", "--model", "glm-5.3", "--port", "3101",
        "--env-file", str(env_file),
        "--client-key-file", str(client_key),
        "--dest", str(tmp_path / "opt"),
        "--skip-systemd", "--skip-verify",
    )
    assert result.returncode == 0, result.stderr
    assert client_key.is_file(), "client key not generated at derived path"
    key_value = client_key.read_text().strip()
    assert len(key_value) == 64, f"expected 64-hex random key, got {len(key_value)} chars"
    # The env file must point the adapter at THIS key file.
    content = env_file.read_text()
    assert f"MAAS_CLIENT_KEY_FILE={client_key}" in content
    # Cross-profile rejection: the profile key must differ from any other
    # profile's key (here: differs from the main profile's installed key if
    # present on this host; always self-consistent otherwise).
    main_key = Path("/etc/claude-code-proxy/client.key")
    if main_key.is_file():
        assert key_value != main_key.read_text().strip(), \
            "profile shares the main client key — must be independent"


def test_profile_unit_hardening_identical():
    """G5: profile installs share the SAME unit template in bootstrap.sh, so
    they inherit the identical hardening directives. Pure source assertion —
    invoking bootstrap here would write a unit into the real
    /etc/systemd/system (test-host pollution observed once; never again)."""
    src = BOOTSTRAP.read_text()
    for directive in ("NoNewPrivileges=yes", "ProtectSystem=strict",
                      "ProtectHome=yes", "CapabilityBoundingSet=",
                      "RestrictAddressFamilies=", "LockPersonality=yes"):
        assert directive in src, f"hardening directive {directive} missing from unit template"
    # The template is emitted once and parameterized only by paths — no
    # per-profile conditional softening.
    assert src.count("NoNewPrivileges=yes") == 1
