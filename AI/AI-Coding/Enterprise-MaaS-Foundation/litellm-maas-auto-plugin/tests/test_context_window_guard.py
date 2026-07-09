import asyncio
import copy
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path

import pytest

if "litellm" not in sys.modules:
    litellm = types.ModuleType("litellm")
    logging_module = types.ModuleType("litellm._logging")
    integrations = types.ModuleType("litellm.integrations")
    custom_logger = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:
        pass

    logging_module.verbose_proxy_logger = logging.getLogger("context_window_guard_test")
    custom_logger.CustomLogger = CustomLogger
    sys.modules.setdefault("litellm", litellm)
    sys.modules.setdefault("litellm._logging", logging_module)
    sys.modules.setdefault("litellm.integrations", integrations)
    sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

_CALLBACK_PATH = (
    Path(__file__).resolve().parents[1]
    / "litellm_plugins"
    / "context_window_guard"
    / "callback.py"
)
_spec = importlib.util.spec_from_file_location("cwg_callback", _CALLBACK_PATH)
cwg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cwg)


def run_hook(data, guard=None):
    return asyncio.run(
        (guard or cwg.proxy_handler_instance).async_pre_call_hook(
            user_api_key_dict=None, cache=None, data=data, call_type="completion"
        )
    )


def vision_guard():
    g = cwg.ContextWindowGuard()
    g.vision_model = "vision-openrouter"
    g.vision_keep_models = {"vision-openrouter"}
    return g


def image_block(chars):
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "A" * chars},
    }


def big_ascii(tokens):
    # ~3.7 chars per estimated token
    return "x" * int(tokens * 3.7)


def tool_exchange(result_text, tool_id="t1"):
    return [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_id, "name": "Read", "input": {"file": "a.py"}}
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": result_text}
            ],
        },
    ]


def test_small_request_untouched():
    data = {
        "model": "claude-opus-4-6",
        "system": "be brief",
        "messages": [{"role": "user", "content": "hello"}],
        "metadata": {},
    }
    expected = copy.deepcopy(data)
    out = run_hook(data)
    assert out == expected


def test_estimator_cjk_weighting():
    ascii_est = cwg._estimate_tokens("x" * 370)
    cjk_est = cwg._estimate_tokens("中" * 370)
    assert 95 <= ascii_est <= 105
    assert cjk_est >= 370


def test_old_tool_results_cleared_first():
    messages = [{"role": "user", "content": "start"}]
    for i in range(8):
        messages.extend(tool_exchange(big_ascii(25000), tool_id=f"t{i}"))
    messages.append({"role": "user", "content": "continue please"})
    data = {"model": "claude-opus-4-6", "messages": messages, "metadata": {}}

    run_hook(data)

    after = cwg._payload_estimate(data)
    assert after <= cwg.proxy_handler_instance.target
    # newest message untouched
    assert data["messages"][-1]["content"] == "continue please"
    audit = data["metadata"]["context_window_guard"]
    assert audit["blocks_cleared"] >= 1
    assert audit["estimated_tokens_after"] < audit["estimated_tokens_before"]


def test_single_turn_burst_in_last_message_truncated():
    # the real 217 failure: eight parallel ~25K-token reads in ONE user turn
    tool_results = [
        {"type": "tool_result", "tool_use_id": f"t{i}", "content": big_ascii(25000)}
        for i in range(8)
    ]
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "user", "content": "read these files"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": f"t{i}", "name": "Read", "input": {}}
                    for i in range(8)
                ],
            },
            {"role": "user", "content": tool_results},
        ],
        "metadata": {},
    }

    run_hook(data)

    after = cwg._payload_estimate(data)
    assert after <= cwg.proxy_handler_instance.target
    blocks = data["messages"][-1]["content"]
    truncated = [b for b in blocks if "truncated by context_window_guard" in b["content"]]
    assert truncated, "at least one oversized block must be truncated"
    for block in truncated:
        # head is preserved
        assert block["content"].startswith("xxxx")


def test_fail_open_on_weird_shapes():
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "user", "content": None},
            {"role": "user", "content": 42},
            "not-a-dict",
            {"role": "user", "content": [{"type": "tool_result", "content": {"odd": 1}}]},
        ],
    }
    expected = copy.deepcopy(data)
    out = run_hook(data)
    assert out == expected

    assert run_hook("not-a-dict") == "not-a-dict"
    assert run_hook({"model": "m"}) == {"model": "m"}


def test_image_request_rerouted_to_vision_model():
    # the 703KB-PNG failure: image request must go to the vision model
    # instead of 400ing on the text-only GLM backend
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "读一下这个图"},
                image_block(900_000),  # ~703KB PNG as base64
            ]},
        ],
        "metadata": {},
    }
    run_hook(data, vision_guard())
    assert data["model"] == "vision-openrouter"
    # image kept for the vision model
    types = [b["type"] for b in data["messages"][0]["content"]]
    assert "image" in types
    assert data["metadata"]["context_window_guard"]["vision_route"] == "vision-openrouter"


def test_vision_route_trims_text_but_keeps_image():
    messages = [{"role": "user", "content": "start"}]
    for i in range(6):
        messages.extend(tool_exchange(big_ascii(30000), tool_id=f"t{i}"))
    messages.append({"role": "user", "content": [
        {"type": "text", "text": "看图"}, image_block(900_000)]})
    data = {"model": "claude-opus-4-6", "messages": messages, "metadata": {}}
    g = vision_guard()

    run_hook(data, g)

    assert data["model"] == "vision-openrouter"
    types = [b["type"] for b in data["messages"][-1]["content"]]
    assert "image" in types, "vision route must keep the image"
    slots = cwg._collect_slots(data["messages"])
    imgs = [s for s in slots if s.kind == "image"]
    assert cwg._estimate_with_images(data, imgs, vision_route=True) <= g.vision_target


def test_already_vision_model_not_rerouted_but_budgeted():
    data = {
        "model": "vision-openrouter",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "hi"}, image_block(200_000)]}],
        "metadata": {},
    }
    run_hook(data, vision_guard())
    assert data["model"] == "vision-openrouter"
    types = [b["type"] for b in data["messages"][0]["content"]]
    assert "image" in types


def test_image_stripped_when_no_vision_model():
    # fallback: no vision route configured -> oversized image is stubbed
    # so the request no longer 400s on the GLM tokenizer
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "读一下这个图"},
                image_block(900_000),
            ]},
        ],
        "metadata": {},
    }
    run_hook(data)  # default instance: vision_model unset
    content = data["messages"][0]["content"]
    assert all(b["type"] != "image" for b in content), "image must be stubbed"
    assert any("image removed by context_window_guard" in b.get("text", "")
               for b in content)
    audit = data["metadata"]["context_window_guard"]
    assert audit["images_removed"] == 1
    assert data["model"] == "claude-opus-4-6"


def test_image_in_tool_result_stripped_when_no_vision_model():
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1",
                 "content": [image_block(900_000)]}]},
        ],
        "metadata": {},
    }
    run_hook(data)
    inner = data["messages"][-1]["content"][0]["content"]
    assert all(b["type"] != "image" for b in inner)
    assert data["metadata"]["context_window_guard"]["images_removed"] == 1


def test_shrunk_tool_inputs_keep_parameter_shape():
    # regression for the live "invalid tool parameters" failure: replacing
    # cleared tool_use inputs with a stub dict taught GLM to invoke NEW tools
    # with {"cleared_by_proxy": ...}; trimmed inputs must stay valid-shaped
    messages = [{"role": "user", "content": "start"}]
    for i in range(8):
        messages.append({
            "role": "assistant",
            "content": [{
                "type": "tool_use", "id": f"t{i}", "name": "Write",
                "input": {"file_path": f"/tmp/f{i}.py", "content": big_ascii(25000)},
            }],
        })
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}",
                         "content": "written"}],
        })
    messages.append({"role": "user", "content": "continue"})
    data = {"model": "claude-opus-4-6", "messages": messages, "metadata": {}}

    run_hook(data)

    assert cwg._payload_estimate(data) <= cwg.proxy_handler_instance.target
    dumped = json.dumps(data["messages"], ensure_ascii=False)
    assert "cleared_by_proxy" not in dumped
    shrunk = data["messages"][1]["content"][0]["input"]
    # parameter keys survive; oversized value is silently truncated (no
    # marker text - models copy markers into new calls too)
    assert set(shrunk) == {"file_path", "content"}
    assert shrunk["file_path"] == "/tmp/f0.py"
    assert len(shrunk["content"]) <= cwg.TOOL_INPUT_KEEP_CHARS
    assert "truncated by context_window_guard" not in shrunk["content"]
    assert data["metadata"]["context_window_guard"]["blocks_cleared"] >= 1


def test_shrunk_tool_inputs_idempotent():
    messages = [{"role": "user", "content": "start"}]
    for i in range(8):
        pair = tool_exchange(big_ascii(25000), tool_id=f"t{i}")
        pair[0]["content"][0]["input"] = {"command": big_ascii(25000)}
        messages.extend(pair)
    messages.append({"role": "user", "content": "continue"})
    data = {"model": "claude-opus-4-6", "messages": messages, "metadata": {}}

    def inputs():
        return [m["content"][0]["input"] for m in data["messages"]
                if isinstance(m.get("content"), list)
                and m["content"][0].get("type") == "tool_use"]

    run_hook(data)
    first = copy.deepcopy(inputs())
    run_hook(data)
    assert inputs() == first


def test_trim_under_backend_limit_with_margin():
    # end-to-end guarantee: a 210K-token-estimate request lands well under
    # the GLM-5.2 hard limit of 196608
    messages = [{"role": "user", "content": "go"}]
    for i in range(6):
        messages.extend(tool_exchange(big_ascii(35000), tool_id=f"t{i}"))
    data = {"model": "claude-opus-4-6", "messages": messages}
    assert cwg._payload_estimate(data) > 196608

    run_hook(data)

    assert cwg._payload_estimate(data) <= cwg.proxy_handler_instance.target < 196608
