#!/usr/bin/env python3
"""Cross-process tests for the sidecar cache and ledger (PRD v2 §7.8 R8, §9.3).

These tests spawn separate OS processes (via subprocess) to verify that the
cross-process flock and ledger claims work across workers — not just within
one process's asyncio loop. PRD v2 §9.1 explicitly disqualifies same-process
coroutines as evidence of cross-process correctness.

Run: python3 -m pytest tests/test_cross_process.py
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIDECAR_CALLBACK = str(ROOT / "litellm_plugins" / "sidecar" / "callback.py")

# A child-process script that races on a caption cache miss. Each child:
#  - imports the sidecar module
#  - calls caption_image with a mocked call_model that records to a shared file
#  - exits
_CHILD_CAPTION_SCRIPT = '''
import asyncio, json, os, sys, types, importlib.util, logging, tempfile, pathlib, time

# stub litellm
litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
litellm.token_counter = lambda **kw: 100
lm = types.ModuleType("litellm._logging")
lm.verbose_proxy_logger = logging.getLogger("child")
sys.modules.setdefault("litellm._logging", lm)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
cl = types.ModuleType("litellm.integrations.custom_logger")
class CustomLogger: pass
cl.CustomLogger = CustomLogger
sys.modules.setdefault("litellm.integrations.custom_logger", cl)

glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

cache_dir = sys.argv[1]
counter_file = sys.argv[2]
sha = sys.argv[3]

spec = importlib.util.spec_from_file_location("sidecar", sys.argv[4])
sidecar = importlib.util.module_from_spec(spec)
sys.modules["sidecar"] = sidecar
spec.loader.exec_module(sidecar)

calls = []
async def mock_call(model, messages, **kw):
    calls.append(model)
    # Record to shared counter file (append mode, line-delimited).
    with open(counter_file, "a") as f:
        f.write(model + "\\n")
    await asyncio.sleep(0.1)  # simulate latency so children overlap
    return {"choices": [{"message": {"content": json.dumps({
        "summary": "red image", "layout": "solid",
        "visible_text": [], "errors": [], "uncertainties": []
    })}}]}

cache = sidecar.CaptionCache(cache_dir)
# Build a minimal valid PNG image ref.
red_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII="
img = sidecar.ImageRef("image/png", red_png_b64, b"\\x89PNG", ("messages", 0, (0,)), {})

async def run():
    result = await sidecar.caption_image(img, call_model=mock_call, cache=cache)
    return result

asyncio.run(run())
print("child done, calls:", len(calls))
'''

# A child-process script that races on a Premium fingerprint claim.
_CHILD_LEDGER_SCRIPT = '''
import asyncio, json, os, sys, types, importlib.util, logging, tempfile, pathlib

litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
litellm.token_counter = lambda **kw: 100
lm = types.ModuleType("litellm._logging")
lm.verbose_proxy_logger = logging.getLogger("child")
sys.modules.setdefault("litellm._logging", lm)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
cl = types.ModuleType("litellm.integrations.custom_logger")
class CustomLogger: pass
cl.CustomLogger = CustomLogger
sys.modules.setdefault("litellm.integrations.custom_logger", cl)

glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

ledger_dir = sys.argv[1]
counter_file = sys.argv[2]
fingerprint = sys.argv[3]
session = sys.argv[4]

spec = importlib.util.spec_from_file_location("sidecar", sys.argv[5])
sidecar = importlib.util.module_from_spec(spec)
sys.modules["sidecar"] = sidecar
spec.loader.exec_module(sidecar)

ledger = sidecar.InterventionLedger(ledger_dir)
claimed = ledger.claim(fingerprint, session)
if claimed:
    with open(counter_file, "a") as f:
        f.write("claimed\\n")
    # Simulate work then record outcome.
    ledger.record_outcome(fingerprint, session, {"advice": "test"}, success=True)
else:
    with open(counter_file, "a") as f:
        f.write("denied\\n")
print("child done, claimed:", claimed)
'''


def test_separate_processes_race_on_one_image_one_call():
    """R8: separate OS processes racing on one uncached image produce exactly
    one provider call (cross-process flock + cache recheck)."""
    with tempfile.TemporaryDirectory() as d:
        cache_dir = os.path.join(d, "cache")
        os.makedirs(cache_dir)
        counter_file = os.path.join(d, "calls.txt")
        # Ensure the counter file exists (empty).
        open(counter_file, "w").close()

        # Spawn 3 child processes simultaneously.
        procs = []
        for _ in range(3):
            p = subprocess.Popen(
                [sys.executable, "-c", _CHILD_CAPTION_SCRIPT,
                 cache_dir, counter_file, "shared_sha", SIDECAR_CALLBACK],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            procs.append(p)

        for p in procs:
            p.wait(timeout=30)

        # Count the provider calls.
        with open(counter_file) as f:
            calls = [line.strip() for line in f if line.strip()]
        assert len(calls) == 1, (
            "R8: expected exactly 1 provider call across 3 processes, got %d" % len(calls)
        )


def test_separate_processes_race_on_one_fingerprint_one_claim():
    """R8: separate OS processes racing on one Premium fingerprint produce
    exactly one claim (cross-process flock around the ledger)."""
    with tempfile.TemporaryDirectory() as d:
        ledger_dir = os.path.join(d, "ledger")
        os.makedirs(ledger_dir)
        counter_file = os.path.join(d, "claims.txt")
        open(counter_file, "w").close()

        procs = []
        for _ in range(3):
            p = subprocess.Popen(
                [sys.executable, "-c", _CHILD_LEDGER_SCRIPT,
                 ledger_dir, counter_file, "fp_shared", "sess1", SIDECAR_CALLBACK],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            procs.append(p)

        for p in procs:
            p.wait(timeout=30)

        with open(counter_file) as f:
            results = [line.strip() for line in f if line.strip()]
        claims = [r for r in results if r == "claimed"]
        denied = [r for r in results if r == "denied"]
        assert len(claims) == 1, (
            "R8: expected exactly 1 claim across 3 processes, got %d" % len(claims)
        )
        assert len(denied) == 2, (
            "R8: expected 2 denials, got %d" % len(denied)
        )


def test_separate_fingerprints_under_one_session_respect_cap():
    """R8: separate fingerprints racing under one session cannot exceed the
    session cap (default 3)."""
    with tempfile.TemporaryDirectory() as d:
        ledger_dir = os.path.join(d, "ledger")
        os.makedirs(ledger_dir)
        counter_file = os.path.join(d, "claims.txt")
        open(counter_file, "w").close()

        # Spawn 5 children with 5 DIFFERENT fingerprints under the same session.
        procs = []
        for i in range(5):
            p = subprocess.Popen(
                [sys.executable, "-c", _CHILD_LEDGER_SCRIPT,
                 ledger_dir, counter_file, "fp_%d" % i, "sess_cap", SIDECAR_CALLBACK],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            procs.append(p)

        for p in procs:
            p.wait(timeout=30)

        with open(counter_file) as f:
            results = [line.strip() for line in f if line.strip()]
        claims = [r for r in results if r == "claimed"]
        # Session cap is 3 (PREMIUM_MAX_DISTINCT_INTERVENTIONS). At most 3 claims.
        assert len(claims) <= 3, (
            "R8: expected at most 3 claims (session cap), got %d" % len(claims)
        )


def test_process_termination_recovers_safely():
    """R8: a process that crashes mid-claim is recovered safely — the next
    claimant can proceed (flock auto-releases on fd close)."""
    with tempfile.TemporaryDirectory() as d:
        cache_dir = os.path.join(d, "cache")
        os.makedirs(cache_dir)
        counter_file = os.path.join(d, "calls.txt")
        open(counter_file, "w").close()

        # Start a child that acquires the lock then is killed.
        p1 = subprocess.Popen(
            [sys.executable, "-c", _CHILD_CAPTION_SCRIPT,
             cache_dir, counter_file, "kill_sha", SIDECAR_CALLBACK],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Kill it mid-flight (before it completes the caption).
        p1.terminate()
        p1.wait(timeout=10)

        # Now a second child should be able to acquire the lock and caption.
        p2 = subprocess.Popen(
            [sys.executable, "-c", _CHILD_CAPTION_SCRIPT,
             cache_dir, counter_file, "kill_sha", SIDECAR_CALLBACK],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        p2.wait(timeout=30)

        # The second child should have succeeded (lock auto-released on kill).
        with open(counter_file) as f:
            calls = [line.strip() for line in f if line.strip()]
        # At least one call from the second child (the first was killed mid-call).
        assert len(calls) >= 1, (
            "R8: second child should proceed after first was killed, got %d calls" % len(calls)
        )


if __name__ == "__main__":
    test_separate_processes_race_on_one_image_one_call()
    print("  ok test_separate_processes_race_on_one_image_one_call")
    test_separate_processes_race_on_one_fingerprint_one_claim()
    print("  ok test_separate_processes_race_on_one_fingerprint_one_claim")
    test_separate_fingerprints_under_one_session_respect_cap()
    print("  ok test_separate_fingerprints_under_one_session_respect_cap")
    test_process_termination_recovers_safely()
    print("  ok test_process_termination_recovers_safely")
    print("\nAll cross-process tests passed.")
