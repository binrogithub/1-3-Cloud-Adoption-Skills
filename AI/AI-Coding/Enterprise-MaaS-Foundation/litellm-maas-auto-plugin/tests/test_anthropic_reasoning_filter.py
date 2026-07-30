import asyncio
import importlib.util
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "anthropic_reasoning_filter" / "callback.py"

custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm", types.ModuleType("litellm"))
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)
spec = importlib.util.spec_from_file_location("anthropic_reasoning_filter", CALLBACK)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sse(event):
    return ("event: %s\ndata: %s\n\n" % (event["type"], json.dumps(event))).encode()


async def feed(items):
    for item in items:
        yield item


async def filtered(items):
    output = []
    async for item in module.proxy_handler_instance.async_post_call_streaming_iterator_hook(
        None, feed(items), {}
    ):
        output.append(item)
    return output


def events(items):
    return [module._parse_anthropic_sse(item) for item in items]


def test_stream_hides_reasoning_and_compacts_indexes():
    source = [
        sse({"type": "message_start", "message": {}}),
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "secret"}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "opaque"}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
        sse({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "answer"}}),
        sse({"type": "content_block_stop", "index": 1}),
        sse({"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "t1", "name": "echo", "input": {}}}),
        sse({"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{}"}}),
        sse({"type": "content_block_stop", "index": 2}),
        sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}}),
        sse({"type": "message_stop"}),
    ]
    result = events(asyncio.run(filtered(source)))
    serialized = json.dumps(result)
    assert "thinking" not in serialized
    assert "signature_delta" not in serialized
    indexed = [(e["type"], e["index"]) for e in result if "index" in e]
    assert indexed == [
        ("content_block_start", 0), ("content_block_delta", 0), ("content_block_stop", 0),
        ("content_block_start", 1), ("content_block_delta", 1), ("content_block_stop", 1),
    ]
    assert result[-2]["delta"]["stop_reason"] == "tool_use"
    assert result[-1]["type"] == "message_stop"


def test_nonstream_and_openai_passthrough():
    response = {"content": [
        {"type": "thinking", "thinking": "secret"},
        {"type": "text", "text": "answer"},
        {"type": "tool_use", "id": "t1", "name": "echo", "input": {}},
    ]}
    module.filter_nonstream_response(response)
    assert [block["type"] for block in response["content"]] == ["text", "tool_use"]
    openai = b'data: {"choices":[{"delta":{"reasoning_content":"secret"}}]}\n\n'
    assert asyncio.run(filtered([openai])) == [openai]


if __name__ == "__main__":
    test_stream_hides_reasoning_and_compacts_indexes()
    test_nonstream_and_openai_passthrough()
    print("anthropic_reasoning_filter tests passed")
