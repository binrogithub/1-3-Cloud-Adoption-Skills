from conftest import load_fixture, route_model, run_guard
import sys


EXPECTED_GLM = "glm-5.2"
EXPECTED_PREMIUM = "opus-4.8"
EXPECTED_VISION = "vision-openrouter"


class _SemanticChoice:
    def __init__(self, name, similarity_score=0.91):
        self.name = name
        self.similarity_score = similarity_score


class _StubSemanticRouteLayer:
    def __init__(self, route_name):
        self.route_name = route_name

    def __call__(self, text):
        return _SemanticChoice(self.route_name)


def test_auto_unit_tests_low_risk_routes_to_glm(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["messages"][-1]["content"] = "Generate unit tests for this Java service."
    request_body["metadata"].update(
        {
            "task_type": "unit_test_generation",
            "repo_risk": "low",
            "context_tokens": 85000,
            "latency_slo": "batch",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["virtual_model"] == "coding-auto"
    assert audit["task_type"] == "unit_test_generation"
    assert audit["context_policy"] == "glm_direct"
    assert audit["route_reason"] == "smart_router_glm_execution"


def test_deep_virtual_model_routes_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "meli-coding-deep"
    request_body["metadata"]["task_type"] = "architecture_planning"

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    assert transformed["metadata"]["cc_glm52_guard"]["route_reason"] == "virtual_deep"


def test_review_high_risk_routes_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "meli-coding-review"
    request_body["metadata"].update(
        {
            "task_type": "pr_review",
            "repo_risk": "high",
            "repo_tags": ["payment", "pci"],
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["repo_risk"] == "high"
    assert audit["route_reason"] == "risk_based_review_premium"


def test_review_low_risk_routes_to_glm(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "meli-coding-review"
    request_body["metadata"].update(
        {
            "task_type": "pr_review",
            "repo_risk": "low",
            "repo_tags": ["docs"],
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    assert transformed["metadata"]["cc_glm52_guard"]["route_reason"] == "risk_based_review_glm"


def test_context_above_glm_limit_routes_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "repo_summary",
            "repo_risk": "low",
            "context_tokens": 250000,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["context_policy"] == "requires_rag_file_selection_summary_or_split"
    assert audit["route_reason"] == "context_above_glm_limit"


def test_near_budget_limit_prefers_glm_for_execution_task(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "code_generation",
            "repo_risk": "medium",
            "budget_state": "near_limit",
            "context_tokens": 60000,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    assert transformed["metadata"]["cc_glm52_guard"]["route_reason"] == "budget_prefers_glm"


def test_fallback_signal_routes_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "ci_auto_fix",
            "repo_risk": "low",
            "retry_count": 2,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["fallback_triggered"] is True
    assert audit["fallback_reason"] == "retry_count_gte_2"


def test_unsegmentable_context_after_glm_attempt_switches_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "repo_summary",
            "repo_risk": "low",
            "context_tokens": 180000,
            "context_unsegmentable": True,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["fallback_triggered"] is True
    assert audit["fallback_reason"] == "context_unsegmentable"
    assert audit["route_reason"] == "context_unsegmentable_to_premium"
    assert audit["context_handoff"]["required"] is True
    assert audit["context_handoff"]["canonical_context_replayed"] is False
    assert audit["context_handoff"]["warning"] == (
        "caller_must_replay_full_canonical_context_to_avoid_context_loss"
    )


def test_context_handoff_replay_injects_premium_model_instruction(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["system"] = "Follow enterprise coding policies."
    request_body["metadata"].update(
        {
            "task_type": "repo_summary",
            "repo_risk": "low",
            "context_tokens": 180000,
            "context_split_failed": True,
            "canonical_context_replayed": True,
            "previous_attempt_id": "glm-attempt-1",
            "attempt_id": "opus-attempt-2",
            "glm_attempt_summary": "GLM identified the checkout dependency graph but could not split payment flows safely.",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    handoff = audit["context_handoff"]
    assert handoff["required"] is True
    assert handoff["strategy"] == "replay_full_canonical_context"
    assert handoff["canonical_context_replayed"] is True
    assert handoff["handoff_summary_present"] is True
    assert handoff["warning"] is None
    assert audit["handoff_instruction_injected"] is True
    assert transformed["system"].startswith("[Context handoff]")
    assert "Previous GLM attempt summary" in transformed["system"]
    assert "Follow enterprise coding policies." in transformed["system"]


def test_image_input_routes_to_vision_even_from_auto(plugin_module):
    request_body = load_fixture("image_request.json")
    request_body["model"] = "coding-auto"

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_VISION
    assert transformed["metadata"]["cc_glm52_guard"]["task_type"] == "vision_task"


def test_commercial_telemetry_records_cost_tpm_latency_failure_and_acceptance(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "tool": "claude-code",
            "team": "marketplace",
            "project": "checkout",
            "repo": "payments-service",
            "language": "java",
            "cost_center": "marketplace-platform",
            "task_type": "unit_test_generation",
            "repo_risk": "medium",
            "context_tokens": 85000,
            "glm_reserved_tpm": 10000000,
            "tpm_queue_delay_ms": 1200,
            "latency_p95_ms": 42000,
            "model_error_rate": 0.01,
            "retry_count": 1,
            "ci_status": "passed",
            "acceptance_status": "accepted",
            "accepted_task": True,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    telemetry = transformed["metadata"]["cc_glm52_guard"]["commercial_telemetry"]
    assert telemetry["team"] == "marketplace"
    assert telemetry["project"] == "checkout"
    assert telemetry["cost_center"] == "marketplace-platform"
    assert telemetry["workload"] == "unit_test_generation"
    assert telemetry["model_pool"] == "glm_execution"
    assert telemetry["reserved_tpm"] == 10000000
    assert telemetry["tpm_queue_delay_ms"] == 1200
    assert telemetry["latency_p95_ms"] == 42000
    assert telemetry["model_error_rate"] == 0.01
    assert telemetry["ci_status"] == "passed"
    assert telemetry["acceptance_status"] == "accepted"
    assert telemetry["accepted_task"] is True
    assert telemetry["relative_cost_vs_premium"] == 0.22


def test_github_failed_check_classifies_ci_auto_fix(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["messages"][-1]["content"] = "Please inspect this failed run."
    request_body["metadata"].update(
        {
            "github_event": "workflow_run",
            "check_name": "build_test_and_deploy",
            "check_conclusion": "failure",
            "repo_risk": "low",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "ci_auto_fix"
    assert audit["task_signal"]["source"] == "github.check_conclusion"


def test_github_code_scanning_alert_classifies_security_review(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "alert_type": "code_scanning",
            "alert_severity": "high",
            "changed_files": ["src/auth/session.py"],
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "security_review"
    assert audit["task_signal"]["source"] == "github.security_alert"


def test_dependabot_version_update_classifies_dependency_update(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "actor": "dependabot[bot]",
            "changed_files": ["package.json", "package-lock.json"],
            "repo_risk": "low",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "dependency_update"
    assert audit["task_signal"]["source"] == "github.dependabot"


def test_dependabot_security_update_routes_to_premium(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "actor": "dependabot[bot]",
            "dependabot_security_update": True,
            "changed_files": ["go.mod", "go.sum"],
            "repo_risk": "medium",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "security_review"
    assert audit["task_signal"]["source"] == "github.dependabot"


def test_codeowners_required_pull_request_classifies_pr_review(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "meli-coding-review"
    request_body["metadata"].update(
        {
            "github_event": "pull_request",
            "github_action": "ready_for_review",
            "codeowners_required": True,
            "repo_risk": "low",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "pr_review"
    assert audit["task_signal"]["source"] == "github.pull_request_action"


def test_changed_path_classifies_documentation_without_prompt_hint(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["messages"][-1]["content"] = ""
    request_body["metadata"].update(
        {
            "changed_files": ["docs/onboarding.md"],
            "repo_risk": "low",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "documentation"
    assert audit["task_signal"]["source"] == "changed_path"


def test_semantic_router_classifies_ambiguous_architecture_prompt(plugin_module, monkeypatch):
    callback_module = sys.modules[plugin_module.CCGLM52Guard.__module__]
    monkeypatch.setattr(callback_module, "_SEMANTIC_ROUTE_LAYER_ATTEMPTED", True)
    monkeypatch.setattr(
        callback_module,
        "_SEMANTIC_ROUTE_LAYER",
        _StubSemanticRouteLayer("architecture_planning"),
    )
    monkeypatch.setattr(
        plugin_module.proxy_handler_instance.config,
        "semantic_router_enabled",
        True,
    )

    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["messages"][-1]["content"] = (
        "We need to choose boundaries, components, and rollout tradeoffs for this change."
    )
    request_body["metadata"].update({"repo_risk": "low"})

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "architecture_planning"
    assert audit["task_signal"]["source"] == "semantic_router"
    assert audit["route_reason"] == "premium_task"


def test_github_signal_takes_precedence_over_semantic_router(plugin_module, monkeypatch):
    callback_module = sys.modules[plugin_module.CCGLM52Guard.__module__]
    monkeypatch.setattr(callback_module, "_SEMANTIC_ROUTE_LAYER_ATTEMPTED", True)
    monkeypatch.setattr(
        callback_module,
        "_SEMANTIC_ROUTE_LAYER",
        _StubSemanticRouteLayer("security_review"),
    )
    monkeypatch.setattr(
        plugin_module.proxy_handler_instance.config,
        "semantic_router_enabled",
        True,
    )

    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["messages"][-1]["content"] = "The wording is ambiguous."
    request_body["metadata"].update(
        {
            "github_event": "workflow_run",
            "check_conclusion": "failure",
            "repo_risk": "low",
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["task_type"] == "ci_auto_fix"
    assert audit["task_signal"]["source"] == "github.check_conclusion"


def test_premium_sticky_suppresses_downgrade_to_glm(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "unit_test_generation",
            "repo_risk": "low",
            "context_tokens": 50000,
            "session_id": "coding-session-1",
            "session_turn": 4,
            "previous_internal_route_model": EXPECTED_PREMIUM,
            "premium_sticky_until_turn": 7,
            "last_model_switch_turn": 3,
            "model_switch_count": 1,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["route_reason"] == "model_switch_suppressed"
    assert audit["model_switch_policy"]["applied"] is True
    assert audit["model_switch_policy"]["reason"] == "premium_sticky_window_active"


def test_hard_high_risk_upgrade_ignores_switch_suppression(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "code_generation",
            "repo_risk": "high",
            "session_id": "coding-session-2",
            "session_turn": 5,
            "previous_internal_route_model": EXPECTED_GLM,
            "last_model_switch_turn": 4,
            "model_switch_count": 5,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_PREMIUM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["route_reason"] == "high_risk_repository"
    assert audit["model_switch_policy"]["reason"] == "hard_route_allows_switch"


def test_successful_probe_allows_premium_downgrade_after_cooldown(plugin_module):
    request_body = load_fixture("text_request.json")
    request_body["model"] = "coding-auto"
    request_body["metadata"].update(
        {
            "task_type": "documentation",
            "repo_risk": "low",
            "context_tokens": 40000,
            "session_id": "coding-session-3",
            "session_turn": 12,
            "previous_internal_route_model": EXPECTED_PREMIUM,
            "premium_sticky_until_turn": 6,
            "last_model_switch_turn": 4,
            "model_switch_count": 1,
            "glm_success_streak": 2,
        }
    )

    transformed = run_guard(plugin_module, request_body)

    assert route_model(transformed) == EXPECTED_GLM
    audit = transformed["metadata"]["cc_glm52_guard"]
    assert audit["route_reason"] == "smart_router_glm_execution"
    assert audit["model_switch_policy"]["reason"] == "switch_allowed"
