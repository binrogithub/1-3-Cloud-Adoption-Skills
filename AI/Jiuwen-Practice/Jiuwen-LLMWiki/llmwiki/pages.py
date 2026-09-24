"""Wiki page model: frontmatter + "Compiled truth" + append-only "Timeline"."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from .config import NAMESPACES

SLUG_RE = re.compile(r"^(%s)/[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$" % "|".join(NAMESPACES))
SLUG_IN_TEXT_RE = re.compile(r"\b(?:%s)/[a-z0-9][a-z0-9._/-]*[a-z0-9]" % "|".join(NAMESPACES))


def valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug)) and ".." not in slug


@dataclass
class Page:
    slug: str
    title: str = ""
    type: str = ""
    compiled_truth: str = ""
    timeline: list[dict] = field(default_factory=list)   # [{"date", "text"}], newest first
    links: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    last_verified: str = ""
    extra: dict = field(default_factory=dict)

    # ---- rendering -------------------------------------------------------
    def to_markdown(self) -> str:
        fm = {
            "slug": self.slug, "title": self.title, "type": self.type,
            "last_verified": self.last_verified, "sources": self.sources,
            "links": self.links, **self.extra,
        }
        lines = ["---"]
        for k, v in fm.items():
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        lines += ["---", "", f"# {self.title or self.slug}", "", "## Compiled truth", "",
                  self.compiled_truth.strip(), "", "## Timeline", ""]
        for e in self.timeline:
            lines.append(f"- {e.get('date', '')} — {e.get('text', '').strip()}")
        return "\n".join(lines).rstrip() + "\n"

    # ---- parsing ---------------------------------------------------------
    @classmethod
    def from_markdown(cls, slug: str, text: str) -> "Page":
        """Accepts our JSON-per-line frontmatter AND gbrain's normalised YAML block
        lists (E0-S5 finding: gbrain rewrites `links: ["a"]` to `links:\n  - a`)."""
        fm: dict = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                body = parts[2]
                pending_key = None
                fold_key = None
                for line in parts[1].splitlines():
                    stripped = line.strip()
                    if fold_key is not None and line[:1] in (" ", "\t") and stripped:
                        cur = fm.get(fold_key) or ""
                        fm[fold_key] = (cur + " " + stripped) if cur else stripped
                        continue
                    fold_key = None
                    if stripped.startswith("- ") and pending_key is not None:
                        item = stripped[2:].strip().strip("'\"")
                        if isinstance(fm[pending_key], list):
                            fm[pending_key].append(item)
                        continue
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k, v = k.strip(), v.strip()
                    if v in (">-", ">", "|", "|-"):   # gbrain folds long scalars this way
                        fm[k] = ""
                        fold_key = k
                        continue
                    if v == "":
                        fm[k] = []                    # block-list key pending its items
                        pending_key = k
                        continue
                    try:
                        fm[k] = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        fm[k] = v.strip("'\"")
                    pending_key = None
        ct = _section(body, "Compiled truth")
        tl_raw = _section(body, "Timeline")
        if ct is None and tl_raw is None:        # page not in our layout: keep all as truth
            ct = re.sub(r"^#\s.*\n", "", body.strip(), count=1)
        timeline = []
        for line in (tl_raw or "").splitlines():
            m = re.match(r"^\s*-\s*(\d{4}-\d{2}-\d{2})\s*[—-]+\s*(.*)$", line)
            if m:
                timeline.append({"date": m.group(1), "text": m.group(2)})
        known = {"slug", "title", "type", "last_verified", "sources", "links"}
        return cls(
            slug=slug,
            title=str(fm.get("title", "")),
            type=str(fm.get("type", "")),
            compiled_truth=(ct or "").strip(),
            timeline=timeline,
            links=list(fm.get("links") or []),
            sources=list(fm.get("sources") or []),
            last_verified=str(fm.get("last_verified", "")),
            extra={k: v for k, v in fm.items() if k not in known},
        )

    def is_stale(self, days: int, today: date | None = None) -> bool:
        try:
            lv = date.fromisoformat(self.last_verified)
        except ValueError:
            return True
        return ((today or date.today()) - lv).days > days


def _section(body: str, name: str) -> str | None:
    m = re.search(r"^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(name), body, re.M | re.S)
    return m.group(1).strip() if m else None
