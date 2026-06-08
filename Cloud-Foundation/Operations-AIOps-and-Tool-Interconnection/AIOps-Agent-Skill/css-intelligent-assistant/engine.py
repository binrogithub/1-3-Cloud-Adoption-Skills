"""Core elasticity loop: collect metrics, health check, AI decision, execute scaling."""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import Settings
from metrics import build_ces_client, collect_metrics, interpret_cluster_status
from css_executor import build_css_client, get_data_node_count, scale_out, scale_in
from ai_decide import ai_decide
from cluster_health import check_cluster_health, collect_diagnosis_context, ai_diagnose

logger = logging.getLogger(__name__)


class ElasticityEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ces_client = build_ces_client(settings)
        self.css_client = build_css_client(settings)

        # Runtime state
        self.current_nodes: int = 0
        self.last_action: Optional[str] = None
        self.last_action_time: Optional[datetime] = None
        self.last_scale_out_time: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None

        # Latest snapshot for dashboard
        self.latest_metrics: dict = {}
        self.latest_decision: dict = {}
        self.latest_action_result: dict = {}
        self.latest_health: dict = {}
        self.latest_diagnosis: dict = {}
        self.latest_diagnosis_context: dict = {}
        self.history: list[dict] = []

    def _in_cooldown(self) -> bool:
        return bool(self.cooldown_until and datetime.now(timezone.utc) < self.cooldown_until)

    def _can_scale_in(self) -> bool:
        """Scale-in guard: must wait scale_in_delay_after_scale_out_minutes after last scale-out."""
        if self._in_cooldown():
            return False
        if self.last_scale_out_time is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_scale_out_time).total_seconds() / 60
        return elapsed >= self.settings.scale_in_delay_after_scale_out_minutes

    def _set_cooldown(self, minutes: int):
        self.cooldown_until = datetime.now(timezone.utc) + __import__("datetime").timedelta(minutes=minutes)

    def _detect_spike(self, metrics: dict) -> bool:
        """Multi-dimension spike detection."""
        s = self.settings
        return bool(
            metrics.get("cpu_avg", 0) >= s.cpu_spike_threshold
            or metrics.get("cpu_max", 0) >= s.cpu_spike_threshold
            or metrics.get("disk_usage_pct", 0) >= s.disk_spike_threshold
            or metrics.get("jvm_heap_max", 0) >= s.jvm_heap_spike_threshold
            or metrics.get("search_latency", 0) >= s.search_latency_spike_threshold
            or metrics.get("indexing_latency", 0) >= s.indexing_latency_spike_threshold
            or metrics.get("tp_search_queue", 0) >= s.thread_pool_queue_spike_threshold
            or metrics.get("tp_write_queue", 0) >= s.thread_pool_queue_spike_threshold
        )

    def run_once(self) -> dict:
        """One check cycle. Returns a summary dict for the dashboard."""
        s = self.settings
        now = datetime.now(timezone.utc).isoformat()

        # 1. Collect all metrics
        metrics = collect_metrics(self.ces_client, s.cluster_id)
        self.latest_metrics = metrics

        # 2. Get current node count
        try:
            self.current_nodes = get_data_node_count(self.css_client, s.cluster_id)
        except Exception as exc:
            logger.error("get_node_count_failed: %s", exc)
            self.current_nodes = 0

        # 3. Cluster health check
        try:
            health = check_cluster_health(self.css_client, self.ces_client, s.cluster_id, metrics)
        except Exception as exc:
            logger.error("health_check_failed: %s", exc)
            health = {"healthy": True, "ces_status": interpret_cluster_status(0), "api_status": "unknown", "unhealthy_nodes": [], "node_count": 0}
        self.latest_health = health

        # 4. If cluster unhealthy → diagnosis flow
        diagnosis = {}
        if not health["healthy"] and s.ai_diagnose_enabled:
            try:
                diag_ctx = collect_diagnosis_context(self.ces_client, self.css_client, s.cluster_id, metrics, health)
                self.latest_diagnosis_context = diag_ctx
                diagnosis = ai_diagnose(s, diag_ctx)
            except Exception as exc:
                logger.error("diagnosis_failed: %s", exc)
                diagnosis = {"root_cause": f"Diagnosis failed: {exc}", "severity": "warning", "suggestions": [], "auto_fix_available": False, "auto_fix_action": ""}
        self.latest_diagnosis = diagnosis

        # 5. Multi-dimension spike detection
        spike = self._detect_spike(metrics)

        # 6. Check scale-in guard
        scale_in_allowed = self._can_scale_in()

        # 7. AI decision (only if spike or scale-in possible)
        if spike or scale_in_allowed:
            decision = ai_decide(
                s, metrics, self.current_nodes, scale_in_allowed,
                self.last_action,
                self.last_action_time.isoformat() if self.last_action_time else None,
            )
        else:
            decision = {"decision": "hold", "delta": 0, "reason": "No spike and scale-in not allowed", "cooldown_minutes": 0}

        self.latest_decision = decision

        # 8. Execute
        action_result = {"action": "hold", "status": "skipped", "message": "No action"}
        if decision["decision"] == "scale_out" and not self._in_cooldown():
            delta = min(decision.get("delta", 1) or s.scale_out_step, s.scale_out_step)
            delta = min(delta, s.max_nodes - self.current_nodes)
            if delta > 0:
                action_result = scale_out(self.css_client, s, delta)
                if action_result["status"] == "success":
                    self.last_action = "scale_out"
                    self.last_action_time = datetime.now(timezone.utc)
                    self.last_scale_out_time = datetime.now(timezone.utc)
                    self._set_cooldown(s.scale_out_cooldown_minutes)

        elif decision["decision"] == "scale_in" and scale_in_allowed:
            delta = min(decision.get("delta", 1) or s.scale_in_step, s.scale_in_step)
            if delta > 0:
                action_result = scale_in(self.css_client, s, delta)
                if action_result["status"] == "success":
                    self.last_action = "scale_in"
                    self.last_action_time = datetime.now(timezone.utc)
                    self._set_cooldown(s.scale_in_cooldown_minutes)

        self.latest_action_result = action_result

        # 9. History record
        record = {
            "timestamp": now,
            "cpu_avg": metrics.get("cpu_avg", 0),
            "cpu_max": metrics.get("cpu_max", 0),
            "disk_usage_pct": metrics.get("disk_usage_pct", 0),
            "disk_io_util_max": metrics.get("disk_io_util_max", 0),
            "jvm_heap_max": metrics.get("jvm_heap_max", 0),
            "jvm_heap_avg": metrics.get("jvm_heap_avg", 0),
            "search_rate": metrics.get("search_rate", 0),
            "search_latency": metrics.get("search_latency", 0),
            "indexing_rate": metrics.get("indexing_rate", 0),
            "indexing_latency": metrics.get("indexing_latency", 0),
            "tp_search_queue": metrics.get("tp_search_queue", 0),
            "tp_write_queue": metrics.get("tp_write_queue", 0),
            "current_nodes": self.current_nodes,
            "cluster_healthy": health.get("healthy", True),
            "decision": decision["decision"],
            "reason": decision.get("reason", ""),
            "action": action_result.get("action", "hold"),
            "action_status": action_result.get("status", "skipped"),
        }
        self.history.append(record)
        if len(self.history) > 500:
            self.history = self.history[-500:]

        logger.info("cycle: %s", record)
        return record

    def trigger_diagnosis(self) -> dict:
        """Manually trigger diagnosis. Returns diagnosis result."""
        s = self.settings
        metrics = self.latest_metrics or collect_metrics(self.ces_client, s.cluster_id)
        try:
            health = check_cluster_health(self.css_client, self.ces_client, s.cluster_id, metrics)
        except Exception as exc:
            health = {"healthy": False, "ces_status": interpret_cluster_status(3), "api_status": "unknown", "unhealthy_nodes": [], "node_count": 0}
        self.latest_health = health

        diag_ctx = collect_diagnosis_context(self.ces_client, self.css_client, s.cluster_id, metrics, health)
        self.latest_diagnosis_context = diag_ctx
        diagnosis = ai_diagnose(s, diag_ctx)
        self.latest_diagnosis = diagnosis
        return diagnosis
