"""Independent CSS engine and business verification helpers.

The module is deliberately provider-neutral. It consumes observations supplied
by the configured data-plane adapter and never changes CSS or OpenSearch.
"""
from __future__ import annotations

from typing import Any


def verify_observation(observation: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    engine = observation.get("engine", {})
    business = observation.get("business", {})
    required_engine = bool(config.get("require_engine_health", True))
    require_business = bool(config.get("require_business", True))
    reasons: list[str] = []
    engine_status = "PASSED"
    if required_engine:
        if not isinstance(engine, dict) or engine.get("status") not in {"green", "PASSED", "HEALTHY"}:
            engine_status = "UNVERIFIED" if not engine else "FAILED"
            reasons.append("ENGINE_HEALTH_NOT_VERIFIED")
        for field in ("relocating_shards", "initializing_shards", "unassigned_shards"):
            if field not in engine or engine.get(field) is None:
                engine_status = "UNVERIFIED" if engine_status != "FAILED" else engine_status
                reasons.append(f"ENGINE_{field.upper()}_UNKNOWN")
        if engine.get("relocating_shards", 0) != 0 or engine.get("initializing_shards", 0) != 0:
            engine_status = "PENDING"
            reasons.append("SHARDS_NOT_STABLE")
        if engine.get("unassigned_shards", 0) != 0:
            engine_status = "FAILED"
            reasons.append("UNASSIGNED_SHARDS")
    business_status = "PASSED"
    if require_business:
        if not business or business.get("status") in {None, "UNVERIFIED", "UNKNOWN", "NOT_CONFIGURED"}:
            business_status = "UNVERIFIED"
            reasons.append("BUSINESS_PROBE_NOT_CONFIGURED")
        elif business.get("status") not in {"PASSED", "VERIFIED", "SUCCEEDED"}:
            business_status = "FAILED"
            reasons.append("BUSINESS_SLO_FAILED")
        elif business.get("sample_count", 0) < int(config.get("minimum_samples", 1)):
            business_status = "UNVERIFIED"
            reasons.append("INSUFFICIENT_SAMPLES")
        elif business.get("error_rate") is None or business.get("p95_latency_ms") is None:
            business_status = "UNVERIFIED"
            reasons.append("BUSINESS_SLO_METRICS_MISSING")
        elif business["error_rate"] > float(config.get("max_error_rate", 0.01)):
            business_status = "FAILED"
            reasons.append("BUSINESS_ERROR_RATE_EXCEEDED")
        elif business["p95_latency_ms"] > float(config.get("max_p95_latency_ms", 5000)):
            business_status = "FAILED"
            reasons.append("BUSINESS_P95_LATENCY_EXCEEDED")
    if engine_status == "FAILED" or business_status == "FAILED":
        status = "DEGRADED"
    elif engine_status != "PASSED" or business_status != "PASSED":
        status = "UNVERIFIED"
    else:
        status = "PASSED"
    return {
        "status": status,
        "engine_verification_status": engine_status,
        "business_verification_status": business_status,
        "reason_codes": reasons,
    }


def evaluate_window(samples: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate a stable post-change business window without inventing data."""
    config = config or {}
    minimum = int(config.get("minimum_samples", 1))
    if len(samples) < minimum:
        return {"status": "UNVERIFIED", "reason_codes": ["INSUFFICIENT_SAMPLES"], "sample_count": len(samples)}
    statuses = [verify_observation(sample, config) for sample in samples]
    failed = [item for item in statuses if item["status"] == "DEGRADED"]
    pending = [item for item in statuses if item["status"] != "PASSED"]
    if failed:
        status = "DEGRADED"
    elif pending:
        status = "UNVERIFIED"
    else:
        status = "PASSED"
    return {
        "status": status,
        "sample_count": len(samples),
        "reason_codes": sorted({reason for item in statuses for reason in item["reason_codes"]}),
        "engine_verification_status": "PASSED" if all(item["engine_verification_status"] == "PASSED" for item in statuses) else "UNVERIFIED",
        "business_verification_status": "PASSED" if all(item["business_verification_status"] == "PASSED" for item in statuses) else "UNVERIFIED",
    }


def evaluate_probe_window(samples: list[dict[str, Any]], config: dict[str, Any] | None = None,
                          *, now_epoch: float | None = None) -> dict[str, Any]:
    """Require explicit application assertions, enough observations and elapsed stability."""
    config = config or {}
    minimum = int(config.get("minimum_samples", 10))
    required_seconds = int(config.get("stable_business_minutes", 10)) * 60
    if len(samples) < minimum:
        return {"status": "UNVERIFIED", "reason_codes": ["INSUFFICIENT_SAMPLES"],
                "sample_count": len(samples), "required_samples": minimum}
    timestamps = [float(sample.get("observed_epoch", 0)) for sample in samples]
    span = max(timestamps) - min(timestamps) if timestamps else 0
    if span < required_seconds:
        return {"status": "UNVERIFIED", "reason_codes": ["BUSINESS_STABILITY_WINDOW_INSUFFICIENT"],
                "sample_count": len(samples), "window_seconds": max(0, span),
                "required_window_seconds": required_seconds}
    failures = [sample for sample in samples if sample.get("status") != "PASSED"]
    error_rate = len(failures) / max(1, len(samples))
    latencies = sorted(float(sample["latency_ms"]) for sample in samples
                       if isinstance(sample.get("latency_ms"), (int, float)))
    if not latencies:
        return {"status": "UNVERIFIED", "reason_codes": ["BUSINESS_LATENCY_SAMPLES_MISSING"],
                "sample_count": len(samples), "window_seconds": span}
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
    reasons = []
    if error_rate > float(config.get("max_error_rate", 0.01)):
        reasons.append("BUSINESS_ERROR_RATE_EXCEEDED")
    if p95 > float(config.get("max_p95_latency_ms", 5000)):
        reasons.append("BUSINESS_P95_LATENCY_EXCEEDED")
    return {"status": "DEGRADED" if reasons else "PASSED", "sample_count": len(samples),
            "window_seconds": span, "error_rate": error_rate, "p95_latency_ms": round(p95, 2),
            "required_samples": minimum, "required_window_seconds": required_seconds,
            "max_error_rate": float(config.get("max_error_rate", 0.01)),
            "max_p95_latency_ms": float(config.get("max_p95_latency_ms", 5000)),
            "reason_codes": reasons}
