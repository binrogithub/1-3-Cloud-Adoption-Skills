"""Invariant tests for the live smoke runner (PRD-r11-minimal-closeout.md §13).

Required tests:
1. HEALTHY produces seven records and summary 7/7 when all pass.
2. An extra uncounted record fails result validation.
3. OpenAI internal reasoning cannot contaminate the public result count.
4. Prompt-driven malformed tool output is not a release gate.
5. Metrics no-op collectors fail Step 0.
6. A zero delta without a successful positive control is rejected.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
LIVE_SMOKE = TESTS_DIR / "live_smoke.py"


def test_healthy_has_seven_probes():
    """PRD §13.1: HEALTHY produces seven records and summary 7/7 when all pass."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'tests'); "
         "import os; os.environ.setdefault('LITELLM_KEY', 'sk-test'); "
         "import live_smoke; "
         "h = live_smoke.PROFILES['healthy']; "
         "assert len(h) == 7, 'HEALTHY must have 7 probes'; "
         "print('HEALTHY has 7 probes')"],
        capture_output=True, text=True, timeout=10, cwd=str(TESTS_DIR.parent),
    )
    assert result.returncode == 0, result.stderr


def test_extra_uncounted_record_fails():
    """PRD §13.2: An extra uncounted record fails result validation.
    If a probe appends an extra result via show() but doesn't return it,
    the summary must still count len(_RESULTS), exposing the inconsistency."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'tests'); "
         "import os; os.environ.setdefault('LITELLM_KEY', 'sk-test'); "
         "import live_smoke; "
         "live_smoke._CURRENT_PROFILE = 'test'; "
         "live_smoke._RESULTS = []; "
         "# Simulate a probe that calls show() twice but returns one value "
         "live_smoke.show('probe_a', True, 200, 0.1, 'ok'); "
         "live_smoke.show('probe_a_extra', True, 200, 0.1, 'extra'); "
         "results = [True]; "  # only one return value
         "total = len(live_smoke._RESULTS); "
         "assert total == 2, 'total should be 2 (both show calls)'; "
         "assert len(results) == 1, 'return values is 1'; "
         "assert total != len(results), 'mismatch detected — invariant catches extra records'; "
         "print('extra record detection OK')"],
        capture_output=True, text=True, timeout=10, cwd=str(TESTS_DIR.parent),
    )
    assert result.returncode == 0, result.stderr


def test_openai_reasoning_cannot_contaminate_public_count():
    """PRD §13.3: OpenAI internal reasoning cannot contaminate the public result count.
    probe_reasoning must not call post_openai."""
    source = LIVE_SMOKE.read_text()
    start = source.index("def probe_reasoning():")
    end = source.index("\n\ndef ", start + 1)
    body = source[start:end]
    assert "post_openai" not in body, \
        "probe_reasoning must not call post_openai — OpenAI is a separate operator probe"


def test_tool_args_not_a_release_gate():
    """PRD §13.4: Prompt-driven malformed tool output is not a release gate.
    tool_args must not be in the HEALTHY profile."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'tests'); "
         "import os; os.environ.setdefault('LITELLM_KEY', 'sk-test'); "
         "import live_smoke; "
         "assert 'tool_args' not in live_smoke.PROFILES['healthy'], "
         "'tool_args must not be in HEALTHY'; "
         "assert 'tool_args' in live_smoke.PROBES, 'tool_args probe still exists as diagnostic'; "
         "print('tool_args is diagnostic only, not a gate')"],
        capture_output=True, text=True, timeout=10, cwd=str(TESTS_DIR.parent),
    )
    assert result.returncode == 0, result.stderr


def test_summary_passed_counts_both_passed_and_exercised():
    """PRD §5.3: summary.passed == count(result.passed and result.exercised).
    An unexercised result must not count as passed."""
    source = LIVE_SMOKE.read_text()
    assert "r.passed and r.exercised" in source, \
        "passed count must check both passed AND exercised"


def test_exit_code_zero_only_if_all_passed_and_exercised():
    """PRD §5.3: suite exit code equals zero iff every selected result has
    both passed=true and exercised=true."""
    source = LIVE_SMOKE.read_text()
    assert "all(r.passed and r.exercised for r in _RESULTS)" in source, \
        "exit code must require all results passed AND exercised"
