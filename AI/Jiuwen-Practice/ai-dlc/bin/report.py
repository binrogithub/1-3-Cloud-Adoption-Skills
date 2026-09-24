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
import contextlib
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_checks import spec_stands  # noqa: E402

# v2 design architecture: design/ IS a product directory. Its files
# (tokens.css, tokens.json, components.md, pages.md, assets.md) count
# toward landed_files/landed_bytes — the structural fix for S1 ("merge
# gate can't see design"). Do NOT add design/** to excludes.
PRODUCT_EXCLUDES = (".ai-dlc/**", "CLAUDE.md", "findings.json",
                    "__pycache__/**", "*.pyc", ".pytest_cache/**",
                    "audits/**", ".ctx-echo", ".skill-echo", "blueprint.json",
                    # session scaffolding the gateway leaves in the tree
                    # (02-static-site finding #6)
                    ".agent_history/**", "coding_memory/**",
                    "prompt_attachment/**")
GATE_BLOCKED_EXIT = 17
GATES = ["G-DELIVER-1", "MERGE_GATE"]
ROUTE_VALUES = ("inline", "planned")

# P0-3 (effort tiering): the expensive patterns are chosen, never
# defaulted into — multi-agent token burn runs ~15x a plain chat and
# token spend alone explained 80% of performance variance (Anthropic's
# multi-agent retrospection), so the tier a task belongs in is stated
# at ROUTE with its shape, crew and a budget ceiling, recorded in
# state.json and echoed by `next`. Tier-3 is entered by explicit choice
# when the task's breadth names it — never by file count alone.
ROUTE_TIERS = {
    "tier-1-inline": {
        "shape": "1-3 files, one surface, no cross-module blast radius",
        "crew": "1 coder-hat session (the coding agent itself)",
        "budget": "3-10 tool calls",
    },
    "tier-2-planned": {
        "shape": "4+ files or spec-bearing; still one repo, one surface",
        "crew": "jiuwenswarm artifact dispatches (proposal/specs/design/tasks) "
                "+ validator dispatch; PM/coder are the agent's hats; adversarial "
                "review round (reviewers run concurrently, default 4)",
        "budget": "10-15 tool calls per role",
    },
    "tier-3-team": {
        "shape": "breadth: multiple surfaces or repos, or context that "
                 "overflows a single session",
        "crew": "tier-2 plus per-surface roles (ui-designer, codegraph) "
                "fanned out concurrently",
        "budget": "bounded per role; the round records what was spent",
    },
}


def route_tier(route: str) -> dict:
    """The tier block for a recorded route — the standing guidance the
    ROUTE decision travels with. tier-3-team is never auto-assigned:
    breadth is named, not counted."""
    tier = "tier-1-inline" if route == "inline" else "tier-2-planned"
    return {"tier": tier, **ROUTE_TIERS[tier],
            "tier_note": ("tier-3-team is entered by explicit choice "
                          "when the task's breadth names it — the "
                          "anti-15x rule: effort scales with complexity, "
                          "never by default")}


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
# G2: the ai-dlc install root (where bin/ + config/ live), measured from
# this file's own location the way install.sh --doctor measures from
# SCRIPT_DIR. A module-level constant so route_doctor_advisory can be
# pointed at a fixture root under test.
_TOOLCHAIN_ROOT = Path(__file__).resolve().parent.parent
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
            "all_files": files,
            "excluded_patterns": list(ROUTE_EXCLUDES),
            "excluded_count": len(excluded)}


def route_check(task_dir: Path, repo: Path, state: dict) -> tuple[dict, dict | None]:
    """The recorded route checked against the change it describes. The
    deliverable is measured and the threshold is one configured number;
    an inline route carrying a change at or above it stops the task for
    a person unless an explicit exception with a reason is recorded —
    the two options are re-running through the plane or recording that
    exception.  A second, independent contradiction: an inline route
    whose change touches the web/deck design surface stops the task
    regardless of file count — even a 1-file .html change — so small
    design-surface changes do not sail through inline with no signal.
    Returns (the check record to carry in the report, the
    block that stops the task, if any)."""
    route = state.get("route")
    threshold = route_threshold()
    work = resolve_work_ref(repo, state)
    measurement = route_measurement(repo, state.get("base_sha"),
                                     ref=work["ref"])
    all_files = measurement.pop("all_files")
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
    # the design surface is an independent contradiction — an inline
    # route touching web/deck files stops the task regardless of file
    # count, so a 1-file .html change does not sail through inline
    # with no signal.  Symmetric with the count-based check: same
    # gate, same exception path, same "contradiction stops the run"
    # shape.
    surface = design_surface(all_files, repo,
                             head=work.get("sha") or work["ref"])
    check["design_surface"] = surface
    if measurement["measured_files"] < threshold and not surface["applicable"]:
        return check, None
    exc = load_json(task_dir / "gates" / "gate-route.answer.json")
    if isinstance(exc, dict) and exc.get("decision") == "exception" \
            and str(exc.get("reason", "")).strip():
        check["exception"] = {"reason": exc.get("reason"),
                              "author": exc.get("author"),
                              "recorded_at": exc.get("ts")}
        return check, None
    over_threshold = measurement["measured_files"] >= threshold
    if over_threshold and surface["applicable"]:
        why = ("an inline route carries a change at or above the "
               "configured threshold and touches the web/deck design "
               "surface — the routing table sends it to the planning plane")
    elif over_threshold:
        why = ("an inline route carries a change at or above "
               "the configured threshold — the routing table "
               "sends it to the planning plane")
    else:
        why = ("an inline route touches the web/deck design surface "
               "(%d file%s) — the routing table sends it to the planning "
               "plane" % (surface["surface_files_total"],
                          "" if surface["surface_files_total"] == 1 else "s"))
    return check, {"why": why, **check}


def is_git_repo(repo: Path) -> bool:
    """N6②: --repo must be an existing git repository. The country-d
    path-typo (wrote <workspace-root>/... when the repo was in /tmp/)
    was silent — this check ends that."""
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def route_doctor_advisory(repo: Path) -> str | None:
    """G2 (ROUTE self-check): a lightweight, read-only subset of
    install.sh --doctor's checks, sized for cmd_next's high-frequency
    read-only call — no network roundtrip, no dispatch, no file writes
    (INV-21/INV-22). Returns None when the toolchain is healthy;
    otherwise a single human-readable string naming the first failed
    check and a copy-pasteable repair command. Never raises.

    Checks, in order, first-failure-wins (design.md §G2):
      1. bin/plan.py and bin/report.py exist and are executable.
      2. config/collapsed.config.yaml exists and parses.
      3. the dispatch gateway client is reachable (a cheap local probe
         of the configured client binary — not a full dispatch).
    """
    root = _TOOLCHAIN_ROOT
    repair = ("re-run the installer from the canonical ai-dlc source: "
              "./install.sh --target <name>")
    # 1. toolchain scripts present and executable
    for f in ("bin/plan.py", "bin/report.py"):
        p = root / f
        if not p.is_file():
            return (f"{f} is missing from the ai-dlc install at {root} — "
                    f"the toolchain is incomplete; {repair}")
        if not os.access(p, os.X_OK):
            return (f"{f} at {p} is not executable — the install lost the "
                    f"exec bit; repair: chmod +x {p}")
    # 2. config exists and parses (no YAML dependency — the file is ours;
    #    readable + non-empty is the parse bar, matching config_scalar)
    cfg = root / "config" / "collapsed.config.yaml"
    if not cfg.is_file():
        return (f"config/collapsed.config.yaml is missing from {root} — "
                f"{repair}")
    try:
        body = cfg.read_text(encoding="utf-8")
    except OSError as exc:
        return (f"config/collapsed.config.yaml at {cfg} is unreadable "
                f"({exc}); {repair}")
    if not body.strip():
        return (f"config/collapsed.config.yaml at {cfg} is empty — the "
                f"install is corrupt; {repair}")
    # 3. gateway client reachable (cheap local probe — no dispatch latency)
    client = os.environ.get(
        "AI_DLC_CLIENT", os.path.expanduser("~/.local/bin/jiuwenswarm"))
    if not Path(client).is_file() or not os.access(client, os.X_OK):
        return (f"the dispatch gateway client {client} is missing or not "
                "executable — planning dispatches will fail; repair: "
                "./install.sh --provision-plane (or set AI_DLC_CLIENT to "
                "an executable client path)")
    return None


def cmd_next(task_dir: Path, repo: Path) -> int:
    """N1/N2: ask the system what to do next. Read-only (V2): no
    dispatch, no state change, no directory creation. The recommendation
    is derived from the task's state files and the plane's records —
    the same preconditions the verbs check (V6), not a second copy.

    Output shape (U-B):
        stage, human_state, blocked_on, why, do, then, not_yet
    where `do` is a directly executable command line and `not_yet`
    names what cannot run yet and the exit code it would return.

    G2: before returning, runs route_doctor_advisory once and, when it
    is non-None, adds an `advisory` key to the returned object. The
    check never blocks, never retries, never changes the exit code, and
    performs no file writes (INV-21/INV-22). Existing keys keep their
    shape and meaning.
    """
    advisory = route_doctor_advisory(repo)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _cmd_next_base(task_dir, repo)
    out = buf.getvalue().strip()
    if advisory is not None and out:
        try:
            obj = json.loads(out)
            if isinstance(obj, dict):
                obj["advisory"] = advisory
                out = json.dumps(obj, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass  # never let the advisory corrupt the base output
    if out:
        print(out)
    return rc


def _cmd_next_base(task_dir: Path, repo: Path) -> int:
    """The pre-G2 body of cmd_next — computes stage/blocked_on/do/then/
    not_yet and prints exactly one JSON object. cmd_next wraps this to
    inject the route-doctor advisory.

    Read-only (V2): no dispatch, no state change, no directory creation.
    The recommendation is derived from the task's state files and the
    plane's records — the same preconditions the verbs check (V6), not a
    second copy. Output shape (U-B): stage, human_state, blocked_on, why,
    do, then, not_yet.
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
    # P0-3: the tier recorded at init (or derived when the state
    # predates it) travels with every recommendation
    tier = state.get("tier") or route_tier(route)
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
                "tier": tier["tier"], "tier_budget": tier["budget"],
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
            "tier": tier["tier"], "tier_budget": tier["budget"],
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
        # 02-static-site finding #5: init run AFTER committing on the
        # task branch records base==head and every later measurement
        # comes back empty - twice bitten. Say it while it is fixable.
        _cur = git(repo, "branch", "--show-current").strip()
        if _cur == branch:
            st["base_warning"] = (
                "HEAD already sits on %s - base recorded at HEAD "
                "measures nothing; reset base to the fork point (git "
                "merge-base <target> HEAD) or re-record it, before "
                "delivering" % branch)
    # P0-3: the effort tier travels with the route decision — its
    # shape, crew and budget ceiling are stated at ROUTE, recorded, and
    # echoed by `next`, so the expensive patterns are chosen
    st["tier"] = route_tier(route)
    # finding #2 (AB-lab E2E, 2026-09-08): the plane keys specs trees,
    # records and task state by the exact repo path — a linked worktree
    # carries its own path and therefore its own plane identity. That
    # is legitimate (every task branch uses one) but mixing the main
    # checkout with the worktree has now stranded work twice (colombia,
    # AB-lab); the warning states the contract while it can still be
    # honored: init, every dispatch and deliver name the SAME path.
    try:
        _gd = Path(git(repo, "rev-parse", "--git-dir").strip())
        _gcd = Path(git(repo, "rev-parse",
                        "--git-common-dir").strip())
        _linked = (_gd.resolve() != _gcd.resolve())
    except Exception:                           # noqa: BLE001
        _linked = False            # unreadable is no reason to warn
    if _linked:
        st["repo_identity_note"] = (
            "linked worktree: the plane keys specs, records and state "
            "by this exact path (%s) — use it for every dispatch and "
            "deliver too; mixing it with the main checkout strands "
            "the work (measured: colombia, AB-lab 2026-09-08)" % repo)
    save_json(task_dir / "state.json", st)
    event(task_dir, event="TASK_STARTED", task_id=task_id, route=route,
          base_sha=base, change_id=change_id)
    out = {"task_dir": str(task_dir), "base_sha": base,
           "route": route, "change_id": change_id,
           "stage": stage, "human_state": human,
           "tier": st["tier"]["tier"], "tier_budget": st["tier"]["budget"]}
    if branch:
        out["branch"] = branch
        out["work_on"] = (f"git -C {repo} worktree add ../wt/{change_id} "
                          f"-b {branch}")
    if "repo_identity_note" in st:
        out["repo_identity_warning"] = st["repo_identity_note"]
    if "base_warning" in st:
        out["base_warning"] = st["base_warning"]
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


# P1-6 (anti-collusion): the merge gate's standing reminder — measured
# facts outrank consensus. A unanimous approval never overrides a
# measured failure; the human reads the diff, not the mood.
GATE_AUTHORITY_NOTE = (
    "Machine facts are authoritative: the git diff, the execution gate "
    "and the five-facts frames outrank any reviewer consensus — however "
    "unanimous an approval reads, it never overrides a measured failure.")


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
            _selection_degraded = bool(_dv.get("selection_degraded"))
            if _selection_degraded:
                # a silently-degraded arbiter result must not reuse the
                # generic nonconforming warning — the human needs to see
                # that the *selection itself* was unreliable, not just
                # "design not verified".
                _sdr = _dv.get("selection_degraded_reason", "")
                _sf = (_dv.get("surface") or {}).get("surface_files") or []
                _sf_display = ", ".join(_sf[:10])
                if len(_sf) > 10:
                    _sf_display += ", and %d more" % (len(_sf) - 10)
                question = (
                    "⚠ Design selection degraded: %s\n"
                    "Files: %s\n"
                    "Merge this delivery into the target branch? "
                    "(rationale required)" % (_sdr, _sf_display))
            elif _design_warn:
                _n = (_dv.get("surface") or {}).get("surface_files_total", 0)
                _rc = (_report.get("design_auto") or {}).get("rc", "?")
                _ds = _dv.get("design_state", "design_unverified")
                question = (
                    "⚠ Design %s: surface has %d web/deck files, "
                    "design not verified (rc=%s)." % (_ds, _n, _rc))
                # append concrete evidence — file names and failed D3
                # check names — so the human sees what specifically
                # failed without opening state.json.
                _sf = (_dv.get("surface") or {}).get("surface_files") or []
                if _sf:
                    _sf_display = ", ".join(_sf[:10])
                    if len(_sf) > 10:
                        _sf_display += ", and %d more" % (len(_sf) - 10)
                    question += "\nFiles: %s" % _sf_display
                _d3_checks = (_dv.get("d3_checks") or {}).get("checks") or {}
                _failed_d3 = [k for k, v in _d3_checks.items() if not v]
                if _failed_d3:
                    question += "\nFailed D3 checks: %s" % ", ".join(
                        _failed_d3)
                question += ("\nMerge this delivery into the target branch? "
                             "(rationale required)")
            else:
                question = ("Merge this delivery into the target branch? "
                            "(rationale required)")
        # P1-6: the standing reminder and the execution gate's verdict
        # ride with every default question — the human at the gate sees
        # the machine facts' state and their authority before deciding
        _eg_state = ((_report.get("execution_gate") or {}).get("state"))
        if not question:
            question = ""
        question += "\nExecution gate: %s." % (
            _eg_state or "not run (this report predates the gate)")
        _orphans = ((_report.get("alignment") or {})
                    .get("orphan_requirements") or [])
        if _orphans:
            question += ("\nSpec alignment: %d requirement(s) not "
                         "reflected in the landed diff: %s."
                         % (len(_orphans), "; ".join(_orphans[:5])))
        question += "\n" + GATE_AUTHORITY_NOTE
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
            # surface concrete evidence in the gate summary so the human
            # can see which D3 checks failed and whether the selection
            # was degraded, without opening report.json.
            _d3 = dv.get("d3_checks") or {}
            _checks = _d3.get("checks") or {}
            summary["failed_d3_checks"] = [
                k for k, v in _checks.items() if not v]
            if dv.get("selection_degraded"):
                summary["selection_degraded"] = True
                summary["selection_degraded_reason"] = dv.get(
                    "selection_degraded_reason", "")
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


def _annotate_selection_degraded(result: dict, state: dict) -> dict:
    """When D0 SELECT recorded a degraded selection (arbiter replied
    but named no shortlist path, etc.), layer that fact onto the
    design_validation result so downstream readers (gate-merge,
    humans) can distinguish 'design verified but the selection itself
    was unreliable' from a clean run. Adds two optional keys only —
    never removes or alters existing keys, so callers that don't know
    about them are unaffected (backward compatible)."""
    selection = state.get("design_selection") or {}
    if selection.get("degraded"):
        result["selection_degraded"] = True
        result["selection_degraded_reason"] = selection.get("reason", "")
    return result


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
            return _annotate_selection_degraded(
                {"design_state": "design_verified",
                 "artifacts": artifacts, "d3_checks": d3,
                 "surface": surface}, state)
        if d3["available"] and not d3["all_pass"]:
            return _annotate_selection_degraded(
                {"design_state": "design_nonconforming",
                 "artifacts": artifacts, "d3_checks": d3,
                 "why": ("design spec artifacts exist but one or more "
                         "D3 verify checks failed — the pages do not "
                         "conform to the spec"),
                 "surface": surface}, state)
        # artifacts exist but D3 verify hasn't run yet — nonconforming
        # until verified (the spec stands but conformance is unproven)
        return _annotate_selection_degraded(
            {"design_state": "design_nonconforming",
             "artifacts": artifacts,
             "d3_checks": d3,
             "why": ("design spec artifacts exist but D3 verify has "
                     "not run — run plan.py design-verify to check "
                     "conformance"),
             "remedy": "plan.py design-verify --change <id> --repo <repo>",
             "surface": surface}, state)
    # v1 legacy fallback: check for signed design records (backward compat
    # for tasks that ran the v1 design dispatch without producing v2
    # product-side artifacts).
    record_key = state.get("change_id") or state.get("task_id")
    if not record_key:
        return _annotate_selection_degraded(
            {"design_state": "design_unspecified",
             "why": ("no design spec artifacts exist and no change id "
                     "or task id recorded — D1 SPECIFY was never run"),
             "artifacts": artifacts, "surface": surface}, state)
    records, rejected = signed_records(str(record_key), "design")
    if rejected:
        return _annotate_selection_degraded(
            {"design_state": "design_unverified",
             "why": ("design records failed signature verification "
                     "— tampering evidence, not a conclusion"),
             "rejected_records": rejected, "surface": surface}, state)
    rec = None
    for r in reversed(records):
        if r.get("verb") == "design":
            rec = r
            break
    if rec is not None:
        return _annotate_selection_degraded(
            {"design_state": "design_applied",
             "record": {k: rec.get(k) for k in
                        ("ts", "session", "surface", "template",
                         "design_system", "files", "assets", "render",
                         "placeholders")},
             "artifacts": artifacts, "surface": surface}, state)
    # no product-side artifacts, no signed record — unspecified
    return _annotate_selection_degraded(
        {"design_state": "design_unspecified",
         "why": ("no design spec artifacts exist (design/tokens.css etc.) "
                 "and no signed design record stands — D1 SPECIFY was "
                 "never run or produced no artifacts"),
         "remedy": "plan.py design-pick --change <id> --repo <repo>",
         "artifacts": artifacts, "surface": surface}, state)


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
    # panama-v2 finding: cmd_design_select/pick write {chosen,
    # skill_name, skill_sha256} — the old `skill` key matched neither,
    # so every selected design looked "not designed" at deliver and
    # the auto-dispatch re-ran the whole design pipeline (select,
    # second opinion, specify) over committed artifacts. Two facts
    # now short-circuit: a selection with a chosen skill path, and a
    # completed D1 (design_spec.all_written).
    _selected = isinstance(selection, dict) and bool(
        selection.get("skill") or selection.get("chosen"))
    _d1_done = isinstance(state.get("design_spec"), dict) and bool(
        state["design_spec"].get("all_written"))
    if _selected or _d1_done:
        _sf = surface.get("surface_files", [])
        _all_have_content = bool(_sf) and all(
            (repo / f).stat().st_size > 200 for f in _sf
            if (repo / f).exists())
        if _all_have_content or _d1_done:
            return False, "designed_in_work"
    planning = load_json(task_dir / "planning.json", {})
    decision = planning.get("design_decision")
    if isinstance(decision, dict) and decision.get("skip"):
        return False, "declined"
    # E1/S1.1+S1.2 — the record question is a union, never one source: a
    # D1 design spec standing in state.json (written by `plan.py design`)
    # counts exactly like a plane-side signed record. Before this, a
    # design run followed by deliver re-entered D0+D1 (381.6s on the
    # chile-tourism-site baseline) and rewrote design/ into a second,
    # diverging generation — the site followed generation one while the
    # repo carried generation two. A standing spec still earns ONE
    # verify-only pass (mode below): a fresh D3 measurement against the
    # surface as it stands at deliver time — the chile run's all_pass
    # was measured against a pageless tree, which proved nothing. A D1
    # rewrite needs an explicit human-triggered --redesign; it never
    # happens implicitly here.
    if spec_stands(state):
        return True, "verify_only"

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
                         head: str | None = None,
                         redesign: bool = False) -> dict:
    """One automatic design dispatch via subprocess (E4). The attempt is
    recorded in planning.json.design_auto BEFORE the session opens — a
    killed process still leaves the fact (J2/A10). The dispatch's rc
    and outcome never change deliver's exit code or `delivered` (J3).

    E1/S1.2 — two modes, chosen by what already stands:
      verify_only  — a D1 spec stands (state.json design_spec): run the
                     D3 checks and nothing else. No session opens, no
                     artifact is rewritten, and the pass does not burn
                     the 2-attempt budget (a verify costs nothing to
                     repeat against a fresh surface).
      full         — nothing stands: the original D0→D1→D3 dispatch.
    A full rewrite over a standing spec requires a human-triggered
    --redesign; it never happens implicitly."""
    # M4: use change_id or task_id as the dispatch and record key.
    change = str(state.get("change_id") or state.get("task_id"))
    mode = "verify_only" if (spec_stands(state) and not redesign) else "full"
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
           "trigger": "deliver", "mode": mode, "rc": None, "outcome": None,
           "session": None, "elapsed_seconds": None,
           "attempts": prior_attempts, "state": "incomplete"}
    planning["design_auto"] = pre
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="DESIGN_AUTO_DISPATCHED", change=change,
          trigger="deliver", attempted_at=attempted_at, mode=mode)
    if mode == "verify_only":
        # D3 only — the shared C-D3 checks through the plan.py verb; no
        # D0, no D1, no session, nothing rewritten (E1/S1.2).
        cmd = [sys.executable, str(PLAN_PY), "design-verify",
               "--change", change, "--repo", str(repo),
               "--task-dir", str(task_dir.resolve())]
    else:
        cmd = [sys.executable, str(PLAN_PY), "design",
               "--change", change, "--repo", str(repo),
               "--task-dir", str(task_dir.resolve())]
    # A4: retrofit sharding — one file per session, all concurrent.
    # The auto-dispatch is the retrofit path (A2); the correct
    # granularity is one file per session, not one serial session
    # over all files.  5 files → 5 ~300s sessions, not 1 × 1800s.
    if mode == "full":
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
    # E1: verify_only passes never burn the attempt budget — a verify
    # opens no session and rewrites nothing, so repeating it against a
    # fresh surface is free.
    new_attempts = prior_attempts if mode == "verify_only" \
        else prior_attempts + 1
    rec = {"attempted_at": attempted_at, "change": change,
           "trigger": "deliver", "mode": mode, "rc": rc, "outcome": outcome,
           "session": session, "elapsed_seconds": elapsed,
           "attempts": new_attempts, "state": "complete"}
    planning = load_json(task_dir / "planning.json", {})
    planning["design_auto"] = rec
    save_json(task_dir / "planning.json", planning)
    event(task_dir, event="DESIGN_AUTO_DISPATCHED", change=change,
          rc=rc, outcome=outcome, elapsed_seconds=elapsed,
          session=session, mode=mode)
    return rec

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


# ── P0-4 execution gate: the repo's own toolchain gets a vote ──────
# G-DELIVER-1 already measures two machine facts: the spec validates
# strictly, and the work landed (git diff). Neither says the code runs.
# This gate adds the third: the repo's own toolchain verdict — tests,
# lint, typecheck. A tool runs only when the repo's surface asks for it
# (changed files of that language + the tool's config/test surface
# present) AND its binary is available; a language with no usable
# toolchain is recorded not_applicable, never silently skipped (the
# design states pattern). Lint/typecheck are scoped to the changed
# files so feedback stays in seconds; the test suite runs as the repo
# defines it. The gate reports executability, not correctness — a green
# gate is necessary, never sufficient (SKILL.md states this).
# AI_DLC_EXEC_TOOLS_JSON replaces discovery with a fixed plan
# ([{"name", "cmd", "scope"}], cmd a list) so tests can drive the gate
# without installing toolchains; AI_DLC_EXEC_TIMEOUT bounds each tool.

EXEC_GATE_TIMEOUT = int(os.environ.get("AI_DLC_EXEC_TIMEOUT", "300"))

EXEC_GATE_LANG_EXTS = {
    "python": (".py",),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx"),
}


def _exec_lang_files(files: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in files:
        for lang, exts in EXEC_GATE_LANG_EXTS.items():
            if f.endswith(exts):
                out.setdefault(lang, []).append(f)
                break
    return out


def _tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None


def execution_tool_plan(repo: Path, files: list[str]) -> list[dict]:
    """The tools this delivery's changed surface asks for. Every entry
    carries either a cmd to run or an explicit not_applicable reason —
    a language present in the change is never absent from the plan."""
    env_plan = os.environ.get("AI_DLC_EXEC_TOOLS_JSON")
    if env_plan:
        return json.loads(env_plan)
    plan: list[dict] = []
    langs = _exec_lang_files(files)
    py = langs.get("python", [])
    if py:
        # flat layouts count too: a root-level test_*.py with no tests/
        # dir and no config is still a pytest surface (the AB-lab E2E
        # measured this gap live - finding #1, 2026-09-08)
        has_pytest_surface = ((repo / "tests").is_dir()
                              or (repo / "pytest.ini").is_file()
                              or (repo / "pyproject.toml").is_file()
                              or any(repo.glob("test_*.py"))
                              or any(repo.glob("*_test.py")))
        if has_pytest_surface:
            # 06-records finding: a downloaded project carries its own
            # venv - the plane interpreter cannot see its deps. Prefer
            # the project's interpreter when it stands and carries
            # pytest; the plane's is the fallback.
            venv_py = repo / ".venv" / "bin" / "python"
            if venv_py.is_file():
                probe = subprocess.run(
                    [str(venv_py), "-c", "import pytest"],
                    capture_output=True)
                if probe.returncode == 0:
                    plan.append({"name": "pytest",
                                 "cmd": [str(venv_py), "-m", "pytest",
                                         "-q"],
                                 "scope": "suite",
                                 "detect": "project .venv carries "
                                           "pytest"})
                else:
                    plan.append({"name": "pytest",
                                 "status": "not_applicable",
                                 "why": (".venv exists but carries no "
                                         "pytest - the plane "
                                         "interpreter cannot see the "
                                         "project deps either")})
            else:
                plan.append({"name": "pytest",
                             "cmd": [sys.executable, "-m", "pytest",
                                     "-q"],
                             "scope": "suite",
                             "detect": "tests/ or pytest config "
                                       "present"})
        else:
            plan.append({"name": "pytest", "status": "not_applicable",
                         "why": "no tests/ directory or pytest config"})
        if _tool_available("ruff"):
            # 04-config-app finding: a foreign repo carries no
            # ruff.toml - the bare default is style maximalism (UP/SIM/
            # TRY...) that blocks real deliveries. The gate brings its
            # own conservative floor, matching the plane's ruff.toml.
            plan.append({"name": "ruff", "cmd": ["ruff", "check",
                                                 "--select", "E,F",
                                                 "--ignore", "E501",
                                                 *py],
                         "scope": "changed-files",
                         "detect": "ruff on PATH"})
        else:
            plan.append({"name": "ruff", "status": "not_applicable",
                         "why": "ruff not on PATH"})
        if (repo / "pyproject.toml").is_file():
            if _tool_available("mypy"):
                plan.append({"name": "mypy", "cmd": ["mypy", *py],
                             "scope": "changed-files",
                             "detect": "mypy on PATH + pyproject.toml"})
            else:
                plan.append({"name": "mypy", "status": "not_applicable",
                             "why": "mypy not on PATH (pyproject.toml present)"})
        else:
            plan.append({"name": "mypy", "status": "not_applicable",
                         "why": "no pyproject.toml"})
    js = langs.get("javascript", []) + langs.get("typescript", [])
    if js:
        pkg = {}
        pkg_path = repo / "package.json"
        if pkg_path.is_file():
            try:
                pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pkg = {}
        if (pkg.get("scripts") or {}).get("test"):
            plan.append({"name": "npm test",
                         "cmd": ["npm", "test", "--silent"],
                         "scope": "suite",
                         "detect": "package.json test script present"})
        else:
            plan.append({"name": "npm test", "status": "not_applicable",
                         "why": "package.json has no test script"})
        if langs.get("typescript") and (repo / "tsconfig.json").is_file():
            if _tool_available("npx"):
                plan.append({"name": "tsc", "cmd": ["npx", "--no-install",
                                                    "tsc", "--noEmit"],
                             "scope": "suite",
                             "detect": "tsconfig.json + npx on PATH"})
            else:
                plan.append({"name": "tsc", "status": "not_applicable",
                             "why": "npx not on PATH (tsconfig.json present)"})
        elif langs.get("typescript"):
            plan.append({"name": "tsc", "status": "not_applicable",
                         "why": "no tsconfig.json"})
    return plan


def _changed_lines(repo: Path, base: str | None,
                   files: list[str]) -> dict[str, set[int]]:
    """Per-file set of line numbers this change touched (diff base..HEAD;
    without a recorded base the last commit is the honest fallback) —
    the input for changed-line-only lint verdicts."""
    ref = f"{base}..HEAD" if base else "HEAD~1..HEAD"
    out: dict[str, set[int]] = {}
    for f in files:
        proc = subprocess.run(
            ["git", "-C", str(repo), "diff", "--unified=0", ref, "--", f],
            capture_output=True, text=True)
        lines = set()
        for m in re.finditer(r"^@@ -(?:\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?",
                             proc.stdout, re.M):
            start = int(m.group(2))
            count = int(m.group(3) or 1)
            lines.update(range(start, start + count))
        if lines:
            out[f] = lines
    return out


def run_execution_gate(repo: Path, files: list[str],
                       base: str | None = None) -> dict:
    """Run the plan, one subprocess per tool, bounded by the timeout.
    The gate runs in the working tree deliver was invoked from — for a
    task branch that must be the worktree where the work lives (the
    diff measures the branch; the tools measure the tree)."""
    plan = execution_tool_plan(repo, files)
    py_files = [f for f in files if f.endswith(".py")]
    results = []
    for entry in plan:
        if "cmd" not in entry:
            results.append({"name": entry["name"],
                            "status": "not_applicable",
                            "why": entry.get("why", "no command")})
            continue
        started = time.monotonic()
        try:
            proc = subprocess.run(entry["cmd"], capture_output=True,
                                  text=True, cwd=str(repo),
                                  timeout=EXEC_GATE_TIMEOUT)
            rc = proc.returncode
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            status = "pass" if rc == 0 else "fail"
            # V3 (process-integrity): a touched file's PRE-EXISTING
            # debt must not block the delivery — ruff verdicts count
            # only diagnostics on lines this change actually touched.
            # The debt is reported honestly, not hidden.
            if entry["name"] == "ruff" and rc != 0 \
                    and os.environ.get(
                        "AI_DLC_EXEC_RUFF_WHOLEFILE") != "1":
                try:
                    jproc = subprocess.run(
                        entry["cmd"] + ["--output-format", "json"],
                        capture_output=True, text=True, cwd=str(repo),
                        timeout=EXEC_GATE_TIMEOUT)
                    diags = json.loads(jproc.stdout or "[]")
                except (json.JSONDecodeError,
                        subprocess.TimeoutExpired):
                    diags = []
                touched = _changed_lines(repo, base, py_files)
                mine, debt = [], 0
                for d in diags:
                    rel = str(Path(d.get("filename", ""))
                              .relative_to(repo))
                    if rel in touched \
                            and d.get("location", {}).get("row")                             in touched[rel]:
                        mine.append(d)
                    else:
                        debt += 1
                if not mine:
                    status = "pass"
                    output = (f"changed lines clean; "
                              f"baseline_debt_ignored={debt} "
                              f"(pre-existing findings on untouched "
                              f"lines of touched files)")
                    rc = 0
                else:
                    output = ("changed-line findings: "
                              + "; ".join(
                                  f"{Path(d['filename']).name}:"
                                  f"{d['location']['row']} "
                                  f"{d.get('code', '?')}"
                                  for d in mine[:5])
                              + f"; baseline_debt_ignored={debt}")
        except subprocess.TimeoutExpired:
            rc, output, status = (None, "timed out after %ss"
                                  % EXEC_GATE_TIMEOUT, "fail")
        except FileNotFoundError:
            rc, output, status = (None, "binary not found: %s"
                                  % entry["cmd"][0], "fail")
        # pool20 finding (semver/arrow/wcwidth): a downloaded project's
        # pytest addopts routinely name plugins the delivery venv does
        # not carry (pytest-cov in .pytest.ini/tox.ini) — the probe
        # dies at usage error (rc 4) before running a single test. A
        # usage error is a broken probe, not a failing suite: retry
        # once with the project addopts cleared and record both. The
        # retry's verdict is the gate's.
        if entry["name"] == "pytest" and rc == 4:
            fb_cmd = entry["cmd"] + ["-o", "addopts="]
            try:
                proc2 = subprocess.run(fb_cmd, capture_output=True,
                                       text=True, cwd=str(repo),
                                       timeout=EXEC_GATE_TIMEOUT)
                fb_out = ((proc2.stdout or "") + "\n"
                          + (proc2.stderr or "")).strip()
                output = ("[probe died at usage error] "
                          + (output.splitlines()[-1]
                             if output.splitlines() else "")
                          + "\n[retry with project addopts cleared]\n"
                          + fb_out)
                rc = proc2.returncode
                status = "pass" if rc == 0 else "fail"
                entry = {**entry, "cmd": fb_cmd,
                         "fallback": ("project addopts cleared after "
                                      "usage error")}
            except subprocess.TimeoutExpired:
                rc, output, status = (None, "retry timed out after %ss"
                                      % EXEC_GATE_TIMEOUT, "fail")
        results.append({
            "name": entry["name"], "cmd": entry["cmd"],
            "scope": entry.get("scope"), "status": status, "rc": rc,
            **({"fallback": entry["fallback"]}
               if "fallback" in entry else {}),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "output_tail": output.splitlines()[-25:]})
    ran = [r for r in results if r["status"] != "not_applicable"]
    state = ("not_applicable" if not ran else
             "fail" if any(r["status"] == "fail" for r in ran) else "pass")
    return {"state": state, "ran": len(ran), "tools": results,
            "timeout_seconds": EXEC_GATE_TIMEOUT}


# ── P1-5 (turn checkpoints — ported from grok-build's session/checkpoint.rs):
# any writing turn can key the worktree's state: HEAD plus the dirty
# region pinned as a stash-commit object (`git stash create` — nothing
# is stashed away, the working tree is untouched; the object simply
# records what was uncommitted). The registry lives in the task dir;
# restore carries a stash-or-abort guard and never clobbers a dirty
# tree blind. Ported per Apache-2.0 §4(b) from xai-org/grok-build
# crates/codegen/xai-grok-workspace/src/session/{checkpoint,git}.rs.
def checkpoints_path(task_dir: Path) -> Path:
    return task_dir / "checkpoints.json"


def _worktree_dirty(repo: Path) -> list[str]:
    """Product paths only — .ai-dlc/ and its siblings are bookkeeping,
    excluded from PRODUCT_EXCLUDES, and never a work region."""
    out = git(repo, "status", "--porcelain")
    dirty = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"').split(" -> ")[-1]
        if not excluded(path):
            dirty.append(line.strip())
    return dirty


def cmd_checkpoint(task_dir: Path, repo: Path, label: str | None,
                   list_cps: bool, show_seq: int | None,
                   restore_seq: int | None, stash_first: bool) -> int:
    if not is_git_repo(repo):
        print(json.dumps({"refused": True, "why": (
            "--repo %s is not a git repository" % repo)},
            indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    cps = load_json(checkpoints_path(task_dir), {"checkpoints": []})
    items: list = cps.get("checkpoints", [])

    def _find(seq: int) -> dict | None:
        return next((c for c in items if c.get("seq") == seq), None)

    if restore_seq is not None:
        cp = _find(restore_seq)
        if cp is None:
            print(json.dumps({"refused": True, "why": (
                "no checkpoint %d on record — checkpoint --list names "
                "what exists" % restore_seq)}, indent=2,
                ensure_ascii=False), file=sys.stderr)
            return 1
        dirty = _worktree_dirty(repo)
        if dirty and not stash_first:
            print(json.dumps({"refused": True, "seq": restore_seq,
                "dirty_now": dirty[:20],
                "why": ("restore refuses rather than clobber a dirty "
                        "tree — pass --stash-first (the stash is named "
                        "and recorded) or clean by hand"),
                "guard": "stash-or-abort"}, indent=2, ensure_ascii=False),
                file=sys.stderr)
            return 1
        if dirty and stash_first:
            stash_msg = ("pre-restore of checkpoint %d — %s"
                         % (restore_seq, now_iso()))
            git(repo, "stash", "push", "-m", stash_msg)
            cp.setdefault("restore_stashes", []).append(
                {"message": stash_msg, "ts": now_iso()})
            save_json(checkpoints_path(task_dir), cps)
        git(repo, "restore", "--source=" + cp["head"],
            "--staged", "--worktree", "--", ".")
        created_after = [d for d in _worktree_dirty(repo)
                         if d.startswith("??")]
        event(task_dir, event="CHECKPOINT_RESTORED", seq=restore_seq,
              head=cp["head"], stashed=bool(dirty and stash_first),
              created_after=created_after[:20])
        print(json.dumps({"restored": restore_seq, "head": cp["head"],
                          "stashed_first": bool(dirty and stash_first),
                          "created_after_remain": created_after[:20],
                          "dirty_commit_at_checkpoint":
                              cp.get("dirty_commit"),
                          "note": ("tracked files are back at the "
                                   "checkpoint's HEAD; files created "
                                   "after it remain and are listed; the "
                                   "checkpoint's uncommitted region is "
                                   "the dirty_commit object above")},
                         indent=2, ensure_ascii=False))
        return 0

    if show_seq is not None:
        cp = _find(show_seq)
        if cp is None:
            print(json.dumps({"refused": True, "why": (
                "no checkpoint %d on record" % show_seq)},
                indent=2, ensure_ascii=False), file=sys.stderr)
            return 1
        prev = next((c for c in reversed(items)
                     if c["seq"] < show_seq), None)
        if prev is None:
            print(json.dumps({"seq": cp["seq"], "head": cp["head"],
                              "first": True,
                              "dirty_files_at_checkpoint":
                                  cp.get("dirty_count", 0)},
                             indent=2, ensure_ascii=False))
            return 0
        diff = git(repo, "diff", "--stat",
                   "%s..%s" % (prev["head"], cp["head"]))
        print(json.dumps({"seq": cp["seq"], "label": cp.get("label"),
                          "from_seq": prev["seq"],
                          "diff_stat": diff.strip().splitlines()[-30:]},
                         indent=2, ensure_ascii=False))
        return 0

    if list_cps or not label:
        print(json.dumps({"checkpoints": [
            {"seq": c["seq"], "ts": c.get("ts"),
             "label": c.get("label"), "head": c["head"],
             "dirty_files": c.get("dirty_count", 0)}
            for c in items]}, indent=2, ensure_ascii=False))
        return 0

    head = git(repo, "rev-parse", "HEAD").strip()
    dirty = _worktree_dirty(repo)
    dirty_commit = git(repo, "stash", "create").strip() or None
    seq = (items[-1]["seq"] + 1) if items else 1
    rec = {"seq": seq, "ts": now_iso(), "label": label,
           "head": head, "dirty_count": len(dirty),
           "dirty_files": dirty[:50],
           "dirty_commit": dirty_commit}
    items.append(rec)
    cps["checkpoints"] = items
    save_json(checkpoints_path(task_dir), cps)
    event(task_dir, event="CHECKPOINT_RECORDED", seq=seq, head=head,
          dirty_files=len(dirty), label=label)
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


# ── P1-4 (decision-pattern dashboard): aggregates over the task's own
# records — dispatch outcomes, per-role wall-clock, execution-gate
# states, checkpoint counts. Patterns, never conversation contents
# (Anthropic's production lesson: monitor decision patterns, not
# prose, for privacy and for signal).
def cmd_patterns(task_dir: Path) -> int:
    planning = load_json(task_dir / "planning.json", {})
    report_json = load_json(task_dir / "report.json", {})
    checkpoints = load_json(task_dir / "checkpoints.json",
                            {"checkpoints": []})

    roles: dict[str, dict] = {}

    def _role(name: str, outcome, elapsed) -> None:
        r = roles.setdefault(name, {"dispatches": 0, "ok": 0,
                                    "elapsed": []})
        r["dispatches"] += 1
        if outcome == 0:
            r["ok"] += 1
        if isinstance(elapsed, (int, float)):
            r["elapsed"].append(round(float(elapsed), 2))

    review = planning.get("review") or {}
    for axis, r in (review.get("reviewers") or {}).items():
        _role("review-%s" % axis, r.get("outcome"),
              r.get("elapsed_seconds"))
    for key, tag in (("codegraph_auto", "codegraph"),
                     ("design_auto", "design-auto")):
        rec = planning.get(key)
        if isinstance(rec, dict):
            _role(tag, rec.get("rc"), rec.get("elapsed_seconds"))
    for verb, rec in (planning.get("plane_dispatches") or {}).items():
        if isinstance(rec, dict):
            _role(verb, rec.get("rc", rec.get("outcome")),
                  rec.get("elapsed_seconds"))

    role_stats = []
    for name, r in sorted(roles.items()):
        elapsed = sorted(r["elapsed"]) or [0.0]
        role_stats.append({
            "role": name, "dispatches": r["dispatches"],
            "ok": r["ok"],
            "success_rate": round(r["ok"] / r["dispatches"], 3)
            if r["dispatches"] else None,
            "elapsed_mean_s": round(sum(elapsed) / len(elapsed), 2),
            "elapsed_median_s": round(
                elapsed[len(elapsed) // 2], 2)})

    events: dict[str, int] = {}
    ev_path = task_dir / "events.jsonl"
    if ev_path.is_file():
        for line in ev_path.read_text(encoding="utf-8",
                                      errors="replace").splitlines():
            try:
                ev = json.loads(line).get("event")
            except (json.JSONDecodeError, ValueError):
                continue
            if ev:
                events[ev] = events.get(ev, 0) + 1

    out = {
        "task_dir": str(task_dir),
        "roles": role_stats,
        "execution_gate": (report_json.get("execution_gate") or {}).get(
            "state"),
        "delivered": report_json.get("delivered"),
        "outcome": report_json.get("outcome"),
        "landed_files": report_json.get("landed_files"),
        "checkpoints": len(checkpoints.get("checkpoints", [])),
        "events": dict(sorted(events.items(),
                              key=lambda kv: -kv[1])[:15]),
        "note": ("patterns over the task's own records — dispatch "
                 "outcomes, wall-clock, gate states; never conversation "
                 "contents"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


# ── P1-10 (spec↔implementation alignment): the delivered diff and the
# change's requirements are laid side by side — every ADDED/MODIFIED
# Requirement should be reflected in at least one hunk, and a hunk
# that answers to no requirement is implementation beyond the spec.
# The mapping is token-overlap (the requirement's significant terms
# against each hunk's changed lines), reported as visible information
# with both directions of orphan named — a spec that validates
# strictly but never lands is a novel, and the human at the gate
# deserves to see that before approving (SDD's validate-alignment
# step; Martin Fowler: an unaligned spec degrades into fiction).
ALIGN_STOPWORDS = frozenset((
    "the", "and", "shall", "must", "when", "then", "with", "that",
    "this", "from", "for", "into", "are", "was", "were", "not", "but",
    "its", "their", "every", "each", "any", "all", "one", "two",
    "requirement", "scenario", "system", "task", "change", "report",
    "record", "file", "files", "name", "named", "carry", "carries",
    "exist", "exists", "present", "before", "after", "never", "always",
))


def _requirement_tokens(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    return {w for w in words if w not in ALIGN_STOPWORDS}


def spec_alignment(repo: Path, base: str | None, head: str | None,
                   specs_dir: Path | None) -> dict | None:
    """The Requirement↔hunk mapping for a planned change, or None when
    there is nothing to align (no change, no specs tree, no diff).
    Tokens: a requirement is covered when a hunk's changed lines carry
    at least two of its significant terms — one shared word is a
    coincidence, two is a trace."""
    if not (base and head and specs_dir and specs_dir.is_dir()):
        return None
    requirements: list[dict] = []
    for spec in sorted(specs_dir.glob("*/spec.md")):
        body = spec.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^#{3,4}\s*Requirement:\s*(.+)$",
                             body, flags=re.M):
            title = m.group(1).strip()
            requirements.append({
                "title": title,
                "spec": spec.parent.name,
                # the title is the requirement's identity — body prose
                # only dilutes the trace with incidental vocabulary
                "tokens": _requirement_tokens(title)})
    if not requirements:
        return None
    diff = git(repo, "diff", base, head, "--unified=3") or ""
    hunks: list[dict] = []
    current_file = None
    current_lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            if current_file and current_lines:
                hunks.append({"file": current_file,
                              "lines": "\n".join(current_lines)})
            current_file, current_lines = line[6:], []
        elif line.startswith(("+", "-")) and not line.startswith(
                ("+++", "---")):
            current_lines.append(line)
    if current_file and current_lines:
        hunks.append({"file": current_file,
                      "lines": "\n".join(current_lines)})
    matrix: list[dict] = []
    covered_hunks: set[int] = set()
    orphan_requirements: list[str] = []
    hunk_words = [set(re.findall(r"[a-z]{4,}", h["lines"].lower()))
                  for h in hunks]

    def _hits(tokens: set[str], words: set[str]) -> set[str]:
        # exact word, or a shared 6-char prefix (checkpointing /
        # checkpoint) — one shared word is a coincidence, the trace
        # needs at least two
        return {t for t in tokens
                if any(t == w or (len(t) >= 6 and len(w) >= 6
                                  and t[:6] == w[:6])
                       for w in words)}

    for req in requirements:
        hits = []
        for i in range(len(hunks)):
            overlap = _hits(req["tokens"], hunk_words[i])
            if len(overlap) >= 2 or (len(req["tokens"]) == 1
                                     and overlap):
                hits.append({"file": hunks[i]["file"],
                             "matched": sorted(overlap)[:6]})
                covered_hunks.add(i)
        matrix.append({"requirement": req["title"],
                       "spec": req["spec"],
                       "hunks": hits})
        if not hits:
            orphan_requirements.append(req["title"])
    orphan_hunks = [{"file": hunks[i]["file"]}
                    for i in range(len(hunks)) if i not in covered_hunks]
    return {"requirements": len(requirements),
            "hunks": len(hunks),
            "matrix": matrix,
            "orphan_requirements": orphan_requirements,
            "orphan_hunks": orphan_hunks,
            "note": ("token-trace alignment, visible information — "
                     "an orphan requirement is a spec promise the diff "
                     "does not show; an orphan hunk answers to no "
                     "requirement (infrastructure, or scope creep — "
                     "the human reads which)")}


# ── P2-1 (stall watch + nudge — ported from OpenBot stall-guard.ts):
# the clock is kept by the frames, not the wall — a dispatch is quiet
# when its own evidence has produced no new frame for the timeout, and
# quiet is judged from the last frame's timestamp alone (content is
# never parsed: a watchdog that can misread a working run into a
# broken one is worse than no watchdog). A suspected stall lands in
# the task's EXISTING event stream — no new event vocabulary for any
# downstream to learn. The nudge surfaces merge gates that have been
# waiting on a person for over 48h.
STALL_TIMEOUT_S = int(os.environ.get("AI_DLC_STALL_TIMEOUT", "300"))
NUDGE_AFTER_HOURS = 48


def cmd_stallguard(task_dir: Path, timeout: int) -> int:
    """One pass over the task's dispatch evidence: for every evidence
    jsonl, the last timestamped frame names how long the wire has been
    quiet; quiet past the timeout is recorded in the task's own event
    stream and reported. Younger frames — or no evidence at all — are
    a normal answer, never an error."""
    now = time.time()
    findings = []
    ev_dir = task_dir / "evidence"
    if ev_dir.is_dir():
        for ev in sorted(ev_dir.glob("plan-*.jsonl")):
            last_ts = None
            try:
                with ev.open("rb") as fh:
                    fh.seek(0, os.SEEK_END)
                    size = fh.tell()
                    fh.seek(max(0, size - 65536))
                    tail = fh.read().decode("utf-8", errors="replace")
                for line in tail.splitlines():
                    try:
                        ts = json.loads(line).get("timestamp")
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if isinstance(ts, (int, float)):
                        last_ts = float(ts)
            except OSError:
                continue
            if last_ts is None:
                continue   # no timestamped frame: not this guard's fact
            quiet = now - last_ts
            if quiet > timeout:
                findings.append({"evidence": ev.name,
                                 "quiet_seconds": round(quiet, 1)})
    if findings:
        event(task_dir, event="STALL_SUSPECTED", timeout=timeout,
              findings=findings)
    print(json.dumps({"task_dir": str(task_dir), "timeout": timeout,
                      "suspected": findings,
                      "note": ("the clock is the frames' — quiet past "
                               "the timeout is named here and in the "
                               "task's event stream; content is never "
                               "parsed")}, indent=2, ensure_ascii=False))
    return 0


def cmd_nudge(root: Path, hours: int) -> int:
    """Merge gates waiting on a person longer than the threshold are
    surfaced — a gate nobody answers is work nobody can see waiting."""
    waiting = []
    for st_path in sorted(root.glob(".ai-dlc/tasks/*/state.json")):
        st = load_json(st_path, {})
        if st.get("stage") != "MERGE_GATE":
            continue
        if load_json(st_path.parent / "gates"
                     / "gate-merge.answer.json", {}):
            continue                      # answered — not waiting
        requested = load_json(st_path.parent / "gates"
                              / "gate-merge.request.json",
                              {}).get("requested_at")
        try:
            dt = datetime.fromisoformat(
                str(requested).replace("Z", "+00:00"))
            age_h = ((datetime.now(timezone.utc) - dt)
                     .total_seconds() / 3600)
        except (TypeError, ValueError):
            continue                      # no readable request time
        if age_h > hours:
            waiting.append({"task": st.get("task_id"),
                            "dir": str(st_path.parent),
                            "waiting_hours": round(age_h, 1)})
            event(st_path.parent, event="MERGE_GATE_NUDGED",
                  waiting_hours=round(age_h, 1))
    print(json.dumps({"root": str(root), "after_hours": hours,
                      "nudged": waiting}, indent=2, ensure_ascii=False))
    return 0


# ── P2-3 (dispatch-doctor): the tool-description repair loop,
# deterministic half. The measured failure this closes: a cold session
# spent 1m56s invoking --help five times because the interface was not
# copy-paste ready — Anthropic's tool-testing finding says rewriting
# unclear tool descriptions cut later agents' task completion time 40
# percent. The loop: measure the fumbling in the session archives,
# emit revision suggestions for a human to review, fix, measure again
# — the count falling is the acceptance. Content is scanned only for
# command shapes (--help invocations, repeated commands); the
# conversation itself is never read.
DISPATCH_DOCTOR_HELP_RE = re.compile(r"([\w./-]+)\s+--help")
DISPATCH_DOCTOR_CMD_RE = re.compile(r'"command":\s*"([^"]+)"')


def cmd_dispatch_doctor(sessions: Path, write: Path | None,
                        limit: int) -> int:
    help_counts: dict[str, int] = {}
    repeat_counts: dict[str, int] = {}
    files = sorted(sessions.glob("*/history.jsonl"))[-max(1, limit):]
    for hf in files:
        try:
            text = hf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in DISPATCH_DOCTOR_HELP_RE.finditer(text):
            tool = m.group(1).rstrip("/").split("/")[-1]
            help_counts[tool] = help_counts.get(tool, 0) + 1
        per_file: dict[str, int] = {}
        for m in DISPATCH_DOCTOR_CMD_RE.finditer(text):
            per_file[m.group(1)] = per_file.get(m.group(1), 0) + 1
        for cmd, n in per_file.items():
            if n >= 3:
                repeat_counts[cmd] = repeat_counts.get(cmd, 0) + n
    suggestions = []
    for tool, n in sorted(help_counts.items(), key=lambda kv: -kv[1]):
        if n >= 2:
            suggestions.append({
                "tool": tool, "help_invocations": n,
                "suggestion": ("the interface was explored with --help "
                               "%d times — put a copy-paste usage "
                               "example in its L0 surface or help text; "
                               "a ready command needs no exploring" % n)})
    for cmd, n in sorted(repeat_counts.items(),
                         key=lambda kv: -kv[1])[:10]:
        suggestions.append({
            "command": cmd, "repetitions": n,
            "suggestion": ("the same command ran %d times — a retry "
                           "loop smell: either it fails confusingly or "
                           "its description invites re-running; name "
                           "the failure mode in its description" % n)})
    out = {"sessions_root": str(sessions), "files_scanned": len(files),
           "help_fumbling": help_counts,
           "repeated_commands": repeat_counts,
           "suggestions": suggestions,
           "note": ("measure -> human-reviewed description fix -> "
                    "measure again; the count falling is the loop's "
                    "acceptance (Anthropic: -40 percent completion "
                    "time from description fixes alone)")}
    if write:
        write.parent.mkdir(parents=True, exist_ok=True)
        write.write_text(json.dumps(out, indent=2, ensure_ascii=False)
                         + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def design_residue(repo: Path) -> dict | None:
    """E1/S1.3 — uncommitted design/ files in the working tree. The
    chile-tourism-site baseline ended with generation-two design/ files
    sitting uncommitted in the main tree while the branch carried
    generation one — invisible until someone diffed. Reported in the
    delivery report; never a gate."""
    r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain",
                        "--", "design/"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    paths = [line[3:].strip() for line in r.stdout.splitlines()
             if line.strip()]
    if not paths:
        return None
    return {"paths": paths[:20], "count": len(paths),
            "why": ("uncommitted design/ files in the working tree — the "
                    "delivery may carry a design generation the task "
                    "branch does not; commit or remove them before the "
                    "merge gate reads the diff")}


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _collect_intervals(node, out: list) -> None:
    """Every dict carrying started_at/ended_at (or elapsed_seconds alone)
    contributes one interval — planning.json nests dispatches, reviews
    and design runs at different depths, and all of them are plane
    work."""
    if isinstance(node, dict):
        start = _parse_ts(node.get("started_at"))
        end = _parse_ts(node.get("ended_at"))
        if start and end and end >= start:
            out.append((start, end))
        elif isinstance(node.get("elapsed_seconds"), (int, float)):
            out.append((None, float(node["elapsed_seconds"])))
        for v in node.values():
            _collect_intervals(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_intervals(v, out)


def cycle_time(planning: dict) -> dict:
    """E2/S2.4 — busy/wall/waiting from the planning record. busy is the
    UNION of dispatch intervals (concurrent reviewers are not counted
    twice); timed intervals without timestamps fall back to a summed
    floor. waiting = wall - busy, which is mostly time standing before
    a person. Honest on empty records: zeros, never guesses."""
    intervals: list = []
    _collect_intervals(planning, intervals)
    spanned = [(s, e) for s, e in intervals if s is not None]
    floor = sum(e for s, e in intervals if s is None)
    busy = floor
    if spanned:
        spanned.sort()
        merged: list = []
        for s, e in spanned:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        busy += sum((e - s).total_seconds() for s, e in merged)
        wall = (max(e for _s, e in spanned)
                - min(s for s, _e in spanned)).total_seconds()
    else:
        wall = 0.0
    return {"plane_busy_s": round(busy, 1),
            "wall_s": round(wall, 1),
            "waiting_s": round(max(wall - busy, 0.0), 1),
            "dispatches_timed": len(intervals),
            "note": ("busy is the union of dispatch intervals; waiting is "
                     "mostly time before a human — it is not waste to "
                     "optimize away")}


def cmd_deliver(task_dir: Path, repo: Path, outcome: str,
                no_design: bool = False,
                no_design_by: str | None = None,
                no_design_why: str | None = None,
                no_exec_gate: bool = False,
                no_exec_gate_by: str | None = None,
                no_exec_gate_why: str | None = None,
                redesign: bool = False) -> int:
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
    # P0-4: --no-exec-gate carries the same contract as --no-design —
    # a named human and a reason; a model may not self-sign a skip.
    exec_gate_skipper: str | None = None
    if no_exec_gate:
        exec_gate_skipper = stated_actor(no_exec_gate_by,
                                         "the execution-gate skip's author")
        if exec_gate_skipper is None:
            return 1
        if not (no_exec_gate_why or "").strip():
            print("refusing: --no-exec-gate requires --no-exec-gate-why — "
                  "a skip without a reason is the silence this check "
                  "exists to end", file=sys.stderr)
            return 1
        _pl = load_json(task_dir / "planning.json", {})
        _pl["exec_gate_decision"] = {"skip": True,
                                     "decided_by": exec_gate_skipper,
                                     "why": no_exec_gate_why.strip(),
                                     "source": "deliver --no-exec-gate",
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
    # 01-notes-cli finding: the gate reader sees the effort tier where
    # the exec gate and alignment already stand — the tier the task
    # was run at is delivery information, not just init chatter
    rep["tier"] = state.get("tier") or route_tier(state.get("route",
                                                              "inline"))
    # P1-10: the spec↔diff alignment, both directions of orphan named
    # — visible information for the human at the gate, never a gate
    _align_specs = None
    if state.get("change_id"):
        _cand = (plane_root(repo) / "openspec" / "changes"
                 / state["change_id"] / "specs")
        _align_specs = _cand if _cand.is_dir() else None
    rep["alignment"] = spec_alignment(repo, base, head, _align_specs)
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
                                                   files, head=head,
                                                   redesign=redesign)
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
    # P0-4 (execution gate): the repo's own toolchain gets a vote. The
    # verdict is a third machine fact next to spec validity and the
    # landed diff; results persist to the task dir before the report is
    # finalised, and the event stream carries the per-tool states.
    if no_exec_gate:
        rep["execution_gate"] = {"state": "skipped",
                                 "skipped_by": exec_gate_skipper,
                                 "why": (no_exec_gate_why or "").strip()}
    else:
        rep["execution_gate"] = run_execution_gate(repo, files, base)
        save_json(task_dir / "execution-gate.json",
                  {**rep["execution_gate"], "measured_ref": measured_ref,
                   "base_sha": base, "ts": now_iso()})
        event(task_dir, event="EXECUTION_GATE",
              state=rep["execution_gate"]["state"],
              tools={t["name"]: t["status"]
                     for t in rep["execution_gate"]["tools"]})
    # E1/S1.3 — design residue is reported, never silently left: an
    # uncommitted design/ tree in the main working tree is how the
    # chile-tourism-site run ended up with two diverging generations
    # (the branch followed one, the working tree carried the other).
    residue = design_residue(repo)
    if residue:
        rep["design_residue"] = residue
    # E2/S2.4 — cycle time from the planning record's own dispatch
    # intervals: how long the plane was busy, how long the task stood
    # overall, and the difference, which is mostly time waiting on a
    # person. Reported, never gated.

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
                     and merge_approved
                     and rep["execution_gate"].get("state") != "fail")
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
    elif rep["execution_gate"].get("state") == "fail":
        # P0-4: executability is a gate, not advice — a failing tool is
        # named before the unanswered merge gate, because a human asked
        # to approve a merge deserves to know the code failed its own
        # toolchain first.
        outcome = "exec_gate_failed"
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
                             "execution gate (the repo's own tests/lint/"
                             "typecheck — executability, not correctness; "
                             "green is necessary, never sufficient)",
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
                   help="why the design round is skipped — required with "
                        "--no-design")
    p.add_argument("--redesign", action="store_true",
                   help="E1: force a full D0+D1 design dispatch even when "
                        "a design spec stands — the human-triggered path "
                        "to a D1 rewrite; without it deliver only "
                        "re-verifies (D3) over a standing spec")
    p.add_argument("--no-exec-gate", action="store_true",
                   dest="no_exec_gate",
                   help="skip the execution gate even when toolchains are "
                        "present (the skip is reported, never silent)")
    p.add_argument("--no-exec-gate-by", default=None,
                   dest="no_exec_gate_by",
                   help="who skips the execution gate — required with "
                        "--no-exec-gate, must be a named human")
    p.add_argument("--no-exec-gate-why", default=None,
                   dest="no_exec_gate_why",
                   help="why the execution gate is skipped — required "
                        "with --no-exec-gate")
    p = sub.add_parser("dispatch-doctor")
    p.add_argument("--sessions", type=Path,
                   default=Path.home() / ".jiuwenswarm" / "agent"
                   / "sessions",
                   help="the session archives to replay (P2-3)")
    p.add_argument("--write", default=None, type=Path,
                   help="also write the suggestions JSON for human "
                        "review")
    p.add_argument("--limit", type=int, default=50,
                   help="the newest N session archives to scan")
    p = sub.add_parser("stallguard")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--timeout", type=int, default=STALL_TIMEOUT_S,
                   help="seconds of frame quiet before a dispatch is "
                        "suspected (default from AI_DLC_STALL_TIMEOUT)")
    p = sub.add_parser("nudge")
    p.add_argument("--root", default=".", type=Path,
                   help="the repo whose .ai-dlc/tasks to scan")
    p.add_argument("--hours", type=int, default=NUDGE_AFTER_HOURS,
                   help="waiting threshold in hours (default 48)")
    p = sub.add_parser("patterns")
    p.add_argument("--task-dir", required=True, type=Path,
                   help="aggregate decision patterns over one task's "
                        "records (P1-4)")
    p = sub.add_parser("checkpoint")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--label", default=None,
                   help="what this turn did — recorded with the "
                        "checkpoint")
    p.add_argument("--list", action="store_true", dest="list_cps",
                   help="list the checkpoints on record")
    p.add_argument("--show", type=int, default=None, dest="show_seq",
                   help="show a checkpoint's diff against the previous")
    p.add_argument("--restore", type=int, default=None,
                   dest="restore_seq",
                   help="restore the worktree to a checkpoint "
                        "(stash-or-abort guard on a dirty tree)")
    p.add_argument("--stash-first", action="store_true",
                   help="with --restore: stash a dirty tree first "
                        "(named and recorded) instead of aborting")
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
    if args.cmd == "checkpoint":
        sys.exit(cmd_checkpoint(args.task_dir, args.repo, args.label,
                                args.list_cps, args.show_seq,
                                args.restore_seq, args.stash_first))
    if args.cmd == "patterns":
        sys.exit(cmd_patterns(args.task_dir))
    if args.cmd == "dispatch-doctor":
        sys.exit(cmd_dispatch_doctor(args.sessions, args.write,
                                     args.limit))
    if args.cmd == "stallguard":
        sys.exit(cmd_stallguard(args.task_dir, args.timeout))
    if args.cmd == "nudge":
        sys.exit(cmd_nudge(args.root.resolve(), args.hours))
    if args.cmd == "deliver":
        sys.exit(cmd_deliver(args.task_dir, args.repo, args.outcome,
                             args.no_design, args.no_design_by,
                             args.no_design_why,
                             no_exec_gate=args.no_exec_gate,
                             no_exec_gate_by=args.no_exec_gate_by,
                             no_exec_gate_why=args.no_exec_gate_why,
                             redesign=args.redesign))
    ap.error(f"unhandled {args.cmd}")


if __name__ == "__main__":
    main()
