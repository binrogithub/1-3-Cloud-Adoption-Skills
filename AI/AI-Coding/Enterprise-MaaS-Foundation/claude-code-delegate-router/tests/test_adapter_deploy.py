"""Tests for adapter/deploy.sh and adapter/rollback.sh.

Verifies the adapter source and legacy fixture are in the repo, the legacy
fixture matches the known production artifact checksum, the candidate adapter
differs from legacy (it has reliability controls), deploy records checksums,
and the scripts never touch the env file.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapter" / "server.js"
LEGACY = ROOT / "tests" / "fixtures" / "legacy_server.js"
DEPLOY = ROOT / "adapter" / "deploy.sh"
ROLLBACK = ROOT / "adapter" / "rollback.sh"

PROD_SHA = "b0d7df992d24b2746652d4c1554e45b74c51fc34de4a1885be3bd355f522bd75"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Adapter source and legacy fixture are in the repo
# ---------------------------------------------------------------------------


def test_adapter_source_exists():
    assert ADAPTER.is_file(), "adapter/server.js must exist"


def test_legacy_fixture_exists():
    assert LEGACY.is_file(), "legacy fixture must exist for red tests"


def test_legacy_fixture_checksum_matches_production():
    """The frozen legacy fixture must match the known production artifact."""
    assert _sha256(LEGACY) == PROD_SHA


def test_candidate_differs_from_legacy():
    """The candidate adapter must differ from the legacy artifact (has controls)."""
    assert _sha256(ADAPTER) != _sha256(LEGACY), \
        "candidate adapter identical to legacy — reliability controls missing"


def test_candidate_has_lifecycle_require():
    """The candidate adapter must require the lifecycle controller."""
    content = ADAPTER.read_text(encoding="utf-8")
    assert "lifecycle.js" in content, "adapter missing lifecycle.js require"
    assert "RequestLifecycleController" in content, "adapter missing controller"


# ---------------------------------------------------------------------------
# Deploy/rollback scripts exist and are valid bash
# ---------------------------------------------------------------------------


def test_deploy_script_exists():
    assert DEPLOY.is_file()


def test_rollback_script_exists():
    assert ROLLBACK.is_file()


def test_deploy_script_syntax_valid():
    result = subprocess.run(["bash", "-n", str(DEPLOY)], capture_output=True)
    assert result.returncode == 0


def test_rollback_script_syntax_valid():
    result = subprocess.run(["bash", "-n", str(ROLLBACK)], capture_output=True)
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Scripts never touch the env file
# ---------------------------------------------------------------------------


def test_deploy_script_does_not_write_env_file():
    """The deploy script must not modify /etc/claude-code-proxy/maas.env."""
    content = DEPLOY.read_text()
    env_path = "/etc/claude-code-proxy/maas.env"
    # The script may READ the env file path but must not WRITE to it.
    # Look for write operations targeting the env file.
    assert f"echo > {env_path}" not in content
    assert f"cat > {env_path}" not in content
    assert f"tee {env_path}" not in content


def test_rollback_script_does_not_write_env_file():
    content = ROLLBACK.read_text()
    env_path = "/etc/claude-code-proxy/maas.env"
    assert f"echo > {env_path}" not in content
    assert f"cat > {env_path}" not in content
    assert f"tee {env_path}" not in content


# ---------------------------------------------------------------------------
# Deploy must ship every runtime dependency, not just server.js
#
# Regression gate: deploy.sh copied only server.js. The candidate server.js
# require()s lifecycle.js at load time, so deploying it alone would have put
# claude-code-maas-proxy.service into a crash-restart loop and taken Claude
# Code on this host offline. The old suite only checked `bash -n`.
# ---------------------------------------------------------------------------

import re
import socket
import time

LIFECYCLE = ROOT / "adapter" / "lifecycle.js"


def _local_requires(js: Path) -> set[str]:
    """Local files the given JS module requires at load time."""
    text = js.read_text(encoding="utf-8")
    names = set(re.findall(r'require\(path\.join\(__dirname,\s*["\']([^"\']+)["\']\)\)', text))
    names |= set(re.findall(r'require\(["\']\./([^"\']+)["\']\)', text))
    return names


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_adapter_local_requires_are_deployed():
    """Every local module server.js requires must be copied by deploy.sh."""
    deploy_text = DEPLOY.read_text(encoding="utf-8")
    missing = [name for name in _local_requires(ADAPTER) if name not in deploy_text]
    assert not missing, f"deploy.sh never copies runtime dependencies: {missing}"


def test_deploy_installs_a_loadable_tree(tmp_path):
    """Deploy into a temp dest, then start the deployed server.js for real.

    A tree missing lifecycle.js cannot answer /health — this fails if deploy.sh
    ships an incomplete artifact set.
    """
    dest = tmp_path / "opt"
    env = dict(os.environ)
    env["ADAPTER_DEST_DIR"] = str(dest)
    env["ADAPTER_SERVICE"] = "no-such-unit-for-tests.service"
    result = subprocess.run(["bash", str(DEPLOY)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    assert (dest / "server.js").is_file()
    assert (dest / "lifecycle.js").is_file()
    assert _sha256(dest / "server.js") == _sha256(ADAPTER)
    assert _sha256(dest / "lifecycle.js") == _sha256(LIFECYCLE)

    port = _free_port()
    env2 = dict(os.environ)
    env2.update({
        "PROXY_PORT": str(port),
        "PROXY_HOST": "127.0.0.1",
        "ENV_FILE": str(tmp_path / "absent.env"),
        "CLAUDE_CODE_PROXY_API_KEY": "test-key",
    })
    proc = subprocess.Popen(
        ["node", str(dest / "server.js")], env=env2,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 5
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.1)
        assert ready, f"deployed adapter never listened; stderr={proc.stderr.read().decode()[:400]}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_deploy_saves_rollback_next_to_the_artifact(tmp_path):
    """The rollback copy lands in the dest directory, not inside the file path."""
    dest = tmp_path / "opt"
    dest.mkdir()
    (dest / "server.js").write_text("// previous artifact\n", encoding="utf-8")
    (dest / "lifecycle.js").write_text("// previous lifecycle\n", encoding="utf-8")
    env = dict(os.environ)
    env["ADAPTER_DEST_DIR"] = str(dest)
    env["ADAPTER_SERVICE"] = "no-such-unit-for-tests.service"

    result = subprocess.run(["bash", str(DEPLOY)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (dest / "server.js.rollback").read_text() == "// previous artifact\n"
    assert (dest / "lifecycle.js.rollback").read_text() == "// previous lifecycle\n"


def test_rollback_restores_every_saved_artifact(tmp_path):
    dest = tmp_path / "opt"
    dest.mkdir()
    (dest / "server.js").write_text("// previous artifact\n", encoding="utf-8")
    (dest / "lifecycle.js").write_text("// previous lifecycle\n", encoding="utf-8")
    env = dict(os.environ)
    env["ADAPTER_DEST_DIR"] = str(dest)
    env["ADAPTER_SERVICE"] = "no-such-unit-for-tests.service"

    assert subprocess.run(["bash", str(DEPLOY)], env=env, capture_output=True).returncode == 0
    result = subprocess.run(["bash", str(ROLLBACK)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (dest / "server.js").read_text() == "// previous artifact\n"
    assert (dest / "lifecycle.js").read_text() == "// previous lifecycle\n"


# ---------------------------------------------------------------------------
# The service really does get restarted
#
# Regression gate: unit detection was `systemctl list-units --all | grep -q
# "$SERVICE"`. Under `set -o pipefail`, grep exits at the first match, systemctl
# dies of SIGPIPE (141), and the pipeline reports failure — so an installed unit
# was reported "not found" and deploy silently skipped the restart, leaving the
# old adapter running in memory with a new artifact on disk.
# ---------------------------------------------------------------------------

STUB_SYSTEMCTL = r"""#!/usr/bin/env bash
# Stub systemctl: the unit exists. `list-units` prints a long listing so an
# early-exiting `grep -q` reader triggers SIGPIPE, as the real one does.
log="$STUB_LOG"
case "${1:-}" in
    cat) echo "[Unit]"; echo "Description=stub"; exit 0 ;;
    is-active) echo active; exit 0 ;;
    restart) echo "restart $2" >>"$log"; exit 0 ;;
    list-units)
        echo "  no-such-unit-for-tests.service loaded active running stub"
        for i in $(seq 1 20000); do echo "  filler-$i.service loaded active running filler"; done
        exit 0 ;;
    *) exit 0 ;;
esac
"""


def _stub_systemctl_env(tmp_path, dest):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "systemctl"
    stub.write_text(STUB_SYSTEMCTL, encoding="utf-8")
    stub.chmod(0o755)
    log = tmp_path / "systemctl.log"
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["STUB_LOG"] = str(log)
    env["ADAPTER_DEST_DIR"] = str(dest)
    env["ADAPTER_SERVICE"] = "no-such-unit-for-tests.service"
    return env, log


def test_deploy_restarts_the_service_when_the_unit_exists(tmp_path):
    dest = tmp_path / "opt"
    env, log = _stub_systemctl_env(tmp_path, dest)
    result = subprocess.run(["bash", str(DEPLOY)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert log.is_file(), f"deploy never restarted the unit; stdout={result.stdout}"
    assert "restart no-such-unit-for-tests.service" in log.read_text()


def test_rollback_restarts_the_service_when_the_unit_exists(tmp_path):
    dest = tmp_path / "opt"
    dest.mkdir()
    (dest / "server.js").write_text("// previous artifact\n", encoding="utf-8")
    (dest / "lifecycle.js").write_text("// previous lifecycle\n", encoding="utf-8")
    env, log = _stub_systemctl_env(tmp_path, dest)
    assert subprocess.run(["bash", str(DEPLOY)], env=env, capture_output=True).returncode == 0
    log.unlink()
    result = subprocess.run(["bash", str(ROLLBACK)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert log.is_file(), f"rollback never restarted the unit; stdout={result.stdout}"
