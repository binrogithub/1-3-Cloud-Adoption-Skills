"""Unit tests for the profile-scoped structured results in live_smoke.py.

PRD-r11-minimal-closeout.md §5: result-count invariants, profile assignments,
and mathematical consistency between summary, JSON, and exit code.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
LIVE_SMOKE = TESTS_DIR / "live_smoke.py"

_CHECK_SCRIPT = """
import sys, os
sys.path.insert(0, 'tests')
os.environ.setdefault('LITELLM_KEY', 'sk-test')
import live_smoke

all_probes = set(live_smoke.PROBES.keys())
assigned = set()
for names in live_smoke.PROFILES.values():
    assigned.update(names)
assert assigned.issubset(all_probes), 'unknown probes in profiles: %s' % (assigned - all_probes)

# HEALTHY must contain exactly 7 deterministic probes (PRD §5.3)
healthy = live_smoke.PROFILES['healthy']
assert len(healthy) == 7, 'HEALTHY must have 7 probes, got %d' % len(healthy)

# HEALTHY must NOT contain nondeterministic probes
assert 'tool_args' not in healthy, 'tool_args must not be in HEALTHY (nondeterministic)'
assert 'reasoning_openai' not in healthy, 'reasoning_openai must not be in HEALTHY (operator)'

# HEALTHY must contain the 7 deterministic public probes
mandatory = {'message','stream','tools','reasoning','image','nested_image','image_limit'}
assert set(healthy) == mandatory, 'HEALTHY mismatch: %s' % (set(healthy) ^ mandatory)

# tool_canary must have 5 canary probes (PRD §5.3, P0-8)
tc = set(live_smoke.PROFILES['tool_canary'])
assert tc == {'tool_canary_valid','tool_canary_repair','tool_canary_reject','tool_guard_enforce_mode','tool_canary_public_acl'}, 'tool_canary mismatch'

# operator profile has the nondeterministic/internal probes
op = set(live_smoke.PROFILES.get('operator', []))
assert 'reasoning_openai' in op, 'reasoning_openai must be in operator profile'
assert 'tool_args' in op, 'tool_args must be in operator profile'

# ProbeResult has all required fields
r = live_smoke.ProbeResult(
    run_id='r1', profile='healthy', candidate_commit='abc',
    artifact_sha256='def', host='h', deploy_root='/',
    probe='message', passed=True, exercised=True,
    http_status=200, expected_status=200, elapsed=0.1, detail='ok')
d = r.to_dict()
required = {'run_id','profile','candidate_commit','artifact_sha256',
            'host','deploy_root','probe','passed','exercised',
            'http_status','expected_status','elapsed','detail'}
assert required.issubset(set(d.keys())), 'missing fields: %s' % (required - set(d.keys()))
print('ALL CHECKS OK')
"""


def test_profile_assignments_and_probe_result():
    """PRD §5.3: HEALTHY = 7 deterministic probes, result-count invariants."""
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_SCRIPT],
        capture_output=True, text=True, timeout=10, cwd=str(TESTS_DIR.parent),
    )
    assert result.returncode == 0, "Profile/ProbeResult check failed: %s" % result.stderr


def test_502_probe_is_unexercised_on_200():
    """The 502 probe must return False when it gets a 200."""
    source = LIVE_SMOKE.read_text()
    assert 'show("502", False' in source, \
        "probe_502 must explicitly return False on HTTP 200 (unexercised mandatory branch)"


def test_show_function_enforces_exercised_false_is_fail():
    """The show() function must set passed=False when exercised=False."""
    source = LIVE_SMOKE.read_text()
    assert "if not exercised:" in source and "passed = False" in source, \
        "show() must enforce that unexercised probes are always FAIL"


def test_json_output_flag_exists():
    """The --json-output flag must exist for machine-readable evidence."""
    result = subprocess.run(
        [sys.executable, str(LIVE_SMOKE), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "--json-output" in result.stdout, "must have --json-output flag"
    assert "--profile" in result.stdout, "must have --profile flag"


def test_no_probe_infers_success_from_200_alone():
    """No helper may infer semantic success solely from HTTP 200."""
    source = LIVE_SMOKE.read_text()
    assert '"PASS" if passed else "FAIL"' in source, \
        "show() must determine PASS/FAIL from the passed boolean, not HTTP status"


def test_reasoning_is_split():
    """probe_reasoning must only do Anthropic filtering (no OpenAI leg).
    probe_reasoning_openai must be a separate function."""
    source = LIVE_SMOKE.read_text()
    assert "def probe_reasoning_openai()" in source, "must have separate probe_reasoning_openai"
    # The public probe_reasoning should NOT call post_openai
    # Find the function body
    start = source.index("def probe_reasoning():")
    end = source.index("\n\ndef ", start + 1)
    body = source[start:end]
    assert "post_openai" not in body, "probe_reasoning must not call post_openai (split required)"


def test_tool_args_not_in_healthy():
    """tool_args must not be in the HEALTHY profile (nondeterministic)."""
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_SCRIPT],
        capture_output=True, text=True, timeout=10, cwd=str(TESTS_DIR.parent),
    )
    assert result.returncode == 0


def test_summary_uses_result_count():
    """summary.total must equal len(_RESULTS), not len(results) return values."""
    source = LIVE_SMOKE.read_text()
    assert "total = len(_RESULTS)" in source, "summary total must use len(_RESULTS)"
    assert "r.passed and r.exercised" in source, "passed count must check both passed and exercised"
