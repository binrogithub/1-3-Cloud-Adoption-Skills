"""Glue pipelines: ask / compile / apply / lint.

Division of labour (PRD §6):
  glue (this code)  – retrieval from GBrain, evidence packing, verification, all writes
  llmwiki role      – language work only (answering, compiling), no tools
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import changesets, grounding, jiuwen
from .config import PROTECTED_NAMESPACES, ROLE_CURATOR, ROLE_ADMIN, ROLE_RANK, Config
from .pages import Page
from .sources import SourceStore
from .store import open_store

_INDEX_TTL_S = 300          # term/confidential index; invalidated eagerly on every write


# The main agent needs "delegate to the sub-agent"; deepseek-class roles read that
# sentence literally and disclaim ("I don't have a sub-agent"). The note tells the
# addressee itself to just do the work. glm-5.2 ignores it either way.
_DISPATCH_NOTE = ("\nNOTE to the `{role}` sub-agent: the delegation sentence above is not for "
                  "you — you ARE the addressee; perform the task directly.")


def _retract_statements(text: str, sid: str) -> tuple[str, int]:
    """Remove the sentences citing [S:sid] from a compiled-truth body (PRD V7 R7-2).
    Line structure and every other sentence stay byte-identical; returns the new
    body and how many statements were removed."""
    marker = f"[S:{sid}]"
    out: list[str] = []
    removed = 0
    for line in text.split("\n"):
        if marker not in line:
            out.append(line)
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        keep = [s for s in parts if marker not in s]
        removed += len(parts) - len(keep)
        if keep:
            out.append(" ".join(keep))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip(), removed


def detect_lang(q: str) -> str:
    """Keyword heuristic, EN/ES/PT-BR (GL-A1). Markers chosen so no marker is shared."""
    low = f" {q.lower()} "
    pt = sum(low.count(w) for w in (" não ", " você", " qual ", " quais ", "ção", " região",
                                    " preço", " como ", " quanto", "disponível", "disponível",
                                    "armazenamento", " é um", " é uma", "obrigad", "ã", "ç"))
    es = sum(low.count(w) for w in (" qué ", " cuál", " cuánto", "ción", " región",
                                    " precio", " cómo", "diferencia", "disponible", "gracias",
                                    "para que", "ñ", "¿", "¡"))
    if pt > es and pt:
        return "pt-BR"
    if es:
        return "es"
    return "en"


@dataclass
class AskResult:
    question: str
    lang: str
    answer: str
    status: str                     # grounded | partially_verified | no_citations | abstained | no_claims | error
    citations: list[str] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    error: str = ""
    raw_answer: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: float | None = None
    elapsed_s: float = 0.0
    evidence_sha256: str = ""       # E5-S10: integrity anchor of the pack actually sent
    evidence_chars: int = 0
    filtered_confidential: list[str] = field(default_factory=list)
    conversation_id: str = ""          # PRD V8 multi-turn: session + turn recorded
    turn: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class Wiki:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = open_store(cfg)
        self.sources = SourceStore(cfg.runtime_dir / "sources")
        self.changes = changesets.ChangeSetStore(cfg.runtime_dir / "changesets")
        self.log = cfg.runtime_dir / "logs" / "ask.jsonl"
        self.audit_log = cfg.runtime_dir / "logs" / "audit.jsonl"
        self._index_at = 0.0
        self._index: dict = {}
        self._io_lock = threading.RLock()      # short critical sections only: never held
        # across a model call (E5/NFR-2: asks must run concurrently)

    # ---- index: terms + confidentiality (E4-S6, E10-S3) ----------------------
    def invalidate_index(self) -> None:
        with self._io_lock:
            self._index_at = 0.0

    def _ensure_index(self) -> dict:
        """One pass over the wiki per TTL window: claim terms, confidential pages,
        source metadata. Without this, every ask costs one gbrain CLI call per
        regions/compliance/services page (E4-S6)."""
        with self._io_lock:
            if self._index and time.monotonic() - self._index_at < _INDEX_TTL_S:
                return self._index
        term_ns = set(self.cfg.ask.term_namespaces)
        terms: set[str] = set()
        confidential: set[str] = set()
        src_meta = {m["id"]: m for m in self.sources.list()}
        conf_ids = {sid for sid, m in src_meta.items() if m.get("licence") == "confidential"}
        for slug in self.store.slugs():
            p = self.store.get(slug)
            if p is None:
                continue
            if slug.split("/")[0] in term_ns and p.title:
                terms.add(p.title)
            if conf_ids & set(p.sources):
                confidential.add(slug)
        gf = self.cfg.path(self.cfg.ask.glossary_terms_file)
        glossary: list[str] = []
        if gf.exists():
            glossary = [l.strip() for l in gf.read_text(encoding="utf-8").splitlines()
                        if l.strip() and not l.startswith("#")]
            terms |= set(glossary)
        self._index = {"terms": sorted(terms), "confidential": sorted(confidential),
                       "sources": src_meta,
                       "term_syn": self._term_synonyms(sorted(terms), glossary)}
        self._index_at = time.monotonic()
        return self._index

    def terms(self) -> list[str]:
        """Checked claim terms: region, certification and service names known to the
        wiki, plus the glossary list (E6-S7: fabricated service names must fail)."""
        return self._ensure_index()["terms"]

    def term_synonyms(self) -> dict[str, list[str]]:
        """Full title -> [title, abbreviations] (glossary pairs + '(ABBR)' in titles)."""
        return self._ensure_index().get("term_syn", {})

    @staticmethod
    def _term_synonyms(terms: list[str], glossary: list[str]) -> dict[str, list[str]]:
        syn: dict[str, list[str]] = {}
        for t in terms:
            m = re.search(r"\(([^)]{2,12})\)\s*$", t)
            if m:                                  # 'Object Storage Service (OBS)' -> 'OBS'
                syn[t] = [t, m.group(1)]
        for i, line in enumerate(glossary):        # glossary pairs: full name then abbreviation
            if i + 1 < len(glossary) and re.fullmatch(r"[A-Z0-9-]{2,12}", glossary[i + 1]) \
               and len(line) > len(glossary[i + 1]) + 4:
                syn.setdefault(line, [line]).append(glossary[i + 1])
        return syn

    def confidential_slugs(self) -> list[str]:
        return self._ensure_index()["confidential"]

    def page_list(self) -> list[dict]:
        """Sidebar listing: [{slug,title,type,last_verified}], parallel fetch, 60s cache
        (invalidated on approve/reject/write). Without this every page load costs one
        gbrain CLI call per slug — seconds of dead time in the studio sidebar."""
        now = time.monotonic()
        with self._io_lock:
            if getattr(self, "_plist", None) and now - self._plist_at < 60:
                return self._plist
        slugs = self.store.slugs()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="llmwiki-list") as pool:
            pages = list(pool.map(self.store.get, slugs))
        items = [{"slug": s, "title": p.title if p else "", "type": p.type if p else "",
                  "last_verified": p.last_verified if p else ""}
                 for s, p in zip(slugs, pages)]
        with self._io_lock:
            self._plist, self._plist_at = items, now
        return items

    def _invalidate_plist(self) -> None:
        self._plist = None

    def _source_meta(self, sid: str) -> dict | None:
        return self._ensure_index()["sources"].get(sid)

    # ---- evidence ------------------------------------------------------------
    def _page_stale(self, slug: str, page: Page) -> bool:
        days = (self.cfg.ask.pricing_stale_after_days if slug.startswith(("pricing/",))
                else self.cfg.ask.stale_after_days)
        if page.is_stale(days):
            return True
        if slug.startswith("pricing/"):
            # E3-S6: pricing freshness also follows the newest source snapshot age
            fetched = [m.get("fetched_at", "") for m in map(self._source_meta, page.sources) if m]
            if fetched:
                newest = max(fetched)[:10]
                try:
                    if (date.today() - date.fromisoformat(newest)).days > days:
                        return True
                except ValueError:
                    pass
        return False

    def _evidence(self, slugs: list[str], allow_confidential: bool = True
                  ) -> tuple[str, dict[str, str], list[str]]:
        blocks, docs, stale = [], {}, []
        budget = self.cfg.ask.max_evidence_chars
        blocked = self.confidential_slugs() if not allow_confidential else []
        # Parallel page loads: with the gbrain backend each get is a CLI call, and
        # serial top_k=6 fetches cost 2-4s of dead time before the model starts.
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="llmwiki-get") as pool:
            pages = list(pool.map(self.store.get, slugs))
        for slug, page in zip(slugs, pages):
            if page is None:
                continue
            if not allow_confidential and slug in blocked:
                continue                      # E10-S3: filtered BEFORE the pack, never after
            is_stale = self._page_stale(slug, page)
            if is_stale:
                stale.append(slug)
            body = page.to_markdown()
            if len(body) > budget:
                break
            budget -= len(body)
            docs[slug] = body
            # The PACK the model re-quotes into the Agent tool call is trimmed to
            # title + compiled truth: frontmatter/timeline/links are write-path
            # metadata the answerer cannot use, and every token of pack is ~1 ms of
            # invisible dispatch time. Verification still uses the full page (docs).
            pack_body = f"# {page.title or page.slug}\n\n{page.compiled_truth.strip()}"
            blocks.append(f"<<<PAGE slug={slug} stale={'true' if is_stale else 'false'}>>>\n"
                          f"{pack_body}\n<<<END PAGE>>>")
        return "\n\n".join(blocks), docs, stale

    # ---- ask ---------------------------------------------------------------
    def ask(self, question: str, lang: str | None = None, role: str = "reader",
            stream_cb=None, on_retrieval=None, history: list[dict] | None = None,
            conversation_id: str = "", turn: int = 0) -> AskResult:
        """PRD V8: history (last verified turns) widens retrieval and travels into
        the prompt as context-only — grounding rules stay identical to V2."""
        t0 = time.monotonic()
        lang = lang or detect_lang(question)
        res = AskResult(question=question, lang=lang, answer="", status="error",
                        conversation_id=conversation_id, turn=turn)
        turns = [t for t in (history or [])[-3:] if t.get("q")]
        try:
            # R8-2: prior questions widen the query; pages the prior answers cited
            # join the candidates so pronoun follow-ups still retrieve the topic.
            rq = " ".join([t["q"] for t in turns[-2:]] + [question])
            slugs = self.store.search(rq, self.cfg.ask.top_k)
            for m in re.finditer(r"\[W:([a-z0-9][a-z0-9/._-]*)\]",
                                 " ".join(t.get("a", "") for t in turns)):
                cited = m.group(1)
                if cited not in slugs and self.store.get(cited) is not None:
                    slugs.append(cited)
            slugs = slugs[:self.cfg.ask.top_k + 2]
        except Exception as e:                                   # FR-Q5/GL-G4: fail loud, never invent
            res.error = f"retrieval_failed: {e}"
            return self._finish(res, t0)
        if ROLE_RANK.get(role, 0) < ROLE_RANK[ROLE_CURATOR]:
            blocked = set(self.confidential_slugs())
            res.filtered_confidential = [s for s in slugs if s in blocked]
            slugs = [s for s in slugs if s not in blocked]        # GL-S2: filter before retrieval
        pack, docs, stale = self._evidence(slugs)
        res.retrieved, res.stale = list(docs), stale
        if on_retrieval is not None:
            try:
                on_retrieval(list(docs), stale, list(res.filtered_confidential))
            except Exception:
                pass
        if not docs:
            res.status, res.answer = "abstained", _not_found(lang)
            return self._finish(res, t0)
        res.evidence_sha256 = hashlib.sha256(pack.encode("utf-8")).hexdigest()[:16]
        res.evidence_chars = len(pack)
        conv_block = ""
        if turns:
            lines = ["CONVERSATION SO FAR (context only, NOT evidence — never cite it):"]
            for i, t in enumerate(turns, 1):
                lines.append(f"Q{i}: {t['q']}")
                lines.append(f"A{i}: {(t.get('a') or '')[:800]}")
            lines.append("Resolve pronouns/ellipses in the newest QUESTION from this "
                         "conversation; every factual claim still needs [W:slug] "
                         "citations from the EVIDENCE PACK only.")
            conv_block = "\n".join(lines) + "\n\n"
        prompt = (f"LLMWIKI_TASK: answer\nDelegate this whole request to the `{self.cfg.jiuwen.role}` "
                  "sub-agent verbatim and return its output verbatim."
                  + _DISPATCH_NOTE.format(role=self.cfg.jiuwen.role) + "\n\n"
                  f"ANSWER_LANGUAGE: {lang}\n{conv_block}QUESTION: {question}\n\nEVIDENCE PACK:\n{pack}\n")
        try:
            run = jiuwen.run(self.cfg, prompt, on_event=stream_cb)
        except jiuwen.JiuwenError as e:
            res.error = str(e)
            return self._finish(res, t0)
        res.raw_answer = run.content
        res.input_tokens, res.output_tokens, res.ttft_ms = run.input_tokens, run.output_tokens, run.ttft_ms
        v = grounding.verify(run.content, docs, cite_prefix="W", terms=self.terms(),
                             url_domains=self.cfg.ask.url_domains,
                             term_synonyms=self.term_synonyms())
        res.status, res.citations = v.status, v.cited
        res.issues = [asdict(i) for i in v.issues]
        if v.status == "no_citations":
            res.answer = _not_found(lang)                        # FR-Q4: never serve uncited facts
        else:
            res.answer = v.redacted_text
        return self._finish(res, t0)

    def _finish(self, res: AskResult, t0: float) -> AskResult:
        res.elapsed_s = round(time.monotonic() - t0, 2)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        rec = {k: v for k, v in asdict(res).items() if k != "raw_answer"}
        rec["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._io_lock:
            with self.log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._rotate_log()
        return res

    def _rotate_log(self) -> None:
        """E5-S8/OQ-4: retention switch for ask.jsonl. Runs every 128 writes."""
        days = self.cfg.ask.log_retention_days
        if not days or not self.log.exists():
            return
        lines = self.log.read_text(encoding="utf-8").splitlines()
        if not lines or len(lines) % 128:
            return
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        keep = []
        for line in lines:
            try:
                at = datetime.fromisoformat(json.loads(line).get("at", "")).timestamp()
            except ValueError:
                keep.append(line)
                continue
            if at >= cutoff:
                keep.append(line)
        if len(keep) != len(lines):
            tmp = self.log.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
            tmp.replace(self.log)

    # ---- audit (GL-S3) -------------------------------------------------------
    def audit(self, action: str, actor: str, **kw) -> None:
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        rec = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "action": action, "actor": actor, **kw}
        with self._io_lock:
            with self.audit_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- compile -------------------------------------------------------------
    def compile(self, source_id: str) -> dict:
        meta, text = self.sources.get(source_id)
        related = self.store.search(text[:2000], self.cfg.ask.top_k)
        pack, _, _ = self._evidence(related)
        prompt = (f"LLMWIKI_TASK: compile\nDelegate this whole request to the `{self.cfg.jiuwen.role}` "
                  "sub-agent verbatim and return its output verbatim."
                  + _DISPATCH_NOTE.format(role=self.cfg.jiuwen.role) + "\n\n"
                  f"<<<SOURCE id={meta['id']} kind={meta['kind']} fetched_at={meta['fetched_at']}>>>\n"
                  f"{text}\n<<<END SOURCE>>>\n\nEVIDENCE PACK (existing pages):\n{pack or '(none)'}\n")
        run = jiuwen.run(self.cfg, prompt)
        try:
            data = changesets.parse_role_output(run.content)
            problems = changesets.validate(
                data, meta["id"], text, self.terms(), self.cfg.ask.url_domains,
                load_source=lambda sid: self.sources.get(sid)[1],
                term_synonyms=self.term_synonyms())
        except changesets.ChangeSetError as e:
            data, problems = {"pages": []}, [{"slug": "*", "problem": str(e)}]
        cs = self.changes.create(meta, data, problems)
        self.audit("compile", "llmwiki", changeset=cs["id"], source=source_id,
                   status=cs["status"])
        if (self.cfg.review.auto_approve_nonprotected and cs["status"] == "pending"
                and self._auto_approvable(cs)):
            self.approve(cs["id"], self.cfg.review.auto_approve_actor,
                         note="policy: non-protected, conflict-free, public source (FR-C4)")
            cs = self.changes.get(cs["id"])                     # report post-policy state
        return cs

    def _auto_approvable(self, cs: dict) -> bool:
        """FR-C4/E7-S7: public source, no protected namespace, no conflicts, and every
        page is new or timeline/link-only (compiled truth unchanged)."""
        if cs["protected"] or cs["conflicts"]:
            return False
        if (self._source_meta(cs["source"]["id"]) or {}).get("licence") != "public":
            return False
        for p in cs["pages"]:
            existing = self.store.get(p.get("slug", ""))
            if existing is None:
                continue
            if (p.get("compiled_truth", "").strip()
                    and p["compiled_truth"].strip() != existing.compiled_truth.strip()):
                return False
        return True

    # ---- apply ---------------------------------------------------------------
    def approve(self, cs_id: str, actor: str, today: str | None = None, note: str = "") -> list[str]:
        cs = self.changes.get(cs_id)
        if cs["status"] != "pending":
            raise changesets.ChangeSetError(f"change set {cs_id} is {cs['status']}, not pending")
        if not actor or actor == "llmwiki" or actor == self.cfg.jiuwen.role:
            raise changesets.ChangeSetError("approval needs a named human actor")
        today = today or date.today().isoformat()
        written = []
        for proposed in cs["pages"]:
            page = changesets.merge(self.store.get(proposed["slug"]), proposed, cs["source"]["id"], today)
            self.store.put(page)
            written.append(page.slug)
        self.changes.set_status(cs, "applied", actor, note=",".join(written) + (f" ({note})" if note else ""))
        self.invalidate_index()
        self._invalidate_plist()
        self.audit("approve", actor, changeset=cs_id, pages=written)
        return written

    def reject(self, cs_id: str, actor: str, note: str) -> None:
        cs = self.changes.get(cs_id)
        self.changes.set_status(cs, "rejected", actor, note)
        self._invalidate_plist()
        self.audit("reject", actor, changeset=cs_id, note=note)

    # ---- source delete (PRD V5) + cascade (PRD V7) -----------------------------
    def delete_source(self, sid: str, cascade: bool = False,
                      actor: str = "upload-autoflow") -> dict:
        """Delete an L1 snapshot. Uncited: snapshot + upload file go, pending change
        sets for it are rejected (V5). Cited without cascade: blocked (the caller
        maps this to 409). cascade=True retracts every statement citing the source
        and deletes pages left without statements — one change set, D-5 intact."""
        meta, _ = self.sources.get(sid)
        cited = []
        for slug in self.store.slugs():
            p = self.store.get(slug)
            if p is not None and sid in p.sources:
                cited.append(slug)
        if cited and not cascade:
            return {"blocked": True, "pages": sorted(cited)}
        pages_report = self._retract_source(sid, meta, actor) if cited else []
        dropped = []
        for cs in self.changes.list("pending"):
            if cs.get("source", {}).get("id") == sid:
                self.changes.set_status(cs, "rejected", actor,
                                        note="source deleted (PRD V5 delete flow)")
                dropped.append(cs["id"])
        for suffix in (".json", ".txt"):
            (self.sources.root / f"{sid}{suffix}").unlink(missing_ok=True)
        ref = meta.get("ref", "")
        if ref.startswith(str(self.cfg.runtime_dir / "uploads")):
            Path(ref).unlink(missing_ok=True)
        elif ref.startswith("uploads/"):
            (self.cfg.runtime_dir / ref).unlink(missing_ok=True)
        self.invalidate_index()
        self._invalidate_plist()
        self.audit("source_delete_cascade" if cascade else "source_delete", actor,
                   source=sid, pages=pages_report, rejected_changesets=dropped)
        return {"deleted": sid, "cascade": bool(cascade), "pages": pages_report,
                "rejected_changesets": dropped}

    def _retract_source(self, sid: str, meta: dict, actor: str) -> list[dict]:
        """Statement-granular retraction (R7-2/R7-3): sentences carrying [S:sid] go,
        survivors byte-identical; a page with no statements left is deleted."""
        today = date.today().isoformat()
        actions: list[dict] = []
        cs_pages: list[dict] = []
        for slug in sorted(self.store.slugs()):
            page = self.store.get(slug)
            if page is None or sid not in page.sources:
                continue
            truth, removed = _retract_statements(page.compiled_truth, sid)
            note = (f"source {meta.get('ref', sid)} deleted; {removed} statement(s) "
                    f"citing it retracted (delete-cascade)")
            if truth:
                page.compiled_truth = truth
                page.sources = [s for s in page.sources if s != sid]
                page.timeline = [{"date": today, "text": note}] + page.timeline
                self.store.put(page)
                actions.append({"slug": slug, "action": "retracted",
                                "statements_removed": removed})
                cs_pages.append({"slug": slug, "compiled_truth": truth,
                                 "timeline": [{"date": today, "text": note}]})
            else:
                self.store.delete(slug)
                actions.append({"slug": slug, "action": "page-deleted",
                                "statements_removed": removed})
                cs_pages.append({"slug": slug, "deleted": True,
                                 "timeline": [{"date": today, "text": note}]})
        cs = self.changes.create(meta, {"pages": cs_pages}, [])
        self.changes.set_status(cs, "applied", actor,
                                note="delete-cascade: " + ",".join(a["slug"] for a in actions))
        return actions

    # ---- manual web edit (PRD V9) ----------------------------------------------
    def edit_page(self, slug: str, compiled_truth: str, actor: str,
                  title: str = "", allow_protected: bool = False) -> dict:
        """Edit compiled_truth through the same gate as model compiles (D-5):
        the text is grounded against the L1 snapshots it cites; one change set
        records the attempt; only clean (and authorized) edits write the page."""
        page = self.store.get(slug)
        if page is None:
            raise changesets.ChangeSetError(f"unknown page {slug}")
        if not actor or actor in ("llmwiki", self.cfg.jiuwen.role):
            raise changesets.ChangeSetError("edit needs a named human actor")
        if slug.split("/")[0] in PROTECTED_NAMESPACES and not allow_protected:
            raise changesets.ChangeSetError(
                f"{slug} is in a protected namespace; a curator must make this edit")
        text = compiled_truth.strip()
        today = date.today().isoformat()
        cited = sorted(set(re.findall(r"\[S:([0-9a-f]{16})\]", text)))
        docs: dict[str, str] = {}
        problems: list[dict] = []
        for c in cited:
            try:
                docs[c] = self.sources.get(c)[1]
            except Exception:
                problems.append({"slug": slug, "problem": f"unknown_citation: {c}",
                                 "unit": ""})
        v = grounding.verify(text, docs, cite_prefix="S", terms=self.terms(),
                             url_domains=self.cfg.ask.url_domains,
                             term_synonyms=self.term_synonyms())
        problems += [{"slug": slug, "problem": f"{i.reason}: {i.claim}",
                      "unit": (i.unit or "")[:240]} for i in v.issues]
        note = f"manual web edit by {actor}"
        data = {"pages": [{"slug": slug, "title": title or page.title,
                           "compiled_truth": text,
                           "timeline": [{"date": today, "text": note}]}]}
        meta = {"id": "manual", "ref": f"web-edit:{slug}", "kind": "edit",
                "licence": "public",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        cs = self.changes.create(meta, data, problems)
        if problems:
            self.audit("page_edit_rejected", actor, changeset=cs["id"], slug=slug,
                       problems=len(problems))
            return {"changeset": cs, "applied": False, "problems": problems}
        # direct write, like delete-cascade: merge() would add the pseudo source id
        page.compiled_truth = text
        if title:
            page.title = title
        page.timeline = [{"date": today, "text": f"{note} (change set {cs['id']})"}] + page.timeline
        page.sources = sorted(set(page.sources) | set(cited))
        page.last_verified = today
        self.store.put(page)
        self.changes.set_status(cs, "applied", actor, note=f"{slug} (web edit)")
        self.invalidate_index()
        self._invalidate_plist()
        self.audit("page_edit_applied", actor, changeset=cs["id"], slug=slug)
        return {"changeset": self.changes.get(cs["id"]), "applied": True, "problems": []}

    # ---- file-back (UC-7 / GL-C8) ---------------------------------------------
    def fileback(self, question: str | None = None) -> dict:
        """Turn the latest grounded answer into an faq/ change set (E7-S8).

        [W:slug] citations are resolved to the first L1 source of that page, so the
        filed answer stays mechanically verifiable against real snapshots.
        """
        if not self.log.exists():
            raise changesets.ChangeSetError("no ask log yet")
        rec = None
        for line in reversed(self.log.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            if r.get("status") == "grounded" and (question is None or r["question"] == question):
                rec = r
                break
        if rec is None:
            raise changesets.ChangeSetError("no grounded ask found"
                                            + (f" for {question!r}" if question else ""))
        docs: dict[str, str] = {}
        slug_to_sid: dict[str, str] = {}
        answer = rec["answer"]
        for slug in rec["citations"]:
            page = self.store.get(slug)
            if page is None or not page.sources:
                raise changesets.ChangeSetError(f"cited page {slug} has no sources to cite")
            sid = page.sources[0]
            slug_to_sid[slug] = sid
            docs[sid] = self.sources.get(sid)[1]

        def _sub(m: re.Match) -> str:
            return f"[S:{slug_to_sid.get(m.group(1), m.group(1))}]"

        truth = re.sub(r"\[W:([^\]\s]+)\]", _sub, answer)
        words = [w for w in re.findall(r"[a-z0-9]+", rec["question"].lower())][:8]
        slug = "faq/" + ("-".join(words) or "untitled")[:70].rstrip("-")
        new_sid = next(iter(docs))
        data = {"pages": [{
            "slug": slug, "title": rec["question"][:200], "type": "faq",
            "compiled_truth": truth,
            "timeline": [{"date": date.today().isoformat(),
                          "text": f"Filed from a verified answer [S:{new_sid}]"}],
            "links": [s for s in rec["citations"] if s != slug]}],
            "conflicts": []}
        problems = changesets.validate(
            data, new_sid, docs[new_sid], self.terms(), self.cfg.ask.url_domains,
            load_source=lambda sid: docs.get(sid, ""))
        meta = {"id": new_sid, "ref": "ask-log", "kind": "faq-fileback",
                "licence": "public", "fetched_at": rec.get("at", "")}
        cs = self.changes.create(meta, data, problems)
        self.audit("fileback", "curator", changeset=cs["id"], source_question=rec["question"])
        return cs

    # ---- re-verification (GL-L3) -----------------------------------------------
    def reverify(self, limit: int = 20) -> list[dict]:
        """Re-fetch crawlable sources behind stale pages; compile when content changed."""
        out: list[dict] = []
        idx = self._ensure_index()["sources"]
        checked = set()
        for slug in self.store.slugs():
            if len(out) >= limit:
                break
            page = self.store.get(slug)
            if page is None or not self._page_stale(slug, page):
                continue
            for sid in page.sources:
                if sid in checked or sid not in idx:
                    continue
                checked.add(sid)
                ref = idx[sid].get("ref", "")
                if not ref.startswith(("http://", "https://")):
                    continue
                try:
                    new_meta = self.sources.add(ref, idx[sid].get("kind", "doc"),
                                                idx[sid].get("licence", "public"))
                except Exception as e:
                    out.append({"slug": slug, "source": sid, "action": "fetch_failed", "detail": str(e)[:200]})
                    continue
                if new_meta.get("duplicate"):
                    out.append({"slug": slug, "source": sid, "action": "unchanged"})
                    continue
                cs = self.compile(new_meta["id"])
                out.append({"slug": slug, "source": sid, "action": "compiled",
                            "changeset": cs["id"], "status": cs["status"]})
        return out

    # ---- lint ----------------------------------------------------------------
    def lint(self) -> dict:
        slugs = self.store.slugs()
        known = set(slugs)
        report = {"pages": len(slugs), "stale": [], "uncited_facts": [], "broken_links": [],
                  "orphans": [], "unknown_sources": [], "contradictions": []}
        inbound = {s: 0 for s in slugs}
        src_ids = {m["id"] for m in self.sources.list()}
        pages = {}
        for s in slugs:
            p = self.store.get(s)
            pages[s] = p
            if self._page_stale(s, p):
                report["stale"].append(s)
            for l in p.links:
                if l in known:
                    inbound[l] += 1
                else:
                    report["broken_links"].append(f"{s} -> {l}")
            v = grounding.verify(p.compiled_truth, {sid: "" for sid in src_ids}, cite_prefix="S")
            for iss in v.issues:
                if iss.reason in ("uncited", "unknown_citation"):
                    report["uncited_facts"].append(f"{s}: {iss.claim}")
            for sid in re.findall(r"\[S:([^\]]+)\]", p.compiled_truth):
                if sid not in src_ids:
                    report["unknown_sources"].append(f"{s}: {sid}")
        report["orphans"] = [s for s, n in inbound.items() if n == 0 and not s.startswith("_meta/")]
        report["protected_namespaces"] = list(PROTECTED_NAMESPACES)
        report["contradictions"] = self._contradictions(pages)
        report["region_drift"] = self._region_drift(pages)
        return report

    def _region_drift(self, pages: dict) -> list[str]:
        """E3-S8/GL-K4: region pages whose title is not backed by the authoritative
        region list (wiki/regions.json). Empty list while OQ-1 is pending."""
        rf = self.cfg.path("wiki/regions.json")
        if not rf.exists():
            return []
        from .regions import RegionList
        try:
            rl = RegionList.load(rf)
        except ValueError as e:
            return [f"regions.json unreadable: {e}"]
        if not rl.regions:
            return []
        titles = [p.title for s, p in pages.items() if s.startswith("regions/") and p.title]
        return [f"region title {t!r} not in authoritative list" for t in rl.drift_against_wiki(titles)]

    def _contradictions(self, pages: dict) -> list[str]:
        """GL-L2: same (entity, attribute) with different values on two pages.
        V1 detects availability pairs (service × region) and per-unit prices."""
        terms = [t for t in self.terms() if len(t) > 2]
        rev = {}                                   # synonym -> canonical (both lower)
        for canon, syns in self.term_synonyms().items():
            rev[canon.lower()] = canon.lower()
            for syn_ in syns:
                rev[syn_.lower()] = canon.lower()
        avail: dict[tuple[str, str], dict[str, set[str]]] = {}
        prices: dict[tuple[str, str, str], dict[str, set[str]]] = {}
        for slug, p in pages.items():
            if slug.startswith("_meta/"):
                continue
            text = p.compiled_truth
            for m in re.finditer(r"(?i)\b(%s)(?![a-z0-9])[^.|]{0,40}?\b"
                                 r"(not available|unavailable|available)\s+in\s+(%s)\b(?![a-z0-9])"
                                 % ("|".join(map(re.escape, terms)), "|".join(map(re.escape, terms))), text):
                svc, region, state = m.group(1), m.group(3), m.group(2).lower()
                key = (rev.get(svc.lower(), svc.lower()), rev.get(region.lower(), region.lower()))
                avail.setdefault(key, {"yes": set(), "no": set()})[
                    "no" if "not" in state or "un" in state else "yes"].add(slug)
            if not terms:
                continue            # empty term list degenerates the region group
            for m in re.finditer(r"(?i)(USD\s?[\d.,]+)\s+per\s+([a-z-]+)-month\s+in\s+(%s)\b"
                                 % "|".join(map(re.escape, terms)), text):
                price, unit, region = m.group(1).replace(" ", ""), m.group(2).lower(), m.group(3).lower()
                svc = slug.split("/", 1)[-1].split("-")[0]
                region = rev.get(region, region)
                prices.setdefault((svc, region, unit), {"v": set(), "pages": set()})
                prices[(svc, region, unit)]["v"].add(price)
                prices[(svc, region, unit)]["pages"].add(slug)
        out = []
        for (svc, region), sides in avail.items():
            if sides["yes"] and sides["no"]:
                out.append(f"availability: {svc} in {region}: available {sorted(sides['yes'])} "
                           f"vs not available {sorted(sides['no'])}")
        for (svc, region, unit), d in prices.items():
            if len(d["v"]) > 1:
                out.append(f"pricing: {svc} per {unit} in {region}: {sorted(d['v'])} on {sorted(d['pages'])}")
        return out

    # ---- dream reconcile (content conflicts; Robin-authorized 2026-09-24) --------
    def dream_reconcile(self) -> dict:
        """Resolve cross-page conflicts, newest wins (user directive 2026-09-24).

        The losing page's contradicting statement is replaced by the winning
        statement (with the winner's [S:] citation), applied through the normal
        change-set path with actor `dream-autoflow` — auditable like any write.
        Protected namespaces stay in the human review queue. Never deletes pages.
        """
        from datetime import date as _date
        pages = {s: self.store.get(s) for s in self.store.slugs()}
        pages = {s: p for s, p in pages.items() if p is not None and not s.startswith("_meta/")}
        contradictions = self._contradictions(pages)
        report = {"conflicts": len(contradictions), "resolved": [], "pending": [],
                  "skipped": []}
        src_meta = self._ensure_index()["sources"]

        def newness(p: Page) -> tuple[str, str]:
            # rank key: source freshness first, page-declared verification as tiebreak
            # (fresh uploads share fetched_at; then last_verified/timeline decides).
            fetched = [str((src_meta.get(sid) or {}).get("fetched_at", "")) for sid in p.sources]
            declared = [p.last_verified or ""] + [e.get("date", "") for e in p.timeline]
            return (max(fetched) or "", max(declared) or "")

        terms = [t for t in self.terms() if len(t) > 2]
        rev = {}                                   # synonym -> canonical (lower)
        for canon, syns in self.term_synonyms().items():
            rev[canon.lower()] = canon.lower()
            for syn_ in syns:
                rev[syn_.lower()] = canon.lower()
        pat_svc = "|".join(map(re.escape, terms))
        AVAIL = re.compile(r"(?i)\b(%s)(?![a-z0-9])[^.|]{0,40}?\b"
                           r"(not available|unavailable|available)\s+in\s+(%s)\b(?![a-z0-9])"
                           % (pat_svc, pat_svc))
        PRICE = re.compile(r"(?i)(USD\s?[\d.,]+)\s+per\s+([a-z-]+)-month\s+in\s+(%s)\b"
                           % pat_svc)

        def find_stmt(text, kind, key):
            # compare through the synonym map: matched text may say "OBS" while the
            # conflict key carries the canonical "object storage service"
            for m in (AVAIL if kind == "avail" else PRICE).finditer(text):
                if kind == "avail" and (rev.get(m.group(1).lower(), m.group(1).lower()),
                                        rev.get(m.group(3).lower(), m.group(3).lower())) == key:
                    return m
                if kind == "price" and (rev.get(m.group(3).lower(), m.group(3).lower()),
                                        m.group(2).lower()) == key:
                    return m
            return None

        jobs = []
        for c in contradictions:
            kind = "avail" if c.startswith("availability:") else "price"
            if kind == "avail":
                svc, region = [x.strip() for x in
                               c[len("availability:"):].split(" in ", 1)[0].split(" ", 1)][0:1] +                               [c.split(" in ", 1)[1].split(":")[0].strip()]
                # parse "svc in region: ..." robustly
                head = c[len("availability:"):]
                svc = head.split(" in ")[0].strip()
                region = head.split(" in ")[1].split(":")[0].strip()
                key_terms = (svc.lower(), region.lower())   # (service, region)
                holders = []
                for slug, p in pages.items():
                    m = find_stmt(p.compiled_truth, "avail", key_terms)
                    if m:
                        holders.append((slug, p, m, "not" in m.group(2).lower() or m.group(2).lower().startswith("una")))
                if len(holders) < 2:
                    report["skipped"].append({"conflict": c, "why": "holders<2"})
                    continue
                jobs.append(("avail", c, key_terms, holders))
            else:
                # pricing: svc per unit in region: vals on pages. Holder key is
                # (region, unit): the sentence regex captures region + unit, not svc.
                head = c[len("pricing:"):]
                unit = head.split(" per ")[1].split(" in ")[0].strip().lower()
                region = head.split(" in ")[1].split(":")[0].strip().lower()
                key_terms = (region, unit)
                holders = []
                for slug, p in pages.items():
                    m = find_stmt(p.compiled_truth, "price", key_terms)
                    if m:
                        holders.append((slug, p, m, m.group(1)))
                if len(holders) < 2:
                    report["skipped"].append({"conflict": c, "why": "holders<2"})
                    continue
                jobs.append(("price", c, key_terms, holders))

        for kind, cdesc, key, holders in jobs:
            ranked = sorted(holders, key=lambda h: newness(h[1]), reverse=True)
            win_slug, win_page, win_m, win_val = ranked[0]
            # the citation of the WINNING STATEMENT (not the page's first source)
            win_sid = ""
            wm = find_stmt(win_page.compiled_truth, kind, key)
            if wm:
                cm = re.search(re.escape(wm.group(0)) + r"\s*\[S:([0-9a-f]{16})\]",
                               win_page.compiled_truth)
                if cm:
                    win_sid = cm.group(1)
            if not win_sid:
                win_sid = win_page.sources[0] if win_page.sources else ""
            if not win_sid:
                report["skipped"].append({"conflict": cdesc, "why": "winner has no sources"})
                continue
            changed = []
            for slug, page, m, val in ranked[1:]:
                if val == win_val:
                    continue
                old_stmt = m.group(0)
                win_stmt = find_stmt(win_page.compiled_truth, kind, key)
                win_stmt_text = win_stmt.group(0) if win_stmt else old_stmt
                # consume the loser's trailing [S:] too: the winner's fact must
                # carry the WINNER's citation, not the stale loser source.
                new_truth = re.sub(re.escape(old_stmt) + r"(\s*\[S:[0-9a-f]{16}\])?",
                                   win_stmt_text + f" [S:{win_sid}]",
                                   page.compiled_truth, count=1)
                if new_truth == page.compiled_truth:
                    report["skipped"].append({"conflict": cdesc, "why": f"replace miss on {slug}"})
                    continue
                proposed = {"slug": slug, "title": page.title, "type": page.type,
                            "compiled_truth": new_truth,
                            "timeline": [{"date": _date.today().isoformat(),
                                          "text": f"conflict resolved by dream: newest source wins "
                                                  f"({win_slug}) [S:{win_sid}]"}],
                            "links": page.links}
                meta = {"id": win_sid, "ref": (src_meta.get(win_sid) or {}).get("ref", "dream"),
                        "kind": "dream-reconcile", "licence": "public",
                        "fetched_at": (src_meta.get(win_sid) or {}).get("fetched_at", "")}
                problems = changesets.validate(
                    {"pages": [proposed], "conflicts": []}, win_sid,
                    (self.sources.get(win_sid)[1] if self.sources.root.exists() and
                     (self.sources.root / f"{win_sid}.txt").exists() else ""),
                    self.terms(), self.cfg.ask.url_domains,
                    load_source=lambda sid: self.sources.get(sid)[1],
                    term_synonyms=self.term_synonyms())
                cs = self.changes.create(meta, {"pages": [proposed], "conflicts": []}, problems)
                if problems:
                    report["skipped"].append({"conflict": cdesc, "why": f"invalid cs {cs['id']}"})
                    continue
                if cs["protected"]:
                    report["pending"].append({"conflict": cdesc, "changeset": cs["id"],
                                              "loser": slug, "winner": win_slug})
                else:
                    self.approve(cs["id"], "dream-autoflow",
                                 note=f"conflict reconcile: newest wins ({win_slug} > {slug})")
                    changed.append(slug)
                    report["resolved"].append({"conflict": cdesc, "loser": slug,
                                               "winner": win_slug, "kept": win_stmt_text[:80]})
        self.invalidate_index()
        self._invalidate_plist()
        return report

    def write_lint_page(self, report: dict) -> str:
        """E8-S2: _meta/lint-report-<date>. _meta pages are glue-written operational
        pages (SCHEMA.md); they never go through change sets."""
        today = date.today().isoformat()
        slug = f"_meta/lint-report-{today}"
        lines = [f"Nightly lint report for {today}.", ""]
        for k, v in report.items():
            lines.append(f"- **{k}**: {v if not isinstance(v, list) else len(v)}")
            if isinstance(v, list):
                lines += [f"  - {x}" for x in v[:50]]
        page = Page(slug=slug, title=f"Lint report {today}", type="lint-report",
                    compiled_truth="\n".join(lines),
                    timeline=[{"date": today, "text": f"Nightly lint run: {report['pages']} pages"}])
        self.store.put(page)
        self.invalidate_index()
        self._invalidate_plist()
        return slug


def _not_found(lang: str) -> str:
    return {
        "es": "NOT_IN_WIKI — La wiki todavía no tiene información verificada para responder esta pregunta.",
        "pt-BR": "NOT_IN_WIKI — A wiki ainda não tem informação verificada para responder a esta pergunta.",
    }.get(lang, "NOT_IN_WIKI — The wiki does not yet have verified information to answer this question.")
