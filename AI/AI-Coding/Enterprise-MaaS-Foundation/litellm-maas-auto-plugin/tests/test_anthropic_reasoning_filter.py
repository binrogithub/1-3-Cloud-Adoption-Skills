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


async def filtered_model(items, model):
    """Streaming hook with an explicit requested model in request_data."""
    output = []
    async for item in module.proxy_handler_instance.async_post_call_streaming_iterator_hook(
        None, feed(items), {"model": model}
    ):
        output.append(item)
    return output


def events(items):
    return [module._parse_anthropic_sse(item) for item in items]


def thinking_stream():
    """A stream with a thinking block followed by a text block."""
    return [
        sse({"type": "message_start", "message": {}}),
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "secret"}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "opaque"}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
        sse({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "answer"}}),
        sse({"type": "content_block_stop", "index": 1}),
        sse({"type": "message_delta", "delta": {"stop_reason": "end_turn"}}),
        sse({"type": "message_stop"}),
    ]


def thinking_response():
    return {"content": [
        {"type": "thinking", "thinking": "secret", "signature": "opaque"},
        {"type": "text", "text": "answer"},
    ]}


def apply_nonstream(model, response):
    """Run the non-stream success hook with the given requested model."""
    asyncio.run(
        module.proxy_handler_instance.async_post_call_success_hook(
            {"model": model}, None, response
        )
    )
    return response


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
    # GLM model: thinking is a provider artifact and is stripped.
    result = events(asyncio.run(filtered_model(source, "claude-glm-5.2")))
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


# ---- family-scoped stripping (PRD-multi-family-routing Item 4) -------------

def test_model_profile_family():
    # Registry resolves model IDs to family profiles (PRD-glm-consolidation §10).
    # Deleted text routes (claude-sonnet-5/claude-haiku-4-5) resolve to the
    # inert fallback (family "other").
    assert module._model_profile("claude-glm-5.2")["family"] == "glm"
    assert module._model_profile("glm-5.2")["family"] == "glm"
    assert module._model_profile("claude-glm-5.2")["family"] == "glm"
    assert module._model_profile("claude-glm-5.2")["family"] == "glm"
    assert module._model_profile("claude-sonnet-5")["family"] == "other"
    assert module._model_profile("claude-haiku-4-5")["family"] == "other"
    assert module._model_profile("gpt-4o")["family"] == "other"
    assert module._model_profile(None)["family"] == "other"
    assert module._model_profile("")["family"] == "other"


def test_model_profile_reasoning_filter_flag():
    # The reasoning_filter flag drives stripping (PRD-multi-family-v2 §3).
    assert module._model_profile("claude-glm-5.2")["reasoning_filter"] is True
    assert module._model_profile("glm-5.2")["reasoning_filter"] is True
    # Deleted text routes resolve to the inert fallback (reasoning_filter=False),
    # so thinking passes through — same behavior as before the consolidation.
    assert module._model_profile("claude-sonnet-5")["reasoning_filter"] is False
    assert module._model_profile("claude-haiku-4-5")["reasoning_filter"] is False
    # Unknown -> inert fallback: does NOT strip (a miss must not remove
    # thinking from a possible genuine Anthropic response — F-C).
    assert module._model_profile("gpt-4o")["reasoning_filter"] is False


def test_nonstream_glm_strips_thinking():
    response = apply_nonstream("claude-glm-5.2", thinking_response())
    assert [block["type"] for block in response["content"]] == ["text"]


def test_nonstream_sonnet_passes_thinking_through():
    response = apply_nonstream("claude-sonnet-5", thinking_response())
    assert [block["type"] for block in response["content"]] == ["thinking", "text"]
    assert response["content"][0]["thinking"] == "secret"


def test_nonstream_haiku_passes_thinking_through():
    response = apply_nonstream("claude-haiku-4-5", thinking_response())
    assert [block["type"] for block in response["content"]] == ["thinking", "text"]
    assert response["content"][0]["thinking"] == "secret"


def test_stream_glm_strips_thinking():
    result = events(asyncio.run(filtered_model(thinking_stream(), "claude-glm-5.2")))
    serialized = json.dumps(result)
    assert "thinking" not in serialized
    assert "signature_delta" not in serialized
    # text block compacted to index 0
    indexed = [(e["type"], e["index"]) for e in result if "index" in e]
    assert indexed == [
        ("content_block_start", 0), ("content_block_delta", 0), ("content_block_stop", 0),
    ]


def test_stream_sonnet_passes_thinking_through():
    source = thinking_stream()
    result = asyncio.run(filtered_model(source, "claude-sonnet-5"))
    # passed through unchanged: output equals input verbatim
    assert result == source


def test_stream_haiku_passes_thinking_through():
    source = thinking_stream()
    result = asyncio.run(filtered_model(source, "claude-haiku-4-5"))
    assert result == source


if __name__ == "__main__":
    test_stream_hides_reasoning_and_compacts_indexes()
    test_nonstream_and_openai_passthrough()
    test_model_profile_family()
    test_model_profile_reasoning_filter_flag()
    test_nonstream_glm_strips_thinking()
    test_nonstream_sonnet_passes_thinking_through()
    test_nonstream_haiku_passes_thinking_through()
    test_stream_glm_strips_thinking()
    test_stream_sonnet_passes_thinking_through()
    test_stream_haiku_passes_thinking_through()
    print("anthropic_reasoning_filter tests passed")
