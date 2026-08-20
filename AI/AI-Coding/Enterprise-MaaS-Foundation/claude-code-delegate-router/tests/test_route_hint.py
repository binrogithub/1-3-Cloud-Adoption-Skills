"""Tests for the advisory route-hint hook (scripts/route-hint.sh).

The hook is advisory only: it outputs ONE concise context line, always exits 0,
never blocks, never invokes MaaS, never reads credentials, and never mutates
files. It classifies a task description using the approved PRD taxonomy:

  OAuth (stay in the Anthropic OAuth session):
    - images / screenshots / vision input
    - security / auth / payment / PCI / incident
    - architecture / cross-service design
    - complex debugging / multi-failure root cause
    - high-risk PR review / infra / DB migration decisions
    - tasks exceeding GLM context boundary
    - escalation after two MaaS failures

  MaaS (delegate to claude-maas / glm-5.2):
    - ordinary code generation / single-module modification
    - unit tests / docs / repo summary
    - CI fixes / mechanical refactor / format migration
    - low/medium-risk review
    - batch / loop / CI / cron / multi-task fan-out

  Premium signals win ties: a task that is both "code-gen" and "security"
  classifies as OAuth.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROUTE_HINT = ROOT / "scripts" / "route-hint.sh"


# ---------------------------------------------------------------------------
# Fixture: run_hint
# ---------------------------------------------------------------------------


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env with all ANTHROPIC_* keys removed."""
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def run_hint(tmp_path: Path):
    """Return a callable that runs route-hint.sh with HOME=tmp_path.

    The environment is stripped of all ANTHROPIC_* variables to prove the
    hook does not rely on provider credentials.
    """
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(tmp_path)

    def _run(
        *args: str,
        stdin: str | None = None,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(ROUTE_HINT), *args],
            env=base_env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result

    return _run


# ---------------------------------------------------------------------------
# Helper: parse the advisory line
# ---------------------------------------------------------------------------


def _parse_route(line: str) -> str:
    """Extract the route token ('oauth' or 'maas') from a route-hint line."""
    # Expected: "route-hint: oauth (reason: ...)" or "route-hint: maas (reason: ...)"
    stripped = line.strip()
    assert stripped.startswith("route-hint: "), f"unexpected line: {stripped!r}"
    rest = stripped[len("route-hint: "):]
    # route token is the first word before " (reason:"
    route = rest.split(" ")[0]
    assert route in ("oauth", "maas"), f"unexpected route: {route!r}"
    return route


def _parse_reason(line: str) -> str:
    """Extract the reason text from a route-hint line."""
    stripped = line.strip()
    assert "(reason:" in stripped, f"missing reason in line: {stripped!r}"
    reason_part = stripped[stripped.index("(reason:") + len("(reason: "):]
    assert reason_part.endswith(")"), f"malformed reason in line: {stripped!r}"
    return reason_part[:-1]


# ---------------------------------------------------------------------------
# Classification: OAuth (premium / high-judgment) tasks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "Analyze this screenshot of the UI bug",
        "Please look at the image attached and describe what's wrong",
        "I have a vision task: classify objects in this photo",
        "Read this screenshot and extract the error message",
        "Review the architecture for the new cross-service design",
        "Design the architecture for the payment service integration",
        "We need cross-service design review for the order pipeline",
        "Audit the authentication flow for security vulnerabilities",
        "Fix the security issue in the auth middleware",
        "Review the payment processing code for PCI compliance",
        "Investigate the production incident from last night",
        "Handle this incident: the checkout service is down",
        "Debug this complex multi-failure issue across the API and DB layers",
        "Root cause analysis: the service has race conditions in multiple subsystems",
        "Complex debugging: three services fail intermittently with cascading errors",
        "High-risk PR review: changing the crypto module",
        "Review the infrastructure migration plan",
        "Database migration decision for the sharding strategy",
    ],
)
def test_oauth_classification(run_hint, description):
    result = run_hint(description)
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


# ---------------------------------------------------------------------------
# Classification: MaaS (delegate) tasks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "Generate unit tests for src/parser.py",
        "Write documentation for the API endpoints",
        "Generate a repo summary of the project structure",
        "Fix the CI pipeline: update the test runner config",
        "Mechanical refactor: rename foo() to bar() across the module",
        "Migrate code formatting from black to ruff",
        "Code generation: implement the CRUD endpoints for the user model",
        "Low-risk review: check the docstring formatting",
        "Medium-risk review: verify the test coverage for utils.py",
        "Run the batch processing job for the daily export",
        "Loop over all modules and update the import paths",
        "CI fix: pin the pytest version in requirements",
        "Cron job: clean up stale temporary files",
        "Fan-out: run the linter on each package in parallel",
        "Write a unit test for the edge case in calculate_total",
        "Generate a docstring for the process_order function",
    ],
)
def test_maas_classification(run_hint, description):
    result = run_hint(description)
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "maas"


# ---------------------------------------------------------------------------
# Tie-breaking: premium signals win
# ---------------------------------------------------------------------------


def test_premium_wins_tie_code_gen_and_security(run_hint):
    """A task that is both 'code-gen' and 'security' must classify as OAuth."""
    result = run_hint("Generate code for the security authentication module")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


def test_premium_wins_tie_test_and_payment(run_hint):
    """A task that is both 'test' and 'payment' must classify as OAuth."""
    result = run_hint("Write unit tests for the payment processing logic")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


def test_premium_wins_tie_docs_and_incident(run_hint):
    """A task that is both 'docs' and 'incident' must classify as OAuth."""
    result = run_hint("Document the incident response runbook for the outage")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


def test_premium_wins_tie_refactor_and_architecture(run_hint):
    """A task that is both 'refactor' and 'architecture' must classify as OAuth."""
    result = run_hint("Refactor the architecture of the cross-service messaging layer")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


# ---------------------------------------------------------------------------
# Advisory-only invariants
# ---------------------------------------------------------------------------


def test_always_exits_zero(run_hint):
    """The hook must always exit 0, even for unknown/empty input."""
    assert run_hint("").returncode == 0
    assert run_hint("some random text that matches nothing").returncode == 0


def test_outputs_exactly_one_line(run_hint):
    """The hook must output exactly one concise advisory line on stdout."""
    result = run_hint("write unit tests for the parser")
    assert result.returncode == 0
    lines = [l for l in result.stdout.split("\n") if l.strip()]
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {result.stdout!r}"


def test_output_line_has_route_hint_prefix(run_hint):
    result = run_hint("generate code for the user model")
    assert result.returncode == 0
    assert result.stdout.strip().startswith("route-hint: ")


def test_output_line_has_reason(run_hint):
    result = run_hint("generate code for the user model")
    assert result.returncode == 0
    assert "(reason:" in result.stdout


def test_does_not_read_credentials(run_hint, tmp_path):
    """The hook must not read or reference MaaS credentials."""
    # Create a fake key file that the hook should never touch.
    config_dir = tmp_path / ".config" / "claude-maas"
    config_dir.mkdir(parents=True)
    key_file = config_dir / "api-key"
    key_file.write_text("SECRET-KEY-MUST-NOT-APPEAR\n")
    key_file.chmod(0o600)

    result = run_hint("write unit tests for the parser")
    combined = result.stdout + result.stderr
    assert "SECRET-KEY-MUST-NOT-APPEAR" not in combined


def test_does_not_invoke_maas(run_hint):
    """The hook must not invoke claude-maas or any subprocess to call MaaS."""
    result = run_hint("write unit tests")
    combined = result.stdout + result.stderr
    assert "claude-maas" not in combined.lower()
    assert "glm-5.2" not in combined.lower()


def test_does_not_mutate_files(run_hint, tmp_path):
    """The hook must not create or modify any files."""
    # Snapshot the tmp_path tree before running.
    before = set()
    for p in tmp_path.rglob("*"):
        before.add(str(p.relative_to(tmp_path)))

    result = run_hint("write unit tests for the parser")
    assert result.returncode == 0

    after = set()
    for p in tmp_path.rglob("*"):
        after.add(str(p.relative_to(tmp_path)))

    assert before == after, f"files changed: {after - before}"


def test_reads_from_stdin(run_hint):
    """The hook must accept task description from stdin."""
    result = run_hint(stdin="analyze this screenshot for the UI bug")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


def test_reads_from_args(run_hint):
    """The hook must accept task description from command-line args."""
    result = run_hint("analyze this screenshot for the UI bug")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "oauth"


def test_stdin_and_args_combined(run_hint):
    """When both stdin and args are provided, the hook should classify the combined text."""
    result = run_hint("unit test", stdin="for the payment module")
    assert result.returncode == 0
    # "payment" is a premium signal -> OAuth
    assert _parse_route(result.stdout) == "oauth"


def test_empty_input_does_not_crash(run_hint):
    """Empty input must produce a valid advisory line, not an error."""
    result = run_hint("")
    assert result.returncode == 0
    lines = [l for l in result.stdout.split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("route-hint: ")


def test_multiline_input(run_hint):
    """Multiline input must be handled gracefully."""
    result = run_hint(stdin="Write unit tests\nfor the parser module\nwith edge cases")
    assert result.returncode == 0
    assert _parse_route(result.stdout) == "maas"
