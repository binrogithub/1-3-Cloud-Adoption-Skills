"""Tests for the fail-closed release evidence writer.

The writer reads a structured gate-result JSON and emits a Markdown evidence
record.  It must reject any pending, skipped, untrusted, dirty-tree, stale
commit/tree, or digest-mismatch state.  It must never accept or serialize a
key, prompt, OAuth metadata, or response body.  Image known-unsupported
(HTTP 400, no fallback) is the only accepted non-PASS terminal state.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "scripts" / "write-release-evidence.py"


def _git_head() -> tuple[str, str]:
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return commit, tree


def _helper_digest(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _run_writer(results: dict) -> subprocess.CompletedProcess:
    """Invoke the writer with a results JSON on stdin."""
    return subprocess.run(
        ["python3", str(WRITER)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _base_results(**overrides) -> dict:
    """A minimal valid results object that the writer must accept."""
    commit, tree = _git_head()
    r = {
        "commit": commit,
        "tree": tree,
        "generated_at_utc": "2026-08-20T00:00:00Z",
        "worktree_clean": True,
        "claude_code_version": "2.1.235",
        "binary_digest": "deadbeef",
        "endpoint_host": "api-ap-southeast-1.modelarts-maas.com",
        "endpoint_path": "/anthropic",
        "model": "glm-5.2",
        "helpers": {
            "tests/live_maas_probe.py": _helper_digest("tests/live_maas_probe.py"),
            "tests/claude_e2e_probe.sh": _helper_digest("tests/claude_e2e_probe.sh"),
            "scripts/check-prohibited-dependencies.py": _helper_digest("scripts/check-prohibited-dependencies.py"),
        },
        "gates": [
            {"name": "config-modes", "status": "PASS", "duration_ms": 10},
            {"name": "direct-api", "status": "PASS", "duration_ms": 500},
            {"name": "token-only-claude-cli", "status": "PASS", "duration_ms": 200},
            {"name": "tool-round-trip", "status": "PASS", "duration_ms": 200},
            {"name": "plain-claude-isolation", "status": "PASS", "duration_ms": 50},
            {"name": "prohibited-dependency-scan", "status": "PASS", "duration_ms": 10},
        ],
        "image_probe": {"status": "KNOWN_UNSUPPORTED", "http_status": 400, "fallback": False},
    }
    r.update(overrides)
    return r


# ---------------------------------------------------------------------------
# Writer exists and accepts a valid result
# ---------------------------------------------------------------------------


def test_writer_exists():
    assert WRITER.is_file(), "scripts/write-release-evidence.py must exist"


def test_valid_results_produce_pass_evidence():
    results = _base_results()
    result = _run_writer(results)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "PASS" in result.stdout
    assert "FAIL" not in result.stdout
    # Required fields must appear.
    assert results["commit"] in result.stdout  # commit
    assert "glm-5.2" in result.stdout  # model
    assert "2.1.235" in result.stdout  # claude version


# ---------------------------------------------------------------------------
# Fail-closed: rejected states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate_name",
    ["config-modes", "direct-api", "token-only-claude-cli", "tool-round-trip",
     "plain-claude-isolation", "prohibited-dependency-scan"],
)
def test_pending_gate_rejected(gate_name):
    results = _base_results()
    for g in results["gates"]:
        if g["name"] == gate_name:
            g["status"] = "pending"
    result = _run_writer(results)
    assert result.returncode != 0, "pending gate must be rejected"
    assert "pending" in result.stderr.lower() or "LIVE_GATE_PENDING" in result.stderr


def test_skipped_gate_rejected():
    results = _base_results()
    results["gates"][0]["status"] = "skipped"
    result = _run_writer(results)
    assert result.returncode != 0, "skipped gate must be rejected"


def test_untrusted_gate_rejected():
    results = _base_results()
    results["gates"][0]["status"] = "UNTRUSTED_TEST_RESULT"
    result = _run_writer(results)
    assert result.returncode != 0, "untrusted gate must be rejected"


def test_dirty_worktree_rejected():
    result = _run_writer(_base_results(worktree_clean=False))
    assert result.returncode != 0, "dirty worktree must be rejected"


def test_stale_commit_rejected():
    """If the results commit does not match the actual HEAD, reject."""
    results = _base_results(commit="stale-not-head")
    result = _run_writer(results)
    assert result.returncode != 0, "stale commit must be rejected"


def test_stale_tree_rejected():
    """If the results tree does not match the actual HEAD tree, reject."""
    results = _base_results(tree="stale-not-tree")
    result = _run_writer(results)
    assert result.returncode != 0, "stale tree must be rejected"
    assert "EVIDENCE_STALE_COMMIT" in result.stderr


def test_helper_digest_mismatch_rejected():
    """If a helper digest does not match the checkout, reject."""
    results = _base_results()
    results["helpers"]["tests/live_maas_probe.py"] = "wrong-digest"
    result = _run_writer(results)
    assert result.returncode != 0, "digest mismatch must be rejected"


# ---------------------------------------------------------------------------
# Image known-unsupported is accepted, fallback is rejected
# ---------------------------------------------------------------------------


def test_image_known_unsupported_accepted():
    result = _run_writer(_base_results())
    assert result.returncode == 0
    assert "KNOWN_UNSUPPORTED" in result.stdout


def test_image_with_fallback_rejected():
    results = _base_results()
    results["image_probe"]["fallback"] = True
    result = _run_writer(results)
    assert result.returncode != 0, "image fallback must be rejected"


def test_image_non_400_rejected():
    results = _base_results()
    results["image_probe"]["http_status"] = 200
    result = _run_writer(results)
    assert result.returncode != 0, "image must be HTTP 400"


# ---------------------------------------------------------------------------
# No secrets in evidence
# ---------------------------------------------------------------------------


def test_key_never_in_evidence():
    """If a key-like string appears in the results, the writer must reject it
    or scrub it — it must never appear in stdout."""
    results = _base_results()
    results["gates"][1]["error_summary"] = "auth failed for Bearer sk-real-secret-key"
    result = _run_writer(results)
    assert "sk-real-secret-key" not in result.stdout, (
        "key must never appear in evidence stdout"
    )


def test_response_body_never_in_evidence():
    results = _base_results()
    results["gates"][1]["raw_body"] = '{"content":"secret response text"}'
    result = _run_writer(results)
    assert result.returncode != 0 or "secret response text" not in result.stdout, (
        "response body must never appear in evidence"
    )


# ---------------------------------------------------------------------------
# Required evidence fields
# ---------------------------------------------------------------------------


def test_evidence_contains_required_fields():
    result = _run_writer(_base_results())
    out = result.stdout
    assert "commit" in out.lower()
    assert "tree" in out.lower()
    assert "endpoint" in out.lower()
    assert "helper" in out.lower() or "sha-256" in out.lower() or "digest" in out.lower()
    assert "glm-5.2" in out
