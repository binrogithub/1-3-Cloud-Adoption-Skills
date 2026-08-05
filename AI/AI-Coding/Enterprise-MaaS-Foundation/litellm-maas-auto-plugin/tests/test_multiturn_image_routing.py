"""Tests for multi-turn image routing — _has_image must only inspect the
latest user message, not historical messages that carry images from prior
turns."""

import copy
import importlib.util
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"

# ── stub litellm so the module loads without the real package ─────────────
litellm = types.ModuleType("litellm")
litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules["litellm"] = litellm
sys.modules["litellm.integrations"] = types.ModuleType("litellm.integrations")
sys.modules["litellm.integrations.custom_logger"] = custom_logger

spec = importlib.util.spec_from_file_location("smart_router", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

# ── helpers ───────────────────────────────────────────────────────────────
IMG_BLOCK = {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR="}}
TEXT_BLOCK = {"type": "text", "text": "hello"}


def msg(role, content):
    """Build a message with either a string or list content."""
    return {"role": role, "content": content}


def user_text(text):
    return msg("user", text)


def user_rich(text, image=False):
    blocks = [{"type": "text", "text": text}]
    if image:
        blocks.append(copy.deepcopy(IMG_BLOCK))
    return msg("user", blocks)


def assistant_text(text):
    return msg("assistant", text)


def run(data):
    """Route a request and return (model, matched_rule)."""
    data = copy.deepcopy(data)
    result = router.route_request(data)
    info = result["metadata"]["smart_router"]
    return result["model"], info["matched_rule"]


# ── 1. Single-turn baseline ───────────────────────────────────────────────

def test_single_turn_with_image_routes_to_vision():
    """Turn 1: user sends an image → must route to vision."""
    data = {"model": "claude-opus-4-6", "messages": [user_rich("What is this?", image=True)]}
    model, rule = run(data)
    assert model == "vision-openrouter", f"expected vision, got {model}"
    assert rule == "image"


def test_single_turn_without_image_stays_on_glm():
    """Turn 1: user sends text only → must stay on GLM."""
    data = {"model": "claude-opus-4-6", "messages": [user_text("Write a Python function")]}
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"expected GLM, got {model}"
    assert rule == "glm_execution"


# ── 2. Multi-turn: image in history, text in current turn ─────────────────

def test_multiturn_image_in_history_text_now_stays_glm():
    """Turn 2: history has image, current message is text-only → GLM."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_rich("What is this?", image=True),       # Turn 1 (history)
            assistant_text("It's a cat."),                 # Turn 1 reply
            user_text("Tell me more about cats"),          # Turn 2 (current)
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"expected GLM (not vision), got {model}"
    assert rule == "glm_execution"


def test_multiturn_image_in_history_vision_text_now_stays_glm():
    """Turn 2: history has image + vision keyword, current is plain → GLM."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_rich("Create a UI design", image=True),   # Turn 1 (history, vision keyword)
            assistant_text("Here's a wireframe..."),        # Turn 1 reply
            user_text("Now write the backend code"),        # Turn 2 (current, no image)
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"expected GLM, got {model}"
    assert rule == "glm_execution"


# ── 3. Multi-turn: image in current turn ──────────────────────────────────

def test_multiturn_image_in_current_turn_routes_to_vision():
    """Turn 2: current message has an image → vision."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_text("Let's talk about photos"),          # Turn 1 (history, text)
            assistant_text("Sure!"),                        # Turn 1 reply
            user_rich("What's in this image?", image=True), # Turn 2 (current, image)
        ],
    }
    model, rule = run(data)
    assert model == "vision-openrouter", f"expected vision, got {model}"
    assert rule == "image"


def test_multiturn_image_in_both_turns_routes_to_vision():
    """Turn 2: both turns have images → vision (current turn has image)."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_rich("First image", image=True),           # Turn 1 (history, image)
            assistant_text("Got it."),                       # Turn 1 reply
            user_rich("Second image", image=True),           # Turn 2 (current, image)
        ],
    }
    model, rule = run(data)
    assert model == "vision-openrouter", f"expected vision, got {model}"
    assert rule == "image"


# ── 4. Multi-turn loop simulation (3+ turns) ──────────────────────────────

def test_three_turn_loop_image_only_in_first():
    """Simulate a 3-turn conversation where only Turn 1 has an image."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_rich("Analyze this screenshot", image=True),  # Turn 1: image
            assistant_text("I see a login form."),              # Turn 1 reply
            user_text("How do I improve it?"),                  # Turn 2: text
            assistant_text("Add error messages."),              # Turn 2 reply
            user_text("Show me the code"),                      # Turn 3: text
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"Turn 3 should be GLM, got {model}"
    assert rule == "glm_execution"


def test_three_turn_loop_image_in_middle_turn():
    """Image appears in Turn 2 but not Turn 3 → Turn 3 stays GLM."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_text("Let's design something"),               # Turn 1: text
            assistant_text("OK."),                              # Turn 1 reply
            user_rich("Check this mockup", image=True),         # Turn 2: image
            assistant_text("Looks good."),                      # Turn 2 reply
            user_text("Write the HTML now"),                    # Turn 3: text
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"Turn 3 should be GLM, got {model}"
    assert rule == "glm_execution"


def test_three_turn_loop_image_in_last_turn():
    """Image in Turn 3 → vision."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_text("Help me with design"),                  # Turn 1: text
            assistant_text("Sure."),                            # Turn 1 reply
            user_text("I have a screenshot"),                   # Turn 2: text
            assistant_text("Share it."),                        # Turn 2 reply
            user_rich("Here it is", image=True),                # Turn 3: image
        ],
    }
    model, rule = run(data)
    assert model == "vision-openrouter", f"Turn 3 should be vision, got {model}"
    assert rule == "image"


# ── 5. Edge cases ─────────────────────────────────────────────────────────

def test_empty_messages():
    """No messages at all → no image, no crash."""
    data = {"model": "claude-opus-4-6", "messages": []}
    assert router._has_image(data) is False


def test_no_user_messages():
    """Only assistant messages → no image."""
    data = {"model": "claude-opus-4-6", "messages": [assistant_text("Hello")]}
    assert router._has_image(data) is False


def test_system_message_with_image_does_not_trigger_vision():
    """System message with image block should NOT trigger vision routing."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "system", "content": [copy.deepcopy(IMG_BLOCK)]},
            user_text("Write a function"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"system image should not route to vision, got {model}"
    assert rule == "glm_execution"


def test_string_content_no_image():
    """User message with plain string content → no image."""
    data = {"model": "claude-opus-4-6", "messages": [user_text("Hello world")]}
    assert router._has_image(data) is False


def test_input_key_works_same_as_messages():
    """The 'input' key (used by some API formats) should behave identically."""
    data = {
        "model": "claude-opus-4-6",
        "input": [
            user_rich("What is this?", image=True),
            assistant_text("A dog."),
            user_text("What breed?"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"input key: Turn 2 should be GLM, got {model}"
    assert rule == "glm_execution"


def test_image_only_in_assistant_reply_not_user():
    """Image in assistant's prior reply, current user message is text → GLM."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            user_text("Generate an image"),
            {"role": "assistant", "content": [copy.deepcopy(IMG_BLOCK)]},
            user_text("Make it bigger"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-opus-4-6", f"assistant image should not route to vision, got {model}"
    assert rule == "glm_execution"


def test_large_historical_image_does_not_force_premium_context_route():
    """Huge historical image payloads should not affect text-turn token routing."""
    old_counter = litellm.token_counter
    litellm.token_counter = lambda **kwargs: len(
        json.dumps(kwargs.get("messages") or [], default=str)
    ) // 4
    try:
        large_image = {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + ("A" * 900000)},
        }
        data = {
            "model": "claude-opus-4-6",
            "messages": [
                msg("user", [{"type": "text", "text": "Analyze this"}, large_image]),
                assistant_text("Done."),
                user_text("Write a simple pytest"),
            ],
        }
        result = router.route_request(copy.deepcopy(data))
        assert result["model"] == "claude-opus-4-6"
        assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"
        assert result["metadata"]["smart_router"]["estimated_tokens"] < 198000
        assert result["messages"][0]["content"] == [
            {"type": "text", "text": "Analyze this"},
            {"type": "text", "text": "[图片内容已省略]"},
        ]
    finally:
        litellm.token_counter = old_counter


# ── 6. Regression: existing single-turn image test still passes ───────────

def test_existing_single_turn_image_test():
    """The original test_image_fallback_stays_vision_capable must still pass."""
    data = {
        "model": "claude-opus-4-6",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is shown?"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
                ],
            }
        ],
    }
    result = router.route_request(data)
    assert result["model"] == "vision-openrouter"
    assert result["fallbacks"] == ["vision-openrouter-secondary"]
    assert result["metadata"]["smart_router"]["matched_rule"] == "image"


# ── 7. Full conversation loop simulation ──────────────────────────────────

def test_full_conversation_loop():
    """Simulate a realistic 5-turn conversation:
    Turn 1: image → vision
    Turn 2: follow-up text → GLM (was vision before fix!)
    Turn 3: text → GLM
    Turn 4: new image → vision
    Turn 5: follow-up text → GLM (was vision before fix!)
    """
    base_model = "claude-opus-4-6"
    conversation = []  # accumulates messages

    # Turn 1: image
    conversation.append(user_rich("Analyze this screenshot", image=True))
    model1, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert model1 == "vision-openrouter", f"Turn 1: expected vision, got {model1}"
    conversation.append(assistant_text("I see a dashboard."))

    # Turn 2: text follow-up
    conversation.append(user_text("Add a chart to it"))
    model2, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert model2 == "claude-opus-4-6", f"Turn 2: expected GLM, got {model2}"
    conversation.append(assistant_text("Here's the updated code."))

    # Turn 3: text
    conversation.append(user_text("Now deploy it"))
    model3, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert model3 == "claude-opus-4-6", f"Turn 3: expected GLM, got {model3}"
    conversation.append(assistant_text("Deployed."))

    # Turn 4: new image
    conversation.append(user_rich("Check this result", image=True))
    model4, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert model4 == "vision-openrouter", f"Turn 4: expected vision, got {model4}"
    conversation.append(assistant_text("Looks correct."))

    # Turn 5: text follow-up
    conversation.append(user_text("Great, write a test for it"))
    model5, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert model5 == "claude-opus-4-6", f"Turn 5: expected GLM, got {model5}"


# ── Bug fix tests: text referencing previous image ──


def test_text_references_previous_image_routes_to_vision():
    """User says '请重新帮我分析下上一张报错截图' with image in history → Vision."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这是报错截图"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR"}},
            ],
        },
        {"role": "assistant", "content": "这是一个错误提示截图。"},
        {"role": "user", "content": "请重新帮我分析下上一张报错截图。"},
    ]
    model, rule = run({"model": "claude-opus-4-6", "messages": messages})
    assert model == "vision-openrouter", f"Expected vision-openrouter, got {model}"
    assert rule == "image_reference", (
        f"Expected route_reason='image_reference', got {rule}"
    )


def test_text_references_image_no_history_stays_glm():
    """User says '看下截图' but NO image in history → stays on GLM (no false positive)."""
    messages = [
        {"role": "user", "content": "我们来讨论一下设计"},
        {"role": "assistant", "content": "好的，请说"},
        {"role": "user", "content": "请帮我看下这张截图"},
    ]
    model, _ = run({"model": "claude-opus-4-6", "messages": messages})
    assert model == "claude-opus-4-6", f"Expected GLM (no history image), got {model}"


def test_text_references_image_keyword_variations():
    """Various Chinese keywords that reference previous images should all route to Vision."""
    base_history = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看这个"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        },
        {"role": "assistant", "content": "看到了"},
    ]
    test_prompts = [
        "再看一下刚才的截图",
        "重新分析下上一张图片",
        "帮我看下那张照片",
        "分析一下这张截图",
        "看看上一张图",
    ]
    for prompt in test_prompts:
        msgs = copy.deepcopy(base_history) + [{"role": "user", "content": prompt}]
        model, rule = run({"model": "claude-opus-4-6", "messages": msgs})
        assert model == "vision-openrouter", (
            f"Prompt '{prompt}': expected vision-openrouter, got {model}"
        )
        assert rule == "image_reference", (
            f"Prompt '{prompt}': expected image_reference, got {rule}"
        )


def test_english_text_references_screenshot_routes_to_vision():
    """English prompts referencing previous screenshots should route to Vision."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Check this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}},
            ],
        },
        {"role": "assistant", "content": "I see the screenshot."},
        {"role": "user", "content": "Can you re-analyze the last screenshot?"},
    ]
    model, rule = run({"model": "claude-opus-4-6", "messages": messages})
    assert model == "vision-openrouter", f"Expected vision-openrouter, got {model}"
    assert rule == "image_reference", (
        f"Expected image_reference, got {rule}"
    )


def test_ordinary_text_containing_tu_stays_glm():
    """Words that merely contain 图 must not be read as image references.

    Once any image appears in history, ``_history_has_image`` is permanently
    true for that conversation, so a loose keyword regex misroutes every
    later text turn to the (external, premium) vision model.  These are all
    ordinary engineering prompts with no image intent.
    """
    base_history = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看这个报错"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        },
        {"role": "assistant", "content": "这是空指针异常。"},
    ]
    non_image_prompts = [
        "我试图解决这个 bug",
        "这个函数的意图是什么",
        "视图层的逻辑有问题",
        "把地图组件重构一下",
        "这个图书管理系统怎么设计",
    ]
    for prompt in non_image_prompts:
        msgs = copy.deepcopy(base_history) + [{"role": "user", "content": prompt}]
        model, rule = run({"model": "claude-opus-4-6", "messages": msgs})
        assert rule != "image_reference", (
            f"Prompt '{prompt}': misread as an image reference, routed to {model}"
        )
        assert model == "claude-opus-4-6", (
            f"Prompt '{prompt}': expected GLM, got {model} (rule={rule})"
        )


# ── Bug fix tests: _strip_images preserves context ──


def test_strip_images_replaces_with_placeholder_not_delete():
    """_strip_images should replace image blocks with text placeholders, not delete them."""
    data = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看这个截图"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                ],
            },
            {"role": "assistant", "content": "我看到了"},
            {"role": "user", "content": "继续分析"},
        ]
    }
    router._strip_images(data)
    # First message should still have 2 blocks: text + placeholder
    first_msg = data["messages"][0]
    assert isinstance(first_msg["content"], list), "Content should still be a list"
    assert len(first_msg["content"]) == 2, (
        f"Expected 2 blocks (text + placeholder), got {len(first_msg['content'])}"
    )
    # First block should be the original text
    assert first_msg["content"][0]["type"] == "text"
    assert first_msg["content"][0]["text"] == "看这个截图"
    # Second block should be the placeholder text
    assert first_msg["content"][1]["type"] == "text"
    assert "省略" in first_msg["content"][1]["text"], (
        f"Expected placeholder text, got: {first_msg['content'][1]['text']}"
    )
    # No image_url blocks should remain
    for msg in data["messages"]:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    assert block.get("type") not in {"image", "image_url", "input_image"}, (
                        f"Image block should have been replaced: {block}"
                    )


def test_strip_images_preserves_text_blocks_around_images():
    """_strip_images should preserve text blocks that appear before and after image blocks."""
    data = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "before image"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}},
                    {"type": "text", "text": "after image"},
                ],
            },
        ]
    }
    router._strip_images(data)
    content = data["messages"][0]["content"]
    assert len(content) == 3, f"Expected 3 blocks, got {len(content)}"
    assert content[0]["text"] == "before image"
    assert content[1]["type"] == "text" and "省略" in content[1]["text"]
    assert content[2]["text"] == "after image"


if __name__ == "__main__":
    tests = [
        test_single_turn_with_image_routes_to_vision,
        test_single_turn_without_image_stays_on_glm,
        test_multiturn_image_in_history_text_now_stays_glm,
        test_multiturn_image_in_history_vision_text_now_stays_glm,
        test_multiturn_image_in_current_turn_routes_to_vision,
        test_multiturn_image_in_both_turns_routes_to_vision,
        test_three_turn_loop_image_only_in_first,
        test_three_turn_loop_image_in_middle_turn,
        test_three_turn_loop_image_in_last_turn,
        test_empty_messages,
        test_no_user_messages,
        test_system_message_with_image_does_not_trigger_vision,
        test_string_content_no_image,
        test_input_key_works_same_as_messages,
        test_image_only_in_assistant_reply_not_user,
        test_large_historical_image_does_not_force_premium_context_route,
        test_existing_single_turn_image_test,
        test_full_conversation_loop,
        # ── Bug fix: text referencing previous image → route to Vision ──
        test_text_references_previous_image_routes_to_vision,
        test_text_references_image_no_history_stays_glm,
        test_text_references_image_keyword_variations,
        test_english_text_references_screenshot_routes_to_vision,
        test_ordinary_text_containing_tu_stays_glm,
        # ── Bug fix: _strip_images preserves context with placeholder ──
        test_strip_images_replaces_with_placeholder_not_delete,
        test_strip_images_preserves_text_blocks_around_images,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✅ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
