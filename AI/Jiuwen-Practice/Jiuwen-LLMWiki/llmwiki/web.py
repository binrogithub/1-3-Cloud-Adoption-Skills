"""Web UI + HTTP API (PRD E11, GL-A7 SSE, GL-O4 health, GL-O5 metrics).

stdlib only: http.server. All truth is computed by the glue (D-7); the UI renders
verdicts, never recomputes them. SSE per GL-A7: ack → retrieval → final/error; the
verified answer is sent once, token streaming of unverified text is not implemented
by design.

Auth: X-LLMWiki-Token header (llmwiki/auth.py). Without a token the caller is a
reader (ask/browse only). Approve/reject need a curator-or-above token.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import threading
from datetime import datetime
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, auth
from .changesets import ChangeSetError
from .config import Config, ROLE_CURATOR
from .jiuwen import _role_output
from .pipeline import Wiki

_wiki: Wiki | None = None
_cfg: Config | None = None
_tokens: auth.TokenStore | None = None
_started = time.time()
_lock = threading.RLock()
_metrics = Counter()
_metrics_last = {"input_tokens": 0, "output_tokens": 0, "ttft_ms": 0.0}
_ask_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llmwiki-ask")


def git_sha() -> str:
    try:
        p = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent.parent),
                            "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else "no-git"
    except Exception:
        return "no-git"


class Handler(BaseHTTPRequestHandler):
    server_version = f"llmwiki/{__version__}"
    disable_nagle_algorithm = True          # SSE: push every small event immediately

    # ---- plumbing -----------------------------------------------------------
    def log_message(self, fmt, *args):                     # quiet access log
        pass

    def _role(self) -> tuple[str, str]:
        return _tokens.role_for(self.headers.get("X-LLMWiki-Token")) or ("anonymous", "reader")

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))

    def _html(self, text: str, code: int = 200):
        self._send(code, text.encode("utf-8"), "text/html; charset=utf-8")

    def _forbid(self, action: str) -> bool:
        name, role = self._role()
        if not auth.allowed(role, action):
            self._json({"error": f"role '{role}' cannot '{action}'"}, 403)
            return True
        return False

    # ---- routes -------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/ask"):
                return self._page_ask()
            if u.path == "/browse":
                return self._page_browse(q)
            if u.path == "/review":
                return self._page_review(q)
            if u.path == "/health":
                return self._health()
            if u.path == "/metrics":
                return self._metrics()
            if u.path == "/pages":
                return self._pages(q)
            if u.path == "/search":
                return self._search(q)
            if u.path == "/sources":
                if self._forbid("sources"):
                    return
                return self._json(_wiki.sources.list())
            if u.path == "/source":
                if self._forbid("sources"):
                    return
                sid = (q.get("id") or [""])[0]
                try:
                    meta, text = _wiki.sources.get(sid)
                except Exception as e:
                    return self._json({"error": str(e)}, 404)
                name, role = self._role()
                if meta.get("licence") == "confidential" and role not in (ROLE_CURATOR, "admin"):
                    return self._json({"error": "confidential source requires curator role"}, 403)
                return self._json({"meta": meta, "text": text})
            if u.path == "/changesets":
                return self._changesets(q)
            if u.path == "/lint":
                if self._forbid("lint"):
                    return
                with _lock:
                    return self._json(_wiki.lint())
            if u.path == "/conversations":            # PRD V12: history list
                return self._conversations_list()
            if u.path.startswith("/conversations/"):
                return self._conversation(u.path.rsplit("/", 1)[-1])
            self._json({"error": "not found", "path": u.path}, 404)
        except Exception as e:                                   # noqa: BLE001 — one place, logged
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_DELETE(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/source":
                if self._forbid("ingest"):
                    return
                return self._delete_source(q)
            if u.path.startswith("/conversations/"):   # PRD V12: delete a thread
                cid = u.path.rsplit("/", 1)[-1]
                return self._conversation_delete(cid)
            self._json({"error": "not found", "path": u.path}, 404)
        except Exception as e:                                   # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def _delete_source(self, q):
        """PRD V5 delete guard + V7 cascade: an uncited source deletes freely; a
        cited one 409s (advertising cascade_available) unless &cascade=1, which
        retracts every statement citing it and deletes emptied pages."""
        sid = (q.get("id") or [""])[0]
        cascade = (q.get("cascade") or [""])[0] in ("1", "true", "yes")
        try:
            r = _wiki.delete_source(sid, cascade=cascade,
                                    actor="delete-cascade" if cascade else "upload-autoflow")
        except Exception as e:
            return self._json({"error": str(e)}, 404)
        if r.get("blocked"):
            return self._json({"error": "source is cited by wiki pages; delete or "
                                        "re-compile those pages first",
                               "pages": r["pages"], "cascade_available": True}, 409)
        return self._json(r)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/upload":                      # multipart: reads its own body
            if self._forbid("ingest"):
                return
            try:
                return self._upload()
            except Exception as e:
                return self._json({"error": f"upload failed: {e}"}, 500)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        try:
            if u.path == "/upload":
                if self._forbid("ingest"):
                    return
                return self._upload()
            if u.path == "/ask":
                if self._forbid("ask"):
                    return
                return self._ask(body, sse=True)
            if u.path == "/recompile":
                if self._forbid("compile"):
                    return
                name, _ = self._role()
                sid = (body.get("id") or "").strip()
                try:
                    meta, _ = _wiki.sources.get(sid)
                except Exception as e:
                    return self._json({"error": str(e)}, 404)
                with _lock:                                   # R10-4: one compile at a time
                    cs = _wiki.compile(sid)
                    auto = _autoflow_apply(cs, meta)
                    cs = _wiki.changes.get(cs["id"])
                _wiki.audit("recompile", name, source=sid, changeset=cs["id"],
                            auto_applied=auto)
                return self._json({"changeset": {k: cs.get(k) for k in ("id", "status", "pages", "protected")},
                                   "auto_applied": auto,
                                   "problems": cs.get("problems", [])})
            if u.path == "/pages/edit":
                if self._forbid("edit"):
                    return
                name, role = self._role()
                if name == "anonymous":
                    return self._json({"error": "edit needs a named token"}, 403)
                slug = (body.get("slug") or "").strip()
                if not slug or not (body.get("compiled_truth") or "").strip():
                    return self._json({"error": "slug and compiled_truth required"}, 400)
                protected = slug.split("/")[0] in ("pricing", "compliance", "availability")
                if protected and not auth.allowed(role, "approve"):
                    return self._json({"error": f"{slug} is protected; edit needs a curator token"}, 403)
                try:
                    with _lock:
                        r = _wiki.edit_page(slug, body["compiled_truth"], name,
                                            title=(body.get("title") or "").strip(),
                                            allow_protected=protected)
                except Exception as e:
                    return self._json({"error": str(e)}, 400)
                return self._json({"applied": r["applied"],
                                   "problems": r["problems"],
                                   "changeset": {k: r["changeset"].get(k)
                                                 for k in ("id", "status")}})
            if u.path == "/ask.json":
                if self._forbid("ask"):
                    return
                return self._ask(body, sse=False)
            if u.path == "/changesets/approve":
                if self._forbid("approve"):
                    return
                name, _ = self._role()
                if name == "anonymous":
                    return self._json({"error": "approve needs a named curator token"}, 403)
                with _lock:
                    pages = _wiki.approve(body["id"], name)
                return self._json({"applied": pages})
            if u.path == "/changesets/reject":
                if self._forbid("reject"):
                    return
                name, _ = self._role()
                if name == "anonymous":
                    return self._json({"error": "reject needs a named curator token"}, 403)
                with _lock:
                    _wiki.reject(body["id"], name, body.get("note", ""))
                return self._json({"rejected": body["id"]})
            self._json({"error": "not found", "path": u.path}, 404)
        except ChangeSetError as e:
            self._json({"error": str(e)}, 409)
        except Exception as e:                                   # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    # ---- upload (PRD V5) --------------------------------------------------------
    def _upload(self):
        ctype = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length") or 0)
        if not ctype.startswith("multipart/form-data") or length <= 0:
            return self._json({"error": "multipart/form-data with a file field required"}, 400)
        if length > 10 * 1024 * 1024:
            return self._json({"error": "file too large (max 10 MiB)"}, 413)
        fields = _parse_multipart(self.rfile.read(length), ctype)
        file = fields.get("file")
        if not file or not file[0] or not file[1].strip():
            return self._json({"error": "empty or missing file field"}, 400)
        filename, data = file
        filename = os.path.basename(filename).replace("\\", "_")[:120] or "upload.bin"
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext not in ("md", "txt", "html", "htm", "pdf", "csv", "json", "yaml", "yml"):
            return self._json({"error": f"unsupported type .{ext}; convert to MD/TXT/HTML/PDF first"}, 415)
        kind = (fields.get("kind", (None, b"doc"))[1] or b"doc").decode() or "doc"
        licence = (fields.get("licence", (None, b"public"))[1] or b"public").decode() or "public"
        lang = (fields.get("lang", (None, b""))[1] or b"").decode()
        owner = (fields.get("owner", (None, b""))[1] or b"").decode()
        updir = _cfg.runtime_dir / "uploads"
        updir.mkdir(parents=True, exist_ok=True)
        fpath = updir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{filename}"
        fpath.write_bytes(data)
        try:
            meta = _wiki.sources.add(str(fpath), kind=kind, licence=licence, lang=lang, owner=owner,
                                     meta_ref=f"uploads/{fpath.name}")
        except Exception as e:
            fpath.unlink(missing_ok=True)
            return self._json({"error": f"ingest rejected: {e}"}, 422)
        if meta.get("duplicate"):
            return self._json({"source": meta, "changeset": None, "auto_applied": False,
                               "note": "identical content already ingested (dedup); nothing to compile"})
        _, role = self._role()
        try:
            cs = _wiki.compile(meta["id"])
        except Exception as e:
            return self._json({"source": meta, "changeset": None, "auto_applied": False,
                               "error": f"compile failed: {e}"}, 502)
        auto = _autoflow_apply(cs, meta)
        cs = _wiki.changes.get(cs["id"])
        return self._json({"source": meta,
                           "changeset": {k: cs.get(k) for k in ("id", "status", "pages", "protected")},
                           "auto_applied": auto})

    # ---- endpoints ------------------------------------------------------------
    def _health(self):
        import socket
        gw_up = False
        with socket.socket() as s:
            s.settimeout(1.5)
            gw_up = s.connect_ex(("127.0.0.1", _cfg.jiuwen.gateway_port)) == 0
        self._json({
            "service": "llmwiki-web", "version": __version__, "git_sha": git_sha(),
            "uptime_s": round(time.time() - _started, 1),
            "components": {
                "store_backend": _cfg.gbrain.backend,
                "dedicated_gateway_listening": gw_up,
                "pages": len(_wiki.store.slugs()),
            },
        })

    def _metrics(self):
        lines = [
            "# TYPE llmwiki_asks_total counter",
            f"llmwiki_asks_total {_metrics['asks']}",
            "# TYPE llmwiki_ask_status_total counter",
        ]
        for status, n in sorted(_metrics.items()):
            if status.startswith("status:"):
                lines.append(f'llmwiki_ask_status_total{{status="{status[7:]}"}} {n}')
        lines += [
            "# TYPE llmwiki_ask_tokens_total counter",
            f"llmwiki_ask_input_tokens_total {_metrics_last['input_tokens']}",
            f"llmwiki_ask_output_tokens_total {_metrics_last['output_tokens']}",
            "# TYPE llmwiki_ask_ttft_ms gauge",
            f"llmwiki_ask_ttft_ms {_metrics_last['ttft_ms']}",
            "# TYPE llmwiki_up gauge",
            f"llmwiki_up 1",
        ]
        self._send(200, ("\n".join(lines) + "\n").encode("utf-8"),
                   "text/plain; version=0.0.4; charset=utf-8")

    def _pages(self, q):
        slug = (q.get("slug") or [None])[0]
        if slug:
            page = _wiki.store.get(slug)
            detail = None if page is None else {
                "slug": page.slug, "title": page.title, "type": page.type,
                "compiled_truth": page.compiled_truth, "timeline": page.timeline,
                "links": page.links, "sources": page.sources,
                "last_verified": page.last_verified}
            return self._json({"page": detail})
        _, role = self._role()
        hidden = set(_wiki.confidential_slugs()) if role not in (ROLE_CURATOR, "admin") else set()
        items = [p for p in _wiki.page_list() if p["slug"] not in hidden]
        return self._json({"pages": items, "hidden_confidential": len(hidden)})

    def _search(self, q):
        query = (q.get("q") or [""])[0]
        k = int((q.get("k") or ["6"])[0])
        slugs = _wiki.store.search(query, k)
        self._json({"q": query, "results": slugs})

    def _changesets(self, q):
        cs_id = (q.get("id") or [None])[0]
        if cs_id:
            return self._json(_wiki.changes.get(cs_id))
        status = (q.get("status") or [None])[0]
        return self._json({"changesets": _wiki.changes.list(status)})

    def _conversation(self, cid):
        f = _cfg.runtime_dir / "conversations" / f"{cid}.json"
        if not f.exists():
            return self._json({"error": "unknown conversation"}, 404)
        return self._json(json.loads(f.read_text(encoding="utf-8")))

    def _conversations_list(self):
        """PRD V12 R12-1: the requester's threads, newest activity first.
        Owner guard matches _conversation_open (own + anonymous-owned)."""
        name, _ = self._role()
        root = _cfg.runtime_dir / "conversations"
        out = []
        if root.exists():
            for f in root.glob("*.json"):
                try:
                    conv = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if name != "anonymous" and conv.get("owner") not in (name, "anonymous"):
                    continue
                if name == "anonymous" and conv.get("owner") != "anonymous":
                    continue
                turns = conv.get("turns") or []
                if not turns:
                    continue
                out.append({"id": conv.get("id") or f.stem,
                            "title": (turns[0].get("q") or "")[:48],
                            "turns": len(turns),
                            "created_at": conv.get("created_at"),
                            "last_at": turns[-1].get("at")})
        out.sort(key=lambda c: c["last_at"] or 0, reverse=True)
        return self._json({"conversations": out[:50]})

    def _conversation_delete(self, cid):
        """PRD V12 R12-2: remove a thread (same ownership guard)."""
        if not re.fullmatch(r"[0-9a-f]{12}", cid or ""):
            return self._json({"error": "bad conversation id"}, 400)
        f = _cfg.runtime_dir / "conversations" / f"{cid}.json"
        if not f.exists():
            return self._json({"error": "unknown conversation"}, 404)
        conv = json.loads(f.read_text(encoding="utf-8"))
        name, _ = self._role()
        if name != "anonymous" and conv.get("owner") not in (name, "anonymous"):
            return self._json({"error": "conversation belongs to another owner"}, 403)
        f.unlink()
        _wiki.audit("conversation_delete", name, conversation=cid)
        return self._json({"deleted": cid})

    # ---- ask + SSE (GL-A7) ------------------------------------------------------
    def _ask(self, body: dict, sse: bool):
        question = (body.get("question") or "").strip()
        if not question:
            return self._json({"error": "question required"}, 400)
        name, role = self._role()
        lang = body.get("lang")
        conv_id = body.get("conversation_id") or ""
        conv = _conversation_open(conv_id, name, role, lang)

        if sse:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def emit(event: str, data: dict):
                self.wfile.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            emit("ack", {"question": question, "lang": lang or "auto",
                         "conversation_id": conv["id"], "at": time.time()})
        else:
            def emit(event: str, data: dict):                  # noqa: F811
                pass

        # GL-A8/E5-S12 + PRD V8: follow-ups widen retrieval AND carry the
        # conversation into the model prompt; ownership was fixed at creation.
        hist = [{"q": t["q"], "a": t.get("a", "")} for t in conv["turns"][-3:]]
        emit("retrieval", {"state": "started"})
        # SSE v2 (PRD V2 R2-1): thinking / progress / provisional stream live; the
        # verified `final` stays the only authoritative event. Writes from the pool
        # thread and the ping loop share one per-request lock.
        wlock = threading.Lock()
        think_buf: list[str] = []
        think_at = [time.time()]
        provisional_sent = [False]

        def flush_thinking() -> None:
            if think_buf:
                with wlock:
                    emit("thinking", {"delta": "".join(think_buf)})
                think_buf.clear()

        def stream_cb(ev: dict) -> None:
            name = ev.get("event", "")
            pl = ev.get("payload") or {}
            if name == "chat.reasoning":
                think_buf.append(pl.get("content", ""))
                now = time.time()
                if now - think_at[0] > 0.4:            # coalesce bursts (R2-4)
                    with wlock:
                        emit("thinking", {"delta": "".join(think_buf)})
                    think_buf.clear()
                    think_at[0] = now
            elif name == "chat.tool_call":
                tc = pl.get("tool_call") or pl
                with wlock:
                    emit("progress", {"stage": "dispatch",
                                      "tool": tc.get("name") or pl.get("name") or ""})
            elif name == "chat.tool_update":
                with wlock:
                    emit("progress", {"stage": "update", "detail": str(pl)[:160]})
            if name == "chat.tool_result":
                out = _role_output(pl, _cfg.jiuwen.role)
                if out is not None and not provisional_sent[0]:
                    flush_thinking()
                    provisional_sent[0] = True
                    with wlock:
                        # raw role output, BEFORE verification (display-only, GL-A7 V2)
                        emit("provisional", {"text": out})

        def on_retrieval(slugs, stale, filtered):
            with wlock:
                emit("retrieval", {"state": "done", "slugs": slugs,
                                   "stale": stale, "filtered_confidential": filtered})

        def run_ask():
            return _wiki.ask(question, lang, role=role,
                             stream_cb=stream_cb if sse else None,
                             on_retrieval=on_retrieval if sse else None,
                             history=hist, conversation_id=conv["id"],
                             turn=len(conv["turns"]) + 1)

        t_ask = time.time()
        fut = _ask_pool.submit(run_ask)
        if sse:
            while True:
                try:
                    res = fut.result(timeout=5)
                    if think_buf:
                        with wlock:
                            emit("thinking", {"delta": "".join(think_buf)})
                        think_buf.clear()
                    break
                except FutTimeout:
                    if time.time() - think_at[0] > 5:
                        with wlock:
                            emit("ping", {"elapsed_s": round(time.time() - t_ask, 1)})
                        think_at[0] = time.time()
        else:
            res = fut.result()
        _metrics["asks"] += 1
        _metrics[f"status:{res.status}"] += 1
        _metrics_last.update(input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                             ttft_ms=res.ttft_ms or 0.0)
        _conversation_append(conv, question, res)
        _wiki.audit("ask", name, question=question[:200], status=res.status,
                    conversation=conv["id"])
        if res.status == "error":
            emit("error", {"error": res.error})
            if not sse:
                return self._json({"error": res.error, "status": "error"}, 503)
            return
        payload = {"answer": res.answer, "status": res.status, "citations": res.citations,
                   "retrieved": res.retrieved, "stale": res.stale, "issues": res.issues,
                   "lang": res.lang, "elapsed_s": res.elapsed_s,
                   "conversation_id": conv["id"]}
        emit("final", payload)
        if not sse:
            self._json(payload)

    # ---- HTML pages ---------------------------------------------------------------
    def _page_ask(self):
        self._html(_RENDER.ask_page())

    def _page_browse(self, q):
        slug = (q.get("slug") or [None])[0]
        if slug:
            p = _wiki.store.get(slug)
            body = p.to_markdown() if p else "(no such page)"
            return self._html(_RENDER.page_detail(slug, p))
        slugs = _wiki.store.slugs()
        return self._html(_RENDER.browse_page(slugs))

    def _page_review(self, q):
        cs_id = (q.get("id") or [None])[0]
        if cs_id:
            cs = _wiki.changes.get(cs_id)
            diffs = []
            for p in cs["pages"]:
                old = _wiki.store.get(p.get("slug", ""))
                old_text = old.compiled_truth if old else "(new page)"
                d = "\n".join(difflib.unified_diff(
                    old_text.splitlines(), (p.get("compiled_truth") or old_text).splitlines(),
                    "current", "proposed", lineterm="", n=2))
                diffs.append({"slug": p.get("slug"), "diff": d or "(no compiled-truth change)"})
            return self._html(_RENDER.review_detail(cs, diffs))
        items = _wiki.changes.list(q.get("status", ["pending"])[0])
        return self._html(_RENDER.review_list(items))


# ---- conversations (GL-A8) ----------------------------------------------------
_conv_lock = threading.Lock()


def _autoflow_apply(cs: dict, meta: dict) -> bool:
    """PRD V5 §2 upload autoflow — shared by upload and recompile (PRD V10 R10-2)
    so the two flows can never drift. Audits failures; the cs stays pending."""
    if not (_cfg.review.auto_apply_uploads and cs["status"] == "pending"
            and not cs["protected"] and not cs["conflicts"] and not cs["problems"]
            and (meta.get("licence") == "public")):
        return False
    try:
        _wiki.approve(cs["id"], _cfg.review.upload_actor,
                      note="upload autoflow: public + non-protected + clean (PRD V5 §2)")
        return True
    except Exception as e:
        _wiki.audit("upload_autoflow_failed", _cfg.review.upload_actor,
                    changeset=cs["id"], error=str(e)[:300])
        return False


def _conversation_open(cid: str, owner: str, role: str, lang: str | None) -> dict:
    with _conv_lock:
        d = _cfg.runtime_dir / "conversations"
        d.mkdir(parents=True, exist_ok=True)
        if cid:
            f = d / f"{cid}.json"
            if f.exists():
                conv = json.loads(f.read_text(encoding="utf-8"))
                if owner != "anonymous" and conv["owner"] not in (owner, "anonymous"):
                    raise PermissionError("conversation belongs to another owner")
                return conv
        conv = {"id": cid or uuid.uuid4().hex[:12], "owner": owner, "role": role,
                "lang": lang or "", "created_at": time.time(), "turns": []}
        (d / f"{conv['id']}.json").write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")
        return conv


def _conversation_append(conv: dict, question: str, res) -> None:
    with _conv_lock:
        conv["turns"].append({"q": question, "a": res.answer, "status": res.status,
                              "at": time.time()})
        f = _cfg.runtime_dir / "conversations" / f"{conv['id']}.json"
        f.write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")


# ---- minimal server-side rendered UI (no build step, no CDN) --------------------
class _Render:
    STYLE = """<style>
      :root{--bg:#0f1420;--fg:#e8ecf4;--muted:#8b94a7;--accent:#c74634;--ok:#2e9e6b;--warn:#c98a2b;--card:#171e2e;--line:#28324a}
      *{box-sizing:border-box} body{font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);margin:0}
      header{display:flex;gap:18px;align-items:center;padding:14px 22px;border-bottom:1px solid var(--line);background:var(--card)}
      header a{color:var(--fg);text-decoration:none;font-weight:600} header a:hover{color:#fff}
      header .logo{color:var(--accent);font-weight:800;letter-spacing:.4px}
      main{max-width:1000px;margin:26px auto;padding:0 20px}
      .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:18px}
      h1{font-size:1.35rem;margin:.2rem 0 .8rem} h2{font-size:1.05rem;margin:1rem 0 .5rem}
      input[type=text],select,textarea{width:100%;background:#0c111c;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:9px 12px;font:inherit}
      textarea{min-height:84px;resize:vertical}
      button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer}
      button.ghost{background:transparent;border:1px solid var(--line);color:var(--fg)}
      .muted{color:var(--muted)} .small{font-size:.85rem}
      pre{background:#0c111c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;white-space:pre-wrap}
      .pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:700;margin-right:6px}
      .p-grounded{background:#123a2b;color:#5ad8a1}.p-partially_verified{background:#3a2f14;color:#e3b34c}
      .p-abstained{background:#33203a;color:#cf9ae0}.p-error,.p-invalid{background:#3a1414;color:#ef8080}
      .p-pending{background:#132c3a;color:#6cc4e8}.p-applied{background:#123a2b;color:#5ad8a1}.p-rejected{background:#3a1414;color:#ef8080}
      table{border-collapse:collapse;width:100%} td,th{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
      .issue{border-left:3px solid var(--warn);padding:6px 10px;margin:6px 0;background:#241d10}
      .slug{font-family:ui-monospace,Menlo,monospace;color:#9db4e8}
    </style>"""

    def frame(self, title: str, body: str) -> str:
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{title} — LLMWiki</title>{self.STYLE}</head><body>
<header><span class="logo">LLMWiki</span>
<a href="/">Ask</a><a href="/browse">Wiki</a><a href="/review">Review</a>
<span class="muted small" style="margin-left:auto">Huawei Cloud LATAM · every fact cited</span>
</header><main>{body}</main></body></html>"""

    def ask_page(self) -> str:
        return self.frame("Ask", """
<h1>Ask the LATAM wiki</h1>
<div class="card">
  <label class="muted small">Language</label>
  <select id="lang" style="margin:6px 0 12px;width:160px">
    <option value="">auto-detect</option><option value="en">English</option>
    <option value="es">Español</option><option value="pt-BR">Português (BR)</option>
  </select>
  <textarea id="q" placeholder="e.g. Is OBS available in LA-Sao Paulo1? / ¿Cuál es el precio de OBS?"></textarea>
  <div style="margin-top:12px;display:flex;gap:10px;align-items:center">
    <button onclick="ask()">Ask</button>
    <button class="ghost" onclick="window.location='/browse'">Browse the wiki</button>
    <span id="state" class="muted small"></span>
  </div>
</div>
<div class="card" id="out" style="display:none">
  <span id="pill"></span><span id="meta" class="muted small"></span>
  <div id="answer" style="margin-top:10px"></div>
  <h2>Unverified claims (redacted in the answer)</h2><div id="issues" class="muted">none</div>
  <h2>Citations</h2><div id="cites" class="slug small"></div>
</div>
<div class="card muted small">Answers come only from wiki pages (evidence pack). Numbers, URLs and
names are verified against the cited page before anything is shown. If the wiki has no verified
answer you will see <b>NOT_IN_WIKI</b> — that is the system working, not failing.</div>
<script>
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q)return;
  const lang=document.getElementById('lang').value;
  const out=document.getElementById('out'); out.style.display='block';
  document.getElementById('answer').innerHTML='<span class="muted">retrieving and verifying…</span>';
  document.getElementById('state').textContent='asking…';
  const res=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({question:q,lang:lang||undefined})});
  const reader=res.body.getReader(); const dec=new TextDecoder(); let buf='';
  while(true){const {done,value}=await reader.read(); if(done)break; buf+=dec.decode(value,{stream:true});
    let i; while((i=buf.indexOf('\\n\\n'))>=0){const chunk=buf.slice(0,i); buf=buf.slice(i+2); handle(chunk);} }
  document.getElementById('state').textContent='';
}
function handle(chunk){
  const ev=(chunk.match(/^event: (.*)$/m)||[])[1];
  const data=JSON.parse((chunk.match(/^data: (.*)$/m)||[])[1]||'{}');
  if(ev==='retrieval'){window._t0=Date.now();document.getElementById('state').textContent='retrieved pages, verifying answer…';}
  if(ev==='ping'){const s=Math.round((Date.now()-(window._t0||Date.now()))/1000);
    document.getElementById('state').textContent='verifying answer… '+s+'s (model working, typical 30–90s)';}
  if(ev==='final'){show(data);}
  if(ev==='error'){document.getElementById('answer').innerHTML='<b style="color:#ef8080">'+data.error+'</b>';}
}
function show(d){
  const pill=document.getElementById('pill');
  pill.className='pill p-'+d.status; pill.textContent=d.status;
  document.getElementById('meta').textContent=(d.stale.length?('⚠ '+d.stale.length+' stale page(s) · '):'')
    +d.citations.length+' citation(s) · '+d.elapsed_s+'s · lang='+d.lang;
  document.getElementById('answer').innerHTML=d.answer.replace(/&/g,'&amp;').replace(/</g,'&lt;');
  const iss=d.issues||[];
  document.getElementById('issues').innerHTML=iss.length?iss.map(i=>
    '<div class="issue"><b>'+i.claim.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</b> — '+i.reason+
    '<div class="muted small">'+i.unit.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</div></div>').join(''):'none';
  document.getElementById('cites').textContent=(d.citations||[]).join('  ');
}
</script>""")

    def browse_page(self, slugs: list[str]) -> str:
        rows = "\n".join(
            f'<tr><td><a class="slug" href="/browse?slug={s}">{s}</a></td></tr>' for s in slugs)
        return self.frame("Wiki", f"""
<h1>Wiki ({len(slugs)} pages)</h1>
<div class="card"><table><tr><th>Page</th></tr>{rows or '<tr><td class="muted">empty</td></tr>'}</table></div>""")

    def page_detail(self, slug: str, p) -> str:
        if p is None:
            return self.frame(slug, f'<div class="card">No page {slug}</div>')
        return self.frame(slug, f"""
<h1 class="slug">{slug}</h1>
<div class="card"><pre>{p.to_markdown().replace('&', '&amp;').replace('<', '&lt;')}</pre></div>""")

    def review_list(self, items: list[dict]) -> str:
        rows = "\n".join(
            f"""<tr><td><a class="slug" href="/review?id={c['id']}">{c['id']}</a></td>
            <td><span class="pill p-{c['status']}">{c['status']}</span></td>
            <td class="small">{'<br>'.join(p.get('slug','') for p in c['pages'])}</td>
            <td class="small">{len(c['conflicts'])} conflicts, {len(c['problems'])} problems
            {'<br><b>PROTECTED</b>' if c['protected'] else ''}</td></tr>""" for c in items)
        return self.frame("Review", f"""
<h1>Review queue</h1>
<div class="card"><table><tr><th>Change set</th><th>Status</th><th>Pages</th><th>Notes</th></tr>
{rows or '<tr><td colspan="4" class="muted">queue empty</td></tr>'}</table></div>
<div class="card muted small">Approving needs a curator token (header X-LLMWiki-Token); set it in
the form on a change set's page. The glue is the only writer; this UI only calls approve/reject.</div>""")

    def review_detail(self, cs: dict, diffs: list[dict]) -> str:
        conflict_rows = ""
        for c in cs.get("conflicts", []):
            conflict_rows += (f"<tr><th>existing</th><td><pre>{str(c.get('existing','')).replace('&','&amp;').replace('<','&lt;')}</pre></td></tr>"
                              f"<tr><th>new (source {c.get('source','')})</th><td><pre>{str(c.get('new','')).replace('&','&amp;').replace('<','&lt;')}</pre></td></tr>"
                              f"<tr><th colspan=2><hr></th></tr>")
        blocks = "".join(
            f'<div class="card"><h2 class="slug">{d["slug"]}</h2><pre>{d["diff"].replace("&","&amp;").replace("<","&lt;")}</pre></div>'
            for d in diffs)
        script = """
<script>
async function decide(what){
  const tok=document.getElementById('tok').value;
  const r=await fetch('/changesets/'+what,{method:'POST',
    headers:{'Content-Type':'application/json','X-LLMWiki-Token':tok},
    body:JSON.stringify({id:CS_ID,note:document.getElementById('note').value})});
  const j=await r.json();
  document.getElementById('decres').textContent=JSON.stringify(j);
  if(r.ok)setTimeout(()=>window.location='/review',900);
}
</script>""".replace("CS_ID", json.dumps(cs["id"]))
        return self.frame(cs["id"], f"""
<h1>Change set <span class="slug">{cs['id']}</span>
<span class="pill p-{cs['status']}">{cs['status']}</span></h1>
<div class="card small">source: <span class="slug">{cs['source'].get('id')}</span>
({cs['source'].get('kind')}, licence {cs['source'].get('licence')})
{('<br>PROTECTED namespaces: ' + ', '.join(cs['protected'])) if cs['protected'] else ''}
{(('<br>problems: ' + '; '.join(p.get('problem','') for p in cs['problems']))) if cs['problems'] else ''}</div>
{blocks}
<div class="card"><h2>Conflicts (side by side, never auto-overwritten)</h2>
<table>{conflict_rows or '<tr><td class="muted">none</td></tr>'}</table></div>
<div class="card"><h2>Decision</h2>
<label class="muted small">Curator token</label>
<input type="text" id="tok" placeholder="llmwiki_…" style="margin:6px 0 12px">
<label class="muted small">Reject note (only for reject)</label>
<input type="text" id="note" style="margin:6px 0 12px"><br>
<button onclick="decide('approve')">Approve</button>
<button class="ghost" onclick="decide('reject')">Reject</button>
<span id="decres" class="small"></span></div>
{script}""")


def _parse_multipart(body: bytes, ctype: str) -> dict:
    """Minimal stdlib multipart/form-data parser: {field: (filename, bytes)}."""
    m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', ctype)
    if not m:
        return {}
    boundary = (m.group(1) or m.group(2)).strip().encode()
    parts: dict = {}
    for seg in body.split(b"--" + boundary):
        seg = seg.strip(b"\r\n")
        if not seg or seg == b"--":
            continue
        head, _, data = seg.partition(b"\r\n\r\n")
        headers = head.decode("utf-8", "replace")
        nm = re.search(r'name="([^"]*)"', headers)
        fn = re.search(r'filename="([^"]*)"', headers)
        if nm:
            parts[nm.group(1)] = (fn.group(1) if fn else None, data.rstrip(b"\r\n"))
    return parts


_RENDER = _Render()


def serve(cfg: Config, host: str | None = None, port: int | None = None) -> None:
    global _wiki, _cfg, _tokens
    _cfg = cfg
    _wiki = Wiki(cfg)
    _tokens = auth.open_tokens(cfg)
    port = port or cfg.web.port
    binds = [host or cfg.web.host]
    # R2-11: the studio api container reaches the glue through its docker network
    # gateway; extra binds come from the env (never 0.0.0.0 — internal only).
    extra = [b.strip() for b in os.environ.get("LLMWIKI_BIND_EXTRA", "").split(",") if b.strip()]
    servers = []
    for b in dict.fromkeys(binds + extra):
        httpd = ThreadingHTTPServer((b, port), Handler)
        print(f"llmwiki-web {__version__} on http://{b}:{port}  (git {git_sha()})", flush=True)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        servers.append(httpd)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        for httpd in servers:
            httpd.shutdown()
