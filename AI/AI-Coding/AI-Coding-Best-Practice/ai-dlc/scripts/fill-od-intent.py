#!/usr/bin/env python3.12
"""Deterministic od-intent sidecar filler (PRD v9 P0-A).

Derives .od-intent.json for OpenDesign templates from facts already in
each SKILL.md frontmatter — triggers, description, category, scenario,
zh_name, platform — with zero model calls: the derivation is mechanical
so the fill is reproducible and auditable. P2-1: defaults to ALL
templates under design-templates/ and skills/ (--top N caps, richer
example.html carriers first); --synonyms merges the curated bridge
terms (lowercased, deduped, capped 8). --dry-run prints what would
be written.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
from plan import _parse_frontmatter  # noqa: E402

STOP = {"the", "a", "an", "and", "or", "for", "with", "of", "to", "in",
        "on", "page", "site", "website", "best", "optional", "this",
        "that", "from", "your", "you", "is", "are", "as", "by", "it"}

PAGE_TYPE_HINTS = ("landing", "waitlist", "coming-soon", "portfolio",
                   "blog", "docs", "dashboard", "pricing", "about",
                   "contact", "ecommerce", "checkout", "profile",
                   "settings", "login", "signup", "error", "gallery",
                   "hero", "faq", "legal", "status", "changelog",
                   "onboarding", "search", "email", "cover", "resume")


def _page_types(fm: dict, name: str) -> list[str]:
    """Page-type tokens from triggers/category/name — a trigger phrase
    like 'waitlist page' contributes 'waitlist'; a name like
    'blog-post' contributes 'blog-post'."""
    out: set = set()
    for t in (fm.get("triggers") or []):
        for w in re.findall(r"[a-z0-9-]+", str(t).lower()):
            if w in PAGE_TYPE_HINTS:
                out.add(w)
    for src in (fm.get("category", ""), fm.get("od", {}).get("scenario")
                if isinstance(fm.get("od"), dict) else fm.get("scenario",
                                                              ""), name):
        for w in re.findall(r"[a-z0-9-]+", str(src).lower()):
            if w in PAGE_TYPE_HINTS:
                out.add(w)
    hyph = name.lower()
    for hint in PAGE_TYPE_HINTS:
        if hint in hyph:
            out.add(hint)
    if not out:
        # fallback: the template's own name is its page-type identity —
        # 'audio-jingle' or 'clinical-case-report' are page types too
        out.add(hyph)
    return sorted(out)[:6]


def _token_family(fm: dict, name: str) -> list[str]:
    words: list[str] = []
    for src in (name.replace("-", " "), str(fm.get("description", ""))):
        for w in re.findall(r"[a-z0-9]{3,}", src.lower()):
            if w not in STOP:
                words.append(w)
    seen: set = set()
    fam = [w for w in words if not (w in seen or seen.add(w))]
    return fam[:6]


def derive(fm: dict, dirname: str) -> dict:
    od = fm.get("od") if isinstance(fm.get("od"), dict) else {}
    locale = "zh" if fm.get("zh_name") else "en"
    platform = str(fm.get("platform") or od.get("platform") or "")
    framework = ("react" if "react" in platform.lower()
                 else "vue" if "vue" in platform.lower()
                 else "html-css")
    return {
        "template": dirname,
        "intent_page_types": _page_types(fm, dirname),
        "token_family": _token_family(fm, dirname),
        "co_appear": [],
        "locale": [locale],
        "framework": [framework],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/opt/open-design",
                    help="OpenDesign root — scans design-templates/ and "
                         "skills/ (P2-1: full coverage, both roots)")
    ap.add_argument("--top", type=int, default=None,
                    help="cap N templates (default: all)")
    ap.add_argument("--synonyms", default=None, type=Path,
                    help="curated synonyms JSON ({templates: {dir: "
                         "[terms]}}); terms are lowercased, deduped and "
                         "capped at 8 per template")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    syn: dict = {}
    if a.synonyms:
        data = json.loads(a.synonyms.read_text(encoding="utf-8"))
        syn = data.get("templates", data)
    tdirs: list = []
    for sub in ("design-templates", "skills"):
        base = root / sub
        if base.is_dir():
            tdirs += [d for d in base.iterdir()
                      if d.is_dir() and (d / "SKILL.md").is_file()]
    # deterministic priority for --top: templates carrying example.html
    # first (richer derivation signal), then the rest by name
    tdirs.sort(key=lambda d: (not (d / "example.html").is_file(), d.name))
    picked = tdirs if a.top is None else tdirs[: a.top]
    written = 0
    for d in picked:
        fm = _parse_frontmatter((d / "SKILL.md").read_text(
            encoding="utf-8", errors="replace"))
        meta = derive(fm, d.name)
        if not meta["intent_page_types"]:
            print(f"skip {d.name}: no derivable page types")
            continue
        if d.name in syn:
            merged, seen = [], set()
            for t in syn[d.name]:
                t = str(t).strip().lower()
                if t and t not in seen:
                    seen.add(t)
                    merged.append(t)
            meta["synonyms"] = merged[:8]
        out = d / ".od-intent.json"
        if a.dry_run:
            print(d.name, json.dumps(meta, ensure_ascii=False))
            written += 1
            continue
        out.write_text(json.dumps(meta, indent=2, ensure_ascii=False)
                       + "\n", encoding="utf-8")
        written += 1
    print(f"{'would write' if a.dry_run else 'wrote'} {written} "
          f"sidecars under {root}"
          + (f" (+synonyms for {sum(1 for d in picked if d.name in syn)})"
             if a.synonyms else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
