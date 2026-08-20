"""Self-contained unit tests for the sidecar module (PRD-glm52-mainline-sidecars §17.1).

    python3 tests/test_sidecar.py

No proxy, no API key, no litellm install required. Mocks the sidecar transport
(call_model) so no live model calls are made.
"""

import asyncio
import base64
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "sidecar" / "callback.py"

# Ensure premium repair is enabled for these tests (another test file may have
# set TOOL_ARG_PREMIUM_REPAIR=false in os.environ before we load the sidecar).
os.environ["TOOL_ARG_PREMIUM_REPAIR"] = "true"

# Stub litellm so the module loads without the real package.
# Use setdefault so we don't clobber the conftest stub (or other test files' stubs).
litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
if not hasattr(litellm, "token_counter"):
    litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

spec = importlib.util.spec_from_file_location("sidecar", CALLBACK)
sidecar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidecar)

# Also stub glm_loop_breaker (imported lazily by detect_triggers).
glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

FAILURES = []


def check(name, got, want):
    if got == want:
        print("  ok    %s" % name)
    else:
        print("  FAIL  %s: got %r, want %r" % (name, got, want))
        FAILURES.append(name)


def check_true(name, got):
    check(name, bool(got), True)


def check_false(name, got):
    check(name, bool(got), False)


# A raw tool-call markup marker, built from chr() so the literal never appears
# in this source file (it would confuse tooling that scans for it).
_MARK = chr(60) + "tool_call" + chr(62)

# A minimal valid 1x1 red PNG.
_RED_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
_RED_PNG_BYTES = base64.b64decode(_RED_PNG_B64)
_RED_PNG_SHA = hashlib.sha256(_RED_PNG_BYTES).hexdigest()

# A minimal valid 1x1 GIF.
_GIF_B64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


def user_image_block(b64=_RED_PNG_B64, mime="image/png"):
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}


def user_image_url_block(b64=_RED_PNG_B64, mime="image/png"):
    return {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}}


def user_input_image_block(b64=_RED_PNG_B64, mime="image/png"):
    return {"type": "input_image", "image_url": "data:%s;base64,%s" % (mime, b64)}


def make_mock_call_model(caption_obj=None, premium_obj=None, fail_models=None):
    """Return an async call_model mock that returns canned responses."""
    fail_models = fail_models or set()
    calls = []

    async def mock(model, messages, *, max_tokens=4096, timeout=60, temperature=None):
        calls.append({"model": model, "messages": messages})
        if model in fail_models:
            raise sidecar.SidecarCallError("mock failure for %s" % model)
        if "premium" in model or "opus" in model:
            obj = premium_obj or {
                "diagnosis": "the tool is misconfigured",
                "next_action": "check the config file",
                "stop_conditions": ["if config is still missing"],
                "prohibited_retries": ["calling the same tool again"],
                "user_visible_blocker": "config file not found",
            }
            return {"choices": [{"message": {"content": json.dumps(obj)}}]}
        obj = caption_obj or {
            "summary": "a red square",
            "visible_text": ["Red"],
            "errors": [],
            "layout": "centered",
            "uncertainties": [],
        }
        return {"choices": [{"message": {"content": json.dumps(obj)}}]}

    mock.calls = calls
    return mock


# ── 1. Image extraction: every supported representation ────────────────────

print("image extraction: representations")


def test_extract_top_level_image():
    data = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "what is this"},
        user_image_block(),
    ]}]}
    imgs = sidecar.extract_images(data)
    check("top-level image extracted", len(imgs), 1)
    check("sha256 matches", imgs[0].sha256, _RED_PNG_SHA)


def test_extract_image_url_block():
    data = {"messages": [{"role": "user", "content": [user_image_url_block()]}]}
    check("image_url block extracted", len(sidecar.extract_images(data)), 1)


def test_extract_input_image_block():
    data = {"messages": [{"role": "user", "content": [user_input_image_block()]}]}
    check("input_image block extracted", len(sidecar.extract_images(data)), 1)


def test_extract_nested_tool_result_image():
    data = {"messages": [
        {"role": "user", "content": "read the file"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_1", "name": "Read", "input": {"path": "x.png"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": [
                {"type": "text", "text": "file contents"},
                user_image_block(),
            ]},
        ]},
    ]}
    check("nested tool_result image extracted", len(sidecar.extract_images(data)), 1)


def test_extract_dedup_equal_images():
    data = {"messages": [
        {"role": "user", "content": [user_image_block(), user_image_block()]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": [user_image_block()]},
    ]}
    check("equal images deduped", len(sidecar.extract_images(data)), 1)


def test_extract_scans_all_messages():
    data = {"messages": [
        {"role": "user", "content": [user_image_block()]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "now what"},
    ]}
    check("history image found", len(sidecar.extract_images(data)), 1)


def test_extract_no_images():
    check("no images", len(sidecar.extract_images({"messages": [{"role": "user", "content": "hello"}]})), 0)


def test_extract_empty_messages():
    check("empty messages", len(sidecar.extract_images({})), 0)


for t in [test_extract_top_level_image, test_extract_image_url_block,
          test_extract_input_image_block, test_extract_nested_tool_result_image,
          test_extract_dedup_equal_images, test_extract_scans_all_messages,
          test_extract_no_images, test_extract_empty_messages]:
    t()


# ── 2. Rejection: malformed, remote URL, limits ────────────────────────────

print("\nrejection: malformed / remote / limits")


def test_reject_malformed_base64():
    data = {"messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "!!!not-base64!!!"}},
    ]}]}
    try:
        sidecar.extract_images(data)
        check("malformed base64 rejected", False, True)
    except sidecar.InvalidImageInput:
        check("malformed base64 rejected", True, True)


def test_reject_mime_signature_mismatch():
    data = {"messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _GIF_B64}},
    ]}]}
    try:
        sidecar.extract_images(data)
        check("mime/signature mismatch rejected", False, True)
    except sidecar.InvalidImageInput:
        check("mime/signature mismatch rejected", True, True)


def test_reject_unsupported_mime():
    data = {"messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/tiff", "data": _RED_PNG_B64}},
    ]}]}
    try:
        sidecar.extract_images(data)
        check("unsupported mime rejected", False, True)
    except sidecar.InvalidImageInput:
        check("unsupported mime rejected", True, True)


def test_reject_remote_http_url():
    data = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
    ]}]}
    try:
        sidecar.extract_images(data)
        check("remote http url rejected", False, True)
    except sidecar.InvalidImageInput:
        check("remote http url rejected", True, True)


def test_reject_too_many_images():
    imgs = [sidecar.ImageRef("image/png", _RED_PNG_B64, _RED_PNG_BYTES, {}, {})
            for _ in range(5)]
    try:
        sidecar.validate_and_limit(imgs)
        check("too many images rejected", False, True)
    except sidecar.ImageLimitExceeded:
        check("too many images rejected", True, True)


def test_reject_image_too_large():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (sidecar.VISION_MAX_IMAGE_BYTES + 1)
    img = sidecar.ImageRef("image/png", "x", big, {}, {})
    try:
        sidecar.validate_and_limit([img])
        check("image too large rejected", False, True)
    except sidecar.ImageLimitExceeded:
        check("image too large rejected", True, True)


for t in [test_reject_malformed_base64, test_reject_mime_signature_mismatch,
          test_reject_unsupported_mime, test_reject_remote_http_url,
          test_reject_too_many_images, test_reject_image_too_large]:
    t()


# ── 3. Caption injection: preserves tool IDs + adjacent text ────────────────

print("\ncaption injection")


def test_injection_preserves_tool_ids():
    data = {"messages": [
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": [
                {"type": "text", "text": "file"},
                user_image_block(),
            ]},
        ]},
    ]}
    sidecar.replace_with_captions(data, {_RED_PNG_SHA: "[vision-caption]Red[/vision-caption]"})
    tr = data["messages"][0]["content"][0]
    check("tool_use_id preserved", tr.get("tool_use_id"), "tu_1")
    check("text block preserved", tr["content"][0]["text"], "file")
    check("image replaced with caption", "vision-caption" in tr["content"][1]["text"], True)


def test_injection_preserves_adjacent_text():
    data = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "before"},
        user_image_block(),
        {"type": "text", "text": "after"},
    ]}]}
    sidecar.replace_with_captions(data, {_RED_PNG_SHA: "[vision-caption]Red[/vision-caption]"})
    content = data["messages"][0]["content"]
    check("before text preserved", content[0]["text"], "before")
    check("image replaced", "vision-caption" in content[1]["text"], True)
    check("after text preserved", content[2]["text"], "after")


def test_render_caption_deterministic():
    obj = {"summary": "red", "visible_text": ["Red"], "errors": [],
           "layout": "center", "uncertainties": []}
    text1 = sidecar.render_caption_text(_RED_PNG_SHA, obj)
    text2 = sidecar.render_caption_text(_RED_PNG_SHA, obj)
    check("caption deterministic (identical)", text1, text2)
    check("caption has sha256", _RED_PNG_SHA in text1, True)
    check("caption has schema version", "schema=v1" in text1, True)


for t in [test_injection_preserves_tool_ids, test_injection_preserves_adjacent_text,
          test_render_caption_deterministic]:
    t()


# ── 4. Caption cache ───────────────────────────────────────────────────────

print("\ncaption cache")


def test_cache_hit_miss():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d, ttl_seconds=3600, max_bytes=1000000, max_entries=100)
        check("miss before put", cache.get(_RED_PNG_SHA), None)
        cache.put(_RED_PNG_SHA, "rendered caption", "vision-openrouter")
        check("hit after put", cache.get(_RED_PNG_SHA), "rendered caption")


def test_cache_version_invalidation():
    with tempfile.TemporaryDirectory() as d:
        cache1 = sidecar.CaptionCache(d, prompt_version=1)
        cache1.put(_RED_PNG_SHA, "v1 caption", "vision-openrouter")
        check("v1 hit", cache1.get(_RED_PNG_SHA), "v1 caption")
        cache2 = sidecar.CaptionCache(d, prompt_version=2)
        check("v2 miss (version mismatch)", cache2.get(_RED_PNG_SHA), None)


def test_cache_ttl_expiry():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d, ttl_seconds=1)
        cache.put(_RED_PNG_SHA, "caption", "vision-openrouter")
        check("hit before ttl", cache.get(_RED_PNG_SHA), "caption")
        path = cache._entry_path(_RED_PNG_SHA)
        entry = json.loads(path.read_text())
        entry["last_access"] = time.time() - 100
        path.write_text(json.dumps(entry))
        check("miss after ttl", cache.get(_RED_PNG_SHA), None)


def test_cache_corrupt_quarantine():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        path = cache._entry_path(_RED_PNG_SHA)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json{")
        check("corrupt -> miss", cache.get(_RED_PNG_SHA), None)
        check("corrupt file quarantined (deleted)", path.exists(), False)


def test_cache_atomic_write():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        cache.put(_RED_PNG_SHA, "caption", "vision-openrouter")
        entry = json.loads(cache._entry_path(_RED_PNG_SHA).read_text())
        check("atomic write produces valid json", isinstance(entry, dict), True)
        check("entry has rendered_caption", entry.get("rendered_caption"), "caption")
        check("no image bytes stored", "decoded_bytes" not in entry, True)
        check("no raw_b64 stored", "raw_b64" not in entry, True)


def test_cache_eviction_lru():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d, max_bytes=10000, max_entries=3)
        for i in range(5):
            cache.put("sha%02d" % i, "x" * 100, "vision-openrouter")
        cache.evict_if_needed()
        check("eviction respects max_entries", len(list(cache.root.glob("*.json"))) <= 3, True)


def test_cache_concurrent_lock():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        async def run():
            lock1 = await cache.get_lock(_RED_PNG_SHA)
            lock2 = await cache.get_lock(_RED_PNG_SHA)
            check("same lock returned", lock1 is lock2, True)
        asyncio.run(run())


def test_cache_cross_process_lock():
    """PRD §7.8: cross_process_lock acquires an fcntl.flock so concurrent
    workers on the same hash serialize. The lockfile is created and the
    context manager runs without error."""
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        sha = "abc123"
        # Acquiring the lock should work and create the lockfile.
        with cache.cross_process_lock(sha):
            lockfile = cache._lockfile_path(sha)
            check("cross-process lockfile created", lockfile.exists(), True)
        # Re-acquiring after release should work (no stale lock).
        with cache.cross_process_lock(sha):
            check("cross-process lock re-acquirable", True, True)


def test_caption_image_one_call_under_concurrency():
    """PRD §7.8, C7: two concurrent caption_image calls on the same uncached
    hash produce exactly ONE call_model invocation (the cross-process lock +
    cache recheck prevents duplicate work)."""
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        calls = []
        async def mock_call(model, messages, **kw):
            calls.append(model)
            # Simulate latency so the second coroutine arrives while the first holds the lock.
            await asyncio.sleep(0.05)
            return {"choices": [{"message": {"content": json.dumps({
                "summary": "red image", "layout": "solid",
                "visible_text": [], "errors": [], "uncertainties": []
            })}}]}
        # Build two identical ImageRefs (same sha256 from same bytes).
        img = sidecar.ImageRef("image/png", _RED_PNG_B64, _RED_PNG_BYTES, ("messages", 0, (0,)), {})
        img2 = sidecar.ImageRef("image/png", _RED_PNG_B64, _RED_PNG_BYTES, ("messages", 0, (0,)), {})
        async def run():
            r1, r2 = await asyncio.gather(
                sidecar.caption_image(img, call_model=mock_call, cache=cache),
                sidecar.caption_image(img2, call_model=mock_call, cache=cache),
            )
            return r1, r2
        r1, r2 = asyncio.run(run())
        check("concurrent caption: exactly one call_model", len(calls), 1)
        check("concurrent caption: both got a caption", bool(r1) and bool(r2), True)


for t in [test_cache_hit_miss, test_cache_version_invalidation, test_cache_ttl_expiry,
          test_cache_corrupt_quarantine, test_cache_atomic_write, test_cache_eviction_lru,
          test_cache_concurrent_lock, test_cache_cross_process_lock,
          test_caption_image_one_call_under_concurrency]:
    t()


# ── 5. Vision sidecar: Luna -> Luna Pro, strict failure ─────────────────────

print("\nvision sidecar dispatch")


def test_vision_luna_success():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        data = {"messages": [{"role": "user", "content": [user_image_block()]}]}
        mock = make_mock_call_model()
        result = asyncio.run(sidecar.process_vision(data, call_model=mock, cache=cache))
        check("vision processed 1 image", result["images"], 1)
        check("luna called once", len(mock.calls), 1)
        check("luna model is primary", mock.calls[0]["model"], sidecar.VISION_PRIMARY_MODEL)
        check("image replaced with caption", "vision-caption" in str(data["messages"]), True)


def test_vision_luna_fail_luna_pro_success():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        data = {"messages": [{"role": "user", "content": [user_image_block()]}]}
        mock = make_mock_call_model(fail_models={sidecar.VISION_PRIMARY_MODEL})
        result = asyncio.run(sidecar.process_vision(data, call_model=mock, cache=cache))
        check("two attempts (luna + luna pro)", len(mock.calls), 2)
        check("second is secondary", mock.calls[1]["model"], sidecar.VISION_SECONDARY_MODEL)
        check("caption injected", "vision-caption" in str(data["messages"]), True)


def test_vision_both_fail_raises():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        data = {"messages": [{"role": "user", "content": [user_image_block()]}]}
        mock = make_mock_call_model(fail_models={
            sidecar.VISION_PRIMARY_MODEL, sidecar.VISION_SECONDARY_MODEL,
        })
        try:
            asyncio.run(sidecar.process_vision(data, call_model=mock, cache=cache))
            check("both fail raises VisionSidecarUnavailable", False, True)
        except sidecar.VisionSidecarUnavailable:
            check("both fail raises VisionSidecarUnavailable", True, True)
        check("exactly two attempts (no third)", len(mock.calls), 2)


def test_vision_cache_hit_no_model_call():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        cache.put(_RED_PNG_SHA, "cached caption", "vision-openrouter")
        data = {"messages": [{"role": "user", "content": [user_image_block()]}]}
        mock = make_mock_call_model()
        result = asyncio.run(sidecar.process_vision(data, call_model=mock, cache=cache))
        check("cache hit -> no model call", len(mock.calls), 0)
        check("cached caption injected", "cached caption" in str(data["messages"]), True)


for t in [test_vision_luna_success, test_vision_luna_fail_luna_pro_success,
          test_vision_both_fail_raises, test_vision_cache_hit_no_model_call]:
    t()


# ── 6. Premium triggers ────────────────────────────────────────────────────

print("\npremium triggers")


def _seed_loop_messages(reps=3):
    msgs = [{"role": "user", "content": "go"}]
    for i in range(reps):
        msgs.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_%d" % i, "name": "read_file", "input": {"path": "x"}},
        ]})
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_%d" % i, "content": "same error"},
        ]})
    return msgs


def test_premium_tool_error_trigger():
    data = {"messages": [
        {"role": "user", "content": "do it"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "failed"},
        ]},
    ]}
    signals = sidecar.detect_triggers(data)
    check("tool_error detected", "tool_error" in [s["kind"] for s in signals], True)


def test_premium_raw_markup_trigger():
    # Build the raw markup text from chr() so the literal never appears here.
    raw_text = "I will run it.\n" + _MARK + "Bash_tool" + chr(62)
    data = {
        "tools": [{"name": "Bash", "input_schema": {}}],
        "messages": [
            {"role": "user", "content": "run it"},
            {"role": "assistant", "content": [{"type": "text", "text": raw_text}]},
        ],
    }
    signals = sidecar.detect_triggers(data)
    check("raw_tool_markup detected", "raw_tool_markup" in [s["kind"] for s in signals], True)


def test_premium_loop_trigger():
    def real_seq(msgs):
        seq = []
        for msg in msgs:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                for b in (msg.get("content") or []):
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        raw = "%s|%s" % (b.get("name", ""), json.dumps(b.get("input", {}), sort_keys=True))
                        seq.append(hashlib.sha1(raw.encode()).hexdigest()[:12])
        return seq

    def real_detect(seq, max_period=3):
        best = (0, 0)
        for period in range(1, max_period + 1):
            if len(seq) < period * 2:
                break
            reps = 1
            while True:
                span = period * (reps + 1)
                if span > len(seq):
                    break
                tail = seq[-span:]
                if all(tail[i] == tail[i % period] for i in range(span)):
                    reps += 1
                else:
                    break
            if reps >= 2 and reps > best[1]:
                best = (period, reps)
        return best

    glm_lb._tool_call_sequence = real_seq
    glm_lb.detect_cycle = real_detect
    # Ensure sys.modules points at our stub (another test file may have replaced it).
    _saved_lb = sys.modules.get("glm_loop_breaker")
    sys.modules["glm_loop_breaker"] = glm_lb
    try:
        signals = sidecar.detect_triggers({"messages": _seed_loop_messages(3)})
        check("tool_loop detected", "tool_loop" in [s["kind"] for s in signals], True)
    finally:
        glm_lb._tool_call_sequence = lambda msgs: []
        glm_lb.detect_cycle = lambda seq: (0, 0)
        if _saved_lb is not None:
            sys.modules["glm_loop_breaker"] = _saved_lb
        else:
            sys.modules.pop("glm_loop_breaker", None)


def test_premium_no_keyword_trigger():
    data = {"messages": [
        {"role": "user", "content": "This is a very complex and important task. "
         "Please analyze this carefully. It is critical and difficult."},
    ]}
    check("keywords do not trigger", len(sidecar.detect_triggers(data)), 0)


def test_premium_long_context_no_trigger():
    check("long context does not trigger", len(sidecar.detect_triggers({"messages": [{"role": "user", "content": "a" * 500000}]})), 0)


for t in [test_premium_tool_error_trigger, test_premium_raw_markup_trigger,
          test_premium_loop_trigger, test_premium_no_keyword_trigger,
          test_premium_long_context_no_trigger]:
    t()


# ── 7. Premium fingerprint + one-shot + hard-stop ──────────────────────────

print("\npremium fingerprint + one-shot + hard-stop")


def test_fingerprint_stable_for_same_content():
    """Volatile call IDs do not change the fingerprint (PRD §10.2)."""
    s1 = {"kind": "tool_error", "tool_use_id": "tu_abc", "content": "error X"}
    s2 = {"kind": "tool_error", "tool_use_id": "tu_xyz", "content": "error X"}
    fp1 = sidecar.fingerprint_signal(s1, "session-1")
    fp2 = sidecar.fingerprint_signal(s2, "session-1")
    check_true("fingerprint stable for same content", fp1 == fp2)


def test_premium_one_shot_then_hard_stop():
    with tempfile.TemporaryDirectory() as d:
        sidecar._ledger = sidecar.InterventionLedger(d)
        try:
            data1 = {"messages": [
                {"role": "user", "content": "do it"},
                {"role": "assistant", "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
                ]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "failed"},
                ]},
            ], "tools": [{"name": "Bash", "input_schema": {}}]}
            mock = make_mock_call_model()
            r1 = asyncio.run(sidecar.process_premium(data1, call_model=mock))
            check("first occurrence: 1 intervention", r1["interventions"], 1)
            check("first occurrence: 0 hard stops", r1["hard_stops"], 0)
            check("premium called once", len(mock.calls), 1)
            check("advice injected", "premium-recovery" in str(data1["messages"]), True)

            data2 = copy.deepcopy(data1)
            mock2 = make_mock_call_model()
            r2 = asyncio.run(sidecar.process_premium(data2, call_model=mock2))
            check("repeat: 0 interventions", r2["interventions"], 0)
            check("repeat: 1 hard stop", r2["hard_stops"], 1)
            check("repeat: no premium call", len(mock2.calls), 0)
            check("tools intact on repeat (not removed)", "tools" in data2, True)
            check("no hard-stop instruction injected", "SYSTEM" in str(data2["messages"]), False)
        finally:
            sidecar._ledger = None


def test_premium_unavailable_hard_stops():
    with tempfile.TemporaryDirectory() as d:
        sidecar._ledger = sidecar.InterventionLedger(d)
        try:
            data = {"messages": [
                {"role": "user", "content": "do it"},
                {"role": "assistant", "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
                ]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "failed"},
                ]},
            ], "tools": [{"name": "Bash", "input_schema": {}}]}
            mock = make_mock_call_model(fail_models={sidecar.PREMIUM_SIDECAR_MODEL})
            r = asyncio.run(sidecar.process_premium(data, call_model=mock))
            check("premium unavailable: 0 interventions", r["interventions"], 0)
            check("premium unavailable: hard stop", r["hard_stops"], 1)
            check("tools intact (not removed)", "tools" in data, True)
        finally:
            sidecar._ledger = None


def test_premium_payload_bounded():
    data = {"messages": [
        {"role": "user", "content": "x" * 100000},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "failed"},
        ]},
    ], "tools": [{"name": "Bash", "input_schema": {}}]}
    payload = sidecar._build_premium_payload(data, {"kind": "tool_error", "tool_use_id": "t1", "content": "failed"})
    check("payload bounded", len(payload[0]["content"]) <= sidecar.PREMIUM_MAX_PAYLOAD_TOKENS * 4 + 1000, True)


def test_ledger_claim_consumes_fingerprint_on_failure():
    """PRD §7.7: a failed Premium attempt must consume the fingerprint — a
    retry on the next turn must NOT re-call Premium (hard-stop instead)."""
    with tempfile.TemporaryDirectory() as d:
        ledger = sidecar.InterventionLedger(d)
        fp = "test_fp_001"
        sess = "sess-1"
        # First claim succeeds (first claimant).
        check("claim first succeeds", ledger.claim(fp, sess), True)
        # Finalize as failed.
        ledger.record_outcome(fp, sess, {}, success=False)
        # Second claim for the same fingerprint must FAIL (consumed).
        check("claim after failure rejected", ledger.claim(fp, sess), False)


def test_ledger_claim_atomic_one_claimant():
    """PRD §7.7, C7: two sequential claims for the same fingerprint produce
    exactly one claimant (the second is rejected)."""
    with tempfile.TemporaryDirectory() as d:
        ledger = sidecar.InterventionLedger(d)
        fp = "test_fp_002"
        sess = "sess-2"
        c1 = ledger.claim(fp, sess)
        c2 = ledger.claim(fp, sess)
        check("first claimant wins", c1, True)
        check("second claimant rejected", c2, False)


for t in [test_fingerprint_stable_for_same_content, test_premium_one_shot_then_hard_stop,
          test_premium_unavailable_hard_stops, test_premium_payload_bounded,
          test_ledger_claim_consumes_fingerprint_on_failure,
          test_ledger_claim_atomic_one_claimant]:
    t()


# ── 8. Recursion bypass (I5/I10) ───────────────────────────────────────────

print("\nrecursion bypass")


def test_internal_key_bypass():
    old = sidecar.SIDECAR_API_KEY
    sidecar.SIDECAR_API_KEY = "secret-internal-key"
    try:
        check("internal key bypasses", sidecar.is_internal_key({"key": "secret-internal-key"}), True)
        check("wrong key does not bypass", sidecar.is_internal_key({"key": "wrong-key"}), False)
        check("no key does not bypass", sidecar.is_internal_key(None), False)
        check("forged metadata still blocked", sidecar.is_internal_key({"key": "wrong", "metadata": {"sidecar": True}}), False)
    finally:
        sidecar.SIDECAR_API_KEY = old


test_internal_key_bypass()


# ── 9. Orchestration ───────────────────────────────────────────────────────

print("\norchestration")


def test_process_request_vision_injects_caption():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": [user_image_block()]}]}
        mock = make_mock_call_model()
        result = asyncio.run(sidecar.process_request(data, call_model=mock, cache=cache))
        check("vision processed", result["vision"]["images"], 1)
        check("image replaced with caption", "vision-caption" in str(data["messages"]), True)


def test_process_request_no_images_no_premium():
    data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hello"}]}
    mock = make_mock_call_model()
    result = asyncio.run(sidecar.process_request(data, call_model=mock))
    check("no vision calls", result["vision"]["images"], 0)
    check("no premium triggers", result["premium"]["triggers"], 0)


def test_process_request_fail_open_on_unexpected_error():
    def bad_call_model(model, messages, **kw):
        raise RuntimeError("unexpected")
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        sidecar._ledger = sidecar.InterventionLedger(d)
        try:
            data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": [user_image_block()]}]}
            result = asyncio.run(sidecar.process_request(data, call_model=bad_call_model, cache=cache))
            check("vision fail-open recorded", result["vision"].get("error"), "RuntimeError")
        finally:
            sidecar._ledger = None


for t in [test_process_request_vision_injects_caption,
          test_process_request_no_images_no_premium,
          test_process_request_fail_open_on_unexpected_error]:
    t()


# ── 10. Text-reference never triggers a new vision call ────────────────────

print("\ntext reference")


def test_text_reference_no_vision_call():
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)
        cache.put(_RED_PNG_SHA, "[vision-caption]Red[/vision-caption]", "vision-openrouter")
        data = {"messages": [
            {"role": "user", "content": [user_image_block()]},
            {"role": "assistant", "content": "I see red."},
            {"role": "user", "content": "re-analyze the previous screenshot"},
        ]}
        mock = make_mock_call_model()
        result = asyncio.run(sidecar.process_vision(data, call_model=mock, cache=cache))
        check("history image found", result["images"], 1)
        check("cache hit -> no model call", len(mock.calls), 0)
        check("caption in history", "vision-caption" in str(data["messages"]), True)


test_text_reference_no_vision_call()


# ── Tool-argument repair (PRD-tool-argument-guard §10) ─────────────────────


def test_tool_repair_success():
    """Premium repairs invalid tool arguments and returns the fixed dict."""
    schema = {
        "type": "object",
        "properties": {"taskId": {"type": "string"}, "status": {"type": "string"}},
        "required": ["taskId", "status"],
        "additionalProperties": False,
    }
    invalid = {"task_id": "t1", "status": "done"}  # wrong field name + bad enum
    errors = [{"keyword": "required", "path": "$", "expected": "taskId"}]
    mock = make_mock_call_model(premium_obj={"arguments": {"taskId": "t1", "status": "completed"}})
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        result = asyncio.run(sidecar.repair_tool_arguments(
            "TaskUpdate", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        check("tool repair returns dict", isinstance(result, dict), True)
        check("tool repair fixed taskId", result.get("taskId"), "t1")
        check("tool repair fixed status", result.get("status"), "completed")
        check("tool repair one call", len(mock.calls), 1)
    finally:
        sidecar._ledger = None


test_tool_repair_success()


def test_tool_repair_one_shot_ledger():
    """Same fingerprint -> only one Premium call, second returns None (I7)."""
    schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    invalid = {"y": 1}
    errors = [{"keyword": "required", "path": "$", "expected": "x"}]
    mock = make_mock_call_model(premium_obj={"arguments": {"x": "fixed"}})
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        r1 = asyncio.run(sidecar.repair_tool_arguments(
            "Test", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        r2 = asyncio.run(sidecar.repair_tool_arguments(
            "Test", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        check("first repair succeeds", r1 is not None, True)
        check("second repair skipped (ledger)", r2, None)
        check("only one premium call", len(mock.calls), 1)
    finally:
        sidecar._ledger = None


test_tool_repair_one_shot_ledger()


def test_tool_repair_secret_disables():
    """Secret-bearing arguments skip Premium (PRD §10.1)."""
    schema = {"type": "object", "properties": {"api_key": {"type": "string"}}, "required": ["api_key"]}
    invalid = {"api_key": "sk-secret-123"}
    errors = [{"keyword": "additionalProperties", "path": "$", "expected": ""}]
    mock = make_mock_call_model(premium_obj={"arguments": {"api_key": "x"}})
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        result = asyncio.run(sidecar.repair_tool_arguments(
            "Test", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        check("secret args skip premium", result, None)
        check("no premium call for secret", len(mock.calls), 0)
    finally:
        sidecar._ledger = None


test_tool_repair_secret_disables()


def test_tool_repair_premium_unavailable():
    """Premium call fails -> returns None (caller rejects the tool call)."""
    schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    invalid = {}
    errors = [{"keyword": "required", "path": "$", "expected": "x"}]
    mock = make_mock_call_model(fail_models={sidecar.PREMIUM_SIDECAR_MODEL})
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        result = asyncio.run(sidecar.repair_tool_arguments(
            "Test", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        check("premium failure returns None", result, None)
    finally:
        sidecar._ledger = None


test_tool_repair_premium_unavailable()


def test_tool_repair_invalid_output():
    """Premium returns malformed output -> returns None."""
    schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    invalid = {}
    errors = [{"keyword": "required", "path": "$", "expected": "x"}]
    # Return a response missing "arguments"
    mock = make_mock_call_model(premium_obj={"diagnosis": "wrong shape"})
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        result = asyncio.run(sidecar.repair_tool_arguments(
            "Test", schema, invalid, errors, "sess-1", call_model=mock,
        ))
        check("invalid repair output returns None", result, None)
    finally:
        sidecar._ledger = None


test_tool_repair_invalid_output()


def test_validate_tool_repair():
    """validate_tool_repair accepts {arguments:{}} and rejects everything else."""
    check("valid repair", sidecar.validate_tool_repair({"arguments": {"x": 1}}), {"arguments": {"x": 1}})
    try:
        sidecar.validate_tool_repair({"x": 1})
        check("missing arguments raises", False, True)
    except ValueError:
        check("missing arguments raises", True, True)
    try:
        sidecar.validate_tool_repair({"arguments": "not a dict"})
        check("non-dict arguments raises", False, True)
    except ValueError:
        check("non-dict arguments raises", True, True)
    try:
        sidecar.validate_tool_repair({"arguments": {}, "extra": 1})
        check("extra fields raise", False, True)
    except ValueError:
        check("extra fields raise", True, True)


test_validate_tool_repair()


def test_has_secret_field():
    """_has_secret_field detects secret-named fields recursively."""
    check("top-level secret", sidecar._has_secret_field({"api_key": "x"}), True)
    check("nested secret", sidecar._has_secret_field({"config": {"password": "x"}}), True)
    check("list secret", sidecar._has_secret_field([{"token": "x"}]), True)
    check("no secret", sidecar._has_secret_field({"x": 1, "y": "z"}), False)
    check("empty no secret", sidecar._has_secret_field({}), False)


test_has_secret_field()


# ── Data residency policy (PRD §7.1, C2) ────────────────────────────────────


def test_residency_policy_from_key():
    """ResidencyPolicy.from_key derives the decision from authenticated key tags/metadata."""
    # Default: allow (no tags, no metadata).
    p = sidecar.ResidencyPolicy.from_key(None)
    check("none key → allow", p.mode, "allow")
    check("none key allows egress", p.allows_egress, True)

    # Plain dict with tags.
    p = sidecar.ResidencyPolicy.from_key({"tags": ["residency:china-only"]})
    check("tag china-only → china-only", p.mode, "china-only")
    check("china-only blocks egress", p.allows_egress, False)
    check("china-only is_china_only", p.is_china_only, True)

    # Plain dict with metadata (canonical field: data_residency).
    p = sidecar.ResidencyPolicy.from_key({"metadata": {"data_residency": "china-only"}})
    check("metadata china-only → china-only", p.mode, "china-only")

    # Other tags → allow.
    p = sidecar.ResidencyPolicy.from_key({"tags": ["team:backend"]})
    check("other tag → allow", p.mode, "allow")

    # Pydantic-like object (getattr).
    class _FakeKey:
        tags = ["residency:china-only"]
        metadata = {}
    p = sidecar.ResidencyPolicy.from_key(_FakeKey())
    check("pydantic tag china-only → china-only", p.mode, "china-only")


test_residency_policy_from_key()


def test_residency_check_egress_raises_403():
    """A china-only policy.check_egress raises SidecarPolicyDenied (403)."""
    p = sidecar.ResidencyPolicy("china-only")
    raised = False
    try:
        p.check_egress("vision")
    except sidecar.SidecarPolicyDenied as e:
        raised = True
        check("policy denied http_status 403", e.http_status, 403)
        check("policy denied error_code", e.error_code, "SIDECAR_POLICY_DENIED")
    check("china-only check_egress raises", raised, True)

    # allow policy does not raise.
    p2 = sidecar.ResidencyPolicy("allow")
    try:
        p2.check_egress("vision")
        check("allow check_egress no raise", True, True)
    except sidecar.SidecarPolicyDenied:
        check("allow check_egress no raise", False, True)


test_residency_check_egress_raises_403()


def test_residency_china_only_blocks_vision_cache_miss():
    """PRD §7.1: a china-only key with an image cache miss must raise
    SIDECAR_POLICY_DENIED before Luna. No external call."""
    red_png = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII="
    data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "what color?"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": red_png}},
    ]}]}

    # Set china-only residency via contextvar.
    token = sidecar._residency_ctx.set(sidecar.ResidencyPolicy("china-only"))
    # Use an isolated cache that's empty (cache miss).
    d = tempfile.mkdtemp()
    cache = sidecar.CaptionCache(d)
    try:
        raised = False
        try:
            asyncio.run(sidecar.process_vision(data, cache=cache))
        except sidecar.SidecarPolicyDenied as e:
            raised = True
            check("vision china-only 403", e.http_status, 403)
        check("vision china-only raises on cache miss", raised, True)
    finally:
        sidecar._residency_ctx.reset(token)


test_residency_china_only_blocks_vision_cache_miss()


def test_residency_china_only_allows_cache_hit():
    """PRD §7.1: a china-only key with a cache HIT is permitted (local lookup)."""
    red_png = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII="
    data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "what color?"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": red_png}},
    ]}]}

    # Pre-populate the cache so it's a hit.
    d = tempfile.mkdtemp()
    cache = sidecar.CaptionCache(d)
    images = sidecar.extract_images(data)
    sha = images[0].sha256
    cache.put(sha, "RED (cached caption)", "test-model")

    token = sidecar._residency_ctx.set(sidecar.ResidencyPolicy("china-only"))
    try:
        result = asyncio.run(sidecar.process_vision(data, cache=cache))
        check("china-only cache hit succeeds", result["images"], 1)
        check("china-only cache hit count", result["cache_hits"], 1)
    finally:
        sidecar._residency_ctx.reset(token)


test_residency_china_only_allows_cache_hit()


def test_residency_china_only_blocks_premium():
    """PRD §7.1: a china-only key with a premium trigger must inject the safe
    blocker (hard-stop), not call Premium. No external egress."""
    # A request with a tool_error trigger (tool_result with is_error=true).
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": "run ls"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Error: command not found", "is_error": True}]},
    ]}

    token = sidecar._residency_ctx.set(sidecar.ResidencyPolicy("china-only"))
    # Mock call_model that would FAIL the test if called (china-only must not call it).
    called = []
    async def mock_call(model, messages, **kw):
        called.append(model)
        return {"choices": [{"message": {"content": "{}"}}]}
    try:
        result = asyncio.run(sidecar.process_premium(data, call_model=mock_call))
        check("china-only premium no external call", len(called), 0)
        check("china-only premium hard-stops", result["hard_stops"] >= 1, True)
    finally:
        sidecar._residency_ctx.reset(token)


test_residency_china_only_blocks_premium()


def test_residency_china_only_blocks_tool_repair():
    """PRD §7.1: a china-only key must not call Premium for tool repair."""
    schema = {"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]}
    invalid = {"task_id": "t1"}
    errors = [{"keyword": "required", "path": "$", "expected": "taskId"}]

    token = sidecar._residency_ctx.set(sidecar.ResidencyPolicy("china-only"))
    called = []
    async def mock_call(model, messages, **kw):
        called.append(model)
        return {"choices": [{"message": {"content": '{"arguments": {"taskId": "t1"}}'}}]}
    d = tempfile.mkdtemp()
    sidecar._ledger = sidecar.InterventionLedger(d)
    try:
        result = asyncio.run(sidecar.repair_tool_arguments(
            "TaskUpdate", schema, invalid, errors, "sess-1", call_model=mock_call,
        ))
        check("china-only tool repair returns None", result, None)
        check("china-only tool repair no external call", len(called), 0)
    finally:
        sidecar._residency_ctx.reset(token)
        sidecar._ledger = None


test_residency_china_only_blocks_tool_repair()


# ── 11. PRD-remove-tool-disabling: counterexamples (§6.1) ───────────────────
#
# These tests assert the post-fix behavior: the hard-stop mechanism no longer
# removes tools, the ledger TTL is 15 min, and raw tool markup is a structural
# error (tested in test_anthropic_stream_guard.py).  They must pass after the
# fix and would have failed before it.

print("\nPRD-remove-tool-disabling: counterexamples")


def _tool_error_data():
    """A request with a tool_error trigger (Bash failed)."""
    return {"messages": [
        {"role": "user", "content": "do it"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
             "content": "command timed out after 600s"},
        ]},
    ], "tools": [{"name": "Bash", "input_schema": {}}]}


def test_repeat_fingerprint_keeps_tools():
    """§6.1(1): same tool_error fingerprint three times → tools always present,
    hard_stops counter increments, request never modified."""
    with tempfile.TemporaryDirectory() as d:
        sidecar._ledger = sidecar.InterventionLedger(d)
        try:
            for i in range(3):
                data = copy.deepcopy(_tool_error_data())
                mock = make_mock_call_model()
                r = asyncio.run(sidecar.process_premium(data, call_model=mock))
                check("round %d: tools intact" % i, "tools" in data, True)
                check("round %d: tools count unchanged" % i,
                      len(data.get("tools", [])), 1)
                check("round %d: tool_choice not popped" % i,
                      "tool_choice" not in data, True)
            # After the first intervention, repeats must increment hard_stops
            # WITHOUT touching the request.
            data_final = copy.deepcopy(_tool_error_data())
            mock_f = make_mock_call_model()
            r_first = asyncio.run(sidecar.process_premium(data_final, call_model=mock_f))
            data_repeat = copy.deepcopy(_tool_error_data())
            mock_r = make_mock_call_model()
            r_repeat = asyncio.run(sidecar.process_premium(data_repeat, call_model=mock_r))
            check("repeat: hard_stops >= 1", r_repeat["hard_stops"] >= 1, True)
            check("repeat: tools still intact", "tools" in data_repeat, True)
            check("repeat: tools count unchanged", len(data_repeat.get("tools", [])), 1)
        finally:
            sidecar._ledger = None


def test_hard_stop_instruction_absent():
    """§6.1(2): _inject_hard_stop and HARD_STOP_INSTRUCTION must not exist in
    the loaded module (grep-style regression guard)."""
    check("no _inject_hard_stop", hasattr(sidecar, "_inject_hard_stop"), False)
    check("no HARD_STOP_INSTRUCTION",
          hasattr(sidecar, "HARD_STOP_INSTRUCTION"), False)
    # Also confirm the source file has no references (defense in depth).
    source = CALLBACK.read_text(encoding="utf-8")
    check("source: no _inject_hard_stop",
          "_inject_hard_stop" in source, False)
    check("source: no HARD_STOP_INSTRUCTION",
          "HARD_STOP_INSTRUCTION" in source, False)


def test_ledger_ttl_is_15min():
    """§6.1(3): PREMIUM_LEDGER_TTL_SECONDS must be 900 (15 min), not 86400."""
    check("ledger TTL is 900", sidecar.PREMIUM_LEDGER_TTL_SECONDS, 900)


def test_ledger_entry_expires_after_ttl():
    """§6.1(3): a ledger entry is repeat within TTL, fresh after expiry."""
    with tempfile.TemporaryDirectory() as d:
        ledger = sidecar.InterventionLedger(d, ttl_seconds=1)
        fp = "fp_expire_test"
        sess = "sess-expire"
        check("claim first succeeds", ledger.claim(fp, sess), True)
        ledger.record_outcome(fp, sess, {}, success=True)
        check("within TTL: is_repeat", ledger.is_repeat(fp, sess), True)
        time.sleep(1.2)
        check("after TTL: not repeat", ledger.is_repeat(fp, sess), False)


def test_session_cap_keeps_tools():
    """§6.1(5): reaching the per-session intervention cap must NOT remove tools.
    The cap only stops calling Premium (cost protection)."""
    with tempfile.TemporaryDirectory() as d:
        # Use a cap of 1 so the second distinct fingerprint hits the cap.
        ledger = sidecar.InterventionLedger(d, max_per_session=1)
        sidecar._ledger = ledger
        sess_meta = {"metadata": {"session_id": "cap-test-session"}}
        try:
            # First distinct fingerprint → intervention.
            data1 = copy.deepcopy(_tool_error_data())
            data1.update(sess_meta)
            mock1 = make_mock_call_model()
            asyncio.run(sidecar.process_premium(data1, call_model=mock1))
            check("cap: first intervention tools intact",
                  "tools" in data1, True)

            # Second distinct fingerprint (different error text, same session)
            # → cap reached, no Premium call, but tools MUST remain.
            data2 = {"messages": [
                {"role": "user", "content": "do it again"},
                {"role": "assistant", "content": [
                    {"type": "tool_use", "id": "t2", "name": "Bash",
                     "input": {"command": "pwd"}},
                ]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                     "content": "a different error message"},
                ]},
            ], "tools": [{"name": "Bash", "input_schema": {}}]}
            data2.update(sess_meta)
            mock2 = make_mock_call_model()
            r2 = asyncio.run(sidecar.process_premium(data2, call_model=mock2))
            check("cap: no premium call on second", len(mock2.calls), 0)
            check("cap: tools intact after cap", "tools" in data2, True)
            check("cap: tools count unchanged", len(data2["tools"]), 1)
        finally:
            sidecar._ledger = None


def test_premium_unavailable_keeps_tools():
    """Premium unavailable (SidecarCallError) must increment hard_stops but
    leave tools intact — no _inject_hard_stop, no instruction injection."""
    with tempfile.TemporaryDirectory() as d:
        sidecar._ledger = sidecar.InterventionLedger(d)
        try:
            data = copy.deepcopy(_tool_error_data())
            mock = make_mock_call_model(fail_models={sidecar.PREMIUM_SIDECAR_MODEL})
            r = asyncio.run(sidecar.process_premium(data, call_model=mock))
            check("unavailable: hard_stops counted", r["hard_stops"] >= 1, True)
            check("unavailable: tools intact", "tools" in data, True)
            check("unavailable: no SYSTEM instruction",
                  "SYSTEM" in str(data["messages"]), False)
        finally:
            sidecar._ledger = None


def test_china_only_hard_stop_keeps_tools():
    """China-only key with a premium trigger must hard-stop (no egress) but
    leave tools intact."""
    data = copy.deepcopy(_tool_error_data())
    token = sidecar._residency_ctx.set(sidecar.ResidencyPolicy("china-only"))
    called = []

    async def mock_call(model, messages, **kw):
        called.append(model)
        return {"choices": [{"message": {"content": "{}"}}]}

    try:
        result = asyncio.run(sidecar.process_premium(data, call_model=mock_call))
        check("china-only: no external call", len(called), 0)
        check("china-only: hard_stops >= 1", result["hard_stops"] >= 1, True)
        check("china-only: tools intact", "tools" in data, True)
    finally:
        sidecar._residency_ctx.reset(token)


for t in [test_repeat_fingerprint_keeps_tools,
          test_hard_stop_instruction_absent,
          test_ledger_ttl_is_15min,
          test_ledger_entry_expires_after_ttl,
          test_session_cap_keeps_tools,
          test_premium_unavailable_keeps_tools,
          test_china_only_hard_stop_keeps_tools]:
    t()


# ── runner ─────────────────────────────────────────────────────────────────

def test_no_failures():
    """Pytest entry point: assert every check() across all test_* functions succeeded."""
    assert not FAILURES, "%d checks failed: %s" % (len(FAILURES), ", ".join(FAILURES))


if __name__ == "__main__":
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all sidecar tests passed")
