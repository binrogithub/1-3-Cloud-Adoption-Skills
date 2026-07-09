from conftest import EXPECTED_EXECUTION_MODEL, load_fixture, route_model, run_guard


def test_backend_mode_search_injects_litellm_search_tool(plugin_module):
    request_body = load_fixture("backend_search_request.json")

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_EXECUTION_MODEL
    tools = transformed.get("tools") or []
    assert any(tool.get("name") == "litellm_web_search" for tool in tools)

    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["capability_mode"] == "backend_fallback"
    assert audit["search_intent"] is True
    assert audit["backend_search_enabled"] is True
    assert audit["search_backend_used"] is True
