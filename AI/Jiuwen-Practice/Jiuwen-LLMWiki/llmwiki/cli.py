"""llmwiki CLI.

  llmwiki ask "Is GaussDB available in LA-Sao Paulo1?" [--lang es] [--json] [--as NAME]
  llmwiki ingest <file|url> [--kind doc|price|quota|note] [--licence public|internal|confidential] [--compile]
  llmwiki compile <source_id>
  llmwiki review [--status pending]
  llmwiki show <changeset_id>
  llmwiki approve <changeset_id> --by <name>
  llmwiki reject <changeset_id> --by <name> --note "..."
  llmwiki fileback ["question"]                # verified answer -> faq/ change set (UC-7)
  llmwiki reverify [--limit N]                 # re-fetch crawlable stale sources (GL-L3)
  llmwiki lint [--json] [--write-page]
  llmwiki terms
  llmwiki token --role curator --name "ana"    # mint an API token (printed once)
  llmwiki serve [--host H] [--port P]
  llmwiki doctor
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys

from . import __version__, config as config_mod
from .changesets import ChangeSetError
from .jiuwen import JiuwenError
from .pipeline import Wiki
from .sources import SourceError
from .store import StoreError

EXIT_OK, EXIT_FAIL, EXIT_INFRA = 0, 1, 3


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="llmwiki")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask"); a.add_argument("question"); a.add_argument("--lang", choices=["en", "es", "pt-BR"]); a.add_argument("--json", action="store_true"); a.add_argument("--as", dest="actor", default="cli-user")
    i = sub.add_parser("ingest"); i.add_argument("ref"); i.add_argument("--kind", default="doc"); i.add_argument("--licence", default="public"); i.add_argument("--lang", default=""); i.add_argument("--owner", default=""); i.add_argument("--compile", action="store_true")
    c = sub.add_parser("compile"); c.add_argument("source_id")
    r = sub.add_parser("review"); r.add_argument("--status", default="pending")
    s = sub.add_parser("show"); s.add_argument("cs_id")
    ok = sub.add_parser("approve"); ok.add_argument("cs_id"); ok.add_argument("--by", required=True)
    no = sub.add_parser("reject"); no.add_argument("cs_id"); no.add_argument("--by", required=True); no.add_argument("--note", required=True)
    fb = sub.add_parser("fileback"); fb.add_argument("question", nargs="?", default=None)
    rv = sub.add_parser("reverify"); rv.add_argument("--limit", type=int, default=20)
    l = sub.add_parser("lint"); l.add_argument("--json", action="store_true"); l.add_argument("--write-page", action="store_true")
    sub.add_parser("terms")
    sub.add_parser("regions")
    t = sub.add_parser("token"); t.add_argument("--role", required=True, choices=["reader", "contributor", "curator", "admin"]); t.add_argument("--name", required=True)
    srv = sub.add_parser("serve"); srv.add_argument("--host"); srv.add_argument("--port", type=int)
    sub.add_parser("doctor")
    args = ap.parse_args(argv)

    cfg = config_mod.load(args.config)
    if args.cmd == "serve":
        from . import web
        web.serve(cfg, args.host, args.port)
        return EXIT_OK
    wiki = Wiki(cfg)
    try:
        if args.cmd == "ask":
            role = "curator" if args.actor.startswith("curator") else "reader"
            res = wiki.ask(args.question, args.lang, role=role)
            wiki.audit("ask", args.actor, question=args.question[:200], status=res.status)
            if args.json:
                print(res.to_json())
            else:
                print(res.answer or f"[error] {res.error}")
                print(f"\n— status={res.status} citations={len(res.citations)} "
                      f"retrieved={len(res.retrieved)} stale={len(res.stale)} "
                      f"tokens_in={res.input_tokens} elapsed={res.elapsed_s}s", file=sys.stderr)
                if res.filtered_confidential:
                    print(f"  hidden confidential pages: {res.filtered_confidential}", file=sys.stderr)
                for iss in res.issues:
                    print(f"  unverified: {iss['claim']!r} ({iss['reason']})", file=sys.stderr)
            if res.status == "error":
                return EXIT_INFRA if "gateway_down" in res.error or "retrieval_failed" in res.error else EXIT_FAIL
            return EXIT_OK
        if args.cmd == "ingest":
            meta = wiki.sources.add(args.ref, args.kind, args.licence, args.lang, args.owner)
            print(json.dumps(meta, indent=2, ensure_ascii=False))
            wiki.audit("ingest", args.actor, source=meta["id"], ref=args.ref,
                       licence=args.licence, kind=args.kind)
            if args.compile and not meta.get("duplicate"):
                cs = wiki.compile(meta["id"])
                print(f"change set {cs['id']}: {cs['status']} ({len(cs['pages'])} pages, "
                      f"{len(cs['problems'])} problems)")
            return EXIT_OK
        if args.cmd == "compile":
            cs = wiki.compile(args.source_id)
            print(f"change set {cs['id']}: {cs['status']} ({len(cs['pages'])} pages, "
                  f"{len(cs['problems'])} problems, conflicts={len(cs['conflicts'])})")
            return EXIT_OK if cs["status"] == "pending" else EXIT_FAIL
        if args.cmd == "review":
            for cs in wiki.changes.list(args.status):
                prot = f" PROTECTED:{','.join(cs['protected'])}" if cs["protected"] else ""
                print(f"{cs['id']}  {cs['status']:8}  src={cs['source']['id']}  "
                      f"pages={','.join(p['slug'] for p in cs['pages'])}  "
                      f"conflicts={len(cs['conflicts'])}{prot}")
                for c in cs["conflicts"]:
                    print(f"    conflict on {c.get('slug')}:")
                    print(f"      existing: {str(c.get('existing', ''))[:160]}")
                    print(f"      new     : {str(c.get('new', ''))[:160]}")
            return EXIT_OK
        if args.cmd == "show":
            print(json.dumps(wiki.changes.get(args.cs_id), indent=2, ensure_ascii=False))
            return EXIT_OK
        if args.cmd == "approve":
            print("applied:", ", ".join(wiki.approve(args.cs_id, args.by)))
            return EXIT_OK
        if args.cmd == "reject":
            wiki.reject(args.cs_id, args.by, args.note)
            print("rejected")
            return EXIT_OK
        if args.cmd == "fileback":
            cs = wiki.fileback(args.question)
            print(f"change set {cs['id']}: {cs['status']} ({len(cs['pages'])} pages, "
                  f"{len(cs['problems'])} problems) — review with `llmwiki review`")
            return EXIT_OK if cs["status"] == "pending" else EXIT_FAIL
        if args.cmd == "reverify":
            for row in wiki.reverify(args.limit):
                print(json.dumps(row, ensure_ascii=False))
            return EXIT_OK
        if args.cmd == "lint":
            rep = wiki.lint()
            if args.write_page:
                print("lint page:", wiki.write_lint_page(rep))
            if args.json:
                print(json.dumps(rep, indent=2, ensure_ascii=False))
            else:
                for k, v in rep.items():
                    print(f"{k}: {v if not isinstance(v, list) else len(v)}")
                    if isinstance(v, list):
                        for x in v[:20]:
                            print(f"   {x}")
            return EXIT_OK
        if args.cmd == "regions":
            from .regions import RegionList
            rf = cfg.path("wiki/regions.json")
            rl = RegionList.load(rf) if rf.exists() else None
            if rl is None:
                print(f"no {rf}; see wiki/regions.json (OQ-1)")
            else:
                print(f"source: {rl.expected_source or 'UNRESOLVED (OQ-1)'}; fetched_at: {rl.fetched_at}")
                for r in rl.regions:
                    print(" ", r)
                print(f"{len(rl.regions)} regions")
            return EXIT_OK
        if args.cmd == "terms":
            for t2 in wiki.terms():
                print(t2)
            return EXIT_OK
        if args.cmd == "token":
            from . import auth
            tok = auth.open_tokens(cfg).create(args.role, args.name, cfg)
            print(f"token (shown once, store it now): {tok}")
            return EXIT_OK
        if args.cmd == "doctor":
            return doctor(cfg)
    except (JiuwenError, StoreError) as e:
        print(f"[infra] {e}", file=sys.stderr)
        return EXIT_INFRA
    except (ChangeSetError, SourceError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return EXIT_FAIL
    return EXIT_FAIL


def doctor(cfg) -> int:
    checks = []
    jb = cfg.jiuwen.bin
    checks.append(("jiuwenswarm binary", bool(shutil.which(jb) or __path_exists(jb)), jb))
    data = cfg.path(cfg.jiuwen.data_dir)
    role = data / "agents" / f"{cfg.jiuwen.role}.md"
    checks.append(("dedicated instance data dir", data.exists(), str(data)))
    checks.append(("llmwiki role installed", role.exists(), str(role)))
    checks.append(("instance .env present (E1-S5)",
                   (data / "config" / ".env").exists(), str(data / "config" / ".env")))
    work = data / "work"
    checks.append(("code-mode work dir (R-10)", work.exists(), str(work)))
    with socket.socket() as s:
        s.settimeout(2)
        up = s.connect_ex(("127.0.0.1", cfg.jiuwen.gateway_port)) == 0
    checks.append(("LLMWiki gateway listening", up, f"127.0.0.1:{cfg.jiuwen.gateway_port}"))
    if cfg.gbrain.backend == "gbrain":
        env = dict(cfg.gbrain.env)
        home = env.get("GBRAIN_HOME", "~/.gbrain")
        from pathlib import Path
        import os
        home_path = Path(os.path.expanduser(home))
        if not home_path.is_absolute():
            home_path = config_mod.PROJECT_ROOT / home_path
        env["GBRAIN_HOME"] = str(home_path)
        checks.append(("gbrain binary", bool(shutil.which(cfg.gbrain.bin)), cfg.gbrain.bin))
        if home_path.exists():
            p = subprocess.run([cfg.gbrain.bin, "engine", "status"], capture_output=True,
                               text=True, timeout=30,
                               env={**os.environ, **env}) if shutil.which(cfg.gbrain.bin) else None
            engine = "unknown"
            if p and p.returncode == 0:
                engine = next((l.split(":", 1)[1].strip() for l in (p.stdout or "").splitlines()
                               if l.startswith("Engine")), p.stdout.strip()[:60])
            checks.append(("gbrain engine", bool(p and p.returncode == 0 and "postgres" in engine.lower()),
                           f"GBRAIN_HOME={home} engine={engine}"))
        else:
            checks.append(("gbrain engine", False, f"GBRAIN_HOME={home} missing"))
    else:
        checks.append(("store backend", True,
                       f"files (keyword-only, not launch-grade — PRD B-1) at {cfg.path(cfg.gbrain.files_dir)}"))
    embed_url = cfg.gbrain.env.get("LITELLM_BASE_URL", "")
    if embed_url:
        import urllib.request as _u
        try:
            _u.urlopen(embed_url.rstrip("/") + "/models", timeout=3)
            checks.append(("embedding endpoint", True, embed_url))
        except _u.HTTPError:
            # TEI answers 404 for /models but any HTTP response proves the endpoint is up
            checks.append(("embedding endpoint", True, f"{embed_url} (reachable)"))
        except Exception as e:
            checks.append(("embedding endpoint", False, f"{embed_url} ({type(e).__name__})"))
    else:
        checks.append(("embedding endpoint", False, "not configured (keyword-only, not launch-grade)"))
    checks.append(("pdftotext (PDF ingest)", bool(shutil.which("pdftotext")), "optional"))
    tok = cfg.path(cfg.web.tokens_file)
    checks.append(("web token store", tok.exists(), f"{tok} (create with `llmwiki token`)"))
    bad = 0
    for name, ok, detail in checks:
        print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}")
        bad += (not ok) and detail != "optional"
    return EXIT_OK if not bad else EXIT_FAIL


def __path_exists(p: str) -> bool:
    from pathlib import Path
    return Path(p).exists()


if __name__ == "__main__":
    sys.exit(main())
