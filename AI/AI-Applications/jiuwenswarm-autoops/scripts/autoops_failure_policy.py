#!/usr/bin/env python3
"""Bounded failure classification shared by AutoOps adapters and the ledger."""
from __future__ import annotations

from typing import Any


RETRY_CLASSES = {
    "none",
    "transient_read",
    "authorization",
    "input",
    "external_unknown",
    "verification",
    "permanent",
}

RETRYABLE_READ_CODES = {
    "TIMEOUT", "REQUEST_TIMEOUT", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503",
    "HTTP_504", "DATA_SOURCE_TIMEOUT", "DATA_SOURCE_BUSY",
}
AUTHORIZATION_CODES = {
    "AUTHORIZATION_REQUIRED", "AUTHORIZATION_DENIED", "AUTHORIZATION_CONSUMED",
    "PERMISSION_DENIED", "PREAUTHORIZATION_REQUIRED", "PREAUTHORIZATION_DENIED",
}


def classify_failure(*, status: Any = "", error_code: Any = "") -> str:
    """Return a policy class; this function never claims a failed action succeeded."""
    normalized_status = str(status or "").upper()
    normalized_error = str(error_code or "").upper()
    if normalized_error == "RESULT_UNKNOWN" or normalized_status == "UNKNOWN":
        return "external_unknown"
    if normalized_status in {"SUCCEEDED", "COMPLETED", "SUCCESS", "NO_CHANGE", "OK"}:
        return "none"
    if normalized_error in AUTHORIZATION_CODES or "AUTHORIZATION" in normalized_error \
            or normalized_error.startswith("PERMISSION_"):
        return "authorization"
    if normalized_error in {"INPUT_ERROR", "INVALID_INPUT", "INVALID", "JOB_NOT_ALLOWED",
                            "IDEMPOTENCY_CONFLICT", "TARGET_UNSUPPORTED"}:
        return "input"
    if normalized_error in RETRYABLE_READ_CODES or normalized_status in {"RUNNING", "WAITING"}:
        return "transient_read"
    if normalized_status in {"PARTIAL", "VERIFYING", "EMPTY", "INCONCLUSIVE", "TRACE_INCOMPLETE"} \
            or "VERIF" in normalized_error:
        return "verification"
    if not normalized_status and not normalized_error:
        return "none"
    return "permanent"


def can_retry_without_replan(retry_class: str) -> bool:
    """Only bounded read-only transient failures may be retried automatically."""
    return retry_class == "transient_read"


def can_replan(retry_class: str) -> bool:
    """Replanning is never a way around authorization or an unknown write result."""
    return retry_class in {"transient_read", "verification"}
