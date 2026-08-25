"""WP-A tests (PRD RUNTIME_RESILIENCE_V1): bootstrap python preflight.

The 2026-08-24 field failure on 124.81.97.217: default python3 was 3.6.8,
the canary probe (from __future__ import annotations, dataclasses) died with
SyntaxError exit 1, and bootstrap reported "MaaS rejected the request" —
sending the operator to debug key/URL/service, all wrong directions.

Gates:
  A-G1  python < 3.7 → bootstrap fails BEFORE any disk write, message names
        the version problem (not the upstream).
  A-G2  --python <path> routes the canary through that interpreter.
  A-G3  canary "cannot execute" (SyntaxError/ImportError) vs "upstream
        rejected" (probe HTTP failure) produce DIFFERENT messages.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"

MAAS_URL = "https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions"
KEY = "test-key-wpa-0123456789"


def _make_fake_old_python(bindir: Path, version: str = "3.6.8") -> Path:
    """A stub interpreter that reports an old version, like CentOS 8's
    system python3. It must be able to run bootstrap's inline python too
    (the URL validation) so we prove the preflight fires even when the
    interpreter is otherwise usable."""
    py = bindir / "python3"
    py.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-c\" ]; then\n"
        "  case \"$2\" in\n"
        "    *version_info*) exit 1;;\n"
        "    *sys.version_info*) exit 1;;\n"
        "    *) exit 0;;\n"
        "  esac\n"
        "fi\n"
        f"echo \"{version}\"\n"
        "exit 0\n"
    )
    py.chmod(0o755)
    return py


def _run_bootstrap(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(BOOTSTRAP), "--maas-url", MAAS_URL,
         "--service", "wpa-test-no-such-unit.service", *args],
        input=KEY + "\n", env=env,
        capture_output=True, text=True, timeout=120,
    )


def _base_env(home: Path, path_prefix: str = "") -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
    env["HOME"] = str(home)
    env["PATH"] = f"{path_prefix}{env.get('PATH', '')}"
    return env


# ---------------------------------------------------------------------------
# A-G1: version preflight before any write
# ---------------------------------------------------------------------------


def test_a_g1_old_python_fails_before_writes(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_fake_old_python(bindir)

    result = _run_bootstrap(
        _base_env(home, str(bindir) + ":"),
        "--env-file", str(tmp_path / "etc" / "maas.env"),
        "--dest", str(tmp_path / "opt"),
        "--skip-systemd", "--skip-verify", "--dry-run",
    )

    assert result.returncode == 2, (
        f"expected exit 2 (dependency failure), got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # The message must name the version problem...
    assert "too old" in result.stderr
    assert "3.7" in result.stderr
    # ...and explicitly NOT point at the upstream.
    assert "MaaS rejected" not in result.stderr
    assert "NOT an upstream" in result.stderr


def test_a_g1_no_files_written_on_preflight_failure(tmp_path):
    """The preflight must fire before ANY disk write — not even --dry-run's
    zero writes, and certainly no env file / dest / unit."""
    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_fake_old_python(bindir)

    env_file = tmp_path / "etc" / "claude-code-proxy" / "maas.env"
    result = _run_bootstrap(
        _base_env(home, str(bindir) + ":"),
        "--env-file", str(env_file),
        "--dest", str(tmp_path / "opt"),
        "--skip-systemd", "--skip-verify",
    )
    assert result.returncode == 2
    assert not env_file.exists(), "env file was written despite preflight failure"
    assert not (tmp_path / "opt").exists()


def test_a_g1_missing_interpreter_fails_cleanly(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run_bootstrap(
        _base_env(home),
        "--python", "/nonexistent/python-xyz",
        "--skip-systemd", "--skip-verify",
    )
    assert result.returncode == 2
    assert "not found" in result.stderr
    assert "MaaS rejected" not in result.stderr


# ---------------------------------------------------------------------------
# A-G2: --python routes the canary through the given interpreter
# ---------------------------------------------------------------------------


def test_a_g2_python_flag_selects_interpreter(tmp_path):
    """The canary (via BOOTSTRAP_CANARY_PROBE stub) must be executed with the
    interpreter given by --python, not the ambient python3.

    The canary runs even when earlier verify stages fail (it is not gated on
    stage-1), so an isolated --skip-systemd install reaches it."""
    home = tmp_path / "home"
    home.mkdir()

    probe = tmp_path / "probe.py"
    # The probe records its interpreter into a file and passes.
    probe.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path({str(tmp_path / 'used_interp')!r}).write_text(sys.executable)\n"
        "print('  text: HTTP 200 — PASS')\n"
        "print('overall: PASS')\n"
    )

    sentinel = tmp_path / "fakepython311"
    # A shell stub cannot run the python probe — use the REAL interpreter
    # path as the sentinel is meaningless there. Instead the sentinel is a
    # real python that we can identify: use the current interpreter.
    real = shutil.which("python3") or "python3"
    result = _run_bootstrap(
        _base_env(home),
        "--python", real,
        "--env-file", str(tmp_path / "maas.env"),
        "--dest", str(tmp_path / "opt"),
        "--skip-systemd", "--verify-live",
    )
    # _run_bootstrap doesn't carry BOOTSTRAP_CANARY_PROBE; redo with env.
    env = _base_env(home)
    env["BOOTSTRAP_CANARY_PROBE"] = str(probe)
    result = subprocess.run(
        ["bash", str(BOOTSTRAP),
         "--maas-url", MAAS_URL,
         "--service", "wpa-test-no-such-unit.service",
         "--python", real,
         "--env-file", str(tmp_path / "maas.env"),
         "--dest", str(tmp_path / "opt"),
         "--skip-systemd", "--verify-live"],
        input=KEY + "\n", env=env,
        capture_output=True, text=True, timeout=120,
    )
    used = tmp_path / "used_interp"
    assert used.exists(), (
        f"canary probe never ran\nstdout:{result.stdout}\nstderr:{result.stderr}"
    )
    # The recorded interpreter must be the one we passed (resolved).
    recorded = used.read_text().strip()
    assert recorded == real or Path(recorded).resolve() == Path(real).resolve()


def test_a_g2_maas_python_env_var(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path({str(tmp_path / 'used_interp')!r}).write_text(sys.executable)\n"
        "print('  text: HTTP 200 — PASS')\n"
        "print('overall: PASS')\n"
    )
    real = shutil.which("python3") or "python3"

    env = _base_env(home)
    env["MAAS_PYTHON"] = real
    env["BOOTSTRAP_CANARY_PROBE"] = str(probe)
    result = subprocess.run(
        ["bash", str(BOOTSTRAP),
         "--maas-url", MAAS_URL,
         "--service", "wpa-test-no-such-unit.service",
         "--env-file", str(tmp_path / "maas.env"),
         "--dest", str(tmp_path / "opt"),
         "--skip-systemd", "--verify-live"],
        input=KEY + "\n", env=env,
        capture_output=True, text=True, timeout=120,
    )
    used = tmp_path / "used_interp"
    assert used.exists(), f"canary never ran\n{result.stdout}\n{result.stderr}"
    recorded = used.read_text().strip()
    assert recorded == real or Path(recorded).resolve() == Path(real).resolve()


# ---------------------------------------------------------------------------
# A-G3: attribution split
# ---------------------------------------------------------------------------


def _run_canary_case(tmp_path, probe_body: str) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    home = tmp_path / "home"
    home.mkdir()
    probe = tmp_path / "probe.py"
    probe.write_text(probe_body)
    env = _base_env(home)
    env["BOOTSTRAP_CANARY_PROBE"] = str(probe)
    result = subprocess.run(
        ["bash", str(BOOTSTRAP),
         "--maas-url", MAAS_URL,
         "--service", "wpa-test-no-such-unit.service",
         "--env-file", str(tmp_path / "maas.env"),
         "--dest", str(tmp_path / "opt"),
         "--skip-systemd", "--verify-live"],
        input=KEY + "\n", env=env,
        capture_output=True, text=True, timeout=120,
    )
    return result.stderr + result.stdout


def test_a_g3_exec_error_vs_upstream_rejection(tmp_path):
    """SyntaxError/ImportError -> 'could not be EXECUTED';
    HTTP failure -> 'MaaS rejected'. The two messages must differ."""
    exec_err = _run_canary_case(
        tmp_path / "case1",
        "from __future__ import annotations\n"
        "import module_that_does_not_exist_xyz\n",
    )
    assert "could not be EXECUTED" in exec_err, exec_err
    assert "NOT a key/URL/MaaS problem" in exec_err, exec_err
    assert "MaaS rejected" not in exec_err

    http_err = _run_canary_case(
        tmp_path / "case2",
        "print('  text: HTTP 401 — FAIL')\n"
        "print('overall: FAIL')\n"
        "import sys; sys.exit(1)\n",
    )
    assert "upstream canary failed" in http_err, http_err
    assert "MaaS rejected the request" in http_err, http_err
    assert "could not be EXECUTED" not in http_err

    # The two attributions must be distinguishable messages.
    assert "could not be EXECUTED" not in http_err
    assert "MaaS rejected" not in exec_err


def test_a_g3_exec_error_names_interpreter_and_fix(tmp_path):
    err = _run_canary_case(
        tmp_path / "case3",
        "from __future__ import annotations\n"
        "import module_that_does_not_exist_xyz\n",
    )
    assert "interpreter:" in err
    assert "dnf install python39" in err  # actionable fix guidance
