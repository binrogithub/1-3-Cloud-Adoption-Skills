import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from css_collector import SnapshotCache, collect_snapshot


class CssCollectorTests(unittest.TestCase):
    def test_cache_is_identity_scoped_and_fresh_bypasses_it(self):
        calls = {"topology": 0, "metrics": 0}
        def topology(profile, credentials):
            calls["topology"] += 1
            return {"cluster_healthy": True, "observed_at": str(calls["topology"])}
        def metrics(profile, credentials):
            calls["metrics"] += 1
            return {"max_cpu_usage": {"value": calls["metrics"], "observed_at": "x"}}
        cache = SnapshotCache(ttl_seconds=30)
        profile = {"cluster_id": "one", "project_id": "p", "region": "r"}
        collect_snapshot(profile, {}, topology, metrics, cache=cache)
        collect_snapshot(profile, {}, topology, metrics, cache=cache)
        collect_snapshot(profile, {}, topology, metrics, cache=cache, fresh=True)
        self.assertEqual(calls, {"topology": 2, "metrics": 2})
        self.assertEqual(cache.hits, 1)


if __name__ == "__main__":
    unittest.main()
