import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseCustomerDocsTests(unittest.TestCase):
    def test_customer_start_path_and_support_boundary_are_documented(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        environment = (ROOT / "docs/release-environment.md").read_text(encoding="utf-8")
        self.assertIn("scripts/install-autoops.sh", readme)
        self.assertIn("Jiuwen_autoops_tui", readme)
        self.assertIn("支持矩阵", environment)
        self.assertIn("未声明支持", environment)
        self.assertIn("systemd-journal", environment)

    def test_operations_manual_preserves_unknown_external_execution(self):
        operations = (ROOT / "docs/release-operations.md").read_text(encoding="utf-8")
        self.assertIn("external_actions_replayed=false", operations)
        self.assertIn("RECONCILING", operations)
        self.assertIn("不能重新提交", operations)
        self.assertIn("清理失败", operations)

    def test_release_notes_do_not_claim_a_release(self):
        notes = (ROOT / "docs/release-notes.md").read_text(encoding="utf-8")
        decision = (ROOT / "docs/release-decision.md").read_text(encoding="utf-8")
        self.assertIn("candidate-unverified", notes)
        self.assertIn("NO_GO", notes)
        self.assertIn("NO_GO", decision)
        self.assertIn("tag_created", decision)


if __name__ == "__main__":
    unittest.main()
