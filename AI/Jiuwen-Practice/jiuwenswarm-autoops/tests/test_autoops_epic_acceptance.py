import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "autoops_epic_acceptance", ROOT / "scripts" / "autoops-epic-acceptance.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
NATIVE_SPEC = importlib.util.spec_from_file_location(
    "autoops_native_evidence", ROOT / "scripts" / "autoops-native-evidence.py"
)
NATIVE = importlib.util.module_from_spec(NATIVE_SPEC)
assert NATIVE_SPEC.loader is not None
NATIVE_SPEC.loader.exec_module(NATIVE)
PERF_SPEC = importlib.util.spec_from_file_location(
    "autoops_native_performance", ROOT / "scripts" / "autoops-native-performance.py"
)
PERF = importlib.util.module_from_spec(PERF_SPEC)
assert PERF_SPEC.loader is not None
PERF_SPEC.loader.exec_module(PERF)


class AutoOpsEpicAcceptanceTests(unittest.TestCase):
    def test_ro00_compatibility_matrix_has_project_entrypoints_and_runtime_gap(self):
        matrix = json.loads((ROOT / "config" / "ro00-compatibility-matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["schema_version"], 1)
        self.assertIn("native_workflow", matrix["integration_entrypoints"])
        contracts = {item["capability"]: item for item in matrix["contracts"]}
        self.assertEqual(contracts["native_workflow"]["status"], "supported")
        self.assertEqual(contracts["tui_history_activity"]["status"], "runtime_gap")

    def test_native_e03_workflow_uses_only_project_route(self):
        source = (ROOT / "swarmflow" / "e03-kubernetes-validation-v1.py").read_text()
        self.assertIn("autoops-project-manager.py", source)
        self.assertIn("Make exactly one tool call", source)
        self.assertIn('"--cluster"', source)
        self.assertIn('"--workload"', source)
        self.assertIn("Do not read any Skill", source)

    def test_native_evidence_requires_structured_workflow_tool_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text("\n".join(json.dumps(item) for item in [
                {"type": "event", "payload": {"event_type": "workflow.updated", "workflow": {"id": "run-1", "phases": [{
                    "name": "inspect", "agents": [{"id": "agent-1", "name": "log-investigator",
                    "status": "completed", "activity": [{"type": "tool_result", "tool_name": "logs.query.v2",
                    "tool_result_preview": "status=ok"}]}]}, {"name": "metrics", "agents": [
                    {"id": "agent-2", "name": "metrics-observer", "status": "completed", "activity": [
                    {"type": "tool_result", "tool_name": "metrics.query.v1", "tool_result_preview": "status=ok"}]}]}]}}},
            ]) + "\n", encoding="utf-8")
            payload = NATIVE.collect(history)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["qualified_expert_count"], 2)
        self.assertEqual(payload["workflow_run_ids"], ["run-1"])
        self.assertEqual(len(payload["observed_experts"]), 2)
        self.assertEqual(payload["structured_expert_result_count"], 0)

    def test_native_evidence_records_structured_outcome_without_promoting_it_to_tool_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text(json.dumps({"type": "event", "payload": {
                "event_type": "workflow.updated", "workflow": {"id": "run-2", "phases": [{
                    "name": "inspect", "agents": [{"id": "agent-1", "name": "runbook-operator",
                    "status": "completed", "activity": [],
                    "outcome": json.dumps({"task_id": "RO-00", "execution_status": "completed"})}]
                }]}
            }}) + "\n", encoding="utf-8")
            payload = NATIVE.collect(history)
        self.assertEqual(payload["status"], "INCONCLUSIVE")
        self.assertEqual(payload["qualified_expert_count"], 0)
        self.assertEqual(payload["structured_expert_result_count"], 1)
        expert = payload["observed_experts"][0]
        self.assertEqual(expert["structured_result_status"], "present")
        self.assertTrue(expert["structured_result_digest"])

    def test_native_evidence_can_join_matching_runtime_trace_tool_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text(json.dumps({"payload": {"workflow": {"id": "wf_abc123", "phases": [{
                "name": "inspect", "agents": [{"id": "runbook-operator-1", "name": "runbook-operator",
                "status": "completed", "activity": [], "outcome": {"status": "completed"}}]},
                {"name": "diagnose", "agents": [{"id": "log-investigator-1", "name": "log-investigator",
                "status": "completed", "activity": [], "outcome": {"status": "completed"}}]}]}}}) + "\n",
                encoding="utf-8")
            trace = Path(directory) / "trace.jsonl"
            spans = []
            for name, role in (("bash", "runbook-operator"), ("loki_query", "log-investigator")):
                spans.append({"name": f"tool.{name}", "attributes": [
                    {"key": "gen_ai.tool.name", "value": {"stringValue": name}},
                    {"key": "gen_ai.tool.id", "value": {"stringValue": f"{name}_team_wf-abc123-{role}-1"}},
                    {"key": "gen_ai.tool.output", "value": {"stringValue": "sha256:receipt"}},
                ]})
            trace.write_text(json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}) + "\n",
                              encoding="utf-8")
            payload = NATIVE.collect(history, trace)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["trace_tool_event_count"], 2)
        self.assertEqual(payload["qualified_expert_count"], 2)

    def test_native_evidence_recovers_background_workflow_from_otel_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "session-x" / "history.jsonl"
            history.parent.mkdir()
            history.write_text(json.dumps({"role": "user", "content": "#autoops-project-manager diagnose"}) + "\n", encoding="utf-8")
            trace = Path(directory) / "trace.jsonl"
            def attrs(values):
                return [{"key": key, "value": {"stringValue": value}} for key, value in values.items()]
            progress = []
            for kind, label, child, outcome in (
                ("agent_started", "log-investigator", "wf-abc-log-investigator-0", None),
                ("agent_completed", "log-investigator", "wf-abc-log-investigator-0", {"status": "PARTIAL"}),
                ("agent_started", "metrics-observer", "wf-abc-metrics-observer-1", None),
                ("agent_completed", "metrics-observer", "wf-abc-metrics-observer-1", {"status": "PARTIAL"}),
            ):
                observation = {"workflow_name": "ro05-parallel-observability-v1", "run_id": "wf_abc",
                               "kind": kind, "label": label, "phase": "parallel_evidence", "outcome": outcome}
                progress.append({"name": "event.workflow.progress", "attributes": attrs({
                    "agentteam.session.id": "session-x", "agentteam.team.name": "team_session-x",
                    "agentteam.agent.id": child,
                    "langfuse.observation.input": json.dumps(observation),
                })})
            tools = []
            for label in ("log-investigator", "metrics-observer"):
                tools.append({"name": "tool.bash", "attributes": attrs({
                    "session.id": "session-x", "gen_ai.tool.name": "bash",
                    "gen_ai.tool.id": f"bash_team_wf-abc-{label}-0",
                    "gen_ai.tool.output": "sha256:receipt",
                })})
            trace.write_text(json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": progress + tools}]}]}) + "\n", encoding="utf-8")
            payload = NATIVE.collect(history, trace)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["qualified_expert_count"], 2)

    def test_native_performance_joins_history_and_trace_without_copying_content(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text("\n".join(json.dumps({"payload": item}) for item in [
                {"event_type": "chat.llm_usage", "session_id": "s1", "total_latency_ms": 1200,
                 "ttft_ms": 300, "usage_metadata": {}},
                {"event_type": "chat.llm_usage", "session_id": "s1", "total_latency_ms": 800,
                 "ttft_ms": 250, "usage_metadata": {}},
            ]) + "\n", encoding="utf-8")
            trace = Path(directory) / "trace.jsonl"
            spans = []
            for name, start, end in (("bash", 1_000_000_000, 1_500_000_000),
                                     ("structured_output", 2_000_000_000, 2_100_000_000)):
                spans.append({"name": f"tool.{name}", "startTimeUnixNano": str(start),
                              "endTimeUnixNano": str(end), "attributes": [
                    {"key": "session.id", "value": {"stringValue": "s1"}},
                    {"key": "gen_ai.tool.name", "value": {"stringValue": name}},
                    {"key": "gen_ai.tool.id", "value": {"stringValue": f"{name}_wf-abc123-runbook-operator-1"}},
                    {"key": "gen_ai.tool.output", "value": {"stringValue": "sha256:receipt"}},
                ]})
            trace.write_text(json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}) + "\n",
                              encoding="utf-8")
            payload = PERF.collect(history, trace, "RO-00", "wf_abc123")
        self.assertEqual(payload["acceptance_scope"], "RO-14-04")
        self.assertEqual(payload["model_seconds"], 2.0)
        self.assertEqual(payload["query_count"], 1)
        self.assertEqual(payload["first_ack_seconds"], 0.25)
        self.assertEqual(payload["quiet_gap_seconds"], 0.5)

    def test_native_performance_uses_tui_timestamp_fallback(self):
        payload = [
            {"role": "user", "timestamp": 100.0},
            {"event_type": "chat.final", "role": "assistant", "timestamp": 101.0, "content": "ack"},
            {"event_type": "chat.tool_call", "role": "assistant", "timestamp": 102.0,
             "tool_call": {"name": "bash"}},
            {"event_type": "chat.tool_result", "role": "assistant", "timestamp": 104.0},
            {"event_type": "chat.final", "role": "assistant", "timestamp": 110.0, "content": "done"},
        ]
        result = PERF._collect_from_history(payload, "RO-00", "run-1", "session-1")
        self.assertEqual(result["evidence_level"], "real-tui")
        self.assertEqual(result["model_seconds"], 8.0)
        self.assertEqual(result["tool_seconds"], 2.0)
        self.assertEqual(result["query_count"], 1)
        self.assertEqual(result["first_ack_seconds"], 1.0)

    def test_native_performance_cli_allows_history_only_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text("\n".join(json.dumps({"payload": item}) for item in [
                {"role": "user", "timestamp": 100.0, "session_id": "s1"},
                {"role": "assistant", "event_type": "chat.final", "timestamp": 101.0,
                 "content": "ack", "session_id": "s1"},
            ]) + "\n", encoding="utf-8")
            output = Path(directory) / "measurement.json"
            result = PERF.main([
                str(history), "--scenario-id", "RO-11-01", "--run-id", "run-1",
                "--output", str(output),
            ])
            self.assertEqual(result, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["evidence_level"], "real-tui")
            self.assertEqual(payload["first_ack_seconds"], 1.0)

    def test_fixed_route_suite_has_56_cases_and_passes(self):
        result = MODULE.route_acceptance(ROOT / "config/acceptance/route-cases-v1.json")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["details"]["count"], 56)

    def test_missing_runtime_evidence_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            report = MODULE.build_report(
                ROOT / "config/acceptance/route-cases-v1.json", Path(directory), ROOT
            )
        self.assertEqual(report["overall"], "INCOMPLETE")
        self.assertEqual(report["checks"]["RO-14-02-real-tui"]["status"], "BLOCKED")
        self.assertEqual(report["checks"]["RO-14-03-native-experts"]["status"], "BLOCKED")
        self.assertEqual(report["checks"]["RO-14-04-performance"]["status"], "BLOCKED")

    def test_fixture_with_all_runtime_evidence_can_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            rows = [{"acceptance_scope": "RO-14-02", "evidence_level": "real-tui",
                     "scenario_id": f"S{index:02d}", "run_id": f"run-{index:02d}", "result": "PASS"}
                    for index in range(36)]
            (evidence / "tui.json").write_text(json.dumps({"scenarios": rows}), encoding="utf-8")
            (evidence / "native.json").write_text(json.dumps({"native_expert_events": [
                {"expert_role": "log-investigator", "parent_run_id": "p", "child_run_id": "c1", "tool_result": "ok"},
                {"expert_role": "metrics-observer", "parent_run_id": "p", "child_run_id": "c2", "tool_result": "ok"},
            ]}), encoding="utf-8")
            measurements = [{"acceptance_scope": "RO-14-04", "evidence_level": "real-tui",
                             "scenario_id": f"S{index:02d}", "run_id": f"run-{index:02d}",
                             "model_seconds": 1, "tool_seconds": 2, "query_count": 3,
                             "first_ack_seconds": 1, "quiet_gap_seconds": 4} for index in range(36)]
            (evidence / "metrics.json").write_text(json.dumps({"measurements": measurements}), encoding="utf-8")
            report = MODULE.build_report(ROOT / "config/acceptance/route-cases-v1.json", evidence, ROOT)
        self.assertEqual(report["overall"], "PASS", report)


if __name__ == "__main__":
    unittest.main()
