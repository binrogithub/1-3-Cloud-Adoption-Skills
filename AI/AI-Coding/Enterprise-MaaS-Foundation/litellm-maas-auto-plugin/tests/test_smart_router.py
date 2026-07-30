import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
RULES = ROOT / "litellm_plugins" / "smart_router" / "smart_router_rules.json"
SCHEMA = ROOT / "litellm_plugins" / "smart_router" / "smart_router_rules.schema.json"

litellm = types.ModuleType("litellm")
litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm", litellm)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)
spec = importlib.util.spec_from_file_location("smart_router", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def request(text, token_count=100):
    litellm.token_counter = lambda **kwargs: token_count
    return {"model": "claude-opus-4-6", "messages": [{"role": "user", "content": text}]}


def test_multilingual_routes():
    premium = [
        "Design the system architecture",
        "设计数据库表结构",
        "Desenhe a arquitetura do sistema",
        "Diseña la arquitectura del sistema",
        "Faça uma revisão de segurança",
        "Analiza un incidente en producción",
    ]
    for text in premium:
        assert router.route_request(request(text))["model"] == "premium-openrouter"

    vision = [
        "Create a UI design",
        "设计网页界面",
        "Crie um design de interface",
        "Crea un diseño de interfaz",
    ]
    for text in vision:
        assert router.route_request(request(text))["model"] == "vision-openrouter"


def test_observability_and_score_does_not_route():
    result = router.route_request(
        request("Analyze why this code fails, then fix it:\n```python\nprint(x)\n```", 1000)
    )
    info = result["metadata"]["smart_router"]
    assert result["model"] == "claude-opus-4-6"
    assert info["estimated_tokens"] == 1000
    assert info["matched_rule"] == "glm_execution"
    assert 0 < info["complexity_score"] <= 1
    assert info["router_version"] == "2.0.0"
    assert info["fallback_chain"] == ["premium-openrouter"]


def test_context_boundary_and_controlled_fallbacks():
    boundary = router.route_request(request("Fix the test", 198000))
    assert boundary["model"] == "claude-opus-4-6"
    assert boundary["fallbacks"] == ["premium-openrouter"]

    over = router.route_request(request("Fix the test", 198001))
    assert over["model"] == "premium-openrouter"
    assert "fallbacks" not in over

    architecture = router.route_request(request("Design the system architecture", 100))
    assert architecture["fallbacks"] == ["claude-*"]

    security = router.route_request(request("Perform a security review", 100))
    assert security["model"] == "premium-openrouter"
    assert "fallbacks" not in security

    sensitive = router.route_request(request("Fix this confidential personal data parser", 100))
    assert sensitive["model"] == "claude-opus-4-6"
    assert "fallbacks" not in sensitive
    assert sensitive["metadata"]["smart_router"]["cross_border_fallback_blocked"] is True

    sensitive_system = request("Fix the parser", 100)
    sensitive_system["system"] = "China-only confidential workload"
    sensitive_system = router.route_request(sensitive_system)
    assert "fallbacks" not in sensitive_system
    assert (
        sensitive_system["metadata"]["smart_router"]["cross_border_fallback_blocked"]
        is True
    )

    vision = router.route_request(request("Create a UI design", 100))
    assert vision["fallbacks"] == ["vision-openrouter-secondary"]
    assert "claude-*" not in vision["fallbacks"]


def test_image_fallback_stays_vision_capable():
    data = request("What is shown?", 100)
    data["messages"][0]["content"] = [
        {"type": "text", "text": "What is shown?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
    ]
    result = router.route_request(data)
    assert result["model"] == "vision-openrouter"
    assert result["fallbacks"] == ["vision-openrouter-secondary"]
    assert result["metadata"]["smart_router"]["matched_rule"] == "image"


def test_rules_schema_and_runtime_validation():
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert router._validate_rules(copy.deepcopy(rules)) == rules

    invalid = copy.deepcopy(rules)
    invalid["unknown"] = True
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(invalid, handle)
        handle.flush()
        try:
            router.load_rules(handle.name)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown keys must fail validation")

    invalid = copy.deepcopy(rules)
    invalid["complexity"]["weights"]["code"] = 0.99
    try:
        router._validate_rules(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("weights that do not sum to one must fail")


if __name__ == "__main__":
    test_multilingual_routes()
    test_observability_and_score_does_not_route()
    test_context_boundary_and_controlled_fallbacks()
    test_image_fallback_stays_vision_capable()
    test_rules_schema_and_runtime_validation()
    print("smart_router tests passed")
