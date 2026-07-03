from conftest import edits_by_type, load_fixture, run_guard, trigger_value


def test_missing_context_management_injects_default_edits(plugin_module):
    request_body = load_fixture("text_request.json")

    transformed = run_guard(plugin_module, request_body)
    edits = edits_by_type(transformed)

    assert set(edits) == {"clear_tool_uses_20250919", "compact_20260112"}
    clear_tool_uses = edits["clear_tool_uses_20250919"]
    compact = edits["compact_20260112"]

    assert trigger_value(clear_tool_uses) == 100000
    assert clear_tool_uses["keep"] == {"type": "tool_uses", "value": 3}
    assert trigger_value(compact) == 150000


def test_existing_context_management_is_preserved_and_clamped(plugin_module):
    request_body = load_fixture("existing_context_management.json")

    transformed = run_guard(plugin_module, request_body)
    edits = edits_by_type(transformed)

    assert "custom_audit_marker" in edits
    assert "clear_tool_uses_20250919" in edits
    assert "compact_20260112" in edits

    clear_tool_uses = edits["clear_tool_uses_20250919"]
    compact = edits["compact_20260112"]

    assert trigger_value(clear_tool_uses) <= 100000
    assert clear_tool_uses["keep"]["type"] == "tool_uses"
    assert clear_tool_uses["keep"]["value"] <= 3
    assert trigger_value(compact) <= 150000
