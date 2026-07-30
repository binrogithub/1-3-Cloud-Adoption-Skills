import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"

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


def test_context_boundary_and_default_glm():
    assert router.route_request(request("Fix the test", 198000))["model"] == "claude-opus-4-6"
    assert router.route_request(request("Fix the test", 198001))["model"] == "premium-openrouter"
    result = router.route_request(request("Corrija este teste unitário", 100))
    assert result["model"] == "claude-opus-4-6"
    assert result["metadata"]["smart_router"]["route_reason"] == "glm_execution"


if __name__ == "__main__":
    test_multilingual_routes()
    test_context_boundary_and_default_glm()
    print("smart_router tests passed")
