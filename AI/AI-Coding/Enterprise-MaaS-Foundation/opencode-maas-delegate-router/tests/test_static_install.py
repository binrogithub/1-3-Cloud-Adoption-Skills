import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenCodeInstallStaticTests(unittest.TestCase):
    def test_install_targets_opencode_json_global_config(self):
        install = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
        verify = (ROOT / "scripts" / "verify-setup.ps1").read_text(encoding="utf-8")

        self.assertIn("'opencode.json'", install)
        self.assertIn("'opencode.json'", verify)
        self.assertNotIn("'opencode.jsonc'", install)
        self.assertNotIn("'opencode.jsonc'", verify)

    def test_install_copies_skills_from_existing_sources(self):
        install = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")

        expected_sources = [
            "SKILL.md",
            "assets\\skills\\glm-review\\SKILL.md",
            "assets\\skills\\glm-repo-summary\\SKILL.md",
            "assets\\skills\\glm-test-batch\\SKILL.md",
        ]
        for rel in expected_sources:
            self.assertIn(rel, install)

        self.assertNotIn(".opencode\\skills", install)

    def test_skill_names_match_install_destinations(self):
        skill_files = {
            "maas-delegate-router": ROOT / "SKILL.md",
            "glm-review": ROOT / "assets" / "skills" / "glm-review" / "SKILL.md",
            "glm-repo-summary": ROOT
            / "assets"
            / "skills"
            / "glm-repo-summary"
            / "SKILL.md",
            "glm-test-batch": ROOT / "assets" / "skills" / "glm-test-batch" / "SKILL.md",
        }
        for expected_name, path in skill_files.items():
            text = path.read_text(encoding="utf-8")
            match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
            self.assertIsNotNone(match, f"{path} missing skill name")
            self.assertEqual(match.group(1), expected_name)

    def test_policies_match_prd_routing_contract(self):
        policy_files = [
            ROOT / "SKILL.md",
            ROOT / "assets" / "orchestrator-policy.md",
            ROOT / "reference" / "AGENTS.md",
        ]
        required_execution = [
            "CI fixes",
            "format",
            "migration transforms",
            "low/medium-risk",
        ]
        required_premium = [">128K raw context"]
        required_escalation = [
            "attempt 1",
            "attempt 2",
            "never re-delegated",
            "Workflow remainder >30%",
        ]

        for path in policy_files:
            text = path.read_text(encoding="utf-8")
            for phrase in required_execution + required_premium + required_escalation:
                self.assertIn(phrase, text, f"{path} missing {phrase!r}")
            self.assertNotIn('subagent_type="general"', text)
            self.assertIn("ds-executor", text)
            self.assertIn("ds-reviewer", text)


if __name__ == "__main__":
    unittest.main()
