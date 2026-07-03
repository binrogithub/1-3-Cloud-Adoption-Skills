import asyncio, sys, json
import logging, types

if "litellm" not in sys.modules:
    litellm = types.ModuleType("litellm")
    logging_module = types.ModuleType("litellm._logging")
    integrations = types.ModuleType("litellm.integrations")
    custom_logger = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:
        pass

    logging_module.verbose_proxy_logger = logging.getLogger("anthropic_stream_guard_test")
    custom_logger.CustomLogger = CustomLogger
    sys.modules.setdefault("litellm", litellm)
    sys.modules.setdefault("litellm._logging", logging_module)
    sys.modules.setdefault("litellm.integrations", integrations)
    sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

from pathlib import Path
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "litellm_plugins" / "anthropic_stream_guard"),
)
from callback import proxy_handler_instance, _normalize_thinking_signatures, _sse

def sse(e): return _sse(e)

async def feed(items):
    for e in items: yield e

async def run(items, request_data=None):
    out=[]
    async for c in proxy_handler_instance.async_post_call_streaming_iterator_hook(
        user_api_key_dict=None, response=feed(items), request_data=request_data or {}):
        out.append(c)
    return out

def parse_all(chunks):
    evs=[]
    for c in chunks:
        assert isinstance(c,(bytes,bytearray)), f"non-bytes leaked: {type(c)}"
        for ln in c.decode().split("\n"):
            if ln.startswith("data: "): evs.append(json.loads(ln[6:]))
    return evs

def validate(evs):
    cur={}; order=[]
    legal={"thinking":{"thinking_delta","signature_delta"},"text":{"text_delta"},"tool_use":{"input_json_delta"}}
    for e in evs:
        t=e["type"]
        if t=="content_block_start":
            cur[e["index"]]=e["content_block"]["type"]; order.append((e["index"],e["content_block"]["type"]))
        elif t=="content_block_delta":
            bt=cur.get(e["index"]); dt=e["delta"]["type"]
            assert bt is not None, f"delta before start {e}"
            assert dt in legal[bt], f"violation: {dt} in {bt}"
        elif t=="content_block_stop":
            cur[e["index"]]=None
    return order

# T1 real malformed single-block stream
MAL=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m1"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"hm"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"mm"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"sig"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"4"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":9}},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(MAL)))
assert validate(evs)==[(0,"thinking"),(1,"text")]
print("T1 malformed re-sequencing: PASS")

# T2 correct stream byte-identity
OK=[sse(e) for e in [
 {"type":"message_start","message":{}},
 {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"x"}},
 {"type":"content_block_stop","index":0},
 {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"hi"}},
 {"type":"content_block_stop","index":1},
 {"type":"message_stop"},
]]
assert asyncio.run(run(OK))==OK
print("T2 correct-stream byte-identity: PASS")

# T3 text-only identity
TXT=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hello"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
assert asyncio.run(run(TXT))==TXT
print("T3 text-only identity: PASS")

# T4 tool_use identity
TOOL=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"t","name":"Bash","input":{}}},
 {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{}"}},
 {"type":"content_block_stop","index":0},
]]
assert asyncio.run(run(TOOL))==TOOL
print("T4 tool_use identity: PASS")

# T5 malformed first block + native next block (index remap)
MIX=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"t"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"a"}},
 {"type":"content_block_stop","index":0},
 {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"t","name":"Bash","input":{}}},
 {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{}"}},
 {"type":"content_block_stop","index":1},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(MIX)))
assert validate(evs)==[(0,"thinking"),(1,"text"),(2,"tool_use")]
print("T5 index remap: PASS")

# T6 ADVERSARIAL: text delta whose CONTENT fakes a thinking_delta marker
ADV=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"benign"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"try this: \"thinking_delta\" marker injection"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"and \"input_json_delta\" too"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
out=asyncio.run(run(ADV))
assert out==ADV, "adversarial markers must not trigger any rewrite"
print("T6 adversarial marker injection: PASS (byte-identical)")

# T6b same but inside a thinking block faking text_delta
ADV2=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"see \"text_delta\" here"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
assert asyncio.run(run(ADV2))==ADV2
print("T6b adversarial reverse direction: PASS")

# T7 oversize chunk: must pass through unparsed, stream continues correctly
big_text = "x" * 300000
big_chunk = sse({"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":big_text}})
assert len(big_chunk) > 262144
OVS=[
 sse({"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}),
 sse({"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"a"}}),
 big_chunk,
 sse({"type":"content_block_stop","index":0}),
 sse({"type":"message_stop"}),
]
out=asyncio.run(run(OVS))
assert big_chunk in out and len(out)==len(OVS)
print("T7 oversize passthrough: PASS")

# T8 CONCURRENT ISOLATION: two interleaved streams share the singleton handler
async def concurrent():
    r1, r2 = await asyncio.gather(run(MAL), run(OK))
    return r1, r2
r1, r2 = asyncio.run(concurrent())
assert validate(parse_all(r1))==[(0,"thinking"),(1,"text")]
assert r2==OK
print("T8 concurrent stream isolation: PASS")

# T9 malformed first tool block: adapter declared text but emitted input_json_delta
MAL_TOOL_FIRST=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","id":"t1","name":"Bash","input":{}}},
 {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\"command\":\"pwd\"}"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":4}},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(MAL_TOOL_FIRST, {"tools":[{"name":"Bash"}]})))
assert validate(evs)==[(0,"tool_use")]
assert evs[0]["content_block"]["id"]=="t1"
assert evs[0]["content_block"]["name"]=="Bash"
print("T9 malformed first tool block retyping: PASS")

# T10 malformed text->tool transition with no tool identity: keep it as text
MAL_TEXT_TOOL=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"running"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{}"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(MAL_TEXT_TOOL, {"tools":[{"name":"Bash"}]})))
assert validate(evs)==[(0,"text")]
assert [e["delta"]["type"] for e in evs if e["type"]=="content_block_delta"] == [
    "text_delta",
    "text_delta",
]
print("T10 text-to-fake-tool transition downgraded: PASS")

# T11 no declared tools: adapter/tool-call artifact must stay text, not create fake tool
NO_TOOLS_FAKE_TOOL=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"if balance"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":" < amount:"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" raise InsufficientFundsError()"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(NO_TOOLS_FAKE_TOOL)))
assert validate(evs)==[(0,"text")]
assert [e["delta"]["type"] for e in evs if e["type"]=="content_block_delta"] == [
    "text_delta",
    "text_delta",
    "text_delta",
]
assert "if balance < amount:" in "".join(
    e["delta"].get("text","") for e in evs if e["type"]=="content_block_delta"
)
print("T11 no-tool input_json artifact downgraded to text: PASS")

# T12 non-stream/logging response normalization: thinking signature must be a string
resp={"content":[{"type":"thinking","thinking":"x","signature":None},{"type":"text","text":"OK"}]}
_normalize_thinking_signatures(resp)
assert resp["content"][0]["signature"] == ""
print("T12 thinking signature normalization: PASS")

# T13 tools request with text start but no id/name must not create toolu_asg/tool
TOOLS_BUT_NO_ID=[sse(e) for e in [
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":" < hi:"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_stop"},
]]
evs=parse_all(asyncio.run(run(TOOLS_BUT_NO_ID, {"tools":[{"name":"Bash"}]})))
assert validate(evs)==[(0,"text")]
assert all(
    e.get("content_block", {}).get("name") != "tool"
    for e in evs
    if e["type"] == "content_block_start"
)
assert " < hi:" in "".join(
    e["delta"].get("text","") for e in evs if e["type"]=="content_block_delta"
)
print("T13 tools request without tool identity downgraded: PASS")

# T14 upstream ends right after a complete tool_use block (the GLM/MaaS
# "Connection closed mid-response" bug): guard must synthesize termination
TRUNC_TOOL=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m1"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"我先看一下"}},
 {"type":"content_block_stop","index":0},
 {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"t1","name":"Bash","input":{}}},
 {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\"command\":\"ls\"}"}},
 {"type":"content_block_stop","index":1},
 # stream dies here: no message_delta, no message_stop
]]
evs=parse_all(asyncio.run(run(TRUNC_TOOL, {"tools":[{"name":"Bash"}]})))
types=[e["type"] for e in evs]
assert types[-1]=="message_stop", f"must end with message_stop, got {types[-3:]}"
assert types[-2]=="message_delta"
md=[e for e in evs if e["type"]=="message_delta"][-1]
assert md["delta"]["stop_reason"]=="tool_use"
print("T14 synthesized termination after tool_use: PASS")

# T15 upstream dies mid-text with the block still open
TRUNC_TEXT=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m2"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"partial ans"}},
 # stream dies mid-block
]]
evs=parse_all(asyncio.run(run(TRUNC_TEXT)))
types=[e["type"] for e in evs]
assert types[-3:]==["content_block_stop","message_delta","message_stop"], types[-4:]
md=[e for e in evs if e["type"]=="message_delta"][-1]
assert md["delta"]["stop_reason"]=="end_turn"
print("T15 synthesized termination mid-text: PASS")

# T16 healthy complete streams gain NOTHING (T2/T3 byte-identity still hold)
assert asyncio.run(run(OK))==OK
assert asyncio.run(run(TXT))==TXT
print("T16 no synthesis on complete streams: PASS")

# T17 upstream iterator raises mid-stream: finalize instead of propagating
async def dying_feed(items, exc):
    for e in items: yield e
    raise exc
async def run_dying(items, exc):
    out=[]
    async for c in proxy_handler_instance.async_post_call_streaming_iterator_hook(
        user_api_key_dict=None, response=dying_feed(items, exc), request_data={}):
        out.append(c)
    return out
DIES=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m3"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hi"}},
]]
evs=parse_all(asyncio.run(run_dying(DIES, RuntimeError("upstream died"))))
types=[e["type"] for e in evs]
assert types[-1]=="message_stop", types
print("T17 upstream exception finalized: PASS")

# T18 fake message_stop marker inside passthrough chunk suppresses synthesis
# (fail-open direction: rescue disabled, nothing injected)
FAKE=[
 sse({"type":"message_start","message":{"id":"m4"}}),
 b'data: {"some":"passthrough with message_stop marker"}\ndata: {"x":1}\n\n',
]
out=asyncio.run(run(FAKE))
tail=b"".join(c for c in out if isinstance(c,(bytes,bytearray)))
assert b'"type": "message_stop"' not in tail
print("T18 fake terminal marker suppresses synthesis: PASS")

# T19 raw <tool_call markup in text with tools declared: metric+log only,
# stream must pass through byte-identical (no rewrite of improvised markup)
import callback as _cbmod
class _Rec:
    def __init__(self): self.n = 0
    def inc(self, *_a, **_k): self.n += 1
_rec = _Rec(); _old_markup = _cbmod.TOOL_MARKUP; _cbmod.TOOL_MARKUP = _rec
MARKUP=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m5"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"开始创建。<tool_call>Bash_tool>"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"<command>mkdir -p /x</command></Bash_tool>"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":9}},
 {"type":"message_stop"},
]]
out=asyncio.run(run(MARKUP, {"tools":[{"name":"Bash"}]}))
assert out==MARKUP, "markup detection must never rewrite the stream"
assert _rec.n==1, f"TOOL_MARKUP should increment once per stream, got {_rec.n}"
_cbmod.TOOL_MARKUP=_old_markup
print("T19 unparsed tool markup detected without rewrite: PASS")

# T20 raw <tool_call marker split across byte chunks is still diagnosed
_rec = _Rec(); _old_markup = _cbmod.TOOL_MARKUP; _cbmod.TOOL_MARKUP = _rec
SPLIT_MARKUP=[sse(e) for e in [
 {"type":"message_start","message":{"id":"m6"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"<tool_"}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"call>Bash_tool>"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":9}},
 {"type":"message_stop"},
]]
out=asyncio.run(run(SPLIT_MARKUP, {"tools":[{"name":"Bash"}]}))
assert out==SPLIT_MARKUP, "split markup detection must never rewrite bytes"
assert _rec.n==1, f"TOOL_MARKUP should increment once per stream, got {_rec.n}"
_cbmod.TOOL_MARKUP=_old_markup
print("T20 split unparsed tool markup detected without rewrite: PASS")

# T21 dict-mode text deltas are diagnosed too
_rec = _Rec(); _old_markup = _cbmod.TOOL_MARKUP; _cbmod.TOOL_MARKUP = _rec
DICT_MARKUP=[
 {"type":"message_start","message":{"id":"m7"}},
 {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
 {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"<tool_call>Bash_tool>"}},
 {"type":"content_block_stop","index":0},
 {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":9}},
 {"type":"message_stop"},
]
out=asyncio.run(run(DICT_MARKUP, {"tools":[{"name":"Bash"}]}))
assert out==DICT_MARKUP, "dict markup detection must never rewrite events"
assert _rec.n==1, f"TOOL_MARKUP should increment once per stream, got {_rec.n}"
_cbmod.TOOL_MARKUP=_old_markup
print("T21 dict-mode unparsed tool markup detected without rewrite: PASS")

print("ALL 21 TESTS PASS")
