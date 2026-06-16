#!/usr/bin/env python3
"""Deterministic signal taxonomy for review-only dream evidence.

Ported from the targeted-grep approach in ``references/grandamenium_dream-skill``.
The point is cheap, bounded classification: instead of re-reading whole
transcripts, the host agent gets told *where* the high-value signals are
(corrections, preferences, decisions, recurring pain) so it can look there
first. This module is pure and dependency-free; it never writes memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Only records with these roles are scanned for signals. System and attachment
# records (including SKILL.md content loaded as context) are excluded so they
# cannot generate self-referential false positives.
SCANNABLE_ROLES: frozenset[str] = frozenset({"human", "user", "assistant"})

# Ordered highest-priority first. Corrections outrank everything because a user
# correction is the strongest durable signal; recurring pain is weakest.
SIGNAL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "corrections": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bactually\b",
            r"\bno,",
            r"\bthat(?:'s| is| was) wrong\b",
            r"\byou(?:'re| are| were) wrong\b",
            r"\bwrong (?:approach|answer|solution|output|result)\b",
            r"\bincorrect\b",
            r"\bnot right\b",
            r"\bthat'?s not\b",
            r"\bstop doing\b",
            r"\bdon'?t do\b",
            r"\bi said\b",
            r"\bi meant\b",
            r"\bcorrection\b",
        )
    ],
    "preferences": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bi prefer\b",
            r"\balways use\b",
            r"\bnever use\b",
            r"\bi like\b",
            r"\bi don'?t like\b",
            r"\bfrom now on\b",
            r"\bgoing forward\b",
            r"\bremember that\b",
            r"\bkeep in mind\b",
            r"\bmake sure to\b",
            r"\bdefault to\b",
        )
    ],
    "decisions": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\blet'?s go with\b",
            r"\bi decided\b",
            r"\bwe'?re using\b",
            r"\bthe plan is\b",
            r"\bswitch to\b",
            r"\bmove to\b",
            r"\bwe agreed\b",
            r"\bdecision\b",
        )
    ],
    "recurring": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bagain\b",
            r"\bevery time\b",
            r"\bkeep forgetting\b",
            r"\bas usual\b",
            r"\bsame as before\b",
            r"\blike last time\b",
            r"\bwe always\b",
            r"\bthe usual\b",
        )
    ],
}

# Priority order used when a single record matches more than one class.
SIGNAL_CLASSES: tuple[str, ...] = tuple(SIGNAL_PATTERNS.keys())


@dataclass(frozen=True)
class SignalHit:
    evidence_id: str
    signal_class: str
    role: str
    timestamp: str
    preview: str


def classify(text: str) -> list[str]:
    """Return every signal class ``text`` matches, in priority order."""
    if not text:
        return []
    return [name for name, patterns in SIGNAL_PATTERNS.items()
            if any(p.search(text) for p in patterns)]


def primary_class(text: str) -> str | None:
    """Return the single highest-priority class ``text`` matches, or ``None``."""
    matches = classify(text)
    return matches[0] if matches else None


def scan_records(
    records: Iterable,
    limit: int = 20,
    *,
    require_role: frozenset[str] = SCANNABLE_ROLES,
) -> list[SignalHit]:
    """Classify bounded evidence ``records`` into prioritized signal hits.

    ``records`` are duck-typed ``EvidenceRecord``-like objects exposing
    ``evidence_id``, ``role``, ``timestamp`` and ``preview``. Records whose
    ``role`` is not in ``require_role`` are skipped entirely; this prevents
    system prompts and attachment records (e.g. SKILL.md content) from
    generating self-referential false positives. Hits are returned
    highest-priority class first, capped at ``limit``.
    """
    hits: list[SignalHit] = []
    for record in records:
        role = getattr(record, "role", "") or ""
        if role not in require_role:
            continue
        cls = primary_class(getattr(record, "preview", "") or "")
        if cls is None:
            continue
        hits.append(
            SignalHit(
                evidence_id=getattr(record, "evidence_id", "?"),
                signal_class=cls,
                role=getattr(record, "role", "") or "-",
                timestamp=getattr(record, "timestamp", "") or "unknown",
                preview=getattr(record, "preview", ""),
            )
        )
    order = {name: i for i, name in enumerate(SIGNAL_CLASSES)}
    hits.sort(key=lambda h: order.get(h.signal_class, len(order)))
    return hits[:limit]


def class_counts(hits: Iterable[SignalHit]) -> dict[str, int]:
    counts = {name: 0 for name in SIGNAL_CLASSES}
    for hit in hits:
        counts[hit.signal_class] = counts.get(hit.signal_class, 0) + 1
    return counts
