from conftest import EXPECTED_EXECUTION_MODEL, load_fixture, route_model, run_guard


def test_text_request_routes_to_execution_model(plugin_module):
    request_body = load_fixture("text_request.json")

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_EXECUTION_MODEL
    assert route_model(transformed) != "vision-openrouter"


def test_current_host_opus_alias_routes_to_execution_model(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "claude-opus-4-6"

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_EXECUTION_MODEL


def test_current_host_backend_alias_routes_to_execution_model(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "claude-opus-4-6-backend"

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_EXECUTION_MODEL
    metadata = transformed.get("metadata") or {}
    guard_audit = metadata.get("cc_glm52_guard") if isinstance(metadata, dict) else {}
    assert guard_audit.get("capability_mode") == "backend_fallback"
