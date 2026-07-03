import asyncio, sys, json
sys.path.insert(0, "/root/litellm-maas-plugin/litellm_plugins/anthropic_stream_guard")
from callback import proxy_handler_instance, _sse

def sse(e): return _sse(e)

async def feed(items):
    for e in items: yield e

async def run(items):
    out=[]
    async for c in proxy_handler_instance.async_post_call_streaming_iterator_hook(
        user_api_key_dict=None, response=feed(items), request_data={}):
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

print("ALL 9 TESTS PASS")
