import pytest
from src.tools.registry import (
    ToolDefinition,
    build_hcloud_command,
    build_obs_command,
    collect_all_tools,
)


class TestBuildHcloudCommand:
    def test_simple_command(self):
        cmd = build_hcloud_command("ECS", "ListServersDetails", {"region": "la-north-2"})
        assert cmd == "ECS ListServersDetails --cli-region=la-north-2"

    def test_with_param(self):
        cmd = build_hcloud_command("ECS", "ShowServer", {"region": "la-north-2", "server_id": "abc123"})
        assert "--cli-region=la-north-2" in cmd
        assert "--server_id=abc123" in cmd

    def test_with_param_mapping(self):
        cmd = build_hcloud_command("RDS", "ListFlavors", {"region": "la-north-2", "database_name": "MySQL"}, param_mapping={"database_name": "--database_name"})
        assert "--cli-region=la-north-2" in cmd
        assert "--database_name=MySQL" in cmd

    def test_none_value_skipped(self):
        cmd = build_hcloud_command("ECS", "ListServersDetails", {"region": "la-north-2", "name": None})
        assert "None" not in cmd
        assert "--cli-region=la-north-2" in cmd

    def test_boolean_value(self):
        cmd = build_hcloud_command("ECS", "ListServersDetails", {"region": "la-north-2", "brief": True})
        assert "--brief=true" in cmd

    def test_list_value(self):
        cmd = build_hcloud_command("ECS", "BatchAction", {"region": "la-north-2", "server_ids": ["id1", "id2"]})
        assert "--server_ids=id1,id2" in cmd


class TestBuildObsCommand:
    def test_simple(self):
        cmd = build_obs_command("ls", [], "la-north-2")
        assert cmd == "obs ls --cli-region=la-north-2"

    def test_with_args(self):
        cmd = build_obs_command("ls", ["obs://mybucket"], "la-north-2")
        assert "obs ls obs://mybucket --cli-region=la-north-2" == cmd


class TestCollectAllTools:
    def test_collects_tools(self):
        tools = collect_all_tools()
        assert len(tools) > 30
        names = [t.name for t in tools]
        assert "hcloud_list_servers" in names
        assert "hcloud_list_vpcs" in names
        assert "hcloud_list_images" in names
        assert "hcloud_list_nat_gateways" in names
        assert "hcloud_list_dcs_instances" in names
        assert "hcloud_list_dds_instances" in names
        assert "hcloud_list_smn_topics" in names
        assert "hcloud_obs_ls" in names

    def test_no_destructive_structured_tools(self):
        tools = collect_all_tools()
        for t in tools:
            assert not hasattr(t, "is_destructive") or not t.is_destructive

    def test_all_tools_have_valid_names(self):
        tools = collect_all_tools()
        for t in tools:
            assert t.name.startswith("hcloud_"), f"Tool {t.name} doesn't start with hcloud_"
            assert t.description, f"Tool {t.name} has no description"

    def test_all_tools_convert_to_mcp(self):
        tools = collect_all_tools()
        for t in tools:
            mcp_tool = t.to_mcp_tool()
            assert mcp_tool.name == t.name
            assert mcp_tool.inputSchema["type"] == "object"

    def test_region_always_maps_to_cli_region(self):
        tools = collect_all_tools()
        for t in tools:
            if "region" in t.params:
                cmd = t.build({"region": "test-region", **{k: "val" for k in t.required if k != "region"}})
                assert "--cli-region=test-region" in cmd, f"Tool {t.name}: region should map to --cli-region"


class TestToolDefinition:
    def test_to_mcp_tool(self):
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            params={"region": {"type": "string", "description": "Region"}},
            required=["region"],
            build_command=lambda p: f"test {p['region']}",
        )
        mcp = tool.to_mcp_tool()
        assert mcp.name == "test_tool"
        assert "region" in mcp.inputSchema["properties"]
        assert mcp.inputSchema["required"] == ["region"]

    def test_enum_in_params(self):
        tool = ToolDefinition(
            name="test_enum",
            description="Test with enum",
            params={"status": {"type": "string", "description": "Status", "enum": ["ACTIVE", "ERROR"]}},
            required=["status"],
            build_command=lambda p: f"test {p['status']}",
        )
        mcp = tool.to_mcp_tool()
        assert mcp.inputSchema["properties"]["status"]["enum"] == ["ACTIVE", "ERROR"]
