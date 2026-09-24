import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts" / "install-jiuwenswarm-autoops-skills.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("autoops_skill_installer", INSTALLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AutoOpsSkillRoutingTests(unittest.TestCase):
    def test_project_manager_skill_declares_kubernetes_route(self):
        skill = (ROOT / "skills/autoops-project-manager/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("E03 Kubernetes", skill)
        self.assertIn("--cluster", skill)
        self.assertIn("--workload", skill)
        self.assertIn("postcondition", skill)

    def test_project_manager_skill_routes_complex_observability_to_native_workflow(self):
        skill = (ROOT / "skills/autoops-project-manager/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("ro05-parallel-observability-v1.py", skill)
        self.assertIn("log-investigator", skill)
        self.assertIn("metrics-observer", skill)
        self.assertIn("event-investigator", skill)
        self.assertIn("Do not call `autoops-project-manager.py` or an observability adapter before or", skill)
        self.assertIn("This rule takes precedence over the", skill)
        self.assertIn("PARTIAL E05 result may still contain anomaly lines", skill)

    def test_bootstrap_declares_kubernetes_project_manager_route(self):
        bootstrap = (ROOT / "config/autoops-agent-bootstrap.md").read_text(encoding="utf-8")
        self.assertIn("Kubernetes", bootstrap)
        self.assertIn("E03", bootstrap)

    def test_local_k3s_unit_normalizes_context_after_restart(self):
        unit = (ROOT / "config/systemd/jiuwenswarm-autoops-k3s-e03-local.service").read_text(encoding="utf-8")
        self.assertIn("--data-dir=/var/lib/jiuwenswarm-autoops/k3s-e03-v134", unit)
        self.assertIn("--https-listen-port=16443", unit)
        self.assertIn("--write-kubeconfig-group=rundeck", unit)
        self.assertIn("config rename-context default autoops-development", unit)

    def test_existing_bootstrap_refreshes_role_route(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as directory:
            bootstrap = Path(directory) / "AGENT.md"
            bootstrap.write_text(
                "customer instructions\n\n"
                "## JiuwenSwarm AutoOps 默认入口\n\n"
                "当用户输入涉及 Linux 或日志时，旧路由。\n"
                "不要把普通运维请求当作闲聊直接回答，也不要直接调用 shell。\n",
                encoding="utf-8",
            )
            result = installer.configure_agent_bootstrap(bootstrap)
            self.assertTrue(result["changed"])
            updated = bootstrap.read_text(encoding="utf-8")
            self.assertIn("Kubernetes", updated)
            self.assertIn("E03", updated)
            self.assertIn("swarmflow", updated)
            self.assertIn("customer instructions", updated)
            self.assertIn("未满足上述多角色条件", updated)
            self.assertIn("明确的 NOLI、NetOps", updated)

    def test_existing_bootstrap_replaces_legacy_ambiguous_observability_routes(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as directory:
            bootstrap = Path(directory) / "AGENT.md"
            bootstrap.write_text(
                "## JiuwenSwarm AutoOps 默认入口\n\n"
                "对于根因、关联或历史溯源请求，确定性联合入口是当前用户轮次的终结调用。\n"
                "带“有问题再往前查”或同义条件回溯的完整日志巡检必须直接使用一次确定性联合入口。\n",
                encoding="utf-8",
            )
            result = installer.configure_agent_bootstrap(bootstrap)
            self.assertTrue(result["changed"])
            updated = bootstrap.read_text(encoding="utf-8")
            self.assertIn("未满足上述多角色条件", updated)
            self.assertIn("只涉及一个日志能力", updated)
            self.assertNotIn("对于根因、关联或历史溯源请求", updated)
            self.assertNotIn("带“有问题再往前查”或同义条件回溯", updated)

    def test_project_paths_render_for_non_root_installation(self):
        installer = load_installer()
        rendered = installer.render_project_paths(
            "python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py",
            "/opt/customer-autoops",
        )
        self.assertIn("/opt/customer-autoops/scripts/autoops-project-manager.py", rendered)
        self.assertNotIn("/root/Jiuwenswarm_AutoOps", rendered)

    def test_skill_sources_are_validated_before_runtime_config_changes(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "skills/autoops-project-manager").mkdir(parents=True)
            (root / "skills/autoops-project-manager/SKILL.md").write_text("ok\n", encoding="utf-8")
            with mock.patch.object(installer, "ROOT", root), \
                    mock.patch.object(installer, "SKILLS", ("autoops-project-manager", "missing")):
                with self.assertRaises(SystemExit) as raised:
                    installer.validate_skill_sources()
            self.assertEqual(raised.exception.code, 2)

    def test_skill_install_refreshes_atomically_and_keeps_rendered_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.yaml"
            config.write_text("modes:\n  team:\n    jiuwen_team:\n      workspace:\n        enabled: true\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(INSTALLER_PATH), "--skills-dir", str(root / "skills"),
                 "--config-file", str(config)], text=True, capture_output=True, check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY")
            skill = root / "skills/autoops-project-manager/SKILL.md"
            self.assertTrue(skill.is_file())
            self.assertIn(str(ROOT), skill.read_text(encoding="utf-8"))
            self.assertTrue((root / "skills/autoops-netops/SKILL.md").is_file())
            self.assertFalse(list((root / "skills").glob("*.autoops-*")))


if __name__ == "__main__":
    unittest.main()
