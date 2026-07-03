#!/usr/bin/env python3
"""Live smoke test: Claude Code -> :4010 adapter -> LiteLLM -> GLM-5.2 / vision.
Tests: short text, large payload, image routing, search intent.
Reads LITELLM_ANTHROPIC_KEY from /root/LiteLLM/.env.
Usage: python3 tests/live_smoke.py [all|text|big|image|search]
"""
import json, os, re, sys, time, urllib.request, urllib.error, base64, zlib, struct

ADAPTER = os.environ.get("ADAPTER_URL", "http://127.0.0.1:4000/v1/messages")
LITELLM = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000/v1/chat/completions")

def load_key():
    for line in open("/root/LiteLLM/.env", encoding="utf-8", errors="ignore"):
        m = re.match(r'^LITELLM_ANTHROPIC_KEY=(.*)$', line.strip())
        if m:
            return m.group(1).strip().strip('"')
    sys.exit("no LITELLM_ANTHROPIC_KEY")
KEY = load_key()

def _red_png(w=64, h=64, rgb=(220, 20, 20)):
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
PNG_B64 = base64.b64encode(_red_png()).decode()

def post(url, body, anthropic=True, timeout=180):
    data = json.dumps(body).encode()
    hdr = {"content-type": "application/json"}
    if anthropic:
        hdr["x-api-key"] = KEY; hdr["anthropic-version"] = "2023-06-01"
    else:
        hdr["authorization"] = f"Bearer {KEY}"
    req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), time.time() - t0
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}", time.time() - t0

def show(name, status, body, dt, chars=None):
    print(f"\n===== {name} =====")
    if chars is not None:
        print(f"payload chars={chars:,}  (~{chars//4:,} est tokens)")
    print(f"HTTP {status}  {dt:.1f}s")
    try:
        j = json.loads(body)
        if isinstance(j, dict) and j.get("type") == "message":
            txt = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
            tools = [b.get("name") for b in j.get("content", []) if b.get("type") == "tool_use"]
            print("usage:", j.get("usage"))
            if tools: print("tool_use:", tools)
            print("reply:", (txt[:220] + ("..." if len(txt) > 220 else "")))
        else:
            print("body:", body[:600])
    except Exception:
        print("body:", body[:600])
    return status

def t_text():
    s, b, dt = post(ADAPTER, {"model": "claude-opus-4-6", "max_tokens": 32,
        "messages": [{"role": "user", "content": "reply with exactly: TEXT-OK"}]})
    return show("1. short text (baseline)", s, b, dt)

def t_big(tokens=185000):
    unit = "The quick brown fox jumps over the lazy dog. "
    filler = unit * ((tokens * 4) // len(unit) + 1)
    content = filler + "\n\nAfter reading the above, reply with exactly: BIG-OK"
    s, b, dt = post(ADAPTER, {"model": "claude-opus-4-6", "max_tokens": 32,
        "messages": [{"role": "user", "content": content}]}, timeout=300)
    return show(f"2. large context ~{tokens//1000}K tokens", s, b, dt, chars=len(content))

def t_image_default():
    s, b, dt = post(ADAPTER, {"model": "claude-opus-4-6", "max_tokens": 64,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "What color is this image? Answer with one word."},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG_B64}}]}]})
    return show("3. image via default alias (plugin should route -> vision)", s, b, dt)

def t_image_vision():
    url = f"data:image/png;base64,{PNG_B64}"
    s, b, dt = post(LITELLM, {"model": "vision-openrouter", "max_tokens": 64,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "What color is this image? Answer with one word."},
            {"type": "image_url", "image_url": {"url": url}}]}]}, anthropic=False)
    print("\n===== 4. image direct to vision-openrouter (OpenAI fmt) =====")
    print(f"HTTP {s}  {dt:.1f}s"); print("body:", b[:400])
    return s

def t_search():
    s, b, dt = post(ADAPTER, {"model": "claude-opus-4-6-backend", "max_tokens": 256,
        "messages": [{"role": "user", "content": "搜索今天的最新新闻，给我三条 (search latest news today)"}]})
    return show("5. search-intent (backend alias)", s, b, dt)

def t_tooluse():
    """Backend must parse tool calls into structured tool_use blocks. If the
    model instead prints raw <tool_call> markup as text, Claude Code shows the
    whole thing as plain text and never executes tools (issue #111)."""
    s, b, dt = post(ADAPTER, {"model": "claude-opus-4-6", "max_tokens": 300,
        "tools": [{"name": "echo_check",
                   "description": "Echo a short string back. Used to verify tool calling works.",
                   "input_schema": {"type": "object",
                                    "properties": {"text": {"type": "string"}},
                                    "required": ["text"]}}],
        "messages": [{"role": "user",
                      "content": "Call the echo_check tool with text set to ok. Do not answer in plain text."}]})
    show("6. tool-call capability", s, b, dt)
    if '"tool_use"' in b:
        print("verdict: PASS - structured tool_use block")
    elif re.search(r'<tool_call|<arg_key>|</[A-Za-z_]+_tool>', b):
        print("verdict: FAIL - raw tool markup in text; backend endpoint is "
              "not parsing tool calls (enable function calling on the "
              "endpoint / vLLM --enable-auto-tool-choice --tool-call-parser)")
        return -1
    else:
        print("verdict: WARN - no tool_use block (inconclusive)")
    return s

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    r = {}
    if which in ("all", "text"):   r["text"] = t_text()
    if which in ("all", "big"):    r["big"] = t_big(int(os.environ.get("BIG_TOKENS", "185000")))
    if which in ("all", "image"):  r["image_default"] = t_image_default()
    if which in ("all", "image"):  r["image_vision"] = t_image_vision()
    if which in ("all", "search"): r["search"] = t_search()
    if which in ("all", "tools"):  r["tooluse"] = t_tooluse()
    print("\n===== SUMMARY =====")
    for k, v in r.items():
        print(f"{k:16} HTTP {v}")
