"""Contract tests for scripts/verify.sh — the release verification command.

These tests verify the verifier's *contract* without requiring real network
access or a real ``claude`` binary.  They do this by constructing a fake HOME
in which every gate's underlying script is replaced with a controlled stub,
then invoking ``verify.sh`` (key on stdin) and asserting:

  * The six gates run in the documented order:
      1. config modes
      2. direct API text/stream/thinking/tools
      3. token-only Claude CLI
      4. tool round trip
      5. plain Claude isolation
      6. prohibited dependency scan
  * Each gate is reported with a PASS/FAIL verdict.
  * Any secret substring (the key read from stdin) that appears in a gate's
    raw output is **redacted** from verify.sh's final stdout/stderr.
  * verify.sh exits 1 if any required gate fails, 0 if all pass.
  * Image-unsupported is reported as a known condition, not a failure.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify.sh"

KEY_VALUE = "super-secret-maas-key-DO-NOT-LEAK"
MODEL = "glm-5.2"

# The six gate names in the exact order verify.sh must report them.
EXPECTED_GATES = [
    "config-modes",
    "direct-api",
    "token-only-claude-cli",
    "tool-round-trip",
    "plain-claude-isolation",
    "prohibited-dependency-scan",
    "launcher-entry",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_executable(path: Path, content: str) -> None:
    """Write *content* to *path* and mark it executable (0755)."""
    path.write_text(content)
    path.chmod(0o755)


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """A fake HOME with a valid 0600 api-key and 0700 config dir.

    The config layout mirrors what claude-maas-setup.sh produces so that
    verify.sh's config-modes gate can pass.
    """
    config_dir = tmp_path / ".config" / "claude-maas"
    config_dir.mkdir(parents=True)
    config_dir.chmod(0o700)

    key_file = config_dir / "api-key"
    key_file.write_text(f"{KEY_VALUE}\n")
    key_file.chmod(0o600)

    import json

    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "anthropic_base_url": "https://api-ap-southeast-1.modelarts-maas.com/anthropic",
                "model": MODEL,
                "context_tokens": 190000,
                "max_output_tokens": 32768,
            }
        )
        + "\n"
    )
    config_file.chmod(0o600)

    # Isolated CLAUDE_CONFIG_DIR.
    (tmp_path / ".claude-maas").mkdir()
    (tmp_path / ".claude-maas").chmod(0o700)

    return tmp_path


@pytest.fixture()
def fake_bin_dir(tmp_path: Path) -> Path:
    """A directory for stub scripts that verify.sh will call."""
    d = tmp_path / "fakebin"
    d.mkdir()
    return d


def _base_env(fake_home: Path, fake_bin_dir: Path) -> dict[str, str]:
    """Minimal environment with fake HOME and fakebin on PATH."""
    env: dict[str, str] = {
        "HOME": str(fake_home),
        "PATH": str(fake_bin_dir) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
    }
    for name in ("LANG", "LC_ALL", "TERM"):
        if name in os.environ:
            env[name] = os.environ[name]
    # Strip any inherited provider config.
    for k in list(env):
        if k.startswith("ANTHROPIC_"):
            env.pop(k, None)
    return env


def _run_verify(
    fake_home: Path,
    fake_bin_dir: Path,
    *,
    key: str = KEY_VALUE,
    env_override: dict[str, str] | None = None,
    use_test_helpers: bool = True,
) -> subprocess.CompletedProcess:
    """Invoke verify.sh with the key on stdin and return the result.

    By default we point verify.sh at the stub helpers via the explicit
    ``VERIFY_TEST_HELPERS_DIR`` test override, so the existing orchestration
    tests continue to exercise the verifier with controlled stubs.  The
    PATH-attack test calls with ``use_test_helpers=False`` to exercise real
    release-mode resolution.
    """
    env = _base_env(fake_home, fake_bin_dir)
    if use_test_helpers:
        env["VERIFY_TEST_HELPERS_DIR"] = str(fake_bin_dir)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        ["bash", str(VERIFY)],
        input=key + "\n",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Gate ordering and presence
# ---------------------------------------------------------------------------


def test_verify_sh_exists():
    assert VERIFY.is_file(), "scripts/verify.sh must exist"


def test_verify_sh_is_executable():
    assert VERIFY.stat().st_mode & stat.S_IXUSR, "verify.sh must be executable"


def test_all_six_gates_reported_in_order(fake_home, fake_bin_dir):
    """verify.sh must report all six gates in the documented order.

    We stub every gate to succeed so we can observe the full happy-path
    sequence.  Each stub writes a unique marker line so we can confirm the
    underlying script was actually invoked.
    """
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    result = _run_verify(fake_home, fake_bin_dir)

    assert result.returncode == 0, f"verify.sh should pass when all gates pass\nstdout: {result.stdout}\nstderr: {result.stderr}"

    # Each gate name must appear in the output.
    for gate in EXPECTED_GATES:
        assert gate in result.stdout, f"gate '{gate}' missing from output:\n{result.stdout}"

    # The gates must appear in order.
    positions = {gate: result.stdout.index(gate) for gate in EXPECTED_GATES}
    for i in range(len(EXPECTED_GATES) - 1):
        g1, g2 = EXPECTED_GATES[i], EXPECTED_GATES[i + 1]
        assert positions[g1] < positions[g2], (
            f"gate '{g1}' must appear before '{g2}'\n{result.stdout}"
        )


def test_each_gate_reports_pass_or_fail(fake_home, fake_bin_dir):
    """Each gate line must include a PASS or FAIL verdict."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 0

    for gate in EXPECTED_GATES:
        # Find the line containing this gate name.
        gate_lines = [ln for ln in result.stdout.splitlines() if gate in ln]
        assert gate_lines, f"no output line for gate '{gate}'"
        # At least one of those lines must mention PASS or FAIL.
        assert any("PASS" in ln or "FAIL" in ln for ln in gate_lines), (
            f"gate '{gate}' line lacks PASS/FAIL verdict:\n{gate_lines}"
        )


# ---------------------------------------------------------------------------
# Exit code semantics
# ---------------------------------------------------------------------------


def test_exit_zero_when_all_gates_pass(fake_home, fake_bin_dir):
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 0, f"expected exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_exit_one_when_any_gate_fails(fake_home, fake_bin_dir):
    """A single failing gate must cause exit 1."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    # Make the direct-api gate fail.
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        _stub_script("direct-api", exit_code=1),
    )
    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 1, f"expected exit 1 on gate failure\nstdout: {result.stdout}\nstderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


def test_secret_redacted_from_stdout(fake_home, fake_bin_dir):
    """The key read from stdin must never appear in verify.sh stdout.

    We install a stub that deliberately prints the key (simulating a
    misbehaving subprocess leaking it).  verify.sh must scrub it.
    """
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    # Override the direct-api stub to echo the key into its output.
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        _leaky_stub("direct-api"),
    )
    result = _run_verify(fake_home, fake_bin_dir)
    assert KEY_VALUE not in result.stdout, (
        f"key leaked into stdout:\n{result.stdout}"
    )


def test_secret_redacted_from_stderr(fake_home, fake_bin_dir):
    """The key must never appear in verify.sh stderr either."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        _leaky_stub_stderr("direct-api"),
    )
    result = _run_verify(fake_home, fake_bin_dir)
    assert KEY_VALUE not in result.stderr, (
        f"key leaked into stderr:\n{result.stderr}"
    )


def test_secret_substring_redacted(fake_home, fake_bin_dir):
    """Even a substring of the key embedded in a longer error must be scrubbed."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    # Stub prints a longer string that contains the key as a substring.
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        _leaky_substring_stub("direct-api", KEY_VALUE),
    )
    result = _run_verify(fake_home, fake_bin_dir)
    assert KEY_VALUE not in result.stdout, (
        f"key substring leaked into stdout:\n{result.stdout}"
    )
    assert KEY_VALUE not in result.stderr


# ---------------------------------------------------------------------------
# Image-unsupported is not a failure
# ---------------------------------------------------------------------------


def test_image_unsupported_is_known_condition_not_failure(fake_home, fake_bin_dir):
    """If the direct-api probe reports image as known-unsupported, verify.sh
    must not treat that as a failure."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    # Override direct-api to print the known-unsupported marker and exit 0.
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        _image_unsupported_stub(),
    )
    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 0, (
        f"image-unsupported should not cause failure\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Key read from stdin, never argv
# ---------------------------------------------------------------------------


def test_key_read_from_stdin_not_argv(fake_home, fake_bin_dir):
    """verify.sh must read the key from stdin, never from argv.

    We invoke verify.sh with no argv (only stdin).  If it required the key
    as an argument it would fail to find it.
    """
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 0, f"verify.sh should read key from stdin\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_verify_fails_on_empty_stdin(fake_home, fake_bin_dir):
    """An empty key on stdin must cause failure, not a silent pass."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    env = _base_env(fake_home, fake_bin_dir)
    result = subprocess.run(
        ["bash", str(VERIFY)],
        input="\n",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, "empty key should cause failure"


# ---------------------------------------------------------------------------
# set -euo pipefail discipline
# ---------------------------------------------------------------------------


def test_verify_uses_strict_shell_options(fake_home, fake_bin_dir):
    """verify.sh must use 'set -euo pipefail' for safe shell behavior."""
    text = VERIFY.read_text()
    # The set directive must appear early (within the first 30 lines).
    head = "\n".join(text.splitlines()[:30])
    assert "set -e" in head, "verify.sh must use 'set -e'"
    assert "pipefail" in head, "verify.sh must use 'set -o pipefail'"


# ---------------------------------------------------------------------------
# PATH-substitution attack (PRD §G-RC2, §FR-4)
# ---------------------------------------------------------------------------


def test_path_stub_does_not_replace_checkout_helpers(fake_home, fake_bin_dir):
    """Always-pass PATH stubs must not be executed by release mode.

    We place sentinel-writing stubs named identically to the three release
    helpers at the FRONT of PATH.  We then run verify.sh WITHOUT the
    test-helpers override (so it must use the checkout helpers).  The sentinel
    files must not exist — proving the stubs were bypassed.  verify.sh must not
    emit a release PASS.

    To keep the test fast, we point the config base_url at a closed localhost
    port (connection refused instantly) and install a fake ``claude`` that
    exits 0 with empty output — so the real checkout helpers fail quickly
    rather than hanging on real network/CLI.
    """
    import json as _json

    # Make the real live_maas_probe.py fail fast (connection refused).
    config_file = fake_home / ".config" / "claude-maas" / "config.json"
    config_file.write_text(
        _json.dumps(
            {
                "anthropic_base_url": "http://127.0.0.1:1/anthropic",
                "model": MODEL,
                "context_tokens": 190000,
                "max_output_tokens": 32768,
            }
        )
        + "\n"
    )
    config_file.chmod(0o600)

    # Fake claude that exits 0 with empty output (e2e probe fails on empty).
    _make_executable(
        fake_bin_dir / "claude",
        "#!/usr/bin/env bash\nexit 0\n",
    )

    sentinel_dir = fake_home / "sentinels"
    sentinel_dir.mkdir()

    for name in ("live_maas_probe.py", "claude_e2e_probe.sh", "check-prohibited-dependencies.py"):
        _make_executable(
            fake_bin_dir / name,
            f"""#!/usr/bin/env bash
touch "{sentinel_dir / name}.sentinel" 2>/dev/null || true
exit 0
""",
        )

    # Run without VERIFY_TEST_HELPERS_DIR — release mode.
    env = _base_env(fake_home, fake_bin_dir)
    result = subprocess.run(
        ["bash", str(VERIFY)],
        input=KEY_VALUE + "\n",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # The PATH stubs must not have been executed.
    for name in ("live_maas_probe.py", "claude_e2e_probe.sh", "check-prohibited-dependencies.py"):
        assert not (sentinel_dir / f"{name}.sentinel").exists(), (
            f"PATH stub {name} was executed instead of the checkout helper"
        )

    # verify.sh must not emit a clean release PASS.
    assert "all gates PASS" not in result.stdout, (
        f"PATH stubs must not produce a release PASS\nstdout: {result.stdout}"
    )


def test_helper_provenance_logged(fake_home, fake_bin_dir):
    """verify.sh must log the SHA-256 of each pinned helper.

    In release mode (no test override) the digests must match the checkout
    helpers.  We use a fast-fail config so the real helpers don't hang.
    """
    import hashlib
    import json as _json

    config_file = fake_home / ".config" / "claude-maas" / "config.json"
    config_file.write_text(
        _json.dumps(
            {
                "anthropic_base_url": "http://127.0.0.1:1/anthropic",
                "model": MODEL,
                "context_tokens": 190000,
                "max_output_tokens": 32768,
            }
        )
        + "\n"
    )
    config_file.chmod(0o600)
    _make_executable(fake_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    result = _run_verify(fake_home, fake_bin_dir, use_test_helpers=False)
    for rel in (
        "tests/live_maas_probe.py",
        "tests/claude_e2e_probe.sh",
        "tests/claude_maas_launcher_probe.sh",
        "scripts/check-prohibited-dependencies.py",
    ):
        digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert digest in result.stdout, (
            f"SHA-256 of {rel} ({digest}) missing from verify output\n{result.stdout}"
        )


def test_test_helpers_marked_untrusted(fake_home, fake_bin_dir):
    """When VERIFY_TEST_HELPERS_DIR is set, output must be marked UNTRUSTED."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    result = _run_verify(
        fake_home, fake_bin_dir,
        env_override={"VERIFY_TEST_HELPERS_DIR": str(fake_bin_dir)},
    )
    assert "UNTRUSTED_TEST_RESULT" in result.stdout, (
        f"test-mode results must be marked UNTRUSTED_TEST_RESULT\n{result.stdout}"
    )
    # A clean release PASS must not appear in test mode.
    assert "all gates PASS" not in result.stdout


# ---------------------------------------------------------------------------
# plain-claude-isolation observability (PRD §G-RC3, §FR-5)
# ---------------------------------------------------------------------------


def test_plain_claude_gate_invokes_version(tmp_path, fake_home, fake_bin_dir):
    """The isolation gate must actually invoke `claude --version`.

    We install a recording fake claude that writes its argv to a file, plus a
    claude-maas stub for resolve-binary.  We run only the isolation gate by
    making the other gates pass, then inspect the recording.
    """
    _install_all_pass_stubs(fake_home, fake_bin_dir)

    record_file = tmp_path / "claude_argv_record"
    # Override claude to record argv and respond to --version.
    _make_executable(
        fake_bin_dir / "claude",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$@" >"{record_file}"
if [[ "${{1:-}}" == "--version" ]]; then
    echo "claude-stub 1.0.0"
    exit 0
fi
exit 0
""",
    )

    result = _run_verify(fake_home, fake_bin_dir)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert record_file.exists(), "claude --version was never invoked"
    recorded = record_file.read_text()
    assert "--version" in recorded, (
        f"isolation gate must invoke --version, got argv: {recorded}"
    )


def test_plain_claude_gate_clears_maas_env(tmp_path, fake_home, fake_bin_dir):
    """The subprocess running claude --version must have no ANTHROPIC_* vars."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)

    env_record = tmp_path / "claude_env_record"
    # Recording claude that dumps its environment to a file.
    _make_executable(
        fake_bin_dir / "claude",
        f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "--version" ]]; then
    env >"{env_record}"
    echo "claude-stub 1.0.0"
    exit 0
fi
exit 0
""",
    )

    # Run with MaaS vars set in the verifier environment — they must be cleared
    # in the claude --version subprocess.
    result = _run_verify(
        fake_home, fake_bin_dir,
        env_override={
            "ANTHROPIC_BASE_URL": "https://leak.example.com",
            "ANTHROPIC_AUTH_TOKEN": "leak-token",
            "ANTHROPIC_MODEL": "leak-model",
        },
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert env_record.exists(), "claude --version was never invoked"
    env_dump = env_record.read_text()
    assert "ANTHROPIC_BASE_URL" not in env_dump, "MaaS base URL leaked into claude --version subprocess"
    assert "ANTHROPIC_AUTH_TOKEN" not in env_dump, "MaaS token leaked into claude --version subprocess"
    assert "ANTHROPIC_MODEL" not in env_dump, "MaaS model leaked into claude --version subprocess"
    assert "ANTHROPIC_API_KEY" not in env_dump, "ANTHROPIC_API_KEY leaked into claude --version subprocess"


def test_plain_claude_gate_rejects_wrapper(tmp_path, fake_home, fake_bin_dir):
    """If plain claude resolves to claude-maas, the gate must FAIL."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)

    # Make `claude` a symlink to `claude-maas` (wrapper recursion).
    (fake_bin_dir / "claude").unlink()
    (fake_bin_dir / "claude").symlink_to(fake_bin_dir / "claude-maas")

    result = _run_verify(fake_home, fake_bin_dir)
    assert "plain-claude-isolation: FAIL" in result.stdout, (
        f"gate must reject wrapper recursion\n{result.stdout}"
    )
    assert "PLAIN_CLAUDE_WRAPPED" in result.stdout


def test_plain_claude_gate_rejects_binary_mismatch(tmp_path, fake_home, fake_bin_dir):
    """If plain claude and claude-maas resolve to different binaries, FAIL."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)

    # Make claude-maas report a different binary than the fake claude.
    other_bin = tmp_path / "other-claude"
    _make_executable(other_bin, "#!/usr/bin/env bash\necho other\nexit 0\n")
    _make_executable(
        fake_bin_dir / "claude-maas",
        f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "resolve-binary" ]]; then
    printf '%s\\t%s\\n' "{other_bin}" "aaa"
    exit 0
fi
exit 0
""",
    )

    result = _run_verify(fake_home, fake_bin_dir)
    assert "plain-claude-isolation: FAIL" in result.stdout, (
        f"gate must reject binary mismatch\n{result.stdout}"
    )


def test_plain_claude_gate_fails_when_claude_maas_absent(tmp_path, fake_home, fake_bin_dir):
    """If claude-maas is not on PATH, the sameness check must FAIL, not pass."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    # Remove claude-maas from PATH.
    (fake_bin_dir / "claude-maas").unlink()

    # Use a PATH that only contains fake_bin_dir + minimal system bins, but
    # NOT /usr/local/bin where a system claude-maas might live.
    result = _run_verify(
        fake_home, fake_bin_dir,
        env_override={"PATH": str(fake_bin_dir) + os.pathsep + "/usr/bin:/bin"},
    )
    assert "plain-claude-isolation: FAIL" in result.stdout, (
        f"gate must FAIL when claude-maas is absent (sameness unprovable)\n{result.stdout}"
    )


def test_plain_claude_gate_fails_when_resolve_binary_errors(tmp_path, fake_home, fake_bin_dir):
    """If `claude-maas resolve-binary` exits non-zero, the gate must FAIL."""
    _install_all_pass_stubs(fake_home, fake_bin_dir)
    _make_executable(
        fake_bin_dir / "claude-maas",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "resolve-binary" ]]; then
    exit 1
fi
exit 0
""",
    )

    result = _run_verify(
        fake_home, fake_bin_dir,
        env_override={"PATH": str(fake_bin_dir) + os.pathsep + "/usr/bin:/bin"},
    )
    assert "plain-claude-isolation: FAIL" in result.stdout, (
        f"gate must FAIL when resolve-binary errors\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Stub builders
# ---------------------------------------------------------------------------


def _stub_script(gate: str, exit_code: int = 0) -> str:
    """A stub script that prints its gate name and exits with *exit_code*."""
    return f"""#!/usr/bin/env bash
echo "{gate}: stub ok"
exit {exit_code}
"""


def _leaky_stub(gate: str) -> str:
    """A stub that prints the key (read from its own argv/env) to stdout.

    verify.sh passes the key via stdin to sub-stubs, so we read it from stdin
    here to simulate a subprocess that leaks it.
    """
    return f"""#!/usr/bin/env bash
IFS= read -r _k || true
echo "{gate}: error detail with key=$_k"
exit 0
"""


def _leaky_stub_stderr(gate: str) -> str:
    """A stub that prints the key to stderr."""
    return f"""#!/usr/bin/env bash
IFS= read -r _k || true
echo "{gate}: error detail with key=$_k" >&2
exit 0
"""


def _leaky_substring_stub(gate: str, key: str) -> str:
    """A stub that embeds the key in a longer error string."""
    return f"""#!/usr/bin/env bash
IFS= read -r _k || true
echo "{gate}: connection failed for token=[$_k] at host example.com"
exit 0
"""


def _image_unsupported_stub() -> str:
    """A stub that reports image as known-unsupported and exits 0."""
    return """#!/usr/bin/env bash
echo "image: HTTP 400 — known-unsupported"
echo "overall: PASS"
exit 0
"""


def _install_all_pass_stubs(fake_home: Path, fake_bin_dir: Path) -> None:
    """Install stubs for every script verify.sh invokes so all gates pass.

    verify.sh calls:
      - live_maas_probe.py   (direct API canary)
      - claude_e2e_probe.sh  (token-only Claude CLI + tool round trip)
      - check-prohibited-dependencies.py
      - plain `claude`       (isolation check)

    We stub each to exit 0.  The config-modes gate is satisfied by the
    fake_home fixture's real 0600/0700 files.
    """
    # live_maas_probe.py — direct API canary (all probes pass).
    _make_executable(
        fake_bin_dir / "live_maas_probe.py",
        """#!/usr/bin/env bash
# Stub: consume key from stdin, report all probes pass.
IFS= read -r _k || true
echo "text: HTTP 200 — PASS"
echo "stream: HTTP 200 — PASS"
echo "thinking: HTTP 200 — PASS"
echo "tool-auto: HTTP 200 — PASS"
echo "tool-forced: HTTP 200 — PASS"
echo "image: HTTP 400 — known-unsupported"
echo "overall: PASS"
exit 0
""",
    )

    # claude_e2e_probe.sh — token-only Claude CLI + tool round trip.
    _make_executable(
        fake_bin_dir / "claude_e2e_probe.sh",
        """#!/usr/bin/env bash
echo "claude_e2e_probe: model=glm-5.2 ok"
echo "claude_e2e_probe: tool round trip ok"
exit 0
""",
    )

    # check-prohibited-dependencies.py — no offenders.
    _make_executable(
        fake_bin_dir / "check-prohibited-dependencies.py",
        """#!/usr/bin/env bash
echo "no prohibited dependencies found"
exit 0
""",
    )

    # claude — stub for the isolation check.  Handles --version and records
    # that the MaaS env was cleared in the subprocess.
    _make_executable(
        fake_bin_dir / "claude",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
    echo "claude-stub 1.0.0"
    exit 0
fi
echo "claude stub ok"
exit 0
""",
    )

    # claude-maas — stub for resolve-binary diagnostic used by the isolation
    # gate, and for --print --output-format json used by the launcher probe.
    # Prints the fake claude path and a dummy digest for resolve-binary;
    # emits valid JSON with modelUsage for --print.
    _make_executable(
        fake_bin_dir / "claude-maas",
        f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "resolve-binary" ]]; then
    printf '%s\\t%s\\n' "{fake_bin_dir / 'claude'}" "deadbeef"
    exit 0
fi
if [[ "${{1:-}}" == "--print" ]]; then
    # Emit valid JSON for the launcher probe.
    # Touch the marker file if the prompt asks for it.
    for arg in "$@"; do
        case "$arg" in
            touch\\ *) touch "${{arg#touch }}" 2>/dev/null || true ;;
        esac
    done
    printf '{{"is_error":false,"stop_reason":"end_turn","modelUsage":{{"glm-5.2":{{"inputTokens":1,"outputTokens":1}}}}}}\\n'
    exit 0
fi
exit 0
""",
    )

    # claude_maas_launcher_probe.sh — stub for the launcher-entry gate.
    _make_executable(
        fake_bin_dir / "claude_maas_launcher_probe.sh",
        """#!/usr/bin/env bash
echo "LAUNCHER_OK: stop_reason=end_turn, modelUsage keys=['glm-5.2']"
echo "claude_maas_launcher_probe: PASS"
exit 0
""",
    )
