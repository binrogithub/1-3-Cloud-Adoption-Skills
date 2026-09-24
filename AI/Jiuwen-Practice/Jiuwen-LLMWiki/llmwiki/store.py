"""Wiki store adapters. GBrain is used strictly through its public CLI (no code changes).

Two backends share one interface:
  * GBrainStore – shells out to the `gbrain` CLI (command templates in llmwiki.toml).
  * FileStore   – plain Markdown directory with keyword search; the M1 fallback while
                  no embedding model is available (PRD B-1), and the test double.

Every page written through GBrainStore is also mirrored to FileStore, so the wiki is
always inspectable/diffable on disk even if the brain DB is lost.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from .config import Config
from .pages import SLUG_IN_TEXT_RE, Page, valid_slug


class StoreError(RuntimeError):
    pass


class FileStore:
    def __init__(self, root: Path):
        self.root = root

    def _file(self, slug: str) -> Path:
        if not valid_slug(slug):
            raise StoreError(f"invalid slug: {slug!r}")
        return self.root / f"{slug}.md"

    def get(self, slug: str) -> Page | None:
        f = self._file(slug)
        return Page.from_markdown(slug, f.read_text(encoding="utf-8")) if f.exists() else None

    def put(self, page: Page) -> None:
        f = self._file(page.slug)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".md.tmp")
        tmp.write_text(page.to_markdown(), encoding="utf-8")
        tmp.replace(f)

    def delete(self, slug: str) -> None:
        """PRD V7 cascade: remove a page file outright (page left with no statements)."""
        self._file(slug).unlink(missing_ok=True)

    def slugs(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(str(p.relative_to(self.root).with_suffix("")) for p in self.root.rglob("*.md"))

    def search(self, q: str, k: int) -> list[str]:
        """BM25-style keyword ranking over title + body. Accent-insensitive, EN/ES/PT tokens."""
        q_terms = _tokens(q)
        if not q_terms:
            return []
        docs = {s: _tokens(s.replace("/", " ") + " " + (self.root / f"{s}.md").read_text(encoding="utf-8"))
                for s in self.slugs()}
        n = len(docs) or 1
        avg = sum(len(t) for t in docs.values()) / n if docs else 1
        df = Counter(t for toks in docs.values() for t in set(toks))
        scores = {}
        for slug, toks in docs.items():
            tf = Counter(toks)
            s = 0.0
            for t in set(q_terms):
                if t in tf:
                    idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                    s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(toks) / avg))
            if s > 0:
                scores[slug] = s
        return [s for s, _ in sorted(scores.items(), key=lambda x: -x[1])[:k]]


class GBrainStore:
    def __init__(self, cfg: Config):
        self.cfg = cfg.gbrain
        self.full_cfg = cfg                       # for resolving relative env paths
        self.mirror = FileStore(cfg.path(cfg.gbrain.files_dir))
        self._mcp = None                          # PRD V6: persistent MCP transport

    def _mcp_client(self):
        from .gbrain_client import GBrainMCP
        if self._mcp is None:
            env = {k: (self.full_cfg.path(v) if isinstance(v, str) and k.endswith(("_DIR", "_HOME")) else v)
                   for k, v in self.cfg.env.items()}
            self._mcp = GBrainMCP(self.cfg.bin, env=env, timeout_s=self.cfg.timeout_s)
        return self._mcp

    @property
    def use_mcp(self) -> bool:
        return self.cfg.backend == "gbrain-mcp"

    def _run(self, template: list[str], stdin: str | None = None, **kw) -> str:
        argv = [a.format(bin=self.cfg.bin, **kw) for a in template]
        env = dict(os.environ)
        env.update({k: self.full_cfg.path(v) if isinstance(v, str) and k.endswith(("_DIR", "_HOME")) else v
                    for k, v in self.cfg.env.items()})
        try:
            p = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                               timeout=self.cfg.timeout_s, env=env)
        except FileNotFoundError as e:
            raise StoreError(f"gbrain not installed: {argv[0]}") from e
        except subprocess.TimeoutExpired as e:
            raise StoreError(f"gbrain timed out: {' '.join(argv[:2])}") from e
        if p.returncode != 0:
            raise StoreError(f"gbrain {argv[1]} rc={p.returncode}: {p.stderr.strip()[:300]}")
        return p.stdout

    def search(self, q: str, k: int) -> list[str]:
        if self.use_mcp:
            try:
                return [s for s in self._mcp_client().search(q, k) if valid_slug(s)][:k]
            except Exception as e:
                raise StoreError(f"gbrain-mcp search failed: {e}")
        out = self._run(self.cfg.search_cmd, q=q)
        return _slugs_from_output(out)[:k]

    def get(self, slug: str) -> Page | None:
        if not valid_slug(slug):
            raise StoreError(f"invalid slug: {slug!r}")
        if self.use_mcp:
            # The glue is the sole writer, so the mirror is always current and a
            # local read costs nothing; only brain-only pages go over MCP (E4-S5).
            page = self.mirror.get(slug)
            if page is not None:
                return page
            try:
                data = self._mcp_client().get_page(slug)
            except Exception as e:
                # a brand-new page (empty wiki / first compile) is None, not an error
                if "not found" in str(e).lower() or "page_not_found" in str(e).lower():
                    return None
                raise StoreError(f"gbrain-mcp get failed: {e}")
            if not data:
                return None
            return _page_from_mcp(slug, data)
        try:
            out = self._run(self.cfg.get_cmd, slug=slug)
        except StoreError as e:
            if "not found" in str(e).lower():
                return None
            raise
        text = _unwrap_json_page(out)
        return Page.from_markdown(slug, text) if text.strip() else None

    def put(self, page: Page) -> None:
        if self.use_mcp:
            try:
                self._mcp_client().put_page(page.slug, page.to_markdown())
            except Exception as e:
                raise StoreError(f"gbrain-mcp put failed: {e}")
            self.mirror.put(page)
            return
        self._run(self.cfg.put_cmd, stdin=page.to_markdown(), slug=page.slug)
        self.mirror.put(page)

    def delete(self, slug: str) -> None:
        """PRD V7 cascade: `gbrain delete <slug>` (CLI — no MCP delete probed) + mirror."""
        self._run(self.cfg.delete_cmd, slug=slug)
        self.mirror.delete(slug)

    def slugs(self) -> list[str]:
        """E4-S5: pages known to gbrain, not only the local mirror.

        gbrain `list` prints "slug<TAB>type<TAB>date<TAB>title" lines; the mirror may lag
        behind (manual gbrain writes) or run ahead (mirror written before a failed put is
        impossible — put writes gbrain first). Union keeps lint honest.
        """
        slugs = set(self.mirror.slugs())
        if self.use_mcp:
            try:
                slugs |= {p.get("slug", "") for p in self._mcp_client().list_pages()
                          if p.get("slug")}
            except Exception:
                pass           # lint must survive a brain that is briefly down
        elif self.cfg.list_cmd:
            try:
                slugs |= set(_slugs_from_output(self._run(self.cfg.list_cmd)))
            except StoreError:
                pass
        return sorted(slugs)


def _page_from_mcp(slug: str, data: dict) -> Page:
    """Build a Page from an MCP get_page record (probed shape: metadata fields +
    compiled_truth markdown). Timeline/versions are approximated conservatively."""
    truth = data.get("compiled_truth") or ""
    return Page(slug=slug,
                title=str(data.get("title", "")),
                type=str(data.get("type", "")),
                compiled_truth=truth,
                timeline=[{"date": e.get("date", ""), "text": e.get("text", "")}
                          for e in (data.get("timeline") or []) if isinstance(e, dict)],
                links=[l for l in (data.get("links") or []) if isinstance(l, str)],
                sources=[sid for sid in (data.get("sources") or []) if isinstance(sid, str)],
                last_verified=str(data.get("last_verified", "")))


def open_store(cfg: Config):
    if cfg.gbrain.backend == "files":
        return FileStore(cfg.path(cfg.gbrain.files_dir))
    if cfg.gbrain.backend in ("gbrain", "gbrain-mcp"):
        return GBrainStore(cfg)
    raise StoreError(f"unknown gbrain.backend {cfg.gbrain.backend!r}")


# ---- helpers --------------------------------------------------------------

_ACCENTS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")
_STOP = set("the a an of in on for to and or is are what which how de la el los las en y o que "
            "es un una para por con do da dos das no na e o um uma com qual quais como".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower().translate(_ACCENTS))
            if t not in _STOP and len(t) > 1]


def _slugs_from_output(out: str) -> list[str]:
    """Accept JSON (list of objects with slug/path) or free text; keep order, dedupe."""
    found: list[str] = []
    try:
        data = json.loads(out)
        items = data if isinstance(data, list) else data.get("results") or data.get("pages") or []
        for it in items:
            s = it.get("slug") or it.get("path") if isinstance(it, dict) else it
            if isinstance(s, str):
                found.append(s.removesuffix(".md"))
    except (json.JSONDecodeError, AttributeError):
        found = SLUG_IN_TEXT_RE.findall(out)
    seen, result = set(), []
    for s in found:
        if s not in seen and valid_slug(s):
            seen.add(s)
            result.append(s)
    return result


def _unwrap_json_page(out: str) -> str:
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out
    if isinstance(data, dict):
        for key in ("markdown", "content", "body", "text"):
            if isinstance(data.get(key), str):
                return data[key]
    return out
