import json
import math
import os
import re
from collections.abc import MutableMapping
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger


DEFAULT_EXECUTION_MODEL = "glm-5.2"
DEFAULT_PREMIUM_MODEL = "opus-4.8"
DEFAULT_VISION_MODEL = "vision-openrouter"
DEFAULT_SUMMARY_MODEL = "opus-summary"
DEFAULT_SOFT_LIMIT = 180000
DEFAULT_GLM_DIRECT_LIMIT = 160000
DEFAULT_GLM_MAX_LIMIT = 196000
DEFAULT_COMPACT_TRIGGER = 150000
DEFAULT_CLEAR_TOOL_TRIGGER = 100000
DEFAULT_SEARCH_MODE = "native"
DEFAULT_CAPABILITY_MODE = "frontend_capable"
DEFAULT_TOOL_USE_KEEP = 3
DEFAULT_GLM_RELATIVE_COST = 0.22
DEFAULT_PREMIUM_RELATIVE_COST = 1.0
DEFAULT_VISION_RELATIVE_COST = 1.0
DEFAULT_SWITCH_COOLDOWN_TURNS = 3
DEFAULT_PREMIUM_STICKY_TURNS = 5
DEFAULT_MAX_SWITCHES_PER_SESSION = 2
DEFAULT_GLM_DOWNGRADE_SUCCESS_STREAK = 2
DEFAULT_SEMANTIC_ROUTER_ENABLED = False
DEFAULT_SEMANTIC_ROUTER_ENCODER = "huggingface"
DEFAULT_SEMANTIC_ROUTER_HF_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_RELIABLE_TOOL_MODEL = ""

EXECUTION_ALIASES = {
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "glm-5.2",
    "claude-glm1",
}

BACKEND_FALLBACK_ALIASES = {
    "claude-opus-4-6-backend",
    "claude-sonnet-4-6-backend",
    "glm-5.2-backend",
    "claude-glm1-backend",
}

VIRTUAL_MODEL_ALIASES = {
    "meli-coding-fast",
    "coding-auto",
    "meli-coding-auto",
    "meli-coding-deep",
    "meli-coding-review",
    "meli-coding-vision",
}

AUTO_ROUTER_ALIASES = {
    "coding-auto",
    "meli-coding-auto",
}

IMAGE_BLOCK_TYPES = {
    "image",
    "image_url",
    "input_image",
}

STRIPPED_CONTENT_BLOCK_TYPES = {
    "thinking",
    "redacted_thinking",
}

SEARCH_INTENT_RE = re.compile(
    r"搜索|新闻|最新|今天|今日|current|latest|today|news|search",
    re.IGNORECASE,
)

TASK_CLASSIFIER_PATTERNS = (
    ("vision_task", re.compile(r"screenshot|image|ui|视觉|截图|图片", re.IGNORECASE)),
    (
        "security_review",
        re.compile(r"security|vulnerability|漏洞|安全|pci|authz|authn", re.IGNORECASE),
    ),
    (
        "architecture_planning",
        re.compile(r"architecture|design|rfc|方案|架构|设计", re.IGNORECASE),
    ),
    (
        "complex_debug",
        re.compile(
            r"root cause|race condition|deadlock|复杂.*debug|疑难|根因",
            re.IGNORECASE,
        ),
    ),
    (
        "production_incident",
        re.compile(r"incident|outage|p0|p1|生产事故|故障|线上事故", re.IGNORECASE),
    ),
    (
        "unit_test_generation",
        re.compile(r"unit test|junit|pytest|coverage|单元测试|测试覆盖", re.IGNORECASE),
    ),
    (
        "pr_review",
        re.compile(r"pr diff|pull request|merge request|code review|代码审查", re.IGNORECASE),
    ),
    (
        "ci_auto_fix",
        re.compile(r"ci|pipeline failed|build failed|stacktrace|fix.*test|修复.*流水线", re.IGNORECASE),
    ),
    (
        "repo_summary",
        re.compile(r"repo summary|repository summary|summari[sz]e repo|仓库总结|代码库总结", re.IGNORECASE),
    ),
    (
        "documentation",
        re.compile(r"documentation|readme|docs|文档|说明", re.IGNORECASE),
    ),
    (
        "refactoring",
        re.compile(r"refactor|cleanup|重构|整理代码", re.IGNORECASE),
    ),
    (
        "migration_execution",
        re.compile(r"migration|migrate|legacy|迁移|遗留", re.IGNORECASE),
    ),
)

SEMANTIC_TASK_UTTERANCES = {
    "architecture_planning": [
        "Design the architecture for a new service from requirements.",
        "Create an RFC comparing approaches and tradeoffs.",
        "Plan a migration architecture across modules and systems.",
        "制定系统架构方案并说明关键取舍。",
        "评审整体技术方案和模块边界。",
    ],
    "complex_debug": [
        "Find the root cause of a race condition across services.",
        "Debug an intermittent deadlock or flaky production failure.",
        "Investigate a deep bug with logs, stack traces, and timing issues.",
        "定位复杂线上问题的根因。",
        "分析难复现的并发缺陷。",
    ],
    "unit_test_generation": [
        "Generate focused unit tests for this code.",
        "Add pytest coverage for edge cases and error paths.",
        "Write JUnit tests for the service behavior.",
        "补充单元测试和边界条件覆盖。",
        "为这个模块生成测试用例。",
    ],
    "documentation": [
        "Update README usage and configuration documentation.",
        "Write developer docs for this API.",
        "Document the behavior and operational runbook.",
        "完善文档、说明和示例。",
        "整理接口说明和使用指南。",
    ],
    "ci_auto_fix": [
        "Fix the failing CI workflow.",
        "Diagnose a failed GitHub Actions build.",
        "Repair broken tests from a pipeline failure.",
        "修复流水线失败和构建错误。",
        "根据 CI 日志修复测试失败。",
    ],
    "security_review": [
        "Review this change for security vulnerabilities.",
        "Analyze authentication and authorization risks.",
        "Check for secrets, injection, and sensitive data exposure.",
        "进行安全审查并指出漏洞风险。",
        "评估鉴权、注入和敏感信息泄露问题。",
    ],
}

LABEL_TASK_HINTS = {
    "bug": "bug_fix",
    "fix": "bug_fix",
    "feature": "code_generation",
    "enhancement": "code_generation",
    "documentation": "documentation",
    "docs": "documentation",
    "test": "unit_test_generation",
    "tests": "unit_test_generation",
    "ci": "ci_auto_fix",
    "github-actions": "ci_auto_fix",
    "dependencies": "dependency_update",
    "dependabot": "dependency_update",
    "security": "security_review",
    "vulnerability": "security_review",
    "codeql": "security_review",
}

PATH_TASK_RULES = (
    ("security_review", re.compile(r"(^|/)(security|auth|pci|risk)(/|$)", re.IGNORECASE)),
    (
        "ci_auto_fix",
        re.compile(r"(^|/)(\.github/workflows|Jenkinsfile|\.gitlab-ci\.yml|circleci)(/|$)", re.IGNORECASE),
    ),
    (
        "documentation",
        re.compile(r"(^|/)(docs?|README|CHANGELOG|adr)(/|\.|$)", re.IGNORECASE),
    ),
    (
        "unit_test_generation",
        re.compile(r"(^|/)(test|tests|spec|specs|__tests__)(/|$)|(_test|\.spec|\.test)\.", re.IGNORECASE),
    ),
    (
        "dependency_update",
        re.compile(
            r"(^|/)(package-lock\.json|package\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|requirements\.txt|go\.mod|go\.sum|pom\.xml|build\.gradle|Cargo\.toml|Cargo\.lock)(/|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "migration_execution",
        re.compile(r"(^|/)(migrations?|liquibase|flyway)(/|$)", re.IGNORECASE),
    ),
    (
        "infrastructure_change",
        re.compile(r"\.(tf|tfvars)$|(^|/)(terraform|helm|k8s|kubernetes|charts)(/|$)", re.IGNORECASE),
    ),
)

GLM_EXECUTION_TASKS = {
    "unit_test_generation",
    "documentation",
    "repo_summary",
    "ci_auto_fix",
    "code_generation",
    "bug_fix",
    "refactoring",
    "migration_execution",
    "dependency_update",
    "merge_conflict_resolution",
}

PREMIUM_TASKS = {
    "architecture_planning",
    "complex_debug",
    "production_incident",
    "security_review",
    "infrastructure_change",
}

HIGH_RISK_TAGS = {"payment", "payments", "auth", "risk", "pci", "security"}
LOW_RISK_TAGS = {"internal-tools", "docs", "test", "tests", "sandbox"}

_SEMANTIC_ROUTE_LAYER: Any = None
_SEMANTIC_ROUTE_LAYER_ATTEMPTED = False


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        verbose_proxy_logger.warning(
            "cc_glm52_guard ignored invalid integer env %s=%r", name, value
        )
        return default
    return parsed if parsed > 0 else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value)
    except ValueError:
        verbose_proxy_logger.warning(
            "cc_glm52_guard ignored invalid float env %s=%r", name, value
        )
        return default
    return parsed if parsed >= 0 else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class GuardConfig:
    def __init__(self) -> None:
        self.execution_model = _env_str(
            "CC_GLM52_EXECUTION_MODEL", DEFAULT_EXECUTION_MODEL
        )
        self.premium_model = _env_str("CC_GLM52_PREMIUM_MODEL", DEFAULT_PREMIUM_MODEL)
        self.vision_model = _env_str("CC_GLM52_VISION_MODEL", DEFAULT_VISION_MODEL)
        self.summary_model = _env_str("CC_GLM52_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL)
        self.reliable_tool_model = _env_str(
            "CC_GLM52_RELIABLE_TOOL_MODEL", DEFAULT_RELIABLE_TOOL_MODEL
        )
        self.soft_limit = _env_int("CC_GLM52_SOFT_LIMIT", DEFAULT_SOFT_LIMIT)
        self.glm_direct_limit = _env_int(
            "CC_GLM52_DIRECT_LIMIT", DEFAULT_GLM_DIRECT_LIMIT
        )
        self.glm_max_limit = _env_int("CC_GLM52_MAX_LIMIT", DEFAULT_GLM_MAX_LIMIT)
        self.compact_trigger = _env_int(
            "CC_GLM52_COMPACT_TRIGGER", DEFAULT_COMPACT_TRIGGER
        )
        self.clear_tool_trigger = _env_int(
            "CC_GLM52_CLEAR_TOOL_TRIGGER", DEFAULT_CLEAR_TOOL_TRIGGER
        )
        self.search_mode = _env_str("CC_GLM52_SEARCH_MODE", DEFAULT_SEARCH_MODE)
        self.capability_mode = normalize_capability_mode(
            _env_str("CC_GLM52_CAPABILITY_MODE", DEFAULT_CAPABILITY_MODE)
        )
        self.glm_relative_cost = _env_float(
            "CC_GLM52_GLM_RELATIVE_COST", DEFAULT_GLM_RELATIVE_COST
        )
        self.premium_relative_cost = _env_float(
            "CC_GLM52_PREMIUM_RELATIVE_COST", DEFAULT_PREMIUM_RELATIVE_COST
        )
        self.vision_relative_cost = _env_float(
            "CC_GLM52_VISION_RELATIVE_COST", DEFAULT_VISION_RELATIVE_COST
        )
        self.switch_cooldown_turns = _env_int(
            "CC_GLM52_SWITCH_COOLDOWN_TURNS", DEFAULT_SWITCH_COOLDOWN_TURNS
        )
        self.premium_sticky_turns = _env_int(
            "CC_GLM52_PREMIUM_STICKY_TURNS", DEFAULT_PREMIUM_STICKY_TURNS
        )
        self.max_switches_per_session = _env_int(
            "CC_GLM52_MAX_SWITCHES_PER_SESSION", DEFAULT_MAX_SWITCHES_PER_SESSION
        )
        self.glm_downgrade_success_streak = _env_int(
            "CC_GLM52_GLM_DOWNGRADE_SUCCESS_STREAK",
            DEFAULT_GLM_DOWNGRADE_SUCCESS_STREAK,
        )
        self.semantic_router_enabled = _env_bool(
            "CC_GLM52_SEMANTIC_ROUTER_ENABLED",
            DEFAULT_SEMANTIC_ROUTER_ENABLED,
        )
        self.semantic_router_encoder = _env_str(
            "CC_GLM52_SEMANTIC_ROUTER_ENCODER",
            DEFAULT_SEMANTIC_ROUTER_ENCODER,
        )
        self.semantic_router_hf_model = _env_str(
            "CC_GLM52_SEMANTIC_ROUTER_HF_MODEL",
            DEFAULT_SEMANTIC_ROUTER_HF_MODEL,
        )


class CCGLM52Guard(CustomLogger):
    def __init__(self, config: Optional[GuardConfig] = None) -> None:
        super().__init__()
        self.config = config or GuardConfig()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not isinstance(data, dict):
            return data

        external_model = data.get("model")
        input_tokens_estimated = estimate_input_tokens(data)
        has_image = has_image_content(data)
        stripped_blocks = strip_unsupported_content_blocks(data)
        capability_mode = request_capability_mode(data, external_model, self.config)
        search_intent = has_search_intent(data)
        backend_search_enabled = maybe_enable_backend_search(
            data, capability_mode, search_intent, self.config
        )

        route_decision = self._route_model(
            data=data,
            external_model=external_model,
            has_image=has_image,
            input_tokens_estimated=input_tokens_estimated,
        )
        if route_decision["internal_route_model"] is not None:
            data["model"] = route_decision["internal_route_model"]

        context_handoff = build_context_handoff(data, route_decision, self.config)
        handoff_instruction_injected = maybe_inject_context_handoff_instruction(
            data, context_handoff
        )
        context_action = merge_context_management(data, self.config)
        commercial_telemetry = build_commercial_telemetry(
            data=data,
            route_decision=route_decision,
            input_tokens_estimated=input_tokens_estimated,
            config=self.config,
        )
        audit = {
            "external_model": external_model,
            "internal_route_model": data.get("model"),
            "route_reason": route_decision["route_reason"],
            "virtual_model": route_decision["virtual_model"],
            "task_type": route_decision["task_type"],
            "task_signal": route_decision["task_signal"],
            "repo_risk": route_decision["repo_risk"],
            "repo_tags": route_decision["repo_tags"],
            "budget_state": route_decision["budget_state"],
            "latency_slo": route_decision["latency_slo"],
            "capacity_state": route_decision["capacity_state"],
            "fallback_triggered": route_decision["fallback_triggered"],
            "fallback_reason": route_decision["fallback_reason"],
            "model_switch_policy": route_decision["model_switch_policy"],
            "context_policy": route_decision["context_policy"],
            "context_handoff": context_handoff,
            "handoff_instruction_injected": handoff_instruction_injected,
            "multimodal_route": has_image,
            "input_tokens_estimated": input_tokens_estimated,
            "context_action": context_action_for_estimate(
                input_tokens_estimated, context_action, self.config
            ),
            "summary_model": self.config.summary_model,
            "premium_model": self.config.premium_model,
            "glm_direct_limit": self.config.glm_direct_limit,
            "glm_max_limit": self.config.glm_max_limit,
            "capability_mode": capability_mode,
            "soft_limit": self.config.soft_limit,
            "compact_trigger": self.config.compact_trigger,
            "clear_tool_trigger": self.config.clear_tool_trigger,
            "search_mode": self.config.search_mode,
            "search_intent": search_intent,
            "backend_search_enabled": backend_search_enabled,
            "search_backend_used": backend_search_enabled,
            "stripped_content_blocks": stripped_blocks,
            "commercial_telemetry": commercial_telemetry,
            "call_type": str(call_type),
        }
        merge_audit_fields(data, audit)
        return data

    def _route_model(
        self,
        data: Dict[str, Any],
        external_model: Any,
        has_image: bool,
        input_tokens_estimated: int,
    ) -> Dict[str, Any]:
        task_signal = classify_task_signal(data, has_image, self.config)
        task_type = task_signal["task_type"]
        repo_tags = classify_repo_tags(data)
        repo_risk = classify_repo_risk(data, repo_tags)
        budget_state = metadata_value(data, "budget_state", "normal")
        latency_slo = metadata_value(data, "latency_slo", "interactive")
        context_tokens = metadata_int(data, "context_tokens", input_tokens_estimated)
        capacity_state = classify_capacity_state(data)
        fallback_reason = fallback_reason_for_request(data, capacity_state)
        context_policy = context_policy_for_tokens(context_tokens, self.config)

        decision: Dict[str, Any] = {
            "internal_route_model": None,
            "route_reason": "unchanged",
            "virtual_model": (
                external_model if external_model in VIRTUAL_MODEL_ALIASES else None
            ),
            "task_type": task_type,
            "task_signal": task_signal,
            "repo_risk": repo_risk,
            "repo_tags": repo_tags,
            "budget_state": budget_state,
            "latency_slo": latency_slo,
            "capacity_state": capacity_state,
            "fallback_triggered": fallback_reason is not None,
            "fallback_reason": fallback_reason,
            "model_switch_policy": {
                "applied": False,
                "reason": None,
            },
            "context_policy": context_policy,
        }

        if has_image:
            decision.update(
                internal_route_model=self.config.vision_model,
                route_reason="image_content",
            )
            return stabilize_route_decision(data, decision, self.config)

        if self.config.reliable_tool_model and has_client_tools(data):
            decision.update(
                internal_route_model=self.config.reliable_tool_model,
                route_reason="reliable_tool_model",
            )
            return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model == "meli-coding-vision":
            decision.update(
                internal_route_model=self.config.vision_model,
                route_reason="virtual_vision",
            )
            return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model == "meli-coding-deep":
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason="virtual_deep",
            )
            return stabilize_route_decision(data, decision, self.config)

        if fallback_reason is not None:
            route_reason = (
                "context_unsegmentable_to_premium"
                if fallback_reason
                in {
                    "context_unsegmentable",
                    "context_split_failed",
                    "compression_failed",
                }
                else "fallback_to_premium"
            )
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason=route_reason,
            )
            return stabilize_route_decision(data, decision, self.config)

        if task_type in PREMIUM_TASKS:
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason="premium_task",
            )
            return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model == "meli-coding-review":
            if repo_risk in {"medium", "high", "restricted"} or task_type == "pr_review":
                model = (
                    self.config.premium_model
                    if repo_risk in {"high", "restricted"}
                    else self.config.execution_model
                )
                reason = (
                    "risk_based_review_premium"
                    if model == self.config.premium_model
                    else "risk_based_review_glm"
                )
                decision.update(internal_route_model=model, route_reason=reason)
                return stabilize_route_decision(data, decision, self.config)

        if repo_risk in {"high", "restricted"}:
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason="high_risk_repository",
            )
            return stabilize_route_decision(data, decision, self.config)

        if context_tokens > self.config.glm_max_limit:
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason="context_above_glm_limit",
            )
            return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model == "meli-coding-fast":
            decision.update(
                internal_route_model=self.config.execution_model,
                route_reason="virtual_fast_execution",
            )
            return stabilize_route_decision(data, decision, self.config)

        if capacity_state.get("glm_available") is False and latency_slo == "interactive":
            decision.update(
                internal_route_model=self.config.premium_model,
                route_reason="interactive_glm_capacity_unavailable",
            )
            return stabilize_route_decision(data, decision, self.config)

        if budget_state in {"near_limit", "limited", "exhausted"}:
            decision.update(
                internal_route_model=self.config.execution_model,
                route_reason="budget_prefers_glm",
            )
            return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model in AUTO_ROUTER_ALIASES:
            if task_type in GLM_EXECUTION_TASKS or task_type == "unknown":
                decision.update(
                    internal_route_model=self.config.execution_model,
                    route_reason="smart_router_glm_execution",
                )
                return stabilize_route_decision(data, decision, self.config)

        if isinstance(external_model, str) and external_model in (
            EXECUTION_ALIASES | BACKEND_FALLBACK_ALIASES
        ):
            decision.update(
                internal_route_model=self.config.execution_model,
                route_reason="execution_alias",
            )
            return stabilize_route_decision(data, decision, self.config)
        return stabilize_route_decision(data, decision, self.config)


def stabilize_route_decision(
    data: Dict[str, Any], decision: Dict[str, Any], config: GuardConfig
) -> Dict[str, Any]:
    state = model_switch_state(data)
    policy = {
        "applied": False,
        "reason": None,
        "session_id": state["session_id"],
        "session_turn": state["session_turn"],
        "previous_model": state["previous_model"],
        "candidate_model": decision.get("internal_route_model"),
        "switch_count": state["switch_count"],
        "cooldown_turns": config.switch_cooldown_turns,
        "premium_sticky_turns": config.premium_sticky_turns,
    }

    candidate = decision.get("internal_route_model")
    previous = state["previous_model"]
    if not candidate or not previous or candidate == previous:
        decision["model_switch_policy"] = policy
        return decision

    if hard_route_reason(decision.get("route_reason")):
        policy["reason"] = "hard_route_allows_switch"
        decision["model_switch_policy"] = policy
        return decision

    previous_is_premium = previous == config.premium_model
    candidate_is_glm = candidate == config.execution_model
    if previous_is_premium and candidate_is_glm:
        sticky_until = state["premium_sticky_until_turn"]
        current_turn = state["session_turn"]
        if current_turn is not None and sticky_until is not None:
            if current_turn <= sticky_until:
                return keep_previous_model(
                    decision,
                    policy,
                    previous,
                    "premium_sticky_window_active",
                )

        if switch_in_cooldown(state, config):
            return keep_previous_model(
                decision,
                policy,
                previous,
                "switch_cooldown_active",
            )

        allow_downgrade = metadata_bool(data, "allow_premium_downgrade", False)
        glm_success_streak = metadata_int(data, "glm_success_streak", 0)
        if not allow_downgrade and glm_success_streak < config.glm_downgrade_success_streak:
            return keep_previous_model(
                decision,
                policy,
                previous,
                "premium_sticky_requires_successful_glm_probe",
            )

    if state["switch_count"] >= config.max_switches_per_session:
        return keep_previous_model(
            decision,
            policy,
            previous,
            "max_switches_per_session_reached",
        )

    policy["reason"] = "switch_allowed"
    decision["model_switch_policy"] = policy
    return decision


def keep_previous_model(
    decision: Dict[str, Any], policy: Dict[str, Any], previous_model: str, reason: str
) -> Dict[str, Any]:
    policy.update(
        {
            "applied": True,
            "reason": reason,
            "suppressed_candidate_model": decision.get("internal_route_model"),
        }
    )
    decision["internal_route_model"] = previous_model
    decision["route_reason"] = "model_switch_suppressed"
    decision["model_switch_policy"] = policy
    return decision


def hard_route_reason(route_reason: Any) -> bool:
    return route_reason in {
        "reliable_tool_model",
        "image_content",
        "virtual_vision",
        "virtual_deep",
        "fallback_to_premium",
        "context_unsegmentable_to_premium",
        "premium_task",
        "risk_based_review_premium",
        "high_risk_repository",
        "context_above_glm_limit",
        "interactive_glm_capacity_unavailable",
    }


def switch_in_cooldown(state: Dict[str, Any], config: GuardConfig) -> bool:
    current_turn = state["session_turn"]
    last_switch_turn = state["last_switch_turn"]
    if current_turn is None or last_switch_turn is None:
        return False
    return (current_turn - last_switch_turn) < config.switch_cooldown_turns


def model_switch_state(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": metadata_value(data, "session_id", None),
        "session_turn": optional_metadata_int(data, "session_turn"),
        "previous_model": metadata_value(
            data,
            "previous_internal_route_model",
            metadata_value(data, "previous_route_model", None),
        ),
        "last_switch_turn": optional_metadata_int(data, "last_model_switch_turn"),
        "switch_count": metadata_int(data, "model_switch_count", 0),
        "premium_sticky_until_turn": optional_metadata_int(
            data, "premium_sticky_until_turn"
        ),
    }


def normalize_capability_mode(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_CAPABILITY_MODE
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"frontend", "frontend_capable", "oauth", "oauth_present"}:
        return "frontend_capable"
    if normalized in {"backend", "backend_fallback", "no_oauth", "oauth_absent"}:
        return "backend_fallback"
    return DEFAULT_CAPABILITY_MODE


def request_capability_mode(
    data: Dict[str, Any], external_model: Any, config: GuardConfig
) -> str:
    for value in iter_capability_mode_values(data):
        mode = normalize_capability_mode(value)
        if mode != DEFAULT_CAPABILITY_MODE or str(value).lower() in {
            "frontend",
            "frontend_capable",
        }:
            return mode
    if isinstance(external_model, str) and external_model in BACKEND_FALLBACK_ALIASES:
        return "backend_fallback"
    return config.capability_mode


def classify_task(data: Dict[str, Any], has_image: bool) -> str:
    return classify_task_signal(data, has_image)["task_type"]


def classify_task_signal(
    data: Dict[str, Any],
    has_image: bool,
    config: Optional[GuardConfig] = None,
) -> Dict[str, Any]:
    if has_image:
        return task_signal("vision_task", "modality", "image_content")

    explicit = metadata_value(data, "task_type", None)
    if isinstance(explicit, str) and explicit.strip():
        return task_signal(
            explicit.strip().lower().replace("-", "_"),
            "metadata.task_type",
            explicit,
        )

    github_task = classify_github_task(data)
    if github_task is not None:
        return github_task

    path_task = classify_path_task(data)
    if path_task is not None:
        return path_task

    text = latest_user_text(data)
    semantic_task = classify_semantic_task(text, config or GuardConfig())
    if semantic_task is not None:
        return semantic_task

    for task_type, pattern in TASK_CLASSIFIER_PATTERNS:
        if pattern.search(text):
            return task_signal(task_type, "prompt_pattern", pattern.pattern)
    return task_signal("code_generation" if text else "unknown", "default", None)


def task_signal(task_type: str, source: str, evidence: Any) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "source": source,
        "evidence": evidence,
    }


def classify_semantic_task(
    text: str,
    config: GuardConfig,
) -> Optional[Dict[str, Any]]:
    if not config.semantic_router_enabled or not text.strip():
        return None

    route_layer = semantic_route_layer(config)
    if route_layer is None:
        return None

    try:
        choice = route_layer(text)
    except Exception as exc:
        verbose_proxy_logger.warning(
            "cc_glm52_guard semantic-router classification failed: %s", exc
        )
        return None

    route_name = getattr(choice, "name", None)
    if not route_name and isinstance(choice, str):
        route_name = choice
    if route_name not in SEMANTIC_TASK_UTTERANCES:
        return None

    return task_signal(
        route_name,
        "semantic_router",
        {
            "route": route_name,
            "similarity_score": getattr(choice, "similarity_score", None),
            "encoder": config.semantic_router_encoder,
        },
    )


def semantic_route_layer(config: GuardConfig) -> Any:
    global _SEMANTIC_ROUTE_LAYER, _SEMANTIC_ROUTE_LAYER_ATTEMPTED

    if _SEMANTIC_ROUTE_LAYER is not None:
        return _SEMANTIC_ROUTE_LAYER
    if _SEMANTIC_ROUTE_LAYER_ATTEMPTED:
        return None
    _SEMANTIC_ROUTE_LAYER_ATTEMPTED = True

    try:
        from semantic_router import Route

        try:
            from semantic_router.layer import RouteLayer
        except ImportError:
            from semantic_router import RouteLayer

        encoder = semantic_router_encoder(config)
        routes = [
            Route(name=task_type, utterances=utterances)
            for task_type, utterances in SEMANTIC_TASK_UTTERANCES.items()
        ]
        _SEMANTIC_ROUTE_LAYER = RouteLayer(encoder=encoder, routes=routes)
    except Exception as exc:
        verbose_proxy_logger.warning(
            "cc_glm52_guard semantic-router disabled: %s", exc
        )
        _SEMANTIC_ROUTE_LAYER = None
    return _SEMANTIC_ROUTE_LAYER


def semantic_router_encoder(config: GuardConfig) -> Any:
    encoder_name = config.semantic_router_encoder.strip().lower().replace("_", "-")
    if encoder_name == "openai":
        from semantic_router.encoders import OpenAIEncoder

        return OpenAIEncoder()
    if encoder_name == "cohere":
        from semantic_router.encoders import CohereEncoder

        return CohereEncoder()
    if encoder_name == "fastembed":
        from semantic_router.encoders import FastEmbedEncoder

        return FastEmbedEncoder()

    from semantic_router.encoders import HuggingFaceEncoder

    return HuggingFaceEncoder(name=config.semantic_router_hf_model)


def classify_github_task(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event = normalized_metadata_string(data, "github_event")
    action = normalized_metadata_string(data, "github_action")
    actor = normalized_metadata_string(data, "actor")
    check_name = normalized_metadata_string(data, "check_name")
    check_conclusion = normalized_metadata_string(data, "check_conclusion")
    check_status = normalized_metadata_string(data, "check_status")
    alert_type = normalized_metadata_string(data, "alert_type")
    alert_severity = normalized_metadata_string(data, "alert_severity")
    pr_state = normalized_metadata_string(data, "pr_state")

    if actor == "dependabot[bot]" or metadata_bool(data, "dependabot", False):
        if metadata_bool(data, "dependabot_security_update", False):
            return task_signal("security_review", "github.dependabot", "security_update")
        return task_signal("dependency_update", "github.dependabot", actor or "dependabot")

    if alert_type in {"code_scanning", "secret_scanning", "dependabot_alert"}:
        return task_signal("security_review", "github.security_alert", alert_type)

    if alert_severity in {"error", "critical", "high"}:
        return task_signal("security_review", "github.alert_severity", alert_severity)

    if event in {"check_run", "check_suite", "workflow_run", "workflow_job"}:
        if check_conclusion in {"failure", "timed_out", "cancelled", "action_required"}:
            return task_signal("ci_auto_fix", "github.check_conclusion", check_conclusion)
        if check_status in {"failure", "failed"}:
            return task_signal("ci_auto_fix", "github.check_status", check_status)

    if "codeql" in check_name or "code scanning" in check_name:
        return task_signal("security_review", "github.check_name", check_name)

    labels = normalize_string_list(metadata_value(data, "labels", None))
    labels.extend(normalize_string_list(metadata_value(data, "github_labels", None)))
    for label in labels:
        for hint, task_type in LABEL_TASK_HINTS.items():
            if hint in label:
                return task_signal(task_type, "github.label", label)

    if metadata_bool(data, "merge_conflict", False) or action == "resolve_conflicts":
        return task_signal(
            "merge_conflict_resolution",
            "github.merge_conflict",
            action or "merge_conflict",
        )

    if event in {"pull_request_review", "pull_request_review_comment"}:
        return task_signal("pr_review", "github.event", event)

    if event in {"pull_request", "pull_request_target"}:
        if action in {"review_requested", "ready_for_review", "opened", "reopened"}:
            return task_signal("pr_review", "github.pull_request_action", action)
        if action in {"synchronize", "edited"} and pr_state != "draft":
            return task_signal("pr_review", "github.pull_request_action", action)

    if metadata_bool(data, "codeowners_required", False):
        return task_signal("pr_review", "github.codeowners", "codeowners_required")

    return None


def classify_path_task(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    paths = changed_paths(data)
    for path in paths:
        for task_type, pattern in PATH_TASK_RULES:
            if pattern.search(path):
                return task_signal(task_type, "changed_path", path)
    return None


def changed_paths(data: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for key in (
        "changed_files",
        "file_paths",
        "paths",
        "modified_files",
        "added_files",
        "removed_files",
    ):
        paths.extend(normalize_path_list(metadata_value(data, key, None)))
    return sorted(set(paths))


def normalized_metadata_string(data: Dict[str, Any], key: str) -> str:
    value = metadata_value(data, key, "")
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_")


def classify_repo_tags(data: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("repo_tags", "repository_tags", "tags"):
        value = metadata_value(data, key, None)
        tags.extend(normalize_string_list(value))
    for key in ("repo", "repository", "project", "path", "file_path", "cost_center"):
        value = metadata_value(data, key, None)
        if isinstance(value, str):
            lowered = value.lower()
            for tag in HIGH_RISK_TAGS | LOW_RISK_TAGS:
                if tag in lowered:
                    tags.append(tag)
    return sorted(set(tags))


def classify_repo_risk(data: Dict[str, Any], repo_tags: List[str]) -> str:
    explicit = metadata_value(data, "repo_risk", None)
    if isinstance(explicit, str) and explicit.strip():
        normalized = explicit.strip().lower().replace("-", "_")
        if normalized in {"low", "medium", "high", "restricted"}:
            return normalized
    if any(tag in HIGH_RISK_TAGS for tag in repo_tags):
        return "high"
    if repo_tags and all(tag in LOW_RISK_TAGS for tag in repo_tags):
        return "low"
    return "medium"


def classify_capacity_state(data: Dict[str, Any]) -> Dict[str, Any]:
    available = metadata_bool(data, "glm_available", True)
    queue_delay_ms = metadata_int(data, "tpm_queue_delay_ms", 0)
    latency_p95_ms = metadata_int(data, "latency_p95_ms", 0)
    error_rate = metadata_float(data, "model_error_rate", 0.0)
    return {
        "glm_available": available,
        "tpm_queue_delay_ms": queue_delay_ms,
        "latency_p95_ms": latency_p95_ms,
        "model_error_rate": error_rate,
    }


def fallback_reason_for_request(
    data: Dict[str, Any], capacity_state: Dict[str, Any]
) -> Optional[str]:
    if metadata_bool(data, "context_unsegmentable", False):
        return "context_unsegmentable"
    if metadata_bool(data, "context_split_failed", False):
        return "context_split_failed"
    if metadata_bool(data, "compression_failed", False):
        return "compression_failed"
    retry_count = metadata_int(data, "retry_count", 0)
    if retry_count >= 2:
        return "retry_count_gte_2"
    if metadata_bool(data, "test_failed_twice", False):
        return "test_failed_twice"
    if capacity_state["latency_p95_ms"] > 60000:
        return "latency_p95_gt_60000"
    if capacity_state["model_error_rate"] > 0.03:
        return "model_error_rate_gt_0_03"
    if capacity_state["tpm_queue_delay_ms"] > 30000:
        return "tpm_queue_delay_gt_30000"
    return None


def context_policy_for_tokens(context_tokens: int, config: GuardConfig) -> str:
    if context_tokens <= config.glm_direct_limit:
        return "glm_direct"
    if context_tokens <= config.glm_max_limit:
        return "compression_required"
    return "requires_rag_file_selection_summary_or_split"


def build_commercial_telemetry(
    data: Dict[str, Any],
    route_decision: Dict[str, Any],
    input_tokens_estimated: int,
    config: GuardConfig,
) -> Dict[str, Any]:
    target_model = route_decision.get("internal_route_model") or data.get("model")
    model_pool = model_pool_for_target(target_model, config)
    relative_cost = relative_cost_for_pool(model_pool, route_decision, config)
    return {
        "tool": metadata_value(data, "tool", None),
        "team": metadata_value(data, "team", None),
        "project": metadata_value(data, "project", None),
        "repo": metadata_value(data, "repo", metadata_value(data, "repository", None)),
        "language": metadata_value(data, "language", None),
        "cost_center": metadata_value(data, "cost_center", None),
        "workload": route_decision.get("task_type"),
        "model_pool": model_pool,
        "target_model": target_model,
        "estimated_input_tokens": input_tokens_estimated,
        "declared_context_tokens": metadata_int(
            data, "context_tokens", input_tokens_estimated
        ),
        "reserved_tpm": metadata_int(data, "glm_reserved_tpm", 0),
        "tpm_queue_delay_ms": route_decision["capacity_state"]["tpm_queue_delay_ms"],
        "latency_p95_ms": route_decision["capacity_state"]["latency_p95_ms"],
        "model_error_rate": route_decision["capacity_state"]["model_error_rate"],
        "retry_count": metadata_int(data, "retry_count", 0),
        "test_failed_twice": metadata_bool(data, "test_failed_twice", False),
        "ci_status": metadata_value(data, "ci_status", None),
        "acceptance_status": metadata_value(data, "acceptance_status", None),
        "accepted_task": metadata_bool(data, "accepted_task", False),
        "fallback_triggered": route_decision.get("fallback_triggered", False),
        "fallback_reason": route_decision.get("fallback_reason"),
        "context_handoff_required": (
            route_decision.get("route_reason") == "context_unsegmentable_to_premium"
        ),
        "model_switch_suppressed": route_decision["model_switch_policy"]["applied"],
        "model_switch_suppression_reason": route_decision["model_switch_policy"][
            "reason"
        ],
        "relative_cost_vs_premium": relative_cost,
        "cost_model": "relative_to_premium_model",
    }


def build_context_handoff(
    data: Dict[str, Any],
    route_decision: Dict[str, Any],
    config: GuardConfig,
) -> Dict[str, Any]:
    required = route_decision.get("route_reason") == "context_unsegmentable_to_premium"
    canonical_replayed = metadata_bool(data, "canonical_context_replayed", False)
    summary = metadata_value(
        data,
        "glm_attempt_summary",
        metadata_value(data, "previous_attempt_summary", None),
    )
    return {
        "required": required,
        "strategy": (
            "replay_full_canonical_context"
            if required
            else "none"
        ),
        "source_model": config.execution_model if required else None,
        "target_model": config.premium_model if required else None,
        "canonical_context_replayed": canonical_replayed,
        "handoff_summary_present": isinstance(summary, str) and bool(summary.strip()),
        "attempt_id": metadata_value(data, "attempt_id", None),
        "previous_attempt_id": metadata_value(data, "previous_attempt_id", None),
        "warning": (
            None
            if (not required or canonical_replayed)
            else "caller_must_replay_full_canonical_context_to_avoid_context_loss"
        ),
    }


def maybe_inject_context_handoff_instruction(
    data: Dict[str, Any], context_handoff: Dict[str, Any]
) -> bool:
    if not context_handoff.get("required"):
        return False
    if metadata_bool(data, "disable_context_handoff_instruction", False):
        return False
    note = context_handoff_note(data, context_handoff)
    if not note:
        return False
    prepend_system_text(data, note)
    return True


def context_handoff_note(
    data: Dict[str, Any], context_handoff: Dict[str, Any]
) -> str:
    summary = metadata_value(
        data,
        "glm_attempt_summary",
        metadata_value(data, "previous_attempt_summary", None),
    )
    parts = [
        "[Context handoff]",
        "This request was escalated from GLM-5.2 to the premium model because the context could not be safely split or compressed.",
        "Use the full canonical conversation/context included in this request as authoritative.",
    ]
    if not context_handoff.get("canonical_context_replayed"):
        parts.append(
            "Warning: canonical_context_replayed is not true; the caller must replay the complete original context to avoid context loss."
        )
    if isinstance(summary, str) and summary.strip():
        parts.append(f"Previous GLM attempt summary: {summary.strip()}")
    return "\n".join(parts)


def prepend_system_text(data: Dict[str, Any], text: str) -> None:
    system = data.get("system")
    if system is None:
        data["system"] = text
        return
    if isinstance(system, str):
        if text in system:
            return
        data["system"] = f"{text}\n\n{system}"
        return
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and block.get("text") == text:
                return
        system.insert(0, {"type": "text", "text": text})
        return

    messages = data.get("messages")
    if isinstance(messages, list):
        messages.insert(0, {"role": "system", "content": text})


def model_pool_for_target(target_model: Any, config: GuardConfig) -> str:
    if target_model == config.execution_model:
        return "glm_execution"
    if target_model == config.premium_model:
        return "premium_reasoning"
    if target_model == config.vision_model:
        return "vision"
    return "external_or_unchanged"


def relative_cost_for_pool(
    model_pool: str, route_decision: Dict[str, Any], config: GuardConfig
) -> float:
    if route_decision.get("fallback_triggered") and model_pool == "premium_reasoning":
        return round(config.glm_relative_cost + config.premium_relative_cost, 4)
    if model_pool == "glm_execution":
        return config.glm_relative_cost
    if model_pool == "premium_reasoning":
        return config.premium_relative_cost
    if model_pool == "vision":
        return config.vision_relative_cost
    return config.premium_relative_cost


def metadata_value(data: Dict[str, Any], key: str, default: Any) -> Any:
    if key in data:
        return data.get(key)
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and key in metadata:
        return metadata.get(key)
    extra_body = data.get("extra_body")
    if isinstance(extra_body, dict) and key in extra_body:
        return extra_body.get(key)
    litellm_metadata = data.get("litellm_metadata")
    if isinstance(litellm_metadata, dict) and key in litellm_metadata:
        return litellm_metadata.get(key)
    return default


def metadata_int(data: Dict[str, Any], key: str, default: int) -> int:
    value = metadata_value(data, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def optional_metadata_int(data: Dict[str, Any], key: str) -> Optional[int]:
    value = metadata_value(data, key, None)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def metadata_float(data: Dict[str, Any], key: str, default: float) -> float:
    value = metadata_value(data, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def metadata_bool(data: Dict[str, Any], key: str, default: bool) -> bool:
    value = metadata_value(data, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "available"}:
            return True
        if normalized in {"0", "false", "no", "n", "unavailable"}:
            return False
    return default


def normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,;\s]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return []
    return [
        str(item).strip().lower().replace("_", "-")
        for item in raw_items
        if str(item).strip()
    ]


def normalize_path_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,;\s]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return []
    return [str(item).strip() for item in raw_items if str(item).strip()]


def iter_capability_mode_values(data: Dict[str, Any]) -> Iterable[Any]:
    for key in (
        "capability_mode",
        "claude_code_capability_mode",
        "cc_glm52_capability_mode",
    ):
        if key in data:
            yield data.get(key)

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        for key in (
            "capability_mode",
            "claude_code_capability_mode",
            "cc_glm52_capability_mode",
        ):
            if key in metadata:
                yield metadata.get(key)
        guard_metadata = metadata.get("cc_glm52_guard")
        if isinstance(guard_metadata, dict) and "capability_mode" in guard_metadata:
            yield guard_metadata.get("capability_mode")

    extra_body = data.get("extra_body")
    if isinstance(extra_body, dict):
        for key in (
            "capability_mode",
            "claude_code_capability_mode",
            "cc_glm52_capability_mode",
        ):
            if key in extra_body:
                yield extra_body.get(key)


def has_search_intent(data: Dict[str, Any]) -> bool:
    return bool(SEARCH_INTENT_RE.search(latest_user_text(data)))


def latest_user_text(data: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("messages", "input"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in reversed(items):
            if isinstance(item, dict) and item.get("role") == "user":
                collect_text(item.get("content"), parts)
                return "\n".join(parts)
    return ""


def collect_text(value: Any, parts: List[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        if "<system-reminder>" not in value:
            parts.append(value)
        return
    if isinstance(value, list):
        for item in value:
            collect_text(item, parts)
        return
    if isinstance(value, dict):
        for key in ("text", "content", "input_text"):
            item = value.get(key)
            if isinstance(item, str):
                collect_text(item, parts)
            elif isinstance(item, list):
                collect_text(item, parts)


def maybe_enable_backend_search(
    data: Dict[str, Any],
    capability_mode: str,
    search_intent: bool,
    config: GuardConfig,
) -> bool:
    if capability_mode != "backend_fallback" or not search_intent:
        return False
    if config.search_mode == "disabled":
        return False
    ensure_litellm_web_search_tool(data)
    return True


def ensure_litellm_web_search_tool(data: Dict[str, Any]) -> None:
    tools = data.get("tools")
    if not isinstance(tools, list):
        tools = []
        data["tools"] = tools
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        function = tool.get("function")
        if name == "litellm_web_search":
            return
        if isinstance(function, dict) and function.get("name") == "litellm_web_search":
            return
    tools.append(litellm_web_search_tool())


def litellm_web_search_tool() -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to execute.",
            }
        },
        "required": ["query"],
    }
    return {
        "name": "litellm_web_search",
        "description": "Search the web through the LiteLLM backend search provider.",
        "input_schema": schema,
    }


def has_image_content(data: Dict[str, Any]) -> bool:
    for content in iter_content_values(data):
        if content_has_image(content):
            return True
    return False


def has_client_tools(data: Dict[str, Any]) -> bool:
    """Return true for executable client tools, excluding server-side tools."""
    tools = data.get("tools")
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = str(tool.get("type") or "")
        if tool.get("name") or tool_type in {"function", "custom"}:
            return True
    return False


def content_has_image(content: Any) -> bool:
    if isinstance(content, list):
        return any(block_has_image(block) for block in content)
    if isinstance(content, dict):
        return block_has_image(content)
    return False


def block_has_image(block: Any) -> bool:
    if not isinstance(block, dict):
        return False
    block_type = block.get("type")
    if block_type in IMAGE_BLOCK_TYPES:
        return True
    if "image_url" in block or ("source" in block and block_type == "image"):
        return True
    nested = block.get("content")
    return content_has_image(nested)


def iter_content_values(data: Dict[str, Any]) -> Iterable[Any]:
    for key in ("messages", "input"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "content" in item:
                    yield item.get("content")
                elif isinstance(item, list):
                    yield item
        elif isinstance(items, dict) and "content" in items:
            yield items.get("content")

    system = data.get("system")
    if system is not None:
        yield system


def strip_unsupported_content_blocks(data: Dict[str, Any]) -> int:
    stripped = 0
    for key in ("messages", "input"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("content"), list):
                content, removed = filtered_content_blocks(item["content"])
                item["content"] = content if content else ""
                stripped += removed

    if isinstance(data.get("system"), list):
        content, removed = filtered_content_blocks(data["system"])
        data["system"] = content
        stripped += removed
    return stripped


def filtered_content_blocks(blocks: List[Any]) -> Tuple[List[Any], int]:
    filtered = []
    removed = 0
    for block in blocks:
        if isinstance(block, dict) and block.get("type") in STRIPPED_CONTENT_BLOCK_TYPES:
            removed += 1
            continue
        filtered.append(block)
    return filtered, removed


def merge_context_management(data: Dict[str, Any], config: GuardConfig) -> str:
    existing = data.get("context_management")
    if not isinstance(existing, dict):
        data["context_management"] = {"edits": required_context_edits(config)}
        return "injected"

    edits = existing.get("edits")
    if not isinstance(edits, list):
        existing["edits"] = required_context_edits(config)
        return "repaired"

    changed = upsert_context_edit(
        edits,
        required_clear_tool_uses_edit(config),
        replace_fields=("trigger", "keep"),
    )
    changed = (
        upsert_context_edit(
            edits,
            required_compact_edit(config),
            replace_fields=("trigger",),
        )
        or changed
    )
    return "merged" if changed else "kept"


def required_context_edits(config: GuardConfig) -> List[Dict[str, Any]]:
    return [
        required_clear_tool_uses_edit(config),
        required_compact_edit(config),
    ]


def required_clear_tool_uses_edit(config: GuardConfig) -> Dict[str, Any]:
    return {
        "type": "clear_tool_uses_20250919",
        "trigger": {
            "type": "input_tokens",
            "value": config.clear_tool_trigger,
        },
        "keep": {
            "type": "tool_uses",
            "value": DEFAULT_TOOL_USE_KEEP,
        },
    }


def required_compact_edit(config: GuardConfig) -> Dict[str, Any]:
    return {
        "type": "compact_20260112",
        "trigger": {
            "type": "input_tokens",
            "value": config.compact_trigger,
        },
    }


def upsert_context_edit(
    edits: List[Any],
    required: Dict[str, Any],
    replace_fields: Tuple[str, ...],
) -> bool:
    required_type = required["type"]
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("type") != required_type:
            continue
        changed = False
        for field in replace_fields:
            required_value = deepcopy(required[field])
            if edit.get(field) != required_value:
                edit[field] = required_value
                changed = True
        return changed
    edits.append(deepcopy(required))
    return True


def estimate_input_tokens(data: Dict[str, Any]) -> int:
    fields = {
        key: data.get(key)
        for key in ("messages", "input", "system", "tools", "tool_choice", "prompt")
        if key in data
    }
    if not fields:
        return 0
    try:
        payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        payload = str(fields)
    return int(math.ceil(len(payload) / 4))


def context_action_for_estimate(
    input_tokens_estimated: int,
    base_action: str,
    config: GuardConfig,
) -> str:
    if input_tokens_estimated >= config.soft_limit:
        return "soft_limit_exceeded"
    if input_tokens_estimated >= config.compact_trigger:
        return "compact_configured"
    if input_tokens_estimated >= config.clear_tool_trigger:
        return "clear_tool_uses_configured"
    return base_action


def merge_audit_fields(data: Dict[str, Any], audit: Dict[str, Any]) -> None:
    metadata = data.get("metadata")
    if not isinstance(metadata, MutableMapping):
        metadata = {}
        data["metadata"] = metadata
    merge_namespaced_mapping(metadata, "cc_glm52_guard", audit)

    # Avoid creating extra_body only for audit data: many providers forward it
    # to the upstream API verbatim. If a caller already supplied a guard audit
    # namespace there, keep it in sync without adding new provider parameters.
    extra_body = data.get("extra_body")
    if isinstance(extra_body, MutableMapping):
        if "cc_glm52_guard_audit" in extra_body:
            merge_namespaced_mapping(extra_body, "cc_glm52_guard_audit", audit)


def merge_namespaced_mapping(
    target: MutableMapping[str, Any],
    key: str,
    value: Dict[str, Any],
) -> None:
    existing = target.get(key)
    if isinstance(existing, MutableMapping):
        merged = dict(existing)
        merged.update(value)
        target[key] = merged
        return
    target[key] = value


proxy_handler_instance = CCGLM52Guard()
