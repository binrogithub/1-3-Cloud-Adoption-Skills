#!/usr/bin/env python3
"""bin/report — the human surface + the gates that stay (devteam D1)

No verification role exists: nothing here judges whether an artifact is
correct. The machine criteria are structural only — the repository head
advanced, product files landed, and the plane's signed verdict says the
change passes strict spec validation (openspec is never executed
caller-side; the records under AI_DLC_RECORDS are the only spec
surface). Correctness is judged by the human who reads the deliverable
at the merge gate; every report says so plainly.

No budget capability exists (landing L1): nothing here computes, caps,
stops, warns or annotates on a token total. Usage lives where upstream
already records it — the gateway's session histories and the agent
transcripts — read there, never combined here.

Subcommands:
  init     stamp a task workspace (route, intent pointer, base sha,
           change id for spec validation)
  deliver  G-DELIVER-1 + spec validity → report.json, and the four-state
           human surface. delivered = head advanced ∧ product files
           landed ∧ a signed spec verdict with rc 0 ∧ MERGE_GATE
           approved with a rationale by a human. The verdict is read
           from the plane's records — never produced here.
  gate     write/read the MERGE_GATE answer file (the human's approval)
  exception record a person's explicit exception to the route check,
           with the reason that makes it explicit

The person sees four states — Working / Checking / Ready /
Needs your decision — derived on every write, never stored ahead.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

# v2 design architecture: design/ IS a product directory. Its files
# (tokens.css, tokens.json, components.md, pages.md, assets.md) count
# toward landed_files/landed_bytes — the structural fix for S1 ("merge
# gate can't see design"). Do NOT add design/** to excludes.
PRODUCT_EXCLUDES = (".ai-dlc/**", "CLAUDE.md", "findings.json",
                    "__pycache__/**", "*.pyc", ".pytest_cache/**",
                    "audits/**", ".ctx-echo", ".skill-echo", "blueprint.json")
GATE_BLOCKED_EXIT = 17
GATES = ["G-DELIVER-1", "MERGE_GATE"]
ROUTE_VALUES = ("inline", "planned")


# ── the plane's records: the only spec surface the caller reads ─────
#
# openspec is never executed caller-side (containment §1, invariant
# I1): the artifact graph, the artifact statuses and every validator
# verdict arrive as records the plane produced and signed. A record
# that is missing or wrongly signed is reported as exactly that —
# never recomputed here, never substituted with a caller-side CLI run.

RECORDS_ROOT = Path(os.environ.get("AI_DLC_RECORDS",
                                   "/var/lib/aidlc/records"))
VERDICT_KEY_PATH = Path(os.environ.get("AI_DLC_VERDICT_KEY",
                                       "/etc/aidlc/verdict.key"))
SPECS_HOME = Path(os.environ.get("AI_DLC_SPECS", "/var/lib/aidlc/specs"))


def plane_root(repo: Path) -> Path:
    """The project's root inside the plane's spec home (containment
    N6): the directory the tree's own tools resolve `openspec/` from.
    One root per repository, named by the repo's identity slug."""
    return SPECS_HOME / repo_id(repo)


def plane_tree(repo: Path) -> Path:
    """The project's openspec tree in the plane's home — the ONLY place
    the spec surface lives once N6 has migrated it. The caller names
    where the tree lives; it never constructs, mirrors or copies what is
    inside (D12)."""
    return plane_root(repo) / "openspec"


def repo_id(repo: Path) -> str:
    """The tree's identity in the records store: the absolute path with
    its separators doubled away — the same slug staging names copies
    by."""
    return str(Path(repo).resolve()).strip("/").replace("/", "--")


def record_dir(change: str) -> Path:
    return RECORDS_ROOT / change


def canonical_payload(record: dict) -> str:
    """The signed surface of a record: every field except the hmac, in
    sorted-key compact JSON — one canonical form, so a record can be
    re-verified by anyone holding the key."""
    return json.dumps({k: record[k] for k in sorted(record)
                       if k != "hmac"},
                      sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def record_hmac(record: dict, key: bytes) -> str:
    return hmac.new(key, canonical_payload(record).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def sign_record(record: dict, key: bytes) -> dict:
    out = {k: v for k, v in record.items() if k != "hmac"}
    out["hmac"] = record_hmac(out, key)
    return out


def verify_record(record: object) -> bool:
    if not isinstance(record, dict) or not record.get("hmac"):
        return False
    try:
        key = VERDICT_KEY_PATH.read_bytes()
    except OSError:
        return False
    return hmac.compare_digest(record_hmac(record, key),
                               str(record["hmac"]))


def signed_records(change: str, prefix: str) -> tuple[list[dict], list[str]]:
    """Every <prefix>-<seq>.json record for the change, signature
    verified, oldest first. A record whose signature does not verify is
    dropped and named — it is tampering evidence, not a verdict."""
    good, rejected = [], []
    if not record_dir(change).is_dir():
        return [], []
    for p in sorted(record_dir(change).glob(f"{prefix}-*.json")):
        rec = load_json(p, {})
        if verify_record(rec):
            good.append(rec)
        else:
            rejected.append(str(p))
    return good, rejected


def next_record_seq(change: str, prefix: str) -> int:
    """One past the highest <prefix>-<seq> already on disk, so a second
    record never overwrites a first."""
    n = 0
    d = record_dir(change)
    if d.is_dir():
        for p in d.glob(f"{prefix}-*.json"):
            try:
                n = max(n, int(p.stem.split("-")[-1]))
            except ValueError:
                continue
    return n + 1


def write_record(change: str, prefix: str, record: dict) -> Path:
    """Sign and persist one record — the single writing path every
    producer shares (a dispatch's judge here, a test's stand-in plane in
    records_tool), so what is written is always the shape the readers
    above verify."""
    key = VERDICT_KEY_PATH.read_bytes()
    d = record_dir(change)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{prefix}-{next_record_seq(change, prefix):03d}.json"
    path.write_text(json.dumps(sign_record(record, key), indent=2,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def plane_graph(change: str) -> dict | None:
    """The change's artifact graph, produced once by a graph dispatch.
    Static for the change's life: ids, dependency edges, and the
    conditional artifacts' own inclusion conditions, verbatim."""
    recs, _ = signed_records(change, "graph")
    for rec in reversed(recs):
        if rec.get("verb") == "graph":
            return rec
    return None


def plane_status(change: str) -> dict | None:
    """The newest status snapshot a status dispatch recorded: artifact
    states and the phase-complete flag, as the plane reported them. A
    record of its own (PRD §8: graph · artifact-status · verdict are
    three records) — the validate dispatch runs one command only and
    cannot carry it."""
    recs, _ = signed_records(change, "status")
    for rec in reversed(recs):
        if rec.get("verb") == "status" and isinstance(rec.get("artifacts"),
                                                      dict):
            return {"artifacts": rec.get("artifacts"),
                    "is_planning_complete":
                        bool(rec.get("is_planning_complete"))}
    return None


def newest_verdict(change: str) -> dict | None:
    """The newest validate verdict — the only source of a spec judgment
    the caller ever reads."""
    recs, _ = signed_records(change, "verdict")
    for rec in reversed(recs):
        if rec.get("verb") == "validate":
            return rec
    return None


def artifacts_view(change: str) -> list[dict]:
    """The graph and the newest status merged into the one shape the
    role readers consume: the graph static from its record, the
    statuses live-side from the newest verdict that carries them."""
    g = plane_graph(change)
    if g is None:
        return []
    states = (plane_status(change) or {}).get("artifacts") or {}
    out = []
    for a in g.get("artifacts", []):
        aid = a.get("id")
        out.append({"id": aid, "requires": list(a.get("requires", [])),
                    "conditional": bool(a.get("conditional")),
                    "conditions": list(a.get("conditions", [])),
                    "status": states.get(aid, "unknown")})
    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event(task_dir: Path, **kw) -> None:
    kw.setdefault("event", kw.pop("kind", "NOTE"))
    kw["ts"] = now_iso()
    with (task_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


def load_json(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default


def save_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True,
                          cwd=str(repo))
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}: {proc.stderr[:200]}")
    return proc.stdout


def excluded(path: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(path, pat) or fnmatch(Path(path).name, pat)
               for pat in PRODUCT_EXCLUDES)


def stale_route_guard(task_dir: Path) -> dict | None:
    """A task record carrying a route that names no existing plane stops
    the run for the human — the run never guesses an equivalent. A closed
    record keeps its historical value."""
    state = load_json(task_dir / "state.json", {})
    route = state.get("route")
    if route is None or route in ROUTE_VALUES:
        return None
    if state.get("stage") in ("DONE", "FAILED", "CANCELLED"):
        return None
    return {"stale_route": True, "route": route,
            "allowed": list(ROUTE_VALUES), "stage": state.get("stage"),
            "why": ("this task record carries a route naming no existing "
                    "plane — a human chooses an equivalent; the run does "
                    "not guess")}


# ── the route threshold: one number, read from the config ───────────

# this tool's own configuration (bin/ sits in the tool repo, never in
# the target the tool operates on)
CONFIG_PATH = (Path(__file__).resolve().parent.parent / "config"
               / "collapsed.config.yaml")
# the route measurement counts the deliverable, not the bookkeeping:
# the delivery gate's own non-product patterns, plus the openspec tree,
# the dispatch evidence and the gateway bookkeeping dirs
ROUTE_EXCLUDES = list(PRODUCT_EXCLUDES) + [
    "openspec/**", "evidence/**",
    ".agent_history/**", "coding_memory/**", "prompt_attachment/**"]


def config_scalar(section: str, key: str) -> object:
    """One scalar from the project configuration. No YAML dependency:
    the file is ours and its scalars are simple; a line this reader
    cannot make sense of reads as absent — the route check then stops
    for a person rather than assuming a value."""
    if not CONFIG_PATH.is_file():
        return None
    cur = None
    for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace():
            cur = stripped.split(":", 1)[0].strip()
            continue
        m = re.match(r"[\w.-]+:\s*(.+)$", stripped)
        if m and cur == section \
                and stripped.split(":", 1)[0].strip() == key:
            val = m.group(1).split("#", 1)[0].strip().strip("'\"")
            return val or None
    return None


def route_threshold() -> int | None:
    """The file count at which the routing table sends a change to the
    planning plane — one configured number, or None when it is not
    readable (the check stops; it never assumes)."""
    raw = config_scalar("execution", "planning_threshold_files")
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def resolve_work_ref(repo: Path, state: dict) -> dict:
    """Resolve the ref a change's work lives on.

    Order: the branch recorded at init > the task/<change> convention >
    HEAD. Any other task/* branch found while the chosen ref is HEAD is
    carried as `mismatch` - that is the country-b shape, and the shape
    every caller must be able to see.

    Z5: this is one of two text-identical copies (the other is in
    plan.py); gate Y7 asserts they agree."""
    def _verify(ref):
        r = subprocess.run(["git", "-C", str(repo), "rev-parse",
                            "--verify", "-q", ref],
                           capture_output=True, text=True, cwd=str(repo))
        return r.stdout.strip() if r.returncode == 0 else None

    change   = state.get("change_id")
    recorded = state.get("branch")
    out = {"ref": "HEAD", "kind": "head", "resolved_by": "fallback",
           "sha": None, "convention": f"task/{change}" if change else None,
           "recorded_branch": recorded, "other_task_branches": [],
           "mismatch": None}
    for branch, how in ((recorded, "recorded"),
                        (f"task/{change}" if change else None, "convention")):
        if not branch:
            continue
        sha = _verify("refs/heads/" + branch)
        if sha:
            out.update(ref="refs/heads/" + branch, kind="task_branch",
                       resolved_by=how, sha=sha)
            break
    if out["kind"] == "head":
        out["sha"] = _verify("HEAD")

    r = subprocess.run(["git", "-C", str(repo), "for-each-ref",
                        "--format=%(refname:short)", "refs/heads/task/"],
                       capture_output=True, text=True, cwd=str(repo))
    others = [b for b in r.stdout.split() if b and
              "refs/heads/" + b != out["ref"]]
    out["other_task_branches"] = others
    if out["kind"] == "head" and others:
        out["mismatch"] = {
            "expected": out["convention"],
            "found": others,
            "why": ("the work was measured on HEAD because no branch named "
                    "%s exists, but %s does - a task branch named after "
                    "something other than the change id is invisible to "
                    "every measurement"
                    % (out["convention"], ", ".join(others))),
            "remedy": ("git -C %s branch -m %s %s   (or record the branch "
                       "at init)" % (repo, others[0], out["convention"]))}
    return out


def route_measurement(repo: Path, base: str | None,
                      ref: str = "HEAD") -> dict:
    """What the change actually delivers, counted: the product files in
    the base..ref diff, excluding the paths the delivery gate already
    treats as non-product plus the openspec tree, the dispatch evidence
    and the gateway bookkeeping. The excluded patterns are listed beside
    the count so the measurement can be re-derived."""
    from fnmatch import fnmatch
    head = git(repo, "rev-parse", ref).strip()
    files, excluded = [], []
    if base and head != base:
        for f in git(repo, "diff", "--name-only", base, ref).splitlines():
            hit = any(fnmatch(f, pat) or fnmatch(Path(f).name, pat)
                      for pat in ROUTE_EXCLUDES)
            (excluded if hit else files).append(f)
    return {"measured_files": len(files), "files": files[:10],
            "excluded_patterns": list(ROUTE_EXCLUDES),
            "excluded_count": len(excluded)}


def route_check(task_dir: Path, repo: Path, state: dict) -> tuple[dict, dict | None]:
    """The recorded route checked against the change it describes. The
    deliverable is measured and the threshold is one configured number;
    an inline route carrying a change at or above it stops the task for
    a person unless an explicit exception with a reason is recorded —
    the two options are re-running through the plane or recording that
    exception. Returns (the check record to carry in the report, the
    block that stops the task, if any)."""
    route = state.get("route")
    threshold = route_threshold()
    work = resolve_work_ref(repo, state)
    measurement = route_measurement(repo, state.get("base_sha"),
                                     ref=work["ref"])
    check = {"route": route, "threshold": threshold,
             "threshold_source": str(CONFIG_PATH), **measurement,
             "work_ref": work}
    if route != "inline":
        if route == "planned" and measurement["measured_files"] == 0:
            why = ("the planned route measured no files on %s - a planned "
                   "change exists because work was expected, so an empty "
                   "measurement is a broken measurement or an empty branch, "
                   "never a delivery" % measurement.get("measured_ref"))
            block = {"why": why, **check}
            if work.get("mismatch"):
                block["work_ref_mismatch"] = work["mismatch"]
                block["why"] = why + " - " + work["mismatch"]["why"]
            return check, block
        return check, None
    if threshold is None:
        return check, {"why": ("no route threshold is configured — the "
                               "check stops rather than assuming one"),
                       **check}
    if measurement["measured_files"] < threshold:
        return check, None
    exc = load_json(task_dir / "gates" / "gate-route.answer.json")
    if isinstance(exc, dict) and exc.get("decision") == "exception" \
            and str(exc.get("reason", "")).strip():
        check["exception"] = {"reason": exc.get("reason"),
                              "author": exc.get("author"),
                              "recorded_at": exc.get("ts")}
        return check, None
    return check, {"why": ("an inline route carries a change at or above "
                           "the configured threshold — the routing table "
                           "sends it to the planning plane"),
                   **check}


def is_git_repo(repo: Path) -> bool:
    """N6②: --repo must be an existing git repository. The country-d
    path-typo (wrote <workspace-root>/... when the repo was in /tmp/)
    was silent — this check ends that."""
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def cmd_next(task_dir: Path, repo: Path) -> int:
    """N1/N2: ask the system what to do next. Read-only (V2): no
    dispatch, no state change, no directory creation. The recommendation
    is derived from the task's state files and the plane's records —
    the same preconditions the verbs check (V6), not a second copy.

    Output shape (U-B):
        stage, human_state, blocked_on, why, do, then, not_yet
    where `do` is a directly executable command line and `not_yet`
    names what cannot run yet and the exit code it would return.
    """
    # N6②: validate repo before reading state — a non-existent repo
    # is the country-d path-typo failure mode.
    if not is_git_repo(repo):
        print(json.dumps({
            "stage": None, "human_state": None,
            "blocked_on": "a repository that exists",
            "why": ("--repo %s is not a git repository — the path must "
                    "name an existing git working tree" % repo),
            "do": ("git init <repo>  # or correct the path to the "
                   "actual repository"),
            "then": [], "not_yet": []
        }, indent=2, ensure_ascii=False))
        return 1

    state = load_json(task_dir / "state.json", {})
    if not state:
        print(json.dumps({
            "stage": None, "human_state": None,
            "blocked_on": "initialization",
            "why": "no task workspace at %s — run init first" % task_dir,
            "do": ("python3 bin/report.py init --task-dir %s --repo %s "
                   "--route inline|planned --task-id <id> --change <change-id>"
                   % (task_dir, repo)),
            "then": [], "not_yet": []
        }, indent=2, ensure_ascii=False))
        return 0

    stage = state.get("stage", "WORK")
    route = state.get("route", "inline")
    change_id = state.get("change_id")
    report = load_json(task_dir / "report.json", {})
    gate_ans = load_json(task_dir / "gates" / "gate-merge.answer.json")
    gate_req = load_json(task_dir / "gates" / "gate-merge.request.json")
    planning = load_json(task_dir / "planning.json", {})
    dispatches = (planning or {}).get("plane_dispatches", {})

    def _cmd(*parts: str) -> str:
        return " ".join(parts)

    # ---- DONE / FAILED / CANCELLED — terminal ---------------------------
    if stage in ("DONE", "CANCELLED"):
        print(json.dumps({
            "stage": stage,
            "human_state": human_state(stage, report.get("delivered")),
            "blocked_on": None,
            "why": "the task is %s" % ("complete" if stage == "DONE"
                                       else "cancelled"),
            "do": None, "then": [], "not_yet": []
        }, indent=2, ensure_ascii=False))
        return 0

    if stage == "FAILED":
        print(json.dumps({
            "stage": "FAILED",
            "human_state": "Needs your decision",
            "blocked_on": "a person",
            "why": "delivery reported failure — investigate and fix",
            "do": ("fix the failure, then: python3 bin/report.py deliver "
                   "--task-dir %s --repo %s --outcome completed"
                   % (task_dir, repo)),
            "then": [], "not_yet": []
        }, indent=2, ensure_ascii=False))
        return 0

    # ---- ROUTE_STOP — the route check blocked ---------------------------
    if stage == "ROUTE_STOP":
        print(json.dumps({
            "stage": "ROUTE_STOP",
            "human_state": "Needs your decision",
            "blocked_on": "a person",
            "why": ("the route check stopped the task — the measured "
                    "product files contradict the recorded route"),
            "do": ("python3 bin/report.py exception --task-dir %s "
                   "--reason <why> --author <your-name>" % task_dir),
            "then": ["or re-init with --route planned and re-dispatch"],
            "not_yet": [{"verb": "deliver", "why": "route not resolved",
                         "exit_if_run": 17}]
        }, indent=2, ensure_ascii=False))
        return 0

    # ---- MERGE_GATE — the delivery stands; gate + close -----------------
    if stage == "MERGE_GATE":
        if gate_ans and gate_ans.get("decision") == "approve":
            # approved → close
            do = _cmd("python3 bin/plan.py close --change", change_id or "<id>",
                      "--repo", str(repo), "--task-dir", str(task_dir))
            print(json.dumps({
                "stage": "MERGE_GATE",
                "human_state": "Ready",
                "blocked_on": None,
                "why": "the merge gate is approved — close merges, "
                       "archives, and cleans up",
                "do": do, "then": [], "not_yet": []
            }, indent=2, ensure_ascii=False))
            return 0
        if gate_ans and gate_ans.get("decision") == "request_changes":
            print(json.dumps({
                "stage": "MERGE_GATE",
                "human_state": "Needs your decision",
                "blocked_on": "a person",
                "why": "the gate requested changes — revise and re-deliver",
                "do": ("address the requested changes, then: "
                       "python3 bin/report.py deliver --task-dir %s "
                       "--repo %s --outcome completed" % (task_dir, repo)),
                "then": [], "not_yet": []
            }, indent=2, ensure_ascii=False))
            return 0
        if gate_ans and gate_ans.get("decision") == "cancel":
            print(json.dumps({
                "stage": "MERGE_GATE",
                "human_state": "Needs your decision",
                "blocked_on": None,
                "why": "the gate was cancelled — sweep to clean up",
                "do": ("python3 bin/plan.py sweep --change %s --repo %s"
                       % (change_id or "<id>", repo)),
                "then": [], "not_yet": []
            }, indent=2, ensure_ascii=False))
            return 0
        # gate requested but not answered, or not yet requested
        if gate_req and not gate_ans:
            print(json.dumps({
                "stage": "MERGE_GATE",
                "human_state": "Needs your decision",
                "blocked_on": "a person",
                "why": "the delivery report stands; the merge gate is "
                       "unanswered",
                "do": ("a person answers: python3 bin/report.py gate "
                       "--task-dir %s --decision approve --approver "
                       "<your-name> --rationale <why>" % task_dir),
                "then": ["then: python3 bin/plan.py close --change %s "
                         "--repo %s --task-dir %s"
                         % (change_id or "<id>", repo, task_dir)],
                "not_yet": [{"verb": "close",
                             "why": "no approval recorded",
                             "exit_if_run": 11}]
            }, indent=2, ensure_ascii=False))
            return 0
        # gate not yet requested
        print(json.dumps({
            "stage": "MERGE_GATE",
            "human_state": "Needs your decision",
            "blocked_on": None,
            "why": "delivery reported merge_pending — request the gate",
            "do": ("python3 bin/report.py gate --request --task-dir %s "
                   "--repo %s" % (task_dir, repo)),
            "then": ["a person answers with --decision approve|request_changes "
                     "--approver <name> --rationale <text>"],
            "not_yet": [{"verb": "close", "why": "no approval recorded",
                         "exit_if_run": 11}]
        }, indent=2, ensure_ascii=False))
        return 0

    # ---- WORK — the default; deliver or validate first ------------------
    # For the planned route, the spec verdict must exist before deliver
    # can report spec_valid. If no validate dispatch has run, point there.
    has_validate = "validate" in dispatches
    # A1.2: if design-pick ran, carry the selected SKILL.md into the WORK
    # stage.  The main session has all the context (requirements, spec,
    # design.md, the files it just wrote) — it only needs to read one
    # more file.  The marginal cost of design drops from "a 1800s
    # cold-start rewrite" to "one extra file read".
    design_carry = None
    selection = state.get("design_selection")
    if isinstance(selection, dict) and selection.get("skill"):
        skill = selection["skill"]
        design_carry = {
            "read_first": skill.get("path"),
            "sha256": skill.get("sha256"),
            "name": skill.get("name"),
            "instruction": (
                "Read the selected SKILL.md in full before writing the "
                "pages. Apply its design system, tokens, and component "
                "patterns to the product surface. Real content throughout "
                "— lorem ipsum, placeholder images, and TODO markers are "
                "failures. Every local asset must exist when you are done."),
        }
        if selection.get("design_system"):
            design_carry["design_system"] = selection["design_system"]
    if not report:
        if route == "planned" and change_id and not has_validate:
            do = _cmd("python3 bin/plan.py validate --change", change_id,
                      "--repo", str(repo))
            print(json.dumps({
                "stage": "WORK",
                "human_state": "Working",
                "blocked_on": None,
                "why": ("planned route, no spec verdict yet — validate "
                        "produces the signed verdict deliver reads"),
                "do": do,
                "design_carry": design_carry,
                "then": ["then: python3 bin/report.py deliver --task-dir %s "
                         "--repo %s --outcome completed" % (task_dir, repo)],
                "not_yet": []
            }, indent=2, ensure_ascii=False))
            return 0
        do = ("python3 bin/report.py deliver --task-dir %s --repo %s "
              "--outcome completed" % (task_dir, repo))
        print(json.dumps({
            "stage": "WORK",
            "human_state": "Working",
            "blocked_on": None,
            "why": "work in progress — deliver when the code and tests pass",
            "do": do, "design_carry": design_carry,
            "then": [], "not_yet": []
        }, indent=2, ensure_ascii=False))
        return 0

    # report exists but stage still WORK (outcome=working)
    do = ("python3 bin/report.py deliver --task-dir %s --repo %s "
          "--outcome completed" % (task_dir, repo))
    print(json.dumps({
        "stage": "WORK",
        "human_state": "Working",
        "blocked_on": None,
        "why": "a delivery report exists but outcome is still working — "
               "re-deliver as completed when ready",
        "do": do, "design_carry": design_carry,
        "then": [], "not_yet": []
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_correct(task_dir: Path, keys: list[str],
                corrected_by: str | None, why: str | None) -> int:
    """Remove specified keys from planning.json and append a
    RECORD_CORRECTION event. The correction is a human act — a model may
    not sign it (L6), and a correction without a reason is the silence
    this check exists to end. The keys are removed from planning.json;
    the event records what was removed, who decided, and why, so the
    correction is never a silent delete (N6/R5)."""
    who = stated_actor(corrected_by, "the correction's author")
    if who is None:
        return 1
    if not (why or "").strip():
        print("refusing: a correction requires --why — removing a record "
              "without a reason is the silence this check exists to end",
              file=sys.stderr)
        return 1
    if not keys:
        print("refusing: no keys to correct — pass --remove-key for each "
              "planning.json key to remove", file=sys.stderr)
        return 1
    planning = load_json(task_dir / "planning.json", {})
    removed = []
    for k in keys:
        if k in planning:
            del planning[k]
            removed.append(k)
    if not removed:
        print(json.dumps({"corrected": False, "task_dir": str(task_dir),
                          "note": "none of the specified keys were present"},
                         indent=2, ensure_ascii=False))
        return 0
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="RECORD_CORRECTION",
          corrected_by=who, removed=removed, why=why)
    print(json.dumps({"corrected": True, "task_dir": str(task_dir),
                      "removed": removed, "by": who, "why": why},
                     indent=2, ensure_ascii=False))
    return 0


def cmd_exception(task_dir: Path, reason: str | None, author: str | None,
                  design_override: bool = False,
                  override_by: str | None = None,
                  override_why: str | None = None) -> int:
    """Record an explicit exception — either a route-check exception
    (reason + author) or a design-gate override (design_override + by
    + why). Neither is assumed: an exception is the moment a person
    overrides a gate, and one recorded with no stated author is an
    override with no one behind it — refused exactly as one without a
    reason is."""
    if design_override:
        # M8: design-gate override — a human overrides the design-
        # required gate with a name and a reason. A model may not
        # sign (L6/C9).
        who = stated_actor(override_by, "the design override's author")
        if who is None:
            return 1
        if not (override_why or "").strip():
            print("refusing: --design-override requires --why — an "
                  "override without a reason is the narration this "
                  "check exists to end", file=sys.stderr)
            return 1
        planning = load_json(task_dir / "planning.json", {})
        planning["design_override"] = {"by": who, "why": override_why,
                                        "ts": now_iso()}
        save_json(task_dir / "planning.json", planning)
        event(task_dir, event="DESIGN_OVERRIDE_RECORDED", by=who,
              why=override_why)
        print(json.dumps({"recorded": "design override",
                          "task_dir": str(task_dir), "by": who,
                          "why": override_why}))
        return 0
    # route-check exception (the original path)
    if not (reason or "").strip():
        print("refusing: an exception without a reason is the narration "
              "this check exists to end", file=sys.stderr)
        return 1
    author = stated_actor(author, "the exception's author")
    if author is None:
        return 1
    save_json(task_dir / "gates" / "gate-route.answer.json", {
        "gate_id": "gate-route", "decision": "exception",
        "reason": reason, "author": author, "ts": now_iso()})
    print(json.dumps({"recorded": "gate-route exception",
                      "task_dir": str(task_dir), "reason": reason,
                      "author": author}))
    return 0


# ── init ────────────────────────────────────────────────────────────

def cmd_init(task_dir: Path, repo: Path, route: str, task_id: str,
             change_id: str | None) -> int:
    task_dir.mkdir(parents=True, exist_ok=True)
    base = git(repo, "rev-parse", "HEAD").strip()
    stage = "WORK"
    human = "Working"
    # W3: the branch name is a contract, not a convention — decided here,
    # written to state.json, echoed to the executor. The executor never
    # invents a branch name.
    branch = f"task/{change_id}" if (route == "planned" and change_id) else None
    st = {
        "task_id": task_id, "route": route, "base_sha": base,
        "change_id": change_id,
        "repo": str(Path(repo).resolve()),
        "task_dir": str(Path(task_dir).resolve()),
        "stage": stage, "human_state": human, "started_at": now_iso()}
    if branch:
        st["branch"] = branch
    save_json(task_dir / "state.json", st)
    event(task_dir, event="TASK_STARTED", task_id=task_id, route=route,
          base_sha=base, change_id=change_id)
    out = {"task_dir": str(task_dir), "base_sha": base,
           "route": route, "change_id": change_id,
           "stage": stage, "human_state": human}
    if branch:
        out["branch"] = branch
        out["work_on"] = (f"git -C {repo} worktree add ../wt/{change_id} "
                          f"-b {branch}")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


# ── MERGE_GATE + delivery ───────────────────────────────────────────

# a stated identity names an actor, never a class of actor: the bare
# words below are the residue of the default this refusal ends — they
# claim a human without naming one, and an agent recording a decision
# in its own voice says so in the value itself
HUMAN_CLASS_WORDS = ("user", "human", "person")
# C9/L6: a model or agent may not sign an override, skip, or gate
# approval. country-d's route exception (author: "AI-DLC Executor") showed
# how a model self-signs — the new override paths close that hole.
MODEL_NAMES = ("ai-dlc executor", "agent", "model", "claude", "gpt",
               "glm", "ai", "bot", "assistant", "system", "executor",
               "automated", "ci")


def stated_actor(value: str | None, what: str) -> str | None:
    """The caller states who acted, or the command refuses. An identity
    is never assumed, and one that claims a human without naming one is
    exactly the silent attribution this exists to refuse. A model or
    agent name is refused just as firmly — an override, skip, or
    approval is a human act (L6)."""
    v = str(value or "").strip()
    if not v:
        print(f"refusing: {what} is unstated — who acted is stated by "
              "the caller, never assumed", file=sys.stderr)
        return None
    if v.lower() in HUMAN_CLASS_WORDS:
        print(f"refusing: {what} is {v!r} — a class word claiming a "
              "human without naming one; state who acted (an agent "
              "records itself as an agent)", file=sys.stderr)
        return None
    if v.lower() in MODEL_NAMES:
        print(f"refusing: {what} is {v!r} — a model may not sign an "
              "override, skip, or approval; a human states their own "
              "name (L6)", file=sys.stderr)
        return None
    return v


def gate_answer(task_dir: Path, gate_id: str) -> dict | None:
    return load_json(task_dir / "gates" / f"{gate_id}.answer.json")


def cmd_gate(task_dir: Path, gate_id: str, decision: str | None,
             approver: str | None, rationale: str, request: bool,
             summary_file: Path | None, gate_type: str,
             question: str | None, options: list[str] | None) -> int:
    if request:
        # P0-3: the merge gate must surface design state to the decision
        # face.  When a non-verified design state holds on an applicable
        # surface, the question's first line warns the human — previously
        # the warning was buried in the summary JSON and the human approved
        # without ever seeing it (the country-c-coffee merge gate).
        # v2: design_unspecified and design_nonconforming are also surfaced
        # (split from design_unverified). Design never hard-blocks merge
        # — the warning is visible, the human decides.
        _report = load_json(task_dir / "report.json", {})
        _dv = _report.get("design", {})
        _design_warn_states = ("design_unverified", "design_unspecified",
                               "design_nonconforming")
        _design_warn = (
            _dv.get("design_state") in _design_warn_states
            and bool((_dv.get("surface") or {}).get("applicable")))
        if not question:
            if _design_warn:
                _n = (_dv.get("surface") or {}).get("surface_files_total", 0)
                _rc = (_report.get("design_auto") or {}).get("rc", "?")
                _ds = _dv.get("design_state", "design_unverified")
                question = (
                    "⚠ Design %s: surface has %d web/deck files, "
                    "design not verified (rc=%s).\n"
                    "Merge this delivery into the target branch? "
                    "(rationale required)" % (_ds, _n, _rc))
            else:
                question = ("Merge this delivery into the target branch? "
                            "(rationale required)")
        if not options:
            if _design_warn:
                options = ["run_design_first", "approve", "request_changes",
                           "cancel"]
            else:
                options = ["approve", "request_changes", "cancel"]
        # M7/L5: the merge gate's summary carries the design state and
        # surface so a human can't approve without seeing it. Read from
        # the deliver report if it stands, then layer any explicit
        # --summary-file on top.
        summary = {}
        report = load_json(task_dir / "report.json", {})
        if report:
            dv = report.get("design", {})
            summary["design_state"] = dv.get("design_state")
            summary["surface"] = dv.get("surface")
            summary["outcome"] = report.get("outcome")
            summary["delivered"] = report.get("delivered")
            # N2: which ref was measured — the human sees this at the
            # merge gate and knows whether the report measured the task
            # branch (pre-merge) or HEAD (inline / post-merge).
            summary["measured_ref"] = report.get("measured_ref")
            summary["ref_kind"] = report.get("ref_kind")
            # N3: the measurement warning must be visible at the merge
            # gate — a 0-byte delivery is either a pure deletion or an
            # inconsistent measurement, and the human decides which. If
            # this is not in the summary, the warning is invisible at
            # the moment of approval (the client-x bug's exact failure mode).
            if report.get("measurement_warning"):
                summary["measurement_warning"] = report["measurement_warning"]
            if report.get("design_override"):
                summary["design_override"] = report["design_override"]
        if summary_file:
            summary.update(load_json(summary_file, {}))
        save_json(task_dir / "gates" / f"{gate_id}.request.json", {
            "gate_id": gate_id, "gate_type": gate_type,
            "question": question or "Decide:",
            "options": options or [],
            "summary": summary,
            "requested_at": now_iso()})
        state = load_json(task_dir / "state.json", {})
        state.update(human_state="Needs your decision", stage="MERGE_GATE")
        save_json(task_dir / "state.json", state)
        event(task_dir, event="NEED_HUMAN", gate_id=gate_id, type=gate_type)
        print(json.dumps({"requested": gate_id, "type": gate_type}))
        return 0
    if decision:
        approver = stated_actor(approver, "the approver")
        if approver is None:
            return 1
        if decision == "approve" and not rationale.strip():
            print("refusing: an approval without a rationale is a contract "
                  "breach", file=sys.stderr)
            return 1
        save_json(task_dir / "gates" / f"{gate_id}.answer.json", {
            "gate_id": gate_id, "decision": decision, "approver": approver,
            "rationale": rationale, "ts": now_iso()})
        event(task_dir, event="GATE_APPROVED" if decision == "approve"
              else "GATE_REJECTED", gate_id=gate_id,
              rationale_present=bool(rationale.strip()))
        print(json.dumps({"answered": gate_id, "decision": decision}))
        return 0
    ans = gate_answer(task_dir, gate_id)
    print(json.dumps(ans) if ans else json.dumps({"no_answer": gate_id}))
    return 0 if ans else 1


def human_state(stage: str, delivered: bool | None) -> str:
    """Derived, never stored ahead — the four-state surface (PRD §9)."""
    if stage in ("MERGE_GATE", "ROUTE_STOP"):
        return "Needs your decision"
    if stage in ("DONE", "FAILED", "CANCELLED"):
        if stage == "DONE" and delivered:
            return "Ready"
        return "Needs your decision"
    if stage == "VERIFY":
        return "Checking"
    return "Working"


def spec_validation(repo: Path, change_id: str | None) -> dict:
    """The spec verdict, read from the plane's signed records — never
    run here. Three states: spec_valid (a signed verdict with rc 0),
    spec_invalid (a signed verdict with rc != 0, its output verbatim),
    and spec_unverified (no verdict, or one whose signature does not
    verify). spec_unverified is never treated as spec_invalid and never
    triggers a re-run."""
    if not change_id:
        return {"spec_valid": False, "spec_state": "spec_unverified",
                "why": "no change id recorded"}
    verdicts, rejected = signed_records(str(change_id), "verdict")
    if rejected:
        return {"spec_valid": False, "spec_state": "spec_unverified",
                "why": ("verdict records failed signature verification "
                        "— tampering evidence, not a verdict"),
                "rejected_records": rejected}
    v = None
    for rec in reversed(verdicts):
        if rec.get("verb") == "validate":
            v = rec
            break
    if v is None:
        return {"spec_valid": False, "spec_state": "spec_unverified",
                "why": ("no signed validate verdict exists; the caller "
                        "does not run the validator — a validate "
                        "dispatch produces the verdict"),
                "remedy": ("plan.py validate --change <id> "
                           "--repo <repo>")}
    rc = int(v.get("rc") or 0)
    out = {"spec_valid": rc == 0,
           "spec_state": "spec_valid" if rc == 0 else "spec_invalid",
           "validator_rc": rc,
           "verdict_ts": v.get("ts"), "session": v.get("session")}
    if rc != 0:
        out["why"] = "the signed verdict carries a non-zero rc"
        out["validator_output"] = str(v.get("stdout") or "").strip()
    return out


# ── the design surface: applicability by measurement (ui-designer) ──
#
# Whether the design role applies is measured from the change's product
# files by extension — never asked of a model, never inferred from the
# prompt's adjectives. The classes are the delivery surface's own:
# product_excludes filters the file list before it reaches here.

DESIGN_WEB_EXTS = (".html", ".htm", ".css", ".scss", ".less", ".styl",
                   ".sass", ".jsx", ".tsx", ".vue", ".svelte", ".astro")
DESIGN_DECK_DIRS = ("slides", "deck")
_DECK_FRONTMATTER = re.compile(r"^deck:|^\s*od\.mode:\s*deck", re.M)


def design_file_classes(path: str, repo: Path) -> list[str]:
    """The design classes one standing product file belongs to."""
    p = PurePosixPath(path)
    ext = p.suffix.lower()
    classes = []
    if ext in DESIGN_WEB_EXTS:
        classes.append("web")
    deck = ext == ".pptx"
    if ext == ".html" and any(part in DESIGN_DECK_DIRS
                              for part in p.parts[:-1]):
        deck = True
    if ext == ".md":
        try:
            head = (repo / path).read_text(encoding="utf-8",
                                           errors="replace")[:512]
            if _DECK_FRONTMATTER.search(head):
                deck = True
        except OSError:
            pass
    if deck:
        classes.append("deck")
    return classes


def _file_exists_in_worktrees(repo: Path, rel: str) -> bool:
    """Check if a file exists in the main repo or any linked worktree."""
    if (repo / rel).exists():
        return True
    wt = subprocess.run(["git", "-C", str(repo), "worktree", "list",
                         "--porcelain"], capture_output=True, text=True)
    if wt.returncode != 0:
        return False
    for line in (wt.stdout or "").splitlines():
        if line.startswith("worktree "):
            wt_path = line[len("worktree "):]
            if wt_path != str(repo) and (Path(wt_path) / rel).exists():
                return True
    return False


def design_surface(files: list, repo: Path,
                   head: str | None = None) -> dict:
    """The measured design surface of a file list: which classes stand,
    which files carry them. Applicability is `web + deck >= 1` on the
    standing files — a deleted path measures nothing.

    N1 (deliver-measures-work): when head is a task-branch SHA, the
    working tree may be on a different branch and the files may not
    exist on disk. In that case, check existence via git cat-file
    against the measured ref's tree instead of the working tree.

    W8 (worktree-uncommitted): uncommitted files in a linked worktree are
    not in any git tree yet, so the cat-file check fails.  Fall back to a
    filesystem check across the main repo and linked worktrees so these
    files are measured before the first commit."""
    hits: dict = {}
    for f in files:
        if head is not None:
            # check existence against the measured ref's tree
            r = subprocess.run(["git", "-C", str(repo), "cat-file", "-e",
                                f"{head}:{f}"], capture_output=True,
                               text=True, cwd=str(repo))
            if r.returncode != 0:
                # W8: file may be uncommitted in a worktree — check the
                # filesystem before discarding it
                if not _file_exists_in_worktrees(repo, f):
                    continue
        elif not _file_exists_in_worktrees(repo, f):
            continue
        cs = design_file_classes(f, repo)
        if cs:
            hits[f] = cs
    classes = sorted({c for cs in hits.values() for c in cs})
    return {"applicable": bool(hits), "classes": classes,
            "surface_files": sorted(hits)[:50],
            "surface_files_total": len(hits),
            "measured_files": len(files)}


def codegraph_surface(files: list, repo: Path,
                      base_sha: str | None) -> dict:
    """The codegraph surface of a file list: which of the changed files
    ALREADY EXISTED at base_sha. A file that is net-new in this change
    (did not exist at base_sha) does not count — there is nothing
    pre-existing to query a graph about. Applicability is
    `pre_existing >= 1`.

    This mirrors design_surface's shape (capped list + *_total count +
    measured_files) but with different applicability semantics:
    design_surface measures extension classes (web/deck) on standing
    files; codegraph_surface measures prior existence at base_sha. When
    base_sha is None there is no base to check against, so nothing can
    be pre-existing and applicability is false."""
    hits: dict = {}
    if base_sha:
        for f in files:
            r = subprocess.run(["git", "-C", str(repo), "cat-file", "-e",
                                f"{base_sha}:{f}"], capture_output=True,
                               text=True, cwd=str(repo))
            if r.returncode == 0:
                hits[f] = True
    return {"applicable": bool(hits),
            "pre_existing_files": sorted(hits)[:50],
            "pre_existing_files_total": len(hits),
            "measured_files": len(files)}


# ── v2 design architecture: product-side spec artifacts + D3 checks ──
#
# D1 SPECIFY produces design/tokens.css + tokens.json + components.md +
# pages.md + assets.md — concrete artifacts on disk, not a frame-side
# ceremony. D3 VERIFY runs six mechanical checks against the filesystem
# (tokens_used, skill_sha_match, components_conform, no_placeholder,
# design_artifacts_exist, tokens_json_valid). report.py reads the
# results; it does not re-run the checks (plan.py cmd_design_verify
# does, and writes them to state.json.design_verification).

DESIGN_SPEC_FILES = ("tokens.css", "tokens.json", "components.md",
                     "pages.md", "assets.md")


def design_spec_artifacts(repo: Path) -> dict:
    """The design spec artifacts on disk (D1 SPECIFY output). Returns
    which of the five expected files exist, their sizes, and whether
    any spec exists at all — the product-side evidence that replaces
    frame-side 'did the agent call the tool' checks (B2 deleted)."""
    design_dir = repo / "design"
    files = {}
    any_exist = False
    for name in DESIGN_SPEC_FILES:
        p = design_dir / name
        if p.is_file():
            sz = p.stat().st_size
            files[name] = {"exists": True, "bytes": sz}
            if sz > 0:
                any_exist = True
        else:
            files[name] = {"exists": False, "bytes": 0}
    return {"any_exist": any_exist, "files": files,
            "design_dir": str(design_dir)}


def design_d3_checks(task_dir: Path, repo: Path) -> dict:
    """The D3 VERIFY check results, read from state.json.design_verification
    (written by plan.py cmd_design_verify). Six mechanical checks against
    the filesystem — report.py reads, never re-runs. Returns the check
    pass/fail map and an overall pass flag."""
    state = load_json(task_dir / "state.json", {})
    dv = state.get("design_verification")
    if not isinstance(dv, dict):
        return {"available": False, "checks": {}, "all_pass": False}
    checks = dv.get("checks", {})
    # checks is a flat {name: bool} map from cmd_design_verify
    all_pass = all(v for v in checks.values()) if checks else False
    return {"available": True, "checks": checks,
            "all_pass": all_pass,
            "ts": dv.get("ts")}


def design_validation(task_dir: Path, repo: Path, state: dict,
                      landed: list, head: str | None = None) -> dict:
    """The design conclusion, read the way the spec verdict is: from the
    product-side spec artifacts (v2) and the plane's signed records (v1
    fallback), never from a model's claim.

    v2 states (product-side, D1+D3):
      design_unspecified    — no design spec artifacts exist (no
                              design/tokens.css etc.)
      design_nonconforming  — spec exists but D3 verify checks fail
      design_verified       — spec exists and all D3 checks pass
      design_declined       — a person recorded skipping it (unchanged)
      design_not_applicable — the measured surface carries no web/deck
                              file (unchanged)
      design_unmeasured     — nothing was measured (unchanged)

    v1 legacy fallback (backward compat):
      design_applied        — a signed design record stands (v1 path)
      design_unverified     — applicable with no verifying record and no
                              product-side artifacts (legacy fallback)"""
    surface = design_surface(landed, repo, head=head)
    if not surface["applicable"] and not surface.get("measured_files"):
        return {"design_state": "design_unmeasured",
                "why": ("the measured surface is empty - nothing was measured, "
                        "so nothing can be said about whether design applies; "
                        "this is not the same as a change that asks nothing "
                        "of design"),
                "remedy": ("check the work ref: report.py deliver reports "
                           "work_ref, and a mismatch there means the branch "
                           "carrying the work is not the branch being measured"),
                "surface": surface}
    if not surface["applicable"]:
        return {"design_state": "design_not_applicable",
                "surface": surface}
    decision = load_json(task_dir / "planning.json", {}) \
        .get("design_decision")
    if isinstance(decision, dict) and decision.get("skip"):
        return {"design_state": "design_declined",
                "why": decision.get("why"),
                "declined_by": decision.get("decided_by"),
                "declined_at": decision.get("ts"),
                "surface": surface}
    # v2: check product-side spec artifacts first (D1 SPECIFY output).
    # This is the structural fix for S1 — design/ files are product files
    # that count toward landed_files/landed_bytes, so the merge gate
    # sees them.
    artifacts = design_spec_artifacts(repo)
    if artifacts["any_exist"]:
        d3 = design_d3_checks(task_dir, repo)
        if d3["available"] and d3["all_pass"]:
            return {"design_state": "design_verified",
                    "artifacts": artifacts, "d3_checks": d3,
                    "surface": surface}
        if d3["available"] and not d3["all_pass"]:
            return {"design_state": "design_nonconforming",
                    "artifacts": artifacts, "d3_checks": d3,
                    "why": ("design spec artifacts exist but one or more "
                            "D3 verify checks failed — the pages do not "
                            "conform to the spec"),
                    "surface": surface}
        # artifacts exist but D3 verify hasn't run yet — nonconforming
        # until verified (the spec stands but conformance is unproven)
        return {"design_state": "design_nonconforming",
                "artifacts": artifacts,
                "d3_checks": d3,
                "why": ("design spec artifacts exist but D3 verify has "
                        "not run — run plan.py design-verify to check "
                        "conformance"),
                "remedy": "plan.py design-verify --change <id> --repo <repo>",
                "surface": surface}
    # v1 legacy fallback: check for signed design records (backward compat
    # for tasks that ran the v1 design dispatch without producing v2
    # product-side artifacts).
    record_key = state.get("change_id") or state.get("task_id")
    if not record_key:
        return {"design_state": "design_unspecified",
                "why": ("no design spec artifacts exist and no change id "
                        "or task id recorded — D1 SPECIFY was never run"),
                "artifacts": artifacts, "surface": surface}
    records, rejected = signed_records(str(record_key), "design")
    if rejected:
        return {"design_state": "design_unverified",
                "why": ("design records failed signature verification "
                        "— tampering evidence, not a conclusion"),
                "rejected_records": rejected, "surface": surface}
    rec = None
    for r in reversed(records):
        if r.get("verb") == "design":
            rec = r
            break
    if rec is not None:
        return {"design_state": "design_applied",
                "record": {k: rec.get(k) for k in
                           ("ts", "session", "surface", "template",
                            "design_system", "files", "assets", "render",
                            "placeholders")},
                "artifacts": artifacts, "surface": surface}
    # no product-side artifacts, no signed record — unspecified
    return {"design_state": "design_unspecified",
            "why": ("no design spec artifacts exist (design/tokens.css etc.) "
                    "and no signed design record stands — D1 SPECIFY was "
                    "never run or produced no artifacts"),
            "remedy": "plan.py design-pick --change <id> --repo <repo>",
            "artifacts": artifacts, "surface": surface}


# ── the auto-dispatch: scheduling, not gating (design-autodispatch) ──
#
# deliver already computes design_validation() — applicable, a record,
# a skip. The gap v0.18.0 left was the fourth question: "did we try?"
# When the answer is no and the surface is applicable, we dispatch
# plan.py design once via subprocess (E4: report does not import plan),
# record the attempt BEFORE the session opens (J2: a crash leaves the
# fact), and re-read design_validation() afterwards. The dispatch's
#成败 never changes `delivered` (J3) — this is scheduling, not a gate.

PLAN_PY = Path(__file__).resolve().parent / "plan.py"


def design_auto_due(task_dir: Path, repo: Path, state: dict,
                    landed: list, no_design: bool,
                    head: str | None = None) -> tuple[bool, str]:
    """Whether the design role is due for one automatic dispatch, and
    the human-readable reason it is not when it isn't. due is the
    conjunction of: the surface is applicable, no signed design record
    stands, no person recorded a skip, no prior auto attempt is
    recorded, and --no-design was not passed.

    N4 (deliver-measures-work): a half-finished attempt (rc is None) is
    not a completed attempt — a crash or timeout that left the pre-write
    record standing must not permanently lock the retry path. The
    attempts counter tracks completed dispatches; incomplete ones don't
    count. The limit is 2 completed attempts (Q4), not infinity."""
    if no_design:
        return False, "disabled"
    surface = design_surface(landed, repo, head=head)
    if not surface["applicable"]:
        if not surface.get("measured_files"):
            return False, "surface_unmeasured"
        return False, "not_applicable"
    # A2: if design-pick ran (state.json.design_selection exists) and the
    # surface files already stand with non-trivial content, the design
    # was carried in-work (A1.2) — the main session read the SKILL.md
    # and wrote the pages as part of its WORK.  The independent dispatch
    # is for retrofit only (A2); it must not fire on the main path.
    # design_validation still runs and reports the four-state conclusion
    # — the human at the gate sees design_unverified if no signed record
    # stands, and decides.
    selection = state.get("design_selection")
    if isinstance(selection, dict) and selection.get("skill"):
        _sf = surface.get("surface_files", [])
        _all_have_content = bool(_sf) and all(
            (repo / f).stat().st_size > 200 for f in _sf
            if (repo / f).exists())
        if _all_have_content:
            return False, "designed_in_work"
    planning = load_json(task_dir / "planning.json", {})
    decision = planning.get("design_decision")
    if isinstance(decision, dict) and decision.get("skip"):
        return False, "declined"
    # N4: a prior design_auto record that completed (rc is not None)
    # counts as an attempt; an incomplete one (rc is None) does not.
    # The limit is 2 completed attempts — a half-finished crash doesn't
    # burn one.
    da = planning.get("design_auto")
    if isinstance(da, dict):
        completed = da.get("rc") is not None
        attempts = da.get("attempts", 1 if completed else 0)
        if attempts >= 2:
            return False, "already_attempted"
        if completed and attempts >= 1:
            return False, "already_attempted"
    # M4: record key is change_id or task_id — no_change_id is gone.
    record_key = state.get("change_id") or state.get("task_id")
    if not record_key:
        return False, "no_record_key"
    records, _ = signed_records(str(record_key), "design")
    for r in reversed(records):
        if r.get("verb") == "design":
            return False, "record_exists"
    return True, "due"


def backfill_design_auto(task_dir: Path, state: dict) -> dict | None:
    """N2: if design_auto.rc is null (the process was killed before the
    final write) but a signed design record exists (the session completed
    and wrote the record, just didn't update planning.json), backfill
    the design_auto entry from the record. Marks recovered_from_frames.
    Returns the backfilled record, or None if no backfill was needed."""
    planning = load_json(task_dir / "planning.json", {})
    da = planning.get("design_auto")
    if not isinstance(da, dict) or da.get("rc") is not None:
        return None  # rc is not null — no backfill needed
    change = str(state.get("change_id") or state.get("task_id") or "")
    if not change:
        return None
    # check if a signed design record was actually written
    verdicts, _ = signed_records(change, "design")
    if not verdicts:
        return None
    # the session completed and wrote a record — backfill
    rec = {**da,
           "rc": 0,
           "outcome": "design_applied",
           "state": "complete",
           "recovered_from_frames": True,
           "recovered_at": now_iso()}
    planning["design_auto"] = rec
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="DESIGN_AUTO_BACKFILLED", change=change,
          recovered_from="frames")
    return rec


def design_auto_dispatch(task_dir: Path, repo: Path, state: dict,
                         landed: list,
                         head: str | None = None) -> dict:
    """One automatic design dispatch via subprocess (E4). The attempt is
    recorded in planning.json.design_auto BEFORE the session opens — a
    killed process still leaves the fact (J2/A10). The dispatch's rc
    and outcome never change deliver's exit code or `delivered` (J3)."""
    # M4: use change_id or task_id as the dispatch and record key.
    change = str(state.get("change_id") or state.get("task_id"))
    started = time.monotonic()
    attempted_at = now_iso()
    # N4: carry the attempts counter forward — a prior incomplete record
    # (rc is None) doesn't count as a completed attempt.
    planning = load_json(task_dir / "planning.json", {})
    prior_da = planning.get("design_auto")
    prior_attempts = 0
    if isinstance(prior_da, dict):
        prior_attempts = prior_da.get("attempts", 0)
        if prior_da.get("rc") is not None:
            prior_attempts = max(prior_attempts, 1)
    # J2: write the attempt first — the key's presence is the fence,
    # regardless of rc. A crash between this write and the session's
    # end still counts as "tried".
    pre = {"attempted_at": attempted_at, "change": change,
           "trigger": "deliver", "rc": None, "outcome": None,
           "session": None, "elapsed_seconds": None,
           "attempts": prior_attempts, "state": "incomplete"}
    planning["design_auto"] = pre
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="DESIGN_AUTO_DISPATCHED", change=change,
          trigger="deliver", attempted_at=attempted_at)
    cmd = [sys.executable, str(PLAN_PY), "design",
           "--change", change, "--repo", str(repo),
           "--task-dir", str(task_dir.resolve())]
    # A4: retrofit sharding — one file per session, all concurrent.
    # The auto-dispatch is the retrofit path (A2); the correct
    # granularity is one file per session, not one serial session
    # over all files.  5 files → 5 ~300s sessions, not 1 × 1800s.
    _surface = design_surface(landed, repo, head=head)
    _n_files = _surface.get("surface_files_total", 0)
    if _n_files > 1:
        cmd += ["--shard", str(_n_files)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(repo))
        rc = proc.returncode
    except Exception:
        rc = -1
    elapsed = round(time.monotonic() - started, 3)
    # re-read the design validation to see what the dispatch produced:
    # design_applied/design_verified if a record or artifacts now stand,
    # design_unverified otherwise (the five facts did not all hold, or
    # the session crashed). Either way, deliver's `delivered` is
    # untouched (J3) — design never hard-blocks merge (v2).
    dv = design_validation(task_dir, repo, state, landed, head=head)
    outcome = dv["design_state"] if dv["design_state"] in \
        ("design_applied", "design_verified", "design_nonconforming",
         "design_unspecified", "design_unverified") \
        else "design_unverified"
    session = None
    if rc == 0:
        try:
            out = json.loads(proc.stdout)
            session = out.get("session_name")
        except (json.JSONDecodeError, ValueError):
            pass
    rec = {"attempted_at": attempted_at, "change": change,
           "trigger": "deliver", "rc": rc, "outcome": outcome,
           "session": session, "elapsed_seconds": elapsed,
           "attempts": prior_attempts + 1, "state": "complete"}
    planning = load_json(task_dir / "planning.json", {})
    planning["design_auto"] = rec
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="DESIGN_AUTO_DISPATCHED", change=change,
          rc=rc, outcome=outcome, elapsed_seconds=elapsed,
          session=session)
    return rec


# ── codegraph auto-dispatch: scheduling, not gating (codegraph-author-
#    autodispatch) ──
#
# Same discipline as design_auto_due/design_auto_dispatch above, but
# triggered at the START of author dispatch (WORK phase), not at deliver
# — the brief is an input for the author, so it must exist before the
# author starts writing, not after.  The dispatch's outcome never changes
# cmd_phase/cmd_dispatch's exit code or stops role dispatch (INV-14).

def _change_files_for_codegraph(repo: Path,
                                task_dir: Path) -> tuple[list, str | None]:
    """The changed-file list for codegraph_auto_due's applicability check.
    This is the report.py-side equivalent of plan.py's change_surface —
    structurally aligned with its W8 worktree-visibility block so the two
    see the same files under ai-dlc's standard worktree-first flow.  The
    full resolve_work_ref logic has a text-identical copy in report.py
    (Z5), so this stays self-contained (E4: report does not import plan).
    Reads base_sha from state.json, diffs base..<resolved work sha>, and
    adds uncommitted paths from repo itself plus any linked worktree bound
    to the resolved branch, applying excluded()."""
    state = load_json(task_dir / "state.json", {})
    base = state.get("base_sha")
    files: list = []

    # N1: measure the work's ref via resolve_work_ref (recorded branch >
    # task/{change} convention > HEAD).  On the planned route the work
    # lives on the task branch before the merge, so diffing repo's own
    # HEAD would see an empty tree — and commits already landed on the
    # task branch (not yet merged) would be invisible to a bare
    # rev-parse HEAD on the main checkout.
    work = resolve_work_ref(repo, state)
    head_sha = work["sha"]
    measured_ref = work["ref"]
    if head_sha is None:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(repo))
        head_sha = head.stdout.strip() if head.returncode == 0 else None
    if base and head_sha and base != head_sha:
        diff = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only",
             base, head_sha],
            capture_output=True, text=True, cwd=str(repo))
        files += [f for f in diff.stdout.splitlines()
                  if f and not excluded(f)]

    # Fold uncommitted paths from a `git status --porcelain -uall` proc
    # into files (rename-arrow handling, excluded() filter, dedupe) —
    # the same parse the original inline loop did, factored so the W8
    # worktree pass below reuses it verbatim.
    def _fold_status(proc):
        if proc.returncode != 0:
            return
        for line in proc.stdout.splitlines():
            path = line[3:].strip().strip('"')
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            path = path.rstrip("/\\")
            if path and not excluded(path) and path not in files:
                files.append(path)

    # status on repo itself — covers the case where --repo points directly
    # at a working tree (the main checkout or a worktree passed as --repo).
    _fold_status(subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uall"],
        capture_output=True, text=True, cwd=str(repo)))

    # W8: worktree visibility — uncommitted files in a linked worktree are
    # invisible to the status call above (which only sees repo's own tree).
    # Parse `git worktree list --porcelain`, find the linked worktree (not
    # repo itself) whose branch matches the branch resolved by
    # resolve_work_ref, and fold its uncommitted paths in.  Mirrors
    # plan.py change_surface's W8 block, via subprocess (this function's
    # existing style) rather than a shared helper (E4).
    measured_branch = None
    if measured_ref.startswith("refs/heads/"):
        measured_branch = measured_ref[len("refs/heads/"):]
    if measured_branch:
        wt = subprocess.run(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, cwd=str(repo))
        if wt.returncode == 0 and wt.stdout.strip():
            cur_wt_path = None
            cur_wt_branch = None
            for line in wt.stdout.splitlines():
                if line.startswith("worktree "):
                    cur_wt_path = line[len("worktree "):]
                elif line.startswith("branch "):
                    cur_wt_branch = line[len("branch "):]
                    if cur_wt_branch.startswith("refs/heads/"):
                        cur_wt_branch = cur_wt_branch[len("refs/heads/"):]
                elif line == "" and cur_wt_path and cur_wt_branch:
                    if cur_wt_path != str(repo) \
                            and cur_wt_branch == measured_branch:
                        _fold_status(subprocess.run(
                            ["git", "-C", cur_wt_path, "status",
                             "--porcelain", "-uall"],
                            capture_output=True, text=True,
                            cwd=cur_wt_path))
                    cur_wt_path = None
                    cur_wt_branch = None
    return files, base


def codegraph_auto_due(task_dir: Path, repo: Path,
                       state: dict) -> tuple[bool, str]:
    """Whether a codegraph brief is due for one automatic dispatch, and
    the human-readable reason it is not when it isn't.  Implements PRD
    §02 decision table:

      route != "planned"            → (False, "inline")
      codegraph-scope not applicable → (False, "not_applicable" /
                                             "surface_unmeasured")
      already attempted              → (False, "already_attempted")
      otherwise                      → (True, "due")

    Record-keeping choice (mirroring design_auto's own comments): the
    "already attempted" check reads TWO locations — state.json's
    codegraph_brief key (written by cmd_codegraph_brief, catches manual
    `plan.py codegraph brief` runs regardless of outcome) and
    planning.json's codegraph_auto key (written by
    codegraph_auto_dispatch's pre-record, catches auto-dispatch attempts
    that may not have completed).  Either key's presence means "tried" —
    idempotent, no retry counter (INV-16, unlike design's 2-attempt
    limit, because a failed brief just means the author reads code
    directly)."""
    if state.get("route") != "planned":
        return False, "inline"
    files, base_sha = _change_files_for_codegraph(repo, task_dir)
    surface = codegraph_surface(files, repo, base_sha)
    if not surface["applicable"]:
        if not surface.get("measured_files"):
            return False, "surface_unmeasured"
        return False, "not_applicable"
    # already attempted?  Check both state.json (manual cmd_codegraph_brief
    # runs) and planning.json (auto-dispatch pre-records).  Any of the four
    # codegraph_state outcomes from cmd_codegraph_brief counts — the key's
    # presence is the fence, not its success.
    st = load_json(task_dir / "state.json", {})
    if isinstance(st.get("codegraph_brief"), dict):
        return False, "already_attempted"
    planning = load_json(task_dir / "planning.json", {})
    if isinstance(planning.get("codegraph_auto"), dict):
        return False, "already_attempted"
    return True, "due"


def codegraph_auto_dispatch(task_dir: Path, repo: Path, state: dict,
                            change: str) -> dict:
    """One automatic codegraph-brief dispatch via subprocess (E4).  The
    attempt is recorded in planning.json.codegraph_auto BEFORE the
    subprocess opens — a killed process still leaves the fact (J2/INV-15).
    The dispatch's rc and outcome never change cmd_phase/cmd_dispatch's
    exit code or stop role dispatch (J3/INV-14) — this is scheduling,
    not a gate.

    Record-keeping choice: the pre-record goes to planning.json.codegraph_auto
    (not state.json) to mirror design_auto_dispatch's J2 discipline exactly
    — planning.json is the attempt ledger, state.json is the outcome
    ledger.  The subprocess calls `plan.py codegraph brief` which writes
    its own outcome to state.json.codegraph_brief; codegraph_auto_due
    checks both locations (see its docstring)."""
    started = time.monotonic()
    attempted_at = now_iso()
    # J2: write the attempt first — the key's presence is the fence,
    # regardless of rc.  A crash between this write and the subprocess's
    # end still counts as "tried" (INV-15).
    planning = load_json(task_dir / "planning.json", {})
    pre = {"attempted_at": attempted_at, "change": change,
           "trigger": "phase", "rc": None, "outcome": None,
           "session": None, "elapsed_seconds": None,
           "state": "incomplete"}
    planning["codegraph_auto"] = pre
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="CODEGRAPH_AUTO_DISPATCHED", change=change,
          trigger="phase", attempted_at=attempted_at)
    cmd = [sys.executable, str(PLAN_PY), "codegraph", "brief",
           "--change", change, "--repo", str(repo),
           "--task-dir", str(task_dir.resolve())]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(repo))
        rc = proc.returncode
    except Exception:
        rc = -1
    elapsed = round(time.monotonic() - started, 3)
    session = None
    outcome = "brief_incomplete"
    if rc == 0:
        try:
            out = json.loads(proc.stdout)
            session = out.get("session_name")
            outcome = out.get("codegraph_state", "brief_written")
        except (json.JSONDecodeError, ValueError):
            pass
    rec = {"attempted_at": attempted_at, "change": change,
           "trigger": "phase", "rc": rc, "outcome": outcome,
           "session": session, "elapsed_seconds": elapsed,
           "state": "complete"}
    planning = load_json(task_dir / "planning.json", {})
    planning["codegraph_auto"] = rec
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="CODEGRAPH_AUTO_DISPATCHED", change=change,
          rc=rc, outcome=outcome, elapsed_seconds=elapsed,
          session=session)
    return rec


def cmd_deliver(task_dir: Path, repo: Path, outcome: str,
                no_design: bool = False,
                no_design_by: str | None = None,
                no_design_why: str | None = None) -> int:
    # N6②: --repo must be an existing git repository (W8 — country-d
    # path-typo: wrote <workspace-root>/... when the repo was in /tmp/).
    if not is_git_repo(repo):
        print(json.dumps({"refused": True, "why": (
            "--repo %s is not a git repository — the path must name an "
            "existing git working tree" % repo), "remedy": (
            "correct --repo to the actual repository path, or: git init %s"
            % repo)}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    # M5/C9: --no-design requires a named human and a reason — a model
    # may not self-sign a skip (L6, country-d's route-exception lesson).
    if no_design:
        who = stated_actor(no_design_by, "the design skip's author")
        if who is None:
            return 1
        if not (no_design_why or "").strip():
            print("refusing: --no-design requires --no-design-why — "
                  "a skip without a reason is the silence this check "
                  "exists to end", file=sys.stderr)
            return 1
        _pl = load_json(task_dir / "planning.json", {})
        _pl["design_decision"] = {"skip": True, "decided_by": who,
                                  "why": no_design_why.strip(),
                                  "source": "deliver --no-design",
                                  "ts": now_iso()}
        save_json(task_dir / "planning.json", _pl)
    blocked = stale_route_guard(task_dir)
    if blocked:
        save_json(task_dir / "gates" / "gate-route.request.json", {
            **blocked, "gate_id": "gate-route",
            "options": ["set_route_planned", "set_route_inline", "cancel"],
            "requested_at": now_iso()})
        st = load_json(task_dir / "state.json", {})
        st.update(stage="ROUTE_STOP", human_state="Needs your decision")
        save_json(task_dir / "state.json", st)
        event(task_dir, event="STALE_ROUTE_STOP", route=blocked["route"])
        print(json.dumps(blocked, indent=2, ensure_ascii=False))
        return GATE_BLOCKED_EXIT
    state = load_json(task_dir / "state.json", {})
    # W7: validate --repo against the recorded value (Z1). A mismatch
    # means the caller is delivering into a different repo than the one
    # init stamped — the country-b task-dir/repo confusion.
    recorded_repo = state.get("repo")
    if recorded_repo:
        actual_repo = str(Path(repo).resolve())
        if actual_repo != recorded_repo:
            print(json.dumps({"refused": True, "why": (
                "--repo %s does not match the repository recorded at init: "
                "%s — the task workspace was created for a different repo"
                % (actual_repo, recorded_repo)),
                "recorded_repo": recorded_repo,
                "actual_repo": actual_repo,
                "remedy": ("use --repo %s, or re-init the task workspace "
                           "for this repo" % recorded_repo)},
                indent=2, ensure_ascii=False), file=sys.stderr)
            return 1
    base = state.get("base_sha")
    rep: dict = {"outcome": outcome, "task_id": state.get("task_id"),
                 "route": state.get("route"), "base_sha": base,
                 "gates": list(GATES)}
    repo_head = git(repo, "rev-parse", "HEAD").strip()
    # N1 (deliver-measures-work): measure the work's ref — resolved by
    # resolve_work_ref (recorded branch > task/{change} convention > HEAD).
    # repo_head stays as the actual HEAD for the head_advanced check.
    work = resolve_work_ref(repo, state)
    head = work["sha"] or repo_head
    ref_kind = work["kind"]
    measured_ref = work["ref"]
    files = []
    if base and head != base:
        changed = git(repo, "diff", "--name-only", base, head).splitlines()
        files = [f for f in changed if not excluded(f)]
    # N1: when measuring a task branch, the working tree may be on a
    # different branch — read file sizes from the measured ref's tree,
    # not the working tree. For HEAD (inline / post-merge) the working
    # tree matches, so the fallback is the same.
    def _file_bytes(f: str) -> int:
        if ref_kind == "task_branch":
            try:
                return int(git(repo, "cat-file", "-s", f"{head}:{f}"))
            except Exception:
                return 0
        p = repo / f
        return p.stat().st_size if p.exists() else 0
    rep.update(repo_head=repo_head, head_advanced=repo_head != base,
               landed_files=len(files),
               landed_bytes=sum(_file_bytes(f) for f in files),
               work_ref=work,
               measured_ref=measured_ref, ref_kind=ref_kind)
    rep["files"] = files[:10]
    # the route check: the recorded route against the measured change —
    # a contradiction stops the task here, before anything downstream
    # (spec validation, merge gate) runs, because the route question
    # comes first: nothing about this delivery is judged until the task
    # is even on the right plane
    rcheck, rblock = route_check(task_dir, repo, state)
    if rblock:
        save_json(task_dir / "gates" / "gate-route.request.json", {
            "gate_id": "gate-route", **rblock,
            "options": ["rerun_through_plane", "record_exception", "cancel"],
            "requested_at": now_iso()})
        st = load_json(task_dir / "state.json", {})
        st.update(stage="ROUTE_STOP", human_state="Needs your decision")
        save_json(task_dir / "state.json", st)
        event(task_dir, event="ROUTE_STOP", route=rcheck.get("route"),
              measured_files=rcheck.get("measured_files"),
              threshold=rcheck.get("threshold"))
        print(json.dumps({"route_check": rcheck, "why": rblock["why"],
                          "options": ["rerun_through_plane",
                                      "record_exception", "cancel"],
                          "remedy": ("re-init with --route planned, or record "
                                     "an exception: report.py exception "
                                     "--task-dir <dir> --reason <why> "
                                     "--author <who>")},
                         indent=2, ensure_ascii=False))
        return GATE_BLOCKED_EXIT
    rep["route_check"] = rcheck
    if "exception" in rcheck:
        # the recorded exception travels: its reason, who recorded it, when
        rep["route_exception"] = rcheck["exception"]
    rep["spec"] = spec_validation(repo, state.get("change_id"))
    # the design auto-dispatch (N1): scheduling, not gating. If the
    # surface is applicable, no record stands, no skip is recorded, no
    # prior attempt is on file, and --no-design was not passed, dispatch
    # plan.py design once via subprocess (E4). The attempt is recorded
    # before the session opens (J2); its成败 never changes `delivered`
    # (J3). This runs after the product files have landed (J5) and
    # before the report is finalised.
    due, why_not = design_auto_due(task_dir, repo, state, files,
                                   no_design, head=head)
    # N2: before dispatching, try to backfill a prior incomplete design_auto
    # (rc=null) from a signed record the session may have written before
    # the process was killed. If backfill succeeds, the dispatch is skipped.
    if not due:
        backfilled = backfill_design_auto(task_dir, state)
        if backfilled:
            rep["design_auto_backfilled"] = backfilled
            due = False  # already recovered — don't re-dispatch
    if due:
        rep["design_auto"] = design_auto_dispatch(task_dir, repo, state,
                                                   files, head=head)
    else:
        rep["design_auto_skipped"] = why_not
        skip_evt = {"change": state.get("change_id"), "why": why_not,
                    "surface": design_surface(files, repo, head=head)}
        if no_design and why_not == "disabled":
            skip_evt["skipped_by"] = no_design_by
            skip_evt["skip_reason"] = no_design_why
        event(task_dir, event="DESIGN_AUTO_SKIPPED", **skip_evt)
    # the design conclusion, the same way: measured applicability, the
    # recorded decision, and the product-side spec artifacts (v2) or
    # signed record (v1 fallback). Design state is visible information,
    # never a gate — the human at the merge gate reads it and decides.
    # If the auto-dispatch just ran, this re-reads the now-possibly-
    # signed record; otherwise it reads whatever stood before.
    rep["design"] = design_validation(task_dir, repo, state, files,
                                      head=head)
    dv = rep["design"]
    design_applicable = bool(dv["surface"]["applicable"])
    design_state = dv["design_state"]
    planning = load_json(task_dir / "planning.json", {})
    design_override = planning.get("design_override")
    if design_override and design_applicable:
        rep["design_override"] = design_override
    # v2: surface design spec artifacts and D3 verify check results in
    # the report. When design/ files exist, list them with their verify
    # check results (tokens_used, skill_sha_match, components_conform,
    # no_placeholder, design_artifacts_exist, tokens_json_valid).
    _artifacts = dv.get("artifacts")
    if _artifacts and _artifacts.get("any_exist"):
        rep["design_artifacts"] = _artifacts
        _d3 = dv.get("d3_checks")
        if _d3:
            rep["design_d3_checks"] = _d3
    ans = gate_answer(task_dir, "gate-merge")
    merge_approved = bool(ans and ans.get("decision") == "approve"
                          and str(ans.get("rationale", "")).strip())
    # v2 design architecture: design state NEVER hard-blocks merge.
    # delivered is a conjunction of: work landed AND the change validates
    # strictly AND a human approved the merge. Design state is visible
    # information in the report — the human at the gate reads it and
    # judges beauty themselves. A design_override is still surfaced for
    # visibility but does not gate. (S1: design/ files count toward
    # landed_files/landed_bytes, so the merge gate sees them structurally.)
    delivered = bool(rep["head_advanced"] and rep["landed_files"]
                     and rep["spec"]["spec_valid"]
                     and merge_approved)
    # honest derivation, in precedence: a broken spec is named before an
    # unanswered merge gate, which is named before unlanded work, which
    # is named before a missing design record. An unverified spec is
    # never folded into spec_invalid — the states stay distinct.
    # N3 (deliver-measures-work): head_advanced ∧ files>0 ∧ bytes==0 is
    # self-contradictory — a head that advanced with files but zero bytes
    # means the measurement is inconsistent (the ref was wrong, or the
    # files are phantoms). This is the cheapest gate and would have caught
    # the client-x bug on the day it shipped.
    # R4 validation: a pure-deletion change (file existed at base, deleted
    # at head) is a legitimate 0-byte delivery. So N3 is a WARNING, not a
    # hard failure — the inconsistency is carried in the report for the
    # human to read, but does not override the outcome or set delivered
    # to false. The client-x case (2 openspec files, 0 bytes, on a wrong ref)
    # is distinguished from a real deletion by the human reading the
    # report; the warning ensures they see it.
    if (rep["head_advanced"] and rep["landed_files"] > 0
            and rep["landed_bytes"] == 0):
        rep["measurement_warning"] = {
            "head_advanced": True,
            "landed_files": rep["landed_files"],
            "landed_bytes": 0,
            "why": ("the head advanced and files are reported, but every "
                    "file measures zero bytes — this is either a "
                    "pure-deletion delivery (legitimate) or an "
                    "inconsistent measurement (wrong ref diffed); the "
                    "human reads the file list to tell them apart")}
    if not rep["spec"]["spec_valid"]:
        outcome = rep["spec"].get("spec_state") or "spec_invalid"
        delivered = False
    elif not merge_approved:
        outcome = "merge_pending"
        delivered = False
    elif not (rep["head_advanced"] and rep["landed_files"]):
        delivered = False
    elif outcome == "working":
        outcome = "completed"
    rep["outcome"] = outcome
    if rep["outcome"] != "completed":
        delivered = False
    rep["delivered"] = delivered
    # 1.5 (delivery-criteria): every report states what was NOT checked
    rep["correctness"] = {
        "machine_checked": False,
        "criteria_applied": ["spec validity (openspec validate --strict)",
                             "human merge approval",
                             "design state (visible information — v2 "
                             "product-side artifacts and D3 verify checks, "
                             "never a merge gate)"],
        "why": ("no machine judges artifact correctness — the human "
                "reads the deliverable; this report does not imply "
                "verification")}
    # the design-review round travels as advice (design-review V3.4):
    # its findings inform the reader of the deliverable and take no
    # part in the decision above — the criteria are unchanged by any
    # finding. The record is read where it lives (the task record, or
    # the planning task-dir a planned change's round ran in) and is
    # never combined with anything
    _review = None
    _cid = state.get("change_id")
    _cands = [task_dir / "planning.json"]
    if _cid:
        _cands.append(repo / ".ai-dlc" / "tasks"
                      / f"{_cid}-planning" / "planning.json")
    for _c in _cands:
        _r = load_json(_c, {}).get("review")
        if isinstance(_r, dict) and _r and not _r.get("skipped") \
                and not _r.get("rejected_team_mode"):
            _review = _r
            break
    if _review is not None:
        _rev = _review.get("revision") or {}
        _syn = _review.get("synthesis") or {}
        rep["review_advice"] = {
            "axes_chosen": [c.get("axis")
                            for c in _review.get("axes_chosen") or []],
            "findings": {a: (r or {}).get("kind") for a, r in
                         (_review.get("reviewers") or {}).items()},
            "convergent": (_review.get("convergent") or {}).get("flag"),
            "synthesis": {
                "path": _syn.get("path"),
                "produced_by": _syn.get("produced_by"),
                "opposing_pairs": [p.get("axes")
                                   for p in
                                   (_syn.get("opposing_pairs") or [])
                                   if isinstance(p, dict)],
                "no_opposing_pairs": _syn.get("no_opposing_pairs"),
                "ok": _syn.get("ok")},
            "unanswered": _rev.get("unanswered"),
            "complete": _review.get("complete"),
            "record": "advice — never a delivery criterion; the "
                      "criteria above are unchanged by any finding "
                      "and by anything the synthesis says"}
    stage = ("DONE" if rep["outcome"] == "completed"
             else "MERGE_GATE" if rep["outcome"] == "merge_pending"
             else "FAILED")
    rep["human_state"] = human_state(stage, delivered)
    # P0-2: a single deliver report must not carry contradictory
    # measurements.  If the design surface is applicable (web/deck files
    # found) but the auto-dispatch returned EXIT_DESIGN_SURFACE (24 —
    # "no web or deck file"), two measurement paths disagreed on the same
    # surface.  This is the country-c-coffee bug: deliver's own
    # design_validation found applicable=true while the subprocess (run
    # with a wrong cwd-resolved task-dir) found 0 files.  Rather than
    # emit a self-contradictory report, fail hard with both measurements
    # so the operator can see the disagreement.
    _da = rep.get("design_auto") or {}
    if (design_applicable
            and isinstance(_da, dict)
            and _da.get("rc") == 24
            and _da.get("state") == "complete"):
        _diag = {
            "refused": True,
            "why": ("contradictory design measurements in one report: "
                    "design.surface.applicable is true but design_auto.rc "
                    "is 24 (no web/deck file) — two paths measured the "
                    "same surface and disagreed"),
            "design_surface": dv["surface"],
            "design_auto": _da,
            "task_dir": str(task_dir),
            "repo": str(repo),
            "measured_ref": measured_ref,
            "remedy": ("this is a bug in task-dir resolution — check that "
                       "the subprocess received an absolute --task-dir")}
        print(json.dumps(_diag, indent=2, ensure_ascii=False),
              file=sys.stderr)
        return 1
    save_json(task_dir / "report.json", rep)
    state.update(stage=stage, human_state=rep["human_state"])
    save_json(task_dir / "state.json", state)
    # N5 (deliver-measures-work): debounce identical delivery reports.
    # A retry that measures the same (ref, base, files) is not a new
    # result — it's the same wrong measurement repeated. The first
    # emission is a full DELIVERY_REPORT; subsequent identical ones are
    # DELIVERY_REPORT_REPEAT with a count, so the event stream doesn't
    # pretend three identical reports are three distinct observations.
    _sig = hashlib.sha256(json.dumps(
        [rep.get("measured_ref"), rep.get("base_sha"),
         sorted(rep.get("files", []))],
        sort_keys=True).encode()).hexdigest()
    _repeat = False
    _repeat_count = 0
    _ev_path = task_dir / "events.jsonl"
    if _ev_path.is_file():
        _lines = _ev_path.read_text(encoding="utf-8").splitlines()
        # search backwards for the last DELIVERY_REPORT or REPEAT event
        # — other events (DESIGN_AUTO_SKIPPED, etc.) may have been
        # appended between delivers
        for _line in reversed(_lines):
            try:
                _ev = json.loads(_line)
            except (json.JSONDecodeError, ValueError):
                continue
            if _ev.get("event") in ("DELIVERY_REPORT",
                                    "DELIVERY_REPORT_REPEAT"):
                if _ev.get("_measurement_sig") == _sig:
                    _repeat = True
                    _repeat_count = _ev.get("_repeat_count", 1) + 1
                break
    if _repeat:
        event(task_dir, event="DELIVERY_REPORT_REPEAT",
              _repeat_count=_repeat_count,
              _measurement_sig=_sig,
              measured_ref=rep.get("measured_ref"),
              outcome=rep.get("outcome"), delivered=rep.get("delivered"))
    else:
        event(task_dir, event="DELIVERY_REPORT",
              _measurement_sig=_sig, **{
                  k: v for k, v in rep.items() if k != "task_id"})
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


def describe_contract(ap: argparse.ArgumentParser) -> dict:
    """N3: a machine-readable capability contract derived from the
    argparse structure (V1 — not hand-written). Lists every verb, its
    required arguments, and the exit codes this executable uses."""
    verbs = []
    for action in ap._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sp in action.choices.items():
                required = []
                for a in sp._actions:
                    if isinstance(a, argparse._StoreAction) and a.required:
                        required.append(a.option_strings[0] if a.option_strings
                                        else a.dest)
                verbs.append({"name": name, "requires": required})
    return {"executable": "report.py",
            "purpose": "the human surface + the gates (delivery report, merge gate)",
            "verbs": verbs,
            "exits": {"0": "success", "1": "refused or no answer",
                      "17": "gate blocked (GATE_BLOCKED_EXIT)"}}


def _build_subparsers(sub) -> None:
    p = sub.add_parser("init")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--route", default="inline",
                   choices=list(ROUTE_VALUES))
    p.add_argument("--task-id", required=True)
    p.add_argument("--change", default=None, dest="change_id",
                   help="openspec change id — deliver validates it strictly")
    p = sub.add_parser("deliver")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--outcome", default="working",
                   help="working | completed | failed")
    p.add_argument("--no-design", action="store_true", dest="no_design",
                   help="do not auto-dispatch the design round even when "
                        "the surface is applicable (J7 — the skip is "
                        "reported, never silent)")
    p.add_argument("--no-design-by", default=None, dest="no_design_by",
                   help="who skips the design round — required with "
                        "--no-design, must be a named human (L6)")
    p.add_argument("--no-design-why", default=None, dest="no_design_why",
                   help="why the design round is skipped — required "
                        "with --no-design")
    p = sub.add_parser("gate")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--gate-id", default="gate-merge")
    p.add_argument("--decision", choices=["approve", "request_changes", "cancel"])
    p.add_argument("--approver", default=None,
                   help="who answered the gate — required with "
                        "--decision, stated by the caller and never "
                        "assumed; an agent says so in the value")
    p.add_argument("--rationale", default="")
    p.add_argument("--request", action="store_true")
    p.add_argument("--summary-file", type=Path)
    p.add_argument("--type", default="MERGE_GATE", dest="gate_type",
                   choices=["MERGE_GATE"],
                   help="MERGE_GATE (delivery approval — the only gate type)")
    p.add_argument("--question", help="override the request question")
    p.add_argument("--options", help="comma-separated decision options")
    p = sub.add_parser("exception")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--reason", default=None,
                   help="why this change stays inline despite the threshold "
                        "(required for a route exception)")
    p.add_argument("--author", default=None,
                   help="who made the exception — stated by the caller, "
                        "never assumed; an agent says so in the value")
    p.add_argument("--design-override", action="store_true",
                   dest="design_override",
                   help="record a human's override of the design-required "
                        "gate — requires --by and --why (M8/L6)")
    p.add_argument("--by", default=None, dest="override_by",
                   help="who overrides the design gate — a named human (L6)")
    p.add_argument("--why", default=None, dest="override_why",
                   help="why the design gate is overridden — required with "
                        "--design-override")
    p = sub.add_parser("correct")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--remove-key", action="append", dest="remove_keys",
                   default=[], metavar="KEY",
                   help="a planning.json key to remove (repeatable) — "
                        "e.g. design_auto, design_override")
    p.add_argument("--corrected-by", default=None, dest="corrected_by",
                   help="who corrects the record — a named human (L6); "
                        "a model may not sign a correction")
    p.add_argument("--why", default=None, dest="correct_why",
                   help="why the record is corrected — required")
    p = sub.add_parser("next",
                       help="ask the system what to do next — a read-only "
                            "query that returns a directly executable "
                            "command (U-B)")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)


def main() -> None:
    if "--describe" in sys.argv:
        ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        sub = ap.add_subparsers(dest="cmd", required=False)
        _build_subparsers(sub)
        print(json.dumps(describe_contract(ap), indent=2, ensure_ascii=False))
        return
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    _build_subparsers(sub)
    args = ap.parse_args()
    # P0-1: resolve task_dir to absolute once, at the entry point — a
    # relative --task-dir is correct only against the parent's cwd, but
    # subprocess dispatches (design_auto_dispatch) re-land with cwd=repo,
    # re-resolving the same relative string against a different base and
    # reading state.json from a non-existent path (the country-c-coffee
    # rc-24 bug).  Resolving here means every downstream function and
    # subprocess receives an absolute path regardless of its own cwd.
    if hasattr(args, "task_dir") and args.task_dir is not None:
        args.task_dir = args.task_dir.resolve()
    if args.cmd == "next":
        sys.exit(cmd_next(args.task_dir, args.repo))
    if args.cmd == "init":
        sys.exit(cmd_init(args.task_dir, args.repo, args.route, args.task_id,
                          args.change_id))
    if args.cmd == "gate":
        sys.exit(cmd_gate(args.task_dir, args.gate_id, args.decision,
                          args.approver, args.rationale, args.request,
                          args.summary_file, args.gate_type,
                          args.question,
                          args.options.split(",") if args.options else None))
    if args.cmd == "exception":
        sys.exit(cmd_exception(args.task_dir, args.reason, args.author,
                               args.design_override, args.override_by,
                               args.override_why))
    if args.cmd == "correct":
        sys.exit(cmd_correct(args.task_dir, args.remove_keys,
                             args.corrected_by, args.correct_why))
    if args.cmd == "deliver":
        sys.exit(cmd_deliver(args.task_dir, args.repo, args.outcome,
                             args.no_design, args.no_design_by,
                             args.no_design_why))
    ap.error(f"unhandled {args.cmd}")


if __name__ == "__main__":
    main()
