import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import koo_cli  # noqa: E402


class Completed:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class KooCliTests(unittest.TestCase):
    def profile(self):
        return {
            "api_adapter": "koo-cli",
            "koo_cli_path": "/usr/local/bin/hcloud",
            "koo_cli_profile": "default",
            "region": "la-south-2",
            "project_id": "project-test",
            "domain_id": "domain-test",
            "cluster_id": "57913cbd-01cc-49b6-b8d0-f3914b35659a",
        }

    def test_cluster_read_uses_hcloud_without_credentials(self):
        response = json.dumps({
            "id": "57913cbd-01cc-49b6-b8d0-f3914b35659a",
            "status": "200",
            "instances": [
                {"id": "node-1", "type": "ess", "status": "200", "availability_zone": "az1"},
                {"id": "node-2", "type": "ess", "status": "200", "availability_zone": "az2"},
            ],
        })
        with patch.object(koo_cli.subprocess, "run", return_value=Completed(response)) as run:
            snapshot = koo_cli.cluster_snapshot(self.profile())
        command = run.call_args.args[0]
        self.assertEqual(snapshot["data_node_count"], 2)
        self.assertEqual(snapshot["api_adapter"], "koo-cli")
        self.assertIn("CSS", command)
        self.assertIn("ShowClusterDetail", command)
        self.assertIn("--cluster_id=57913cbd-01cc-49b6-b8d0-f3914b35659a", command)
        self.assertIn("--cli-domain-id=domain-test", command)
        self.assertIn("--cli-mode=AKSK", command)
        self.assertNotIn("--cli-access-key", " ".join(command))
        self.assertNotIn("--cli-secret-key", " ".join(command))

    def test_metric_and_scale_commands_use_documented_operations(self):
        metric_response = json.dumps({"datapoints": [{"timestamp": 2, "average": 83}]})
        scale_response = json.dumps({"request_id": "request-1"})
        with patch.object(
            koo_cli.subprocess, "run",
            side_effect=[Completed(metric_response), Completed(scale_response)],
        ) as run:
            value = koo_cli.metric(self.profile(), "max_cpu_usage", now_ms=1_000_000)
            response = koo_cli.scale_cluster(self.profile(), "scale_out", 1)
        self.assertEqual(value, 83)
        self.assertEqual(koo_cli.request_id(response), "request-1")
        metric_command = run.call_args_list[0].args[0]
        scale_command = run.call_args_list[1].args[0]
        self.assertIn("CES", metric_command)
        self.assertIn("ShowMetricData", metric_command)
        self.assertIn("--dim.0=cluster_id,57913cbd-01cc-49b6-b8d0-f3914b35659a", metric_command)
        self.assertIn("UpdateExtendInstanceStorage", scale_command)
        self.assertIn("--grow.1.type=ess", scale_command)
        self.assertIn("--grow.1.nodesize=1", scale_command)

    def test_role_worker_can_pin_koo_cli_home_without_exposing_credentials(self):
        response = json.dumps({"id": "cluster-1", "status": "200", "instances": []})
        profile = self.profile() | {"koo_cli_home": "/root"}
        with patch.object(koo_cli.subprocess, "run", return_value=Completed(response)) as run:
            koo_cli.cluster_snapshot(profile)
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/root")
        self.assertNotIn("AK", run.call_args.kwargs["env"])
        self.assertNotIn("SK", run.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
