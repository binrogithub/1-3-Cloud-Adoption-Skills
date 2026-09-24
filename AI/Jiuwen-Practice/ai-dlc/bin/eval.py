#!/usr/bin/env python3
"""bin/eval — the plane's small evaluation set (P1-3).

~20 tasks was the Anthropic finding: a small fixed set, run before and
after a plane change, beats a large one run once. This runner
materialises each task's fixture as a fresh git repo, dispatches one
code session per task through the same client the plane uses, judges
deterministically (file exists / content pattern / command exit), and
writes comparable results files under evals/results/ tagged with the
plane's git sha. --compare names what changed between two runs.

The judge is deliberately mechanical here: checks assert behaviour, not
opinion. An LLM-judge pass can layer on later; a deterministic baseline
that two plane versions can be compared against comes first.

Usage:
  python3 bin/eval.py                       # run the set, write results
  python3 bin/eval.py --only fix-off-by-one
  python3 bin/eval.py --compare A.json B.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SET_PATH = ROOT / "evals" / "set.json"
RESULTS_DIR = ROOT / "evals" / "results"
CLIENT = os.environ.get("AI_DLC_EVAL_CLIENT",
                        "/root/.local/bin/jiuwenswarm")
TIMEOUT = int(os.environ.get("AI_DLC_EVAL_TIMEOUT", "240"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plane_git() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def materialise(task: dict, run_root: Path) -> Path:
    d = run_root / task["id"]
    d.mkdir(parents=True)
    for rel, content in (task.get("files") or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    subprocess.run(["git", "-c", "user.name=eval", "-c",
                    "user.email=eval@eval", "-C", str(d), "add", "-A"],
                   check=True)
    subprocess.run(["git", "-c", "user.name=eval", "-c",
                    "user.email=eval@eval", "-C", str(d), "commit", "-q",
                    "--allow-empty", "-m", "fixture"], check=True)
    return d


def run_checks(task: dict, d: Path) -> list[dict]:
    results = []
    for c in task.get("checks", []):
        kind = c.get("kind")
        want_rc = int(c.get("expect_rc", 0))
        try:
            if kind == "exists":
                ok = (d / c["path"]).is_file()
                detail = c["path"]
            elif kind == "contains":
                ok = c["pattern"] in (d / c["path"]).read_text(
                    encoding="utf-8", errors="replace")
                detail = "%s ~ %s" % (c["path"], c["pattern"][:40])
            elif kind == "command":
                r = subprocess.run(c["cmd"], cwd=str(d),
                                   capture_output=True, text=True,
                                   timeout=120)
                ok = (r.returncode == want_rc)
                detail = " ".join(c["cmd"])[:60]
            else:
                ok, detail = False, "unknown check kind %r" % kind
        except Exception as exc:                    # noqa: BLE001
            ok, detail = False, repr(exc)[:80]
        results.append({"kind": kind, "ok": ok, "detail": detail})
    return results


def brief(task: dict) -> str:
    return "\n".join([
        task["prompt"],
        "",
        "Objective: %s" % task.get("objective", task["id"]),
        "Expected output: the files this task names, in this repository "
        "root, with the behaviour the task states.",
        "Tools: your shell and file tools; work only inside the current "
        "directory.",
        "Boundary: write only inside the current directory; finish with "
        "a one-line summary of what changed.",
    ])


def run_set(only: str | None) -> int:
    tasks = json.loads(SET_PATH.read_text(encoding="utf-8"))["tasks"]
    if only:
        tasks = [t for t in tasks if t["id"] == only]
        if not tasks:
            print(json.dumps({"refused": True,
                              "why": "no task %r in the set" % only}),
                  file=sys.stderr)
            return 1
    epoch = int(time.time())
    out = {"ran_at": now_iso(), "plane_git": plane_git(),
           "client": CLIENT, "tasks": []}
    passed = 0
    with tempfile.TemporaryDirectory(prefix="aidlc-eval-") as tmp:
        run_root = Path(tmp)
        for t in tasks:
            d = materialise(t, run_root)
            started = time.monotonic()
            rc = None
            try:
                proc = subprocess.run(
                    [CLIENT, "chat", brief(t), "--jsonl",
                     "--cwd", str(d), "--mode", "code.normal",
                     "--timeout", str(TIMEOUT),
                     "--session", "eval-%s-%d" % (t["id"], epoch)],
                    capture_output=True, text=True, cwd=str(d),
                    timeout=TIMEOUT + 60)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                rc = None
            checks = run_checks(t, d)
            ok = rc == 0 and all(c["ok"] for c in checks)
            passed += int(ok)
            out["tasks"].append({
                "id": t["id"], "client_rc": rc, "passed": ok,
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "checks": checks})
            print("%-22s %s (%ss)" % (t["id"], "PASS" if ok else "FAIL",
                                      out["tasks"][-1]["elapsed_seconds"]),
                  flush=True)
    out["summary"] = {"total": len(out["tasks"]), "passed": passed,
                      "pass_rate": round(passed / len(out["tasks"]), 3)}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / ("run-%s.json" % datetime.now().strftime(
        "%Y%m%d-%H%M%S"))
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(json.dumps({"results": str(path), **out["summary"]},indent=2))
    return 0


def compare(a_path: str, b_path: str) -> int:
    a = json.loads(Path(a_path).read_text(encoding="utf-8"))
    b = json.loads(Path(b_path).read_text(encoding="utf-8"))
    by_id = lambda r: {t["id"]: t for t in r["tasks"]}    # noqa: E731
    ba, bb = by_id(a), by_id(b)
    rows = []
    for tid in sorted(set(ba) | set(bb)):
        ta, tb = ba.get(tid), bb.get(tid)
        rows.append({
            "id": tid,
            "a": (ta or {}).get("passed"),
            "b": (tb or {}).get("passed"),
            "changed": (ta or {}).get("passed") != (tb or {}).get("passed"),
            "elapsed_a": (ta or {}).get("elapsed_seconds"),
            "elapsed_b": (tb or {}).get("elapsed_seconds")})
    print(json.dumps({
        "a": {"file": a_path, "plane_git": a.get("plane_git"),
              "pass_rate": (a.get("summary") or {}).get("pass_rate")},
        "b": {"file": b_path, "plane_git": b.get("plane_git"),
              "pass_rate": (b.get("summary") or {}).get("pass_rate")},
        "regressions": [r["id"] for r in rows
                        if r["a"] and r["changed"] and not r["b"]],
        "improvements": [r["id"] for r in rows
                         if not r["a"] and r["changed"] and r["b"]],
        "tasks": rows}, indent=2, ensure_ascii=False))
    return 0


DESIGN_SET_PATH = ROOT / "evals" / "design-select-set.json"


def run_design_eval(root: Path | None = None) -> int:
    """P1-C: offline design-selection eval over the fixed query set.
    Deterministic retrieval only — the shortlist ranking the plane
    would use in D0, no session, no billing. Reports hit@1/@3 and the
    deduped-pool size; AI_DLC_NO_INTENT_META=1 gives the before-arm."""
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("plan_eval", ROOT / "bin" / "plan.py")
    plan = _ilu.module_from_spec(spec)
    spec.loader.exec_module(plan)
    data = json.loads(DESIGN_SET_PATH.read_text(encoding="utf-8"))
    troot = Path(root) if root else Path(plan.OPENDESIGN_ROOT)
    cands = plan._scan_design_candidates(troot)
    idf = plan._build_design_index(troot)["idf"]
    meta_off = os.environ.get("AI_DLC_NO_INTENT_META") == "1"
    hits1 = hits3 = 0
    rows = []
    for item in data["queries"]:
        q = item["q"]
        golden = item["golden"]
        qtoks = plan._tokenize_query(q) - plan._negated_tokens(q)
        kw = {"query_tokens": qtoks,
              "keywords": {t for t in qtoks
                           if t.isascii() and len(t) >= 3},
              "surface_hint": None, "text": q.lower()}
        scored = sorted(
            ((plan._score_candidate(c, kw, idf), c) for c in cands),
            key=lambda x: (x[0], plan._tiebreak_key(x[1])), reverse=True)
        ranked, _clusters = plan._dedup_scored(scored)
        top = [c["dir"] for _s, c in ranked[:3]]
        h1 = golden == top[0] if top else False
        h3 = golden in top
        hits1 += h1
        hits3 += h3
        rows.append({"q": q, "golden": golden, "top3": top,
                     "hit@1": h1, "hit@3": h3})
    n = len(rows)
    report = {
        "mode": "design-select", "root": str(troot),
        "intent_meta": "off (before-arm)" if meta_off else "on",
        "queries": n, "hit@1": round(hits1 / max(1, n), 3),
        "hit@3": round(hits3 / max(1, n), 3), "rows": rows,
        "plane_git": plane_git(), "ts": now_iso(),
    }
    out = RESULTS_DIR / f"design-{report['plane_git'][:8]}" \
        f"-{'nometa' if meta_off else 'meta'}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"},
                     indent=2))
    print(f"results: {out}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(prog="eval.py")
    ap.add_argument("--only", default=None, help="run one task by id")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"))
    ap.add_argument("--design", action="store_true",
                    help="run the offline design-selection eval "
                         "(deterministic retrieval, hit@1/@3)")
    ap.add_argument("--design-root", default=None,
                    help="OpenDesign root override for --design (tests)")
    args = ap.parse_args()
    if args.design:
        return run_design_eval(Path(args.design_root) if args.design_root
                               else None)
    if args.compare:
        return compare(*args.compare)
    return run_set(args.only)


if __name__ == "__main__":
    sys.exit(main())
