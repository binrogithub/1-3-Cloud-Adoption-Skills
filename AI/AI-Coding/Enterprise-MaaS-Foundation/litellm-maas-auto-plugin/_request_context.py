"""RequestContext — one immutable request context from admission to response
completion (PRD-plugin-convergence §7.1).

Replaces the scattered residency mechanisms:
  - smart_router._cross_border_blocked (bool)
  - sidecar._residency_ctx (contextvar)
  - sidecar._residency_store (module-level mutable dict)
  - data["metadata"]["_residency_request_id"] stashing

The context is constructed once by the Router from the authenticated key and
request data, then passed explicitly to Sidecar and Tool Guard operations.
ContextVar may provide convenience within one callback, but it is not the
source of truth and is not used as durable cross-hook storage.
"""

import hashlib
import os
from typing import Any, Optional

# dataclasses is stdlib in 3.7+; provide a fallback for 3.6.
try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls=None, **kw):
        def wrap(c):
            return c
        return wrap(cls) if cls is not None else wrap


# ── Residency policy (canonical, shared by Router and Sidecar) ───────────────

class ResidencyPolicy:
    """Canonical residency decision. Two modes: allow (default) and china-only.

    Derived from the authenticated key/team context, never from client request
    metadata. A server-side env default (SMART_ROUTER_DEFAULT_DATA_RESIDENCY)
    makes protection default-on for china-only deployments.
    """

    ALLOW = "allow"
    CHINA_ONLY = "china-only"

    __slots__ = ("mode",)

    def __init__(self, mode: str = "") -> None:
        self.mode = mode if mode in (self.ALLOW, self.CHINA_ONLY) else self.ALLOW

    @property
    def is_china_only(self) -> bool:
        return self.mode == self.CHINA_ONLY

    @property
    def allows_egress(self) -> bool:
        return self.mode == self.ALLOW

    def check_egress(self, kind: str) -> None:
        """Raise SidecarPolicyDenied if egress is not allowed. Imported lazily
        to avoid a circular dependency at module load."""
        if not self.allows_egress:
            try:
                from sidecar import SidecarPolicyDenied, SIDECAR_POLICY_DENIALS
                SIDECAR_POLICY_DENIALS.labels(kind=kind).inc()
                raise SidecarPolicyDenied(
                    "sidecar egress denied by residency policy (%s) for kind=%s"
                    % (self.mode, kind)
                )
            except ImportError:
                pass  # sidecar not loaded — deny silently in test/dev

    @classmethod
    def from_key(cls, user_api_key_dict: Any) -> "ResidencyPolicy":
        """Derive the residency policy from the authenticated key.

        Reads server-controlled key tags/metadata (not client request metadata).
        A key tagged 'residency:china-only' or with metadata.data_residency ==
        'china-only' gets the china-only policy. A server env default
        SMART_ROUTER_DEFAULT_DATA_RESIDENCY=china-only applies regardless of key.
        """
        # Server env default (strongest — cannot be weakened by key or client).
        if os.getenv("SMART_ROUTER_DEFAULT_DATA_RESIDENCY", "").lower() == "china-only":
            return cls(cls.CHINA_ONLY)

        if user_api_key_dict is None:
            return cls(cls.ALLOW)

        # LiteLLM UserAPIKeyAuth: tags is a list of strings, metadata is a dict.
        tags = getattr(user_api_key_dict, "tags", None)
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.lower() == "residency:china-only":
                    return cls(cls.CHINA_ONLY)

        metadata = getattr(user_api_key_dict, "metadata", None)
        if isinstance(metadata, dict):
            residency = metadata.get("data_residency")
            if isinstance(residency, str) and residency.lower() == "china-only":
                return cls(cls.CHINA_ONLY)
        elif metadata is not None:
            # Pydantic model: metadata is an attribute, not a dict key.
            residency = getattr(metadata, "data_residency", None)
            if isinstance(residency, str) and residency.lower() == "china-only":
                return cls(cls.CHINA_ONLY)

        # Also support plain-dict keys (tests).
        if isinstance(user_api_key_dict, dict):
            tags = user_api_key_dict.get("tags")
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and tag.lower() == "residency:china-only":
                        return cls(cls.CHINA_ONLY)
            metadata = user_api_key_dict.get("metadata")
            if isinstance(metadata, dict):
                residency = metadata.get("data_residency")
                if isinstance(residency, str) and residency.lower() == "china-only":
                    return cls(cls.CHINA_ONLY)

        return cls(cls.ALLOW)

    def __repr__(self) -> str:
        return "ResidencyPolicy(%r)" % self.mode


# ── RequestContext (immutable, one per request) ──────────────────────────────

class RequestContext:
    """Immutable request context passed explicitly through the request and
    response lifecycle (PRD-plugin-convergence §7.1).

    Contains only bounded identifiers and decisions required later:
      - request_id: internal request ID for log/metric correlation;
      - residency: canonical residency mode (allow/china-only);
      - mainline_model: the GLM-5.2 mainline model string;
      - has_tools: whether the request declared tools;
      - has_images: whether the request contains image content;
      - session_anchor: bounded session anchor for fingerprinting.
    """

    __slots__ = ("request_id", "residency", "mainline_model", "has_tools", "has_images", "session_anchor")

    def __init__(self, request_id: str, residency: "ResidencyPolicy",
                 mainline_model: str, has_tools: bool, has_images: bool,
                 session_anchor: str = "") -> None:
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "residency", residency)
        object.__setattr__(self, "mainline_model", mainline_model)
        object.__setattr__(self, "has_tools", has_tools)
        object.__setattr__(self, "has_images", has_images)
        object.__setattr__(self, "session_anchor", session_anchor)

    @property
    def cross_border_blocked(self) -> bool:
        """True if cross-provider fallback must be suppressed (china-only)."""
        return self.residency.is_china_only


def _detect_has_images(data: Any) -> bool:
    """Quick check: does the request contain image content?"""
    if not isinstance(data, dict):
        return False
    messages = data.get("messages") or data.get("input") or []
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
                # Check tool_result nested images.
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        for ib in inner:
                            if isinstance(ib, dict) and ib.get("type") in ("image", "image_url"):
                                return True
    return False


def _session_anchor(data: Any) -> str:
    """Bounded session anchor for fingerprinting (same as sidecar._session_anchor)."""
    if not isinstance(data, dict):
        return ""
    messages = data.get("messages") or data.get("input") or []
    if not isinstance(messages, list) or not messages:
        return ""
    first = messages[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if isinstance(content, str):
        return content[:512]
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return (block.get("text") or "")[:512]
    return ""


def build_context(
    user_api_key_dict: Any,
    data: Any,
    mainline_model: str,
) -> RequestContext:
    """Construct the RequestContext from the authenticated key and request data.

    Called once by the Router in async_pre_call_hook.
    """
    import os as _os
    request_id = ""
    if isinstance(data, dict):
        meta = data.get("metadata")
        if isinstance(meta, dict):
            request_id = meta.get("request_id") or _os.urandom(16).hex()
        else:
            request_id = _os.urandom(16).hex()

    return RequestContext(
        request_id=request_id,
        residency=ResidencyPolicy.from_key(user_api_key_dict),
        mainline_model=mainline_model,
        has_tools=isinstance(data, dict) and bool(data.get("tools")),
        has_images=_detect_has_images(data),
        session_anchor=_session_anchor(data),
    )
