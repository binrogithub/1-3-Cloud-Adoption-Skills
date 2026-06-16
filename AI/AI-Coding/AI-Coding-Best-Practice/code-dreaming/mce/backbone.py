"""Thin governed wrapper over the vendored Mem0 backbone.

First-party glue only. ALL memory storage, extract->update, vector search, and
scoping is done by `vendor/mem0` (Apache-2.0) — this module just adds the
enterprise gate the PRD requires and that Mem0 does not: a privacy-before-write
filter and required scope metadata (PRD-design §8). It does not reimplement any
Mem0 capability.

    from mce.backbone import Backbone
    bb = Backbone.from_config("assets/mem0.config.yaml")
    bb.capture("fallback after health-check failure", scope=Scope(org="acme", ...))
    bb.recall("routing fallback", scope=Scope(org="acme", ...), max_tokens=2000)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

# Reject obvious secrets before any write (PRD-design §8.4). Conservative on
# purpose: a false positive blocks a write; a miss leaks a secret into memory.
_SECRET_RE = re.compile(
    r"(sk-proj-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|password\s*[:=]\s*\S+|api[_-]?key\s*[:=]\s*\S+|Bearer\s+[A-Za-z0-9._-]{20,})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Scope:
    """Required tenant/app/user/run isolation fields (PRD-design §8.3)."""
    org: str
    app: str = ""
    user: str = ""
    run: str = ""


class PrivacyError(ValueError):
    """Raised when a candidate write contains secret-like content."""


class Backbone:
    def __init__(self, memory):
        self._m = memory  # a vendored mem0.Memory instance

    @classmethod
    def from_config(cls, config_path: str) -> "Backbone":
        import yaml
        from mem0 import Memory  # vendored, Apache-2.0
        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)
        return cls(Memory.from_config(cfg))

    # --- write path: privacy gate, then delegate to Mem0 add (extract->update) ---
    def capture(self, text: str, scope: Scope, **metadata):
        if _SECRET_RE.search(text):
            raise PrivacyError("refused: secret-like content (PRD-design §8.4)")
        meta = {k: v for k, v in asdict(scope).items() if v}
        meta.update(metadata)
        return self._m.add(text, user_id=scope.user or scope.org, metadata=meta)

    # --- read path: delegate to Mem0 search, enforce scope + token budget ---
    def recall(self, query: str, scope: Scope, top_k: int = 5, max_tokens: int = 2000):
        identity = scope.user or scope.org
        try:
            hits = self._m.search(query, filters={"user_id": identity}, top_k=top_k)
        except TypeError:
            # Older Mem0 shims and tests used top-level user_id/limit.
            hits = self._m.search(query, user_id=identity, limit=top_k)
        results = hits.get("results", hits) if isinstance(hits, dict) else hits
        scoped = [r for r in results if _same_org(r, scope.org)]
        return _pack_budget(scoped, max_tokens)


def _same_org(record, org: str) -> bool:
    meta = record.get("metadata") or {}
    return meta.get("org", org) == org  # tenant isolation (PRD-design §8.3)


def _pack_budget(records, max_tokens: int):
    """Greedy top-k packing under a rough token budget (~4 chars/token)."""
    out, used = [], 0
    for r in records:
        cost = len(str(r.get("memory", r))) // 4 + 1
        if used + cost > max_tokens:
            break
        out.append(r)
        used += cost
    return out
