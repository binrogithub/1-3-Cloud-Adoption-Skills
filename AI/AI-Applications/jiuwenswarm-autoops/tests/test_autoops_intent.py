import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from autoops_intent import is_host_system_request, parse_request, parse_time_window


class AutoOpsIntentTests(unittest.TestCase):
    def test_linux_system_request_is_host_scope(self):
        result = parse_request("运维 Linux 系统日志")
        self.assertEqual(result["scope"]["kind"], "host_system")
        self.assertEqual(result["scope"]["target_ref"], "local")
        self.assertEqual(result["time"]["requested_minutes"], 1440)
        self.assertEqual(result["mode"], "read_only")

    def test_application_named_local_is_not_host_scope(self):
        self.assertFalse(is_host_system_request("查看 local 应用日志", application="local"))
        result = parse_request("查看 local 应用日志", application="local")
        self.assertEqual(result["scope"]["kind"], "application")

    def test_common_time_phrases_are_normalized(self):
        self.assertEqual(parse_time_window("检查最近一小时日志")["minutes"], 60)
        self.assertEqual(parse_time_window("检查过去 30 分钟日志")["minutes"], 30)
        self.assertEqual(parse_time_window("检查最近24小时日志")["minutes"], 1440)
        self.assertEqual(parse_time_window("检查日志", explicit_minutes=10)["minutes"], 10)

    def test_today_has_a_local_calendar_boundary(self):
        result = parse_time_window("检查今天的系统日志")
        self.assertEqual(result["expression"], "今天")
        self.assertIn("start", result)
        self.assertIn("end", result)
        self.assertTrue(result["start"].endswith("T00:00:00+08:00"))


if __name__ == "__main__":
    unittest.main()
