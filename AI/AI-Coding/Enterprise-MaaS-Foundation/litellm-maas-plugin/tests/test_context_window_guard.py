import asyncio
import copy
import importlib.util
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


def run_hook(data):
    return asyncio.run(
        cwg.proxy_handler_instance.async_pre_call_hook(
            user_api_key_dict=None, cache=None, data=data, call_type="completion"
        )
    )


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
