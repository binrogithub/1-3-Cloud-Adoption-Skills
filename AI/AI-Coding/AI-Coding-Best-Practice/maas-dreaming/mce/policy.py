"""Writeback policy for verified dream candidates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from mce.backbone import Scope


@dataclass(frozen=True)
class WritebackCandidate:
    section: str
    text: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    scope_kind: str = "project"
    source_path: str = ""


@dataclass(frozen=True)
class WritebackDecision:
    candidate: WritebackCandidate
    allowed: bool
    action: str
    reason: str
    candidate_hash: str
    metadata: dict[str, object] = field(default_factory=dict)


def candidate_hash(candidate: WritebackCandidate, scope: Scope) -> str:
    basis = "\n".join(
        [
            candidate.section.strip().lower(),
            candidate.text.strip(),
            scope.org.strip(),
            scope.app.strip(),
            scope.user.strip(),
            scope.run.strip(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def decide_writeback(
    candidate: WritebackCandidate,
    scope: Scope,
    seen_hashes: set[str],
    *,
    allow_global: bool = False,
) -> WritebackDecision:
    h = candidate_hash(candidate, scope)
    metadata: dict[str, object] = {
        "source": "dream-writeback",
        "section": candidate.section,
        "candidate_hash": h,
        "evidence_ids": list(candidate.evidence_ids),
        "verified_status": candidate.status,
        "scope_kind": candidate.scope_kind,
    }
    if candidate.source_path:
        metadata["source_path"] = candidate.source_path

    status = candidate.status.lower()
    text_lower = candidate.text.lower()
    if h in seen_hashes:
        return WritebackDecision(candidate, False, "skip", "duplicate candidate hash", h, metadata)
    if candidate.scope_kind == "global" and not allow_global:
        return WritebackDecision(candidate, False, "skip", "global candidate requires --allow-global", h, metadata)
    if status == "contradicted":
        return WritebackDecision(candidate, False, "skip", "contradicted candidate", h, metadata)
    if status not in {"verified", "repo-verified"}:
        return WritebackDecision(candidate, False, "skip", f"status is {candidate.status}", h, metadata)
    if "[unverified:" in text_lower or "[unverified]" in text_lower:
        return WritebackDecision(candidate, False, "skip", "text contains unverified marker", h, metadata)
    if not candidate.text.strip():
        return WritebackDecision(candidate, False, "skip", "empty candidate text", h, metadata)
    return WritebackDecision(candidate, True, "write", "eligible verified candidate", h, metadata)

