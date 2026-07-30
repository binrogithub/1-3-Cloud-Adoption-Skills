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
from callback import (
    apply_stop_sequences,
    normalize_image_url_blocks,
    proxy_handler_instance,
    _normalize_thinking_signatures,
    _sse,
)

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

# T13b OpenAI-style image_url blocks are normalized to Anthropic image/source.
img_req = {
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "color?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,QUJD",
                    },
                },
            ],
        }
    ]
}
assert normalize_image_url_blocks(img_req) == 1
assert img_req["messages"][0]["content"][1] == {
    "type": "image",
    "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"},
}
print("T13b image_url normalized to Anthropic image source: PASS")

# T13c non-stream stop_sequences are enforced if the backend ignores them.
stop_resp = {
    "content": [{"type": "text", "text": "BEGIN STOPXYZ AFTER"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
}
assert apply_stop_sequences({"stop_sequences": ["STOPXYZ"]}, stop_resp) is True
assert stop_resp["content"][0]["text"] == "BEGIN "
assert stop_resp["stop_reason"] == "stop_sequence"
assert stop_resp["stop_sequence"] == "STOPXYZ"
print("T13c stop_sequences enforced for non-stream response: PASS")

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

# T22 queued mid-task user message (#115): re-surfaced as top-level text
from callback import amplify_user_interjections, AMPLIFIED_HEADER
REMINDER = ("<system-reminder>\nThe user sent the following message: "
            "still compacting? you are not compacting just now?\n"
            "IMPORTANT: After completing your current task, you MUST address "
            "the user's message. Do not ignore it.\n</system-reminder>")
req = {"messages": [
    {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]},
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1",
         "content": [{"type": "text", "text": "ok\n" + REMINDER}]},
    ]},
]}
n = amplify_user_interjections(req)
assert n == 1, n
last_block = req["messages"][-1]["content"][-1]
assert last_block["type"] == "text"
assert last_block["text"].startswith(AMPLIFIED_HEADER)
assert "still compacting?" in last_block["text"]
# idempotent on retry
assert amplify_user_interjections(req) == 0
print("T22 queued user message re-surfaced: PASS")

# T23 ordinary system-reminders must NOT be amplified
req2 = {"messages": [
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1",
         "content": "<system-reminder>The TODO list was updated.</system-reminder>"},
        {"type": "text", "text": "<system-reminder>Contents of CLAUDE.md: ...</system-reminder>"},
    ]},
]}
before2 = json.dumps(req2)
assert amplify_user_interjections(req2) == 0
assert json.dumps(req2) == before2, "ordinary reminders must not mutate the request"
print("T23 ordinary system-reminders untouched: PASS")

# T24 only the NEWEST user message is scanned (history not resurrected)
req3 = {"messages": [
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t0", "content": REMINDER}]},
    {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
    {"role": "user", "content": [{"type": "text", "text": "next task"}]},
]}
before3 = json.dumps(req3)
assert amplify_user_interjections(req3) == 0
assert json.dumps(req3) == before3
print("T24 historical reminders not resurrected: PASS")

# T25 Anthropic server tools stripped; client tools untouched
from callback import strip_server_tools
req_t = {"tools": [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8},
    {"name": "Bash", "description": "run", "input_schema": {"type": "object"}},
], "tool_choice": {"type": "auto"}}
assert strip_server_tools(req_t) == 1
assert [t["name"] for t in req_t["tools"]] == ["Bash"]
assert "tool_choice" in req_t  # still has usable tools
print("T25 server tool stripped, client tool kept: PASS")

# T26 lone server tool: tools and tool_choice dropped entirely (CC WebSearch
# sub-request shape that intermittently 400s on GLM/MaaS 'tools' validation)
req_t2 = {"tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
          "tool_choice": {"type": "auto"}}
assert strip_server_tools(req_t2) == 1
assert "tools" not in req_t2 and "tool_choice" not in req_t2
print("T26 lone server tool drops tools+tool_choice: PASS")

# T27 requests without server tools are untouched byte-for-byte
req_t3 = {"tools": [{"name": "Bash", "input_schema": {"type": "object"}}]}
before_t3 = json.dumps(req_t3)
assert strip_server_tools(req_t3) == 0
assert json.dumps(req_t3) == before_t3
assert strip_server_tools({}) == 0
print("T27 client-only tools untouched: PASS")

# T28 Huawei raw pretty JSON SSE framing is repaired into valid Anthropic SSE
RAW_PRETTY = (
    b"event: message_start\n"
    b"data:\n"
    b"{\n"
    b'  "type": "message_start",\n'
    b'  "message": {\n'
    b'    "id": "m_raw"\n'
    b"  }\n"
    b"}\n\n"
)
raw_event = {"type": "message_start", "message": {"id": "m_raw"}}
raw_stop = {"type": "message_stop"}
assert asyncio.run(run([RAW_PRETTY, sse(raw_stop)])) == [sse(raw_event), sse(raw_stop)]
print("T28 Huawei raw pretty JSON SSE repaired: PASS")

# T29 trailing OpenAI-style data: [DONE] after Anthropic message_stop is dropped
TRAILING_DONE = [
    sse({"type": "message_start", "message": {"id": "m_done"}}),
    sse({"type": "message_stop"}),
    b"data: [DONE]\n\n",
]
assert asyncio.run(run(TRAILING_DONE)) == TRAILING_DONE[:2]
print("T29 trailing OpenAI DONE after message_stop dropped: PASS")

# T30 Huawei pretty JSON repair refuses multi-event chunks rather than
# dropping trailing content.
RAW_PRETTY_MULTI_EVENT = RAW_PRETTY + sse({"type": "message_stop"})
assert asyncio.run(run([RAW_PRETTY_MULTI_EVENT])) == [RAW_PRETTY_MULTI_EVENT]
print("T30 Huawei raw pretty JSON multi-event chunk is fail-open: PASS")

# T31 forced Anthropic tool_choice translation is opt-in for direct adapters
async def pre_call(data):
    return await proxy_handler_instance.async_pre_call_hook(
        user_api_key_dict=None, cache=None, data=data, call_type="acompletion"
    )

forced_req = {"tool_choice": {"type": "tool", "name": "get_weather"}}
asyncio.run(pre_call(forced_req))
assert forced_req["tool_choice"] == {"type": "tool", "name": "get_weather"}

old_translate = _cbmod.TRANSLATE_TOOL_CHOICE
_cbmod.TRANSLATE_TOOL_CHOICE = True
forced_req = {"tool_choice": {"type": "tool", "name": "get_weather"}}
asyncio.run(pre_call(forced_req))
assert forced_req["tool_choice"] == {
    "type": "function",
    "function": {"name": "get_weather"},
}
for choice in ("auto", "any", "none"):
    req_choice = {"tool_choice": {"type": choice}}
    before_choice = json.dumps(req_choice)
    asyncio.run(pre_call(req_choice))
    assert json.dumps(req_choice) == before_choice, choice
_cbmod.TRANSLATE_TOOL_CHOICE = old_translate
print("T31 forced Anthropic tool_choice translated only when enabled: PASS")

# T32 compatibility metrics exist and can be monkey-patched to no-op counters
for metric_name in (
    "RAW_SSE_REPAIRED",
    "OPENAI_DONE_DROPPED",
    "TOOL_CHOICE_TRANSLATED",
):
    metric = getattr(_cbmod, metric_name)
    assert hasattr(metric, "inc")
    old_metric = metric
    noop_metric = _Rec()
    setattr(_cbmod, metric_name, noop_metric)
    getattr(_cbmod, metric_name).inc()
    assert noop_metric.n == 1
    setattr(_cbmod, metric_name, old_metric)
print("T32 compatibility metrics degrade through inc-compatible counters: PASS")

print("ALL TESTS PASS")
