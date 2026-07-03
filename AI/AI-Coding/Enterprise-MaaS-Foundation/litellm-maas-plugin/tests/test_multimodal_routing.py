from conftest import EXPECTED_VISION_MODEL, load_fixture, route_model, run_guard


def test_image_request_routes_to_vision_openrouter(plugin_module):
    request_body = load_fixture("image_request.json")

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_VISION_MODEL
    metadata = transformed.get("metadata") or {}
    routing = metadata.get("routing") if isinstance(metadata, dict) else {}
    guard_audit = metadata.get("cc_glm52_guard") if isinstance(metadata, dict) else {}
    multimodal_route = (
        transformed.get("multimodal_route")
        or metadata.get("multimodal_route")
        or (guard_audit or {}).get("multimodal_route")
        or (routing or {}).get("multimodal_route")
    )
    assert multimodal_route is True
