"""Meta-test: real HOME config must not be modified by the test suite.

PRD CLIENT_CONFIG_PROTECTION §5.2 (acceptance #2):

    Run a representative slice of the test suite and verify that
    $HOME/.config/claude-maas/{config.json,api-key,manifest.json}
    are byte-identical before and after. Any change is a failure.

This is the meta-gate that would have caught the 2026-08-20 port-38123
incident: a test run that silently rewrote the real
~/.config/claude-maas/config.json from port 3000 to 38123, breaking
claude-maas for ~3 hours while all gates stayed green.

We snapshot the *real* HOME (not tmp_path) because the incident was
caused by tests whose HOME isolation failed — the only way to catch that
class of bug is to monitor the real HOME.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The three files that the incident corrupted.
CONFIG_FILES = ["config.json", "api-key", "manifest.json"]


def _real_config_dir() -> Path:
    """The real user's claude-maas config directory."""
    home = os.environ.get("HOME", "")
    return Path(home) / ".config" / "claude-maas"


def _snapshot() -> dict[str, str]:
    """SHA-256 of each config file that exists. Missing files → absent key."""
    snap: dict[str, str] = {}
    d = _real_config_dir()
    for name in CONFIG_FILES:
        p = d / name
        if p.exists() and p.is_file():
            snap[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


# A representative slice of tests that exercise install paths.
# These are the tests most likely to touch the client config:
#   - test_setup.py: claude-maas-setup.sh contract tests
#   - test_bootstrap.py: bootstrap.sh contract tests
# We do NOT run the full suite (too slow for a meta-test) — just the
# install-path tests that could clobber the config.
TEST_SLICE = ["tests/test_setup.py", "tests/test_bootstrap.py"]


def test_real_home_config_unchanged_by_test_slice():
    """Acceptance #2: running the install-path test slice must not modify
    any file in the real $HOME/.config/claude-maas/."""
    before = _snapshot()

    # Run the test slice. We use subprocess to get a clean process —
    # pytest's own process has already imported these modules, but the
    # subprocess runs them fresh with the real HOME.
    result = subprocess.run(
        ["python3", "-m", "pytest", *TEST_SLICE, "-q", "-x",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )

    after = _snapshot()

    # The slice itself must pass (we're not testing the tests, just that
    # they don't clobber the real HOME — but if they crash that's also
    # a problem worth surfacing).
    assert result.returncode == 0, \
        f"test slice failed — output:\n{result.stdout}\n{result.stderr}"

    # Every file that existed before must be byte-identical after.
    for name, before_hash in before.items():
        assert name in after, \
            f"config file {name} was DELETED by the test slice"
        assert after[name] == before_hash, \
            f"config file {name} was MODIFIED by the test slice " \
            f"(sha256 changed from {before_hash[:16]}… to {after[name][:16]}…)"

    # No new config files should appear either.
    new_files = set(after) - set(before)
    assert not new_files, \
        f"test slice created new config files in real HOME: {new_files}"
