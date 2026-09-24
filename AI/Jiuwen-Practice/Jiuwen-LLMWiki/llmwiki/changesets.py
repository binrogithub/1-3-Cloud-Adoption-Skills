"""Change sets: the ONLY write path into the wiki (PRD D-2).

The llmwiki role proposes page edits as JSON; this module validates them mechanically,
stores them for review, and on approval merges them into GBrain pages. Agents never
write to GBrain themselves.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from . import grounding
from .config import PROTECTED_NAMESPACES
from .pages import Page, valid_slug

MAX_PAGES = 10


class ChangeSetError(RuntimeError):
    pass


def parse_role_output(text: str) -> dict:
    """Extract the JSON object from the role's compile output (tolerates code fences/prose)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ChangeSetError("compile output contains no JSON object")
    try:
        data = json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise ChangeSetError(f"compile output is not valid JSON: {e}") from e
    if not isinstance(data.get("pages"), list):
        raise ChangeSetError("compile output has no 'pages' list")
    return data


def validate(data: dict, source_id: str, source_text: str, terms: list[str],
             url_domains: list[str], load_source=None,
             term_synonyms: dict[str, list[str]] | None = None) -> list[dict]:
    """Return a list of per-page problems. Empty list == mechanically valid.

    Facts kept from an existing page cite older sources ([S:<old id>]); those are resolved
    through `load_source(id) -> text` so they are checked against their own snapshot.
    Timeline entries must cite the NEW source only (the timeline records this change).
    """
    problems: list[dict] = []
    pages = data.get("pages", [])
    if len(pages) > MAX_PAGES:
        problems.append({"slug": "*", "problem": f"{len(pages)} pages > limit {MAX_PAGES}"})
    new_only = {source_id: source_text}
    for p in pages:
        slug = p.get("slug", "")
        if not valid_slug(slug):
            problems.append({"slug": slug, "problem": "invalid slug / namespace"})
            continue
        truth = p.get("compiled_truth", "")
        docs = dict(new_only)
        for sid in set(re.findall(r"\[S:([0-9a-f]{16})\]", truth)) - {source_id}:
            if load_source is not None:
                try:
                    docs[sid] = load_source(sid)
                except Exception:
                    pass          # stays unresolved → reported as unknown_citation
        checks = [(truth, docs)] + [(e.get("text", ""), new_only) for e in p.get("timeline", [])]
        for t, d in checks:
            v = grounding.verify(t, d, cite_prefix="S", terms=terms, url_domains=url_domains,
                                 term_synonyms=term_synonyms)
            for iss in v.issues:
                problems.append({"slug": slug, "problem": f"{iss.reason}: {iss.claim!r}",
                                 "unit": iss.unit})
        for e in p.get("timeline", []):
            try:
                date.fromisoformat(e.get("date", ""))
            except ValueError:
                problems.append({"slug": slug, "problem": f"bad timeline date {e.get('date')!r}"})
    return problems


class ChangeSetStore:
    def __init__(self, root: Path):
        self.root = root

    def create(self, source_meta: dict, data: dict, problems: list[dict]) -> dict:
        cs = {
            "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": {k: source_meta.get(k) for k in ("id", "ref", "kind", "licence", "fetched_at")},
            "pages": data.get("pages", []),
            "conflicts": data.get("conflicts", []),
            "problems": problems,
            "status": "invalid" if problems else "pending",
            "protected": sorted({p.get("slug", "").split("/")[0] for p in data.get("pages", [])}
                                & set(PROTECTED_NAMESPACES)),
            "history": [],
        }
        self._save(cs)
        return cs

    def get(self, cs_id: str) -> dict:
        if not re.fullmatch(r"[0-9]{14}-[0-9a-f]{6}", cs_id):
            raise ChangeSetError(f"bad change set id {cs_id!r}")
        f = self.root / f"{cs_id}.json"
        if not f.exists():
            raise ChangeSetError(f"unknown change set {cs_id}")
        return json.loads(f.read_text())

    def list(self, status: str | None = None) -> list[dict]:
        if not self.root.exists():
            return []
        items = [json.loads(p.read_text()) for p in sorted(self.root.glob("*.json"))]
        return [c for c in items if status is None or c["status"] == status]

    def set_status(self, cs: dict, status: str, actor: str, note: str = "") -> None:
        cs["status"] = status
        cs["history"].append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "status": status, "actor": actor, "note": note})
        self._save(cs)

    def _save(self, cs: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{cs['id']}.json.tmp"
        tmp.write_text(json.dumps(cs, indent=2, ensure_ascii=False))
        tmp.replace(self.root / f"{cs['id']}.json")


def merge(existing: Page | None, proposed: dict, source_id: str, today: str) -> Page:
    """Apply one proposed page onto the existing one. Timeline is append-only."""
    page = existing or Page(slug=proposed["slug"])
    if proposed.get("title"):
        page.title = proposed["title"]
    if proposed.get("type"):
        page.type = proposed["type"]
    if proposed.get("compiled_truth", "").strip():
        page.compiled_truth = proposed["compiled_truth"].strip()
    old = {(e["date"], e["text"]) for e in page.timeline}
    new_entries = [e for e in proposed.get("timeline", []) if (e["date"], e["text"]) not in old]
    page.timeline = sorted(new_entries + page.timeline, key=lambda e: e["date"], reverse=True)
    page.links = sorted(set(page.links) | {l for l in proposed.get("links", []) if valid_slug(l)})
    if source_id not in page.sources:
        page.sources.append(source_id)
    page.last_verified = today
    return page
