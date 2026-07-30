import pytest
from src.tools.registry import collect_all_tools
from src.config import ExecutionConfig
from src.executor import execute_command

REGION = "la-north-2"
SENTINEL_ID = "00000000-0000-0000-0000-000000000000"

KNOWN_VPC_ID = "ca5aa4ea-4df9-4a7f-b359-c85045147f32"
KNOWN_SUBNET_ID = "701ac87c-47ea-4b12-b112-d05ddecffa81"
KNOWN_SG_ID = "7d730547-c294-4484-9dde-0709625c3a24"

CONFIG = ExecutionConfig(timeout_seconds=30)

TOOL_TEST_CASES = {
    "hcloud_list_servers": {"region": REGION, "limit": 1},
    "hcloud_show_server": {"region": REGION, "server_id": SENTINEL_ID},
    "hcloud_list_flavors": {"region": REGION},
    "hcloud_list_availability_zones": {"region": REGION},
    "hcloud_list_server_interfaces": {"region": REGION, "server_id": SENTINEL_ID},
    "hcloud_list_server_block_devices": {"region": REGION, "server_id": SENTINEL_ID},
    "hcloud_list_keypairs": {"region": REGION},
    "hcloud_show_server_limits": {"region": REGION},

    "hcloud_list_vpcs": {"region": REGION, "limit": 1},
    "hcloud_show_vpc": {"region": REGION, "vpc_id": KNOWN_VPC_ID},
    "hcloud_list_subnets": {"region": REGION, "limit": 1},
    "hcloud_show_subnet": {"region": REGION, "subnet_id": KNOWN_SUBNET_ID},
    "hcloud_list_security_groups": {"region": REGION, "limit": 1},
    "hcloud_show_security_group": {"region": REGION, "security_group_id": KNOWN_SG_ID},
    "hcloud_list_security_group_rules": {"region": REGION, "security_group_id": KNOWN_SG_ID, "limit": 1},
    "hcloud_list_route_tables": {"region": REGION, "limit": 1},
    "hcloud_show_quota": {"region": REGION},

    "hcloud_list_public_ips": {"region": REGION, "limit": 1},
    "hcloud_show_public_ip": {"region": REGION, "publicip_id": SENTINEL_ID},
    "hcloud_list_bandwidths": {"region": REGION, "limit": 1},
    "hcloud_list_eip_quotas": {"region": REGION},

    "hcloud_list_volumes": {"region": REGION, "limit": 1},
    "hcloud_show_volume": {"region": REGION, "volume_id": SENTINEL_ID},
    "hcloud_list_snapshots": {"region": REGION, "limit": 1},
    "hcloud_show_snapshot": {"region": REGION, "snapshot_id": SENTINEL_ID},
    "hcloud_list_volume_types": {"region": REGION},

    "hcloud_list_users": {"limit": 1},
    "hcloud_show_user": {"user_id": SENTINEL_ID},
    "hcloud_list_groups": {"limit": 1},
    "hcloud_list_policies": {"limit": 1},
    "hcloud_list_user_policies": {"user_id": SENTINEL_ID},
    "hcloud_list_agencies": {},
    "hcloud_list_projects": {},
    "hcloud_list_domains": {},

    "hcloud_list_load_balancers": {"region": REGION, "limit": 1},
    "hcloud_show_load_balancer": {"region": REGION, "loadbalancer_id": SENTINEL_ID},
    "hcloud_show_load_balancer_topology": {"region": REGION, "loadbalancer_id": SENTINEL_ID},
    "hcloud_list_listeners": {"region": REGION, "limit": 1},
    "hcloud_list_pools": {"region": REGION, "limit": 1},
    "hcloud_list_members": {"region": REGION, "pool_id": SENTINEL_ID, "limit": 1},
    "hcloud_list_health_monitors": {"region": REGION, "limit": 1},
    "hcloud_list_l7_policies": {"region": REGION, "limit": 1},
    "hcloud_list_elb_flavors": {"region": REGION},

    "hcloud_list_rds_instances": {"region": REGION, "limit": 1},
    "hcloud_list_rds_flavors": {"region": REGION, "database_name": "MySQL"},
    "hcloud_list_rds_storage_types": {"region": REGION, "database_name": "MySQL", "version_name": "5.7"},
    "hcloud_list_rds_datastores": {"region": REGION, "database_name": "MySQL"},
    "hcloud_list_rds_backups": {"region": REGION, "instance_id": SENTINEL_ID, "limit": 1},

    "hcloud_list_cce_clusters": {"region": REGION},
    "hcloud_show_cce_cluster": {"region": REGION, "cluster_id": SENTINEL_ID},
    "hcloud_list_cce_nodes": {"region": REGION, "cluster_id": SENTINEL_ID},
    "hcloud_list_node_pools": {"region": REGION, "cluster_id": SENTINEL_ID},
    "hcloud_show_node_pool": {"region": REGION, "cluster_id": SENTINEL_ID, "nodepool_id": SENTINEL_ID},
    "hcloud_list_addon_instances": {"region": REGION, "cluster_id": SENTINEL_ID},

    "hcloud_list_scaling_groups": {"region": REGION, "limit": 1},
    "hcloud_show_scaling_group": {"region": REGION, "scaling_group_id": SENTINEL_ID},
    "hcloud_list_scaling_configs": {"region": REGION, "limit": 1},
    "hcloud_show_scaling_config": {"region": REGION, "scaling_configuration_id": SENTINEL_ID},
    "hcloud_list_scaling_policies": {"region": REGION, "scaling_group_id": SENTINEL_ID, "limit": 1},
    "hcloud_show_scaling_policy": {"region": REGION, "scaling_policy_id": SENTINEL_ID},
    "hcloud_list_scaling_instances": {"region": REGION, "scaling_group_id": SENTINEL_ID},

    "hcloud_list_dns_zones": {"region": REGION, "limit": 1},
    "hcloud_show_dns_zone": {"region": REGION, "zone_id": "00000000000000000000000000000000"},
    "hcloud_list_dns_recordsets": {"region": REGION, "zone_id": "00000000000000000000000000000000", "limit": 1},

    "hcloud_list_kms_keys": {"region": REGION, "limit": 1},
    "hcloud_list_kms_key_detail": {"region": REGION, "key_id": SENTINEL_ID},

    "hcloud_list_alarms": {"region": REGION, "limit": 1},
    "hcloud_list_alarm_rules": {"region": REGION, "limit": 1},
    "hcloud_list_metrics": {"region": REGION, "limit": 1},
    "hcloud_show_metric_data": {"region": REGION, "namespace": "SYS.ECS", "metric_name": "cpu_util", "dim_0": f"instance_id,{SENTINEL_ID}", "filter": "average", "period": 300, "from_": 1700000000000, "to": 1700003000000},

    "hcloud_list_images": {"region": REGION, "imagetype": "gold", "os_type": "Linux", "limit": 1},
    "hcloud_show_image": {"region": REGION, "image_id": SENTINEL_ID},
    "hcloud_list_os_versions": {"region": REGION},
    "hcloud_show_image_quotas": {"region": REGION},

    "hcloud_list_nat_gateways": {"region": REGION, "limit": 1},
    "hcloud_show_nat_gateway": {"region": REGION, "nat_gateway_id": SENTINEL_ID},
    "hcloud_list_nat_gateway_snat_rules": {"region": REGION, "limit": 1},
    "hcloud_list_nat_gateway_dnat_rules": {"region": REGION, "limit": 1},

    "hcloud_list_dcs_instances": {"region": REGION, "limit": 1},
    "hcloud_show_dcs_instance": {"region": REGION, "instance_id": SENTINEL_ID},
    "hcloud_list_dcs_flavors": {"region": REGION},
    "hcloud_list_dcs_available_zones": {"region": REGION},

    "hcloud_list_dds_instances": {"region": REGION, "limit": 1},
    "hcloud_list_dds_flavors": {"region": REGION},
    "hcloud_list_dds_storage_types": {"region": REGION},

    "hcloud_list_smn_topics": {"region": REGION, "limit": 1},
    "hcloud_list_smn_subscriptions": {"region": REGION, "limit": 1},

    "hcloud_obs_ls": {"region": REGION},
    "hcloud_obs_stat": {"region": REGION, "bucket": "nonexistent-bucket-test"},
    "hcloud_obs_cat": {"region": REGION, "bucket": "nonexistent-bucket-test", "key": "test"},
}


def _get_tool_map():
    return {t.name: t for t in collect_all_tools()}


@pytest.mark.parametrize("tool_name", sorted(TOOL_TEST_CASES.keys()))
def test_tool_executes(tool_name):
    tool_map = _get_tool_map()
    tool = tool_map[tool_name]
    args = TOOL_TEST_CASES[tool_name]
    command = tool.build(args)

    stdout, stderr, returncode = execute_command(command, CONFIG)

    combined = stdout + stderr
    assert "USE_ERROR" not in combined, f"USE_ERROR for {tool_name}: command={command}\n{combined}"
    assert returncode != -1, f"Command failed to execute for {tool_name}: command={command}\n{stderr}"


def test_all_tools_have_test_cases():
    tool_map = _get_tool_map()
    tested = set(TOOL_TEST_CASES.keys())
    all_tools = set(tool_map.keys())
    missing = all_tools - tested
    assert not missing, f"Tools missing test cases: {sorted(missing)}"
