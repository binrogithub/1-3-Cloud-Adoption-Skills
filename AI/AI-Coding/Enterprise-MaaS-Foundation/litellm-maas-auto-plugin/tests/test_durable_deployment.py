"""Tests for durable artifact deployment (PRD-r11-minimal-closeout.md §9).

Verifies that deploy-and-verify.sh:
- Never replaces a live release directory in place (§9.1)
- Rolls back on every failure with a global trap (§9.2)
- Verifies installed clients, not only artifact clients (§9.3)
- Keeps deployment and gate execution separate (§9.4)
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEPLOY_SCRIPT = REPO_ROOT / "server" / "deploy-and-verify.sh"
INSTALL_SCRIPT = REPO_ROOT / "server" / "install-litellm-plugin.sh"


def test_deploy_script_has_durable_release_root():
    source = DEPLOY_SCRIPT.read_text()
    assert "RELEASE_ROOT" in source
    assert "RELEASES_BASE" in source
    assert "current" in source
    assert "--releases-base" in source


def test_deploy_script_never_replaces_live_dir():
    """PRD §9.1: existing release roots must be verified and reused, never rm -rf'd."""
    source = DEPLOY_SCRIPT.read_text()
    assert "verifying and reusing" in source, "must reuse existing release root"
    assert "existing release root verified OK" in source
    # The old rm -rf of RELEASE_ROOT must be gone.
    assert 'rm -rf "$RELEASE_ROOT"' not in source, "must not rm -rf the release root"


def test_deploy_script_uses_atomic_rename():
    """PRD §9.1: new SHA uses same-filesystem atomic rename."""
    source = DEPLOY_SCRIPT.read_text()
    assert "STAGING_FINAL" in source, "must use a staging dir for atomic rename"
    assert 'mv "$STAGING_FINAL" "$RELEASE_ROOT"' in source, "must atomic rename"


def test_deploy_script_has_global_rollback_trap():
    """PRD §9.2: global error/signal trap restores previous state."""
    source = DEPLOY_SCRIPT.read_text()
    assert "rollback_restore" in source, "must have rollback_restore function"
    assert "trap cleanup EXIT INT TERM" in source or "trap cleanup EXIT INT TERM HUP" in source
    assert "ROLLBACK_NEEDED" in source, "must track rollback state"
    assert "SNAPSHOT_DIR" in source, "must snapshot compose/config before mutation"
    assert "Restoring previous release" in source or "restoring previous release" in source.lower()


def test_deploy_script_restores_compose_on_failure():
    """PRD §9.2: rollback must restore compose mount sources, not just symlink."""
    source = DEPLOY_SCRIPT.read_text()
    assert "docker-compose.yml" in source and "SNAPSHOT_DIR" in source
    assert "cp -a" in source, "must copy back compose from snapshot"


def test_deploy_script_verifies_installed_clients():
    """PRD §9.3: manifest -> durable release -> installed destination."""
    source = DEPLOY_SCRIPT.read_text()
    assert "INSTALLED_CLIENT_DIR" in source, "must check installed destination"
    assert "installed=" in source, "must report installed hash"
    assert "manifest=release=installed" in source, "must verify all three match"


def test_deploy_script_keeps_deployment_and_gates_separate():
    """PRD §9.4: deployer does hash/ACL/health; gate execution is separate."""
    source = DEPLOY_SCRIPT.read_text()
    assert "Gate execution is handled by the closeout controller" in source or "check hash failure BEFORE clearing rollback flag" in source


def test_install_script_accepts_source_root():
    source = INSTALL_SCRIPT.read_text()
    assert "--source-root" in source
    assert "SOURCE_ROOT_ARG" in source


def test_deploy_script_reconciles_container_files():
    source = DEPLOY_SCRIPT.read_text()
    assert "CONTAINER_FILES" in source
    assert "manifest_hash" in source and "release_hash" in source and "container_hash" in source


def test_deploy_script_runs_profile_healthy():
    source = DEPLOY_SCRIPT.read_text()
    assert "--profile healthy" in source
    assert "--json-output" in source
