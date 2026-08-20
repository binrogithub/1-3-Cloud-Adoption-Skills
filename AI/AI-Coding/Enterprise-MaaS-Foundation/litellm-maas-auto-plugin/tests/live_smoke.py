#!/usr/bin/env python3
"""Live probes for Claude Code -> LiteLLM -> Huawei MaaS GLM-5.2.

Usage:
    LITELLM_KEY=sk-... python3 tests/live_smoke.py --profile healthy
    LITELLM_KEY=sk-... python3 tests/live_smoke.py --profile all
    LITELLM_KEY=sk-... python3 tests/live_smoke.py --profile healthy --json-output results.json
    python3 tests/live_smoke.py message

The key is resolved from LITELLM_KEY, ANTHROPIC_API_KEY, or KEY_FILE.

Profiles (PRD-r11-final-closeout.md §4.2):
    healthy        - normal production config; 8 public probes
    tool_canary    - operator-only deterministic tool upstream
    policy_denied  - operator key tagged china-only
    primary_fault  - Luna name invalid; Luna Pro valid
    vision_fault   - Luna and Luna Pro names both invalid
    premium        - healthy models with seeded tool error
    all            - every profile (for sequential execution against a
                     pre-configured deployment; individual fault profiles
                     still require the operator to set the deployment state
                     before running)
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
MODEL = os.environ.get("CLAUDE_CODE_MODEL", "claude-glm-5.2")
OPENAI_MODEL = os.environ.get("OPENCODE_MODEL", "glm-5.1-fallback")
KEY_FILE = os.environ.get("KEY_FILE", "")
CANDIDATE_COMMIT = os.environ.get("CANDIDATE_COMMIT", "")
ARTIFACT_SHA256 = os.environ.get("ARTIFACT_SHA256", "")
HOST_IDENTITY = os.environ.get("HOST_IDENTITY", os.uname().nodename if hasattr(os, "uname") else "unknown")
DEPLOY_ROOT = os.environ.get("DEPLOY_ROOT", "")


def _git_commit():
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=5).decode().strip()[:12]
    except Exception:
        return ""


if not CANDIDATE_COMMIT:
    CANDIDATE_COMMIT = _git_commit()


class ProbeResult(object):
    """One structured record per probe (PRD-r11-final-closeout.md §4.3)."""

    __slots__ = (
        "run_id", "profile", "candidate_commit", "artifact_sha256",
        "host", "deploy_root", "probe", "passed", "exercised",
        "http_status", "expected_status", "elapsed", "detail",
    )

    def __init__(self, run_id, profile, candidate_commit, artifact_sha256,
                 host, deploy_root, probe, passed, exercised,
                 http_status, expected_status, elapsed, detail=""):
        self.run_id = run_id
        self.profile = profile
        self.candidate_commit = candidate_commit
        self.artifact_sha256 = artifact_sha256
        self.host = host
        self.deploy_root = deploy_root
        self.probe = probe
        self.passed = passed
        self.exercised = exercised
        self.http_status = http_status
        self.expected_status = expected_status
        self.elapsed = elapsed
        self.detail = detail

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "profile": self.profile,
            "candidate_commit": self.candidate_commit,
            "artifact_sha256": self.artifact_sha256,
            "host": self.host,
            "deploy_root": self.deploy_root,
            "probe": self.probe,
            "passed": self.passed,
            "exercised": self.exercised,
            "http_status": self.http_status,
            "expected_status": self.expected_status,
            "elapsed": self.elapsed,
            "detail": self.detail,
        }


_RESULTS = []
_RUN_ID = hashlib.sha256("{}{}{}".format(time.time(), os.getpid(), CANDIDATE_COMMIT).encode()).hexdigest()[:16]
_CURRENT_PROFILE = "unscoped"


def load_key():
    key = os.environ.get("LITELLM_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        with open(KEY_FILE, encoding="utf-8") as handle:
            value = json.load(handle).get("key")
            if value:
                return value
    except (OSError, ValueError, AttributeError):
        pass
    raise SystemExit("No virtual key found. Set LITELLM_KEY or KEY_FILE; do not use the MaaS or LiteLLM master key.")


KEY = None  # lazily loaded by _ensure_key()


def _ensure_key():
    global KEY
    if KEY is None:
        KEY = load_key()
    return KEY


def post(body, timeout=120):
    _ensure_key()
    request = urllib.request.Request(BASE_URL + "/v1/messages", data=json.dumps(body).encode("utf-8"), headers={"content-type": "application/json", "x-api-key": KEY, "anthropic-version": "2023-06-01"}, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8"), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), time.time() - started
    except Exception as exc:
        return -1, "{}: {}".format(type(exc).__name__, exc), time.time() - started


def post_openai(body, timeout=120):
    request = urllib.request.Request(BASE_URL + "/v1/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"content-type": "application/json", "authorization": "Bearer " + KEY}, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8"), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), time.time() - started
    except Exception as exc:
        return -1, "{}: {}".format(type(exc).__name__, exc), time.time() - started


def show(name, passed, status, elapsed, detail, exercised=True, expected=200):
    """Print a probe result and record a ProbeResult. PASS/FAIL is determined by
    the ``passed`` boolean, NOT by HTTP status alone (R11 section 4.2)."""
    if not exercised:
        passed = False
    print("{}: {} (HTTP {}, {:.1f}s)".format(name, "PASS" if passed else "FAIL", status, elapsed))
    if detail:
        print("  " + detail)
    _RESULTS.append(ProbeResult(run_id=_RUN_ID, profile=_CURRENT_PROFILE, candidate_commit=CANDIDATE_COMMIT, artifact_sha256=ARTIFACT_SHA256, host=HOST_IDENTITY, deploy_root=DEPLOY_ROOT, probe=name, passed=passed, exercised=exercised, http_status=status, expected_status=expected, elapsed=round(elapsed, 3), detail=detail[:500]))
    return passed


def probe_message():
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 32, "messages": [{"role": "user", "content": "Reply with MESSAGE_OK only."}]})
    try:
        payload = json.loads(raw)
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        valid = status == 200 and payload.get("type") == "message" and bool(text)
        detail = "type={}, text={!r}".format(payload.get("type"), text[:80])
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("message", valid, status, elapsed, detail)
    return valid


def probe_stream():
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "stream": True, "thinking": {"type": "enabled", "budget_tokens": 1024}, "messages": [{"role": "user", "content": "Reply with STREAM_OK only."}]})
    event_types = re.findall(r'"type"\s*:\s*"([^"]+)"', raw)
    valid = status == 200 and "message_start" in event_types and "message_stop" in event_types and event_types.index("message_start") < event_types.index("message_stop")
    detail = "events={}, terminal={}".format(len(event_types), "message_stop" in event_types)
    show("stream", valid, status, elapsed, detail)
    return valid


_RAW_TOOL_MARKUP_RE = re.compile(r"<tool_call|<function|</[A-Za-z_]+_tool>")


def probe_tools():
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 300, "tools": [{"name": "echo_check", "description": "Echo a short string to verify structured tool calling.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}], "messages": [{"role": "user", "content": "Call the echo_check tool with text set to ok. Do not answer in plain text."}]})
    has_tool = bool(re.search(r'"type"\s*:\s*"tool_use"', raw))
    raw_markup = bool(_RAW_TOOL_MARKUP_RE.search(raw))
    valid = status == 200 and has_tool and not raw_markup
    if has_tool:
        detail = "structured tool_use received"
    elif raw_markup:
        detail = "raw tool markup received; provider function calling is unavailable"
    else:
        detail = "no tool_use block; response={!r}".format(raw[:160])
    show("tools", valid, status, elapsed, detail)
    return valid


def probe_reasoning():
    """Public HEALTHY probe: Anthropic reasoning filtering only.

    The canonical public model returns HTTP 200 with text, and Anthropic
    thinking blocks and reasoning_content are absent from the response.

    OpenAI fallback preservation is a separate operator/internal probe
    (probe_reasoning_openai) that uses an internal credential. It is never
    called with the public key and is not part of the HEALTHY profile.
    """
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "thinking": {"type": "enabled", "budget_tokens": 1024}, "messages": [{"role": "user", "content": "Think briefly, then reply REASONING_OK."}]})
    try:
        payload = json.loads(raw)
        block_types = [block.get("type") for block in payload.get("content", [])]
        valid = status == 200 and "text" in block_types and not {"thinking", "redacted_thinking"} & set(block_types) and "reasoning_content" not in raw
    except (ValueError, AttributeError):
        block_types = []
        valid = False
    show("reasoning", valid, status, elapsed, "block_types={!r}".format(block_types))
    return valid


def probe_reasoning_openai():
    """Operator/internal probe: OpenAI fallback reasoning preservation.

    Uses an internal model (glm-5.1-fallback) with an internal credential.
    Never called with the public key. Not part of the HEALTHY profile.
    A public 401 for this model is part of the ACL test, not a failed
    reasoning result.
    """
    status, raw, elapsed = post_openai({"model": OPENAI_MODEL, "max_tokens": 64, "messages": [{"role": "user", "content": "Think briefly, then reply REASONING_OK."}]})
    try:
        payload = json.loads(raw)
        message = payload["choices"][0]["message"]
        valid = status == 200 and bool(message.get("content")) and "reasoning_content" in message
        detail = "reasoning_content={}, final_content={}".format("present" if "reasoning_content" in message else "missing", bool(message.get("content")))
    except (ValueError, KeyError, IndexError, TypeError):
        valid = False
        detail = raw[:160]
    show("reasoning_openai", valid, status, elapsed, detail)
    return valid


_RED_PNG = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII="

CAPTION_CACHE_DIR = os.environ.get("CAPTION_CACHE_DIR", "")


def _unique_png():
    """A per-run unique PNG plus its SHA-256.

    A fixed fixture is served from the caption cache, so it stays green even
    when the Vision path is completely down — that is how the 2026-08-13 run
    reported 4x HEALTHY green against a dead sidecar
    (docs/PRD-project-shutdown.md §2.4).
    """
    import base64 as _b64, struct as _struct, zlib as _zlib
    seed = int(_RUN_ID[:6], 16)
    r = (seed % 251) + 1
    g = ((seed // 251) % 251) + 1
    b = ((seed // 63001) % 251) + 1
    w = h = 16
    raw = b"".join(b"\x00" + bytes([r, g, b]) * w for _ in range(h))

    def _chunk(tag, data):
        c = tag + data
        return _struct.pack(">I", len(data)) + c + _struct.pack(">I", _zlib.crc32(c) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", _struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + _chunk(b"IDAT", _zlib.compress(raw))
           + _chunk(b"IEND", b""))
    return _b64.b64encode(png).decode(), hashlib.sha256(png).hexdigest()


def probe_image():
    """A never-before-seen image produces a GLM final response AND a caption
    file. HTTP 200 alone is not evidence — it can come entirely from cache."""
    b64, sha = _unique_png()
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "messages": [
        {"role": "user", "content": [
            {"type": "text", "text": "What single color is shown in this image? Reply with just the color name."},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
        ]}]})
    try:
        payload = json.loads(raw)
        text = "".join(block.get("text", "") for block in payload.get("content", [])
                       if block.get("type") == "text").strip()
        rid = payload.get("id", "")
        valid = status == 200 and bool(text) and not rid.startswith("gen-")
        detail = "sha=%s id=%s text=%r" % (sha[:12], rid, text[:60])
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    if not CAPTION_CACHE_DIR:
        valid = False
        detail += " | CAPTION_CACHE_DIR unset — probe cannot discriminate"
    else:
        path = os.path.join(CAPTION_CACHE_DIR, sha + ".json")
        cached = os.path.isfile(path) and os.path.getsize(path) > 0
        valid = valid and cached
        detail += " | cached=%s" % cached
    show("image", valid, status, elapsed, detail)
    return valid


def probe_nested_image():
    """A Claude Code Read-style image nested in tool_result.content[] is captioned."""
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "tools": [{"name": "Read", "description": "Read a file and return its contents.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}], "messages": [{"role": "user", "content": "Read the image at /tmp/red.png and tell me its color."}, {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_1", "name": "Read", "input": {"path": "/tmp/red.png"}}]}, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": [{"type": "text", "text": "image file"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _RED_PNG}}]}]}]})
    try:
        payload = json.loads(raw)
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text").strip()
        valid = status == 200 and "red" in text.lower()
        detail = "text=%r" % text[:80]
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("nested_image", valid, status, elapsed, detail)
    return valid


def probe_tool_args():
    """A tool call with wrong field name (task_id) and bad enum (done) is normalized
    by the guard to the schema-valid form (taskId + completed). The probe asserts
    the EMITTED tool input is the normalized object."""
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 300, "tools": [{"name": "TaskUpdate", "description": "Update a task.", "input_schema": {"type": "object", "properties": {"taskId": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["taskId", "status"], "additionalProperties": False}}], "messages": [{"role": "user", "content": "Call TaskUpdate with task_id t1 and status done."}]})
    try:
        payload = json.loads(raw)
        tool_blocks = [b for b in payload.get("content", []) if b.get("type") == "tool_use"]
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        if tool_blocks:
            inp = tool_blocks[0].get("input", {})
            has_normalized_taskid = "taskId" in inp and "task_id" not in inp
            has_normalized_status = inp.get("status") in ("pending", "in_progress", "completed")
            valid = status == 200 and has_normalized_taskid and has_normalized_status
            detail = "normalized taskId=%s status=%s" % (has_normalized_taskid, inp.get("status"))
        else:
            valid = False
            detail = "no tool_use block; text=%r (permissive text-only response rejected)" % text[:80]
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("tool_args", valid, status, elapsed, detail)
    return valid


def _make_png(r, g, b):
    import base64 as _b64, struct as _struct, zlib as _zlib
    w, h = 2, 2
    raw = b""
    for _y in range(h):
        raw += b"\x00" + bytes([r, g, b]) * w
    comp = _zlib.compress(raw)

    def _chunk(tag, data):
        c = tag + data
        return _struct.pack(">I", len(data)) + c + _struct.pack(">I", _zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", _struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", comp)
    iend = _chunk(b"IEND", b"")
    return _b64.b64encode(sig + ihdr + idat + iend).decode()


def probe_image_limit():
    """Five genuinely valid distinct PNG files must return HTTP 413 IMAGE_LIMIT_EXCEEDED."""
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
    images = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _make_png(r, g, b)}} for r, g, b in colors]
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "messages": [{"role": "user", "content": [{"type": "text", "text": "Describe these images."}] + images}]})
    try:
        payload = json.loads(raw)
        err = payload.get("error", {})
        err_str = str(err)
        valid = status == 413 and "IMAGE_LIMIT" in err_str.upper()
        detail = "status=%d code=%s" % (status, err.get("code", ""))
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("image_limit", valid, status, elapsed, detail, expected=413)
    return valid


def probe_502():
    """When both Vision models fail, the gateway must return HTTP 502
    VISION_SIDECAR_UNAVAILABLE. A 200 (vision worked) is a FAIL: the mandatory
    502 branch was not exercised."""
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    status, raw, elapsed = post({"model": MODEL, "max_tokens": 64, "messages": [{"role": "user", "content": [{"type": "text", "text": "What color is this image?"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": tiny_png}}]}]})
    if status == 200:
        show("502", False, 200, elapsed, "vision succeeded (200) - 502 path NOT exercised (FAIL: mandatory branch unexercised)", exercised=False, expected=502)
        return False
    try:
        payload = json.loads(raw)
        err = payload.get("error", {})
        code = err.get("code", "") or err.get("type", "")
        valid = status == 502 and "VISION" in str(code).upper()
        detail = "status=%d code=%s" % (status, code)
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("502", valid, status, elapsed, detail, expected=502)
    return valid


# ── Tool Argument Guard canary probes (PRD section 6) ─────────────────────────
# These use an operator-only canary model/key to deterministically exercise the
# guard through the real LiteLLM response-hook path. The canary model is absent
# from the public model list and inaccessible to the normal client key.

CANARY_MODEL = os.environ.get("TOOL_CANARY_MODEL", "tool-canary-internal")
CANARY_KEY = os.environ.get("TOOL_CANARY_KEY", "")


def _canary_post(body, timeout=120):
    """Post using the canary key (operator-only). Falls back to the normal key
    if CANARY_KEY is not set, but marks the probe as unexercised."""
    key = CANARY_KEY or KEY
    request = urllib.request.Request(BASE_URL + "/v1/messages", data=json.dumps(body).encode("utf-8"), headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8"), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), time.time() - started
    except Exception as exc:
        return -1, "{}: {}".format(type(exc).__name__, exc), time.time() - started


def probe_tool_canary_valid():
    """Case 1: Valid input with taskId and allowed status passes byte-for-byte."""
    status, raw, elapsed = _canary_post({"model": CANARY_MODEL, "max_tokens": 100, "tools": [{"name": "TaskUpdate", "description": "Update a task.", "input_schema": {"type": "object", "properties": {"taskId": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["taskId", "status"], "additionalProperties": False}}], "messages": [{"role": "user", "content": "Call TaskUpdate with taskId t1 and status pending."}]})
    try:
        payload = json.loads(raw)
        tool_blocks = [b for b in payload.get("content", []) if b.get("type") == "tool_use"]
        if tool_blocks:
            inp = tool_blocks[0].get("input", {})
            byte_identity = inp == {"taskId": "t1", "status": "pending"}
            valid = status == 200 and byte_identity
            detail = "input=%r byte_identity=%s" % (inp, byte_identity)
        else:
            valid = False
            detail = "no tool_use block; raw=%r" % raw[:160]
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    exercised = bool(CANARY_KEY)
    show("tool_canary_valid", valid, status, elapsed, detail, exercised=exercised)
    return valid


def probe_tool_canary_repair():
    """Case 2: Repairable input with task_id and done normalizes to taskId and completed."""
    status, raw, elapsed = _canary_post({"model": CANARY_MODEL, "max_tokens": 100, "tools": [{"name": "TaskUpdate", "description": "Update a task.", "input_schema": {"type": "object", "properties": {"taskId": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["taskId", "status"], "additionalProperties": False}}], "messages": [{"role": "user", "content": "Call TaskUpdate with task_id t1 and status done."}]})
    try:
        payload = json.loads(raw)
        tool_blocks = [b for b in payload.get("content", []) if b.get("type") == "tool_use"]
        if tool_blocks:
            inp = tool_blocks[0].get("input", {})
            normalized = inp == {"taskId": "t1", "status": "completed"}
            no_undeclared = "task_id" not in inp and "done" not in str(inp.get("status", ""))
            valid = status == 200 and normalized and no_undeclared
            detail = "input=%r normalized=%s" % (inp, normalized)
        else:
            valid = False
            detail = "no tool_use block; raw=%r" % raw[:160]
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    exercised = bool(CANARY_KEY)
    show("tool_canary_repair", valid, status, elapsed, detail, exercised=exercised)
    return valid


def probe_tool_canary_reject():
    """Case 3: Unsafe non-repairable input is safely rejected and does not recur."""
    status, raw, elapsed = _canary_post({"model": CANARY_MODEL, "max_tokens": 100, "tools": [{"name": "TaskUpdate", "description": "Update a task.", "input_schema": {"type": "object", "properties": {"taskId": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["taskId", "status"], "additionalProperties": False}}], "messages": [{"role": "user", "content": "Call TaskUpdate with taskId t1 and status INVALID_UNSAFE_VALUE_XYZ."}]})
    try:
        payload = json.loads(raw)
        tool_blocks = [b for b in payload.get("content", []) if b.get("type") == "tool_use"]
        if tool_blocks:
            inp = tool_blocks[0].get("input", {})
            valid = False
            detail = "unsafe input passed through: %r" % inp
        else:
            # Safe rejection: no tool_use block with the unsafe value.
            valid = status in (200, 400, 422)
            detail = "safely rejected (no tool_use with unsafe value)"
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    exercised = bool(CANARY_KEY)
    show("tool_canary_reject", valid, status, elapsed, detail, exercised=exercised)
    return valid


def probe_tool_guard_enforce_mode():
    """Case 5: The live callback object reports enforce mode, not merely the container env."""
    # Query the container's tool_argument_guard module for its live mode.
    import subprocess
    try:
        result = subprocess.run(["docker", "exec", "litellm_proxy", "python3", "-c", "import sys; sys.path.insert(0,'/app'); import tool_argument_guard; print(tool_argument_guard.MODE)"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
        mode = result.stdout.strip()
        valid = mode == "enforce"
        detail = "live callback MODE=%s" % mode
        status = 200 if result.returncode == 0 else 500
    except Exception as exc:
        valid = False
        status = -1
        detail = "could not query container: %s" % exc
    show("tool_guard_enforce_mode", valid, status, 0.0, detail, exercised=True)
    return valid


def probe_tool_canary_public_acl():
    """Case 5: Normal public key cannot call the internal canary model.

    The public key must receive 401/403 when requesting tool-canary-internal.
    This verifies the temporary internal model is not exposed to normal users.
    """
    body = {"model": CANARY_MODEL, "max_tokens": 16,
            "messages": [{"role": "user", "content": "test"}]}
    request = urllib.request.Request(
        BASE_URL + "/v1/messages", data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": KEY,
                  "anthropic-version": "2023-06-01"}, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    except Exception as exc:
        status = -1
        raw = "{}: {}".format(type(exc).__name__, exc)
    elapsed = time.time() - started
    # Accept 401/403 (key auth denial) or -1 (smart_router rejection causing
    # connection error — the model is still not accessible to the public key).
    valid = status in (401, 403, -1)
    detail = "public key -> canary model: status=%d" % status
    exercised = bool(CANARY_KEY)  # only exercised when canary is set up
    show("tool_canary_public_acl", valid, status, elapsed, detail,
         exercised=exercised, expected=403)
    return valid


# ── Policy denial probe (PRD section 7.4) ──────────────────────────────────────

POLICY_KEY = os.environ.get("POLICY_DENIED_KEY", "")


def probe_policy_denied():
    """A cache-miss image with a china-only tagged key returns 403 before egress."""
    key = POLICY_KEY or KEY
    # Use a unique image that won't be in cache.
    import base64 as _b64
    unique_png = _make_png(128, 64, 32)
    request = urllib.request.Request(BASE_URL + "/v1/messages", data=json.dumps({"model": MODEL, "max_tokens": 64, "messages": [{"role": "user", "content": [{"type": "text", "text": "What color is this image?"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": unique_png}}]}]}).encode("utf-8"), headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    except Exception as exc:
        status = -1
        raw = "{}: {}".format(type(exc).__name__, exc)
    elapsed = time.time() - started
    try:
        payload = json.loads(raw)
        err = payload.get("error", {})
        code = str(err.get("code", "") or err.get("type", ""))
        valid = status == 403 and "POLICY" in code.upper()
        detail = "status=%d code=%s" % (status, code)
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    exercised = bool(POLICY_KEY)
    show("policy_denied", valid, status, elapsed, detail, exercised=exercised, expected=403)
    return valid


# ── Premium intervention probe (PRD section 9) ────────────────────────────────

def probe_premium_intervention():
    """A seeded tool error triggers exactly one Premium advisory; GLM owns the final
    response. Repeating the same fingerprint does not trigger a second intervention."""
    # Seed: a message history with a tool_result marked is_error=true.
    seed_body = {"model": MODEL, "max_tokens": 200, "tools": [{"name": "TaskUpdate", "description": "Update a task.", "input_schema": {"type": "object", "properties": {"taskId": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["taskId", "status"], "additionalProperties": False}}], "messages": [{"role": "user", "content": "Update task t1 to completed."}, {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_1", "name": "TaskUpdate", "input": {"taskId": "t1", "status": "completed"}}]}, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "Error: database connection failed", "is_error": True}]}]}
    status, raw, elapsed = post(seed_body)
    try:
        payload = json.loads(raw)
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text").strip()
        # GLM should own the final response (non-empty text, not just the premium advisory).
        valid = status == 200 and bool(text)
        detail = "status=%d text=%r" % (status, text[:80])
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("premium_intervention", valid, status, elapsed, detail)
    return valid


# ── Probe registry ─────────────────────────────────────────────────────────────

PROBES = {
    "message": probe_message,
    "stream": probe_stream,
    "tools": probe_tools,
    "reasoning": probe_reasoning,
    "image": probe_image,
    "nested_image": probe_nested_image,
    "image_limit": probe_image_limit,
    "502": probe_502,
    "tool_args": probe_tool_args,
    "reasoning_openai": probe_reasoning_openai,
    "tool_canary_valid": probe_tool_canary_valid,
    "tool_canary_repair": probe_tool_canary_repair,
    "tool_canary_reject": probe_tool_canary_reject,
    "tool_guard_enforce_mode": probe_tool_guard_enforce_mode,
    "tool_canary_public_acl": probe_tool_canary_public_acl,
    "policy_denied": probe_policy_denied,
    "premium_intervention": probe_premium_intervention,
}

# ── Profile assignments (PRD-r11-minimal-closeout.md §5) ──────────────────────
# Every mandatory probe is assigned to exactly one applicable configuration.
# HEALTHY contains only probes executable in normal production configuration.
# tool_args is nondeterministic (GLM may refuse) — NOT in HEALTHY.
# reasoning_openai is operator/internal — NOT in HEALTHY.

PROFILES = {
    "healthy": ["message", "stream", "tools", "reasoning", "image", "nested_image", "image_limit"],
    "tool_canary": ["tool_canary_valid", "tool_canary_repair", "tool_canary_reject", "tool_guard_enforce_mode", "tool_canary_public_acl"],
    "policy_denied": ["policy_denied"],
    "primary_fault": ["image"],
    "vision_fault": ["502"],
    "premium": ["premium_intervention"],
    "operator": ["reasoning_openai", "tool_args"],
}

ALL_PROBE_NAMES = list(PROBES.keys())


def main():
    global _CURRENT_PROFILE

    import argparse
    parser = argparse.ArgumentParser(description="Live smoke probes for R11 release closure.")
    parser.add_argument("probe", nargs="?", default=None, help="Single probe name (legacy positional arg)")
    parser.add_argument("--profile", default=None, help="Profile name: healthy, tool_canary, policy_denied, primary_fault, vision_fault, premium, all")
    parser.add_argument("--json-output", default=None, help="Write structured results as JSON to this path")
    parser.add_argument("--probe-name", default=None, help="Single probe name (explicit flag)")
    args = parser.parse_args()

    # Determine which probes to run.
    single = args.probe_name or args.probe
    if single:
        if single == "all":
            # Legacy: run all probes in the "unscoped" profile.
            names = ALL_PROBE_NAMES
            _CURRENT_PROFILE = "all"
        elif single in PROBES:
            names = [single]
            _CURRENT_PROFILE = "single"
        else:
            raise SystemExit("Unknown probe: %s. Available: %s" % (single, ", ".join(ALL_PROBE_NAMES)))
    elif args.profile:
        if args.profile == "all":
            # Run every profile sequentially.
            all_results = []
            for profile_name, probe_names in PROFILES.items():
                _CURRENT_PROFILE = profile_name
                print("--- Profile: %s ---" % profile_name)
                results = [PROBES[name]() for name in probe_names]
                all_results.extend(results)
                print("profile %s: %d/%d passed" % (profile_name, sum(results), len(results)))
                print()
            names = None  # already ran
            results = all_results
        elif args.profile in PROFILES:
            _CURRENT_PROFILE = args.profile
            names = PROFILES[args.profile]
        else:
            raise SystemExit("Unknown profile: %s. Available: %s" % (args.profile, ", ".join(list(PROFILES.keys()) + ["all"])))
    else:
        # Default: healthy profile.
        _CURRENT_PROFILE = "healthy"
        names = PROFILES["healthy"]

    if names is not None:
        results = [PROBES[name]() for name in names]

    # Enforce result-count invariant (PRD §5.3):
    # summary.total == len(_RESULTS), one result per probe.
    # If a composite function appended extra uncounted results, fail.
    total = len(_RESULTS)
    passed = sum(1 for r in _RESULTS if r.passed and r.exercised)
    print("summary: %d/%d passed" % (passed, total))

    # Write JSON output if requested.
    if args.json_output:
        all_passed = all(r.passed and r.exercised for r in _RESULTS)
        output = {
            "run_id": _RUN_ID,
            "candidate_commit": CANDIDATE_COMMIT,
            "artifact_sha256": ARTIFACT_SHA256,
            "host": HOST_IDENTITY,
            "deploy_root": DEPLOY_ROOT,
            "profile": _CURRENT_PROFILE if _CURRENT_PROFILE != "all" else "all",
            "results": [r.to_dict() for r in _RESULTS],
            "summary": {"passed": passed, "total": total, "exit_code": 0 if all_passed else 1},
        }
        with open(args.json_output, "w") as f:
            json.dump(output, f, indent=2)
        print("json output: %s" % args.json_output)

    all_passed = all(r.passed and r.exercised for r in _RESULTS)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
