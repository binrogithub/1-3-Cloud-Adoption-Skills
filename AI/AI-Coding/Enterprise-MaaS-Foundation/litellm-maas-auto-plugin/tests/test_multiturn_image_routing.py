"""Tests for multi-turn image handling after the GLM-5.2 mainline + sidecar
rework (PRD-glm52-mainline-sidecars).

Before the rework, an image in the current turn routed the WHOLE turn to
vision-openrouter. Now GLM-5.2 owns every final answer: the bounded Vision
sidecar captions images and injects the caption text in-place, so the request
stays on the GLM mainline. These tests verify route_request (the sync core,
run AFTER sidecar orchestration) keeps every turn — image or text — on the
mainline as glm_execution.

The sidecar's own extraction/captioning/injection logic is tested in
tests/test_sidecar.py.
"""

import copy
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"

# Stub litellm so the module loads without the real package.
litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

spec = importlib.util.spec_from_file_location("smart_router", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

IMG_BLOCK = {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR="}}


def msg(role, content):
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


# ── Every turn stays on the mainline (images no longer route to vision) ─────


def test_single_turn_with_image_stays_on_glm():
    """Turn 1: user sends an image -> stays on GLM (sidecar captions it)."""
    data = {"model": "claude-glm-5.2", "messages": [user_rich("What is this?", image=True)]}
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"expected GLM, got {model}"
    assert rule == "glm_execution"


def test_single_turn_without_image_stays_on_glm():
    data = {"model": "claude-glm-5.2", "messages": [user_text("Write a Python function")]}
    model, rule = run(data)
    assert model == "claude-glm-5.2"
    assert rule == "glm_execution"


def test_multiturn_image_in_history_text_now_stays_glm():
    """Turn 2: history has image, current message is text-only -> GLM."""
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            user_rich("What is this?", image=True),
            assistant_text("It's a cat."),
            user_text("Tell me more about cats"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"expected GLM, got {model}"
    assert rule == "glm_execution"


def test_multiturn_image_in_current_turn_stays_glm():
    """Turn 2: current message has an image -> GLM (not vision)."""
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            user_text("Let's talk about photos"),
            assistant_text("Sure!"),
            user_rich("What's in this image?", image=True),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"expected GLM, got {model}"
    assert rule == "glm_execution"


def test_multiturn_image_in_both_turns_stays_glm():
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            user_rich("First image", image=True),
            assistant_text("Got it."),
            user_rich("Second image", image=True),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"expected GLM, got {model}"
    assert rule == "glm_execution"


def test_three_turn_loop_image_only_in_first():
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            user_rich("Analyze this screenshot", image=True),
            assistant_text("I see a login form."),
            user_text("How do I improve it?"),
            assistant_text("Add error messages."),
            user_text("Show me the code"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"Turn 3 should be GLM, got {model}"
    assert rule == "glm_execution"


def test_three_turn_loop_image_in_last_turn():
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            user_text("Help me with design"),
            assistant_text("Sure."),
            user_text("I have a screenshot"),
            assistant_text("Share it."),
            user_rich("Here it is", image=True),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"Turn 3 with image should be GLM, got {model}"
    assert rule == "glm_execution"


def test_text_references_previous_image_stays_glm():
    """A text turn referencing a previous image stays on GLM. The cached caption
    already exists in history (injected by the sidecar), so no vision call."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这是报错截图"},
                {"type": "text", "text": "[vision-caption]error[/vision-caption]"},
            ],
        },
        {"role": "assistant", "content": "这是一个错误提示截图。"},
        {"role": "user", "content": "请重新帮我分析下上一张报错截图。"},
    ]
    model, rule = run({"model": "claude-glm-5.2", "messages": messages})
    assert model == "claude-glm-5.2", f"Expected GLM, got {model}"
    assert rule == "glm_execution"


def test_input_key_works_same_as_messages():
    data = {
        "model": "claude-glm-5.2",
        "input": [
            user_rich("What is this?", image=True),
            assistant_text("A dog."),
            user_text("What breed?"),
        ],
    }
    model, rule = run(data)
    assert model == "claude-glm-5.2", f"input key: Turn 2 should be GLM, got {model}"
    assert rule == "glm_execution"


def test_full_conversation_loop():
    """A 5-turn conversation: every turn (image or text) stays on GLM."""
    base_model = "claude-glm-5.2"
    conversation = []
    conversation.append(user_rich("Analyze this screenshot", image=True))
    m1, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert m1 == "claude-glm-5.2", f"Turn 1: expected GLM, got {m1}"
    conversation.append(assistant_text("I see a dashboard."))

    conversation.append(user_text("Add a chart to it"))
    m2, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert m2 == "claude-glm-5.2", f"Turn 2: expected GLM, got {m2}"
    conversation.append(assistant_text("Here's the updated code."))

    conversation.append(user_text("Now deploy it"))
    m3, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert m3 == "claude-glm-5.2", f"Turn 3: expected GLM, got {m3}"
    conversation.append(assistant_text("Deployed."))

    conversation.append(user_rich("Check this result", image=True))
    m4, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert m4 == "claude-glm-5.2", f"Turn 4: expected GLM, got {m4}"
    conversation.append(assistant_text("Looks correct."))

    conversation.append(user_text("Great, write a test for it"))
    m5, _ = run({"model": base_model, "messages": copy.deepcopy(conversation)})
    assert m5 == "claude-glm-5.2", f"Turn 5: expected GLM, got {m5}"


def test_route_request_does_not_strip_image_blocks():
    """route_request leaves image blocks in place — the sidecar owns caption
    injection (run before route_request). route_request must not strip."""
    data = {
        "model": "claude-glm-5.2",
        "messages": [user_rich("What is this?", image=True)],
    }
    result = router.route_request(copy.deepcopy(data))
    # The image block is still there (route_request doesn't touch it).
    content = result["messages"][0]["content"]
    assert any(b.get("type") == "image_url" for b in content if isinstance(b, dict)), (
        "route_request must not strip image blocks (sidecar owns that)"
    )


if __name__ == "__main__":
    tests = [
        test_single_turn_with_image_stays_on_glm,
        test_single_turn_without_image_stays_on_glm,
        test_multiturn_image_in_history_text_now_stays_glm,
        test_multiturn_image_in_current_turn_stays_glm,
        test_multiturn_image_in_both_turns_stays_glm,
        test_three_turn_loop_image_only_in_first,
        test_three_turn_loop_image_in_last_turn,
        test_text_references_previous_image_stays_glm,
        test_input_key_works_same_as_messages,
        test_full_conversation_loop,
        test_route_request_does_not_strip_image_blocks,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ok {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
