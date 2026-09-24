import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from autoops_compensation import resolve_compensation


class AutoOpsCompensationTests(unittest.TestCase):
    def test_default_recovery_has_no_unpublished_rollback(self):
        result = resolve_compensation("host.ensure_service.v1")
        self.assertEqual(result["status"], "NOT_PUBLISHED")
        self.assertEqual(result["error_code"], "COMPENSATION_NOT_PUBLISHED")

    def test_published_compensation_requires_a_published_write_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            registry = path / "compensations.json"
            capabilities = path / "capabilities.json"
            registry.write_text(json.dumps({"compensations": [{
                "id": "rollback", "trigger_capability": "host.ensure_service.v1",
                "status": "PUBLISHED", "capability": "host.inspect.v1",
            }]}), encoding="utf-8")
            capabilities.write_text(json.dumps({"capabilities": {
                "host.inspect.v1": {"effect": "read"},
            }}), encoding="utf-8")
            result = resolve_compensation("host.ensure_service.v1",
                                         registry_path=registry, capability_path=capabilities)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["error_code"], "COMPENSATION_CAPABILITY_INVALID")

    def test_missing_registry_is_explicit(self):
        result = resolve_compensation("host.ensure_service.v1",
                                      registry_path=Path("/tmp/missing-autoops-compensations.json"))
        self.assertEqual(result["status"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
