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
        assert result["messages"][0]["content"] == [{"type": "text", "text": "Analyze this"}]
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
