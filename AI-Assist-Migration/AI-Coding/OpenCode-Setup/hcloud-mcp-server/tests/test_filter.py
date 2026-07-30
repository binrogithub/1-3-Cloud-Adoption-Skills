from src.server import HCloudMCPServer
from src.config import ServerConfig


def _make_server():
    return HCloudMCPServer(ServerConfig())


class TestDeduplicateOperations:
    def test_slash_version_dedup(self):
        ops = ["ListVpcs/v2", "ListVpcs/v3", "CreateVpc", "DeleteVpc"]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert result == ["ListVpcs/v3", "CreateVpc", "DeleteVpc"]
        assert hidden == 1

    def test_no_versions(self):
        ops = ["CreateVpc", "DeleteVpc", "ListVpcs"]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert result == ops
        assert hidden == 0

    def test_multiple_versioned_groups(self):
        ops = [
            "ListVpcs/v2", "ListVpcs/v3",
            "CreateSecurityGroup/v2", "CreateSecurityGroup/v3",
            "ShowPort/v2", "ShowPort/v3",
            "AcceptVpcPeering",
        ]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert "ListVpcs/v3" in result
        assert "CreateSecurityGroup/v3" in result
        assert "ShowPort/v3" in result
        assert "AcceptVpcPeering" in result
        assert "ListVpcs/v2" not in result
        assert "CreateSecurityGroup/v2" not in result
        assert "ShowPort/v2" not in result
        assert hidden == 3

    def test_name_suffix_v5_dedup(self):
        ops = ["CreateAgency", "CreateAgencyV5", "ListUsers", "ListUsersV5"]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert "CreateAgencyV5" in result
        assert "ListUsersV5" in result
        assert "CreateAgency" not in result
        assert "ListUsers" not in result
        assert hidden == 2

    def test_v5_without_base_kept(self):
        ops = ["SomeOperationV5", "AnotherOp"]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert "SomeOperationV5" in result
        assert "AnotherOp" in result
        assert hidden == 0

    def test_preserves_order(self):
        ops = ["Alpha", "ListVpcs/v2", "ListVpcs/v3", "Beta", "ShowPort/v2", "ShowPort/v3", "Gamma"]
        result, hidden = HCloudMCPServer._deduplicate_operations(ops)
        assert result == ["Alpha", "ListVpcs/v3", "Beta", "ShowPort/v3", "Gamma"]
        assert hidden == 2


class TestFilterHelpVersions:
    def test_no_operations_section(self):
        output = "Some output\nwithout operations\n"
        assert _make_server()._filter_help_versions(output) == output

    def test_filters_operations_section(self):
        output = (
            "KooCLI Version 6.2.9\n\n"
            "Available Operations:\n"
            "  CreateVpc\n"
            "  ListVpcs/v2\n"
            "  ListVpcs/v3\n"
            "  DeleteVpc\n\n"
            "Run `hcloud VPC <operation> --help` for details.\n"
        )
        result = _make_server()._filter_help_versions(output)
        assert "ListVpcs/v3" in result
        assert "ListVpcs/v2" not in result
        assert "CreateVpc" in result
        assert "DeleteVpc" in result
        assert "1 older version(s) hidden" in result

    def test_no_filter_needed(self):
        output = (
            "Available Operations:\n"
            "  CreateVpc\n"
            "  DeleteVpc\n\n"
            "Run `hcloud VPC <operation> --help` for details.\n"
        )
        result = _make_server()._filter_help_versions(output)
        assert "older version" not in result
