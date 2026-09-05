#!/usr/bin/env python3
"""bin/plan — the planning dispatch (devteam D3)

Roles are read from the change's recorded artifact graph; a role prompt
is assembled from the upstream instruction verbatim (never a hand-written
format guide); dispatch goes through the shipped gateway client and is
judged from its event frames — the final envelope never decides alone.
openspec is never executed here: the artifact graph, the artifact states
and every validator verdict arrive as signed records the plane produced
(containment PRD). Nothing here judges whether an artifact is good:
acceptance reads the plane's verdict record and returns its text
verbatim to the role that owns the failing artifact.

Subcommands:
  roles     read the artifact list and its dependencies from the signed
            graph record, emit the role set, what is dispatchable now,
            and the planning-phase completeness — the plane's own
            verdict, so an incomplete phase is never called complete
  prompt    assemble a role prompt: handoff package, operational clauses,
            the artifact identity and write boundary, the instruction to
            obtain the authoring guidance from the CLI through the
            authoring skill (the guidance itself is NOT copied in), the
            language context
  dispatch  run the shipped client with the event stream enabled and the
            repository as working directory; judge the frames; scan the
            frames for what the role DID (the author is not the judge:
            a validator invocation fails the dispatch, and so does a
            command that removes or rewrites a path the pre-dispatch
            baseline carries); run the boundary check. Before any of
            that, the authoring skill is verified installed and
            registered (the role fetches its own guidance through it),
            and the target is admitted:
            a tree holding source of a dependency this project may never
            modify is refused outright (exit 12, the paths named), and a
            working tree that shows fewer files than its head commit —
            a sparse or partial checkout — is reported and waits for a
            human to accept the narrower view (--accept-partial-view
            records the acceptance). A role whose artifact openspec
            already reports done is skipped and recorded, never
            re-paid — unless
            a validator rejection is pending on that role, in which case
            the revision dispatch runs. Each attempt lands in
            planning.json (session, attempt count, frame verdict, start,
            end, elapsed seconds beside the outcome) so a resume knows
            what was reached, and the deterministic session
            name means a re-dispatch continues that session — reuse is
            the client's contract for a named session. --frames-file
            judges an offline frame file instead (test hook: no client,
            no live plane)
  phase     run the planning phase end to end: every role the artifact
            graph reports dispatchable at the same moment dispatches —
            up to --concurrency at a time, each in its own session with
            its own frame file and boundary baseline; a failure stops
            new dispatches, the ones running finish, every outcome is
            reported before the phase stops. The phase record carries
            each role's duration, the sum of the role durations and the
            wall-clock span, so a serial phase (--concurrency 1, the
            baseline) is visibly different from a concurrent one. An
            artifact the upstream instruction makes conditional needs a
            recorded decision before anything dispatches
  decide    record a person's decision on an artifact the upstream
            instruction makes conditional: the condition that applies
            (in the instruction's own wording) or why none does. The
            phase runner reads it before dispatching; neither way is
            ever assumed
  review    the adversarial design-review round: one reviewer per
            chosen axis from the named list in the configuration, each
            dispatched exactly like an artifact role (own session, own
            frame file, own boundary baseline) and each writing exactly
            one finding to its own path under the task record — a
            second finding, a write outside its own path, or silence
            in place of an explicit nothing-found fails the dispatch.
            The caller then synthesises the findings itself (no
            session is opened for it): groups by where in the design
            each lands, every opposing pair named, every concern
            citing its finding — an uncited concern, an omitted
            finding or a passage that picks a side fails the round.
            The author is then dispatched once more with every finding
            and the synthesis alongside, and answers each finding on
            the record; an unanswered finding blocks the phase from
            reporting complete, and nothing else: a finding is advice
            and never a delivery criterion. Team mode is refused with
            the three recorded reasons
  boundary  standalone product-surface check judged against a baseline:
            the first call records the tree's pre-existing uncommitted
            state (a dirty tree is the caller's, never a role's leak);
            later calls judge only the increment since that baseline —
            new paths must sit inside the change dir or the three
            gateway bookkeeping dirs (.agent_history/, coding_memory/,
            prompt_attachment/). dispatch snapshots its own baseline
            before every run and judges the same increment
  accept    run strict validation; on failure exit non-zero with the
            validator output verbatim, the owning artifact and a revision
            prompt (and record the pending revision, so the artifact's
            existence never reads as done to a later dispatch); on
            success guard against unbidden requirement and scenario
            count drift, then report the phase gate and record skipped
            optional artifacts with their reasons
  close     the tail: read the merge-gate answer; without an approval
            carrying a rationale do nothing and report waiting on a
            person. With one — merge the task branch into the target
            branch (a no-op report when the work already landed without
            a branch), archive the change through the upstream archive
            command (its failure output carried verbatim, the close
            stops), close the task record with the state that follows
            delivery, then remove the task worktree and branch the run
            created (or record their retention with --keep-task-branch)
  sweep     the run leaves the target as it found it: judged against the
            earliest pre-boundary baseline, what the run introduced and
            did not deliver is removed, what the tree already carried
            is never touched (the skip recorded), the openspec/ tree
            stays for a person to commit unless --purge-openspec says
            the run was voided, and the task worktree and branch go
            once the branch is merged (an unmerged branch holds the
            only copy of the work, so it is retained with that reason).
            Without a baseline nothing is removed — sweep cannot tell
            the run's paths from the tree's own
  classify  the target's class, probed read and write separately through
            the gateway's own view of the path: writable, readable-only,
            or invisible. No prefix is trusted to guess it
  stage     a copy of the target inside the writable area — only for the
            invisible class; a readable target is refused with the split
            workspace named as the remedy and the size the copy would
            have cost
  snapshot  a tree's manifest, every file hashed and symlinks with their
            targets — the before/after proof a read-in-place round is
            judged against
  untouched compares a tree against a pre-round manifest byte-for-byte,
            gateway bookkeeping directories included
  migrate   N6, one time: move the repo's openspec tree into the plane's
            home (/var/lib/aidlc/specs/<repo-id>) — after this every
            round writes the plane's tree and reads the project, and
            the archive dispatch at close writes the tree back
  sandbox   the service unit's writable paths reported, a project tree
            among them flagged, and a drafted unit that widens them
            refused with the split workspace named as the remedy
  design    N1 (uidesigner): one fresh session over the change's
            measured frontend surface. The stops fire before any
            session opens — the pointer skill (25), the upstream pin
            (26), a surface with no web or deck file (24), a repo the
            plane cannot write. The record is written only when the
            frames carry all five facts: an upstream SKILL.md read,
            writes the filesystem confirms, every referenced asset
            resolving, pages rendering (200, non-empty DOM), no
            placeholder text. The role's conclusion sentence is never
            the evidence; deliver reports design_unverified without
            the record
  design-scope  the applicability measurement on its own: the change's
            product surface by extension class (web / deck) — a report,
            not a gate; `design` refuses on it
  design-pin write (--write) or verify the OpenDesign pin beside the
            tree — the install script calls here so the pin and the
            dispatch's check share one digest contract

Exit codes:
   0  ok. accept may still report is_planning_complete false — the phase
      gate is openspec's verdict, printed honestly, never asserted
   1  inconclusive: the frame stream carried neither a round-complete
      frame nor an interrupt frame, or a subprocess failed before a
      verdict existed, or a partial working-tree view is waiting for a
      human's acceptance, or sweep found no baseline to judge against
   2  usage error (argparse)
   3  handoff package rejected by shape: the requirement names a file
      count, a module count or a directory layout — rejected BEFORE any
      dispatch
   4  role rejected: it owns no artifact of the schema, or its
      dependencies are not done (a role never starts early)
   5  handoff package invalid: a key is missing or empty, a value has
      the wrong type, the repo path does not exist, or change_id does
      not match --change
   6  retired: the target's class is probed now (see classify); a path
      under the private temporary namespace stages a copy instead of
      being refused
   7  the run was interrupted and no responder exists headless; the
      JSON names the tool and its argument from the interrupt frame,
      and a final envelope claiming success is disregarded
   8  boundary violated: the product surface names paths outside the
      change dir and outside the gateway bookkeeping dirs, or a split
      round's frames show a write inside the project it may only read,
      or the project is not byte-for-byte as the round found it;
      nothing is cleaned up
   9  strict validation rejected the change; the validator output is
      returned verbatim to the owning artifact
  10  requirement or scenario counts drifted from the last accepted
      snapshot without --counts-approved
  11  close failed: the merge or the upstream archive command exited
      non-zero; its output is carried verbatim and nothing is reported
      as closed. A close still waiting on the human's merge-gate answer
      exits 1 with closed:false — waiting is a state, not an error
  12  forbidden target: the repository holds source of a dependency
      this project may never modify; the paths are named and the client
      was never invoked
  13  the author judged: the frames show the role ran the validator
      (openspec validate). The invocation is named and the artifact it
      produced is not accepted on that dispatch
  14  the frames show a command that removes or rewrites a path the
      pre-dispatch baseline carried; the command and the path are named
  15  the role reported it could not run the openspec CLI
      (OPENSPEC_CLI_UNAVAILABLE in its final message); the role's own
      account is carried — the failure is never worked around by
      supplying the guidance in the prompt
  16  the authoring skill is not installed or not registered in the
      gateway workspace; the dispatch is refused before the client
      exists, with the remedy
  17  the assembled prompt carries a clause naming a constraint the
      runtime no longer imposes (the surface audit); the clause is named
  20  workspace contract violated: a split dispatch refused before the
      client existed (a grant missing, a copy not self-contained), a
      readable target someone tried to copy, or a return carrying
      anything but the change directory; the remedy is named, never
      applied
  21  sandbox widening refused: a drafted unit file adds a writable
      path; the split workspace is named as the remedy and nothing is
      applied or restarted
  22  a signed plane record is missing or does not verify — the graph,
      a validate verdict, or a verdict that predates the newest
      artifact write. The caller runs no spec tool to fill the gap;
      the remedy names the dispatch that produces the record
  23  a validate dispatch whose event frames carry no normalized
      validator call — there is no verdict to read, and none is
      invented
  24  the change's measured product surface carries no web or deck
      file — the design dispatch refused before a session opened; the
      measured surface travels in the refusal
  25  the ui-designer pointer skill is not installed or not registered
      in the gateway workspace; refused with the remedy, nothing
      installs itself
  26  the OpenDesign pin is missing, or the tree's measured digest
      moved off it; the upstream reference cannot back a record until
      it is restored or deliberately re-pinned
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import ast
import hashlib
import grp
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import html.parser
import http.server
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import (RECORDS_ROOT, artifacts_view, codegraph_auto_dispatch,  # noqa: E402
                    codegraph_auto_due, codegraph_surface,
                    design_surface, cmd_next, event, excluded, human_state,
                    is_git_repo, load_json, newest_verdict, now_iso,
                    plane_graph, plane_root, plane_status, plane_tree,
                    save_json, signed_records, write_record)
from initiative import (  # noqa: E402
    cmd_advance as init_advance, cmd_register as init_register,
    cmd_status as init_status,
    _find_manifest_for_change as init_find_manifest)

# the shipped gateway client; AI_DLC_CLIENT overrides the path only (an
# alternate install, or a double standing in for it — the flags are the
# contract either way)
CLIENT = os.environ.get("AI_DLC_CLIENT",
                        os.path.expanduser("~/.local/bin/jiuwenswarm"))
# the pinned Understand-Anything skill tree (C1/C2).  This is a pure
# prompt/skill tree — no compiled binary, no glibc dependency — installed
# by scripts/install-understand-anything.sh to /opt/understand-anything.
# The pin (.aidlc-pin.json) records tag + tree_sha256; the codegraph
# build/brief commands dispatch sessions that read the skill files, not
# subprocess calls to a binary.  AI_DLC_UNDERSTAND_ANYTHING_ROOT overrides
# the path only (an alternate install).
UNDERSTAND_ANYTHING_ROOT = Path(os.environ.get(
    "AI_DLC_UNDERSTAND_ANYTHING_ROOT", "/opt/understand-anything"))
UNDERSTAND_ANYTHING_PATHS = ("understand-anything-plugin",)
GATEWAY_BOOKKEEPING = (".agent_history", "coding_memory", "prompt_attachment")
INTERRUPT_EVENTS = ("chat.ask_user_question", "plan.approval_required")
# the authoring skill the role reaches the CLI through, and where the
# gateway workspace keeps it (AI_DLC_SKILLS_DIR overrides the location
# only — the installed-and-registered contract is the same either way)
AUTHORING_SKILL = "openspec-author"
SKILLS_DIR = os.environ.get("AI_DLC_SKILLS_DIR",
                            os.path.expanduser("~/.jiuwenswarm/agent/workspace/skills"))
# the role's structured report that it could not run the CLI: the last
# line of its final message. The dispatch fails on it carrying the
# role's own account — never worked around by embedding the guidance
CLI_UNAVAILABLE_MARKER = "OPENSPEC_CLI_UNAVAILABLE:"
# no budget key: budgeting is not provided upstream, and no figure is
# computed, capped or reported here (landing L1)
PACKAGE_KEYS = ("requirement", "change_id", "capability", "repo")
ARTIFACT_BASENAMES = {"proposal.md": "proposal", "design.md": "design",
                      "tasks.md": "tasks"}

EXIT_INCONCLUSIVE = 1
EXIT_SHAPE_REJECTED = 3
EXIT_ROLE_REJECTED = 4
EXIT_PACKAGE_INVALID = 5
# 6 was EXIT_REPO_INVISIBLE — retired by any-directory: a target the
# gateway cannot see is no longer refused, it is staged as a copy
EXIT_INTERRUPTED = 7
EXIT_BOUNDARY = 8
EXIT_VALIDATOR_REJECTED = 9
EXIT_COUNT_DRIFT = 10
EXIT_CLOSE_FAILED = 11
EXIT_FORBIDDEN_TARGET = 12
EXIT_AUTHOR_JUDGED = 13
EXIT_BASELINE_DESTRUCTIVE = 14
EXIT_CLI_UNAVAILABLE = 15
EXIT_SKILL_MISSING = 16
EXIT_PROMPT_SURFACE = 17
EXIT_WORKSPACE = 20            # the split-workspace or staging contract is
                               # violated: a missing trusted-location grant,
                               # a refused copy of a readable target, or a
                               # staged copy that is not self-contained
EXIT_SANDBOX_WIDENING = 21     # a change would widen the service sandbox
# the design role's own stops (uidesigner-opendesign): each fires
# BEFORE any session opens — a dispatch that cannot honestly run never
# bills one
EXIT_DESIGN_SURFACE = 24       # the measured product surface carries no
                               # web or deck file — a backend change
                               # buys no beautifying
EXIT_DESIGN_SKILL = 25         # the ui-designer pointer skill is absent
                               # or unregistered; nothing self-installs
EXIT_DESIGN_PIN = 26           # the upstream pin is missing or the
                               # tree's digest moved off it


def emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return code


def run(cmd: list, cwd=None, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                          timeout=timeout)


def git_run(args: list, repo: Path, cwd=None,
            timeout=None) -> subprocess.CompletedProcess:
    """Like run(["git", "-C", str(repo)] + args), but always scopes a
    per-invocation safe.directory override to exactly this path — never
    written to any config file, never affecting any call outside this one
    subprocess. Exists because plane_root() paths are chowned to a
    different uid (swarm) than the caller's own, which trips git's
    dubious-ownership refusal; this is git's own documented answer to
    that scenario, applied narrowly (INV-31/INV-32)."""
    return run(["git", "-c", f"safe.directory={repo}", "-C", str(repo)]
               + args, cwd=cwd, timeout=timeout)


# ── the plane's records: the only spec surface the caller reads ─────
#
# openspec is never executed caller-side (containment §1, invariant
# I1): the artifact graph, the artifact statuses and every validator
# verdict arrive as records the plane produced and signed. The reading
# and signing layer lives in bin/report.py — shared with the delivery
# surface — and a record that is missing or wrongly signed is reported
# as exactly that: never recomputed here, never substituted with a
# caller-side CLI run.

# the validator invocation a validate dispatch must show verbatim in its
# frames: an absolute path and a normalized literal, no shell
# metacharacters — anything else in the frame is not a verdict source
NORMALIZED_VALIDATE_BIN = "/usr/local/bin/openspec"

# the account the plane's own state belongs to (the ownership G4/G5/G6
# lean on; the service writes as root today and the per-file rule
# tightens when the caller's shell stops being root — P4)
PLANE_USER = "swarm"
PLANE_GROUP = "swarm"

# 22 a signed record is missing or its signature does not verify;
# 23 a plane tool dispatch (validate/graph/status) whose frames carry
#    no normalized call for a command it owed — the validate case is
#    PRD §8's; graph and status fail the same way for the same reason
EXIT_RECORD_MISSING = 22
EXIT_NO_NORMALIZED_CALL = 23


def stale_against(change: str, verdict: dict, repo: Path) -> list:
    """Artifact files written after the verdict's timestamp: that
    verdict speaks of a tree that no longer stands, and accept does
    not judge with it. The tree is the plane's own (N6) — the paths
    reported are relative to the plane root. The stamp is UTC and
    truncated to the second, so a file inside the verdict's own second
    is NOT stale — the ambiguity of one second resolves toward
    trusting the verdict."""
    ts = str(verdict.get("ts") or "")
    try:
        vt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return ["<the verdict record carries no parseable ts>"]
    root = plane_root(Path(repo))
    tree = root / "openspec" / "changes" / change
    if not tree.is_dir():
        return []
    return [f"openspec/changes/{change}/{p.relative_to(tree)}"
            for p in sorted(tree.rglob("*"))
            if p.is_file() and p.stat().st_mtime > vt + 1]


def missing_record_stop(change: str, needs: list[str],
                        remedy: str) -> None:
    sys.exit(emit({"change": change, "stopped": "caller runs no spec "
                                              "tool — a record is missing",
                   "needs": needs,
                   "records_root": str(RECORDS_ROOT),
                   "why": ("the spec surface is read from signed plane "
                           "records; the caller never executes openspec "
                           "to fill a gap"),
                   "remedy": remedy}, EXIT_RECORD_MISSING))


def default_task_dir(repo: Path, change: str) -> Path:
    return repo / ".ai-dlc" / "tasks" / f"{change}-planning"


def planning_path(task_dir: Path) -> Path:
    return task_dir / "planning.json"


# concurrent role dispatches in one phase mutate the same planning.json;
# every load-modify-save goes through this lock so a record one role
# writes is never lost to another's save (dispatch-concurrency)
PLANNING_LOCK = threading.Lock()


def update_planning(task_dir: Path, mutate) -> dict:
    """Load, mutate and save planning.json under the lock. Returns the
    saved document."""
    with PLANNING_LOCK:
        p = load_json(planning_path(task_dir), {})
        mutate(p)
        save_json(planning_path(task_dir), p)
        return p


# ── roles ───────────────────────────────────────────────────────────

def cmd_roles(change: str, repo: Path) -> int:
    """The ONLY source of the role set: the artifact list the change's
    graph record carries. No role exists that owns no artifact, no
    verification role and no implementation role — none is invented
    here, and the schema is never queried caller-side."""
    graph = plane_graph(change)
    if graph is None:
        missing_record_stop(
            change, ["graph"],
            "produce the graph once with a graph dispatch "
            "(plan.py graph --change <id> --repo <repo>) — the artifact "
            "list, dependency edges and conditional conditions, signed")
    arts = artifacts_view(change)
    done = {a.get("id") for a in arts if a.get("status") == "done"}
    roles = [{"artifact": a.get("id"),
              "requires": list(a.get("requires", [])),
              "status": a.get("status"),
              "dispatchable": all(r in done for r in a.get("requires", []))}
             for a in arts]
    return emit({"schema": graph.get("schema"), "change": change,
                 "roles": roles,
                 "dispatchable_now": [r["artifact"] for r in roles
                                      if r["dispatchable"]
                                      and r["artifact"] not in done],
                 "is_planning_complete":
                     bool((plane_status(change) or {})
                          .get("is_planning_complete"))},
                0)


# ── the handoff package ─────────────────────────────────────────────

def load_package(path: Path, change: str) -> dict:
    def bad(why: str, key: str | None = None) -> None:
        sys.exit(emit({"rejected": "package", "why": why,
                       "missing_key": key}, EXIT_PACKAGE_INVALID))

    if not path.is_file():
        bad(f"package file not found: {path}")
    try:
        pkg = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        bad(f"package file unreadable: {exc}")
    if not isinstance(pkg, dict):
        bad("package is not a JSON object")
    for key in PACKAGE_KEYS:
        if key not in pkg or pkg[key] is None or pkg[key] == "":
            bad(f"package key missing or empty: {key}", key)
    if "budget" in pkg:
        bad("the package carries a budget key — budgeting is not provided "
            "upstream and no token figure is computed, capped or reported "
            "here; usage is read from the upstream records where they "
            "already live", "budget")
    if not isinstance(pkg["requirement"], str):
        bad("package key has the wrong type: requirement (str)", "requirement")
    if pkg["change_id"] != change:
        bad(f"package change_id {pkg['change_id']!r} does not match "
            f"--change {change!r}", "change_id")
    if not Path(str(pkg["repo"])).is_dir():
        bad(f"package repo is not a directory: {pkg['repo']}", "repo")
    return pkg


SHAPE_PATTERNS = (
    re.compile(r"\d+\s*个?\s*(?:files?|modules?|dirs?|directories)", re.I),
    re.compile(r"file count", re.I),
    re.compile(r"module count", re.I),
    re.compile(r"director(?:y structure|y layout)", re.I),
    re.compile(r"目录结构"),
    re.compile(r"文件数"),
    re.compile(r"模块数"),
)


def shape_violation(requirement: str) -> str | None:
    """A package naming a file count, a module count or a directory
    layout is rejected before dispatch — it states structure, not
    behaviour. Returns the offending phrase so the error names it."""
    for pat in SHAPE_PATTERNS:
        m = pat.search(requirement)
        if m:
            return m.group(0)
    return None


CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿"
                 r"一-鿿豈-﫿＀-￯]")


def detect_language(change_dir: Path, requirement: str) -> str:
    """Language context, detected from the change's existing artifacts:
    the proposal if one exists, else the requirement text itself."""
    text = requirement
    proposal = change_dir / "proposal.md"
    if proposal.is_file():
        text = proposal.read_text(encoding="utf-8", errors="replace")
    body = "".join(text.split())
    if body and len(CJK.findall(body)) / len(body) >= 0.3:
        return "Chinese"
    return "English"


def assemble_prompt(pkg: dict, role: str, language: str,
                    split: dict | None = None) -> str:
    """The prompt carries the handoff package, the artifact identity, the
    write boundary and the instruction to obtain the authoring guidance
    from the CLI. The guidance itself is NOT copied in: the role runs
    `openspec instructions` itself through the authoring skill — the
    caller stopped fetching on its behalf when the runtime opened.
    A split workspace (a target the plane reads but must not write)
    adds the one clause that makes reading in place work: the project's
    absolute path as the place to read, with the working directory —
    where every write belongs — named as separate from it."""
    sections = [
        "===== 1. HANDOFF PACKAGE =====",
        f"requirement (verbatim):\n{pkg['requirement']}",
        f"change_id: {pkg['change_id']}\ncapability: {pkg['capability']}\n"
        f"repo: {pkg['repo']}\n",
        "===== 2. OPERATIONAL CLAUSES =====",
        "- You write ONLY your own artifact, at the output path the CLI "
        "reports for it.\n"
        "- You obtain your authoring guidance yourself: run the openspec "
        f"CLI (`openspec instructions {role} --change {pkg['change_id']} "
        "--json`) through the openspec-author skill and follow the "
        "instruction, template and output path it reports. That guidance "
        "is deliberately NOT copied into this prompt.\n"
        f"- If you could not run the openspec CLI, do not improvise the "
        "artifact from memory: end your final message with a line reading "
        f"\"{CLI_UNAVAILABLE_MARKER} <your account of why>\" and stop.\n"
        "- You do NOT invoke the validator (`openspec validate`): the "
        "verdict comes from a separate validate dispatch through the "
        "plane — neither you nor the caller judges this change in this "
        "session, and a dispatch whose frames show you validating "
        "fails outright.\n"
        "- You do NOT write, remove or rewrite any file outside your own "
        "artifact path; files that existed before this dispatch stay "
        "untouched.\n"
        + (
            f"- Your working directory is the round's workspace "
            f"({split['workspace']}), and it is NOT the project. The "
            f"project you are planning against lives at {split['project']} "
            f"— read it there, by absolute path. Write nothing inside the "
            f"project: your artifact path is under your working directory, "
            f"and the project must come out of this round exactly as it "
            f"went in."
            if split else
            "- Your working directory is the repository root (the dispatch "
            "sets it)."
        ),
        "===== 3. YOUR ARTIFACT =====",
        f"artifact: {role}\n"
        f"write boundary: openspec/changes/{pkg['change_id']}/ — the CLI "
        "reports the exact output path for your artifact; write nothing "
        "outside that directory",
        "===== 4. LANGUAGE =====",
        f"Write your artifact in {language}.",
    ]
    return "\n\n".join(sections) + "\n"


# clauses that name a constraint the runtime no longer imposes. The
# permission engine being off, the shell is reachable and compound
# commands run; a prompt stating otherwise describes a retired runtime
RETIRED_PROMPT_PATTERNS = (
    (re.compile(r"bash tool as UNAVAILABLE|shell (?:is|runs) unavailable",
                re.I), "shell-unavailable clause"),
    (re.compile(r"native file tools", re.I),
     "native-tools-only restriction"),
    (re.compile(r"guard rejects compound commands|shell guard rejects",
                re.I), "guard-rejects-compound clause"),
    (re.compile(r"permission ask interrupts", re.I),
     "permission-ask-interrupts clause"),
)


def prompt_surface_audit(prompt: str) -> list[str]:
    """The labels of every retired-constraint clause the prompt carries.
    Prompt text describes the runtime that exists; a clause justified by
    a constraint the runtime no longer imposes does not survive it."""
    return [label for pat, label in RETIRED_PROMPT_PATTERNS
            if pat.search(prompt)]


def prepare(change: str, role: str, package_file: Path,
            workspace: dict | None = None):
    """Everything that must hold BEFORE any dispatch: a well-formed
    package, a shape the pipeline accepts, a role that owns an artifact
    whose dependencies are done, and a prompt whose surface names no
    retired constraint. Returns the assembled dispatch. The authoring
    instruction is NOT fetched here — the role fetches it itself.
    A workspace (the plane's tree under N6) is where the artifact
    graph and the language
    context are read: that is where this round's artifacts live."""
    pkg = load_package(package_file, change)
    phrase = shape_violation(pkg["requirement"])
    if phrase:
        sys.exit(emit({"rejected": "package",
                       "why": ("the requirement names a file count, a "
                               "module count or a directory layout — "
                               "structure, not behaviour; rejected before "
                               "any dispatch"),
                       "phrase": phrase}, EXIT_SHAPE_REJECTED))
    repo = Path(str(pkg["repo"])).resolve()
    tree = Path(workspace["path"]).resolve() if workspace else repo
    arts = artifacts_view(change)
    if not arts:
        missing_record_stop(
            change, ["graph"],
            "produce the graph once with a graph dispatch "
            "(plan.py graph --change <id> --repo <repo>) — preflight "
            "admits a role only against the recorded artifact graph")
    ids = [a.get("id") for a in arts]
    if role not in ids:
        sys.exit(emit({"rejected": role,
                       "why": "role owning no artifact rejected",
                       "graph_artifacts": ids}, EXIT_ROLE_REJECTED))
    done = {a.get("id") for a in arts if a.get("status") == "done"}
    missing = [d for a in arts if a.get("id") == role
               for d in a.get("requires", []) if d not in done]
    if missing:
        sys.exit(emit({"rejected": role,
                       "why": ("a role does not start before every "
                               "artifact it depends on is done"),
                       "dependencies_not_done": missing}, EXIT_ROLE_REJECTED))
    change_dir = tree / "openspec" / "changes" / change
    language = detect_language(change_dir, pkg["requirement"])
    split = None
    if workspace is not None:
        # every dispatch is a split round under N6: the write side is
        # the plane's tree, the read side is the project (or its staged
        # copy) — the class only decided which read side
        split = {"project": workspace["project"],
                 "workspace": workspace["path"]}
    prompt = assemble_prompt(pkg, role, language, split=split)
    retired = prompt_surface_audit(prompt)
    if retired:
        sys.exit(emit({"rejected": "prompt surface",
                       "why": ("the assembled prompt carries a clause "
                               "naming a constraint the runtime no longer "
                               "imposes; the clause is removed or restated "
                               "against the constraint that does apply"),
                       "retired_clauses": retired}, EXIT_PROMPT_SURFACE))
    return pkg, repo, prompt, language


def cmd_prompt(change: str, role: str, package_file: Path, mode: str) -> int:
    pkg, _repo, prompt, language = prepare(change, role, package_file)
    return emit({"artifact": role, "prompt": prompt, "language": language,
                 "prompt_bytes": len(prompt.encode("utf-8")),
                 "package": pkg, "mode": mode}, 0)


# ── judging the event frames ────────────────────────────────────────

def _pick(d: dict, keys) -> object:
    for k in keys:
        val = d.get(k)
        if val not in (None, "", [], {}):
            return val
    return None


def interrupt_tool_argument(event: str,
                            payload: dict) -> tuple[object, object]:
    """Name the tool and its argument from the interrupt frame payload.
    The payload shape varies by rail (permission, confirm, ask-user);
    every observed variant carries the tool somewhere in the payload or
    in its questions — fall back to the question text, which carries the
    substance of what was being approved."""
    tool = argument = None
    questions = payload.get("questions")
    sources = [payload]
    if isinstance(questions, list):
        sources += [q for q in questions if isinstance(q, dict)]
    for src in sources:
        if tool is None:
            tool = _pick(src, ("tool_name", "tool", "toolName"))
        if argument is None:
            argument = _pick(src, ("tool_args", "arguments", "args",
                                   "input", "command"))
    if tool is None:
        tool = _pick(payload, ("source", "interaction_type")) or event
    if argument is None:
        argument = _pick(payload, ("message", "question"))
        if argument is None and isinstance(questions, list) and questions:
            first = questions[0]
            if isinstance(first, dict):
                argument = _pick(first, ("question", "message"))
    return tool, argument


def judge_frames(lines: list) -> dict:
    """The outcome is judged from the event frames, never from the final
    envelope's claims. Round-complete is EITHER a chat.processing_status
    frame whose is_processing is false OR a genuine closing chat.final
    frame — measured on this host, successful rounds in code modes end
    at chat.final with no closing status frame at all (measured
    sessions carry zero processing_status frames), while
    interrupted rounds do emit the closing status. A keepalive
    chat.final is not a close. Only the frame's PRESENCE counts as
    termination; its payload (ok/status/content) is recorded, never
    trusted. An interrupt frame means no responder exists headless and
    outranks every completion signal."""
    v = {"round_complete": False, "interrupted": False, "tool": None,
         "argument": None, "events": {}, "final_envelope_seen": False,
         "final_envelope_claims_ok": False}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        ev = d.get("event") or d.get("type")
        payload = d.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if not ev:
            continue
        v["events"][ev] = v["events"].get(ev, 0) + 1
        if ev == "chat.processing_status" and \
                payload.get("is_processing") is False:
            v["round_complete"] = True
        elif ev in INTERRUPT_EVENTS and not v["interrupted"]:
            v["interrupted"] = True
            v["tool"], v["argument"] = interrupt_tool_argument(ev, payload)
        elif ev == "chat.final":
            v["final_envelope_seen"] = True
            v["final_envelope_claims_ok"] = bool(
                payload.get("ok") is True or payload.get("status") == "ok"
                or payload.get("content"))
            if payload.get("event_type") != "keepalive":
                v["round_complete"] = True
    return v


# ── what the role DID: reading the frames as a record, not a claim ───
#
# The author is not the judge. With the CLI reachable the prohibition is
# enforced by inspection of what the role ran, not by what it could
# reach: the frames of a dispatch are scanned for a validator invocation
# and for commands that remove or rewrite paths the pre-dispatch
# baseline carried.

VALIDATOR_RE = re.compile(r"\bopenspec\b[^;|&\n]*\bvalidate\b")

# bins whose operands are paths they remove or rewrite; the redirect
# regex catches > and >> targets (2>/dev/null is filtered by the
# device-file exclusion)
DESTRUCTIVE_BINS = ("rm", "rmdir", "unlink", "shred", "mv", "tee",
                    "truncate", "shred")
REDIRECT_TARGET_RE = re.compile(r"(?:\d)?>>?\s*([^\s;|&<>]+)")
SHELL_SPLIT_RE = re.compile(r"&&|\|\||;|\|")
DEV_FILES = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty",
             "/dev/zero")


def _tool_invocations(lines: list) -> list[dict]:
    """Every tool call the frames carry: (tool name, arguments, id). The
    arguments arrive as a JSON string in both observed frame shapes
    (chat.tool_call nests them under tool_call, chat.tool_update carries
    them flat); both are read so one shape alone cannot hide a call.
    Two frame encodings are supported: the plane's dispatch evidence
    (payload + event keys) and the openjiuwen session history
    (tool_call + event_type keys, flat at the root)."""
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        # Two frame shapes: plane evidence (payload/event) and
        # openjiuwen session history (flat/event_type).
        payload = d.get("payload")
        if isinstance(payload, dict):
            ev = d.get("event") or d.get("type")
        else:
            payload = d
            ev = d.get("event_type") or d.get("event") or d.get("type")
        if ev not in ("chat.tool_call", "chat.tool_update"):
            continue
        tc = payload.get("tool_call")
        if isinstance(tc, dict):
            name, args, cid = (tc.get("name"),
                               tc.get("arguments"), tc.get("tool_call_id"))
        else:
            name = payload.get("tool_name") or payload.get("toolName")
            args, cid = payload.get("arguments"), payload.get("tool_call_id")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                # a partial/unparsable arguments blob is NOT a command:
                # read as one, a write tool's whole page payload becomes
                # shell text and every ">word" in it a phantom write
                # target (measured live, ud1-web round 2) — only a
                # shell-shaped tool keeps the opaque-string reading
                n = (name or "").lower()
                args = ({"command": args} if any(k in n for k in
                        ("bash", "shell", "exec")) else {})
        out.append({"tool": name, "arguments": args if isinstance(args, dict)
                    else {}, "id": cid})
    return out


def frame_shell_commands(lines: list) -> list[dict]:
    """The shell commands the role ran, from any tool whose arguments
    carry a command (bash and the exec variants all do)."""
    cmds = []
    for call in _tool_invocations(lines):
        command = call["arguments"].get("command")
        if isinstance(command, str) and command.strip():
            cmds.append({"command": command, "tool": call["tool"],
                         "tool_call_id": call["id"]})
    return cmds


def _dedup_calls(calls: list[dict]) -> list[dict]:
    """One entry per invocation: the gateway reports the same tool call
    in two frame shapes (chat.tool_call and its chat.tool_update echo),
    and a reader of what the session RAN wants each command once."""
    seen: set = set()
    out = []
    for c in calls:
        key = (c.get("tool_call_id"), c.get("command"))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def validator_invocations(commands: list[dict]) -> list[dict]:
    """The commands that run the validator — the author judging its own
    output. `openspec validate` in any position of a command line counts,
    including behind npx or env; `openspec instructions` does not."""
    return [c for c in commands if VALIDATOR_RE.search(c["command"])]


# ── what a PLANE dispatch ran: the normalized literals and their results ──
#
# A validate, status or graph dispatch is one session whose only product
# is the commands it ran. The verdict is read from the frames' own
# record of those commands — the argv literal seen in a tool call, the
# rc and output read from the matching tool result — never from the
# model's conclusions (containment PRD §5: plan.py reads rc and stdout
# from the frames, not the result sentence). An author dispatch keeps
# the opposite rule: there the validator is the author's own judge and
# a violation (validator_invocations above).

# the rc the gateway's result repr carries on failure: its first line
RESULT_RC_RE = re.compile(r"^Exit code (\d+)\r?$")

# the shell wrappers the gateway's bash tools wrap a command in
COMMAND_WRAPPERS = ("sh", "bash")


def normalized_command_match(command: str, argv: list[str]) -> bool:
    """The command IS the argv literal: absolute path, no pipes, no
    redirects, no shell metacharacters — shlex recovers exactly the
    argv and nothing else. The one unwrapping allowed is the sh/bash -c
    '…' wrapper the shell tools add, judged by the same rule on the
    wrapped string. Anything else fails the match — that failure is the
    point of a normalized literal (containment §5.1)."""
    def exact(text: str) -> bool:
        try:
            return shlex.split(text) == argv
        except ValueError:
            return False

    if exact(command):
        return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) == 3 and tokens[0] in COMMAND_WRAPPERS \
            and tokens[1] == "-c":
        return exact(tokens[2])
    return False


def _result_repr_literals(result: str) -> tuple[str | None, str | None]:
    """Split the gateway's tool-result repr string — success=True
    data={'content': …} error=… — into its data literal and its
    trailing error literal, quote- and depth-aware: a bracket or an
    ' error=' INSIDE either literal must not cut the string at the
    wrong place. (None, None) when the string is another shape
    entirely; the success token is positional at the start and needs
    no scan."""
    data_at = None
    depth = 0
    quote = None
    i = 0
    while i < len(result):
        ch = result[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth = max(0, depth - 1)
        elif depth == 0:
            if data_at is None and result.startswith(" data=", i):
                data_at = i + len(" data=")
            elif data_at is not None \
                    and result.startswith(" error=", i):
                return result[data_at:i], result[i + len(" error="):]
        i += 1
    if data_at is not None:
        return result[data_at:], None
    return None, None


def parse_tool_result(result: object) -> dict:
    """rc and output from a chat.tool_result payload, as measured on
    this host (probe sessions aidlc-rc-probe / aidlc-rc2-probe): the
    gateway renders success=True with the stdout alone in
    data.content (error=None, rc 0), and success=False with
    'Exit code N\\n<stderr>\\n\\n<stdout>' in content — the rc on the
    first line, stderr and stdout split at the blank line the gateway
    puts between them. With stderr empty no blank line is inserted and
    the whole remainder is stdout. Nothing else in the frame is read."""
    out = {"success": None, "rc": None, "stdout": "", "stderr": "",
           "error": None, "raw": result}
    if not isinstance(result, str) or not result.startswith("success="):
        return out
    out["success"] = result.startswith("success=True")
    data_lit, error_lit = _result_repr_literals(result)
    content = ""
    if data_lit is not None:
        try:
            data = ast.literal_eval(data_lit)
        except (ValueError, SyntaxError):
            data = None
        if isinstance(data, dict):
            content = data.get("content")
            content = content if isinstance(content, str) else ""
    if error_lit is not None:
        try:
            err = ast.literal_eval(error_lit)
        except (ValueError, SyntaxError):
            err = None
        out["error"] = err if isinstance(err, str) else None
    if out["success"]:
        out["rc"] = 0
        out["stdout"] = content
        return out
    first, _, rest = content.partition("\n")
    m = RESULT_RC_RE.match(first)
    if m is None:
        # no rc line: the content is not the gateway's failure shape;
        # nothing may be guessed from it
        return out
    out["rc"] = int(m.group(1))
    if "\n\n" in rest:
        err, _, stdout = rest.partition("\n\n")
        out["stderr"], out["stdout"] = err, stdout
    else:
        out["stdout"] = rest
    return out


def tool_results(lines: list) -> dict:
    """Every chat.tool_result frame, keyed by its tool_call_id — the
    outcome of a command is joined to the command that produced it, not
    taken from whichever result frame happens to be last."""
    out: dict = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        payload = d.get("payload")
        if not isinstance(payload, dict):
            continue
        if (d.get("event") or d.get("type")) != "chat.tool_result":
            continue
        cid = payload.get("tool_call_id")
        if cid is None:
            continue
        out[cid] = parse_tool_result(payload.get("result"))
    return out


def normalized_calls(lines: list, argv: list[str]) -> list[dict]:
    """The calls whose command is exactly the argv literal, each joined
    to its parsed result — empty when the frames carry none, which is
    the exit-23 condition of a plane dispatch (N1)."""
    results = tool_results(lines)
    out = []
    for call in _dedup_calls(frame_shell_commands(lines)):
        if not normalized_command_match(call["command"], argv):
            continue
        out.append({"argv": argv, "command": call["command"],
                    "tool_call_id": call["tool_call_id"],
                    "result": results.get(call["tool_call_id"])})
    return out


_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _strip_heredocs(command: str) -> str:
    """A heredoc's body is payload, not commands: the redirect target
    the session really wrote lives on the introducing line (cat > page
    <<EOF), while the body's own markup — an attribute close, then
    text — reads as a redirect that never was. The bodies are dropped,
    every introducing line stays; a heredoc with no terminator keeps
    what follows its own line rather than swallowing the rest."""
    parts, pos = [], 0
    while True:
        m = _HEREDOC_RE.search(command, pos)
        if not m:
            parts.append(command[pos:])
            return "".join(parts)
        parts.append(command[pos:m.start()])
        marker = m.group(2)
        rest = command[m.end():]
        end = re.search(rf"^[ \t]*{marker}[ \t]*$", rest, re.M)
        if end:
            pos = m.end() + end.end()
        else:
            nl = rest.find("\n")
            pos = m.end() + (nl + 1 if nl >= 0 else len(rest))


_QUOTED_RE = re.compile(r"""(['"])(?:\\.|(?!\1).)*\1""")


def _strip_quoted_text(command: str) -> str:
    """Quoted-string payload is not a redirect: a grep pattern's > or
    a python -c snippet's > is not a file target. The contents are
    emptied (the quotes stay as markers) before _normalized_targets
    scans for > — measured live on country-a's 855s session, where
    r'</%s>'%tag and grep -oE "<title>[^<]*</title>" produced four
    phantom write candidates (F1)."""
    return _QUOTED_RE.sub(r'\1\1', command)


def _normalized_targets(command: str) -> list[str]:
    """The paths a shell command removes or rewrites, read generously:
    operands of the destructive bins plus > and >> targets. Over-capture
    is safe (a captured path nothing carries is never matched); under-
    capture is the accident, so flags' operands are taken liberally."""
    targets: list[str] = []
    for raw in REDIRECT_TARGET_RE.findall(command):
        t = raw.strip("\"'")
        if t and not t.startswith("&") and t not in DEV_FILES:
            targets.append(t)
    for seg in SHELL_SPLIT_RE.split(command):
        try:
            toks = shlex.split(seg)
        except ValueError:
            continue          # unparseable quoting: the bins still scan
        hit = False
        for tok in toks:
            if tok in DESTRUCTIVE_BINS:
                hit = True
                continue
            if hit and not tok.startswith("-"):
                targets.append(tok)
    return targets


def _repo_relative(path: str, repo: Path) -> str | None:
    """A path as git reports it (repo-relative), or None when it cannot
    be resolved to this repository (~/..., elsewhere on the machine)."""
    p = path.strip("\"'")
    if p.startswith("~"):
        return None
    if os.path.isabs(p):
        try:
            rel = os.path.relpath(p, str(repo))
        except ValueError:
            return None
        return None if rel.startswith("..") else rel
    return os.path.normpath(p)


def destructive_against_baseline(commands: list[dict], baseline: set,
                                 repo: Path) -> list[dict]:
    """The commands that remove or rewrite a path the pre-dispatch
    baseline carried. A target hits a baseline entry when it names it,
    sits above it (removing a directory removes what it holds) or sits
    inside it (rewriting a file inside a carried directory)."""
    hits = []
    for c in commands:
        for target in _normalized_targets(_strip_quoted_text(_strip_heredocs(c["command"]))):
            rel = _repo_relative(target, repo)
            if rel is None:
                continue
            for b in baseline:
                if b == rel or b.startswith(rel + "/") \
                        or rel.startswith(b + "/"):
                    hits.append({"command": c["command"],
                                 "tool": c["tool"],
                                 "tool_call_id": c["tool_call_id"],
                                 "target": rel, "baseline_path": b})
                    break
    return hits


def final_message(lines: list) -> str:
    """The role's own account: the closing chat.final content when one
    exists, else the concatenated deltas. A keepalive final carries no
    content and never stands in for the message."""
    finals, deltas = [], []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        payload = d.get("payload")
        if not isinstance(payload, dict):
            continue
        if (d.get("event") or d.get("type")) == "chat.final":
            content = payload.get("content")
            if isinstance(content, str) and content.strip():
                finals.append(content)
        elif (d.get("event") or d.get("type")) == "chat.delta":
            content = payload.get("content")
            if isinstance(content, str):
                deltas.append(content)
    return "".join(finals) if finals else "".join(deltas)


def cli_unavailable_account(lines: list) -> str | None:
    """The role's report that it could not run the CLI, verbatim from
    its final message. None when the role said no such thing."""
    text = final_message(lines)
    idx = text.find(CLI_UNAVAILABLE_MARKER)
    if idx < 0:
        return None
    return text[idx + len(CLI_UNAVAILABLE_MARKER):].strip().splitlines()[0] \
        if text[idx + len(CLI_UNAVAILABLE_MARKER):].strip() else ""


def scan_frames(lines: list, baseline: set | None, repo: Path) -> dict:
    """Everything the frames show the role DOING that fails the dispatch
    regardless of how the round ended: judging its own output, or
    destroying what the tree already carried."""
    commands = frame_shell_commands(lines)
    return {"validator_invocations": validator_invocations(commands),
            "baseline_destructions":
                destructive_against_baseline(commands, baseline or set(),
                                             repo),
            "cli_unavailable": cli_unavailable_account(lines),
            "shell_commands_seen": len(commands)}


def authoring_skill_state() -> dict:
    """Whether the authoring skill is installed and registered in the
    gateway workspace — the precondition for a role to fetch its own
    guidance. The dispatch is refused before the client exists when it
    is not, with the remedy."""
    root = Path(SKILLS_DIR)
    skill_file = root / AUTHORING_SKILL / "SKILL.md"
    installed = skill_file.is_file()
    state = load_json(root / "skills_state.json", {})
    plugins = state.get("installed_plugins", []) \
        if isinstance(state, dict) else []
    registered = any(isinstance(p, dict) and p.get("name") == AUTHORING_SKILL
                     for p in plugins)
    return {"skill": AUTHORING_SKILL, "skills_dir": str(root),
            "skill_file": str(skill_file), "installed": installed,
            "registered": registered, "ok": installed and registered,
            "remedy": (f"install the {AUTHORING_SKILL} skill into the "
                       f"gateway workspace ({root}/{AUTHORING_SKILL}/"
                       "SKILL.md) and register it in skills_state.json "
                       "under installed_plugins; the roles fetch their "
                       "authoring guidance through it")}


# ── the design role: one pointer skill, a pinned tree, five facts ────
#
# The UI Designer reaches a read-only upstream tree (OpenDesign) that
# the operator pinned on the host. The contract copies the authoring
# skill's exactly: the skill is installed and registered, or the
# dispatch refuses with the remedy — nothing installs itself, nothing
# edits the gateway's configuration (E6, N4).

DESIGN_SKILL = "ui-designer"
OPENDESIGN_ROOT = Path(os.environ.get("AI_DLC_OPENDESIGN_ROOT",
                                      "/opt/open-design"))
OPENDESIGN_PATHS = ("skills", "design-templates", "design-systems")
# placeholder content the upstream's own example prompts forbid (E8):
# lorem ipsum anywhere, a TODO marker, or a placeholder IMAGE — the
# word "placeholder" in an input's label attribute is legitimate form
# markup and is deliberately not matched
PLACEHOLDER_RES = (re.compile(r"lorem\s+ipsum", re.I),
                   re.compile(r"\bTODO\b"),
                   re.compile(r'(src|href|url)\s*[=:]\s*["\']?'
                              r"[^\"'\s]*placehold", re.I))


def design_skill_state() -> dict:
    """Whether the design pointer skill is installed and registered —
    the precondition for a design dispatch. Same contract as the
    authoring skill: refused with the remedy when not, and never
    installed here (N4)."""
    root = Path(SKILLS_DIR)
    skill_file = root / DESIGN_SKILL / "SKILL.md"
    installed = skill_file.is_file()
    state = load_json(root / "skills_state.json", {})
    plugins = state.get("installed_plugins", []) \
        if isinstance(state, dict) else []
    registered = any(isinstance(p, dict) and p.get("name") == DESIGN_SKILL
                     for p in plugins)
    return {"skill": DESIGN_SKILL, "skills_dir": str(root),
            "skill_file": str(skill_file), "installed": installed,
            "registered": registered, "ok": installed and registered,
            "remedy": (f"install the {DESIGN_SKILL} skill into the "
                       f"gateway workspace ({root}/{DESIGN_SKILL}/"
                       "SKILL.md, shipped as supervisor/skills/workspace/"
                       f"{DESIGN_SKILL}/SKILL.md) and register it in "
                       "skills_state.json under installed_plugins — "
                       "scripts/install-opendesign.sh does both; the "
                       "dispatch never installs anything itself")}


# ── the boundary check ──────────────────────────────────────────────

# the captured stderr of the last git_status_paths failure (empty string on
# success or when no failure has occurred). Read it immediately after a None
# result to learn *why* git status failed — a module-level slot rather than a
# second return value so the existing list[str] | None contract (and every
# caller doing `git_status_paths(...) or []`) is untouched (G4, INV-33).
_GIT_STATUS_LAST_ERROR = ""


def git_status_paths(repo: Path) -> list[str] | None:
    """The paths git reports uncommitted right now, or None on git error."""
    global _GIT_STATUS_LAST_ERROR
    proc = git_run(["status", "--porcelain", "-uall"], repo)
    if proc.returncode != 0:
        _GIT_STATUS_LAST_ERROR = (proc.stderr or "").strip()
        return None
    _GIT_STATUS_LAST_ERROR = ""
    paths = []
    for line in (proc.stdout or "").splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.rstrip("/\\")
        if path:
            paths.append(path)
    return paths


FOREIGN_SERVICE_STOP_RE = re.compile(
    r"\bsystemctl\s+(?:stop|disable)\b"
    r"|\bfuser\s+\S*\-?k\b"
    r"|\bkill\s+\-9\b"
)


def foreign_service_stops(commands: list[dict]) -> list[dict]:
    """Shell commands that stop, disable or kill services or ports not
    belonging to the current change — a role must never reach beyond its
    own change to tear down foreign infrastructure."""
    return [c for c in commands
            if FOREIGN_SERVICE_STOP_RE.search(c["command"])]


def boundary_scan(repo: Path, change: str, extra_roots=(),
                  baseline=None, frames=None):
    """Judge only the increment a run caused. Every path git reports that
    was NOT already reported in the baseline must sit inside the change
    dir or be gateway bookkeeping; a path the working tree already
    carried before the run is the caller's pre-existing state, never the
    role's doing. Nothing is ever cleaned up — the offending paths are
    named and the task aborts. extra_roots lets the dispatch exclude its
    own task bookkeeping (the ledger and frames are ours, not the
    plane's product surface). When *frames* (a list of JSON-line strings)
    is provided, the shell commands the role ran are also scanned for
    foreign service stops (systemctl stop/disable, fuser -k, kill -9)."""
    seen = git_status_paths(repo)
    if seen is None:
        return {"error": "git status failed"}
    allowed_root = f"openspec/changes/{change}"
    rel_extras = []
    for root in extra_roots:
        try:
            rel = os.path.relpath(str(root), str(repo))
        except ValueError:
            continue
        if not rel.startswith(".."):
            rel_extras.append(rel)
    base = set(baseline) if baseline is not None else set()
    offending = []
    for path in seen:
        if path in base:
            continue          # pre-existing working-tree state
        ok = path == allowed_root or path.startswith(allowed_root + "/")
        ok = ok or any(path == b or path.startswith(b + "/")
                       for b in GATEWAY_BOOKKEEPING)
        ok = ok or any(path == r or path.startswith(r + "/")
                       for r in rel_extras)
        if not ok:
            offending.append(path)
    result = {"offending": offending, "changed_paths": seen,
              "baseline_paths": len(base)}
    if frames is not None:
        commands = frame_shell_commands(frames)
        foreign = foreign_service_stops(commands)
        if foreign:
            result["foreign_service_stop"] = foreign
    return result


def boundary_report(change: str, repo: Path, scan: dict) -> dict:
    violated = bool(scan.get("offending")) or bool(scan.get("foreign_service_stop"))
    return {"change": change, "repo": str(repo),
            "boundary": "violated" if violated else "clean",
            "paths": scan.get("offending") or scan.get("changed_paths", []),
            "baseline_paths": scan.get("baseline_paths", 0),
            "allowed_root": f"openspec/changes/{change}",
            "gateway_bookkeeping": [f"{d}/" for d in GATEWAY_BOOKKEEPING],
            **({"foreign_service_stop": scan["foreign_service_stop"]}
               if scan.get("foreign_service_stop") else {})}


def cmd_boundary(change: str, repo: Path, task_dir: Path | None,
                frames_file: Path | None = None) -> int:
    if task_dir is None:
        task_dir = default_task_dir(repo, change)
    # N6: the boundary a round may write is the PLANE tree's — the repo
    # is the round's read side and holds only the caller's own record
    root = plane_root(repo)
    masked = masked_surface_refusal(root)
    if masked:
        return emit({**masked, "change": change, "repo": str(repo),
                     "plane_root": str(root)}, EXIT_FORBIDDEN_TARGET)
    if not root.is_dir():
        return emit({"rejected": str(repo), "change": change,
                     "plane_root": str(root),
                     "why": ("the plane holds no tree for this repository "
                             "— there is no boundary to check"),
                     "remedy": "plan.py migrate --repo <repo> (one time)"},
                    EXIT_INCONCLUSIVE)
    baseline_file = task_dir / "boundary-baseline.json"
    if not baseline_file.is_file():
        # first call on this tree: record what is already there. A
        # pre-existing dirty tree is the caller's state, not a role's
        # leak — no violation can be claimed before a run happened.
        paths = git_status_paths(root)
        if paths is None:
            return emit({"error": "git status failed",
                         "boundary": "unknown"}, 1)
        save_json(baseline_file, sorted(set(paths)))
        return emit({"change": change, "repo": str(repo),
                     "plane_root": str(root),
                     "boundary": "baselined",
                     "baseline_paths": len(set(paths)),
                     "baseline_file": str(baseline_file),
                     "note": ("pre-existing working-tree state recorded; "
                              "later checks judge only the increment a "
                              "run causes")}, 0)
    baseline = set(load_json(baseline_file, []))
    # the baseline file itself lives in our task bookkeeping when the
    # task-dir sits inside the tree — it is never a product-surface path
    frames = None
    if frames_file is not None and frames_file.is_file():
        frames = frames_file.read_text(encoding="utf-8").splitlines()
    scan = boundary_scan(root, change, extra_roots=(task_dir,),
                         baseline=baseline, frames=frames)
    if "error" in scan:
        return emit({"error": scan["error"], "boundary": "unknown"}, 1)
    rep = boundary_report(change, root, scan)
    rep["repo"] = str(repo)
    rep["plane_root"] = str(root)
    rep["baseline_file"] = str(baseline_file)
    violated = bool(scan.get("offending")) or bool(scan.get("foreign_service_stop"))
    return emit(rep, EXIT_BOUNDARY if violated else 0)


# ── dispatch ────────────────────────────────────────────────────────

def under(path: Path, parent) -> bool:
    """Is path inside parent (or parent itself)? Both sides are forced
    to str before the comparison — commonpath always returns a str, and
    a Path on either side of the == would make every answer False."""
    parent = str(parent)
    try:
        return os.path.commonpath([str(path), parent]) == parent
    except ValueError:
        return False


# ── the target's class: what the plane can actually do with it ──────
#
# The plane is the gateway service, and what it can do is settled by
# three things only: the grants its service unit carries (ReadWritePaths
# under ProtectSystem — the sandbox of the hardened regime), a probe
# through the service's OWN mount namespace, and the mounts that
# namespace itself carries. Since the open-sandbox decision
# (docs/prd-gateway-open-sandbox.md) the unit declares no allowlist, and
# the probe alone would say writable for nearly everything — simple, but
# it must be TRUE simple, not unexposed: a probe inside the namespace
# can read the namespace's own pollution as truth (a session's mkdir
# persisting in a private /tmp is what misclassified /tmp/country-e). So the
# deepest mount covering the path is compared between the gateway's
# namespace and the caller's, mechanically, from mountinfo: a mount only
# the gateway sees is a VETO — the path is invisible whatever the probe
# reports. A target is classified writable, readable, or invisible
# before the first dispatch of every run; a mask decides over the probe,
# and every other disagreement between mounts, probe and grants is
# resolved to the most conservative answer, with decision_basis naming
# which one decided.

# the unit file (AI_DLC_GW_UNIT — the same override install.sh reads),
# the plane's writable root override, the probe-root override that
# stands in for /proc/<MainPID>/root (tests point it at a fixture tree),
# and the mountinfo fixture standing in for the service's own
# /proc/<pid>/mountinfo (tests craft a namespace-only mount)
GATEWAY_UNIT_FILE = os.environ.get(
    "AI_DLC_GW_UNIT", "/etc/systemd/system/jiuwenswarm-gateway.service")
PLANE_ROOT_ENV = "AI_DLC_PLANE_ROOT"
GATEWAY_ROOT_ENV = "AI_DLC_GATEWAY_ROOT"
PROBE_READONLY_ENV = "AI_DLC_PROBE_READONLY"
GATEWAY_MOUNTINFO_ENV = "AI_DLC_GW_MOUNTINFO"
# test hook: injects the fault a guard exists to catch, so the refusal
# is provable without shipping the bug
FAULT_ENV = "AI_DLC_FAULT"
DATA_DIR_VAR = "JIUWENSWARM_DATA_DIR"


def unit_state(unit_file: str = GATEWAY_UNIT_FILE) -> dict:
    """The service unit's grants, read from the unit file and its drop-in
    directory the way the installer's plane audit reads them — no
    systemctl round-trip needed for text that sits in a file."""
    writable: list[str] = []
    private_tmp = False
    data_dir = None
    sources: list[str] = []

    def _read(path: Path) -> None:
        nonlocal private_tmp, data_dir
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        sources.append(str(path))
        for ln in lines:
            if ln.startswith("ReadWritePaths="):
                for p in ln.split("=", 1)[1].split():
                    if p.strip():
                        writable.append(p.strip())
            elif ln.startswith("PrivateTmp="):
                private_tmp = ln.split("=", 1)[1].strip().lower() == "true"
            elif ln.startswith("Environment=") and DATA_DIR_VAR + "=" in ln:
                for part in ln.split("=", 1)[1].split():
                    if part.startswith(DATA_DIR_VAR + "="):
                        data_dir = part.split("=", 1)[1].strip()

    unit = Path(unit_file)
    _read(unit)
    for conf in sorted(unit.parent.glob(unit.name + ".d/*.conf")):
        _read(conf)
    return {"unit": str(unit), "sources": sources, "writable": writable,
            "private_tmp": private_tmp, "data_dir": data_dir}


def _gateway_pid() -> int | None:
    """The running service's MainPID, or None when the unit is not
    running (or systemctl cannot say)."""
    proc = run(["systemctl", "show", Path(GATEWAY_UNIT_FILE).name,
                "-p", "MainPID", "--value"], timeout=30)
    if proc.returncode != 0:
        return None
    pid = (proc.stdout or "").strip().splitlines()[:1]
    if not pid or not pid[0].isdigit() or int(pid[0]) <= 0:
        return None
    return int(pid[0])


def probe_root() -> Path | None:
    """The root of the gateway's own filesystem view: /proc/<MainPID>/root
    of the running service, or the fixture a test points at. Through it,
    a path under the service's private /tmp simply does not exist — no
    prefix list is consulted, and none could substitute (a /tmp path the
    service CAN see reads as readable here)."""
    override = os.environ.get(GATEWAY_ROOT_ENV)
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    pid = _gateway_pid()
    if pid is None:
        return None
    root = Path(f"/proc/{pid}/root")
    return root if root.is_dir() else None


_MOUNT_ESCAPES = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}


def _mount_field(s: str) -> str:
    """One mountinfo field with its octal escapes undone — mount points
    carry \040 for a space and kin, and a masked path under such a mount
    must still compare equal."""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and s[i + 1:i + 4] in _MOUNT_ESCAPES:
            out.append(_MOUNT_ESCAPES[s[i + 1:i + 4]])
            i += 4
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _parse_mountinfo(text: str) -> list[dict]:
    """The mounts a mountinfo text carries: mountpoint, device
    (major:minor) and the root within the source filesystem — the three
    that identify a mount instance. Lines that are not mountinfo are
    skipped, not guessed at."""
    mounts = []
    for line in text.splitlines():
        parts = line.split()
        # id parent dev root mountpoint [optional…] - fstype source super
        if len(parts) < 6:
            continue
        try:
            sep = parts.index("-", 5)
        except ValueError:
            continue
        if len(parts) < sep + 3:
            continue
        mounts.append({"mountpoint": _mount_field(parts[4]),
                       "dev": parts[2], "root": _mount_field(parts[3])})
    return mounts


def _covering_mount(mounts: list[dict], path: Path) -> dict | None:
    """The deepest mount whose mountpoint holds the path — the mount the
    path is actually judged through. None when the list says nothing
    covers it (an empty or foreign text, not a real namespace)."""
    best = None
    for m in mounts:
        mp = m["mountpoint"].rstrip("/") or "/"
        if under(path, mp):
            if best is None or len(mp) > len(
                    best["mountpoint"].rstrip("/") or "/"):
                best = m
    return best


def mount_mask(repo: Path) -> dict:
    """I2's mechanical check, read before any probe: the deepest mount
    covering the path in the GATEWAY's namespace against the same mount
    in the caller's own. Identical device, root and mountpoint means the
    path is judged through a mount both sides see; anything else — a
    different tmpfs, a bind the service alone carries — is a mask, and a
    mask vetoes the probe: what a probe reads behind it is the
    namespace's own residue, never the caller's filesystem. When either
    side's mountinfo cannot be read the comparison is recorded as not
    performed — never as passed."""
    repo = repo.resolve()
    self_src = "/proc/self/mountinfo"
    override = os.environ.get(GATEWAY_MOUNTINFO_ENV)
    if override:
        gw_src = override
    else:
        pid = _gateway_pid()
        gw_src = f"/proc/{pid}/mountinfo" if pid is not None else None
    record = {"self_source": self_src, "gateway_source": gw_src}
    try:
        mounts_self = _parse_mountinfo(
            Path(self_src).read_text(encoding="utf-8"))
    except OSError:
        mounts_self = []
    try:
        mounts_gw = _parse_mountinfo(
            Path(gw_src).read_text(encoding="utf-8")) if gw_src else []
    except OSError:
        mounts_gw = []
    if not mounts_self or not mounts_gw:
        return {**record, "checked": False, "masked": False,
                "masked_by": None,
                "note": ("a side's mountinfo could not be read — the "
                         "mount comparison is recorded as not performed, "
                         "never as passed")}
    gw_m = _covering_mount(mounts_gw, repo)
    se_m = _covering_mount(mounts_self, repo)
    same = (gw_m is not None and se_m is not None
            and gw_m["dev"] == se_m["dev"]
            and gw_m["root"] == se_m["root"]
            and (gw_m["mountpoint"].rstrip("/") or "/")
            == (se_m["mountpoint"].rstrip("/") or "/"))
    out = {**record, "checked": True, "masked": not same,
           "gateway_mount": gw_m, "self_mount": se_m}
    if not same:
        who = gw_m or se_m
        out["masked_by"] = (
            f"{who['mountpoint']} (dev {who['dev']}, root {who['root']}) — "
            "the gateway's mount at this point is not the caller's own")
    else:
        out["masked_by"] = None
    return out


def classify_target(repo: Path, grants: dict | None = None) -> dict:
    """Writable, readable, or invisible — established by a probe that
    cannot create existence, a mount comparison that can veto it, and
    the unit's grants, all recorded alongside. A mount only the
    gateway's namespace sees decides first (invisible, whatever the
    probe reports behind it); without a mask, any disagreement between
    probe and a declared allowlist is resolved to the most conservative
    answer, and decision_basis names what decided. An allowlist the unit
    no longer declares (the open regime) claims nothing — the probe
    deciding writable there is agreement, not disagreement."""
    repo = repo.resolve()
    grants = grants if grants is not None else unit_state()
    proot = probe_root()
    if proot is None:
        return {"class": None, "repo": str(repo),
                "grants": grants, "probe": None,
                "why": ("the gateway's filesystem view could not be "
                        "reached (no running service MainPID, or no probe "
                        "root) — the class is established by probing, so "
                        "no class is assumed")}
    mask = mount_mask(repo)
    view = Path(str(proot) + str(repo))
    read = view.exists()
    write = bool(read) and os.access(view, os.W_OK)
    # I1 — the probe must not manufacture existence. os.access creates
    # nothing; the guard exists so a creating probe can never pass
    # silently: a path that did not stand before the probe but stands
    # after it is a refused classification, never a class.
    probe_created_paths = [] if read or not view.exists() else [str(repo)]
    if probe_created_paths:
        return {"class": None, "repo": str(repo),
                "probe_created_paths": probe_created_paths,
                "masked_by": mask.get("masked_by"), "mounts": mask,
                "grants": grants,
                "why": ("the probe left standing a path that did not "
                        "exist before it — a probe observes, it never "
                        "creates; no class is reported for a path the "
                        "measurement itself would bring into being")}
    # a test fixture for the one thing a test cannot reproduce as root:
    # a read-only mount. The real verdict comes from the probe; this
    # only narrows it, and only for the paths named
    ro = os.environ.get(PROBE_READONLY_ENV, "")
    if ro and read and write:
        for prefix in ro.split(":"):
            if prefix and under(repo, prefix):
                write = False
                break
    cls = "writable" if read and write else "readable" if read \
        else "invisible"
    granted = [w for w in grants.get("writable", []) if under(repo, w)]
    declared = [w for w in grants.get("writable", []) if w]
    disagreement = None
    decision_basis = "probe"
    if mask.get("masked"):
        cls = "invisible"
        decision_basis = "mountinfo"
        if read and write:
            disagreement = ("a mount only the gateway's namespace sees "
                            "covers this path — the probe's writable is "
                            "the mount's own residue, and the mount "
                            "vetoes it")
    elif declared:
        if granted and not write:
            disagreement = ("the unit grants this path writable but the plane "
                            "cannot write it (a drop-in not yet daemon-reloaded, "
                            "or a mount above it is read-only)")
        elif not granted and write:
            disagreement = ("the plane can write this path although the "
                            "unit's allowlist does not grant it — the "
                            "conservative answer is taken: the class "
                            "stands at readable until the unit and the "
                            "filesystem agree")
            cls = "readable"
            decision_basis = "grants"
    return {"class": cls, "repo": str(repo),
            "probe": {"root": str(proot), "view": str(view),
                      "read": read, "write": write},
            "masked_by": mask.get("masked_by"),
            "probe_created_paths": probe_created_paths,
            "decision_basis": decision_basis,
            "mounts": mask,
            "grants": {k: grants.get(k) for k in ("writable", "private_tmp",
                                                  "data_dir", "unit")},
            "granted_writable": granted,
            "grant_disagreement": disagreement,
            "method": ("read and write probed separately through the "
                       "gateway's own mount namespace, a probe that "
                       "creates nothing; the deepest covering mount is "
                       "compared against the caller's own mountinfo — a "
                       "mount only the gateway sees vetoes the probe, "
                       "and any remaining disagreement with a declared "
                       "allowlist resolves to the most conservative "
                       "answer (decision_basis names what decided)")}


def writable_root(grants: dict | None = None) -> Path | None:
    """The unit's writable area that hosts the run's own state: the
    writable paths minus the runtime's own data directory. A staged copy
    for a target the plane cannot see lives here — never inside a
    project the round must not write. (Not to be confused with the
    plane root of containment N6 — report.plane_root — which is where a
    repository's spec TREE lives; that one is per-repo, not per-unit.)"""
    override = os.environ.get(PLANE_ROOT_ENV)
    if override:
        return Path(override)
    grants = grants if grants is not None else unit_state()
    data = grants.get("data_dir")
    for w in grants.get("writable", []):
        if data is None or w != data:
            return Path(w)
    # the open regime declares no allowlist at all, so no unit path
    # names itself for run state — the one area whose purpose is run
    # state is the runtime's own data directory, which both regimes
    # keep writable. No path is ever ASSUMED: without a data dir either,
    # the answer stays None and the caller refuses honestly.
    return Path(data) if data else None


def workspace_slug(project: Path) -> str:
    """A flat, unambiguous name for the project a workspace belongs to,
    so two projects running same-named changes never share state."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(project.resolve()).strip("/"))
    return s.strip("-") or "project"


def tree_bytes(tree: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(tree):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total


# ── the split workspace: write in the plane's tree, read the project ──

def split_paths(change: str, project: Path, root: Path) -> dict:
    slug = workspace_slug(project)
    return {
        "stage": root / ".ai-dlc" / "stage" / f"{slug}--{change}",
    }


def self_containment_errors(copy: Path) -> list[str]:
    """Every reference by which the staged copy would depend on a path
    the plane cannot reach: a .git gitfile pointing outside the copy, or
    a symlink resolving outside it. Each is named; one is enough to stop
    the run before dispatch."""
    errors = []
    gitfile = copy / ".git"
    if gitfile.is_file():
        first = gitfile.read_text(encoding="utf-8",
                                  errors="replace").splitlines()[:1]
        if first and first[0].startswith("gitdir:"):
            target = Path(first[0].split(":", 1)[1].strip())
            resolved = target if target.is_absolute() \
                else (copy / target).resolve()
            if not under(resolved, str(copy)):
                errors.append(f".git gitfile points outside the copy: "
                              f"{first[0].strip()} -> {resolved}")
    for root, dirs, files in os.walk(copy):
        for name in dirs + files:
            p = Path(root) / name
            if p.is_symlink():
                target = Path(os.readlink(p))
                resolved = target if target.is_absolute() \
                    else (p.parent / target).resolve()
                if not under(resolved, str(copy)):
                    errors.append(f"symlink resolves outside the copy: "
                                  f"{p} -> {resolved}")
    return errors


def stage_copy(change: str, project: Path, root: Path) -> dict:
    """Copy a target the plane cannot see at all into the writable area.
    The only class this is legal for: the record states that nothing at
    the source was readable. The copy carries its own history store and
    working tree; anything in it that references a path outside the
    reachable area stops the run before dispatch, named."""
    sp = split_paths(change, project, root)
    dest = sp["stage"]
    marker = dest / ".ai-dlc" / "staging.json"
    if dest.is_dir():
        # a resume keeps the copy it has: the round's own artifacts and
        # record live inside it, and re-copying would destroy them. The
        # original cost is carried from the copy, marked as reused —
        # what the source did after the copy is invisible to this round
        # either way, and that is the recorded caveat of a copied round.
        prior = load_json(marker, {}) or {}
        return {"class": "invisible", "source": str(project),
                "copy": str(dest), "reused": True,
                **{k: prior.get(k) for k in
                   ("taken_at", "duration_seconds", "size_bytes",
                    "source_revision")},
                "self_contained": not self_containment_errors(dest),
                "errors": self_containment_errors(dest),
                "why_read_in_place_impossible": (
                    "nothing at the source was readable — the gateway's own "
                    "view of the path does not exist (the private temporary "
                    "namespace), so there is nothing to read in place")}
    started = time.monotonic()
    shutil.copytree(project, dest, symlinks=True)
    duration = round(time.monotonic() - started, 3)
    rev = None
    proc = run(["git", "-C", str(project), "rev-parse", "HEAD"])
    if proc.returncode == 0 and proc.stdout.strip():
        rev = proc.stdout.strip()
    if not (dest / ".git").exists():
        run(["git", "init", "-q", str(dest)])   # the boundary machinery
                                                # judges a git tree
    # nothing else is constructed inside the copy (containment D12): the
    # round's authoring surface is the plane's own tree, so the copy is
    # exactly the project as it stood — read-only side of the round
    errors = self_containment_errors(dest)
    record = {"class": "invisible", "source": str(project),
              "copy": str(dest), "taken_at": now_iso(),
              "duration_seconds": duration,
              "size_bytes": tree_bytes(dest), "source_revision": rev,
              "self_contained": not errors, "errors": errors,
              "reused": False}
    # the copy carries its own staging record, so a resume reports the
    # cost of the copy it actually reuses rather than a fresh measurement
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    return {**record,
            "why_read_in_place_impossible": (
                "nothing at the source was readable — the gateway's own "
                "view of the path does not exist (the private temporary "
                "namespace), so there is nothing to read in place")}


# ── byte-for-byte: the project as the round found it ────────────────

def snapshot_manifest(tree: Path, skip: tuple = ()) -> dict:
    """Every file in the tree with its size and content hash, symlinks
    with their targets: the strongest statement of what the round found,
    independent of version control. Paths under any skipped directory
    are not counted — used for the run's own record (.ai-dlc), which
    the caller writes and the round's comparison must not mistake for
    the round's work."""
    import hashlib
    files: dict = {}
    for root, dirs, names in os.walk(tree):
        dirs[:] = sorted(d for d in dirs
                         if not any(under(Path(root) / d, sp) or
                                    (Path(root) / d) == Path(sp)
                                    for sp in skip))
        for n in names:
            p = Path(root) / n
            rel = str(p.relative_to(tree))
            if p.is_symlink():
                files[rel] = {"symlink": os.readlink(p)}
                continue
            try:
                data = p.read_bytes()
            except OSError:
                files[rel] = {"unreadable": True}
                continue
            files[rel] = {"size": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()}
    return {"tree": str(tree), "taken_at": now_iso(),
            "file_count": len(files), "files": files}


def untouched_report(before: dict, tree: Path,
                      skip: tuple = ()) -> dict:
    """Compare the tree against a manifest taken before the round: every
    path present, absent, or changed is named, and the three gateway
    bookkeeping directories are checked for existence — a read-in-place
    round must leave none of them behind in the project. Skipped
    directories (the run's own record) are outside the comparison both
    before and after."""
    after = snapshot_manifest(tree, skip=skip)
    bf, af = before.get("files", {}), after["files"]
    added = sorted(set(af) - set(bf))
    removed = sorted(set(bf) - set(af))
    changed = sorted(k for k in set(af) & set(bf) if af[k] != bf[k])
    bookkeeping = [d for d in GATEWAY_BOOKKEEPING
                   if (tree / d).exists()]
    return {"tree": str(tree), "before_taken_at": before.get("taken_at"),
            "after_taken_at": after["taken_at"],
            "file_count_before": before.get("file_count"),
            "file_count_after": after["file_count"],
            "added": added, "removed": removed, "changed": changed,
            "bookkeeping_dirs": bookkeeping,
            "untouched": not (added or removed or changed or bookkeeping)}


# ── what the frames say the role wrote, and where it landed ─────────

def frame_write_abs(lines: list, base: Path) -> list[str]:
    """The absolute paths a role's frames show it writing, resolved
    against the working directory the dispatch set (relative targets)
    and kept as named (absolute ones). Read generously: over-capture
    only names a path nobody wrote; under-capture is the accident —
    heredoc bodies are stripped first, so the payload's own markup
    never reads as a write (a fact list would fail on it)."""
    raw: list[str] = []
    for call in _tool_invocations(lines):
        name = (call["tool"] or "").lower()
        if any(k in name for k in ("write", "edit", "create", "notebook")):
            for key in WRITE_TOOL_PATH_KEYS:
                p = call["arguments"].get(key)
                if isinstance(p, str) and p.strip():
                    raw.append(p)
    for c in frame_shell_commands(lines):
        raw += _normalized_targets(_strip_quoted_text(_strip_heredocs(c["command"])))
    out = []
    for t in raw:
        t = t.strip("\"'")
        if not t or t.startswith("~"):
            continue
        p = Path(t) if os.path.isabs(t) else Path(os.path.normpath(base / t))
        s = str(p)
        if s not in out:
            out.append(s)
    return out


def _project_revision(project: Path) -> str | None:
    """The project's revision at the moment the workspace was chosen —
    the anchor a read-in-place round is judged against when the project
    moves underneath it. None when the project carries no history."""
    proc = run(["git", "-C", str(project), "rev-parse", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 else None


def workspace_for(change: str, project: Path, classification: dict,
                  task_dir: Path | None = None) -> dict:
    """The dispatch workspace under containment N6: the spec surface is
    the plane's own tree, so EVERY author dispatch writes there and
    only reads the project — whatever the class. The class decides the
    READ side alone: the project in place when the plane can see it
    (writable or readable — the round never writes it either way now),
    a staged copy when it cannot. There is no scratch anymore: nothing
    caller-side constructs a spec tree (D12), so a round without a
    plane tree is refused with the one-time migration as the remedy.
    The task record stays anchored to the repo — it is caller state,
    written by this tool, not by the gateway."""
    cls = classification.get("class")
    project = project.resolve()
    root = plane_root(project)
    if not root.is_dir():
        return {"refused": True, "class": cls, "project": str(project),
                "plane_root": str(root),
                "stopped": "before dispatch — the client was never invoked",
                "why": ("the plane holds no tree for this repository: the "
                        "spec surface lives plane-side (containment N6), "
                        "and a round cannot be dispatched until it "
                        "exists. No path is assumed and nothing is "
                        "scaffolded here"),
                "remedy": "plan.py migrate --repo <repo> (one time)"}
    ws = {"kind": "plane", "class": cls, "path": str(root),
          "project": str(project), "scratch": None, "stage": None,
          "plane_root": str(root),
          "task_dir": str(task_dir or default_task_dir(project, change)),
          "read": "live", "snapshotted": False,
          "starting_revision": _project_revision(project),
          "note": ("the spec surface is the plane's own tree: the round "
                   "writes there and reads the project in place, by "
                   "absolute path — the project is never written by a "
                   "planning round, whatever its class")}
    if cls == "invisible":
        # a copy is the only option, and the record says why
        area = writable_root(classification.get("grants"))
        if area is None:
            return {"refused": True, "why": (
                        "the plane's writable area cannot be established "
                        "from the service unit's grants — a round whose "
                        "project it cannot see needs somewhere to stage "
                        "a copy, and no path is assumed"),
                    "class": cls, "project": str(project)}
        staged = stage_copy(change, project, area)
        if staged["errors"]:
            return {"refused": True, "class": cls, "project": str(project),
                    "staging": staged,
                    "stopped": ("before dispatch — the client was never "
                                "invoked"),
                    "why": ("the staged copy is not self-contained: it "
                            "references a path outside the reachable "
                            "area, and the round would depend on what it "
                            "cannot reach")}
        ws.update({"project": staged["copy"], "stage": staged["copy"],
                   "staging": staged, "read": "snapshot",
                   "snapshotted": True,
                   # the caller's own record lives inside the copy, as it
                   # always did for a copied round — the source is left
                   # exactly as found, record included
                   "task_dir": str(task_dir
                                   or default_task_dir(Path(staged["copy"]),
                                                       change)),
                   "starting_revision": staged.get("source_revision"),
                   "note": ("nothing at the source was readable; the "
                            "round reads a staged copy and writes the "
                            "plane's own tree. Work done in the source "
                            "after the copy was not seen")})
    return ws


def refuse_copy_of_readable(project: Path, classification: dict) -> dict:
    """The refusal a run earns by trying to copy a target it could read
    in place: the split workspace is the mechanism, and the size the
    copy would have cost is named so the objection is a number, not a
    feeling."""
    return {"refused": str(project),
            "class": classification.get("class"),
            "why": ("a readable target is read in place through the "
                    "split round — the plane's own tree carries the "
                    "round's writes and the project is granted as a "
                    "readable location; copying is reserved for a "
                    "target the plane cannot see at all"),
            "copy_would_have_cost_bytes": tree_bytes(project),
            "remedy": ("dispatch with the split workspace: the working "
                       "directory inside the writable area, the project "
                       "granted as an additional trusted location for "
                       "reading")}


def split_client_cmd(base_cmd: list, workspace: dict) -> list:
    """The client invocation for a split round (every round under N6):
    the working directory and project identity are the plane's tree,
    and the project itself (or its staged copy) is granted as an
    additional trusted location so the role may read it by absolute
    path — the one grant whose absence makes a role refuse and ask a
    confirmation no headless run can answer."""
    cmd = list(base_cmd) + ["--project-dir", workspace["path"]]
    trusted = [workspace["path"], workspace["project"]]
    if os.environ.get(FAULT_ENV) == "omit-project-trust":
        # the fault-injection hook: builds the argv the guard exists to
        # catch, so the refusal is provable without shipping the bug
        trusted = [workspace["path"]]
    for t in trusted:
        cmd += ["--trusted-dir", t]
    return cmd


def split_trust_guard(cmd: list, workspace: dict) -> list:
    """The checks that fail a split dispatch BEFORE the client exists:
    the working directory must be the workspace, and both trusted
    locations — the workspace and the project — must be granted. A role
    granted only its working directory refuses to read the project and
    asks a confirmation nothing headless can answer; that dispatch is
    stopped here, naming the missing grant."""
    problems = []
    cwd = None
    trusted = []
    for i, a in enumerate(cmd):
        if a == "--cwd" and i + 1 < len(cmd):
            cwd = cmd[i + 1]
        if a == "--trusted-dir" and i + 1 < len(cmd):
            trusted.append(cmd[i + 1])
    if cwd != workspace["path"]:
        problems.append(f"the working directory is {cwd}, not the "
                        f"workspace {workspace['path']}")
    for role, path in (("the workspace", workspace["path"]),
                       ("the project", workspace["project"])):
        if not any(t == path for t in trusted):
            problems.append(f"the trusted locations name no grant for "
                            f"{role}: {path}")
    return problems


def next_evidence(task_dir: Path, role: str) -> Path:
    ev = task_dir / "evidence"
    pat = re.compile(rf"plan-{re.escape(role)}-(\d+)\.jsonl$")
    seq = 0
    if ev.is_dir():
        for p in ev.iterdir():
            m = pat.match(p.name)
            if m:
                seq = max(seq, int(m.group(1)))
    return ev / f"plan-{role}-{seq + 1}.jsonl"


# ── the acceptance-target safety rule (landing L7) ──────────────────

# directory-name markers of dependency source this project may never
# modify — the never-modify rule names delegate-router / jiuwenswarm /
# openjiuwen / openspec source
FORBIDDEN_DIR_MARKERS = ("delegate-router", "jiuwenswarm", "openjiuwen")


def forbidden_dependency_paths(repo: Path) -> list[str]:
    """Paths in the target that hold source of a dependency this project
    may never modify. The root-level openspec/ directory is exempt: that
    is the data dir the upstream CLI itself creates in every target, not
    source. The run that taught this rule pointed at a tree holding
    claude-code-oauth-delegate-router source and dispatched into it."""
    hits = []
    for root, dirs, _files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for d in dirs:
            if root == str(repo) and d == "openspec":
                continue          # the data dir, expected in every target
            p = Path(root) / d
            if d == "openspec" and (
                    (p / "package.json").exists() or (p / ".git").exists()
                    or (p / "src").is_dir()):
                hits.append(str(p))   # a vendored checkout of the source
                continue
            if any(m in d.lower() for m in FORBIDDEN_DIR_MARKERS):
                hits.append(str(p))
    return hits


def view_state(repo: Path) -> dict:
    """Roles plan against the working tree. A tree that shows fewer
    files than its head commit — a sparse or partial checkout — is a
    narrower view of the repository than it looks, and nobody should
    discover that after the fact: the mismatch is reported before the
    first dispatch and the run waits for a human to accept the narrower
    view. A complete view passes silently."""
    proc = run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only",
                "HEAD"])
    if proc.returncode != 0:
        return {"state": "no_history"}
    heads = [l for l in (proc.stdout or "").splitlines() if l]
    if not heads:
        return {"state": "no_history"}
    missing = [h for h in heads if not (repo / h).is_file()]
    if not missing:
        return {"state": "complete"}
    return {"state": "partial",
            "head_files": len(heads),
            "visible_of_head": len(heads) - len(missing),
            "roles_will_see": (f"the {len(heads) - len(missing)} of "
                               f"{len(heads)} tracked files present in "
                               f"the working tree"),
            "roles_will_not_see_count": len(missing),
            "roles_will_not_see_sample": missing[:8]}


def covered_by_baseline(path: str, baseline: set) -> bool:
    """A path is the tree's own when a pre-run baseline entry names it,
    sits inside it, or sits above it."""
    return any(b == path or path.startswith(b + "/")
               or b.startswith(path + "/") for b in baseline)


def earliest_baseline_file(task_dir: Path) -> Path | None:
    """The first dispatch's pre-boundary snapshot — the tree as the run
    found it, before any artifact existed."""
    ev = task_dir / "evidence"
    if not ev.is_dir():
        return None
    files = [p for p in ev.glob("plan-*.pre-boundary.json") if p.is_file()]
    return min(files, key=lambda p: p.stat().st_mtime) if files else None


def worktrees_on_branch(repo: Path, branch: str) -> list[str]:
    proc = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    found = []
    for block in (proc.stdout or "").split("\n\n"):
        if f"branch refs/heads/{branch}" not in block:
            continue
        for line in block.splitlines():
            if line.startswith("worktree "):
                found.append(line.split(" ", 1)[1])
    return found


def _run_note(proc: subprocess.CompletedProcess) -> str | None:
    return (((proc.stdout or "") + (proc.stderr or "")).strip()[:500]
            or None)


def cmd_sweep(change: str, repo: Path, task_dir: Path | None,
              purge_openspec: bool, keep_record: bool,
              branch: str | None) -> int:
    """The run leaves the target as it found it (landing L7.4/L7.5).

    Judged against the earliest pre-boundary baseline: paths that path
    set already carried are never touched and the skip is recorded; what
    the run introduced and did not deliver is removed. The openspec/
    tree stays for a person to review and commit unless --purge-openspec
    says the run was voided. The baseline and the status it is judged
    against are the PLANE root's (N6: the round's writes live there);
    the repo is the round's read side and only the task record the run
    kept in it is removed, unless --keep-record. The task worktree and
    branch are removed when the branch is merged; an unmerged branch
    holds the only copy of the work, so its retention is recorded with
    that reason instead.
    Without a baseline nothing is removed — sweep cannot tell the run's
    paths from the tree's own, and guessing is how pre-existing state
    dies."""
    if task_dir is None:
        task_dir = default_task_dir(repo, change)
    base_file = earliest_baseline_file(task_dir)
    if base_file is None:
        return emit({"change": change, "repo": str(repo), "swept": False,
                     "why": ("no pre-boundary baseline exists for this "
                             "change in the task record — sweep cannot "
                             "tell the run's paths from the tree's own, "
                             "so it removes nothing")},
                    EXIT_INCONCLUSIVE)
    # N6: the round's writes live in the plane's own tree, so the
    # baseline and the status it is judged against are the PLANE
    # root's; the repo itself is the round's read side, never written
    # (the project-writes gate), and only the task record the run kept
    # there is the run's to remove
    root = plane_root(repo)
    baseline = set(load_json(base_file, []) or [])
    current = git_status_paths(root) or []

    # group by top-level component: a component holding any baseline
    # path is the tree's own, whole — file-by-file removal inside a
    # component the tree already carried is exactly the accident this
    # command exists to prevent
    comps: dict = {}
    for path in current:
        top = path.split("/", 1)[0]
        c = comps.setdefault(top, {"paths": [], "baseline": []})
        c["paths"].append(path)
        if covered_by_baseline(path, baseline):
            c["baseline"].append(path)
    ls = git_run(["ls-files"], root)
    tracked = {l for l in (ls.stdout or "").splitlines() if l} \
        if ls.returncode == 0 else set()

    removed: list = []
    restored: list = []
    skipped: list = []
    retained: list = []
    for top in sorted(comps):
        c = comps[top]
        if c["baseline"]:
            skipped.append({"component": top,
                            "reason": "present in the pre-run baseline — "
                                      "not the run's to remove",
                            "paths_count": len(c["baseline"]),
                            "paths": c["baseline"][:10]})
            continue
        if top == "openspec" and not purge_openspec:
            retained.append({"component": "openspec",
                             "reason": ("the change/archive tree — a person "
                                        "reviews and commits it; "
                                        "--purge-openspec removes it for a "
                                        "voided run")})
            continue
        for path in c["paths"]:
            target = root / path
            if path in tracked:
                r = git_run(["checkout", "--", path], root)
                restored.append({"path": path,
                                 "restored_to_head": r.returncode == 0,
                                 "output": _run_note(r)})
            elif target.is_dir() and not target.is_symlink():
                shutil.rmtree(target, ignore_errors=True)
                removed.append(path + "/")
            elif target.exists() or target.is_symlink():
                target.unlink()
                removed.append(path)
                # an untracked file gone leaves its directory empty;
                # prune upwards so the run's directories actually leave
                p = target.parent
                while p != root:
                    try:
                        p.rmdir()      # only succeeds when empty
                    except OSError:
                        break
                    removed.append(str(p.relative_to(root)) + "/")
                    p = p.parent

    # the task record the run kept in the repo (N6): the run's own
    # state, removed with the run unless its retention is asked for
    record_report = None
    if task_dir.exists():
        if keep_record:
            record_report = {"path": str(task_dir), "removed": False,
                             "reason": "kept by request (--keep-record)"}
        else:
            shutil.rmtree(task_dir, ignore_errors=True)
            record_report = {"path": str(task_dir), "removed": True}
            # an emptied record leaves its ancestor skeleton behind; the
            # same upward prune the untracked paths take returns the
            # repo's .ai-dlc/ to what stood before the run
            p = task_dir.parent
            while p != repo and p != p.parent:
                try:
                    p.rmdir()      # only succeeds when empty
                except OSError:
                    break
                p = p.parent

    # the branch and worktree the run created (L7.5)
    br = branch or f"task/{change}"
    has_br = run(["git", "-C", str(repo), "rev-parse", "--verify", "-q",
                  "refs/heads/" + br]).returncode == 0
    wt_report: list = []
    br_report = None
    merged = run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                  br, "HEAD"]).returncode == 0 if has_br else True
    if not merged:
        for w in worktrees_on_branch(repo, br):
            wt_report.append({"path": w, "removed": False,
                              "reason": "the branch is unmerged — the "
                                        "worktree holds the only copy of "
                                        "the work"})
        br_report = {"branch": br, "removed": False,
                     "reason": "unmerged — the work exists only here; "
                               "merge it or export it before sweeping "
                               "it away"}
    else:
        for w in worktrees_on_branch(repo, br):
            if Path(w) == repo:
                continue
            r = run(["git", "-C", str(repo), "worktree", "remove", w])
            wt_report.append({"path": w, "removed": r.returncode == 0,
                              "output": _run_note(r)})
        if has_br:
            r = run(["git", "-C", str(repo), "branch", "-d", br])
            br_report = {"branch": br, "removed": r.returncode == 0,
                         "output": _run_note(r)}

    return emit({"change": change, "repo": str(repo), "swept": True,
                 "plane_root": str(root),
                 "baseline_file": str(base_file),
                 "baseline_paths": len(baseline),
                 "removed": removed, "restored_to_head": restored,
                 "skipped_baseline": skipped, "retained": retained,
                 "task_record": record_report,
                 "worktrees": wt_report, "branch": br_report,
                 "note": ("this report is printed rather than stored: the "
                          "task record it read from is itself swept — "
                          "copy it into the caller's evidence if it must "
                          "survive")}, 0)


def cmd_dispatch(change: str, role: str, package_file: Path,
                 task_dir: Path | None, mode: str, timeout: int,
                 frames_file: Path | None,
                 accept_partial_view: bool = False,
                 baseline_file: Path | None = None,
                 split_project: Path | None = None,
                 project_manifest: Path | None = None) -> int:
    if frames_file is not None:
        # offline judge mode — the test hook: judge the frame file and
        # exit. No client, no billing, no boundary, no live guards. The
        # frame scans run here too: what the role DID is judged from the
        # frames alone, so the reverse cases are provable without a
        # live plane (--baseline-file supplies the pre-dispatch paths,
        # --split-project the project a split round may only read).
        if not frames_file.is_file():
            return emit({"error": f"frames file not found: {frames_file}",
                         "artifact": role}, 1)
        lines = frames_file.read_text(encoding="utf-8",
                                      errors="replace").splitlines()
        baseline = set(load_json(baseline_file, []) or []) \
            if baseline_file is not None else set()
        v = judge_frames(lines)
        scan = scan_frames(lines, baseline, repo=Path("."))
        out = {"artifact": role, "offline": True,
               "frames_file": str(frames_file), **v,
               "frame_scan": scan,
               "note": ("judged from frames only; the final envelope "
                        "never decides alone")}
        project_writes: list[str] = []
        untouched = None
        if split_project is not None:
            project = split_project.resolve()
            workspace = Path(".").resolve()
            writes = frame_write_abs(lines, workspace)
            project_writes = sorted(w for w in writes
                                    if under(Path(w), project))
            if project_manifest is not None:
                untouched = untouched_report(
                    load_json(project_manifest, {}), project)
            out["split"] = {"project": str(project),
                            "workspace": str(workspace)}
        if scan["validator_invocations"]:
            out["why"] = ("the frames show the role running the validator "
                          "— the author judged its own output; the "
                          "artifact it produced is not accepted")
            return emit(out, EXIT_AUTHOR_JUDGED)
        if scan["baseline_destructions"]:
            out["why"] = ("the frames show a command removing or rewriting "
                          "a path the pre-dispatch baseline carried")
            return emit(out, EXIT_BASELINE_DESTRUCTIVE)
        if scan["cli_unavailable"] is not None:
            out["role_account"] = scan["cli_unavailable"]
            out["why"] = ("the role reported it could not run the openspec "
                          "CLI; its own account is carried and the failure "
                          "is not worked around from the caller side")
            return emit(out, EXIT_CLI_UNAVAILABLE)
        if v["interrupted"]:
            return emit(out, EXIT_INTERRUPTED)
        if project_writes:
            out["violations"] = project_writes
            out["why"] = ("the frames show the role writing inside the "
                          "project this round may only read; the paths are "
                          "named and nothing was cleaned up")
            return emit(out, EXIT_BOUNDARY)
        if untouched is not None:
            out["project_untouched"] = untouched
            if not untouched["untouched"]:
                out["violations"] = untouched["added"] \
                    + untouched["removed"] + untouched["changed"] \
                    + untouched["bookkeeping_dirs"]
                out["why"] = ("the project is not as the round found it")
                return emit(out, EXIT_BOUNDARY)
        if v["round_complete"]:
            return emit(out, 0)
        return emit(out, EXIT_INCONCLUSIVE)

    # the target's class decides where the round runs — probed, never
    # guessed from a prefix. The package names the repo; the shape check
    # is pure text and runs before anything is paid for, so a malformed
    # package never buys a copy. Everything below needs the class first
    # because the workspace decides where the artifact graph is read
    # from and what the client is invoked against.
    pkg0 = load_package(package_file, change)
    bad_shape = shape_violation(pkg0["requirement"])
    if bad_shape:
        sys.exit(emit({"rejected": "package",
                       "why": ("the requirement names a file count, a "
                               "module count or a directory layout — "
                               "structure, not behaviour; rejected before "
                               "any dispatch"),
                       "phrase": bad_shape}, EXIT_SHAPE_REJECTED))
    repo = Path(str(pkg0["repo"])).resolve()
    # the role fetches its own guidance through the authoring skill, so
    # the skill being installed and registered is a precondition of the
    # dispatch, not a discovery the role makes mid-round: without it the
    # dispatch is refused here, before the client exists, with the remedy
    skill = authoring_skill_state()
    if not skill["ok"]:
        sys.exit(emit({"artifact": role, "change": change,
                       "rejected": "authoring skill",
                       "why": ("the openspec-author skill is not installed "
                               "and registered in the gateway workspace — "
                               "the role cannot fetch its own authoring "
                               "guidance"),
                       "skill_state": skill,
                       "stopped": "before dispatch — the client was never "
                                  "invoked"},
                      EXIT_SKILL_MISSING))
    # the task dir is NOT defaulted from the project here: for a target
    # the plane cannot write, the record lives inside the round's
    # workspace, and workspace_for decides that per class

    # the acceptance-target safety rule (L7.1/L7.2): a tree holding
    # source of a dependency this project may never modify is refused
    # here, before anything is recorded and before the client exists —
    # a run pointed at such a tree could write into that source
    forbidden = forbidden_dependency_paths(repo)
    if forbidden:
        sys.exit(emit({"rejected": str(repo),
                       "stopped": "before dispatch — the client was "
                                  "never invoked",
                       "forbidden": forbidden[:20],
                       "forbidden_count": len(forbidden),
                       "why": ("the target holds source of a dependency "
                               "this project may not modify (the "
                               "never-modify rule names delegate-router / "
                               "jiuwenswarm / openjiuwen / openspec "
                               "source); a run against it could write "
                               "into that source")},
                      EXIT_FORBIDDEN_TARGET))

    # classification: read and write are probed separately, through the
    # service's own view of the filesystem — no prefix is trusted. The
    # class chooses the read side: the project in place when the plane
    # can see it, a staged copy when it cannot — the write side is the
    # plane's own tree either way. The record carries how the verdict
    # was reached.
    classification = classify_target(repo)
    if classification["class"] is None:
        sys.exit(emit({"rejected": str(repo), "change": change,
                       "classification": classification,
                       "stopped": "before dispatch — the client was never "
                                  "invoked",
                       "why": ("the target's class could not be "
                               "established — the gateway's own view of "
                               "the path could not be probed, and no "
                               "prefix is trusted to guess it")},
                      EXIT_INCONCLUSIVE))
    workspace = workspace_for(change, repo, classification,
                              task_dir=task_dir)
    if workspace.get("refused"):
        code = EXIT_INCONCLUSIVE if workspace.get("class") != "invisible" \
            else EXIT_WORKSPACE
        sys.exit(emit({"rejected": str(repo), "change": change,
                       "classification": classification,
                       "workspace": workspace,
                       "stopped": "before dispatch — the client was never "
                                  "invoked"}, code))
    task_dir = Path(workspace["task_dir"])
    ws = workspace   # every round is a split round under N6
    # the classification is recorded once per run — how the verdict was
    # reached is part of the round's record, next to the workspace it
    # chose
    def _record_class(p):
        p["target_class"] = classification
        p["workspace"] = _workspace_record(workspace)
        p["change"] = change
    update_planning(task_dir, _record_class)

    # the graph and the language context are read from the workspace —
    # that is where this round's artifacts live
    pkg, repo, prompt, _lang = prepare(change, role, package_file,
                                       workspace=ws)

    # a partial view is reported before the first dispatch (L7.6): the
    # roles plan against the working tree, and a tree showing less than
    # the head commit is a narrower view than the repository. A human
    # may accept the narrower view; the acceptance is recorded and a
    # resume does not ask again. A complete view passes silently
    view = view_state(repo)
    if view["state"] == "partial":
        prior = load_json(planning_path(task_dir), {})
        if accept_partial_view:
            prior["view"] = {"accepted": True, **view,
                             "accepted_note": ("a human accepted the narrower "
                                               "view (--accept-partial-view)"),
                             "ts": now_iso()}
            save_json(planning_path(task_dir), prior)
        elif (prior.get("view") or {}).get("accepted") is not True:
            sys.exit(emit({"artifact": role, "change": change,
                           "repo": str(repo),
                           "waiting_on": "human view acceptance",
                           "stopped": "before dispatch — the client was "
                                      "never invoked",
                           "view": view,
                           "why": ("the working tree shows fewer files than "
                                   "the head commit (a sparse or partial "
                                   "checkout); the roles would plan against "
                                   "that narrower view — a human accepts it "
                                   "with --accept-partial-view, and the "
                                   "acceptance is recorded")},
                          EXIT_INCONCLUSIVE))

    # the package is recorded before the run so a later accept can build
    # the revision prompt even if this dispatch never completes
    def _record_package(p):
        p.setdefault("packages", {})[role] = pkg
        p["change"] = change
    update_planning(task_dir, _record_package)

    # codegraph auto-dispatch (scheduling, not gating): if a brief is
    # due, dispatch it before the role opens so the author has the
    # impact brief as input.  This is on the live-dispatch path only —
    # the offline judge mode (frames_file) returned early above and
    # never reaches here (PRD §05 reverse gate).  The dispatch's outcome
    # never changes this function's exit code or stops the dispatch
    # (INV-14).
    _maybe_auto_codegraph(change, repo, task_dir)

    # work already paid for is not paid for again: when the newest
    # signed status reports this artifact done, the role is not
    # dispatched. The skip is recorded so a resume shows what was
    # reached. The status is read from the plane's records — that is
    # where this round's artifact states live.
    art = next((a for a in artifacts_view(change)
                if a.get("id") == role), None)
    if art is not None and art.get("status") == "done":
        # …unless a validator rejection is pending on this role: the
        # artifact exists but was returned for revision, and the
        # revision dispatch must run, not skip
        pending = load_json(planning_path(task_dir), {}) \
            .get("revision_pending") or {}
        if pending.get("artifact") != role:
            def _record_skip(p):
                p.setdefault("skips", {})[role] = {
                    "reason": "openspec reports this artifact done",
                    "ts": now_iso()}
            update_planning(task_dir, _record_skip)
            return emit({"artifact": role, "change": change,
                         "skipped": True,
                         "reason": ("openspec reports this artifact done — "
                                    "the role is not dispatched again"),
                         "note": ("the client was not invoked and no "
                                  "session was created; the skip is "
                                  "recorded in planning.json")}, 0)

    out, code = dispatch_role(change, role, pkg, repo, prompt, task_dir,
                              mode, timeout, ws=ws)
    if ws is None:
        # the project class says where it ran too — every class states it
        out["workspace"] = _workspace_record(workspace)
    if view["state"] == "partial":
        out["view"] = {"state": "partial", "accepted": True,
                       "note": "the narrower view was accepted by a human "
                               "before this dispatch ran"}
    return emit(out, code)


def dispatch_role(change: str, role: str, pkg: dict, repo: Path, prompt: str,
                  task_dir: Path, mode: str, timeout: int,
                  ws: dict | None = None,
                  allow_roots: tuple = ()) -> tuple[dict, int]:
    """One live dispatch, start to verdict: snapshot the boundary
    baseline, run the client with the event stream enabled, judge the
    frames, scan what the role DID, run the boundary check and decide
    the verdict. The attempt is recorded with its duration beside its
    outcome, whatever the outcome is — a fast failure records its
    duration and its failure and never reads as a fast success
    (dispatch-timing). The workspace — the plane's own tree under
    N6 — becomes the client's
    working directory and the tree the boundary judges; a split round
    guards the project grant before the client exists and verifies
    afterwards that the project is byte-for-byte as it was found.
    Returns (out, exit_code)."""
    started = time.monotonic()
    started_at = now_iso()
    session_name = f"plan-{change}-{role}"
    tree = Path(ws["path"]).resolve() if ws is not None else repo
    project = Path(ws["project"]).resolve() if ws is not None else repo
    # a masked shell (N5) cannot even stat the tree the boundary would
    # baseline — the honest stop, not a "git status failed" shrug
    masked = masked_surface_refusal(tree)
    if masked:
        return {**masked, "artifact": role, "change": change,
                "stopped": "before dispatch — the client was never "
                           "invoked"}, EXIT_FORBIDDEN_TARGET
    # the boundary baseline: what the working tree already carried
    # BEFORE this run. Pre-existing uncommitted state (an openspec init,
    # a dev's WIP) is the caller's, never the role's — only the
    # increment this dispatch causes can violate the boundary. With
    # concurrent dispatches each role carries its own baseline, so one
    # role's writes are never judged as another's increment
    # (dispatch-concurrency).
    pre_paths = git_status_paths(tree)
    if pre_paths is None:
        # G4/INV-33: distinguish "target not readable at all" (genuinely
        # indeterminate — keep "boundary": "unknown") from "git itself
        # reported a specific error on an existing path" (surface the
        # captured stderr so a human can act on it). The outcome label stays
        # "unknown" per tasks.md; the two causes are distinguishable by the
        # presence of the git_error field.
        if tree.is_dir():
            return {"artifact": role, "change": change,
                    "error": "git status failed (baseline snapshot)",
                    "boundary": "unknown",
                    "git_error": _GIT_STATUS_LAST_ERROR}, EXIT_INCONCLUSIVE
        return {"artifact": role, "change": change,
                "error": ("baseline snapshot target not readable or not a "
                          "directory: %s") % tree,
                "boundary": "unknown"}, EXIT_INCONCLUSIVE
    baseline = set(pre_paths)
    evidence = next_evidence(task_dir, role)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    pre_file = evidence.with_name(evidence.name.replace(
        ".jsonl", ".pre-boundary.json"))
    save_json(pre_file, sorted(baseline))
    # a split round states what it found: the project's manifest before
    # anything runs, compared byte-for-byte when the dispatch returns.
    # Live-read rounds only — a snapshotted round reads a private copy
    # the boundary of which the project-writes scan already judges
    manifest_before = None
    if ws is not None and ws.get("read") == "live":
        # the run's own record (.ai-dlc) is caller state, written by
        # this tool between the two manifests — outside the comparison
        manifest_before = snapshot_manifest(
            project, skip=(project / ".ai-dlc",))
        save_json(evidence.with_name(evidence.name.replace(
            ".jsonl", ".project-manifest.json")), manifest_before)
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(tree),
           "--mode", mode, "--timeout", str(timeout), "--session", session_name]
    if ws is not None:
        cmd = split_client_cmd(cmd, ws)
        problems = split_trust_guard(cmd, ws)
        if problems:
            # the grant is checked here, before any process exists, so a
            # run that would strand a role — granted only its working
            # directory, refusing to read the project, waiting on a
            # confirmation no headless run can answer — never starts
            out = {"artifact": role, "change": change, "mode": mode,
                   "repo": str(repo), "client": CLIENT,
                   "session_name": session_name,
                   "workspace": _workspace_record(ws),
                   "evidence": str(evidence),
                   "started_at": started_at, "ended_at": now_iso(),
                   "elapsed_seconds": round(time.monotonic() - started, 3),
                   "stopped": ("before dispatch — the client was never "
                               "invoked"),
                   "problems": problems,
                   "why": ("a split dispatch grants two locations: the "
                           "workspace as the working directory and the "
                           "project as a trusted location for reading; "
                           "with only the workspace granted the role "
                           "refuses the project and the round cannot "
                           "run")}
            _record_ws_attempt(task_dir, role, session_name, out,
                               EXIT_WORKSPACE, started_at, started)
            out["planning_record"] = str(planning_path(task_dir))
            return out, EXIT_WORKSPACE
    timed_out = False
    client_rc = None
    try:
        with evidence.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                                  text=True, cwd=str(tree),
                                  timeout=timeout + 60)
        client_rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True

    frames = evidence.read_text(encoding="utf-8",
                                errors="replace").splitlines()
    v = judge_frames(frames)
    did = scan_frames(frames, baseline, tree)

    scan = boundary_scan(tree, change,
                         extra_roots=(task_dir, *allow_roots),
                         baseline=baseline)
    elapsed_seconds = round(time.monotonic() - started, 3)
    ended_at = now_iso()

    # a split round's own checks: nothing the frames show the role
    # writing may land inside the project, and a live-read round's
    # project must come out byte-for-byte as it went in — bookkeeping
    # directories included
    project_writes: list[str] = []
    untouched = None
    if ws is not None:
        writes = frame_write_abs(frames, tree)
        # named project-relative: the read side's own naming, what the
        # phase-level disjointness map and the report both speak
        project_writes = sorted(_repo_relative(w, project) or w
                                for w in writes
                                if under(Path(w), project))
        if ws.get("read") == "live":
            untouched = untouched_report(manifest_before, project,
                                         skip=(project / ".ai-dlc",))

    out = {"artifact": role, "change": change, "mode": mode,
           "repo": str(repo), "client": CLIENT,
           "client_rc": client_rc, "timed_out": timed_out,
           "evidence": str(evidence), "baseline_file": str(pre_file),
           "session_name": session_name,
           "usage_record": (f"{os.path.expanduser('~/.jiuwenswarm/agent/sessions/')}"
                            f"{session_name}/history.jsonl"),
           "started_at": started_at, "ended_at": ended_at,
           "elapsed_seconds": elapsed_seconds,
           "round_complete": v["round_complete"], "interrupted": v["interrupted"],
           "events": v["events"],
           "final_envelope_seen": v["final_envelope_seen"],
           "final_envelope_claims_ok": v["final_envelope_claims_ok"],
           "authoring_skill": {"skill": AUTHORING_SKILL,
                               "verified_before_dispatch": True},
           "frame_scan": did,
           "envelope_note": ("the final envelope never decides the "
                             "verdict — the frames do"),
           **boundary_report(change, tree, scan)}
    if ws is not None:
        out["workspace"] = _workspace_record(ws)
    if untouched is not None:
        out["project_untouched"] = untouched
    # every offending path this dispatch saw, named against the tree it
    # lands in — the phase round's disjointness map reads this one list
    out["offending"] = sorted(
        set((scan.get("offending") or []) + project_writes))
    if v["interrupted"]:
        out["tool"] = v["tool"]
        out["argument"] = v["argument"]

    # the verdict, decided once here; the record below carries it beside
    # the duration so a later read never reconstructs it
    code = 0
    if "error" in scan:
        out["boundary"] = "unknown"
        code = EXIT_INCONCLUSIVE
    elif did["validator_invocations"]:
        out["violations"] = did["validator_invocations"]
        out["why"] = ("the frames show the role running the validator — "
                      "the author judged its own output; the artifact it "
                      "produced is not accepted on this dispatch")
        code = EXIT_AUTHOR_JUDGED
    elif did["baseline_destructions"]:
        out["violations"] = did["baseline_destructions"]
        out["why"] = ("the frames show a command removing or rewriting a "
                      "path the pre-dispatch baseline carried; the command "
                      "and the path are named and nothing was cleaned up")
        code = EXIT_BASELINE_DESTRUCTIVE
    elif did["cli_unavailable"] is not None:
        out["role_account"] = did["cli_unavailable"]
        out["why"] = ("the role reported it could not run the openspec CLI; "
                      "its own account is carried and the failure is not "
                      "worked around by supplying the guidance in the prompt")
        code = EXIT_CLI_UNAVAILABLE
    elif v["interrupted"]:
        code = EXIT_INTERRUPTED
    elif project_writes:
        out["violations"] = project_writes
        out["why"] = ("the frames show the role writing inside the "
                      "project this round may only read; the paths are "
                      "named and nothing was cleaned up")
        code = EXIT_BOUNDARY
    elif untouched is not None and not untouched["untouched"]:
        out["violations"] = untouched["added"] + untouched["removed"] \
            + untouched["changed"] + untouched["bookkeeping_dirs"]
        out["why"] = ("the project is not as the round found it — paths "
                      "were added, removed or changed, or a gateway "
                      "bookkeeping directory was left behind; every path "
                      "is named and nothing was cleaned up")
        code = EXIT_BOUNDARY
    elif scan["offending"]:
        out["why"] = ("the product surface names paths outside the change "
                      "dir and outside the gateway bookkeeping dirs; "
                      "nothing was cleaned up")
        code = EXIT_BOUNDARY
    elif timed_out or not v["round_complete"]:
        out["why"] = ("no round-complete frame and no interrupt frame — "
                      "the stream is inconclusive" if not timed_out else
                      f"the client exceeded the timeout ({timeout}s + 60s "
                      "grace)")
        code = EXIT_INCONCLUSIVE

    # the dispatch record a resume reads: which roles were reached, how
    # many attempts, what session, what the frames said, how long the
    # dispatch took and how it ended. The session name is deterministic,
    # so a later dispatch of the same role sends the client the same
    # name — and a named session is reused by the client's own contract,
    # so the re-dispatch continues that conversation instead of starting
    # over.
    def _record(p):
        prev = p.setdefault("dispatches", {}).get(role, {})
        attempts = int(prev.get("attempts", 0)) + 1
        record = {
            "session_name": session_name, "attempts": attempts,
            "client_rc": client_rc, "timed_out": timed_out,
            "round_complete": v["round_complete"],
            "interrupted": v["interrupted"],
            "boundary_offenders": len(scan.get("offending", [])),
            "evidence": str(evidence),
            "started_at": started_at, "ended_at": ended_at,
            "elapsed_seconds": elapsed_seconds, "outcome": code,
            "recorded_at": now_iso()}
        if ws is not None:
            record["workspace"] = _workspace_record(ws)
        # what the frames show the role DOING, recorded when it crossed a
        # checked line: the acceptor refuses an artifact whose latest
        # dispatch carries these, and a later clean dispatch replaces the
        # record wholesale — the latest attempt is what counts
        if did["validator_invocations"] or did["baseline_destructions"] \
                or did["cli_unavailable"] is not None:
            record["frame_violations"] = {
                k: did[k] for k in ("validator_invocations",
                                    "baseline_destructions",
                                    "cli_unavailable") if did[k]}
        if project_writes:
            record.setdefault("frame_violations", {})
            record["frame_violations"]["project_writes"] = project_writes
        if untouched is not None and not untouched["untouched"]:
            record["project_not_untouched"] = True
        p["dispatches"][role] = record
    planning = update_planning(task_dir, _record)
    out["planning_record"] = str(planning_path(task_dir))
    attempts = planning["dispatches"][role]["attempts"]
    if attempts > 1:
        out["resume"] = {
            "prior_attempts": attempts - 1, "session_name": session_name,
            "note": ("the same named session is sent to the client; the "
                     "client reuses it, so this dispatch continues the "
                     "prior conversation rather than starting over")}
    return out, code


def _workspace_record(ws: dict) -> dict:
    """The workspace facts a record carries: the kind, the class it came
    from, the paths, and for a staged copy what the copy cost. Kept
    small — this lands in planning.json on every dispatch."""
    rec = {"kind": ws.get("kind"), "class": ws.get("class"),
           "path": ws.get("path"), "project": ws.get("project"),
           "scratch": ws.get("scratch"), "stage": ws.get("stage"),
           "task_dir": ws.get("task_dir"),
           "plane_root": ws.get("plane_root")}
    if ws.get("read"):
        rec["read"] = ws.get("read")
        rec["snapshotted"] = ws.get("snapshotted")
        rec["starting_revision"] = ws.get("starting_revision")
    if ws.get("read") == "live":
        rec["project_read_live_note"] = (
            "the project was read live, not snapshotted — it may "
            "change underneath the round")
    if ws.get("earlier_copy_not_reused"):
        rec["earlier_copy_not_reused"] = ws["earlier_copy_not_reused"]
        rec["earlier_copy_note"] = ws.get("earlier_copy_note")
    if ws.get("staging"):
        rec["staging"] = {k: ws["staging"].get(k) for k in
                          ("source", "copy", "taken_at", "duration_seconds",
                           "size_bytes", "source_revision", "self_contained",
                           "why_read_in_place_impossible")}
    return rec


def _record_ws_attempt(task_dir: Path, role: str, session_name: str,
                       out: dict, code: int, started_at: str,
                       started: float) -> None:
    """A dispatch refused before the client existed is still an attempt:
    the record carries it with its outcome, so a resume never mistakes a
    refused dispatch for one that never ran."""
    def _record(p):
        prev = p.setdefault("dispatches", {}).get(role, {})
        p["dispatches"][role] = {
            "session_name": session_name,
            "attempts": int(prev.get("attempts", 0)) + 1,
            "client_rc": None, "timed_out": False,
            "round_complete": False, "interrupted": False,
            "boundary_offenders": 0,
            "evidence": out.get("evidence"),
            "started_at": started_at, "ended_at": now_iso(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "outcome": code,
            "workspace": out.get("workspace"),
            "stopped_before_client": True,
            "recorded_at": now_iso()}
    update_planning(task_dir, _record)


# ── plane tool dispatches: validate / status / graph ─────────────────
#
# The three commands the caller needs from the plane are dispatched as
# sessions of their own — never run caller-side (containment PRD, the
# whole point). One session runs the command(s) its prompt names; the
# caller judges ONLY the frames: every named command must appear as its
# normalized literal (absolute path, no metacharacters), and its rc and
# output are read from the matching tool result. The model's own
# conclusions are never read, so a session cannot talk its way to a
# verdict — and a session that never runs the literal fails with exit
# 23 regardless of what it claims (N1).

def normalized_validate_argv(change: str) -> list[str]:
    """§5's normalized validator literal: the absolute binary path, the
    change id, --strict, --json — nothing else anywhere in it."""
    return [NORMALIZED_VALIDATE_BIN, "validate", change, "--strict",
            "--json"]


def normalized_status_argv(change: str) -> list[str]:
    return [NORMALIZED_VALIDATE_BIN, "status", "--json", "--change",
            change]


def normalized_instructions_argv(change: str, artifact: str) -> list[str]:
    return [NORMALIZED_VALIDATE_BIN, "instructions", artifact,
            "--change", change, "--json"]


def _plane_command_prompt(title: str, argvs: list[list[str]],
                          follow_on: str = "") -> str:
    """The prompt of a plane tool dispatch: run these exact commands,
    nothing else, report the outputs. The prompt carries the literal
    argvs so the session knows the exact form; the gate on the other
    side is the frames', so a session that paraphrases the command into
    another shape fails its dispatch no matter what the prompt said."""
    lines = [title, "",
             "Run each of these commands with the bash tool, exactly as "
             "written — absolute path, no pipes, no redirects, no shell "
             "wrappers beyond the tool's own, no extra commands:"]
    for argv in argvs:
        # shlex-quoted, so an argument that carries spaces (the
        # write-back commit's message) survives the prompt as ONE
        # argument — the gate shlex-splits the frames' command back to
        # the argv, and an unquoted join could never round-trip that
        lines.append("- " + " ".join(shlex.quote(a) for a in argv))
    lines += ["", "When every command has run, reply DONE. If a command "
                  "cannot run at all, still reply DONE — do not run "
                  "anything in its place."]
    if follow_on:
        lines += ["", follow_on]
    return "\n".join(lines)


def run_plane_session(change: str, verb: str, prompt: str, repo: Path,
                      task_dir: Path, mode: str,
                      timeout: int) -> tuple[dict, int]:
    """One plane tool session, start to frames. A FRESH session every
    time (N1: validate opens a new session, never a continuing one —
    the verifier must not inherit the author's conversation). The
    attempt is recorded beside its duration like an author dispatch;
    the judging is the caller's, in the cmd_* that invoked this."""
    started = time.monotonic()
    started_at = now_iso()
    evidence = next_evidence(task_dir, verb)
    # a FRESH session every time: the sequence number of this attempt's
    # own evidence file names it, so even two dispatches inside one
    # second never share a session (the client reuses a named session,
    # and the verifier must not inherit the author's conversation)
    seq = re.search(r"-(\d+)\.jsonl$", evidence.name)
    session_name = f"{verb}-{change}-{seq.group(1) if seq else '001'}"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    # N6: the spec tree lives in the plane's own home, so the tool
    # session's working directory is the plane root — the repo is not
    # where the tree stands anymore, and a session run there sees no
    # openspec surface at all
    root = plane_root(repo)
    # a masked shell (N5) cannot stat the plane root, and the client
    # itself is started FROM there — the honest stop, not a migrate
    masked = masked_surface_refusal(root)
    if masked:
        return {**masked, "exit_code": EXIT_FORBIDDEN_TARGET,
                "change": change, "verb": verb,
                "plane_root": str(root),
                "stopped": "before dispatch — the client was never "
                           "invoked"}, EXIT_FORBIDDEN_TARGET
    if not root.is_dir():
        return {"rejected": str(repo), "change": change, "verb": verb,
                "plane_root": str(root),
                "stopped": "before dispatch — the client was never "
                           "invoked",
                "why": ("the plane holds no tree for this repository — "
                        "the tool session has no openspec surface to "
                        "run against"),
                "remedy": "plan.py migrate --repo <repo> (one time)"}, \
            EXIT_INCONCLUSIVE
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(root),
           "--mode", mode, "--timeout", str(timeout),
           "--session", session_name]
    timed_out = False
    client_rc = None
    try:
        with evidence.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                                  text=True, cwd=str(root),
                                  timeout=timeout + 60)
        client_rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    frames = evidence.read_text(encoding="utf-8",
                                errors="replace").splitlines()
    v = judge_frames(frames)
    elapsed_seconds = round(time.monotonic() - started, 3)
    ended_at = now_iso()
    out = {"dispatch": verb, "change": change, "mode": mode,
           "repo": str(repo), "client": CLIENT,
           "client_rc": client_rc, "timed_out": timed_out,
           "evidence": str(evidence),
           "session_name": session_name,
           "started_at": started_at, "ended_at": ended_at,
           "elapsed_seconds": elapsed_seconds,
           "round_complete": v["round_complete"],
           "interrupted": v["interrupted"],
           "commands_seen": [c["command"] for c in
                             _dedup_calls(frame_shell_commands(frames))],
           "envelope_note": ("the final envelope never decides the "
                             "verdict — the frames do"),
           "stopped": ("the client exceeded the timeout "
                       f"({timeout}s + 60s grace)" if timed_out else None),
           "frames": frames}
    def _record(p):
        attempts = p.setdefault("plane_dispatches", {}).setdefault(verb, {})
        n = int(attempts.get("attempts", 0)) + 1
        p["plane_dispatches"][verb] = {
            "session_name": session_name, "attempts": n,
            "client_rc": client_rc, "timed_out": timed_out,
            "round_complete": v["round_complete"],
            "interrupted": v["interrupted"],
            "commands_seen": len(out["commands_seen"]),
            "evidence": str(evidence),
            "started_at": started_at, "ended_at": ended_at,
            "elapsed_seconds": elapsed_seconds,
            "recorded_at": now_iso()}
    update_planning(task_dir, _record)
    return out, 0


def _normalized_failure(out: dict, argvs: list[list[str]],
                        why_missing: list[str]) -> tuple[dict, int]:
    """The exit-23 shape: a plane dispatch whose frames carry no
    normalized call for a command it owed. The commands the session did
    run are carried in full — the evidence of what happened instead of
    the literal — and no record is written: a verdict exists only for a
    command the frames show the plane running."""
    return ({"rejected": "plane dispatch",
             "dispatch": out["dispatch"], "change": out["change"],
             "why": ("the frames carry no normalized call for: "
                     + "; ".join(" ".join(a) for a in argvs)
                     + ("" if not why_missing else
                        " — " + "; ".join(why_missing))),
             "normalized_literals": [" ".join(a) for a in argvs],
             "commands_seen": out["commands_seen"],
             "evidence": out["evidence"],
             "remedy": ("re-dispatch with plan.py "
                        f"{out['dispatch']} --change {out['change']} "
                        "--repo <repo>; the session must run each "
                        "command exactly as written — absolute path, no "
                        "pipes, no redirects")},
            EXIT_NO_NORMALIZED_CALL)


def cmd_validate(change: str, repo: Path, task_dir: Path | None,
                 mode: str, timeout: int) -> int:
    """N1 — the validate dispatch: one fresh session whose only
    business is the normalized validator literal. The verdict is
    written as a signed record (N4) carrying rc and the validator's
    stdout verbatim — spec_valid or spec_invalid is the record's to
    state, never the model's, and never this caller's own run."""
    task_dir = task_dir or default_task_dir(repo, change)
    argv = normalized_validate_argv(change)
    out, _ = run_plane_session(
        change, "validate",
        _plane_command_prompt(
            f"Validate openspec change {change} in this repository.",
            [argv]),
        repo, task_dir, mode, timeout)
    if out.get("refused") or "frames" not in out:
        return emit(out, out.get("exit_code", EXIT_INCONCLUSIVE))
    frames = out.pop("frames")
    calls = normalized_calls(frames, argv)
    if not calls or calls[-1]["result"] is None \
            or calls[-1]["result"]["rc"] is None:
        missing = []
        if calls and calls[-1]["result"] is None:
            missing = ["the tool result for the normalized call never "
                       "arrived in the frames"]
        elif calls and calls[-1]["result"]["rc"] is None:
            missing = ["the tool result carries no readable exit code"]
        return emit(*_normalized_failure(out, [argv], missing))
    res = calls[-1]["result"]
    out.update({"argv": argv, "rc": res["rc"], "stdout": res["stdout"],
                "stderr": res["stderr"], "sha256": hashlib.sha256(
                    res["stdout"].encode("utf-8")).hexdigest()})
    record = {"verb": "validate", "argv": argv, "rc": res["rc"],
              "stdout": res["stdout"], "sha256": out["sha256"],
              "change": change, "ts": now_iso(),
              "session": out["session_name"]}
    out["record"] = str(write_record(change, "verdict", record))
    out["spec_state"] = "spec_valid" if res["rc"] == 0 else "spec_invalid"
    out["note"] = ("the verdict is the frames' — the model's conclusion "
                   "sentence was never read; deliver reads this record "
                   "and nothing else")
    return emit(out, 0)


def cmd_status(change: str, repo: Path, task_dir: Path | None,
               mode: str, timeout: int) -> int:
    """The status dispatch: one session running the normalized status
    literal. The stdout is parsed HERE into artifact states — the same
    JSON the caller once parsed from its own run, now read from the
    plane's command output — and signed as a status record of its own
    (PRD §8: graph, artifact-status and verdict are three records; the
    validate dispatch runs one command and cannot carry this)."""
    task_dir = task_dir or default_task_dir(repo, change)
    argv = normalized_status_argv(change)
    out, _ = run_plane_session(
        change, "status",
        _plane_command_prompt(
            f"Report openspec artifact status for change {change}.",
            [argv]),
        repo, task_dir, mode, timeout)
    if out.get("refused") or "frames" not in out:
        return emit(out, out.get("exit_code", EXIT_INCONCLUSIVE))
    frames = out.pop("frames")
    calls = normalized_calls(frames, argv)
    if not calls or calls[-1]["result"] is None:
        return emit(*_normalized_failure(out, [argv], []))
    res = calls[-1]["result"]
    out.update({"argv": argv, "rc": res["rc"], "stdout": res["stdout"]})
    if res["rc"] != 0:
        out["why"] = ("the plane's status command itself failed; its "
                      "output verbatim: " + res["stdout"])
        return emit(out, EXIT_INCONCLUSIVE)
    try:
        st = json.loads(res["stdout"])
    except json.JSONDecodeError:
        out["why"] = ("the status output is not JSON — carried verbatim "
                      "in stdout; nothing is guessed from it")
        return emit(out, EXIT_INCONCLUSIVE)
    if not isinstance(st, dict) or not isinstance(st.get("artifacts"),
                                                  list):
        out["why"] = "the status output carries no artifact list"
        return emit(out, EXIT_INCONCLUSIVE)
    states = {}
    for a in st["artifacts"]:
        if isinstance(a, dict) and a.get("id") is not None:
            states[str(a["id"])] = str(a.get("status") or "unknown")
    record = {"verb": "status", "argv": argv, "artifacts": states,
              "is_planning_complete":
                  bool(st.get("isPlanningComplete")),
              "change": change, "ts": now_iso(),
              "session": out["session_name"]}
    out["record"] = str(write_record(change, "status", record))
    out["artifacts"] = states
    out["is_planning_complete"] = bool(st.get("isPlanningComplete"))
    return emit(out, 0)


def cmd_graph(change: str, repo: Path, task_dir: Path | None,
              mode: str, timeout: int) -> int:
    """N3 — the graph dispatch: the one time a change's artifact graph
    is produced. One session runs the normalized status literal, then
    the normalized instructions literal for every artifact that status
    reported; the graph — ids, dependency edges and each conditional
    artifact's own inclusion conditions, verbatim from its instruction
    — is derived HERE from those outputs, mechanically, and signed as
    the change's graph record. The change's life never recomputes it:
    roles, preflight and the acceptor read this record."""
    task_dir = task_dir or default_task_dir(repo, change)
    status_argv = normalized_status_argv(change)
    out, _ = run_plane_session(
        change, "graph",
        _plane_command_prompt(
            f"Collect the artifact graph inputs for openspec change "
            f"{change}.",
            [status_argv],
            follow_on=(
                "Then run the same tool for the instructions of every "
                "artifact id the first command reported, one at a time "
                "and in the order it reported them:\n"
                f"- {' '.join(normalized_instructions_argv(change, '<artifact-id>'))}")),
        repo, task_dir, mode, timeout)
    if out.get("refused") or "frames" not in out:
        return emit(out, out.get("exit_code", EXIT_INCONCLUSIVE))
    frames = out.pop("frames")
    calls = normalized_calls(frames, status_argv)
    if not calls or calls[-1]["result"] is None:
        return emit(*_normalized_failure(out, [status_argv], []))
    res = calls[-1]["result"]
    if res["rc"] != 0:
        out["why"] = ("the plane's status command itself failed; its "
                      "output verbatim: " + res["stdout"])
        return emit(out, EXIT_INCONCLUSIVE)
    try:
        st = json.loads(res["stdout"])
    except json.JSONDecodeError:
        out["why"] = ("the status output is not JSON — carried verbatim "
                      "in stdout; nothing is guessed from it")
        return emit(out, EXIT_INCONCLUSIVE)
    raw = [a for a in (st.get("artifacts") or [])
           if isinstance(a, dict) and a.get("id") is not None]
    if not raw:
        out["why"] = "the status output carries no artifact list"
        return emit(out, EXIT_INCONCLUSIVE)

    # every artifact's instruction, from the same frames: each must
    # appear as its own normalized call, or the graph is incomplete
    instructions: dict[str, str] = {}
    missing: list[str] = []
    missing_argv: list[list[str]] = []
    for a in raw:
        aid = str(a["id"])
        argv = normalized_instructions_argv(change, aid)
        icalls = normalized_calls(frames, argv)
        why_missing = None
        if not icalls or icalls[-1]["result"] is None:
            why_missing = " ".join(argv)
            missing_argv.append(argv)
        elif icalls[-1]["result"]["rc"] != 0:
            why_missing = (" ".join(argv) + " exited "
                           + str(icalls[-1]["result"]["rc"]))
            missing_argv.append(argv)
        else:
            # the command's output is JSON carrying the instruction
            # prose — the conditions are read from that prose, verbatim
            try:
                instr = json.loads(icalls[-1]["result"]["stdout"])
            except json.JSONDecodeError:
                instr = None
            if not isinstance(instr, dict) \
                    or not isinstance(instr.get("instruction"), str):
                why_missing = ("the instructions output for " + aid
                               + " is not the JSON the plane's tool "
                                 "returns — its conditions cannot be "
                                 "read")
                missing_argv.append(argv)
            else:
                instructions[aid] = instr["instruction"]
        if why_missing is not None:
            missing.append(why_missing)
    if missing:
        out["why"] = ("the frames carry no usable instructions result "
                      "for every artifact — the graph would be "
                      "incomplete, and nothing may be filled in from "
                      "memory")
        return emit(*_normalized_failure(out, missing_argv, missing))
    arts = []
    for a in raw:
        aid = str(a["id"])
        conds = instruction_conditions(instructions.get(aid, ""))
        arts.append({"id": aid,
                     "requires": [str(r) for r in a.get("requires", [])],
                     "conditional": bool(conds),
                     "conditions": conds})
    record = {"verb": "graph", "schema": st.get("schemaName"),
              "change": change, "artifacts": arts,
              "produced_at": now_iso(),
              "session": out["session_name"]}
    out["record"] = str(write_record(change, "graph", record))
    out["schema"] = record["schema"]
    out["artifacts"] = arts
    out["note"] = ("derived mechanically from the plane's own command "
                   "outputs — conditions verbatim from each artifact's "
                   "instruction; nothing was asked of the model's "
                   "judgment and nothing was inferred here")
    return emit(out, 0)


def cmd_migrate(repo: Path) -> int:
    """N6 — move the project's openspec tree into the plane's home, one
    time. A plain filesystem move plus a git init of the plane root (so
    the boundary check judges increments exactly as it always has) plus
    the plane's ownership: swarm, group-readable, not world-readable —
    the ownership G4/G5 lean on when the caller's shell stops being
    root. No openspec command runs here and nothing inside the tree is
    built, mirrored or copied (D12): the tree changes ADDRESS, and the
    repo loses its openspec/ for the working period by design (R5) —
    the archive dispatch writes it back at close."""
    repo = repo.resolve()
    src = repo / "openspec"
    root = plane_root(repo)
    tree = root / "openspec"
    if tree.exists():
        if src.exists():
            return emit(
                {"rejected": str(repo), "plane_tree": str(tree),
                 "repo_tree": str(src),
                 "why": ("both trees exist — the plane already holds one "
                         "for this repo while the repo still carries "
                         "its own; which is real is a person's call, not "
                         "a move this command may make"),
                 "remedy": ("remove or rename one of them by hand, then "
                            "re-run")}, EXIT_INCONCLUSIVE)
        return emit({"repo": str(repo), "plane_root": str(root),
                     "plane_tree": str(tree), "moved": False,
                     "already_migrated": True,
                     "note": ("the plane tree already stands; nothing "
                              "was touched")}, 0)
    root.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.move(str(src), str(tree))
    else:
        # a project with no spec tree yet: the plane home gets an empty
        # one — the change directories the first round creates land
        # inside it
        tree.mkdir(parents=True, exist_ok=True)
    # the plane root is a git tree so the dispatch boundary judges the
    # increment the way it always has — status only, no history needed
    if not (root / ".git").exists():
        run(["git", "init", "-q", str(root)])
    # the plane's ownership: swarm owns its surface, the group may read,
    # the world may not — G4/G5's basis (enforced when the caller's
    # shell stops being root; the gateway writes as root regardless)
    run(["chown", "-R", "swarm:swarm", str(root)])
    for d in (root, tree):
        run(["chmod", "0750", str(d)])
    out = {"repo": str(repo), "plane_root": str(root),
           "plane_tree": str(tree),
           "moved": bool(src.is_dir() or src.exists()),
           "repo_tree_now": str(src),
           "repo_openspec_exists_after": src.exists(),
           "owner": "swarm:swarm", "mode": "0750",
           "note": ("the repo's openspec/ is gone by design for the "
                    "working period (R5); commit its removal, and the "
                    "archive dispatch writes the tree back at close")}
    return emit(out, 0)


# ── N2: the archive dispatch ────────────────────────────────────────

def normalized_archive_argv(change: str, skip_specs: bool) -> list[str]:
    """§7 N2's normalized archive literal: the absolute binary, the
    change id, --yes, --json — and --skip-specs exactly when the close
    carried it. One shape, so the frames' gate is an equality, not a
    judgement."""
    argv = [NORMALIZED_VALIDATE_BIN, "archive", change]
    if skip_specs:
        argv.append("--skip-specs")
    argv += ["--yes", "--json"]
    return argv


def archive_name_for(change: str) -> str:
    """The directory name archive will give the change: the local date
    prefixed, unless the change id already carries a date prefix
    (upstream keeps such names — dist/core/archive.js's
    ARCHIVE_DATE_PREFIX_PATTERN). Predicted only to BUILD the
    write-back literals; what actually stands afterwards is read from
    the tree, never from this prediction."""
    if re.match(r"^\d{4}-\d{2}-\d{2}-", change):
        return change
    return time.strftime("%Y-%m-%d") + "-" + change


def plane_user_ids() -> tuple[int | None, int | None]:
    """The uid/gid the plane's own state carries. None when the account
    is absent — the ownership checks then report instead of guessing."""
    try:
        pw = pwd.getpwnam(PLANE_USER)
    except KeyError:
        return None, None
    try:
        gid = grp.getgrnam(PLANE_GROUP).gr_gid
    except KeyError:
        gid = pw.pw_gid
    return pw.pw_uid, gid


def masked_surface_refusal(path: Path) -> dict | None:
    """N5's aidlc-shell masks the plane's specs home from the caller.
    A CLI that must READ the plane's tree cannot run inside it — and
    must not mistake the mask for a missing tree (handing out a migrate
    remedy that would fail) or judge from what it cannot see. The
    honest stop names the mask; the plane-sight commands run from the
    operator's shell."""
    try:
        os.stat(path)
        return None
    except PermissionError:
        return {"refused": True, "checked": str(path),
                "why": ("the plane's surface is not readable from this "
                        "shell — aidlc-shell masks the specs home (N5), "
                        "and this command's proof is read from the "
                        "tree, never guessed"),
                "remedy": ("run it from the operator's shell, outside "
                           "aidlc-shell")}
    except FileNotFoundError:
        return None


def plane_surface_state(root: Path) -> dict:
    """G6's surface half: the plane root and its tree must stand as
    migrate left them — owned by the plane's account, group-readable,
    not world-readable. An altered surface (a chmod, a chown) is a
    refusal, not a repair: the archive dispatch does not bless a tree
    whose boundary was moved by hand."""
    uid, gid = plane_user_ids()
    problems = []
    if uid is None:
        problems.append(f"the {PLANE_USER} account does not exist on "
                        "this host — ownership cannot be judged")
    for d in (root, root / "openspec"):
        if not d.is_dir():
            problems.append(f"{d} does not stand")
            continue
        st = d.stat()
        if uid is not None and st.st_uid != uid:
            problems.append(f"{d} is owned by uid {st.st_uid}, not the "
                            f"plane's {PLANE_USER} (uid {uid})")
        if gid is not None and st.st_gid != gid:
            problems.append(f"{d} is group {st.st_gid}, not "
                            f"{PLANE_GROUP} (gid {gid})")
        if oct(st.st_mode & 0o777) != "0o750":
            problems.append(f"{d} is mode "
                            f"{oct(st.st_mode & 0o777)[2:]}, not 750")
    return {"ok": not problems, "problems": problems,
            "checked": [str(root), str(root / "openspec")],
            "expected": f"{PLANE_USER}:{PLANE_GROUP} 0750",
            "note": ("the surface's ownership and mode are the boundary "
                     "G4/G5 bite on when the caller's shell stops being "
                     "root; the archive dispatch refuses a surface that "
                     "was altered by hand")}


def handwritten_paths(change_dir: Path) -> list[str]:
    """G6's content half: paths under the change dir the plane did not
    write. Today the service writes as root, so root and the plane's
    own account are the two legitimate owners and anything ELSE is
    foreign; aidlc-shell (P4) stripped the caller's capabilities but
    not its uid, so a root-written path is still not distinguishable
    from the service's — the tell this gate exists for arrives with
    P5's uid split, and the rule tightens with it. The change dir
    itself is included."""
    uid, _gid = plane_user_ids()
    if uid is None:
        return [f"<the {PLANE_USER} account does not exist on this host — "
                "ownership cannot be judged>"]
    legit = {0, uid}       # root (the service's user today) and swarm
    out = []
    st = change_dir.stat()
    if st.st_uid not in legit:
        out.append(f"{change_dir} (uid {st.st_uid})")
    for p in sorted(change_dir.rglob("*")):
        try:
            if p.stat().st_uid not in legit:
                out.append(f"{p} (uid {p.stat().st_uid})")
        except OSError as e:
            out.append(f"{p} (unreadable: {e})")
    return out


def archive_writeback_cmds(change: str, repo: Path, root: Path,
                           skip_specs: bool,
                           archive_name: str | None = None
                           ) -> tuple[list[list[str]], str]:
    """The normalized literals of the write-back: recreate the repo's
    openspec surface from the plane's tree, then record it in git. Each
    is an exact argv the frames must carry — same rule as the archive
    literal itself. The commit carries the plane's own identity so a
    plane-written archive commit is never confused with the caller's.
    archive_name overrides the predicted directory name — a resume
    targets the archive directory the earlier run actually left (which
    may carry an earlier date), never today's prediction."""
    tree = root / "openspec"
    dst = repo / "openspec"
    name = archive_name or archive_name_for(change)
    cmds = [["mkdir", "-p", str(dst / "changes" / "archive")]]
    if not skip_specs and (tree / "specs").is_dir():
        cmds.append(["cp", "-a", str(tree / "specs"), str(dst) + "/"])
    if (tree / "config.yaml").is_file():
        cmds.append(["cp", "-a", str(tree / "config.yaml"), str(dst) + "/"])
    cmds.append(["cp", "-a", str(tree / "changes" / "archive" / name),
                 str(dst / "changes" / "archive") + "/"])
    cmds.append(["git", "-C", str(repo), "add", "openspec"])
    cmds.append(["git", "-C", str(repo),
                 "-c", f"user.name=ai-dlc-plane",
                 "-c", "user.email=ai-dlc-plane@aidlc.invalid",
                 "commit", "-m", f"openspec: archive {change}"])
    return cmds, name


def cmd_archive_dispatch(change: str, repo: Path, task_dir: Path,
                         skip_specs: bool, mode: str,
                         timeout: int) -> tuple[dict, int]:
    """N2 — archive as ONE plane dispatch: the normalized archive
    literal, then the normalized write-back literals (specs and the
    archived change dir back into the repo, git add, git commit), all
    judged from the frames like every other plane command. What the
    frames say is then checked against the filesystem — the archive
    directory actually moved, the repo actually holding the surface,
    the commit actually in the log — because a dispatch's report is
    never its proof. G6 stands at the door: a change dir the plane
    does not hold, a surface altered by hand, or foreign-owned content
    refuses before any session exists. A tree whose SHAPE says the
    archive already ran (the change dir gone, an archive/<date>-<id>
    standing — the split state a failed close leaves) resumes at the
    write-back alone (I4). The signed archive record carries the
    archive command's rc and stdout verbatim — or says it resumed."""
    root = plane_root(repo)
    # a masked shell (N5 aidlc-shell) cannot even stat the plane root —
    # the honest stop names the mask, not a migrate that would fail
    masked = masked_surface_refusal(root)
    if masked:
        return {**masked, "change": change, "repo": str(repo),
                "plane_root": str(root)}, EXIT_FORBIDDEN_TARGET
    if not root.is_dir():
        return {"refused": True, "change": change, "repo": str(repo),
                "plane_root": str(root),
                "why": ("the plane holds no tree for this repository — "
                        "there is nothing to archive and nowhere the "
                        "archive could run"),
                "remedy": "plan.py migrate --repo <repo> (one time)"}, \
            EXIT_INCONCLUSIVE
    surface = plane_surface_state(root)
    if not surface["ok"]:
        return {"refused": True, "change": change, "repo": str(repo),
                "surface": surface,
                "why": ("the plane's surface does not stand as migrate "
                        "left it — the boundary was altered by hand, and "
                        "the archive dispatch does not bless that"),
                "remedy": ("restore the ownership and mode by hand "
                           f"({PLANE_USER}:{PLANE_GROUP} 0750), or "
                           "re-run migrate on a clean surface")}, \
            EXIT_FORBIDDEN_TARGET
    change_dir = root / "openspec" / "changes" / change
    archive_root = root / "openspec" / "changes" / "archive"
    resumed = False
    if not change_dir.is_dir():
        # I4 — the split state a failed close leaves behind: the plane
        # already archived (the tree SHAPE says so — the change dir
        # gone, an archive/<date>-<id> standing) and the write-back
        # never happened. Re-running the archive literal would fail
        # against a tree that no longer holds the change; the minimal
        # resume runs the write-back literals alone, against the
        # archive directory that actually stands, and the record says
        # the session resumed.
        standing = sorted(archive_root.glob(f"*-{change}")) \
            if archive_root.is_dir() else []
        if not standing:
            return {"refused": True, "change": change, "repo": str(repo),
                    "checked": str(change_dir),
                    "why": ("the change directory does not stand in the "
                            "PLANE's tree — a change written anywhere else "
                            "(the repo's own openspec/, most plausibly: a "
                            "hand-written one) is not the plane's work and "
                            "is never archived by a dispatch"),
                    "remedy": ("the change is authored through plane "
                               "dispatches or it is not archived")}, \
                EXIT_FORBIDDEN_TARGET
        resumed = True
        resume_name = standing[-1].name
        out_note = (f"the plane tree already holds archive/{resume_name} "
                    "from an earlier run — the archive literal was not "
                    "re-run; this session resumed at the write-back")
    else:
        foreign = handwritten_paths(change_dir)
        if foreign:
            return {"refused": True, "change": change, "repo": str(repo),
                    "foreign_owned": foreign[:50],
                    "foreign_count": len(foreign),
                    "why": ("content under the change dir carries an owner "
                            "the plane never writes as — hand-written "
                            "content is refused at the archive door (G6)"),
                    "remedy": ("the change is authored through plane "
                               "dispatches or it is not archived")}, \
                EXIT_FORBIDDEN_TARGET

    argv = normalized_archive_argv(change, skip_specs)
    wb_cmds, predicted = archive_writeback_cmds(
        change, repo, root, skip_specs,
        archive_name=resume_name if resumed else None)
    if resumed:
        required = wb_cmds
        title = (f"Resume the close of openspec change {change}: the "
                 "archive already stands in the plane's tree from an "
                 "earlier run — write the result back into the "
                 "repository.")
    else:
        required = [argv] + wb_cmds
        title = (f"Archive openspec change {change} and write the result "
                 "back into the repository.")
    prompt = _plane_command_prompt(
        title, required,
        "Run them in the order listed. If a command cannot run at all, "
        "still reply DONE — do not run anything in its place.")
    out, _ = run_plane_session(change, "archive", prompt, repo, task_dir,
                               mode, timeout)
    if out.get("refused") or "frames" not in out:
        return out, out.get("exit_code", EXIT_INCONCLUSIVE)
    frames = out.pop("frames")
    # every required literal must appear in the frames with a readable,
    # successful result — the same equality every plane command is
    # judged by, applied to each command the dispatch owed
    missing: list[str] = []
    results: list[dict] = []
    for need in required:
        calls = normalized_calls(frames, need)
        if not calls:
            missing.append(" ".join(need))
            continue
        res = calls[-1]["result"]
        if res is None or res.get("rc") is None:
            missing.append(" ".join(need) + " — its tool result never "
                           "arrived or carries no exit code")
            continue
        results.append({"argv": need, "rc": res["rc"],
                        "stdout": res.get("stdout"),
                        "stderr": res.get("stderr")})
    if missing:
        fail, code = _normalized_failure(out, required, missing)
        fail["g6"] = {"surface": surface}
        return fail, code
    bad = [r for r in results if r["rc"] != 0]
    if bad:
        out.update({"archive": "failed",
                    "failed_commands": bad,
                    "why": ("a command of the archive dispatch exited "
                            "non-zero; its output is carried verbatim "
                            "and nothing is reported archived"),
                    "g6": {"surface": surface}})
        return out, EXIT_CLOSE_FAILED
    # the archive record: rc and stdout verbatim, signed like every
    # plane record. A resume signs what the session actually ran — the
    # archive literal's columns stand empty rather than carrying the
    # numbers of a command that did not run
    if resumed:
        record = {"verb": "archive", "argv": None, "rc": None,
                  "stdout": "",
                  "sha256": hashlib.sha256(b"").hexdigest(),
                  "change": change, "ts": now_iso(),
                  "session": out["session_name"],
                  "resumed": True, "resumed_because": out_note,
                  "writeback": {"argvs": wb_cmds, "predicted_name": predicted,
                                "skip_specs": skip_specs}}
    else:
        arch = results[0]
        record = {"verb": "archive", "argv": argv, "rc": arch["rc"],
                  "stdout": arch["stdout"] or "",
                  "sha256": hashlib.sha256((arch["stdout"] or "")
                                           .encode("utf-8")).hexdigest(),
                  "change": change, "ts": now_iso(),
                  "session": out["session_name"],
                  "writeback": {"argvs": wb_cmds, "predicted_name": predicted,
                                "skip_specs": skip_specs}}
    out["record"] = str(write_record(change, "archive", record))

    # filesystem truth, read after the session: the frames said it ran;
    # this says it happened
    moved = not change_dir.exists()
    actual = sorted((root / "openspec" / "changes" / "archive")
                    .glob(f"*-{change}")) \
        if (root / "openspec" / "changes" / "archive").is_dir() else []
    repo_archive = sorted((repo / "openspec" / "changes" / "archive")
                          .glob(f"*-{change}")) \
        if (repo / "openspec" / "changes" / "archive").is_dir() else []
    repo_specs = (repo / "openspec" / "specs").is_dir()
    last = run(["git", "-C", str(repo), "log", "-1", "--format=%s"])
    commit_subject = (last.stdout or "").strip()
    verified = {
        "plane_change_dir_moved": moved,
        "plane_archive_dir": str(actual[-1]) if actual else None,
        "predicted_name_matched": bool(actual)
        and actual[-1].name == predicted,
        "repo_archive_dir": str(repo_archive[-1]) if repo_archive else None,
        "repo_specs_written": repo_specs or skip_specs,
        "repo_commit_subject": commit_subject,
        "repo_commit_carries_change": change in commit_subject,
    }
    out["archive"] = "dispatched"
    out["verified"] = verified
    if not (verified["plane_change_dir_moved"] and actual
            and repo_archive and verified["repo_specs_written"]
            and verified["repo_commit_carries_change"]):
        out["archive"] = "unverified"
        out["why"] = ("the frames carried every normalized command with "
                      "rc 0, but the filesystem disagrees with at least "
                      "one of them — nothing is reported archived")
        return out, EXIT_CLOSE_FAILED
    if resumed:
        out["resumed_from"] = "write-back"
        out["note"] = ("resumed at the write-back: the plane's tree "
                       "already held the archive from an earlier run, "
                       "and this session ran the write-back literals "
                       "alone — judged from its frames and checked "
                       "against the filesystem; the merge itself stayed "
                       "caller-side behind the human gate")
    else:
        out["note"] = ("archive, write-back and commit ran as one plane "
                       "dispatch, judged from its frames and then checked "
                       "against the filesystem; the merge itself stayed "
                       "caller-side behind the human gate")
    return out, 0


# ── the conditional artifact: decided before it is dispatched ───────

def instruction_conditions(instruction: str) -> list[str]:
    """The inclusion conditions the upstream instruction states for this
    artifact — the bullets under its own 'create only if' / 'when to
    include' anchor, verbatim. Empty when the instruction states none:
    the artifact is mandatory and nothing decides whether it runs."""
    low = instruction.lower()
    anchor = None
    for marker in ("create only if", "when to include"):
        idx = low.find(marker)
        if idx >= 0:
            anchor = idx
            break
    if anchor is None:
        return []
    lines = instruction[anchor:].splitlines()
    bullets = []
    for line in lines[1:]:
        s = line.strip()
        if not s or not s.startswith(("-", "*")):
            break
        bullets.append(s.lstrip(" -*").strip())
    return bullets[:6]


def conditioned_artifact_states(repo: Path, change: str) -> list[dict]:
    """The artifacts the upstream instruction makes conditional — it
    states inclusion conditions ('create only if any apply') — with the
    conditions verbatim and each artifact's current status. The
    conditions travel in the graph record; the instruction is never
    fetched caller-side."""
    out = []
    for a in artifacts_view(change):
        conds = [c for c in a.get("conditions", []) if str(c).strip()]
        if a.get("conditional") or conds:
            out.append({"artifact": a.get("id"), "status": a.get("status"),
                        "conditions": conds})
    return out


def artifact_decision(task_dir: Path, artifact: str) -> dict | None:
    d = (load_json(planning_path(task_dir), {})
         .get("artifact_decisions") or {}).get(artifact)
    return d if isinstance(d, dict) else None


# a stated decider names an actor, never a class of actor: the bare
# words below are the residue of the default this rejection ends — they
# claim a human without naming one, and an agent composing the decision
# itself says so in the value it records
HUMAN_CLASS_WORDS = ("user", "human", "person")


def cmd_decide(change: str, repo: Path, task_dir: Path | None,
               artifact: str, condition: str | None, reason: str | None,
               decided_by: str | None,
               design: str | None = None) -> int:
    """Record a decision on an artifact the upstream instruction makes
    conditional, naming who made it. The artifact runs only when one of
    the instruction's OWN conditions applies; the decision — whichever
    way it goes, with the conditions considered and the decider stated
    — is recorded before any dispatch. A claimed condition that is not
    the instruction's own is refused, a skip without a reason is
    refused, and so is a decider that is unstated or claims a human
    without naming one: an unevaluated skip and an unattributed
    decision are exactly the narration this replaces.

    `--design skip` records the same shape for the design role, whose
    applicability is measured (design-scope), not conditional on the
    instruction — a person who measured it applicable and still wants
    no beautifying says so here, with the reason, and deliver reports
    design_declined instead of design_unverified."""
    if design is not None:
        task_dir = Path(task_dir) if task_dir \
            else default_task_dir(repo, change)
        stated = str(decided_by or "").strip()
        if not stated:
            return emit({"rejected": "decided-by",
                         "why": ("a decision records who made it — the "
                                 "decider is stated by the caller, "
                                 "never assumed")}, EXIT_ROLE_REJECTED)
        if stated.lower() in HUMAN_CLASS_WORDS:
            return emit({"rejected": "decided-by",
                         "why": (f"the decider {stated!r} is a class "
                                 "word claiming a human without naming "
                                 "one; an agent records itself as an "
                                 "agent")}, EXIT_ROLE_REJECTED)
        if design != "skip" or not (reason or "").strip():
            return emit({"rejected": "design",
                         "why": ("the design decision records a skip "
                                 "with its reason (--design skip --why "
                                 "…) — anything else is not a decision "
                                 "but a narration")},
                        EXIT_ROLE_REJECTED)
        decision = {"skip": True, "why": reason,
                    "decided_by": stated, "ts": now_iso()}

        def _rec(p):
            p["design_decision"] = decision
        update_planning(task_dir, _rec)
        return emit({"recorded": decision, "task_dir": str(task_dir),
                     "note": ("deliver reads this and reports "
                              "design_declined with the reason carried "
                              "verbatim — the applicability measurement "
                              "still stands beside it")}, 0)

    # a decision belongs to the round, and the round's tree is the
    # plane's own — that is where the change the phase created lives
    classification = classify_target(repo)
    if classification is None:
        return emit({"rejected": str(repo), "change": change,
                     "classification": classification,
                     "stopped": "before the decision — no prefix is trusted "
                                "to guess the target's class"},
                    EXIT_INCONCLUSIVE)
    workspace = workspace_for(change, repo, classification,
                              task_dir=task_dir)
    if workspace.get("refused"):
        return emit({"rejected": str(repo), "change": change,
                     "workspace": workspace,
                     "stopped": "before the decision"}, EXIT_WORKSPACE)
    task_dir = Path(workspace["task_dir"])
    tree = Path(workspace["path"])
    states = conditioned_artifact_states(tree, change)
    mine = next((c for c in states if c["artifact"] == artifact), None)
    if mine is None:
        return emit({"rejected": artifact,
                     "why": ("the upstream instruction states no inclusion "
                             "conditions for this artifact — it is "
                             "mandatory and nothing decides whether it "
                             "runs"),
                     "conditional_artifacts": [c["artifact"] for c in states]},
                    EXIT_ROLE_REJECTED)
    stated = str(decided_by or "").strip()
    if not stated:
        return emit({"rejected": "decided-by",
                     "why": ("a decision records who made it — the decider "
                             "is stated by the caller, never assumed"),
                     "artifact": artifact,
                     "conditions": mine["conditions"]}, EXIT_ROLE_REJECTED)
    if stated.lower() in HUMAN_CLASS_WORDS:
        return emit({"rejected": "decided-by",
                     "why": (f"the decider {stated!r} is a class word "
                             "claiming a human without naming one — who "
                             "decided is stated by the caller, never "
                             "assumed; an agent records itself as an "
                             "agent"),
                     "artifact": artifact,
                     "decided_by": stated}, EXIT_ROLE_REJECTED)
    decision: dict = {"artifact": artifact,
                      "conditions_considered": mine["conditions"],
                      "decided_by": stated, "ts": now_iso()}
    if condition:
        match = next((c for c in mine["conditions"]
                      if condition.strip().lower() in c.lower()), None)
        if match is None:
            return emit({"rejected": "condition",
                         "why": ("the named condition is not one of the "
                                 "instruction's own — a decision may cite "
                                 "only what upstream states"),
                         "condition": condition,
                         "instruction_conditions": mine["conditions"]},
                    EXIT_ROLE_REJECTED)
        decision.update(dispatch=True, condition_matched=match,
                        reason=f"upstream condition applies: {match}")
    elif reason and reason.strip():
        decision.update(dispatch=False, condition_matched=None,
                        reason=reason)
    else:
        return emit({"rejected": "decision",
                     "why": ("a decision names the condition that applies "
                             "(--condition) or why none does (--skip with "
                             "--reason); an unevaluated decision is what "
                             "this command exists to prevent"),
                     "conditions": mine["conditions"]}, EXIT_ROLE_REJECTED)
    def _rec(p):
        p.setdefault("artifact_decisions", {})[artifact] = decision
    update_planning(task_dir, _rec)
    return emit({"recorded": decision, "task_dir": str(task_dir),
                 "note": ("the phase runner reads this before dispatching; "
                          "a skip means the role is never dispatched and "
                          "the decision is carried into the phase record "
                          "and the delivery surface")}, 0)


# ── what each role's frames show it writing ─────────────────────────

WRITE_TOOL_PATH_KEYS = ("path", "file_path", "notebook_path", "filePath",
                        "target_path")


def frame_write_targets(lines: list, repo: Path) -> list[str]:
    """The repo-relative paths a role's frames show it writing — shell
    redirects plus the write tools' own path arguments. Read generously:
    over-capture only ever names a role that did not write; under-capture
    is the accident."""
    raw: list[str] = []
    for call in _tool_invocations(lines):
        name = (call["tool"] or "").lower()
        if any(k in name for k in ("write", "edit", "create", "notebook")):
            for key in WRITE_TOOL_PATH_KEYS:
                p = call["arguments"].get(key)
                if isinstance(p, str) and p.strip():
                    raw.append(p)
    for c in frame_shell_commands(lines):
        raw += _normalized_targets(_strip_quoted_text(_strip_heredocs(c["command"])))
    out = []
    for t in raw:
        rel = _repo_relative(t, repo)
        if rel is not None and rel not in out:
            out.append(rel)
    return out


def frame_write_named(lines: list, tree: Path,
                      project: Path | None) -> list[str]:
    """The write paths a role's frames show, each named against the
    tree it lands in: plane-tree-relative for the round's own writes,
    project-relative for a write into the round's read side (itself a
    violation the dispatch judges on its own). One list, because the
    phase round's disjointness proof asks one question — whose frames
    carried this path — for every path any role wrote."""
    out: list[str] = []
    for w in frame_write_abs(lines, tree):
        rel = _repo_relative(w, tree)
        if rel is None and project is not None:
            rel = _repo_relative(w, project)
        if rel is not None and rel not in out:
            out.append(rel)
    return out


# ── the design-review round (design-review) ─────────────────────────
#
# A bounded adversarial round between the design artifact and the work
# that follows it. The axes are a fixed named list in the project
# configuration, each with a persona that pulls against the others; each
# reviewer is dispatched exactly like an artifact role (own session, own
# frame file, own boundary baseline) and writes exactly one finding to
# its own path under the task record. The author is then dispatched once
# more with every finding and answers each on the record. A finding is
# advice to the author: it never gates delivery, and an unanswered one
# blocks only the phase report.

EXIT_ROSTER_REJECTED = 17        # the axis/persona contract is violated
EXIT_REVIEW_CONTRACT = 18        # a reviewer or the revision broke the round's own rules
EXIT_REVIEW_UNANSWERED = 19      # a finding carries no answer

REVIEW_FINDING_HEADING = "## Finding"
REVIEW_NOTHING_HEADING = "## Nothing found"
REVIEW_EXAMINED_HEADING = "## Examined"
TEAM_MODE_REASONS = (
    "an ad-hoc team matches the wildcard configuration, so the named "
    "reviewers cannot be given to it",
    "its progress is invisible until it ends",
    "it takes an order of magnitude longer than the per-role dispatch "
    "already in use")
TEAM_MODE_RECORD = "docs/team-mode-record.md"

SYNTHESIS_HEADING = "# Synthesis"       # the file the caller writes itself
SYNTHESIS_GROUP_HEADING = "## Group"    # one per part of the design
SYNTHESIS_PAIR_HEADING = "## Opposing"  # two findings pulling apart
SYNTHESIS_NONE_HEADING = "## No opposing pairs"
# the passages a synthesis may not carry: choosing between findings is
# the author's work and the human's, never the synthesis's
SYNTHESIS_VERDICT_MARKERS = (
    "recommend", "recommends", "recommended", "recommendation",
    "prefer", "prefers", "preferred", "preference",
    "prioritise", "prioritised", "prioritize", "prioritized",
    "more important", "less important", "most important",
    "should win", "stronger finding", "weaker finding", "the better one",
    "采纳", "建议", "优先", "更重要")
# the round's roster holds equal adversarial axes only — a role that
# would synthesise or lead is refused, because the synthesis belongs to
# the caller and a leader breaks the equality the round is made of
SYNTHESIS_RESERVED_ROLES = ("synthesis", "synthesise", "synthesize",
                            "synthesizer", "leader", "chair")
SYNTHESIS_ROLE_REASON = (
    "the round's reviewers are equal by construction, and the synthesis "
    "is the caller's own step — a role dispatched to synthesise would "
    "re-read in a cold session what the caller already holds, and a "
    "leader role breaks the equality the round is made of")


def _config_lines() -> list[str]:
    path = Path(os.environ.get("AI_DLC_CONFIG") or
                (Path(__file__).resolve().parent.parent / "config"
                 / "collapsed.config.yaml"))
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def review_axes() -> dict:
    """The named axis list with each persona — what it is suspicious of,
    the trade it accepts, what it refuses — read from the project
    configuration. The list is fixed: an axis not on it is refused, and
    adding one means amending the configuration first."""
    axes: dict = {}
    section = None
    for line in _config_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace():
            section = stripped.split(":", 1)[0].strip()
            continue
        if section != "review":
            continue
        m = re.match(r"axis\.([\w-]+)\.(stance|accepts|refuses):\s*(.+)$",
                     stripped)
        if m:
            val = m.group(3).split("#", 1)[0].strip()
            axes.setdefault(m.group(1), {})[m.group(2)] = val
    return axes


def review_max_axes() -> int | None:
    """The configured ceiling on axes per round — or None when it is
    not readable; the round then stops for a person rather than
    assuming a number."""
    section = None
    for line in _config_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace():
            section = stripped.split(":", 1)[0].strip()
            continue
        if section == "review" and stripped.startswith("max_axes:"):
            val = stripped.split(":", 1)[1].split("#", 1)[0].strip()
            return int(val) if val.isdigit() else None
    return None


def roster_check(axes: dict) -> list[dict]:
    """The roster's own contract: every persona states all three parts,
    and no two share a stance — two reviewers pulling the same way is
    the convergence the round exists to prevent, caught in the roster
    before a dispatch pays for it."""
    problems: list[dict] = []
    for axis, persona in sorted(axes.items()):
        for field in ("stance", "accepts", "refuses"):
            if not (persona.get(field) or "").strip():
                problems.append({"axes": [axis],
                                 "why": f"the persona states no {field}"})
    seen: dict = {}
    for axis, persona in sorted(axes.items()):
        stance = re.sub(r"\s+", " ",
                        (persona.get("stance") or "")).strip().lower()
        if not stance:
            continue
        if stance in seen:
            problems.append({"axes": sorted([seen[stance], axis]),
                             "why": "two personas share a stance",
                             "stance": stance})
        else:
            seen[stance] = axis
    return problems


def review_dir(task_dir: Path) -> Path:
    return task_dir / "review"


def review_surface(tree: Path, change: str) -> Path:
    """Where the review round's PLANE-WRITTEN paths live: each
    reviewer's finding and the author's answers. Under containment N6
    those are written by plane sessions, so they sit inside the plane
    root — never in the project (a readable round could not write
    there) and never inside the spec tree (the plane tree carries the
    spec surface alone). The synthesis is the caller's own write and
    stays with the task record the caller owns."""
    return tree / ".ai-dlc" / "review" / change


def finding_rel(surface: Path, tree: Path, axis: str) -> str:
    """The reviewer's one path, plane-tree-relative — the only path its
    dispatch is allowed to write."""
    return (surface / axis / "finding.md") \
        .resolve().relative_to(tree.resolve()).as_posix()


def answers_rel(surface: Path, tree: Path) -> str:
    """The author's answers, plane-tree-relative."""
    return (surface / "answers.md") \
        .resolve().relative_to(tree.resolve()).as_posix()


def synthesis_rel(task_dir: Path, project: Path) -> str:
    """The synthesis's one path, project-relative — the caller's own
    write into the task record, never a dispatch's: no session is
    opened for it."""
    return (review_dir(task_dir) / "synthesis.md") \
        .resolve().relative_to(project.resolve()).as_posix()


def reviewer_prompt(change: str, axis: str, persona: dict,
                    finding_path: str) -> str:
    return f"""You are the {axis} reviewer for change {change} — an adversarial reviewer holding exactly one axis, once.

Your persona, held against the other reviewers' axes:
- suspicious of: {persona.get('stance')}
- accept as a trade: {persona.get('accepts')}
- refuse: {persona.get('refuses')}

Read openspec/changes/{change}/design.md. Follow the code it cites where your axis needs to.

Write exactly one file, this path and no other: {finding_path}
Its first line is: Axis: {axis}
Then exactly one of:
{REVIEW_FINDING_HEADING} — where in the design it applies (section or quoted line), the concern on your axis, and what you would change; or
{REVIEW_NOTHING_HEADING} — then {REVIEW_EXAMINED_HEADING} naming what you examined on your axis.

One finding only — a second finding fails the dispatch. Do not edit the design or any other file; your only write is the finding file. Do not run openspec validate. Nothing found is a valid answer; silence is not."""


def revision_prompt(change: str, findings: list[dict],
                    answers_path: str,
                    synthesis_text: str | None = None) -> str:
    body = "\n\n".join(f"### {f['axis']}\n{f['text']}" for f in findings)
    synthesis_block = ""
    if synthesis_text is not None:
        synthesis_block = f"""
A synthesis of the findings follows — a reading aid that groups them and names where they pull against each other. Your answers are owed to the findings above, each by its axis; the synthesis is not a thing to answer.

{synthesis_text}
"""
    return f"""The design you wrote for change {change} went through an adversarial review. Every finding follows, verbatim.

{body}
{synthesis_block}
Revise once, answering every finding on the record:
- where you accept a finding, change openspec/changes/{change}/design.md accordingly;
- write your answers to {answers_path} — one `### <axis>` section per finding, each carrying either `accepted: yes` plus what changed in the design, or `accepted: no` plus why it is rejected;
- every finding must be answered — an unanswered finding blocks the phase from reporting complete;
- this is one revision, not a loop; do not run openspec validate."""


def judge_finding_file(path: Path, axis: str) -> dict:
    """The reviewer's own contract, judged from the file it left: an
    axis-named record carrying exactly one finding, or an explicit
    nothing-found that names what was examined. Anything else — silence
    included — fails the dispatch."""
    if not path.is_file():
        return {"ok": False, "kind": None,
                "why": "the finding file was not written"}
    text = path.read_text(encoding="utf-8", errors="replace")
    headings = [h.strip() for h in re.findall(r"^## .+$", text, flags=re.M)]
    n_finding = headings.count(REVIEW_FINDING_HEADING)
    n_nothing = headings.count(REVIEW_NOTHING_HEADING)
    if not re.search(rf"^Axis:\s*{re.escape(axis)}\s*$", text,
                     flags=re.M | re.I):
        return {"ok": False, "kind": None,
                "why": f"the record does not name its axis ({axis})"}
    if n_finding > 1:
        return {"ok": False, "kind": "finding",
                "why": (f"{n_finding} findings are filed — the contract "
                        "is exactly one")}
    if n_finding == 1 and n_nothing == 0:
        return {"ok": True, "kind": "finding"}
    if n_nothing == 1 and n_finding == 0:
        if not re.search(rf"^{REVIEW_EXAMINED_HEADING}\s*\n+.+\S", text,
                         flags=re.M):
            return {"ok": False, "kind": "nothing",
                    "why": ("nothing found, but no record of what was "
                            "examined")}
        return {"ok": True, "kind": "nothing"}
    return {"ok": False, "kind": None,
            "why": ("the record carries neither one finding nor an "
                    "explicit nothing-found")}


def judge_answers_file(path: Path, axes: list[str]) -> tuple[dict, list]:
    """The revision's contract: one `### <axis>` section per finding,
    each carrying an explicit accepted yes/no. Returns the answers and
    the axes that carry none — the unanswered findings, by name."""
    answers: dict = {}
    if path.is_file():
        section = None
        for line in path.read_text(encoding="utf-8",
                                   errors="replace").splitlines():
            m = re.match(r"^###\s+(.+?)\s*$", line)
            if m:
                section = m.group(1).strip().lower()
                answers.setdefault(section, None)
                continue
            if section is not None and answers.get(section) is None:
                a = re.match(r"^accepted:\s*(yes|no)\b", line.strip(),
                             flags=re.I)
                if a:
                    answers[section] = a.group(1).lower() == "yes"
    unanswered = [a for a in axes if answers.get(a.strip().lower()) is None]
    return answers, unanswered


def judge_synthesis_file(path: Path, finding_axes: list[str]) -> dict:
    """The synthesis's own contract, judged from the file the caller
    wrote: every concern cites a finding a reviewer filed, every filed
    finding appears in a group, no passage picks a side between them,
    and either an opposing pair is named with what one increases and
    the other reduces, or the absence of pairs is stated outright —
    silence never stands in for that statement."""
    if not path.is_file():
        return {"ok": False, "kind": "missing", "breaches": [
            {"kind": "missing",
             "why": "the synthesis was not written"}]}
    lines = path.read_text(encoding="utf-8",
                           errors="replace").splitlines()
    breaches: list[dict] = []
    cited: list[str] = []
    groups: list[dict] = []
    pairs: list[dict] = []
    none_statement = False
    section = None          # "group" | "pair" | "none" | None
    verdict_re = re.compile(
        r"\b(" + "|".join(m for m in SYNTHESIS_VERDICT_MARKERS
                          if m.isascii()) + r")\b", re.I)

    for ln in lines:
        stripped = ln.strip()
        for m in SYNTHESIS_VERDICT_MARKERS:
            hit = (m in stripped) if not m.isascii() \
                else verdict_re.search(stripped)
            if hit:
                breaches.append({
                    "kind": "side", "passage": stripped,
                    "why": ("the synthesis picks a side — recommending "
                            "between findings or ranking them is the "
                            "author's work and the human's, never the "
                            "synthesis's")})
                break
        if stripped.startswith(SYNTHESIS_PAIR_HEADING):
            axes = re.findall(r"\[([\w-]+)\]", stripped)
            pairs.append({"axes": axes, "increases": False,
                          "reduces": False})
            section = "pair"
            continue
        if stripped.startswith(SYNTHESIS_NONE_HEADING):
            none_statement = True
            section = "none"
            continue
        if stripped.startswith(SYNTHESIS_GROUP_HEADING):
            groups.append({"where": stripped[len(
                SYNTHESIS_GROUP_HEADING):].lstrip(" —-") or
                "(unnamed part of the design)", "cites": []})
            section = "group"
            continue
        m = re.match(r"^- \[([\w-]+)\]", stripped)
        if m:
            axis = m.group(1)
            if section == "group":
                if groups:
                    groups[-1]["cites"].append(axis)
                if axis not in finding_axes:
                    breaches.append({
                        "kind": "unfiled-citation", "finding": axis,
                        "why": ("the concern cites a finding no reviewer "
                                "filed — every concern in the synthesis "
                                "maps to a filed finding")})
                elif axis not in cited:
                    cited.append(axis)
            elif section == "pair" and pairs:
                if re.search(r"\bincreases\b", stripped):
                    pairs[-1]["increases"] = True
                if re.search(r"\breduces\b", stripped):
                    pairs[-1]["reduces"] = True
        elif section == "group" and stripped.startswith("- "):
            breaches.append({
                "kind": "uncited", "passage": stripped,
                "why": ("a concern of the synthesis cites no finding — "
                        "every concern names the finding it came from")})
        elif section == "none" and stripped and not stripped.startswith(
                SYNTHESIS_GROUP_HEADING):
            pass                # the statement's body — presence is what counts

    for g in groups:
        if not g["cites"]:
            breaches.append({
                "kind": "uncited", "group": g["where"],
                "why": ("a group of the synthesis names no finding — "
                        "every concern must cite the finding it came "
                        "from")})
    for axis in finding_axes:
        if axis not in cited:
            breaches.append({
                "kind": "omitted", "finding": axis,
                "why": ("a finding filed by a reviewer appears in no "
                        "group of the synthesis")})
    for p in pairs:
        named = [a for a in p["axes"] if a not in finding_axes]
        for a in named:
            breaches.append({
                "kind": "unfiled-citation", "finding": a,
                "why": ("the opposing pair names a finding no reviewer "
                        "filed")})
        if not named and not (p["increases"] and p["reduces"]):
            breaches.append({
                "kind": "pair-incomplete", "axes": p["axes"],
                "why": ("an opposing pair must state what one increases "
                        "and what the other would reduce — both "
                        "directions, or it is not a relationship")})
    if not pairs and not none_statement:
        breaches.append({
            "kind": "no-pair-statement",
            "why": ("no opposing pair is named and no statement says "
                    "none oppose — silence does not stand in for that "
                    "statement")})
    return {"ok": not breaches, "kind": "present", "breaches": breaches,
            "groups": [{"where": g["where"], "cites": g["cites"]}
                       for g in groups],
            "opposing_pairs": [{"axes": p["axes"]} for p in pairs],
            "no_opposing_pairs": not pairs,
            "cited": cited}


def review_convergence(findings: dict) -> dict:
    """Whether two reviewers' findings restate the same concern — a
    word-overlap flag over the finding texts, recorded with the pair so
    a person can read why. Convergence is recorded, never enforced
    here: the remedy is revising the personas, which is a person's
    edit."""
    def words(t: str) -> set:
        return set(re.findall(r"[a-z]{4,}", (t or "").lower()))
    items = [(a, words(t)) for a, t in sorted(findings.items()) if t]
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, wa = items[i]
            b, wb = items[j]
            if not wa or not wb:
                continue
            overlap = len(wa & wb) / len(wa | wb)
            if overlap >= 0.6:
                pairs.append({"axes": [a, b],
                              "overlap": round(overlap, 3)})
    return {"flag": bool(pairs), "pairs": pairs,
            "note": ("convergent findings are recorded and the personas "
                     "revised before the axes run again — the round "
                     "never enforces this itself")}


def design_review_precondition(repo: Path, change: str,
                               task_dir: Path) -> tuple[str, dict | None]:
    """Why the round runs or does not: the design artifact's own state.
    'done' → the round runs; 'skipped' → it does not, and the recorded
    human decision is the reason; anything else is a phase that has not
    reached the question and waits."""
    dd = (load_json(planning_path(task_dir), {})
          .get("artifact_decisions") or {}).get("design")
    if isinstance(dd, dict) and dd.get("dispatch") is False:
        return "skipped", dd
    for a in artifacts_view(change):
        if a.get("id") == "design":
            if a.get("status") == "done":
                return "done", None
            return str(a.get("status") or "unknown"), None
    return "absent", None


def review_phase_gate(planning: dict) -> dict | None:
    """The round's hold on the phase report — and only on the report:
    when the design artifact ran, the phase is not reported complete
    until every finding is answered. A design skipped by decision
    carries no round. A finding never gates delivery; that boundary is
    the round's own spec."""
    dd = (planning.get("artifact_decisions") or {}).get("design")
    if isinstance(dd, dict) and dd.get("dispatch") is False:
        return None
    review = planning.get("review")
    if isinstance(review, dict) and review:
        if review.get("skipped") or review.get("complete"):
            return None
        unanswered = (review.get("revision") or {}).get("unanswered") or []
        if unanswered:
            return {"waiting_on": "design review",
                    "unanswered_findings": unanswered,
                    "why": ("a finding carries no answer — the phase is "
                            "not reported complete while it is "
                            "unanswered")}
        return {"waiting_on": "design review",
                "why": ("the review round is recorded but not complete")}
    design_ran = "design" in (planning.get("dispatches") or {}) \
        or (isinstance(dd, dict) and dd.get("dispatch") is True)
    if design_ran:
        return {"waiting_on": "design review round",
                "why": ("the design artifact ran and no review round is "
                        "recorded — the phase is not reported complete "
                        "without it")}
    return None


def cmd_review(change: str, repo: Path, task_dir: Path | None,
               mode: str, timeout: int, concurrency: int,
               axes_spec: str | None, stage: str,
               accept_partial_view: bool) -> int:
    """Run the adversarial round over a change's design artifact:
    dispatch one reviewer per chosen axis through the same per-role
    dispatch as every artifact role, judge each from its frames and its
    one finding file, then the caller synthesises the findings itself
    (no session is opened for that — it holds every finding already),
    and the author is dispatched once more to answer every finding with
    the synthesis alongside as a reading aid. --stage reviewers stops
    after the reviewers; --stage synthesis checks the synthesis the
    caller wrote; --stage revision resumes from there."""
    # the task dir is not defaulted from the project up here — the
    # target's class decides whether the round's record lives in the
    # project or inside its workspace. The pre-classification refusals
    # below record against the project-local default, which is right
    # for what they are: a refusal, never a round.
    axes = review_axes()
    if not axes:
        return emit({"change": change, "rejected": "review axes",
                     "why": ("the project configuration names no review "
                             "axes — the named list is the round's "
                             "roster and it is empty"),
                     "remedy": ("amend the review: section of "
                                "config/collapsed.config.yaml")},
                    EXIT_ROLE_REJECTED)
    problems = roster_check(axes)
    if problems:
        return emit({"change": change, "rejected": "reviewer roster",
                     "problems": problems,
                     "why": ("the roster's own contract is violated — a "
                             "persona is incomplete, or two share a "
                             "stance and would converge"),
                     "roster": axes}, EXIT_ROSTER_REJECTED)
    reserved = [a for a in sorted(axes)
                if a.lower() in SYNTHESIS_RESERVED_ROLES]
    if reserved:
        def _rec_reserved(p):
            p["review"] = {"rejected_roster_role": {
                "axes": reserved,
                "reason": SYNTHESIS_ROLE_REASON, "ts": now_iso()}}
        update_planning(task_dir or default_task_dir(repo, change),
                        _rec_reserved)
        return emit({"change": change, "rejected": "reviewer roster",
                     "axes": reserved,
                     "why": SYNTHESIS_ROLE_REASON,
                     "record": TEAM_MODE_RECORD,
                     "roster": axes}, EXIT_ROSTER_REJECTED)
    maximum = review_max_axes()
    if maximum is None:
        return emit({"change": change,
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "why": ("the configured maximum axes per round is "
                             "not readable — the round never assumes a "
                             "number")}, EXIT_INCONCLUSIVE)
    if mode == "team":
        def _rec_team(p):
            p["review"] = {"rejected_team_mode": {
                "reasons": list(TEAM_MODE_REASONS),
                "record": TEAM_MODE_RECORD, "ts": now_iso()}}
        update_planning(task_dir or default_task_dir(repo, change),
                        _rec_team)
        return emit({"change": change, "rejected": mode,
                     "reasons": list(TEAM_MODE_REASONS),
                     "record": TEAM_MODE_RECORD,
                     "why": ("the round runs through the per-role "
                             "dispatch already in use; team mode is "
                             "refused for the three reasons recorded in "
                             "the task record and measured in "
                             + TEAM_MODE_RECORD + " — refusing requires "
                             "no new experiment unless a proposal names "
                             "a fact that record does not cover")},
                    EXIT_ROLE_REJECTED)
    # the review round runs where the class says: against the project
    # when the plane can write it, against the round's workspace when it
    # cannot. Reviewers read the artifacts where they were authored and
    # write their findings to the same place.
    classification = classify_target(repo)
    if classification["class"] is None:
        return emit({"rejected": str(repo), "change": change,
                     "classification": classification,
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "why": ("the target's class could not be "
                             "established — the gateway's own view of "
                             "the path could not be probed")},
                    EXIT_INCONCLUSIVE)
    workspace = workspace_for(change, repo, classification,
                              task_dir=task_dir)
    if workspace.get("refused"):
        code = EXIT_INCONCLUSIVE if workspace.get("class") != "invisible" \
            else EXIT_WORKSPACE
        return emit({"rejected": str(repo), "change": change,
                     "classification": classification,
                     "workspace": workspace,
                     "stopped": "before dispatch — the client was never "
                                "invoked"}, code)
    task_dir = Path(workspace["task_dir"])
    tree = Path(workspace["path"])
    ws = workspace   # every round is a split round under N6
    forbidden = forbidden_dependency_paths(repo)
    if forbidden:
        return emit({"rejected": str(repo),
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "forbidden": forbidden[:20],
                     "why": ("the target holds source of a dependency "
                             "this project may not modify")},
                    EXIT_FORBIDDEN_TARGET)
    view = view_state(repo)
    if view["state"] == "partial":
        prior = load_json(planning_path(task_dir), {})
        if accept_partial_view:
            def _acc(p):
                p["view"] = {"accepted": True, **view,
                             "accepted_note": ("a human accepted the "
                                               "narrower view "
                                               "(--accept-partial-view)"),
                             "ts": now_iso()}
            update_planning(task_dir, _acc)
        elif (prior.get("view") or {}).get("accepted") is not True:
            return emit({"change": change, "repo": str(repo),
                         "waiting_on": "human view acceptance",
                         "stopped": "before dispatch — the client was "
                                    "never invoked",
                         "view": view}, EXIT_INCONCLUSIVE)

    # the design artifact's state is read where the round authored it —
    # the workspace tree, not the project a readable round never wrote
    state, decision = design_review_precondition(tree, change, task_dir)
    if state == "skipped":
        def _rec_skip(p):
            p["review"] = {
                "skipped": True,
                "reason": (decision or {}).get("reason"),
                "decided_by": (decision or {}).get("decided_by"),
                "ts": now_iso()}
        update_planning(task_dir, _rec_skip)
        return emit({"change": change, "review": "skipped",
                     "reason": (decision or {}).get("reason"),
                     "decided_by": (decision or {}).get("decided_by"),
                     "why": ("the design artifact was skipped by a "
                             "recorded decision — the review round does "
                             "not run, and the skip is the reason")}, 0)
    if state != "done":
        return emit({"change": change,
                     "waiting_on": "the design artifact",
                     "design_status": state,
                     "why": ("the review round follows the design "
                             "artifact; it is neither done nor skipped "
                             "by decision, so the phase has not reached "
                             "the question")}, EXIT_INCONCLUSIVE)

    # the axes are chosen from the named list, each with a reason, at
    # most the configured maximum — never truncated, never invented
    if not (axes_spec or "").strip():
        return emit({"change": change, "rejected": "axes",
                     "axes_available": sorted(axes),
                     "why": ("the axes for this round are named with a "
                             "reason each (--axes \"axis: reason, "
                             "...\") — a round is never assembled by "
                             "default")}, EXIT_ROLE_REJECTED)
    chosen: list[dict] = []
    seen_axes: set = set()
    for part in axes_spec.split(","):
        part = part.strip()
        if not part:
            continue
        axis, _, reason = part.partition(":")
        axis, reason = axis.strip(), reason.strip()
        if axis not in axes:
            return emit({"change": change, "rejected": axis,
                         "axes_available": sorted(axes),
                         "why": ("the axis is not on the named list — "
                                 "adding one requires amending the "
                                 "list first"),
                         "remedy": ("amend the review: section of "
                                    "config/collapsed.config.yaml")},
                        EXIT_ROLE_REJECTED)
        if not reason:
            return emit({"change": change, "rejected": axis,
                         "why": ("the axis is chosen without a reason — "
                                 "each choice carries why it runs")},
                        EXIT_ROLE_REJECTED)
        if axis not in seen_axes:
            seen_axes.add(axis)
            chosen.append({"axis": axis, "reason": reason})
    if not chosen:
        return emit({"change": change, "rejected": "axes",
                     "why": "no axis was named"}, EXIT_ROLE_REJECTED)
    if len(chosen) > maximum:
        return emit({"change": change, "rejected": "axes",
                     "chosen": [c["axis"] for c in chosen],
                     "maximum": maximum,
                     "why": (f"{len(chosen)} axes named against a "
                             "maximum of {maximum} — the round refuses "
                             "rather than truncate")}, EXIT_ROLE_REJECTED)
    not_chosen = [a for a in sorted(axes) if a not in seen_axes]
    surface = review_surface(tree, change)
    try:
        finding_rel(surface, tree, chosen[0]["axis"])
    except ValueError:
        return emit({"change": change, "rejected": str(surface),
                     "why": ("the review surface must live inside the "
                             "round's working tree — the reviewers' "
                             "finding paths are judged tree-relative")},
                    EXIT_ROLE_REJECTED)

    prior_review = load_json(planning_path(task_dir), {}).get("review") \
        or {}
    prior_reviewers = prior_review.get("reviewers") or {}
    resume_skipped: list = []

    def _write_review(record: dict) -> dict:
        planning = load_json(planning_path(task_dir), {})
        merged = {**planning.get("review", {}), **record}
        planning["review"] = merged
        save_json(planning_path(task_dir), planning)
        return merged

    reviewers: dict = {}
    failures: list = []
    findings: dict = {}
    if stage in ("reviewers", "all"):
        started_at = now_iso()
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            futs = {}
            for c in chosen:
                axis = c["axis"]
                fpath_rel = finding_rel(surface, tree, axis)
                prior = prior_reviewers.get(axis) or {}
                # work already paid for is not paid for again: a
                # reviewer whose recorded round succeeded and whose
                # finding file still satisfies the contract is not
                # re-dispatched
                if prior.get("outcome") == 0 and judge_finding_file(
                        surface / axis / "finding.md",
                        axis)["ok"]:
                    resume_skipped.append(axis)
                    continue
                fpath = tree / fpath_rel
                fpath.parent.mkdir(parents=True, exist_ok=True)
                futs[ex.submit(dispatch_role, change, f"review-{axis}",
                               {}, repo, reviewer_prompt(
                                   change, axis, axes[axis], fpath_rel),
                               task_dir, mode, timeout, ws,
                               allow_roots=(surface,))] = axis
            for fut in futs:
                axis = futs[fut]
                fpath_rel = finding_rel(surface, tree, axis)
                try:
                    out, code = fut.result()
                except BaseException as exc:
                    out, code = {"error": (f"the dispatch died before a "
                                           f"verdict: {exc!r}")}, \
                        EXIT_INCONCLUSIVE
                verdict = judge_finding_file(
                    surface / axis / "finding.md", axis)
                # the write contract: the reviewer's only write is its
                # own finding path — an edit to the design or any other
                # file fails the dispatch
                stray: list = []
                ev = out.get("evidence")
                if ev and Path(ev).is_file():
                    lines = Path(ev).read_text(encoding="utf-8",
                                               errors="replace").splitlines()
                    stray = [w for w in
                             frame_write_named(
                                 lines, tree,
                                 Path(ws["project"])
                                 if ws.get("project") else None)
                             if w != fpath_rel]
                ok = code == 0 and verdict["ok"] and not stray
                why = None
                if not ok:
                    if stray:
                        why = ("the reviewer wrote outside its own path — "
                               f"{stray}")
                    elif not verdict["ok"]:
                        why = verdict["why"]
                    else:
                        why = out.get("why") or out.get("error")
                text = None
                if verdict["kind"] == "finding" and not stray:
                    ffile = surface / axis / "finding.md"
                    if ffile.is_file():
                        text = ffile.read_text(encoding="utf-8",
                                               errors="replace")
                reviewers[axis] = {
                    "role": f"review-{axis}",
                    "session_name": out.get("session_name"),
                    "usage_record": out.get("usage_record"),
                    "evidence": out.get("evidence"),
                    "elapsed_seconds": out.get("elapsed_seconds"),
                    "dispatch_outcome": code, "finding": fpath_rel,
                    "kind": verdict.get("kind"), "finding_text": text,
                    "outcome": 0 if ok else (EXIT_REVIEW_CONTRACT
                                             if code == 0 else code),
                    "why": why}
                if ok and verdict["kind"] == "finding" and text:
                    findings[axis] = text
                if not ok:
                    failures.append(axis)
        merged_reviewers = {**prior_reviewers, **reviewers}
        convergence = review_convergence({
            a: r.get("finding_text") for a, r in merged_reviewers.items()
            if (r or {}).get("kind") == "finding"})
        record = {
            "required": True, "design_status": "done", "mode": mode,
            "concurrency": concurrency, "stage": "reviewers",
            "axes_chosen": chosen, "axes_not_chosen": not_chosen,
            "reviewers": merged_reviewers,
            "convergent": convergence, "failures": failures,
            "resumed_skipping": resume_skipped,
            "started_at": started_at,
            "wall_seconds": round(time.monotonic() - started, 3),
            "ended_at": now_iso(), "complete": False}
        _write_review(record)
        if failures:
            return emit({"change": change, "repo": str(repo),
                         "review": record,
                         "why": ("a reviewer broke the round's contract "
                                 "— its dispatch is named and nothing "
                                 "was cleaned up"),
                         "planning_record": str(planning_path(task_dir))},
                        reviewers[failures[0]]["outcome"]
                        if failures[0] in reviewers
                        else EXIT_REVIEW_CONTRACT)
        if stage == "reviewers":
            return emit({"change": change, "repo": str(repo),
                         "review": record,
                         "note": ("the reviewers are recorded; the caller "
                                  "now writes the synthesis itself "
                                  "(review/synthesis.md — no session is "
                                  "opened for it), --stage synthesis "
                                  "checks it, and --stage revision "
                                  "dispatches the author with every "
                                  "finding and the synthesis alongside"),
                         "planning_record": str(planning_path(task_dir))},
                        0)

    # the synthesis: the caller's own step between the findings and the
    # revision — no session is opened for it, ever; a dispatch that would
    # produce it is refused at the roster
    review_now = load_json(planning_path(task_dir), {}).get("review") or {}
    reviewers_now = review_now.get("reviewers") or {}
    if stage in ("synthesis", "revision") and not reviewers_now:
        return emit({"change": change,
                     "why": ("no reviewers are recorded — run --stage "
                             "reviewers first")}, EXIT_INCONCLUSIVE)
    failed = [a for a, r in reviewers_now.items()
              if (r or {}).get("outcome") not in (0, None)]
    if failed:
        return emit({"change": change,
                     "failed_reviewers": sorted(failed),
                     "why": ("a recorded reviewer failed its contract — "
                             "re-run --stage reviewers before the "
                             "synthesis or the revision; neither answers "
                             "a partial round")},
                    EXIT_REVIEW_CONTRACT)
    finding_axes = [a for a, r in sorted(reviewers_now.items())
                    if (r or {}).get("kind") == "finding"]
    synthesis_path = review_dir(task_dir) / "synthesis.md"
    srel = synthesis_rel(task_dir, Path(ws["project"]))

    if stage == "synthesis" or finding_axes:
        verdict = judge_synthesis_file(synthesis_path, finding_axes) \
            if finding_axes else {"ok": True, "kind": "absent"}
        if not finding_axes:
            merged = _write_review({"synthesis": {
                "required": False, "ok": True,
                "why": ("no reviewer raised a finding — there is nothing "
                        "to synthesise"),
                "ts": now_iso()}})
            if stage == "synthesis":
                return emit({"change": change, "review": merged,
                             "synthesis": "not required",
                             "why": ("no reviewer raised a finding — "
                                     "there is nothing to synthesise"),
                             "planning_record": str(planning_path(task_dir))}, 0)
        elif verdict["kind"] == "missing":
            _write_review({"synthesis": {
                "path": srel, "produced_by": "caller", "ok": False,
                "sessions_opened": 0,
                "breaches": verdict["breaches"], "ts": now_iso()}})
            return emit({"change": change,
                         "waiting_on": "the synthesis",
                         "synthesis_path": srel,
                         "stopped": ("before the author is dispatched — no "
                                     "dispatch can produce the synthesis"),
                         "why": ("the caller writes the synthesis itself: "
                                 "it already holds the design and every "
                                 "finding, and opening a session to "
                                 "re-read them is what this step exists "
                                 "not to do"),
                         "remedy": (f"write {srel} — groups by where in "
                                    "the design each finding lands, every "
                                    "opposing pair named, one citation "
                                    "per concern — then --stage synthesis "
                                    "checks it"),
                         "planning_record": str(planning_path(task_dir))},
                        EXIT_INCONCLUSIVE)
        else:
            merged = _write_review({"synthesis": {
                "path": srel, "produced_by": "caller",
                "sessions_opened": 0,
                "groups": verdict.get("groups"),
                "opposing_pairs": verdict.get("opposing_pairs"),
                "no_opposing_pairs": verdict.get("no_opposing_pairs"),
                "ok": verdict.get("ok"),
                "breaches": verdict.get("breaches"),
                "checked_at": now_iso()}})
            if not verdict["ok"]:
                return emit({"change": change, "review": merged,
                             "synthesis": "breach",
                             "breaches": verdict["breaches"],
                             "why": ("the synthesis broke its contract — "
                                     "it is a reading aid and must carry "
                                     "no opinion of its own; each breach "
                                     "is named"),
                             "planning_record": str(planning_path(task_dir))},
                            EXIT_REVIEW_CONTRACT)
            if stage == "synthesis":
                return emit({"change": change, "review": merged,
                             "synthesis": "checked",
                             "groups": verdict["groups"],
                             "opposing_pairs": verdict["opposing_pairs"],
                             "no_opposing_pairs":
                                 verdict["no_opposing_pairs"],
                             "note": ("the synthesis is the caller's own "
                                      "step — zero sessions, zero "
                                      "dispatches; it travels into the "
                                      "delivery report as advice"),
                             "planning_record": str(planning_path(task_dir))}, 0)

    answers_path = answers_rel(surface, tree)
    if not finding_axes:
        record = {"stage": "revision", "synthesis": {
            "required": False, "ok": True,
            "why": ("no reviewer raised a finding — there is nothing to "
                    "synthesise"),
            "ts": now_iso()}, "revision": {
            "dispatched": False,
            "why": ("no reviewer raised a finding — every axis recorded "
                    "nothing found, so there is nothing to answer"),
            "unanswered": []}, "complete": True, "ended_at": now_iso()}
        merged = _write_review(record)
        return emit({"change": change, "review": merged,
                     "planning_record": str(planning_path(task_dir))}, 0)

    findings_list = [{"axis": a, "text": reviewers_now[a]["finding_text"]}
                     for a in finding_axes]
    synthesis_text = synthesis_path.read_text(encoding="utf-8",
                                              errors="replace")
    started_at = now_iso()
    started = time.monotonic()
    out, code = dispatch_role(
        change, "design", {}, repo,
        revision_prompt(change, findings_list, answers_path,
                        synthesis_text),
        task_dir, mode, timeout, ws, allow_roots=(surface,))
    answers, unanswered = judge_answers_file(tree / answers_path,
                                             finding_axes)
    revision = {
        "dispatched": True, "stage": "revision",
        "session_name": out.get("session_name"),
        "usage_record": out.get("usage_record"),
        "evidence": out.get("evidence"),
        "elapsed_seconds": out.get("elapsed_seconds"),
        "dispatch_outcome": code, "answers_path": answers_path,
        "answers": answers, "unanswered": unanswered,
        "answers_ok": code == 0}
    record = {"stage": "all", "revision": revision,
              "complete": code == 0 and not unanswered,
              "ended_at": now_iso(),
              "revision_wall_seconds": round(time.monotonic() - started, 3)}
    merged = _write_review(record)
    if code != 0:
        return emit({"change": change, "review": merged,
                     "why": out.get("why") or out.get("error"),
                     "planning_record": str(planning_path(task_dir))},
                    code)
    if unanswered:
        return emit({"change": change, "review": merged,
                     "unanswered_findings": unanswered,
                     "why": ("a finding carries no answer — the phase is "
                             "not reported complete while it is "
                             "unanswered; the finding is named"),
                     "planning_record": str(planning_path(task_dir))},
                    EXIT_REVIEW_UNANSWERED)
    return emit({"change": change, "review": merged,
                 "planning_record": str(planning_path(task_dir)),
                 "note": ("the round's findings are advice to the author "
                          "— they never gate delivery; the delivery "
                          "report carries them as advice")}, 0)


# ── the phase: independent roles dispatched together ────────────────

def role_states(repo: Path, change: str) -> dict:
    arts = artifacts_view(change)
    done = {a.get("id") for a in arts if a.get("status") == "done"}
    return {"artifacts": arts, "done": done,
            "is_planning_complete":
                bool((plane_status(change) or {})
                     .get("is_planning_complete"))}


def _run_role(change: str, role: str, package_file: Path, task_dir: Path,
              mode: str, timeout: int,
              ws: dict | None = None) -> tuple[dict, int]:
    """One phase worker: admit the role exactly as a single dispatch
    would (package shape, role ownership, dependencies done), then run
    the same dispatch_role path — own session, own frame file, own
    boundary baseline. The workspace is the phase's, decided once before
    the pool started, so every worker authors in the same tree."""
    pkg, repo, prompt, _lang = prepare(change, role, package_file,
                                       workspace=ws)
    # codegraph: if an impact brief exists, tell the role to read it
    # first (prd-codegraph-role.md §04).  This check is purely file
    # existence — it fires regardless of whether codegraph_auto_dispatch
    # just ran in this invocation, the file came from an earlier run, or
    # a human ran `plan.py codegraph brief` manually.  No file, no change
    # to the prompt (INV-5).
    brief = repo / "codegraph" / "impact-brief.md"
    if brief.is_file():
        prompt += (
            "\n\nBefore writing, read codegraph/impact-brief.md in the "
            "repository root if it exists — it summarizes the callers, "
            "dependencies, and cross-module coupling of the files this "
            "change touches.")
    return dispatch_role(change, role, pkg, repo, prompt, task_dir,
                         mode, timeout, ws=ws)


def _maybe_auto_codegraph(change: str, repo: Path, task_dir: Path) -> None:
    """The codegraph auto-dispatch hook (scheduling, not gating).  Called
    at the start of cmd_phase and cmd_dispatch's live-dispatch path —
    if a codegraph brief is due, dispatch it via subprocess before the
    role pool opens.  The dispatch's outcome never changes the caller's
    exit code or stops role dispatch (INV-14).  Shared by both call
    sites to avoid the two judgment copies drifting apart (PRD §07)."""
    state = load_json(task_dir / "state.json", {})
    due, why_not = codegraph_auto_due(task_dir, repo, state)
    if due:
        codegraph_auto_dispatch(task_dir, repo, state, change)
    else:
        event(task_dir, event="CODEGRAPH_AUTO_SKIPPED",
              change=change, why=why_not)


def cmd_phase(change: str, repo: Path, package_file: Path,
              task_dir: Path | None, mode: str, timeout: int,
              concurrency: int, accept_partial_view: bool) -> int:
    """Run the planning phase for one change end to end. Every role the
    artifact graph reports dispatchable at the same moment is dispatched
    — up to --concurrency at a time; --concurrency 1 runs the same kind
    of run serially, and the phase record makes the difference visible.
    Each dispatch is the same dispatch_role path as a single dispatch.
    A role that fails stops NEW dispatches; the ones already running
    finish, and every outcome is reported before the phase stops. An
    artifact the upstream instruction makes conditional is dispatched
    only on a recorded decision (see `decide`) — none recorded stops the
    phase for a person rather than assuming either way."""
    pkg = load_package(package_file, change)
    repo = repo.resolve()
    skill = authoring_skill_state()
    if not skill["ok"]:
        return emit({"change": change, "rejected": "authoring skill",
                     "why": ("the openspec-author skill is not installed "
                             "and registered in the gateway workspace — "
                             "a role cannot fetch its own authoring "
                             "guidance"),
                     "skill_state": skill,
                     "stopped": "before dispatch — the client was never "
                                "invoked"}, EXIT_SKILL_MISSING)
    # the task dir is not defaulted from the project — the class decides
    # whether the record lives in the project or inside the workspace
    forbidden = forbidden_dependency_paths(repo)
    if forbidden:
        return emit({"rejected": str(repo),
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "forbidden": forbidden[:20],
                     "forbidden_count": len(forbidden),
                     "why": ("the target holds source of a dependency "
                             "this project may not modify; a run against "
                             "it could write into that source")},
                    EXIT_FORBIDDEN_TARGET)

    # the target's class decides where the phase runs — once, before the
    # pool starts, so every worker authors in the same tree
    classification = classify_target(repo)
    if classification["class"] is None:
        return emit({"rejected": str(repo), "change": change,
                     "classification": classification,
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "why": ("the target's class could not be "
                             "established — the gateway's own view of "
                             "the path could not be probed, and no "
                             "prefix is trusted to guess it")},
                    EXIT_INCONCLUSIVE)
    workspace = workspace_for(change, repo, classification,
                              task_dir=task_dir)
    if workspace.get("refused"):
        code = EXIT_INCONCLUSIVE if workspace.get("class") != "invisible" \
            else EXIT_WORKSPACE
        return emit({"rejected": str(repo), "change": change,
                     "classification": classification,
                     "workspace": workspace,
                     "stopped": "before dispatch — the client was never "
                                "invoked"}, code)
    task_dir = Path(workspace["task_dir"])
    tree = Path(workspace["path"])
    ws = workspace   # every round is a split round under N6
    def _record_class(p):
        p["target_class"] = classification
        p["workspace"] = _workspace_record(workspace)
        p["change"] = change
    update_planning(task_dir, _record_class)
    view = view_state(repo)
    if view["state"] == "partial":
        prior = load_json(planning_path(task_dir), {})
        if accept_partial_view:
            def _acc(p):
                p["view"] = {"accepted": True, **view,
                             "accepted_note": ("a human accepted the "
                                               "narrower view "
                                               "(--accept-partial-view)"),
                             "ts": now_iso()}
            update_planning(task_dir, _acc)
        elif (prior.get("view") or {}).get("accepted") is not True:
            return emit({"change": change, "repo": str(repo),
                         "waiting_on": "human view acceptance",
                         "stopped": "before dispatch — the client was "
                                    "never invoked",
                         "view": view,
                         "why": ("the working tree shows fewer files than "
                                 "the head commit; a human accepts the "
                                 "narrower view with "
                                 "--accept-partial-view")},
                        EXIT_INCONCLUSIVE)

    # the conditional artifacts are decided BEFORE any dispatch: whether
    # one runs is the upstream instruction's own conditions, and the run
    # refuses to assume either way
    conditioned = conditioned_artifact_states(tree, change)
    pending = [c for c in conditioned if c["status"] != "done"
               and artifact_decision(task_dir, c["artifact"]) is None]
    if pending:
        return emit({"change": change, "repo": str(repo),
                     "stopped": "before dispatch — the client was never "
                                "invoked",
                     "waiting_on": "artifact decision",
                     "undecided": [{"artifact": c["artifact"],
                                    "conditions": c["conditions"]}
                                   for c in pending],
                     "why": ("an artifact the upstream instruction makes "
                             "conditional carries no recorded decision — "
                             "a person decides whether its conditions "
                             "apply; the run does not assume either way"),
                     "remedy": (f"plan.py decide --change {change} "
                                f"--repo {repo} --artifact <id> "
                                '(--condition "<one of its own conditions>" '
                                'or --skip --reason "<why none apply>")')},
                    EXIT_INCONCLUSIVE)
    decisions = {c["artifact"]: artifact_decision(task_dir, c["artifact"])
                 for c in conditioned}
    skip_decisions = {a: d for a, d in decisions.items()
                      if d and d.get("dispatch") is False}

    states = role_states(tree, change)
    def _record_packages(p):
        for a in states["artifacts"]:
            p.setdefault("packages", {})[a.get("id", "")] = pkg
        p["change"] = change
    update_planning(task_dir, _record_packages)

    # codegraph auto-dispatch (scheduling, not gating): if a brief is
    # due, dispatch it before the role pool opens so the author has the
    # impact brief as input.  The dispatch's outcome never changes this
    # function's exit code or stops the pool (INV-14).
    _maybe_auto_codegraph(change, repo, task_dir)

    started = time.monotonic()
    started_at = now_iso()
    outcomes: dict = {}
    failures: list = []
    round_no = 0
    stopped_early = None
    no_progress = None
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        while stopped_early is None:
            states = role_states(tree, change)
            done_before = set(states["done"])
            dispatchable = [a.get("id") for a in states["artifacts"]
                            if a.get("id") not in done_before
                            and a.get("id") not in skip_decisions
                            and all(d in done_before
                                    for d in a.get("requires", []))]
            if not dispatchable:
                break
            round_no += 1
            futures = {ex.submit(_run_role, change, role, package_file,
                                 task_dir, mode, timeout, ws): role
                       for role in dispatchable}
            for fut in futures:
                role = futures[fut]
                try:
                    out, code = fut.result()
                except BaseException as exc:
                    out, code = {"artifact": role,
                                 "error": (f"the dispatch died before a "
                                           f"verdict: {exc!r}")}, \
                        EXIT_INCONCLUSIVE
                outcomes[role] = {
                    "outcome": code,
                    "elapsed_seconds": out.get("elapsed_seconds"),
                    "session_name": out.get("session_name"),
                    "evidence": out.get("evidence"),
                    "skipped": bool(out.get("skipped")),
                    "offending": out.get("offending") or [],
                    "why": out.get("why") or out.get("error")}
                if code != 0:
                    failures.append(role)
                    stopped_early = role
            # a round that landed nothing is no progress: the same roles
            # would be re-dispatched forever (each one a real, billed
            # dispatch). The phase stops and says so — it never loops on
            # a plane that is not consuming the work
            done_after = set(role_states(tree, change)["done"])
            if stopped_early is None and not (done_after - done_before):
                no_progress = sorted(dispatchable)
                break

    states = role_states(tree, change)
    done = states["done"]
    blocked = [{"artifact": a.get("id"),
                "waiting_on": [d for d in a.get("requires", [])
                               if d not in done]}
               for a in states["artifacts"]
               if a.get("id") not in done and a.get("id") not in skip_decisions
               and a.get("id") not in outcomes]

    # the disjointness the frame proof rests on: every written path
    # appears in exactly one role's frames, and the sessions are
    # pairwise distinct; a path outside the change dir names the role
    # whose frames carry the write
    writers: dict = {}
    sessions = []
    read_side = Path(workspace["project"]) \
        if workspace and workspace.get("project") else None
    for role, o in outcomes.items():
        ev = o.get("evidence")
        if ev and Path(ev).is_file():
            lines = Path(ev).read_text(encoding="utf-8",
                                       errors="replace").splitlines()
            for path in frame_write_named(lines, tree, read_side):
                writers.setdefault(path, []).append(role)
        if o.get("session_name"):
            sessions.append(o["session_name"])
    multi_written = {p: sorted(set(r)) for p, r in writers.items()
                     if len(set(r)) > 1}
    disjointness = {
        "sessions_pairwise_distinct": len(sessions) == len(set(sessions)),
        "artifact_writers": writers, "multi_written": multi_written}
    offender_paths = sorted({p for o in outcomes.values()
                             for p in (o.get("offending") or [])})
    offenders = [{"path": p,
                  "frames_carry": sorted(set(writers.get(p, []))) or None}
                 for p in offender_paths]

    wall_seconds = round(time.monotonic() - started, 3)
    sum_role_seconds = round(sum(o.get("elapsed_seconds") or 0
                                 for o in outcomes.values()), 3)
    phase_record = {
        "started_at": started_at, "ended_at": now_iso(),
        "wall_seconds": wall_seconds,
        "sum_role_seconds": sum_role_seconds,
        "concurrency": concurrency, "serial": concurrency == 1,
        "rounds": round_no, "roles": outcomes, "failures": failures,
        "blocked": blocked, "skipped_by_decision": skip_decisions,
        "no_progress": no_progress,
        "workspace": _workspace_record(workspace),
        "disjointness": disjointness}
    def _record_phase(p):
        p.setdefault("phases", []).append(phase_record)
    update_planning(task_dir, _record_phase)

    out = {"change": change, "repo": str(repo), "phase": phase_record,
           "workspace": _workspace_record(workspace),
           "is_planning_complete": states["is_planning_complete"],
           "planning_record": str(planning_path(task_dir)),
           "note": ("sum_role_seconds is what the role dispatches took "
                    "together; wall_seconds is the span the phase took — "
                    "in a serial phase the two are equal, in a concurrent "
                    "one they are not")}
    if offenders:
        out["offenders"] = offenders
        out["why"] = ("a path outside the change dir sits in this phase's "
                      "increment; the role whose frames carry the write "
                      "is named — nothing was cleaned up")
        return emit(out, EXIT_BOUNDARY)
    if multi_written:
        out["why"] = ("a path was written from more than one role's "
                      "frames — the disjointness the frame proof rests "
                      "on does not hold for this run")
        return emit(out, EXIT_BOUNDARY)
    if failures:
        out["why"] = ("a dispatch failed; dispatches already running "
                      "were allowed to finish and every outcome is "
                      "reported before the phase stopped")
        first = outcomes[failures[0]].get("outcome") or EXIT_INCONCLUSIVE
        return emit(out, first)
    if no_progress:
        out["why"] = ("a full round of dispatches landed no artifact — "
                      "re-dispatching the same roles would repeat the "
                      "payment without progress; the phase stopped")
        return emit(out, EXIT_INCONCLUSIVE)
    return emit(out, 0)


# ── accept ──────────────────────────────────────────────────────────

def owning_artifacts(text: str, change: str, repo: Path) -> list:
    """Map each offending path the validator names to the artifact whose
    role receives the revision. The validator prints paths relative to
    the specs dir, the change dir or the plane root (the session runs
    there under N6) — resolve every candidate against the actual tree
    before deciding."""
    root = plane_root(repo)
    change_dir = root / "openspec" / "changes" / change
    found, order = set(), []
    tokens = re.findall(r"[\w./\\-]+\.md\b|specs/[\w./-]*\.md\b", text)
    for tok in tokens:
        resolved = None
        for cand in (root / tok, change_dir / tok,
                     change_dir / "specs" / tok, repo / tok):
            if cand.is_file():
                resolved = cand
                break
        art = None
        if resolved is not None:
            try:
                rel = resolved.resolve().relative_to(change_dir.resolve())
            except ValueError:
                rel = None
            if rel is not None:
                parts = rel.parts
                if parts and parts[0] == "specs":
                    art = "specs"
                else:
                    art = ARTIFACT_BASENAMES.get(parts[-1] if parts else "")
        else:
            base = os.path.basename(tok)
            art = ARTIFACT_BASENAMES.get(base)
            if art is None and base == "spec.md":
                art = "specs"
        if art and art not in found:
            found.add(art)
            order.append(art)
    return order


def count_headers(change_dir: Path) -> dict:
    req = scen = files = 0
    if change_dir.is_dir():
        for f in sorted(change_dir.rglob("*.md")):
            files += 1
            for line in f.read_text(encoding="utf-8",
                                    errors="replace").splitlines():
                if line.startswith("### Requirement:"):
                    req += 1
                elif line.startswith("#### Scenario:"):
                    scen += 1
    return {"requirements": req, "scenarios": scen, "markdown_files": files}


def skipped_artifacts(change: str, task_dir: Path) -> list:
    """The not-done artifacts this run did not dispatch, each with the
    honest reason: a recorded human decision when one exists, and for a
    conditional artifact with no decision, exactly that — no claim about
    conditions nobody evaluated. The conditions travel in the graph
    record; the instruction is never fetched caller-side."""
    decisions = load_json(planning_path(task_dir), {}) \
        .get("artifact_decisions") or {}
    graph = {a.get("id"): a for a in artifacts_view(change)}
    out = []
    for aid, a in graph.items():
        if a.get("status") == "done":
            continue
        dec = decisions.get(aid)
        if isinstance(dec, dict) and dec.get("dispatch") is False:
            out.append({"artifact": aid, "skipped_by_decision": True,
                        "reason": dec.get("reason"),
                        "decided_by": dec.get("decided_by"),
                        "conditions_considered":
                            dec.get("conditions_considered")})
            continue
        if a.get("conditional") or [c for c in a.get("conditions", [])
                                     if str(c).strip()]:
            out.append({"artifact": aid, "skipped_by_decision": False,
                        "reason": ("no pre-dispatch decision recorded — "
                                   "this run dispatched nothing for it and "
                                   "claims nothing about the conditions")})
    return out


def unacknowledged_frame_violations(task_dir: Path) -> list[dict]:
    """The checked lines the LATEST dispatch of a role crossed. A record
    is replaced wholesale by every dispatch, so an entry here means the
    most recent attempt of that role — a violation followed by a clean
    re-dispatch does not linger."""
    planning = load_json(planning_path(task_dir), {})
    out = []
    for role, rec in (planning.get("dispatches") or {}).items():
        if isinstance(rec, dict) and rec.get("frame_violations"):
            out.append({"artifact": role, **rec["frame_violations"]})
    return out


def cmd_accept(change: str, repo: Path, task_dir: Path | None,
               counts_approved: bool) -> int:
    if task_dir is None:
        task_dir = default_task_dir(repo, change)
    # an artifact whose latest dispatch crossed a checked line — the
    # author validating its own output, or destroying what the tree
    # already carried — is not accepted on that dispatch, however the
    # validator rates the text it produced
    violations = unacknowledged_frame_violations(task_dir)
    if violations:
        return emit({"accepted": False,
                     "why": ("the latest dispatch of a role crossed a "
                             "checked line (the author judged its own "
                             "output, or destroyed a baseline path) — the "
                             "artifact it produced is not accepted on "
                             "that dispatch; re-dispatch the role"),
                     "violations": violations}, EXIT_AUTHOR_JUDGED)
    # the verdict comes from the plane's signed records — the caller
    # no longer runs the validator (containment D5b). A missing,
    # tampered or stale verdict is reported as exactly that; accept
    # judges nothing without one.
    _, tampered = signed_records(change, "verdict")
    if tampered:
        return emit({"accepted": False,
                     "spec_state": "spec_unverified",
                     "why": ("verdict records failed signature "
                             "verification — tampering evidence, not a "
                             "verdict; nothing is judged on it"),
                     "rejected_records": tampered},
                    EXIT_RECORD_MISSING)
    verdict = newest_verdict(change)
    if verdict is None:
        missing_record_stop(
            change, ["validate"],
            "dispatch the validator once: plan.py validate --change <id> "
            "--repo <repo> — the caller never executes openspec, and "
            "accept judges nothing without a signed verdict")
    stale = stale_against(change, verdict, repo)
    if stale:
        return emit({"accepted": False,
                     "spec_state": "spec_unverified",
                     "why": ("the newest verdict predates a write to the "
                             "artifact tree — it is not the verdict of "
                             "what stands now"),
                     "stale_against": stale,
                     "verdict_ts": verdict.get("ts"),
                     "remedy": ("run a validate dispatch again after the "
                                "last artifact write")},
                    EXIT_RECORD_MISSING)
    validator_output = str(verdict.get("stdout") or "").strip()
    if int(verdict.get("rc") or 0) != 0:
        owners = owning_artifacts(validator_output, change, repo)
        packages = (load_json(planning_path(task_dir), {})
                    .get("packages") or {})
        pkg = packages.get(owners[0]) if len(owners) == 1 else None
        # the rejection is recorded: the artifact file exists (status
        # would call it done) but was returned for revision — a later
        # dispatch of the owning role must run, not skip
        planning = load_json(planning_path(task_dir), {})
        planning["revision_pending"] = {
            "artifact": owners[0] if len(owners) == 1 else None,
            "validator_output": validator_output[:2000], "ts": now_iso()}
        save_json(planning_path(task_dir), planning)
        return emit({"accepted": False,
                     "validator_rc": int(verdict.get("rc") or 0),
                     "validator_output": validator_output,
                     "owning_artifact": owners[0] if len(owners) == 1
                     else owners,
                     "revision_prompt": {
                         "package": pkg,
                         "validator_output": validator_output,
                         "clause": ("revise only your artifact; do not "
                                    "change requirement or scenario "
                                    "counts")}},
                    EXIT_VALIDATOR_REJECTED)

    cur = count_headers(plane_tree(repo) / "changes" / change)
    planning = load_json(planning_path(task_dir), {})
    prev = planning.get("accepted_counts")
    drift_keys = ("requirements", "scenarios")
    if prev and any(prev.get(k) != cur[k] for k in drift_keys) \
            and not counts_approved:
        return emit({"accepted": False,
                     "why": ("requirement or scenario counts changed since "
                             "the last accepted snapshot — a revision that "
                             "changes counts unbidden is rejected again"),
                     "counts_now": cur, "counts_last_accepted": prev,
                     "remedy": ("pass --counts-approved once a human has "
                                "approved the count change")},
                    EXIT_COUNT_DRIFT)

    complete = bool((plane_status(change) or {})
                    .get("is_planning_complete"))
    # the design-review round holds the phase report — and only the
    # report: when the design artifact ran, the phase is not called
    # complete until every finding is answered (design-review V3.3)
    review_gate = review_phase_gate(planning)
    if review_gate:
        complete = False
    planning.update(change=change, accepted_counts=cur, accepted_at=now_iso(),
                    is_planning_complete=complete,
                    skipped=skipped_artifacts(change, task_dir))
    # the revision landed and validated — the pending marker clears
    planning.pop("revision_pending", None)
    save_json(planning_path(task_dir), planning)
    out = {"accepted": True, "validator_rc": 0, "counts": cur,
           "counts_changed": bool(
               prev and any(prev.get(k) != cur[k] for k in drift_keys)),
           "counts_approved": bool(counts_approved),
           "is_planning_complete": complete,
           "phase_complete": complete}
    if review_gate:
        out["review"] = review_gate
    # N7: the accepted change's executable entries are delivered to the
    # records store the moment the change is accepted — behavior only
    handoff = write_handoff(change, repo)
    if handoff is not None:
        out["handoff"] = str(handoff)
    return emit({**out,
                 "remaining_artifacts": [a.get("id") for a in
                                         artifacts_view(change)
                                         if a.get("status") != "done"],
                 "skipped": planning["skipped"],
                 "phase_gate": ("the phase is judged complete only by "
                                "openspec's own completeness report"),
                 "task_dir": str(task_dir)}, 0)


# ── N7: the behavior handoff ────────────────────────────────────────

def write_handoff(change: str, repo: Path) -> Path | None:
    """N7 — deliver the executable entries of the tasks artifact where
    the implementation reads them: records/<change>/handoff.md, in the
    plane's records store. Behavior only, verbatim from the artifact —
    the spec tooling, the artifact formats and the validation surface
    that produced the entries are NOT part of the handoff. Without
    this cut the caller implements from memory of formats it has seen,
    hand-writes spec files, and only the boundary is left to stop it."""
    src = plane_tree(repo) / "changes" / change / "tasks.md"
    if not src.is_file():
        return None
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    entries = [ln.strip() for ln in lines
               if re.match(r"^\s*-\s+\[[ xX]\]", ln)]
    out = RECORDS_ROOT / change / "handoff.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = ["# Handoff — behavior only", "",
            f"change: {change}",
            f"repo: {repo}",
            f"entries: {len(entries)}", "",
            "The executable entries of the tasks artifact, verbatim:", ""]
    body += [f"{i + 1}. {e}" for i, e in enumerate(entries)]
    body += ["", "---", "",
             "This handoff carries behavior and nothing else. The spec",
             "tooling, the artifact formats and the validation surface",
             "that produced these entries are deliberately absent",
             "(containment N7): implementation happens in the repo's",
             "worktree, inline, against these entries; the spec surface",
             "is the plane's own tree and is never written by hand."]
    out.write_text("\n".join(body) + "\n", encoding="utf-8")
    return out


# ── close: the tail ─────────────────────────────────────────────────

def merge_gate_answer(task_dir: Path) -> dict | None:
    """The human's merge-gate answer, if one exists. An approval only
    counts when it carries a rationale — the same contract report.py
    enforces when the answer is written."""
    ans = load_json(task_dir / "gates" / "gate-merge.answer.json")
    if not isinstance(ans, dict):
        return None
    if ans.get("decision") != "approve":
        return None
    if not str(ans.get("rationale", "")).strip():
        return None
    return ans


def cmd_close(change: str, repo: Path, task_dir: Path | None,
              branch: str | None, skip_specs: bool,
              keep_task_branch: bool = False,
              mode: str = "normal", timeout: int = 600) -> int:
    if task_dir is None:
        task_dir = default_task_dir(repo, change)
    ans = merge_gate_answer(task_dir)
    if ans is None:
        # W7: reverse-lookup — the gate file might be in a different
        # task-dir (the country-b task-dir/repo confusion). Search by
        # change_id in the repo's own .ai-dlc/ and $PWD's, and tell
        # the caller where the gate file actually is.
        found_at = None
        for root in (Path(repo) / ".ai-dlc" / "tasks",
                     Path.cwd() / ".ai-dlc" / "tasks"):
            if not root.is_dir():
                continue
            for sf in root.glob("*/state.json"):
                st = load_json(sf, {})
                if st.get("change_id") == change:
                    other_td = sf.parent
                    other_ans = load_json(other_td / "gates"
                                          / "gate-merge.answer.json")
                    if isinstance(other_ans, dict) and \
                            other_ans.get("decision") == "approve":
                        found_at = str(other_td / "gates"
                                       / "gate-merge.answer.json")
                        break
            if found_at:
                break
        result = {"closed": False, "change": change, "repo": str(repo),
                  "waiting_on": "merge_gate",
                  "gate_file": str(task_dir / "gates"
                                   / "gate-merge.answer.json"),
                  "why": ("the merge gate carries no approval with a "
                          "rationale — a person decides; neither merge "
                          "nor archive ran")}
        if found_at:
            result["gate_found_elsewhere"] = found_at
            result["remedy"] = ("the gate answer is at %s — pass "
                                 "--task-dir %s" % (
                                     found_at,
                                     str(Path(found_at).parent.parent)))
        return emit(result, EXIT_INCONCLUSIVE)

    out = {"closed": False, "change": change, "repo": str(repo),
           "approved_by": ans.get("approver"), "approved_at": ans.get("ts")}

    # 1. merge the task branch into the branch the repo stands on
    # W1/Z1: read the branch from state.json (the init contract) first,
    # then fall back to the --branch flag, then the task/<change> convention.
    _state = load_json(task_dir / "state.json", {})
    br = branch or _state.get("branch") or f"task/{change}"
    have = run(["git", "-C", str(repo), "rev-parse", "--verify", "-q",
                "refs/heads/" + br])
    if have.returncode != 0:
        out["merge"] = {"status": "no_branch",
                        "branch": br,
                        "note": ("no task branch exists — the work landed "
                                 "without one; nothing to merge")}
    else:
        cur = run(["git", "-C", str(repo), "branch", "--show-current"])
        target = (cur.stdout or "").strip() or "HEAD (detached)"
        ancestor = run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                        br, "HEAD"])
        if ancestor.returncode == 0:
            out["merge"] = {"status": "already_landed", "branch": br,
                            "target": target,
                            "note": "the branch is already contained in "
                                    "the target"}
        else:
            m = run(["git", "-C", str(repo), "merge", "--no-edit", br])
            if m.returncode != 0:
                out["merge"] = {"status": "failed", "branch": br,
                                "target": target,
                                "output": ((m.stdout or "")
                                           + (m.stderr or "")).strip()[:2000]}
                out["why"] = ("the merge exited non-zero; its output is "
                              "carried verbatim and nothing is closed")
                return emit(out, EXIT_CLOSE_FAILED)
            out["merge"] = {"status": "merged", "branch": br,
                            "target": target,
                            "head": run(["git", "-C", str(repo), "rev-parse",
                                         "HEAD"]).stdout.strip()}

    # 2. I3 — reachability BEFORE the plane's tree is touched: the
    #    write-back needs the repo writable through the gateway's own
    #    view, and anything less means the archive would move the
    #    plane's tree and then strand the write-back — the split state
    #    this order exists to make impossible. The plane is left
    #    untouched and the text points at the unit's regime or the
    #    path itself; there is no second exit from this stop.
    classification = classify_target(repo)
    out["reachability"] = {
        "class": classification.get("class"),
        "decision_basis": classification.get("decision_basis"),
        "masked_by": classification.get("masked_by"),
        "checked_at": now_iso(),
    }
    if classification.get("class") is None:
        out["closed"] = False
        out["why"] = (
            "the repository's class could not be established (the "
            "gateway's own view could not be probed) — the archive "
            "dispatch did not run and the plane's tree was not touched")
        return emit(out, EXIT_INCONCLUSIVE)
    if classification.get("class") != "writable":
        cls = classification.get("class")
        basis = classification.get("decision_basis")
        out["closed"] = False
        out["why"] = (
            f"the repository is not writable through the gateway's own "
            f"view (class {cls}, decided by {basis}) — the archive "
            "dispatch did not run and the plane's tree was not "
            "touched. A masked or invisible class on a path that "
            "plainly stands is the unit's sandbox, not the path: a "
            "unit rolled back to its hardened form hides what its "
            "private namespace carries (re-open or restore the unit — "
            "a host step); otherwise the path itself is not writable "
            "and must be made so by its owner")
        return emit(out, EXIT_CLOSE_FAILED)

    # 3. archive is a plane dispatch (containment N2): one session
    #    runs the normalized archive literal and the normalized
    #    write-back literals, the caller judges the frames and then the
    #    filesystem. The merge above stayed caller-side behind the
    #    human gate; the archive never was the caller's to run. A tree
    #    whose shape says the archive already ran resumes at the
    #    write-back (I4) and the fact travels into this record.
    arch, arch_code = cmd_archive_dispatch(
        change, repo, task_dir, skip_specs, mode, timeout)
    out["archive"] = arch
    out["resumed_from"] = arch.get("resumed_from")
    if arch_code != 0:
        out["closed"] = False
        out["why"] = arch.get("why") or (
            "the archive dispatch did not complete; its report is "
            "carried verbatim and nothing is reported closed")
        # S5: when the refusal is a G4/G5 surface alteration, record
        # the fact so a subsequent successful close can mark the repair
        if arch.get("refused") and arch.get("surface"):
            try:
                save_json(task_dir / "surface-refusal.json", {
                    "change": change, "ts": now_iso(),
                    "surface": arch.get("surface"),
                    "why": arch.get("why")})
            except OSError:
                pass
        return emit(out, arch_code)

    # 3. close the task record with the state that follows delivery
    state_file = task_dir / "state.json"
    state = load_json(state_file, {})
    if state:
        state.update(stage="DONE", human_state="Ready",
                     closed_at=now_iso(), closed_change=change)
        save_json(state_file, state)
        event_row = (task_dir / "close-event.jsonl")
        with event_row.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "TASK_CLOSED", "ts": now_iso(),
                                "change": change,
                                "merge": out["merge"]["status"],
                                "archive": "archived",
                                "resumed_from": out.get("resumed_from")},
                               ensure_ascii=False)
                    + "\n")
        out["record"] = {"task_dir": str(task_dir), "stage": "DONE",
                         "human_state": "Ready"}
    else:
        out["record"] = {"task_dir": str(task_dir),
                         "note": "no task record existed; nothing to close"}
    out["closed"] = True

    # S5: if a prior surface refusal was recorded and this close
    # succeeded, the surface was repaired by hand — mark the fact
    surface_refusal_file = task_dir / "surface-refusal.json"
    if surface_refusal_file.is_file():
        out["surface_repaired_by_hand"] = True

    # 4. the run leaves the target as found (L7.5): the worktree and the
    #    task branch it created are removed now that the branch is
    #    merged — or their retention is recorded, never silent
    if keep_task_branch:
        out["cleanup"] = {"worktrees": [], "branch": None,
                          "retention": {"reason": "kept by request "
                                                  "(--keep-task-branch)"}}
    else:
        wts = [w for w in worktrees_on_branch(repo, br) if Path(w) != repo]
        wt_report = []
        for w in wts:
            r = run(["git", "-C", str(repo), "worktree", "remove", w])
            wt_report.append({"path": w, "removed": r.returncode == 0,
                              "output": _run_note(r)})
        br_report = None
        if out["merge"]["status"] in ("merged", "already_landed"):
            r = run(["git", "-C", str(repo), "branch", "-d", br])
            br_report = {"branch": br, "removed": r.returncode == 0,
                         "output": _run_note(r)}
        else:
            br_report = {"branch": br, "removed": False,
                         "reason": "no task branch existed"}
        out["cleanup"] = {"worktrees": wt_report, "branch": br_report}
    out["note"] = ("archived, written back and committed by the plane "
                   "dispatch; the merge stayed caller-side behind the "
                   "human gate, and the delivery report remains the "
                   "honest account of what was and was not checked")

    # G1 (phase-chain-automation Phase B): after a successful merge +
    # archive, advance any initiative that owns this change. Reuses the
    # Phase A function (init_advance) — no second implementation. The
    # manifest lookup is the same one `initiative advance` does
    # internally; a change id in no manifest skips the hook entirely so
    # close stays byte-identical to pre-change for that case (PRD §06
    # regression). Advancement failure is reported under
    # `initiative_advance` but never affects the closed phase's record
    # or close's exit code (INV-20 / spec: "Advancement failure does not
    # affect the closed phase's record").
    if init_find_manifest(repo, change) is not None:
        try:
            _buf = io.StringIO()
            with contextlib.redirect_stdout(_buf):
                _adv_rc = init_advance(change, repo)
            _adv = json.loads(_buf.getvalue()) \
                if _buf.getvalue().strip() else {}
        except Exception as _exc:  # never break a successful close
            _adv = {"advanced": False, "error": str(_exc)}
        out["initiative_advance"] = _adv
    return emit(out, 0)


# ── the design dispatch: measured applicability, pinned reference ────
#
# One fresh session whose write boundary is the change's measured
# frontend surface. The conclusion is never the role's sentence to
# give: the caller reads the session's frames for five facts — which
# upstream SKILL.md was read, which files were written (verified
# against the filesystem), whether every referenced asset resolves,
# whether the pages render, and that no placeholder text stands — and
# writes the signed record only when all five hold (N1, PRD §5).

def opendesign_tree_digest(root: Path) -> str:
    """A deterministic digest of the pinned tree's content: every
    file's sha256 with its relative path, sorted, hashed. Local edits
    to the read-only tree move this off the pin (I3)."""
    root = Path(root)
    lines = []
    for sub in OPENDESIGN_PATHS:
        base = root / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    digest = hashlib.sha256(p.read_bytes()).hexdigest()
                except OSError:
                    continue
                lines.append(f"{digest}  {p.relative_to(root).as_posix()}")
    h = hashlib.sha256()
    for line in sorted(lines):
        h.update(line.encode("utf-8") + b"\n")
    return h.hexdigest()


def opendesign_pin_state(root: Path | None = None) -> dict:
    """The pin and the tree, verified against each other. Ok only when
    the pin stands, the three directories stand, and the tree's
    measured digest equals the pin's — anything else stops the dispatch
    before a session opens (N3, exit 26)."""
    root = Path(root) if root else OPENDESIGN_ROOT
    pin_file = root / ".aidlc-pin.json"
    if not root.is_dir():
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": ("the upstream reference tree does not stand at "
                        f"{root}"),
                "remedy": ("scripts/install-opendesign.sh (the operator's "
                           "one-time host step; the caller never clones "
                           "or installs)"),
                "exit_code": EXIT_DESIGN_PIN}
    if not pin_file.is_file():
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": "no pin stands beside the tree",
                "remedy": "scripts/install-opendesign.sh --write-pin",
                "exit_code": EXIT_DESIGN_PIN}
    pin = load_json(pin_file, {})
    if not isinstance(pin, dict) or not pin.get("tag") \
            or not pin.get("tree_sha256"):
        return {"ok": False, "root": str(root), "pin": pin,
                "why": "the pin carries no tag or tree_sha256",
                "remedy": ("re-run scripts/install-opendesign.sh "
                           "--write-pin; a pin without both fields "
                           "verifies nothing"),
                "exit_code": EXIT_DESIGN_PIN}
    missing = [s for s in OPENDESIGN_PATHS if not (root / s).is_dir()]
    if missing:
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": f"pinned paths missing from the tree: {missing}",
                "remedy": ("re-run scripts/install-opendesign.sh; the "
                           "sparse set shrank under the pin"),
                "exit_code": EXIT_DESIGN_PIN}
    digest = opendesign_tree_digest(root)
    if digest != pin.get("tree_sha256"):
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "pinned_tree_sha256": pin.get("tree_sha256"),
                "measured_tree_sha256": digest,
                "why": ("the tree's measured digest no longer matches "
                        "the pin — the upstream tree was modified after "
                        "the pin was written"),
                "remedy": ("restore the tree (scripts/install-"
                           "opendesign.sh) or re-pin deliberately; a "
                           "modified reference cannot back a record"),
                "exit_code": EXIT_DESIGN_PIN}
    return {"ok": True, "root": str(root),
            "pin": {k: pin.get(k) for k in
                    ("tag", "sha", "sparse_paths", "installed_at",
                     "size_bytes", "tree_sha256")}}


def cmd_design_pin(root: Path, tag: str | None, write: bool) -> int:
    """N3's other half: write or verify the pin. The digest contract is
    the dispatch's own (opendesign_tree_digest) — the install script
    calls here so the pin and the check can never drift apart."""
    root = Path(root)
    if write:
        if not root.is_dir():
            return emit({"rejected": str(root),
                         "why": "no tree stands there to pin",
                         "remedy": "scripts/install-opendesign.sh"}, 2)
        proc = run(["git", "-C", str(root), "rev-parse", "HEAD"])
        sha = proc.stdout.strip() if proc.returncode == 0 else None
        pin = {"tag": tag or "unnamed", "sha": sha,
               "sparse_paths": list(OPENDESIGN_PATHS),
               "installed_at": now_iso(),
               "size_bytes": tree_bytes(root),
               "tree_sha256": opendesign_tree_digest(root)}
        pin_file = root / ".aidlc-pin.json"
        save_json(pin_file, pin)
        return emit({"written": str(pin_file), "pin": pin}, 0)
    state = opendesign_pin_state(root)
    return emit(state, 0 if state.get("ok") else state.get("exit_code", 2))


# ── Understand-Anything pin (C1/C2) ─────────────────────────────────
# Mirrors the opendesign pin trio (digest, pin_state, cmd_*_pin) but for
# the codegraph backend — a pure skill tree, not a binary.  The install
# script calls cmd_codegraph_pin so the pin and the check never drift.

def understand_anything_tree_digest(root: Path) -> str:
    """A deterministic digest of the pinned skill tree's content: every
    git-tracked file's sha256 (of its current on-disk bytes) with its
    relative path, sorted, hashed. Local edits to a tracked file move
    this off the pin (I3, PRD INV-10); untracked runtime artifacts
    (node_modules, dist, __pycache__, …) never enter the measurement, so
    a real analysis run that lazily installs tree-sitter bindings no
    longer trips a false pin mismatch (PRD INV-19)."""
    root = Path(root)
    lines = []
    for sub in UNDERSTAND_ANYTHING_PATHS:
        # git's tracked-file list is the authoritative "this is source,
        # not a runtime artifact" verdict — no need to mirror .gitignore
        # semantics by hand (globs drift, and .gitignore changing would
        # silently desync a hand-maintained exclude list). The sparse
        # cone fully contains each UNDERSTAND_ANYTHING_PATHS entry, so
        # ls-files and on-disk tracked content are in 1:1 correspondence.
        proc = run(["git", "-C", str(root), "ls-files", "-z", "--", sub])
        if proc.returncode != 0:
            continue
        for rel in proc.stdout.split("\0"):
            if not rel:
                continue
            p = root / rel
            if not p.is_file():
                continue
            try:
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                continue
            lines.append(f"{digest}  {rel}")
    h = hashlib.sha256()
    for line in sorted(lines):
        h.update(line.encode("utf-8") + b"\n")
    return h.hexdigest()


def understand_anything_pin_state(root: Path | None = None) -> dict:
    """The pin and the tree, verified against each other. Ok only when
    the pin stands, the plugin subtree stands, and the tree's measured
    digest equals the pin's — anything else stops the dispatch before a
    session opens (PRD §06 reverse gate, exit 26)."""
    root = Path(root) if root else UNDERSTAND_ANYTHING_ROOT
    pin_file = root / ".aidlc-pin.json"
    if not root.is_dir():
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": ("the Understand-Anything skill tree does not "
                        f"stand at {root}"),
                "remedy": ("scripts/install-understand-anything.sh (the "
                           "operator's one-time host step; the caller "
                           "never clones or installs)"),
                "exit_code": EXIT_DESIGN_PIN}
    if not pin_file.is_file():
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": "no pin stands beside the tree",
                "remedy": "scripts/install-understand-anything.sh --write-pin",
                "exit_code": EXIT_DESIGN_PIN}
    pin = load_json(pin_file, {})
    if not isinstance(pin, dict) or not pin.get("tag") \
            or not pin.get("tree_sha256"):
        return {"ok": False, "root": str(root), "pin": pin,
                "why": "the pin carries no tag or tree_sha256",
                "remedy": ("re-run scripts/install-understand-anything.sh "
                           "--write-pin; a pin without both fields "
                           "verifies nothing"),
                "exit_code": EXIT_DESIGN_PIN}
    missing = [s for s in UNDERSTAND_ANYTHING_PATHS if not (root / s).is_dir()]
    if missing:
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "why": f"pinned paths missing from the tree: {missing}",
                "remedy": ("re-run scripts/install-understand-anything.sh; "
                           "the sparse set shrank under the pin"),
                "exit_code": EXIT_DESIGN_PIN}
    digest = understand_anything_tree_digest(root)
    if digest != pin.get("tree_sha256"):
        return {"ok": False, "root": str(root), "pin": str(pin_file),
                "pinned_tree_sha256": pin.get("tree_sha256"),
                "measured_tree_sha256": digest,
                "why": ("the tree's measured digest no longer matches "
                        "the pin — the skill tree was modified after "
                        "the pin was written"),
                "remedy": ("restore the tree (scripts/install-"
                           "understand-anything.sh) or re-pin "
                           "deliberately; a modified reference cannot "
                           "back a codegraph dispatch"),
                "exit_code": EXIT_DESIGN_PIN}
    return {"ok": True, "root": str(root),
            "pin": {k: pin.get(k) for k in
                    ("tag", "sha", "sparse_paths", "installed_at",
                     "size_bytes", "tree_sha256")}}


def cmd_codegraph_pin(root: Path, tag: str | None, write: bool) -> int:
    """C1's other half: write or verify the pin. The digest contract is
    the dispatch's own (understand_anything_tree_digest) — the install
    script calls here so the pin and the check can never drift apart."""
    root = Path(root)
    if write:
        if not root.is_dir():
            return emit({"rejected": str(root),
                         "why": "no tree stands there to pin",
                         "remedy": "scripts/install-understand-anything.sh"}, 2)
        proc = run(["git", "-C", str(root), "rev-parse", "HEAD"])
        sha = proc.stdout.strip() if proc.returncode == 0 else None
        pin = {"tag": tag or "unnamed", "sha": sha,
               "sparse_paths": list(UNDERSTAND_ANYTHING_PATHS),
               "installed_at": now_iso(),
               "size_bytes": tree_bytes(root),
               "tree_sha256": understand_anything_tree_digest(root)}
        pin_file = root / ".aidlc-pin.json"
        save_json(pin_file, pin)
        return emit({"written": str(pin_file), "pin": pin}, 0)
    state = understand_anything_pin_state(root)
    return emit(state, 0 if state.get("ok") else state.get("exit_code", 2))


def resolve_work_ref(repo: Path, state: dict) -> dict:
    """Resolve the ref a change's work lives on.

    Order: the branch recorded at init > the task/<change> convention >
    HEAD. Any other task/* branch found while the chosen ref is HEAD is
    carried as `mismatch` - that is the country-b shape, and the shape
    every caller must be able to see.

    Z5: this is one of two text-identical copies (the other is in
    report.py); gate Y7 asserts they agree."""
    def _verify(ref):
        r = run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", ref])
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

    r = run(["git", "-C", str(repo), "for-each-ref",
             "--format=%(refname:short)", "refs/heads/task/"])
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


def change_surface(repo: Path, task_dir: Path) -> tuple[list, dict]:
    """The change's standing product surface: the landed diff plus the
    uncommitted files, the delivery surface's own excludes applied. The
    design role's applicability and write boundary both come from this
    measurement — never from what a prompt says the change is about.

    N1 (deliver-measures-work): the diff head is the task branch when it
    exists — on the planned route the work lives there before the merge,
    so measuring HEAD would see an empty tree. The ref is resolved by
    resolve_work_ref (recorded branch > task/{change} convention > HEAD).
    After the merge the branch is deleted and we fall back to HEAD, which
    then contains the work — both directions are correct (Q1). inline
    commits go straight to HEAD and have no task branch, so the fallback
    is the only path and behavior is unchanged (Q6)."""
    repo = Path(repo)
    state = load_json(Path(task_dir) / "state.json", {})
    base = state.get("base_sha")
    # N1: measure the work's ref via resolve_work_ref
    work = resolve_work_ref(repo, state)
    head = work["sha"]
    ref_kind = work["kind"]
    measured_ref = work["ref"]
    if head is None:
        head = run(["git", "-C", str(repo),
                    "rev-parse", "HEAD"]).stdout.strip()
    files: list = []
    if base and head and base != head:
        diff = run(["git", "-C", str(repo), "diff", "--name-only",
                    base, head])
        files += [f for f in diff.stdout.splitlines()
                  if f and not excluded(f)]
    status = git_status_paths(repo) or []
    for p in status:
        if p and not excluded(p) and p not in files:
            files.append(p)
    # W8: worktree visibility — uncommitted files in linked worktrees
    # are invisible to git_status_paths (which only sees the main tree).
    # Parse git worktree list --porcelain and collect uncommitted paths
    # from worktrees bound to the measured ref's branch.
    wt_paths: list = []
    measured_branch = None
    if measured_ref.startswith("refs/heads/"):
        measured_branch = measured_ref[len("refs/heads/"):]
    wt = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
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
                if cur_wt_path != str(repo) and cur_wt_branch == measured_branch:
                    wt_status = git_status_paths(Path(cur_wt_path)) or []
                    for p in wt_status:
                        if p and not excluded(p) and p not in files:
                            files.append(p)
                            wt_paths.append(p)
                cur_wt_path = None
                cur_wt_branch = None
    return files, {"base_sha": base, "head": head,
                   "landed": bool(base and head and base != head),
                   "measured": len(files),
                   "measured_ref": measured_ref, "ref_kind": ref_kind,
                   "worktree_paths": wt_paths}


def upstream_reaches(lines: list, root: Path) -> list:
    """Every upstream path the frames show the session reaching for:
    a read-shaped tool naming it, or a read-shaped shell command with
    it in the line. Generous on purpose — naming a path nobody read
    costs nothing; missing the one read that happened is the accident
    (D8)."""
    root_s = str(Path(root))
    out: list = []

    def add(text: str):
        for m in re.finditer(re.escape(root_s) + r"[A-Za-z0-9_./-]*",
                             text):
            if m.group(0) not in out:
                out.append(m.group(0))

    for call in _tool_invocations(lines):
        tool = (call["tool"] or "").lower()
        if "read" in tool:
            for v in call["arguments"].values():
                if isinstance(v, str) and root_s in v:
                    add(v)
        command = call["arguments"].get("command")
        if isinstance(command, str) and root_s in command \
                and re.search(r"\b(cat|head|tail|less|grep|sed|awk|"
                              r"find|rg)\b", command):
            add(command)
    return out


_REF_RES = (re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""",
                       re.I),
            re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I))
_SKIP_REFS = ("#", "data:", "mailto:", "javascript:", "tel:")
_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
_HINT_RELS = ("preconnect", "dns-prefetch")


def _hint_refs(text: str) -> set:
    """The hrefs of preconnect/dns-prefetch link tags — connection
    hints a browser opens but never fetches, so they are not asset
    references. Measured live: fonts.googleapis.com's root answers 404
    to everything because it serves no root resource, and a hint href
    is not a resource."""
    out = set()
    for tag in _LINK_TAG_RE.findall(text):
        rel = re.search(r"""\brel\s*=\s*["']([^"']+)["']""", tag, re.I)
        href = re.search(r"""\bhref\s*=\s*["']([^"']+)["']""", tag, re.I)
        if rel and href and rel.group(1).strip().lower() in _HINT_RELS:
            out.add(href.group(1).strip())
    return out


def _page_refs(text: str) -> list:
    refs: list = []
    for rx in _REF_RES:
        for m in rx.finditer(text):
            r = m.group(1).strip()
            if r and r not in refs:
                refs.append(r)
    return refs


def asset_check(pages: list, repo: Path,
                remote: bool = True) -> dict:
    """Every referenced local asset must exist; every remote reference
    must answer. Placeholder images live here as much as in the text
    scan — a src that resolves to nothing is a fact, not a style
    opinion (PRD §5.3)."""
    local_missing, remote_unreachable = [], []
    checked = 0

    def _answers(url: str) -> bool:
        """HEAD, then GET on its 404 — HEAD is the cheap ask, GET is
        what a browser actually does; a resource is unreachable only
        when both say no."""
        def _fetch(method):
            req = urllib.request.Request(
                url, method=method,
                headers={"User-Agent": "ai-dlc-design-facts/1"})
            return urllib.request.urlopen(req, timeout=8)
        try:
            _fetch("HEAD").close()
            return True
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return True          # answered: not missing, just refused
            try:
                with _fetch(None) as r:
                    r.read(256)
                return True
            except urllib.error.HTTPError as e2:
                return e2.code != 404
            except (urllib.error.URLError, OSError, ValueError):
                return False
        except (urllib.error.URLError, OSError, ValueError):
            return False

    for rel in pages:
        page = repo / rel
        try:
            text = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            local_missing.append(f"{rel} (the page itself unreadable)")
            continue
        hints = _hint_refs(text)
        for ref in _page_refs(text):
            if any(ref.startswith(s) for s in _SKIP_REFS):
                continue
            if ref in hints:
                continue          # a connection hint, not a fetch
            checked += 1
            target = ref.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            if target.startswith(("http://", "https://")) \
                    or target.startswith("//"):
                if not remote:
                    continue
                url = target if target.startswith("http") \
                    else "https:" + target
                if not _answers(url):
                    remote_unreachable.append(f"{rel} -> {url}")
            else:
                # M3 (F3): a root-absolute href (/favicon.svg) is
                # document-root-relative, not filesystem-root-relative.
                # pathlib's absolute operand overrides the base —
                # (page.parent / "/x") yields "/x" — so resolve against
                # the repo root instead.
                if target.startswith("/"):
                    resolved = (repo / target.lstrip("/")).resolve()
                else:
                    resolved = (page.parent / target).resolve()
                if not resolved.exists():
                    local_missing.append(
                        f"{rel} -> {target}")
    return {"local_missing": local_missing,
            "remote_unreachable": remote_unreachable,
            "refs_checked": checked}


def render_check(pages: list, repo: Path) -> list:
    """Serve the repo locally and fetch each page: an HTTP 200 with a
    non-empty DOM. What a browser would see is the page the record
    stands behind (PRD §5.4)."""

    class _Count(html.parser.HTMLParser):
        nodes = 0

        def handle_starttag(self, tag, attrs):
            self.nodes += 1

    results = []

    class _Quiet(http.server.SimpleHTTPRequestHandler):  # noqa: N801
        # serves the repo's own directory; the access log is noise here
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(repo), **kwargs)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        for rel in pages:
            url = f"http://127.0.0.1:{port}/{rel}"
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    body = r.read().decode("utf-8", errors="replace")
                    status = r.status
            except urllib.error.HTTPError as e:
                results.append({"page": rel, "status": e.code,
                                "dom_nodes": 0})
                continue
            except (urllib.error.URLError, OSError) as e:
                results.append({"page": rel, "status": 0,
                                "dom_nodes": 0, "error": str(e)})
                continue
            c = _Count()
            try:
                c.feed(body)
            except Exception:
                pass
            results.append({"page": rel, "status": status,
                            "dom_nodes": c.nodes})
    finally:
        srv.shutdown()
        t.join(timeout=5)
    return results


def placeholder_scan(files: list, repo: Path) -> list:
    """The placeholder patterns the upstream's own example prompts
    forbid (E8): lorem ipsum, a TODO marker, or a placeholder image
    reference. An input's placeholder= attribute is form markup, not
    placeholder content — deliberately not matched."""
    hits = []
    for rel in files:
        try:
            text = (repo / rel).read_text(encoding="utf-8",
                                          errors="replace")
        except OSError:
            continue
        for rx in PLACEHOLDER_RES:
            m = rx.search(text)
            if m:
                hits.append(f"{rel}: {m.group(0)[:60]!r}")
                break
    return hits


def design_prompt(change: str, surface: dict, template: str | None,
                  system: str | None) -> str:
    files = "\n".join(f"  {f}" for f in surface.get("surface_files", []))
    chosen = ""
    if template:
        chosen += (f"\nUse exactly this template/skill: {template}. "
                   "Read its SKILL.md in full before you touch a file.")
    if system:
        chosen += (f"\nPair it with exactly this design system: "
                   f"{system}.")
    return f"""You are the UI Designer for the delivery '{change}' in this repository.

The measured frontend surface to beautify:
{files}

Reach the read-only OpenDesign tree through the ui-designer skill:{chosen}
- pick exactly one primary skill from the tree by its frontmatter
  (od.mode / category / scenario), optionally one design system;
- read the chosen SKILL.md in full before you write anything;
- the template's fixed values stay fixed where it says fixed;
- real content and real data throughout — lorem ipsum, placeholder
  images and TODO markers are failures, not style choices;
- every local asset your pages reference must exist when you are done.

Write only inside this repository, only into its product surface —
nothing into the upstream tree, nothing into .ai-dlc/ or openspec/.

When you are done, report: the skill and design-system paths you chose
(the exact paths you read), every file you wrote, and the local assets
the pages reference."""


def run_design_session(change: str, prompt: str, repo: Path,
                       task_dir: Path, mode: str,
                       timeout: int) -> tuple[dict, int]:
    """One plane session for the design role — the same shape as the
    tool dispatches (fresh session, frames on disk, duration recorded)
    but its working directory is the repo: this role writes the
    product surface, not the plane's tree."""
    started = time.monotonic()
    started_at = now_iso()
    evidence = next_evidence(task_dir, "design")
    seq = re.search(r"-(\d+)\.jsonl$", evidence.name)
    session_name = f"design-{change}-{seq.group(1) if seq else '001'}"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(repo),
           "--mode", mode, "--timeout", str(timeout),
           "--session", session_name]
    timed_out = False
    client_rc = None
    try:
        with evidence.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                                  text=True, cwd=str(repo),
                                  timeout=timeout + 60)
        client_rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    frames = evidence.read_text(encoding="utf-8",
                                errors="replace").splitlines()
    v = judge_frames(frames)
    elapsed = round(time.monotonic() - started, 3)
    out = {"dispatch": "design", "change": change, "mode": mode,
           "repo": str(repo), "client": CLIENT,
           "client_rc": client_rc, "timed_out": timed_out,
           "evidence": str(evidence), "session_name": session_name,
           "started_at": started_at, "ended_at": now_iso(),
           "elapsed_seconds": elapsed,
           "round_complete": v["round_complete"],
           "interrupted": v["interrupted"],
           "envelope_note": ("the record is the frames' — the role's "
                             "conclusion sentence was never read")}
    return out, frames


def run_codegraph_session(change: str, prompt: str, repo: Path,
                          task_dir: Path, mode: str,
                          timeout: int) -> tuple[dict, list]:
    """One plane session for the codegraph role — the same shape as
    run_design_session (fresh session, frames on disk, duration recorded)
    with its working directory set to the repo: this role writes
    codegraph/impact-brief.md into the repo, not the plane's tree."""
    started = time.monotonic()
    started_at = now_iso()
    evidence = next_evidence(task_dir, "codegraph")
    seq = re.search(r"-(\d+)\.jsonl$", evidence.name)
    session_name = f"codegraph-{change}-{seq.group(1) if seq else '001'}"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    cmd = [CLIENT, "chat", prompt, "--jsonl", "--cwd", str(repo),
           "--mode", mode, "--timeout", str(timeout),
           "--session", session_name]
    timed_out = False
    client_rc = None
    try:
        with evidence.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                                  text=True, cwd=str(repo),
                                  timeout=timeout + 60)
        client_rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    frames = evidence.read_text(encoding="utf-8",
                                errors="replace").splitlines()
    v = judge_frames(frames)
    elapsed = round(time.monotonic() - started, 3)
    out = {"dispatch": "codegraph", "change": change, "mode": mode,
           "repo": str(repo), "client": CLIENT,
           "client_rc": client_rc, "timed_out": timed_out,
           "evidence": str(evidence), "session_name": session_name,
           "started_at": started_at, "ended_at": now_iso(),
           "elapsed_seconds": elapsed,
           "round_complete": v["round_complete"],
           "interrupted": v["interrupted"],
           "envelope_note": ("the record is the frames' — the role's "
                             "conclusion sentence was never read")}
    return out, frames


def design_facts(frames: list, repo: Path, task_dir: Path,
                 root: Path, healed: list | None = None) -> dict:
    """The five facts, from the frames and the filesystem. `failed`
    names each fact that did not hold — the dispatch writes no record
    until the list is empty (D8's whole point). `healed` carries paths
    self-healed by N1 — they are filtered from `outside` (the write
    was an accident, cleaned and recorded, not a lingering violation)."""
    healed = healed or []
    repo = Path(repo)
    reaches = upstream_reaches(frames, root)
    skill_reads = [r for r in reaches if r.endswith("SKILL.md")
                   and (Path(root) in Path(r).resolve().parents
                        or str(root) in r)]
    # a probe names paths that never stood — the shipped tree keeps no
    # SKILL.md under design-systems/, and a session that probed for one
    # leaves those names in its commands. The template is a read that
    # landed: a path that stands, and a sha256 the caller can compute
    # (measured live, ud1-web round 2: the probe path was picked and
    # hashed null).
    standing = [r for r in skill_reads if Path(r).is_file()]
    template = None
    for r in standing:
        if "/design-templates/" in r or "/design-systems/" in r:
            template = r
            break
    template = template or (standing[0] if standing else None)

    # writes: what the frames say the role wrote, verified where they
    # landed — the record's file list is the verified intersection
    declared = frame_write_abs(frames, repo)
    files, outside, discarded = [], [], []
    self_check_writes = []
    for w in declared:
        p = Path(w)
        try:
            rel = p.relative_to(repo).as_posix()
        except ValueError:
            # M2 (F2): a /tmp path the session created for self-check
            # (local server log, temp probe) is not a product-surface
            # violation — the role must start a server for render_check.
            # Narrow: only /tmp, only files (not dirs), not in product.
            s = str(p)
            if s.startswith("/tmp/") and not p.is_dir():
                self_check_writes.append(s)
            else:
                outside.append(w)
            continue
        if excluded(rel) or rel.startswith("openspec/"):
            outside.append(rel)
            continue
        if not p.is_file():
            # M1 (F1): a phantom candidate from quoted-text leakage
            # (grep patterns, python -c snippets) is discarded, not a
            # failure — the path neither stands nor was ever written.
            discarded.append(rel)
            continue
        files.append({"path": rel, "bytes": p.stat().st_size,
                      "sha256": hashlib.sha256(
                          p.read_bytes()).hexdigest()})
    surface, _detail = change_surface(repo, task_dir)
    measured = design_surface(surface, repo,
                              head=_detail.get("ref_kind") == "task_branch"
                              and _detail.get("head") or None)
    pages = [f for f in measured.get("surface_files", [])
             if f.endswith((".html", ".htm"))][:10]
    pages_capped = measured.get("surface_files_total", 0) > 10
    assets = asset_check(pages, repo) if pages else \
        {"local_missing": [], "remote_unreachable": [],
         "refs_checked": 0}
    render = render_check(pages, repo) if pages else []
    placeholders = placeholder_scan(
        [f for f in measured.get("surface_files", [])
         if f.endswith((".html", ".htm", ".css", ".md"))], repo)

    failed = []
    if not template:
        if skill_reads:
            failed.append(
                "the frames' SKILL.md reads name paths that do not "
                "stand on the tree — probes, not reads; the record "
                "stands behind no read that landed (D8)")
        else:
            failed.append(
                "no upstream SKILL.md read appears in the frames — the "
                "role claims work the frames do not show (D8)")
    if not files:
        failed.append("the frames show no file written into the "
                      "product surface")
    if outside:
        # N1: filter self-healed paths — the write was an accident,
        # cleaned and recorded, not a lingering violation (Z2).
        healed_set = {str(Path(h).resolve()) for h in healed}
        outside = [o for o in outside
                   if str(Path(o).resolve()) not in healed_set
                   and o not in healed]
    if outside:
        failed.append(f"writes outside the product surface: "
                      f"{outside[:5]}")
    if assets.get("local_missing") or assets.get("remote_unreachable"):
        failed.append("referenced assets do not resolve "
                      f"(local missing {len(assets['local_missing'])}, "
                      f"remote unreachable "
                      f"{len(assets['remote_unreachable'])})")
    # M3 (F3): self-consistency — a path with sha256 in files must not
    # also appear in local_missing. That contradiction is a judge defect
    # (the same record says the file exists and doesn't), not real evidence.
    file_paths_with_sha = {f["path"] for f in files if f.get("sha256")}
    for missing in assets.get("local_missing", []):
        target = missing.split(" -> ")[-1] if " -> " in missing else missing
        target_stripped = target.lstrip("/")
        if target_stripped in file_paths_with_sha:
            failed.append(f"self-contradiction: {target} has sha256 in "
                          f"files but is listed in local_missing")
    for r in render:
        if r.get("status") != 200 or not r.get("dom_nodes"):
            failed.append(f"page {r.get('page')} did not render "
                          f"(status {r.get('status')}, "
                          f"dom_nodes {r.get('dom_nodes')})")
            break
    if placeholders:
        failed.append(f"placeholder content stands in the surface: "
                      f"{placeholders[:3]}")

    tsha = None
    if template:
        try:
            tsha = hashlib.sha256(
                Path(template).read_bytes()).hexdigest()
        except OSError:
            pass
    return {"failed": failed, "upstream_reads": reaches[:20],
            "template": ({"path": template, "sha256": tsha}
                         if template else None),
            "files": files, "writes_outside": outside,
            "discarded_candidates": discarded,
            "assets": assets, "render": render,
            "render_self_check_writes": self_check_writes,
            "render_pages_cap": 10 if pages_capped else None,
            "placeholders": placeholders,
            "surface_after": measured}


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter without PyYAML — handles block scalars
    (``description: |``), two-level nesting under ``od.``, quote
    normalization, inline lists, and boolean values.

    Returns a flat dict with dotted keys for nested fields:
    ``od.mode``, ``od.design_system.requires``, ``od.craft.requires``
    (list), ``od.design_system.sections`` (list), etc.
    """
    m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    raw = m.group(1).splitlines()
    fm: dict = {}
    i = 0
    n = len(raw)
    # stack of (prefix, indent) for nested blocks like od: → design_system:
    # prefix is the dotted key prefix; indent is the indentation level
    block_stack: list[tuple[str, int]] = [("", -1)]
    in_list_key: str | None = None
    in_list_indent: int = -1

    def _strip_val(v: str) -> str:
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        return v

    def _parse_inline_list(v: str) -> list[str] | None:
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [_strip_val(x.strip()) for x in inner.split(",")]
        return None

    def _current_prefix() -> str:
        return block_stack[-1][0]

    while i < n:
        line = raw[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip())

        # Pop block stack if we've dedented past the current block
        while block_stack and indent <= block_stack[-1][1]:
            block_stack.pop()
            if not block_stack:
                block_stack.append(("", -1))

        # Block scalar continuation (for | and >)
        # handled inline below via lookahead, not here

        # List item
        if stripped.startswith("- "):
            val = _strip_val(stripped[2:])
            if in_list_key is not None:
                fm.setdefault(in_list_key, []).append(val)
            i += 1
            continue

        # key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            prefix = _current_prefix()
            full_key = f"{prefix}{key}" if prefix else key

            # Block scalar: | or >
            if val in ("|", ">"):
                fold = val == ">"
                block_lines: list[str] = []
                j = i + 1
                while j < n:
                    nl = raw[j]
                    ns = nl.strip()
                    if not ns:
                        block_lines.append("")
                        j += 1
                        continue
                    nl_indent = len(nl) - len(nl.lstrip())
                    if nl_indent <= indent:
                        break
                    block_lines.append(ns)
                    j += 1
                if fold:
                    fm[full_key] = " ".join(block_lines).strip()
                else:
                    fm[full_key] = "\n".join(block_lines).strip()
                i = j
                in_list_key = None
                continue

            # Empty value → could be nested block or list
            if val == "":
                # Peek ahead: next non-empty line indented further → nested block
                j = i + 1
                while j < n and not raw[j].strip():
                    j += 1
                if j < n:
                    nl_indent = len(raw[j]) - len(raw[j].lstrip())
                    if nl_indent > indent:
                        # Check if it's a list (starts with "- ")
                        if raw[j].strip().startswith("- "):
                            in_list_key = full_key
                            in_list_indent = nl_indent
                            i += 1
                            continue
                        else:
                            # Nested block
                            block_stack.append((full_key + ".", indent))
                            i += 1
                            continue
                in_list_key = None
                i += 1
                continue

            # Inline list
            il = _parse_inline_list(val)
            if il is not None:
                fm[full_key] = il
                in_list_key = None
                i += 1
                continue

            # Boolean / scalar
            sv = _strip_val(val)
            if sv == "true":
                fm[full_key] = True
            elif sv == "false":
                fm[full_key] = False
            else:
                fm[full_key] = sv
            in_list_key = None
            i += 1
            continue

        i += 1
    return fm


def _scan_design_candidates(root: Path) -> list[dict]:
    """Scan all OpenDesign frontmatter candidates across the three trees
    (skills, design-templates, design-systems). Returns a list of
    {path, sha256, kind, dir, name, mode, category, scenario, surface,
     platform, zh_name, triggers, description, design_system, craft,
     has_example_html, body_bytes} dicts. This is the 428-candidate
    scan — millisecond, no session, no model."""
    root = Path(root)
    candidates = []
    for subdir, kind in (("skills", "skill"),
                         ("design-templates", "template"),
                         ("design-systems", "system")):
        base = root / subdir
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
                continue
            skill_md = d / "SKILL.md"
            manifest = d / "manifest.json"
            if skill_md.is_file():
                try:
                    text = skill_md.read_text(encoding="utf-8",
                                              errors="replace")
                except OSError:
                    continue
                fm = _parse_frontmatter(text)
                try:
                    raw_bytes = skill_md.read_bytes()
                    sha = hashlib.sha256(raw_bytes).hexdigest()
                    body_bytes = len(raw_bytes)
                except OSError:
                    sha = None
                    body_bytes = 0
                has_example = (d / "example.html").is_file()
                ds_requires = fm.get("od.design_system.requires")
                ds_sections = fm.get("od.design_system.sections", [])
                craft_requires = fm.get("od.craft.requires", [])
                candidates.append({
                    "path": str(skill_md), "sha256": sha,
                    "kind": kind, "dir": d.name,
                    "name": fm.get("name", d.name),
                    "mode": fm.get("od.mode", ""),
                    "category": fm.get("category", ""),
                    "scenario": fm.get("od.scenario",
                                       fm.get("scenario", "")),
                    "surface": fm.get("od.surface",
                                      fm.get("surface", "")),
                    "platform": fm.get("od.platform", ""),
                    "zh_name": fm.get("zh_name", ""),
                    "triggers": fm.get("triggers", []),
                    "description": fm.get("description", ""),
                    "audience": fm.get("od.audience", ""),
                    "tone": fm.get("od.tone", ""),
                    "design_system": {"requires": bool(ds_requires),
                                      "sections": ds_sections} if ds_requires else None,
                    "craft": {"requires": craft_requires} if craft_requires else None,
                    "has_example_html": has_example,
                    "body_bytes": body_bytes,
                })
            elif manifest.is_file():
                try:
                    data = json.loads(
                        manifest.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                try:
                    sha = hashlib.sha256(
                        manifest.read_bytes()).hexdigest()
                except OSError:
                    sha = None
                candidates.append({
                    "path": str(manifest), "sha256": sha,
                    "kind": kind, "dir": d.name,
                    "name": data.get("name", d.name),
                    "mode": "", "category": data.get("category", ""),
                    "scenario": "", "surface": "",
                    "platform": "", "zh_name": "",
                    "triggers": [],
                    "description": data.get("description", ""),
                    "audience": "",
                    "tone": "",
                    "design_system": None,
                    "craft": None,
                    "has_example_html": False,
                    "body_bytes": 0,
                })
    return candidates
def _tokenize_query(text: str) -> set[str]:
    """Tokenize text for IDF retrieval: ASCII words (2+ chars) AND
    CJK bigrams.  ``管理后台`` → ``管理``, ``理后``, ``后台``.
    This makes 207 Chinese triggers reachable without a segmentation
    library dependency."""
    tokens: set[str] = set()
    # ASCII tokens: [a-z0-9]{2,} (2-char minimum to cover ui/ai)
    for m in re.finditer(r"[a-z0-9]{2,}", text.lower()):
        tokens.add(m.group())
    # CJK bigrams: any run of CJK characters → overlapping pairs
    for cjk_run in re.finditer(r"[一-鿿㐀-䶿]+", text):
        s = cjk_run.group()
        for i in range(len(s) - 1):
            tokens.add(s[i:i + 2])
        # Also add the full run as a token (for short triggers like 后台)
        if len(s) >= 2:
            tokens.add(s)
    return tokens


_NEGATION_LEAD = {"not", "no", "without", "never"}
# Chinese negation markers: multi-character prefixes only, deliberately
# NOT bare "不" — a clause literally starting with 不错/不仅/不但 is not
# a pure exclusion and bare-不 would over-trigger on ordinary Chinese
# prose that happens to open a clause with it.
_NEGATION_PREFIX_ZH = ("不需要", "不是", "没有")

_CLAUSE_DELIM = r"[,.;\n—–，。；、]"
_CLAUSE_SPLIT_RE = re.compile(_CLAUSE_DELIM)
_CLAUSE_SPLIT_CAPTURE_RE = re.compile(f"({_CLAUSE_DELIM})")
_SOFT_WRAP_RE = re.compile(r"(?<!\n)\n(?!\n)")


def _normalize_soft_wraps(text: str) -> str:
    """Collapse a single newline (a soft line-wrap inside one logical
    sentence — common in hand-wrapped Markdown prose, e.g. 'not an\\n
    internal admin dashboard') into a space, so clause-splitting on \\n
    doesn't sever a negation particle from the noun it excludes.  A
    blank line (\\n\\n, a real paragraph break) is left alone."""
    return _SOFT_WRAP_RE.sub(" ", text)


def _clause_is_negated(clause: str) -> bool:
    stripped = clause.strip().lower()
    if not stripped:
        return False
    words = stripped.split()
    if words and (words[0] in _NEGATION_LEAD or
                  (len(words) > 1 and words[1] in _NEGATION_LEAD)):
        return True
    return any(stripped.startswith(p) for p in _NEGATION_PREFIX_ZH)


def _negated_tokens(text: str) -> set[str]:
    """Tokens inside a clause led by a negation particle ('not a slide
    deck', 'without pricing', '不需要后台') — a proposal excluding X
    should not credit X as positive query signal.  Clause-scoped (split
    on sentence/comma punctuation, ASCII and CJK), not single-next-word,
    because the excluded noun is usually not the word immediately after
    the negation marker."""
    negated: set[str] = set()
    for clause in _CLAUSE_SPLIT_RE.split(_normalize_soft_wraps(text.lower())):
        if _clause_is_negated(clause):
            negated |= _tokenize_query(clause)
    return negated


def _strip_negated_clauses(text: str) -> str:
    """Remove clauses led by a negation particle from the text used for
    exact-phrase substring matching (rule 1) — a proposal excluding X
    must not let a candidate's trigger phrase for X match verbatim
    inside the excluded clause.  Delimiters are preserved (not deleted)
    so removing a clause never accidentally splices two unrelated
    clauses into a new substring."""
    parts = _CLAUSE_SPLIT_CAPTURE_RE.split(_normalize_soft_wraps(text))
    out = []
    for i in range(0, len(parts), 2):
        clause = parts[i]
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        out.append("" if _clause_is_negated(clause) else clause)
        out.append(delim)
    return "".join(out)


def _extract_change_keywords(change: str, repo: Path,
                             task_dir: Path) -> dict:
    """Extract query tokens from the change's identifier, proposal.md,
    design.md, and tasks.md.  Returns {surface_hint, query_tokens,
    query_text, keywords} where query_tokens is a set of ASCII words
    and CJK bigrams for IDF retrieval, and keywords is kept for
    backward compatibility with the legacy scorer."""
    surface_hint = None
    # infer surface from the repo's product files
    try:
        files, _detail = change_surface(repo, task_dir)
        surface = design_surface(files, repo)
        if surface.get("classes"):
            cls = surface["classes"]
            if "web" in cls:
                surface_hint = "web"
            elif "deck" in cls:
                surface_hint = "deck"
    except Exception:
        pass

    # Gather source texts: change identifier + proposal + design + tasks
    texts = []
    # change name itself is a signal (ch-country-a-tourism → country-a, tourism)
    texts.append(change.replace("-", " ").replace("_", " "))
    for name in ("proposal.md", "design.md", "tasks.md"):
        for p in (task_dir / name,
                  repo / "openspec" / "changes" / change / name):
            if p.is_file():
                try:
                    texts.append(p.read_text(encoding="utf-8",
                                             errors="replace"))
                except OSError:
                    pass
    full_text = "\n".join(texts)
    query_tokens = _tokenize_query(full_text) - _negated_tokens(full_text)

    # backward-compat keywords set (used by legacy scorer)
    keywords = set(t for t in query_tokens if re.match(r"^[a-z]{3,}$", t))

    return {"surface_hint": surface_hint,
            "query_tokens": query_tokens,
            "keywords": keywords,
            "text": _strip_negated_clauses(full_text).lower()}


def _filter_candidates(candidates: list[dict],
                       surface_hint: str | None) -> tuple[list[dict], int]:
    """L1 hard filter: mode/surface are qualification, not score.

    Returns (eligible_candidates, filtered_count).
    - web → mode in {prototype, template}, surface in {null, "web"}
    - deck → mode == deck, surface in {null, "web"}
    - kind == "system" → always excluded from main pool
    - unknown/other → no filter (pass all non-system)
    """
    eligible = []
    for c in candidates:
        # systems are never in the main selection pool
        if c.get("kind") == "system":
            continue
        mode = c.get("mode", "")
        surface = c.get("surface", "")
        if surface_hint == "web":
            if mode not in ("prototype", "template", ""):
                continue
            if surface and surface != "web":
                continue
        elif surface_hint == "deck":
            if mode and mode != "deck":
                continue
            if surface and surface not in ("web", "deck"):
                continue
        eligible.append(c)
    return eligible, len(candidates) - len(eligible)


def _score_candidate(cand: dict, change_kw: dict,
                     idf: dict | None = None) -> float:
    """Score a candidate against the change's query tokens using
    IDF-weighted retrieval.  Triggers are the primary signal (per
    upstream OpenDesign's activation mechanism).

    Set AI_DLC_DESIGN_SELECT_LEGACY=1 to use the old bonus-based scorer.
    """
    if os.environ.get("AI_DLC_DESIGN_SELECT_LEGACY"):
        return _score_candidate_legacy(cand, change_kw)

    query_tokens = change_kw.get("query_tokens", set())
    if not query_tokens:
        return 0.0

    def _idf(tok: str) -> float:
        if idf:
            return idf.get(tok, math.log(428 / 2))  # unseen → high idf
        return 1.0  # no IDF table → uniform

    score = 0.0
    query_text = change_kw.get("text", "")
    triggers = cand.get("triggers", [])
    name = cand.get("name", "").lower()
    dir_name = cand.get("dir", "").lower()
    desc = cand.get("description", "").lower()
    scen = cand.get("scenario", "").lower()
    cat = cand.get("category", "").lower()
    plat = cand.get("platform", "").lower()

    # 1. Trigger phrase match (strongest signal: 12 × idf)
    #    A trigger phrase appearing verbatim in the query text is the
    #    strongest possible signal — score it once per unique phrase.
    trigger_phrases_matched = 0
    for trig in triggers:
        tl = trig.lower()
        toks = _tokenize_query(tl)
        # Only score as a "phrase" match when the trigger has ≥2 tokens.
        # A single-token trigger's "phrase" is the token itself, so the
        # verbatim-in-query test is identical to rule 2's token test —
        # applying both would double-count the same hit (12×idf on top
        # of the 5×idf from rule 2).  Multi-token triggers still get the
        # full 12×idf/tok strongest signal when they appear verbatim.
        if len(toks) >= 2 and tl in query_text:
            for tok in toks:
                score += 12.0 * _idf(tok)
            trigger_phrases_matched += 1
    # 2. Trigger token match (5 × idf) — deduplicate tokens across
    #    all triggers so a candidate with 5 triggers containing
    #    "dashboard" doesn't out-score one with 1 trigger "dashboard".
    trigger_tokens = set()
    for trig in triggers:
        trigger_tokens.update(_tokenize_query(trig.lower()))
    for tok in trigger_tokens:
        if tok in query_tokens:
            score += 5.0 * _idf(tok)
    # 3. Name / dir token match (5 × idf)
    for tok in _tokenize_query(name):
        if tok in query_tokens:
            score += 5.0 * _idf(tok)
    for tok in _tokenize_query(dir_name):
        if tok in query_tokens:
            score += 5.0 * _idf(tok)
    # 4. Description token match (2 × idf)
    for tok in _tokenize_query(desc):
        if tok in query_tokens:
            score += 2.0 * _idf(tok)
    # 5. Scenario / category / platform token match (2 × idf)
    for field in (scen, cat, plat):
        for tok in _tokenize_query(field):
            if tok in query_tokens:
                score += 2.0 * _idf(tok)

    return score


def _score_candidate_legacy(cand: dict, change_kw: dict) -> int:
    """Legacy bonus-based scorer — kept for A/B via
    AI_DLC_DESIGN_SELECT_LEGACY=1."""
    score = 0
    kw = change_kw.get("keywords", set())
    hint = change_kw.get("surface_hint")
    if hint and cand.get("surface") == hint:
        score += 50
    if hint == "web":
        if cand.get("mode") == "prototype" and cand.get("surface") == "web":
            score += 30
        elif cand.get("mode") == "design-system":
            score += 15
        elif cand.get("mode") == "template":
            score += 10
    elif hint == "deck":
        if cand.get("mode") == "deck":
            score += 30
    name = cand.get("name", "").lower()
    cat = cand.get("category", "").lower()
    scen = cand.get("scenario", "").lower()
    triggers = [t.lower() for t in cand.get("triggers", [])]
    desc = cand.get("description", "").lower()
    for term in kw:
        if term in name:
            score += 5
        if term in cat:
            score += 3
        if term in scen:
            score += 3
        if any(term in t for t in triggers):
            score += 4
        if term in desc:
            score += 1
    if cand.get("kind") == "skill":
        score += 2
    return score


def _tiebreak_key(cand: dict) -> tuple:
    """Tie-break by content量, not kind: has_example_html → body_bytes → dir."""
    return (
        1 if cand.get("has_example_html") else 0,
        cand.get("body_bytes", 0),
        cand.get("dir", ""),
    )


def _design_prefilter(change: str, repo: Path, task_dir: Path,
                      top_n: int = 12) -> tuple[list, list, dict]:
    """The pre-filter layer: L1 hard filter → L2 IDF retrieval →
    top-N shortlist.  Returns (shortlist, scored_list, change_kw).

    L1: mode/surface qualification filter (not bonus).
    L2: IDF-weighted trigger/name/description scoring with CJK bigram.
    Tie-break: has_example_html → body_bytes → dir (not kind).
    """
    root = Path(OPENDESIGN_ROOT)
    candidates = _scan_design_candidates(root)
    change_kw = _extract_change_keywords(change, repo, task_dir)

    # Build IDF table
    index = _build_design_index(root)
    idf = index["idf"]

    # L1 hard filter
    eligible, filtered = _filter_candidates(candidates,
                                             change_kw.get("surface_hint"))
    change_kw["eligible"] = len(eligible)
    change_kw["filtered_from"] = len(candidates)

    # L2 IDF scoring
    scored = sorted(
        ((_score_candidate(c, change_kw, idf), c) for c in eligible),
        key=lambda x: (x[0], _tiebreak_key(x[1])),
        reverse=True)
    shortlist = [cand for _score, cand in scored[:top_n]]
    return shortlist, scored, change_kw


def _needs_arbitration(cand: dict) -> bool:
    """A candidate needs independent judgment before it can be trusted
    on the deterministic fast path — it declares a specific
    audience/tone (bakes in an uncorrectable aesthetic, no design_system
    to re-match), self-describes as a standalone/single-purpose
    component (structural scope narrower than what a multi-section
    change is asking for), or is a widget (a small UI fragment, not a
    page)."""
    if cand.get("audience") or cand.get("tone"):
        return True
    desc = (cand.get("description") or "").lower()
    if "standalone" in desc:
        return True
    if "widget" in desc:
        return True
    return False


def _first_unflagged(scored: list, fallback: dict) -> dict:
    for _, c in scored:
        if not _needs_arbitration(c):
            return c
    return fallback


def cmd_design_select(change: str, repo: Path,
                      task_dir: Path | None,
                      mode: str = "code.normal") -> int:
    """D0 SELECT — L1 hard filter → L2 IDF retrieval → L4 margin-gated
    session.  When margin >= 0.25 the deterministic winner is used with
    no session.  When margin < 0.25 a 90s arbiter session is opened with
    full candidate context (triggers, description).  Output: new schema
    with method, margin, eligible, craft_requires."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    root = Path(OPENDESIGN_ROOT)
    # check applicability first — a backend change buys no design
    files, detail = change_surface(repo, task_dir)
    surface = design_surface(files, repo,
                             head=detail.get("ref_kind") == "task_branch"
                             and detail.get("head") or None)
    if not surface.get("applicable"):
        return emit({"change": change, "repo": str(repo),
                     "applicable": False,
                     "why": ("the change's measured product surface "
                             "carries no web or deck file — design-select "
                             "produces no selection"),
                     **detail, "measured_surface": surface}, 0)
    # L1 + L2 via _design_prefilter
    shortlist, scored, change_kw = _design_prefilter(change, repo, task_dir,
                                                      top_n=12)
    if not shortlist:
        return emit({"change": change, "repo": str(repo),
                     "applicable": True,
                     "error": ("no eligible candidates after L1 filter"),
                     "candidates_considered": 428}, 1)
    best_score, best = scored[0]
    runner_up_score = scored[1][0] if len(scored) > 1 else 0
    margin = (best_score - runner_up_score) / max(best_score, 1)

    chosen = best
    reason = (f"IDF-weighted score {best_score:.1f} vs "
              f"{runner_up_score:.1f} (margin {margin:.2f})")
    method = "deterministic"
    degraded = False

    # Narrow-aesthetic gate: if top1 declares a specific audience/tone,
    # never let it sail through the deterministic fast path regardless of
    # margin — force the 90s arbiter session so the declared aesthetic gets
    # checked against the change's business context.
    narrow_aesthetic = _needs_arbitration(best)
    if narrow_aesthetic and margin >= 0.25:
        margin = 0.0

    # L4: margin-gated session — only when top1 and top2 are close
    if margin < 0.25:
        shortlist_lines = "\n".join(
            f"  {i+1}. {c['path']}\n"
            f"     kind={c['kind']}, name={c['name']}, score={s:.1f}\n"
            f"     triggers={c.get('triggers', [])[:6]}\n"
            f"     description={c.get('description', '')[:200]}"
            + (f"\n     audience={c.get('audience')}  tone={c.get('tone')}"
               if c.get('audience') or c.get('tone') else "")
            for i, (s, c) in enumerate(scored[:6]))
        select_prompt = (
            f"You are judging which OpenDesign skill to use for the change "
            f"'{change}'.\n\n"
            f"Change query tokens: {sorted(change_kw.get('query_tokens', set()))[:20]}\n"
            f"Surface hint: {change_kw.get('surface_hint')}\n\n"
            f"Top {min(6, len(shortlist))} candidates (margin {margin:.2f} — "
            f"too close to decide deterministically):\n"
            f"{shortlist_lines}\n\n"
            f"Pick exactly one SKILL.md path from the list above. "
            f"Reply with the full path on the first line, then one line "
            f"explaining why you chose it. Nothing else.")
        out, _rc = run_plane_session(change, "design-select", select_prompt,
                                     repo, task_dir, mode, 90)
        frames = out.get("frames", [])
        if out.get("timed_out") or not out.get("round_complete") \
                or out.get("interrupted"):
            chosen = _first_unflagged(scored, best)
            if chosen is not best:
                reason = (f"degraded — the 90s arbiter session did not complete; "
                          f"top-scored candidate {best['name']} needs arbitration "
                          f"(audience/tone/standalone-scope declared) and was "
                          f"skipped; using next candidate {chosen['name']} instead")
            else:
                reason = (f"degraded — the 90s arbiter session did not complete; "
                          f"using the top-scored candidate (score {best_score:.1f})")
            degraded = True
            method = "degraded"
        else:
            last_msg = ""
            for line in reversed(frames):
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") == "assistant" and obj.get("message"):
                    msg = obj["message"]
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) \
                                        and block.get("type") == "text":
                                    last_msg = block.get("text", "")
                                    break
                    if last_msg:
                        break
            for cand in shortlist:
                if cand["path"] in last_msg:
                    chosen = cand
                    lines = last_msg.strip().splitlines()
                    reason = lines[1].strip() if len(lines) > 1 else \
                        f"selected by 90s arbiter session"
                    method = "judged"
                    break
            if method == "deterministic":
                chosen = _first_unflagged(scored, best)
                if chosen is not best:
                    reason = (f"degraded — arbiter session replied but named no "
                              f"shortlist path; top-scored candidate "
                              f"{best['name']} needs arbitration "
                              f"(audience/tone/standalone-scope declared) and "
                              f"was skipped; using next candidate "
                              f"{chosen['name']} instead")
                else:
                    reason = (f"degraded — arbiter session replied but named no "
                              f"shortlist path; using top-scored "
                              f"(score {best_score:.1f})")
                degraded = True
                method = "degraded"

    # L3: design system + craft
    design_system = None
    if chosen.get("design_system") and chosen["design_system"].get("requires"):
        all_candidates = _scan_design_candidates(root)
        systems = [c for c in all_candidates if c["kind"] == "system"]
        index = _build_design_index(root)
        design_system = _select_design_system(systems, change_kw, index["idf"])
    craft_requires = []
    if chosen.get("craft") and chosen["craft"].get("requires"):
        craft_requires = chosen["craft"]["requires"]

    skill_sha = chosen.get("sha256")
    if not skill_sha:
        try:
            skill_sha = hashlib.sha256(
                Path(chosen["path"]).read_bytes()).hexdigest()
        except OSError:
            pass

    sl_out = [{"path": c["path"], "name": c["name"], "kind": c["kind"],
               "score": round(s, 1)} for s, c in scored[:12]]
    selection = {
        "chosen": chosen["path"],
        "skill_sha256": skill_sha,
        "skill_name": chosen["name"],
        "skill_kind": chosen["kind"],
        "method": method,
        "margin": round(margin, 3),
        "eligible": change_kw.get("eligible", 0),
        "filtered_from": change_kw.get("filtered_from", 428),
        "reason": reason,
        "shortlist": sl_out,
        "design_system": design_system,
        "craft_requires": craft_requires,
        "surface_hint": change_kw.get("surface_hint"),
        "degraded": degraded,
        "narrow_aesthetic_gate": narrow_aesthetic,
    }
    state_path = task_dir / "state.json"
    state = load_json(state_path, {})
    state["design_selection"] = selection
    save_json(state_path, state)
    return emit({"change": change, "repo": str(repo),
                 "applicable": True,
                 "phase": "D0_SELECT",
                 "selection": selection}, 0)


def cmd_design_specify(change: str, repo: Path,
                       task_dir: Path | None,
                       mode: str = "code.normal",
                       timeout: int = 600) -> int:
    """D1 SPECIFY — the v2 design architecture's second phase.  The
    ui-designer reads the selected SKILL.md full text (chosen in D0) and
    produces concrete design artifacts in the repo's design/ directory:

      design/tokens.css      — CSS custom properties (colors, spacing,
                               typography)
      design/tokens.json      — machine-readable token values
      design/components.md    — component specs with props/states
      design/pages.md         — page-level layout specs
      design/assets.md        — asset requirements

    These are product files — they count toward landed_files/landed_bytes
    and the merge gate sees them (S1 "merge gate can't see design"
    structurally disappears).  The SKILL.md sha256 is recorded in the
    design record for D3's skill_sha_match check."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    # D1 requires a D0 selection
    state = load_json(task_dir / "state.json", {})
    selection = state.get("design_selection")
    if not selection or not selection.get("chosen"):
        return emit({"change": change, "repo": str(repo),
                     "stopped": ("before dispatch — no design_selection in "
                                 "state.json; run design-select (D0) first"),
                     "remedy": ("plan.py design-select --change <id> "
                                "--repo <repo>")}, EXIT_INCONCLUSIVE)
    skill_path = selection["chosen"]
    skill_sha = selection.get("skill_sha256")
    skill_name = selection.get("skill_name", "")
    # build the specify prompt
    specify_prompt = (
        f"You are the UI Designer for the delivery '{change}' in this "
        f"repository.\n\n"
        f"Read this SKILL.md in full before you write anything:\n"
        f"  {skill_path}\n\n"
        f"Then produce a concrete design specification as five files in "
        f"the repo's design/ directory:\n"
        f"  design/tokens.css     — CSS custom properties for colors, "
        f"spacing, typography (every color, font-size, and spacing value "
        f"the pages will use)\n"
        f"  design/tokens.json    — the same tokens as machine-readable "
        f"JSON (parsable by a build tool)\n"
        f"  design/components.md  — component specs: each component with "
        f"its props, states, and which tokens it uses\n"
        f"  design/pages.md       — page-level layout specs: each page's "
        f"composition from components\n"
        f"  design/assets.md      — asset requirements: icons, images, "
        f"fonts the pages reference\n\n"
        f"Write only inside this repository's design/ directory. "
        f"Real content and real data throughout — lorem ipsum, placeholder "
        f"text and TODO markers are failures.\n\n"
        f"When you are done, report: the SKILL.md path you read, and every "
        f"file you wrote.")
    # dispatch the ui-designer session
    out, frames = run_design_session(change, specify_prompt, repo, task_dir,
                                     mode, timeout)
    if out.get("timed_out"):
        return emit({**out, "phase": "D1_SPECIFY",
                     "stopped": "the specify session exceeded its "
                                "timeout"}, EXIT_INCONCLUSIVE)
    if not out.get("round_complete") or out.get("interrupted"):
        return emit({**out, "phase": "D1_SPECIFY",
                     "stopped": "the specify session ended without a "
                                "complete round"}, EXIT_INCONCLUSIVE)
    # check the five design artifacts exist
    design_dir = repo / "design"
    expected = ["tokens.css", "tokens.json", "components.md",
                "pages.md", "assets.md"]
    artifacts = {}
    for name in expected:
        p = design_dir / name
        artifacts[name] = {"exists": p.is_file(),
                           "size": p.stat().st_size if p.is_file() else 0}
    all_written = all(a["exists"] and a["size"] > 0
                      for a in artifacts.values())
    # record the design spec in state.json
    state = load_json(task_dir / "state.json", {})
    state["design_spec"] = {
        "skill_path": skill_path,
        "skill_sha256": skill_sha,
        "skill_name": skill_name,
        "artifacts": artifacts,
        "all_written": all_written,
        "session": out.get("session_name"),
        "ts": now_iso(),
    }
    save_json(task_dir / "state.json", state)
    out["phase"] = "D1_SPECIFY"
    out["design_artifacts"] = artifacts
    out["all_written"] = all_written
    out["note"] = ("design artifacts are product files in design/ — they "
                   "count toward landed_files/landed_bytes and the merge "
                   "gate sees them")
    return emit(out, 0 if all_written else EXIT_INCONCLUSIVE)


def cmd_design_verify(change: str, repo: Path,
                      task_dir: Path | None) -> int:
    """D3 VERIFY — the v2 design architecture's fourth phase (D2 BUILD is
    the main session's job, not plan.py's).  Six mechanical checks
    against the filesystem (NOT frames):

      tokens_used          — all color/font-size/spacing values in HTML/CSS
                             pages come from design/tokens.css
      skill_sha_match      — the SKILL.md sha256 in the design record
                             equals the one in design_selection
      components_conform   — components used in pages match specs in
                             components.md
      no_placeholder       — no lorem/TODO/FIXME/placeholder text in
                             delivered pages
      design_artifacts_exist — all 5 design files exist and are non-empty
      tokens_json_valid    — tokens.json parses as valid JSON

    Returns a design_state: design_unspecified (no spec) |
    design_nonconforming (spec exists, checks fail) |
    design_verified (all pass)."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    state = load_json(task_dir / "state.json", {})
    selection = state.get("design_selection")
    design_spec = state.get("design_spec")
    design_dir = repo / "design"
    # if no spec was ever produced, the state is design_unspecified
    if not design_spec and not (design_dir / "tokens.css").is_file():
        return emit({"change": change, "repo": str(repo),
                     "phase": "D3_VERIFY",
                     "design_state": "design_unspecified",
                     "why": ("no design spec exists — D1 SPECIFY was never "
                             "run or produced no artifacts"),
                     "checks": {}}, 0)
    checks = {}
    # 1. design_artifacts_exist — all 5 design files exist and non-empty
    expected = ["tokens.css", "tokens.json", "components.md",
                "pages.md", "assets.md"]
    missing = []
    for name in expected:
        p = design_dir / name
        if not p.is_file() or p.stat().st_size == 0:
            missing.append(name)
    checks["design_artifacts_exist"] = {
        "pass": not missing,
        "missing": missing,
    }
    # 2. tokens_json_valid — tokens.json parses as valid JSON
    tokens_json_path = design_dir / "tokens.json"
    tokens_data = None
    if tokens_json_path.is_file():
        try:
            tokens_data = json.loads(
                tokens_json_path.read_text(encoding="utf-8"))
            checks["tokens_json_valid"] = {"pass": True}
        except (json.JSONDecodeError, OSError) as exc:
            checks["tokens_json_valid"] = {"pass": False,
                                           "error": str(exc)}
    else:
        checks["tokens_json_valid"] = {"pass": False,
                                       "error": "tokens.json not found"}
    # 3. skill_sha_match — SKILL.md sha256 in record equals design_selection
    expected_sha = (selection or {}).get("skill_sha256")
    actual_sha = (design_spec or {}).get("skill_sha256")
    if expected_sha and actual_sha:
        checks["skill_sha_match"] = {
            "pass": expected_sha == actual_sha,
            "expected": expected_sha[:12],
            "actual": actual_sha[:12],
        }
    elif expected_sha and not actual_sha:
        checks["skill_sha_match"] = {"pass": False,
                                     "error": "no sha in design_spec record"}
    else:
        checks["skill_sha_match"] = {"pass": False,
                                     "error": "no skill_sha256 in "
                                              "design_selection"}
    # 4. tokens_used — colors/font-sizes/spacing in pages come from tokens.css
    #    parse token values from tokens.css (CSS custom properties)
    token_values = set()
    tokens_css_path = design_dir / "tokens.css"
    if tokens_css_path.is_file():
        css_text = tokens_css_path.read_text(encoding="utf-8",
                                             errors="replace")
        for m in re.finditer(r"--[\w-]+\s*:\s*([^;]+);", css_text):
            val = m.group(1).strip()
            # extract hex colors, px sizes, rem sizes
            for unit_match in re.finditer(
                    r"(#[0-9a-fA-F]{3,8}|\d+px|\d+rem|\d+em|\d+%)",
                    val):
                token_values.add(unit_match.group(1))
    # scan HTML/CSS pages for values not in tokens
    rogue_values = []
    if token_values:
        for ext in ("*.html", "*.htm", "*.css"):
            for p in repo.rglob(ext):
                # skip design/ dir itself and .ai-dlc/
                rel = p.relative_to(repo)
                if str(rel).startswith("design/") \
                        or str(rel).startswith(".ai-dlc/") \
                        or str(rel).startswith("openspec/"):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for m in re.finditer(
                        r"(#[0-9a-fA-F]{3,8}|\d+px|\d+rem|\d+em)",
                        text):
                    val = m.group(1)
                    if val not in token_values:
                        rogue_values.append({"file": str(rel),
                                             "value": val})
    checks["tokens_used"] = {
        "pass": not rogue_values,
        "token_count": len(token_values),
        "rogue_count": len(rogue_values),
        "rogue_samples": rogue_values[:10],
    }
    # 5. components_conform — components in pages match specs in components.md
    components_md_path = design_dir / "components.md"
    spec_components = set()
    if components_md_path.is_file():
        cm_text = components_md_path.read_text(encoding="utf-8",
                                               errors="replace")
        # component names are typically ## headings or <Component> tags
        for m in re.finditer(r"^##\s+(.+)$", cm_text, re.MULTILINE):
            spec_components.add(m.group(1).strip().lower())
    # scan pages for component-like tags and check against spec
    unlisted_components = []
    if spec_components:
        for ext in ("*.html", "*.htm"):
            for p in repo.rglob(ext):
                rel = p.relative_to(repo)
                if str(rel).startswith("design/") \
                        or str(rel).startswith(".ai-dlc/") \
                        or str(rel).startswith("openspec/"):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # find custom element tags <X-...> or data-component="..."
                for m in re.finditer(r"<([\w-]+)[\s/>]", text):
                    tag = m.group(1).lower()
                    if "-" in tag and tag not in spec_components:
                        unlisted_components.append({"file": str(rel),
                                                    "tag": tag})
    checks["components_conform"] = {
        "pass": not unlisted_components,
        "spec_count": len(spec_components),
        "unlisted_count": len(unlisted_components),
        "unlisted_samples": unlisted_components[:10],
    }
    # 6. no_placeholder — no lorem/TODO/FIXME/placeholder in delivered pages
    placeholder_hits = []
    placeholder_patterns = re.compile(
        r"\b(lorem\s+ipsum|TODO|FIXME|placeholder|FILL)\b", re.IGNORECASE)
    for ext in ("*.html", "*.htm", "*.css", "*.js", "*.ts"):
        for p in repo.rglob(ext):
            rel = p.relative_to(repo)
            if str(rel).startswith("design/") \
                    or str(rel).startswith(".ai-dlc/") \
                    or str(rel).startswith("openspec/"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in placeholder_patterns.finditer(text):
                placeholder_hits.append({"file": str(rel),
                                         "match": m.group(0)})
    checks["no_placeholder"] = {
        "pass": not placeholder_hits,
        "hit_count": len(placeholder_hits),
        "hits_samples": placeholder_hits[:10],
    }
    # determine design_state
    all_pass = all(c.get("pass", False) for c in checks.values())
    if all_pass:
        design_state = "design_verified"
        exit_code = 0
    else:
        design_state = "design_nonconforming"
        exit_code = EXIT_INCONCLUSIVE
    # record in state.json
    state = load_json(task_dir / "state.json", {})
    state["design_verification"] = {
        "design_state": design_state,
        "checks": {k: v.get("pass", False) for k, v in checks.items()},
        "ts": now_iso(),
    }
    save_json(task_dir / "state.json", state)
    return emit({"change": change, "repo": str(repo),
                 "phase": "D3_VERIFY",
                 "design_state": design_state,
                 "checks": checks}, exit_code)


def _select_design_system(systems: list[dict], change_kw: dict,
                          idf: dict) -> dict | None:
    """L3: select a design system for the winner template.
    Searches systems by name/category/description tokens against the
    change query.  Returns None if no confident match."""
    if not systems:
        return None
    query_tokens = change_kw.get("query_tokens", set())
    if not query_tokens:
        return None
    scored_sys = []
    for sys_c in systems:
        score = 0.0
        for tok in _tokenize_query(sys_c.get("name", "")):
            if tok in query_tokens:
                score += 5.0 * idf.get(tok, 1.0)
        for tok in _tokenize_query(sys_c.get("category", "")):
            if tok in query_tokens:
                score += 3.0 * idf.get(tok, 1.0)
        for tok in _tokenize_query(sys_c.get("description", "")):
            if tok in query_tokens:
                score += 1.0 * idf.get(tok, 1.0)
        if score > 0:
            scored_sys.append((score, sys_c))
    if not scored_sys:
        return None
    scored_sys.sort(key=lambda x: x[0], reverse=True)
    best_s, best_sys = scored_sys[0]
    # Require margin > 0.1 to avoid noise
    if len(scored_sys) > 1:
        margin = (best_s - scored_sys[1][0]) / max(best_s, 1)
        if margin < 0.1:
            return None
    return {"path": best_sys["path"], "sha256": best_sys.get("sha256"),
            "name": best_sys["name"],
            "category": best_sys.get("category", "")}


def cmd_design_pick(change: str, repo: Path,
                    task_dir: Path | None) -> int:
    """D0 SELECT (deterministic): L1 hard filter → L2 IDF retrieval →
    L3 combination (template × design_system × craft).  No session,
    no model — millisecond frontmatter + IDF scoring."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    root = Path(OPENDESIGN_ROOT)
    # check applicability first — a backend change buys no design
    files, detail = change_surface(repo, task_dir)
    surface = design_surface(files, repo,
                             head=detail.get("ref_kind") == "task_branch"
                             and detail.get("head") or None)
    if not surface.get("applicable"):
        return emit({"change": change, "repo": str(repo),
                     "applicable": False,
                     "why": ("the change's measured product surface "
                             "carries no web or deck file — design-pick "
                             "produces no selection"),
                     **detail, "measured_surface": surface}, 0)

    # L1 + L2 via _design_prefilter
    shortlist, scored, change_kw = _design_prefilter(change, repo, task_dir)
    if not scored:
        return emit({"change": change, "repo": str(repo),
                     "applicable": True,
                     "error": "no eligible candidates after L1 filter",
                     "candidates_considered": 428}, 1)

    best_score, best = scored[0]
    runner_up_score = scored[1][0] if len(scored) > 1 else 0
    margin = (best_score - runner_up_score) / max(best_score, 1)

    # L3: design system selection (only if winner requires one)
    design_system = None
    if best.get("design_system") and best["design_system"].get("requires"):
        all_candidates = _scan_design_candidates(root)
        systems = [c for c in all_candidates if c["kind"] == "system"]
        index = _build_design_index(root)
        design_system = _select_design_system(systems, change_kw, index["idf"])

    # L3: craft requires (transparent passthrough for D3 VERIFY)
    craft_requires = []
    if best.get("craft", {}).get("requires"):
        craft_requires = best["craft"]["requires"]

    # Build shortlist for output
    sl_out = [{"path": c["path"], "name": c["name"], "kind": c["kind"],
               "score": round(s, 1)} for s, c in scored[:12]]

    selection = {
        "chosen": best["path"],
        "skill_sha256": best.get("sha256"),
        "skill_name": best["name"],
        "skill_kind": best["kind"],
        "method": "deterministic",
        "margin": round(margin, 3),
        "eligible": change_kw.get("eligible", 0),
        "filtered_from": change_kw.get("filtered_from", 428),
        "reason": (f"IDF-weighted score {best_score:.1f} vs "
                   f"{runner_up_score:.1f} for runner-up "
                   f"(margin {margin:.2f})"),
        "shortlist": sl_out,
        "design_system": design_system,
        "craft_requires": craft_requires,
        "surface_hint": change_kw.get("surface_hint"),
        "degraded": False,
    }
    # write to state.json
    state_path = task_dir / "state.json"
    state = load_json(state_path, {})
    state["design_selection"] = selection
    save_json(state_path, state)
    return emit({"change": change, "repo": str(repo),
                 "applicable": True,
                 "selection": selection}, 0)


def _opendesign_tree_id(root: Path) -> str:
    """A sha256 over all SKILL.md/manifest.json paths+sizes+mtime_ns
    under the three OpenDesign subtrees. Used to detect index staleness."""
    root = Path(root)
    entries = []
    for subdir in OPENDESIGN_PATHS:
        base = root / subdir
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
                continue
            for fname in ("SKILL.md", "manifest.json"):
                p = d / fname
                if p.is_file():
                    st = p.stat()
                    entries.append((str(p.relative_to(root)),
                                    st.st_size, st.st_mtime_ns))
    entries.sort()
    return hashlib.sha256(
        "\n".join(f"{r}:{s}:{m}" for r, s, m in entries).encode()
    ).hexdigest()


def _build_design_index(root: Path) -> dict:
    """Build the OpenDesign index: candidates + tree_id + IDF table.
    The IDF table maps each token to its document frequency across
    all candidate texts (triggers + name + description)."""
    root = Path(root)
    candidates = _scan_design_candidates(root)
    tree_id = _opendesign_tree_id(root)

    # Build IDF: count document frequency for each token
    df: dict[str, int] = {}
    for c in candidates:
        tokens = set()
        for t in c.get("triggers", []):
            tokens.update(_tokenize_query(t))
        tokens.update(_tokenize_query(c.get("name", "")))
        tokens.update(_tokenize_query(c.get("description", "")))
        for tok in tokens:
            df[tok] = df.get(tok, 0) + 1

    N = len(candidates)
    idf = {tok: math.log(N / (1 + freq)) for tok, freq in df.items()}

    return {
        "tree_id": tree_id,
        "candidate_count": N,
        "candidates": candidates,
        "idf": idf,
        "built_at": now_iso(),
    }


def cmd_design_index(root: Path, action: str) -> int:
    """plan.py design-index build|show — produce or display the
    OpenDesign index (candidates + tree_id + IDF table)."""
    root = Path(root).resolve()
    if action == "build":
        index = _build_design_index(root)
        index_path = Path("/var/lib/aidlc/opendesign-index.json")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(index_path, index)
        return emit({
            "action": "build", "root": str(root),
            "tree_id": index["tree_id"],
            "candidate_count": index["candidate_count"],
            "idf_tokens": len(index["idf"]),
            "index_path": str(index_path),
        }, 0)
    elif action == "show":
        index = _build_design_index(root)
        # Show summary, not full dump
        cands = index["candidates"]
        by_kind = {}
        for c in cands:
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
        return emit({
            "action": "show", "root": str(root),
            "tree_id": index["tree_id"],
            "candidate_count": index["candidate_count"],
            "by_kind": by_kind,
            "idf_tokens": len(index["idf"]),
            "top_idf": sorted(index["idf"].items(),
                              key=lambda x: x[1], reverse=True)[:20],
        }, 0)
    return emit({"error": f"unknown action: {action}"}, 1)


def cmd_design_scope(change: str, repo: Path,
                     task_dir: Path | None) -> int:
    """The measurement on its own: the change's product surface by
    extension class. A report, not a gate — `design` is the command
    that refuses on it (exit 24)."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    files, detail = change_surface(repo, task_dir)
    surface = design_surface(files, repo,
                             head=detail.get("ref_kind") == "task_branch"
                             and detail.get("head") or None)
    return emit({"change": change, "repo": str(repo), **detail,
                 **surface,
                 "note": ("applicability is this measurement — "
                          "`plan.py design` refuses exit 24 when "
                          "applicable is false")}, 0)


def cmd_codegraph_scope(change: str, repo: Path,
                        task_dir: Path | None) -> int:
    """The codegraph applicability measurement on its own: which of the
    change's files already existed at base_sha (there is something
    pre-existing to query a graph about). A report, not a gate —
    mirrors cmd_design_scope's shape but with prior-existence semantics
    instead of extension-class semantics."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    files, detail = change_surface(repo, task_dir)
    surface = codegraph_surface(files, repo, detail.get("base_sha"))
    return emit({"change": change, "repo": str(repo), **detail,
                 **surface,
                 "note": ("applicability is this measurement — "
                          "a file counts only if it already existed at "
                          "base_sha (net-new files have no graph to "
                          "query)")}, 0)


def _registered_subagent_types() -> list[str]:
    """Read the agents/*.md filenames from the pinned Understand-Anything
    tree and return the subagent_type names (filename without .md).  If
    the agents directory is unreadable or empty, return [] — callers
    omit the listing sentence gracefully, never error (PRD INV-12)."""
    agents_dir = (UNDERSTAND_ANYTHING_ROOT
                  / "understand-anything-plugin" / "agents")
    try:
        return sorted(p.stem for p in agents_dir.glob("*.md")
                      if p.is_file())
    except OSError:
        return []


def _subagent_listing_sentence() -> str:
    """Build the sentence naming registered subagents, or '' if none."""
    types = _registered_subagent_types()
    if not types:
        return ""
    names = ", ".join(types)
    return (f"\n\nThe following subagents are already registered with "
            f"jiuwenswarm and can be dispatched directly via the Task "
            f"tool by subagent_type: {names}.")


def _codegraph_build_core(repo: Path, change: str = "",
                          task_dir: Path | None = None,
                          mode: str = "code.normal",
                          timeout: int = 600) -> tuple[int, dict]:
    """The core of cmd_codegraph_build without the emit — returns
    (exit_code, result_dict) so callers (cmd_codegraph_brief) can run
    the build step as a subroutine without a second JSON blob on stdout.

    C2: the build is now a session dispatch, not a subprocess shell-out
    to a binary.  The role reads the pinned understand/SKILL.md and
    follows its multi-agent pipeline to produce .ua/knowledge-graph.json
    in the target repo.  Pin missing → (1, unavailable dict), same shape
    as the old missing-binary path."""
    repo = repo.resolve()
    pin = understand_anything_pin_state()
    if not pin.get("ok"):
        return 1, {"error": "understand-anything pin not available",
                   "pin_state": pin,
                   "hint": ("run scripts/install-understand-anything.sh "
                            "--write-pin to install the skill tree and "
                            "write the pin")}
    # read the entry-point build skill (understand/SKILL.md) in full —
    # this is the graph-build skill that dispatches project-scanner,
    # file-analyzer, architecture-analyzer sub-agents to scan the
    # codebase and write .ua/knowledge-graph.json
    skill_path = (UNDERSTAND_ANYTHING_ROOT
                  / "understand-anything-plugin" / "skills" / "understand"
                  / "SKILL.md")
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        return 1, {"error": "cannot read build skill",
                   "skill": str(skill_path), "exc": str(exc)}
    # Non-interactive discipline preamble (PRD
    # prd-codegraph-build-noninteractive-incremental §02).  This is a
    # jiuwenswarm session dispatch, not a local interactive Claude Code
    # session — there is no human present to answer the three-way
    # question SKILL.md §7 asks on the "existing graph + unchanged
    # commit hash" branch.  Tell the role that up front so it does not
    # block waiting for a reply that will never come, and point it at
    # the on-disk graph that an earlier dispatch against this same repo
    # likely left behind.  Wording aligns with the tool author's own
    # automated variant (hooks/hooks.json: "Do not ask the user for
    # confirmation — just do it.").  No --full/--review flags are
    # synthesized — the skill's own decision table acts on real disk
    # state.
    noninteractive_preamble = (
        "## Run context — read before following the skill below\n\n"
        "This is an **unattended, automated session dispatch** (a "
        "jiuwenswarm session, not a local interactive Claude Code "
        "session).  There is no human present during this run who can "
        "answer a question or pick from a menu — do not ask one and do "
        "not wait for a reply.  Wherever the skill's decision logic "
        "below would normally prompt the user to choose between options "
        "and wait for their answer — specifically its \"existing graph + "
        "unchanged commit hash\" branch, which offers (a) full rebuild, "
        "(b) graph review, or (c) do nothing — do **not** wait: treat it "
        "as if the user chose **(c) do nothing**, i.e. reuse the existing "
        "graph without rebuilding.  (The skill's own \"existing graph + "
        "changed files\" branch is already a non-interactive incremental "
        "update and needs no special handling here; other branches that "
        "already document their own non-interactive fallback, such as the "
        "language-detection confirmation step, are likewise left as-is.)\n\n"
        f"{repo}/.ua/knowledge-graph.json may already exist on disk from "
        "an earlier dispatch against this same repository — this is "
        "expected and reusable, not stale leftover.  Follow the skill's "
        "own freshness/decision logic (which reads "
        ".ua/meta.json's gitCommitHash against the current HEAD) to "
        "decide whether to reuse the existing graph, incrementally update "
        "it, or do a full rebuild — do **not** assume a full rebuild is "
        "always required.  Do not ask the user for confirmation — just "
        "do it.\n\n"
    )
    build_prompt = (
        f"You are the Codegraph build role for this repository.\n\n"
        + noninteractive_preamble
        + f"Follow the skill instructions below in full.  They describe a "
        f"multi-agent pipeline (project-scanner → file-analyzer → "
        f"architecture-analyzer) that scans the codebase and writes "
        f".ua/knowledge-graph.json in the project root.\n\n"
        f"--- SKILL.md ---\n{skill_text}\n--- end SKILL.md ---\n\n"
        f"Project root: {repo}\n"
        f"Write .ua/knowledge-graph.json.  When you are done, report "
        f"the file you wrote and a one-line summary of nodes/edges."
        + _subagent_listing_sentence())
    # reuse run_codegraph_session — do not fork a new dispatch function.
    # A standalone `codegraph build --repo` call carries no --change, so
    # default it to "build" BEFORE computing task_dir (not after) — a
    # blank change name would otherwise produce a task dir named
    # ".ai-dlc/tasks/-planning".
    change = change or "build"
    td = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    out, _frames = run_codegraph_session(change, build_prompt,
                                         repo, td, mode, timeout)
    graph_path = repo / ".ua" / "knowledge-graph.json"
    graph_written = graph_path.is_file() and graph_path.stat().st_size > 0
    out["graph_file"] = str(graph_path)
    out["graph_written"] = graph_written
    return (0 if graph_written else 1, out)


def cmd_codegraph_build(repo: Path) -> int:
    """(Re)build the local code graph for repo via a session dispatch
    against the pinned Understand-Anything skill tree (C2).  The role
    reads understand/SKILL.md and follows its multi-agent pipeline to
    produce .ua/knowledge-graph.json.  If the pin is missing (the common
    case until the skill tree is installed), exit non-zero with a
    structured JSON error — never a traceback, never a silent success."""
    code, result = _codegraph_build_core(repo)
    return emit(result, code)


def cmd_codegraph_brief(change: str, repo: Path,
                        task_dir: Path | None,
                        mode: str = "code.normal",
                        timeout: int = 600) -> int:
    """plan.py codegraph brief — the session-dispatched half of the
    codegraph role.  Mirrors cmd_codegraph_scope's applicability check
    and cmd_design_specify's dispatch-and-check shape, but simpler:
    this produces exactly one file (codegraph/impact-brief.md).

    Flow:
      1. Measure applicability (same codegraph_surface call as
         cmd_codegraph_scope).  Not applicable (all net-new files) →
         no-op, return 0 (PRD §07 reverse gate).
      2. Check the Understand-Anything pin is available (same
         understand_anything_pin_state check as cmd_codegraph_build).
         Not installed → emit a JSON result with
         codegraph_state='unavailable' and return 0 — this must not
         block the task (PRD §07).  This is the expected/normal path
         in environments without the skill tree.
      3. Pin available → run build first (reuse _codegraph_build_core),
         then dispatch run_codegraph_session with a prompt instructing
         the role to follow the understand-diff/SKILL.md methodology
         and write codegraph/impact-brief.md with the PRD §06 template
         sections.
      4. After the session, check the file exists and is non-empty;
         record the outcome in state.json under 'codegraph_brief' and
         append a CODEGRAPH_BRIEF_WRITTEN or CODEGRAPH_BRIEF_INCOMPLETE
         event to events.jsonl."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    # 1. applicability — same measurement as cmd_codegraph_scope
    files, detail = change_surface(repo, task_dir)
    surface = codegraph_surface(files, repo, detail.get("base_sha"))
    if not surface.get("applicable"):
        return emit({"change": change, "repo": str(repo),
                     "applicable": False,
                     "codegraph_state": "not_applicable",
                     "note": ("all target files are net-new — nothing "
                              "pre-existing to query a graph about; "
                              "brief is a no-op (PRD §07 reverse gate)")}, 0)
    # 2. pin availability — same check as cmd_codegraph_build
    pin = understand_anything_pin_state()
    if not pin.get("ok"):
        return emit({"change": change, "repo": str(repo),
                     "applicable": True,
                     "codegraph_state": "unavailable",
                     "pin_state": pin,
                     "note": ("understand-anything skill tree not "
                              "installed — brief skipped, author work "
                              "proceeds regardless (PRD §07: must not "
                              "block the task)")}, 0)
    # 3. run build first, then dispatch the brief session
    build_rc, build_result = _codegraph_build_core(
        repo, change=change, task_dir=task_dir, mode=mode, timeout=timeout)
    if build_rc != 0:
        event(task_dir, event="CODEGRAPH_UNAVAILABLE",
              change=change, repo=str(repo), build_error=build_result)
        return emit({"change": change, "repo": str(repo),
                     "applicable": True,
                     "codegraph_state": "build_failed",
                     "build_result": build_result,
                     "note": ("codegraph build failed — brief skipped, "
                              "author work proceeds regardless "
                              "(PRD §07)")}, 0)
    # read the understand-diff skill — its methodology is the query
    # contract: check .ua/knowledge-graph.json staleness via
    # gitCommitHash, grep for nodes matching changed file paths, follow
    # 1-hop edges (imports/calls/depends_on) to find callers/callees
    diff_skill_path = (UNDERSTAND_ANYTHING_ROOT
                       / "understand-anything-plugin" / "skills"
                       / "understand-diff" / "SKILL.md")
    try:
        diff_skill_text = diff_skill_path.read_text(encoding="utf-8")
    except OSError:
        diff_skill_text = ("(understand-diff/SKILL.md not readable — "
                            "fall back to generic graph query)")
    pre_existing = surface.get("pre_existing_files", [])
    files_block = "\n".join(f"  {f}" for f in pre_existing)
    brief_prompt = (
        f"You are the Codegraph analyst for the delivery '{change}' in "
        f"this repository.\n\n"
        f"The pre-existing files in this change's scope (files that "
        f"already existed before this change — these have graph data):\n"
        f"{files_block}\n\n"
        f"Follow the methodology in the understand-diff skill below.  "
        f"Its approach: read .ua/knowledge-graph.json, check staleness "
        f"via the graph's gitCommitHash vs current HEAD, grep for nodes "
        f"whose filePath matches each changed file, then follow 1-hop "
        f"edges (imports, calls, depends_on) to find upstream callers "
        f"and downstream dependencies.\n\n"
        f"--- understand-diff/SKILL.md ---\n{diff_skill_text}\n"
        f"--- end understand-diff/SKILL.md ---\n\n"
        f"Write exactly one file: codegraph/impact-brief.md in the repo "
        f"root, with these sections (PRD §06 data contract):\n\n"
        f"  # Codegraph impact brief — {change}\n\n"
        f"  ## Scope queried\n"
        f"  <the pre-existing file list above>\n\n"
        f"  ## Callers\n"
        f"  <who calls the symbols in the changed files, grouped by "
        f"file>\n\n"
        f"  ## Callees / dependencies\n"
        f"  <what the changed code depends on>\n\n"
        f"  ## Cross-module coupling flagged\n"
        f"  <hidden coupling worth the author's attention, or "
        f"'none found' if none>\n\n"
        f"Write only codegraph/impact-brief.md.  When you are done, "
        f"report the file you wrote."
        + _subagent_listing_sentence())
    out, frames = run_codegraph_session(change, brief_prompt, repo,
                                        task_dir, mode, timeout)
    # 4. check the file exists and is non-empty
    brief_path = repo / "codegraph" / "impact-brief.md"
    brief_written = brief_path.is_file() and brief_path.stat().st_size > 0
    state = load_json(task_dir / "state.json", {})
    state["codegraph_brief"] = {
        "session": out.get("session_name"),
        "ts": now_iso(),
        "file": str(brief_path),
        "written": brief_written,
        "applicable": True,
        "pre_existing_files": pre_existing,
    }
    save_json(task_dir / "state.json", state)
    if brief_written:
        event(task_dir, event="CODEGRAPH_BRIEF_WRITTEN",
              change=change, repo=str(repo),
              session=out.get("session_name"),
              file=str(brief_path))
    else:
        event(task_dir, event="CODEGRAPH_BRIEF_INCOMPLETE",
              change=change, repo=str(repo),
              session=out.get("session_name"),
              reason="session ran but codegraph/impact-brief.md not "
                     "found or empty")
    out["phase"] = "CODEGRAPH_BRIEF"
    out["codegraph_state"] = "brief_written" if brief_written \
        else "brief_incomplete"
    out["brief_file"] = str(brief_path)
    out["brief_written"] = brief_written
    return emit(out, 0 if brief_written else EXIT_INCONCLUSIVE)


def detect_reasoning_runaway(frames: list) -> dict | None:
    """N7 (C1): detect reasoning runaway — line-level dedup ratio +
    cumulative chars dual threshold. The client-x round had 302,814 chars
    at 96% line duplication in a single reasoning block. The existing
    repeat_window_chars=1024 guard can't see this (the window is 0.3%
    of the block, and the repeats are scattered, not adjacent).

    Post-hoc: after the session, extract reasoning_content from frames,
    compute the line-level dedup ratio, and if it exceeds 80% with
    >50,000 cumulative chars, record reasoning_truncated (Z4). This
    does not truncate in real-time (that needs gateway changes) — it
    detects and records, so the runaway is visible and measurable."""
    RATIO_THRESHOLD = 0.80
    CHARS_THRESHOLD = 50_000
    reasoning_chars = 0
    lines = []
    for line in frames:
        if not isinstance(line, str):
            continue
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        # extract reasoning_content from various frame shapes
        payload = ev.get("payload", ev)
        rc = (payload.get("reasoning_content")
              or payload.get("reasoning")
              or payload.get("delta", {}).get("reasoning_content", ""))
        if isinstance(rc, str) and rc:
            reasoning_chars += len(rc)
            lines.extend(rc.splitlines())
    if reasoning_chars < CHARS_THRESHOLD:
        return None
    if not lines:
        return None
    # line-level dedup ratio
    from collections import Counter
    counts = Counter(lines)
    total = len(lines)
    unique = len(counts)
    dup_ratio = 1.0 - (unique / total) if total else 0.0
    if dup_ratio < RATIO_THRESHOLD:
        return None
    return {"reasoning_truncated": {
        "at_chars": reasoning_chars,
        "dup_ratio": round(dup_ratio, 3),
        "total_lines": total,
        "unique_lines": unique,
        "threshold_ratio": RATIO_THRESHOLD,
        "threshold_chars": CHARS_THRESHOLD,
    }}


def heal_out_of_bounds(frames: list, repo: Path,
                       surface_files: list) -> dict:
    """N1+N3: detect writes outside --repo that look like accidents
    (same basename as a surface file, path形态 is a typo of the repo
    path), delete them, and record what was cleaned. Z2: only clean,
    never relax the judgment — the healed paths travel into the record
    as self_healed, and design_facts filters them from `outside`.

    An accident形态: the written path is outside repo, and its basename
    matches a file in the measured surface, AND the path looks like a
    typo of the repo path (e.g. /tmp$client-x-ai-launch/... vs
    /tmp/client-x-ai-launch/...). A real out-of-bounds write that does not
    match this形态 is not healed (Y5)."""
    repo = Path(repo).resolve()
    surface_basenames = {Path(f).name for f in surface_files}
    written = frame_write_abs(frames, repo)
    healed = []
    unhealed = []
    for w in written:
        p = Path(w)
        try:
            p.relative_to(repo)
            continue  # inside repo — not out-of-bounds
        except ValueError:
            pass
        # /tmp self-check writes are already handled in design_facts
        s = str(p)
        if s.startswith("/tmp/") and not p.is_dir():
            # could be a self-check OR an accident — check basename
            pass
        # is the basename one of our surface files?
        if p.name not in surface_basenames:
            unhealed.append(s)
            continue
        # is it on disk?
        if not p.exists():
            continue
        # accident形态: same basename, outside repo, exists on disk.
        # Check it's not a legitimate file (not in any known repo).
        # The client-x形态: /tmp$client-x-ai-launch/site/features.html
        # — the $ breaks the path, making it a sibling of /tmp/ not
        # inside it. Delete and record.
        try:
            if p.is_file():
                p.unlink()
                healed.append(s)
            elif p.is_dir():
                shutil.rmtree(p)
                healed.append(s)
        except OSError:
            unhealed.append(s)
    return {"healed": healed, "unhealed": unhealed}


def _dispatch_shards(change: str, repo: Path, task_dir: Path,
                     surface: dict, template: str | None,
                     system: str | None, mode: str, timeout: int,
                     shard: int, surface_files: list) -> int:
    """N8: split the surface into N shards, dispatch concurrently using
    ThreadPoolExecutor (the same pool cmd_phase uses). Z5: the template
    and design_system sha are shared across all shards — determined by
    --template/--system args, or by the first shard to complete. Each
    shard writes its own design-<seq>.json record."""
    # split surface files into shard groups (round-robin for balance)
    shards = [[] for _ in range(shard)]
    for i, f in enumerate(surface_files):
        shards[i % shard].append(f)
    task_id = load_json(task_dir / "state.json", {}).get("task_id")
    results = []
    template_sha = None

    def _run_shard(idx: int, files: list) -> dict:
        nonlocal template_sha
        shard_prompt = design_prompt(change, surface, template, system)
        # annotate the prompt with the shard's file subset
        shard_prompt += ("\n\n## Sharded dispatch\nYou are shard %d of %d. "
                         "Process only these files: %s\n"
                         "Do not touch files outside this list."
                         % (idx + 1, shard, ", ".join(files)))
        out, frames = run_design_session(change, shard_prompt, repo,
                                         task_dir, mode, timeout)
        out["shard"] = {"index": idx, "total": shard, "files": files}
        if not out.get("timed_out") and out.get("round_complete"):
            facts = design_facts(frames, repo, task_dir,
                                 Path(OPENDESIGN_ROOT))
            if not facts["failed"] and facts.get("template"):
                try:
                    sha = hashlib.sha256(
                        Path(facts["template"]).read_bytes()).hexdigest()
                    if template_sha is None:
                        template_sha = sha
                    out["template_sha256"] = sha
                except OSError:
                    pass
            # write per-shard record
            if not facts["failed"]:
                rec = {"verb": "design", "change": change, "task": task_id,
                       "record_key": change,
                       "shard": {"index": idx, "total": shard,
                                 "files": files},
                       "template": facts["template"],
                       "template_sha256": template_sha,
                       "files": facts["files"],
                       "session": out.get("session_name"), "ts": now_iso()}
                out["record"] = str(write_record(change, "design", rec))
        return out

    with ThreadPoolExecutor(max_workers=shard) as ex:
        futures = {ex.submit(_run_shard, i, files): i
                   for i, files in enumerate(shards) if files}
        for fut in futures:
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append({"shard": {"index": futures[fut]},
                                "error": str(exc)})

    ok = sum(1 for r in results if r.get("record"))
    out = {"change": change, "repo": str(repo), "shard": shard,
           "shards_dispatched": len(results), "shards_ok": ok,
           "template_sha256": template_sha,
           "results": [{k: v for k, v in r.items()
                        if k in ("shard", "record", "template_sha256",
                                 "timed_out", "error")}
                       for r in results]}
    out["note"] = ("sharded dispatch — each shard writes its own record; "
                   "deliver checks every face file is covered")
    return emit(out, 0 if ok == len(results) else EXIT_INCONCLUSIVE)


def cmd_design(change: str, repo: Path, task_dir: Path | None,
               template: str | None, system: str | None,
               mode: str, timeout: int, shard: int = 1,
               retrofit: bool = False) -> int:
    """The v2 design architecture orchestrator: D0 SELECT → D1 SPECIFY →
    D3 VERIFY (D2 BUILD is the main session's job, not plan.py's).

    Without --retrofit, this runs the four-phase flow:
      D0: cmd_design_select  — pre-filter top 12, 120s session judges
      D1: cmd_design_specify — ui-designer reads SKILL.md, produces design/
      D3: cmd_design_verify  — six mechanical checks against the filesystem

    With --retrofit, the legacy N1 path runs: one fresh session, five
    facts from its frames, a signed record only when all five hold.
    --shard N becomes the retrofit default (concurrent file-per-session
    instead of one long serial session).  Every stop fires before a
    session opens: the skill (25), the pin (26), the measured surface
    (24), the repo's class."""
    repo = repo.resolve()
    task_dir = Path(task_dir).resolve() if task_dir else default_task_dir(repo,
                                                                change)
    # ── v2 four-phase flow (default) ────────────────────────────────
    if not retrofit:
        # D0 SELECT
        rc = cmd_design_select(change, repo, task_dir, mode)
        if rc != 0:
            return rc
        # D1 SPECIFY
        rc = cmd_design_specify(change, repo, task_dir, mode, timeout)
        if rc != 0:
            return rc
        # D3 VERIFY (D2 BUILD is the main session's job)
        rc = cmd_design_verify(change, repo, task_dir)
        return rc
    # ── legacy retrofit path (--retrofit) ───────────────────────────
    # N1 — the design dispatch: one fresh session, five facts from its
    # frames, a signed record only when all five hold.
    skill = design_skill_state()
    if not skill["ok"]:
        return emit({**skill,
                     "stopped": "before dispatch — the client was never "
                                "invoked"},
                    EXIT_DESIGN_SKILL)
    pin = opendesign_pin_state()
    if not pin.get("ok"):
        return emit({**pin,
                     "stopped": "before dispatch — the client was never "
                                "invoked"},
                    pin.get("exit_code", EXIT_DESIGN_PIN))
    files, detail = change_surface(repo, task_dir)
    surface = design_surface(files, repo,
                             head=detail.get("ref_kind") == "task_branch"
                             and detail.get("head") or None)
    # P0-4: refuse design dispatch after the task is archived — design
    # must run before the merge gate, not after.  country-b-tourism-site's
    # 16-minute design session ran at 02:40 but the task archived at
    # 02:08; the work was real but orphaned outside the task lifecycle.
    _records_dir = Path("/var/lib/aidlc/records") / change
    _has_archive = any(_records_dir.glob("archive-*.json")) \
        if _records_dir.exists() else False
    _events_file = task_dir / "events.jsonl"
    _has_close_event = False
    if _events_file.exists():
        for _line in _events_file.read_text(encoding="utf-8").splitlines():
            if '"TASK_CLOSED"' in _line:
                _has_close_event = True
                break
    if _has_archive or _has_close_event:
        return emit({"change": change, "repo": str(repo),
                     "stopped": ("before dispatch — the change is already "
                                 "archived/closed; design must run before "
                                 "the merge gate, not after"),
                     "why": ("an archive record or TASK_CLOSED event "
                             "exists — dispatching design now would "
                             "produce orphaned work outside the task "
                             "lifecycle (the country-b-tourism-site bug)"),
                     "remedy": ("run design before report.py deliver / "
                                "plan.py close, or re-open the change")},
                    EXIT_DESIGN_SURFACE)
    if not surface.get("applicable"):
        return emit({"change": change, "repo": str(repo), **detail,
                     "measured_surface": surface,
                     "stopped": ("before dispatch — the client was never "
                                 "invoked"),
                     "why": ("the change's measured product surface "
                             "carries no web or deck file — a backend "
                             "change buys no beautifying"),
                     "remedy": ("plan.py design-scope --change <id> "
                                "--repo <repo> shows the measurement"),
                     "exit_code": EXIT_DESIGN_SURFACE},
                    EXIT_DESIGN_SURFACE)
    cls = classify_target(repo)
    if not isinstance(cls, dict) or cls.get("class") is None:
        return emit({"rejected": str(repo), "classification": cls,
                     "stopped": ("before dispatch — no prefix is trusted "
                                 "to guess the target's class")},
                    EXIT_INCONCLUSIVE)
    if cls.get("class") != "writable":
        return emit({"rejected": str(repo), "classification": cls,
                     "stopped": "before dispatch",
                     "why": (f"the repository classifies "
                             f"{cls.get('class')} — the design role "
                             "writes the product surface, and a surface "
                             "the plane cannot write is not a surface "
                             "it can beautify")},
                    EXIT_FORBIDDEN_TARGET)
    # A5.1: budget by measurement — timeout scales with the surface byte
    # count.  The old fixed 1800s was enough for a 2KB page and nowhere
    # near enough for a 24KB surface (country-c: 360/960/1800 all timed
    # out).  formula: timeout = max(base, base + k × surface_bytes).
    # k = 0.04 s/byte (40s per KB) — enough for the 433-candidate scan
    # plus a full rewrite at the measured surface size.  The floor is
    # the --timeout argument (default 1800); the formula only raises it.
    surface_files = surface.get("surface_files", [])
    _surface_bytes = 0
    for f in surface_files:
        try:
            _surface_bytes += (repo / f).stat().st_size
        except OSError:
            pass
    _measured_timeout = max(timeout, int(timeout + 0.04 * _surface_bytes))
    timeout = _measured_timeout
    # N8/A4: sharding — if --shard N > 1, split the surface files into N
    # shards and dispatch concurrently (reuses cmd_phase's pool). Z5:
    # the template and design_system are fixed by --template/--system
    # (or the first shard), and all shards share the same sha.
    # A4: retrofit uses --shard (one file per session, all concurrent)
    # instead of one long serial session — 5 files → 5 ~300s sessions,
    # not 1 × 1800s.
    if shard > 1 and len(surface_files) > 1:
        return _dispatch_shards(change, repo, task_dir, surface, template,
                                system, mode, timeout, shard, surface_files)
    prompt = design_prompt(change, surface, template, system)

    # P0-5 + A5.4: design-stats.jsonl must be written for EVERY dispatch
    # outcome — ok, failed, timeout, crashed, target_vanished — not only
    # the success path.  A5.4 adds the J2 fence: a `running` line is
    # written BEFORE the session opens, then rewritten in-place with the
    # final outcome.  A SIGKILL between the pre-write and the final write
    # leaves the `running` line — the 3-sessions-2-stats-lines gap
    # (country-b-tourism-site / country-c) is closed.  The path is
    # env-overridable so unit tests can point it at tmp.
    _stats_path = Path(os.environ.get(
        "AIDLC_DESIGN_STATS",
        "/var/lib/aidlc/design-stats.jsonl"))
    _stats_id = hashlib.sha256(
        f"{change}:{time.time_ns()}".encode()).hexdigest()[:16]

    def _write_stats_running() -> None:
        """J2 fence: write a `running` line before the session opens.
        This line is rewritten in-place by _rewrite_stats_final."""
        try:
            _stats_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_stats_path, "a", encoding="utf-8") as _sf:
                _sf.write(json.dumps({
                    "change": change, "ts": now_iso(),
                    "outcome": "running",
                    "stats_id": _stats_id,
                    "session_name": f"design-{change}-pending",
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _rewrite_stats_final(_outcome: str, **extra) -> None:
        """Rewrite the `running` line (matched by stats_id) with the
        final outcome.  If the line cannot be found (file rotated,
        concurrent rewrite), append a new line — the accounting is
        still correct: one final line, no orphan running line."""
        try:
            _stats_path.parent.mkdir(parents=True, exist_ok=True)
            lines = _stats_path.read_text(
                encoding="utf-8", errors="replace").splitlines()
            found = False
            for i, line in enumerate(lines):
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("stats_id") == _stats_id:
                    lines[i] = json.dumps({
                        "change": change, "ts": now_iso(),
                        "elapsed_seconds": extra.get("elapsed_seconds"),
                        "outcome": _outcome,
                        "stats_id": _stats_id,
                        "session_name": extra.get("session_name"),
                        **{k: v for k, v in extra.items()
                           if k not in ("elapsed_seconds", "session_name")},
                    }, ensure_ascii=False)
                    found = True
                    break
            if found:
                _stats_path.write_text(
                    "\n".join(lines) + "\n", encoding="utf-8")
            else:
                with open(_stats_path, "a", encoding="utf-8") as _sf:
                    _sf.write(json.dumps({
                        "change": change, "ts": now_iso(),
                        "outcome": _outcome,
                        "stats_id": _stats_id,
                        **extra,
                    }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # A5.2: record the repo's device+inode before the session opens.
    # A5.3: after the session, check whether the repo still stands —
    # if the directory was unlinked or the inode changed (a different
    # directory mounted at the same path), the session's writes all
    # landed in a vanished directory (the country-c cwd-deleted bug).
    _repo_dev = None
    _repo_ino = None
    try:
        _st = os.stat(repo)
        _repo_dev, _repo_ino = _st.st_dev, _st.st_ino
    except OSError:
        pass

    def _repo_vanished() -> bool:
        """True if the repo directory was deleted or replaced (different
        inode) while the session was running."""
        try:
            _st = os.stat(repo)
        except OSError:
            return True
        if _repo_dev is None or _repo_ino is None:
            return False
        return _st.st_dev != _repo_dev or _st.st_ino != _repo_ino

    _write_stats_running()
    out, frames = run_design_session(change, prompt, repo, task_dir,
                                     mode, timeout)

    # A5.3: the repo vanished during the session — every write landed
    # in a deleted directory.  Record the fact and stop: no facts
    # check, no record, just the stats line and an honest report.
    if _repo_vanished():
        _rewrite_stats_final("target_vanished",
                             session_name=out.get("session_name"),
                             elapsed_seconds=out.get("elapsed_seconds"),
                             repo=str(repo))
        return emit({**out,
                     "stopped": ("the target repository vanished during "
                                 "the session — its directory was deleted "
                                 "or replaced; all writes landed in a "
                                 "vanished directory"),
                     "repo": str(repo),
                     "outcome": "target_vanished"},
                    EXIT_INCONCLUSIVE)

    if out.get("timed_out"):
        _rewrite_stats_final("timeout",
                             session_name=out.get("session_name"),
                             elapsed_seconds=out.get("elapsed_seconds"))
        return emit({**out, "stopped": "the session exceeded its "
                                       "timeout"}, EXIT_INCONCLUSIVE)
    if not out.get("round_complete") or out.get("interrupted"):
        _rewrite_stats_final("crashed",
                             session_name=out.get("session_name"),
                             elapsed_seconds=out.get("elapsed_seconds"),
                             interrupted=out.get("interrupted"))
        return emit({**out, "stopped": "the session ended without a "
                                       "complete round"},
                    EXIT_INCONCLUSIVE)
    # N1+N3: path guardrail + self-heal. After the session, scan for
    # out-of-bounds writes that look like accidents (same basename as a
    # surface file, outside repo). Delete them and record what was
    # cleaned (Z2). This runs BEFORE the five-facts check (N3), so an
    # accident is healed before it can fail the facts — and the healed
    # paths are filtered from `outside` in design_facts.
    surface_file_list = surface.get("surface_files", [])
    heal = heal_out_of_bounds(frames, repo, surface_file_list)
    if heal["healed"]:
        out["self_healed"] = heal["healed"]
    # N7: detect reasoning runaway (C1) — line-level dedup ratio + chars
    runaway = detect_reasoning_runaway(frames)
    if runaway:
        out.update(runaway)
    facts = design_facts(frames, repo, task_dir,
                         Path(OPENDESIGN_ROOT),
                         healed=heal["healed"])
    out["facts"] = {k: v for k, v in facts.items() if k != "surface_after"}
    out["surface_after"] = facts["surface_after"]
    # A3: B2 deleted — a page's quality and whether it was produced via
    # a specific tool call are two different things.  The product-side
    # facts (boundary, assets, render, placeholder_scan) are what matter;
    # the ceremony of a skill_tool invocation is not.
    # A3: D8 rewritten — instead of checking whether the frames *show* a
    # SKILL.md read (ceremony), check whether the template the frames
    # record has a sha256 that matches the design_selection (product).
    # If design_selection exists and the facts' template sha matches it,
    # the role read the right SKILL.md — proven by the sha, not by a
    # tool-call audit.  If no design_selection exists (retrofit path),
    # D8 falls back to the original check (template stands on disk).
    _selection = load_json(task_dir / "state.json", {}).get(
        "design_selection")
    if isinstance(_selection, dict) and _selection.get("skill"):
        _expected_sha = _selection["skill"].get("sha256")
        _actual_sha = (facts.get("template", {}) or {}).get("sha256")
        if _expected_sha and _actual_sha:
            if _actual_sha != _expected_sha:
                facts["failed"].append(
                    f"the SKILL.md sha256 in the frames "
                    f"({_actual_sha[:12]}) does not match the "
                    f"design_selection ({_expected_sha[:12]}) — the "
                    f"role read a different SKILL.md than design-pick "
                    f"selected (D8)")
        elif not _actual_sha:
            # design_selection exists but no template read landed in
            # the frames — the role did not read the selected SKILL.md
            facts["failed"].append(
                "design_selection exists but no SKILL.md read appears "
                "in the frames — the role did not read the selected "
                "skill (D8)")
    # N6: success rate logging — one line per design round (P0-5: now via
    # the _rewrite_stats_final helper, which rewrites the J2 `running` line
    # in-place — no orphan running line on normal completion)
    _rewrite_stats_final("ok" if not facts["failed"] else "failed",
                         session_name=out.get("session_name"),
                         elapsed_seconds=out.get("elapsed_seconds"),
                         failed_facts=facts["failed"][:5],
                         self_healed=heal["healed"])
    if facts["failed"]:
        return emit({**out,
                     "record": None,
                     "why": ("the five facts did not all hold — no "
                             "record was written, and deliver will "
                             "honestly report design_unverified")},
                    EXIT_INCONCLUSIVE)
    task_id = load_json(task_dir / "state.json", {}).get("task_id")
    record = {"verb": "design", "change": change, "task": task_id,
              "record_key": change,
              "surface": facts["surface_after"].get("classes"),
              "template": facts["template"],
              "design_system": (system if system else
                                (facts["template"]["path"]
                                 if facts["template"]
                                 and "/design-systems/" in
                                 str(facts["template"]["path"])
                                 else None)),
              "files": facts["files"],
              "discarded_candidates": facts.get("discarded_candidates", []),
              "self_healed": heal["healed"],
              "assets": facts["assets"],
              "render": facts["render"],
              "render_self_check_writes": facts.get(
                  "render_self_check_writes", []),
              "placeholders": facts["placeholders"],
              "session": out["session_name"], "ts": now_iso()}
    out["record"] = str(write_record(change, "design", record))
    out["note"] = ("the record is the frames' and the filesystem's — "
                   "the role's own sentence was never read; deliver "
                   "reads this record and nothing else")
    return emit(out, 0)


# ── cli ─────────────────────────────────────────────────────────────

# ── the target's class, stated on its own ───────────────────────────

def cmd_classify(repo: Path) -> int:
    """The classification on its own: read and write probed separately
    through the gateway's own view of the path, the mounts compared
    between its namespace and the caller's, the class the evidence
    decides — and decision_basis naming which evidence — so a caller can
    see what a run would do before it does it."""
    classification = classify_target(repo)
    code = 0 if classification.get("class") is not None \
        else EXIT_INCONCLUSIVE
    return emit({"repo": str(repo), **classification,
                 "note": ("read and write are probed separately through "
                          "the service's own mount namespace, by a probe "
                          "that creates nothing; a mount only that "
                          "namespace sees vetoes the probe — no path "
                          "prefix is trusted to guess the class")},
                code)


# ── G3: intent-scenario suggest — a read-only candidate-route menu ────
#
# Complementary to `next` ("this change should now run X"): `suggest`
# answers "given this free text and repo state, which routes are worth
# considering" — usable before any change id exists. It never executes,
# never writes state, never opens a session (INV-23). Scoring reuses
# _extract_change_keywords' IDF/CJK-bigram tokenizer (_tokenize_query)
# against a fixed candidate table; no second tokenizer is introduced.

_SUGGEST_CANDIDATES = [
    {
        "name": "inline_quick_fix",
        "triggers": ["fix", "typo", "rename", "bug", "patch", "hotfix",
                     "single file", "one file", "mechanical", "quick fix",
                     "小改动", "改一行"],
        "why": ("the text reads as a single-file or mechanical edit — "
                "the inline route avoids the planning plane's overhead"),
        "first_command": ("python3 bin/report.py init --task-dir <td> "
                          "--repo <repo> --route inline --task-id <id> "
                          "--change <change-id>"),
    },
    {
        "name": "planned_full_pipeline",
        "triggers": ["architecture", "refactor", "module", "modules",
                     "multi module", "pipeline", "system", "redesign",
                     "restructure", "梳理架构", "多模块", "重构"],
        "why": ("multiple modules or architecture language — the planning "
                "plane (validate → deliver → close) fits the scope"),
        "first_command": ("python3 bin/plan.py validate --change "
                          "<change-id> --repo <repo>"),
    },
    {
        "name": "prd_spec_only",
        "triggers": ["prd", "spec", "proposal", "design doc", "document",
                     "write up", "plan first", "spec first",
                     "先出", "文档", "先写"],
        "why": ("the text asks for a PRD/spec before implementation — "
                "produce the spec and let a human fill it in before "
                "any code lands"),
        "first_command": ("python3 bin/plan.py scaffold --change "
                          "<change-id> --kind spec --repo <repo>"),
    },
    {
        "name": "design_first",
        "triggers": ["design", "ui", "page", "frontend", "web page",
                     "deck", "slides", "dashboard", "界面", "页面", "前端"],
        "why": ("the surface is web/deck — pick a design system before "
                "writing pages"),
        "first_command": ("python3 bin/plan.py design-pick --change "
                          "<change-id> --repo <repo> --task-dir <td>"),
    },
    {
        "name": "deploy_extra_gate",
        "triggers": ["deploy", "production", "prod", "release", "ship",
                     "上线", "部署", "发布"],
        "why": ("deploy/production language — add an extra review gate "
                "before close"),
        "first_command": ("python3 bin/plan.py review --change "
                          "<change-id> --repo <repo> --task-dir <td>"),
    },
]

_SUGGEST_MAX = 4  # INV-24: at most 4 candidates, never silently raised


def score_candidates(text: str, repo: Path,
                     state: dict | None = None) -> list[dict]:
    """Score the fixed candidate table against free text + repo state,
    reusing _tokenize_query (the IDF/CJK-bigram tokenizer
    _extract_change_keywords uses). Returns a list of
    {name, why, first_command, score} sorted by score desc then
    declaration order, with zero-score candidates dropped and the list
    capped at _SUGGEST_MAX. Pure function: no writes, no dispatch."""
    text_tokens = _tokenize_query(text or "")
    state = state or {}

    # A prior design decision (recorded by design-pick) reshapes the
    # design_first rationale from "consider picking" to "continue".
    has_design_selection = isinstance(state.get("design_selection"), dict) \
        and bool(state["design_selection"].get("skill"))

    scored = []
    for i, cand in enumerate(_SUGGEST_CANDIDATES):
        trig_tokens: set[str] = set()
        for t in cand["triggers"]:
            trig_tokens |= _tokenize_query(t)
        score = len(trig_tokens & text_tokens)

        why = cand["why"]
        if cand["name"] == "design_first" and has_design_selection:
            why = ("a design system is already picked for this change — "
                   "continue from D1 rather than choosing afresh")

        # Light state bonus: a recorded design selection nudges
        # design_first up by one so it competes even on thin text.
        if cand["name"] == "design_first" and has_design_selection:
            score += 1

        scored.append({"name": cand["name"], "why": why,
                       "first_command": cand["first_command"],
                       "score": score, "_order": i})

    ranked = sorted(scored, key=lambda c: (-c["score"], c["_order"]))
    positive = [c for c in ranked if c["score"] > 0]
    for c in positive:
        del c["_order"]
    return positive[:_SUGGEST_MAX]


def cmd_suggest(repo: Path, change: str | None, text: str) -> int:
    """G3: `plan.py suggest --repo <repo> [--change <id>] "<text>"`.
    Read-only query (INV-23): scores the fixed candidate table against
    the free text and the change's existing state (when --change is
    given), prints up to _SUGGEST_MAX ranked candidates as JSON, and
    never executes, writes, or dispatches. An all-zero score returns an
    empty candidate list plus a fallback pointing at `plan.py next`."""
    state = None
    if change:
        td = default_task_dir(repo, change)
        state = load_json(td / "state.json", {})
    candidates = score_candidates(text, repo, state)
    fallback = None
    if not candidates:
        fallback = ("no candidate scored above zero — the text does not "
                    "lean toward any route; follow `plan.py next`'s "
                    "default judgment")
    return emit({"repo": str(repo), "change": change,
                 "candidates": candidates, "fallback": fallback}, 0)



def cmd_stage(change: str, repo: Path) -> int:
    """Stage a copy — the one mechanism reserved for a target the plane
    cannot see at all. A readable target is refused here with the split
    workspace named as the remedy and the size the copy would have cost:
    copying a project that could be read in place is the mistake this
    change exists to stop making."""
    classification = classify_target(repo)
    if classification["class"] is None:
        return emit({"rejected": str(repo), "classification": classification,
                     "why": ("the target's class could not be "
                             "established — the gateway's own view of "
                             "the path could not be probed")},
                    EXIT_INCONCLUSIVE)
    if classification["class"] != "invisible":
        return emit(refuse_copy_of_readable(repo, classification),
                    EXIT_WORKSPACE)
    workspace = workspace_for(change, repo, classification)
    if workspace.get("refused"):
        return emit(workspace, EXIT_WORKSPACE)
    def _record_stage(p):
        p["staging"] = workspace.get("staging")
        p["change"] = change
    update_planning(Path(workspace["task_dir"]), _record_stage)
    return emit({"change": change, "staged": workspace.get("staging"),
                 "workspace": _workspace_record(workspace),
                 "note": ("nothing at the source was readable; the copy "
                          "is a point in time and work done in the "
                          "source afterwards was not seen")}, 0)


def cmd_snapshot(tree: Path, out_file: Path | None) -> int:
    """The tree's manifest — every file hashed, symlinks with their
    targets — so a round can prove afterwards that a project is
    byte-for-byte as it was found. Written to --out, or stdout. The
    caller's own record (.ai-dlc) is outside the comparison on both
    sides: under N6 the task record is anchored to the repo while the
    round itself writes only the plane's tree, so a manifest that
    counted caller state could never come back untouched."""
    manifest = snapshot_manifest(tree, skip=(tree / ".ai-dlc",))
    if out_file is not None:
        save_json(out_file, manifest)
    return emit({"tree": str(tree),
                 "files": len(manifest),
                 "manifest": manifest if out_file is None else None,
                 "manifest_file": str(out_file) if out_file else None,
                 "note": ("the strongest statement of what the round "
                          "found, independent of version control")},
                0)


def cmd_untouched(manifest_file: Path, tree: Path) -> int:
    """Compare a tree against a manifest taken before a round: every
    tracked and untracked path as it was, and no gateway bookkeeping
    directory left behind. Any difference is named; nothing is cleaned
    up. The caller's own record (.ai-dlc) is skipped on both sides —
    the same rule the dispatch's in-round comparison applies, so the
    CLI pair and the judged round never disagree about whose state a
    path under .ai-dlc is."""
    report = untouched_report(load_json(manifest_file, {}), tree,
                              skip=(tree / ".ai-dlc",))
    code = 0 if report["untouched"] else EXIT_BOUNDARY
    return emit({"tree": str(tree), "manifest_file": str(manifest_file),
                 **report,
                 "note": ("byte-for-byte against the pre-round manifest; "
                          "a gateway bookkeeping directory counts as a "
                          "change")}, code)


# ── the return: the round's work goes back deliberately ─────────────

def _bookkeeping_hits(base: Path) -> list[str]:
    """Gateway bookkeeping directories anywhere under the path the
    return would copy — a round's artifact surface is not the gateway's
    bookkeeping, and a return carrying it would put it in the project."""
    hits: list[str] = []
    for name in GATEWAY_BOOKKEEPING:
        for p in base.rglob(name):
            hits.append(str(p))
    return sorted(hits)


# ── the sandbox guard ───────────────────────────────────────────────

def cmd_sandbox(unit_file: str | None, audit_unit: Path | None) -> int:
    """Report what the service unit grants as writable, and refuse a
    draft that would widen it. A writable grant that is a project tree
    rather than the runtime's own area is reported; a draft that adds
    any writable path is refused with the split workspace named as the
    remedy — widening the unit brings the gateway's bookkeeping into
    somebody's tree permanently, needs a service restart that kills any
    round in flight, and with the permission engine off it widens the
    only boundary left on this host."""
    live_unit = unit_file or GATEWAY_UNIT_FILE
    live = unit_state(live_unit)
    tool_area = Path(__file__).resolve().parent.parent
    data_dir = live.get("data_dir")
    grants_report = []
    for w in live.get("writable", []):
        if data_dir is not None and under(Path(w), str(Path(data_dir)
                                                      .resolve())):
            kind = "runtime data — the service's own area"
        elif under(tool_area, w) or under(Path(w), str(tool_area)):
            kind = "the runtime's own tooling area"
        else:
            kind = ("NOT the runtime's own area — a project tree granted "
                    "writable; the split workspace is the remedy if a "
                    "round needs to reach it")
        grants_report.append({"path": w, "kind": kind})
    out = {"unit": live_unit, "writable": grants_report,
           "private_tmp": live.get("private_tmp"),
           "data_dir": data_dir}
    if audit_unit is None:
        suspect = [g for g in grants_report
                   if g["kind"].startswith("NOT the runtime")]
        return emit({**out,
                     "suspect_grants": [g["path"] for g in suspect],
                     "note": ("read-write paths as the unit grants them; "
                              "no path is widened by this report")},
                    0)
    draft = unit_state(str(audit_unit))
    live_set = {Path(w).resolve() for w in live.get("writable", [])}
    added = sorted({str(w) for w in draft.get("writable", [])
                    if Path(w).resolve() not in live_set})
    if added:
        return emit({**out, "audit_unit": str(audit_unit),
                     "draft_writable": draft.get("writable", []),
                     "added_writable": added,
                     "refused": added,
                     "stopped": "the draft is not applied and nothing was "
                                "restarted",
                     "why": ("the draft widens the service unit's "
                             "writable paths, and widening is not the "
                             "remedy: it brings the gateway's bookkeeping "
                             "back into somebody's tree permanently, it "
                             "needs a service restart that kills any "
                             "round in flight, and with the permission "
                             "engine off it widens the only boundary left "
                             "on this host"),
                     "remedy": ("the split workspace: the round's "
                                "working directory inside the writable "
                                "area, the project granted as an "
                                "additional trusted location for "
                                "reading")},
                    EXIT_SANDBOX_WIDENING)
    return emit({**out, "audit_unit": str(audit_unit),
                 "draft_writable": draft.get("writable", []),
                 "added_writable": [],
                 "note": ("the draft grants no writable path the live "
                          "unit does not already grant")}, 0)


# ── scaffold: generate a four-file spec skeleton (W10/S6) ────────────
#
# A new change starts with empty artifacts.  scaffold writes the four
# files the pipeline expects — change.md, proposal.md, design.md (for
# kind=site), tasks.md — each carrying explicit <!-- FILL: … --> markers
# so the design judgment's "no placeholder" fact catches an unfilled
# scaffold before the plane ever runs.

_SCAFFOLD_CHANGE_MD = """\
# Change: <!-- FILL: one-line title for this change -->

## Why
<!-- FILL: the problem or opportunity this change addresses — two to four sentences -->

## What
<!-- FILL: what the change produces — the artifacts and their acceptance criteria -->

## Scope
<!-- FILL: in-scope and out-of-scope boundaries -->
"""

_SCAFFOLD_PROPOSAL_MD = """\
# Proposal: <!-- FILL: one-line title for this change -->

## Background
<!-- FILL: context the decision-maker needs — current state, constraints -->

## Options
<!-- FILL: the options considered, with trade-offs -->

## Recommendation
<!-- FILL: the recommended option and why -->

## Risks
<!-- FILL: risks and mitigations -->
"""

_SCAFFOLD_DESIGN_MD = """\
# Design: <!-- FILL: one-line title for this change -->

## Product surface
<!-- FILL: the pages, flows, or components this change touches -->

## Information architecture
<!-- FILL: the content structure, navigation, and key user paths -->

## Visual direction
<!-- FILL: layout, typography, color, and motion decisions -->

## Components
<!-- FILL: the components to build or modify, with their props and states -->

## Acceptance
<!-- FILL: how the design is verified — review criteria, checkpoints -->
"""

_SCAFFOLD_TASKS_MD = """\
# Tasks: <!-- FILL: one-line title for this change -->

## T1 — <!-- FILL: task name -->
- <!-- FILL: what this task does -->
- <!-- FILL: acceptance criteria for this task -->

## T2 — <!-- FILL: task name -->
- <!-- FILL: what this task does -->
- <!-- FILL: acceptance criteria for this task -->
"""

_SCAFFOLD_KINDS = {
    "site": {
        "design.md": _SCAFFOLD_DESIGN_MD,
    },
}


def cmd_scaffold(change: str, kind: str, repo: Path | None) -> int:
    """Generate a four-file spec skeleton under openspec/changes/<id>/.

    Each file carries explicit <!-- FILL: … --> placeholder markers so
    the design judgment's "no placeholder" fact catches an unfilled
    scaffold before the plane ever runs.  Existing files are never
    overwritten — a re-run on a populated change is a no-op that
    reports what was already there.
    """
    root = repo if repo is not None else Path.cwd()
    change_dir = root / "openspec" / "changes" / change
    if kind not in _SCAFFOLD_KINDS:
        return emit({"error": f"unknown kind '{kind}'",
                     "known_kinds": sorted(_SCAFFOLD_KINDS)}, 1)
    files: dict[str, str] = {
        "change.md": _SCAFFOLD_CHANGE_MD,
        "proposal.md": _SCAFFOLD_PROPOSAL_MD,
        "tasks.md": _SCAFFOLD_TASKS_MD,
    }
    files.update(_SCAFFOLD_KINDS[kind])
    change_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []
    for name, content in files.items():
        target = change_dir / name
        if target.exists():
            skipped.append(name)
            continue
        target.write_text(content)
        created.append(name)
    return emit({"change": change, "kind": kind,
                 "dir": str(change_dir.relative_to(root)),
                 "created": created, "skipped": skipped}, 0)


def _exit_constants() -> dict:
    """V1/E2: the EXIT_* constants with their inline comments, derived
    from the module's own globals — not hand-written."""
    out = {}
    for name, val in sorted(globals().items()):
        if name.startswith("EXIT_") and isinstance(val, int):
            out[str(val)] = name
    return out


def describe_contract(ap: argparse.ArgumentParser) -> dict:
    """N3: a machine-readable capability contract derived from the
    argparse structure and EXIT_* constants (V1 — not hand-written)."""
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
    return {"executable": "plan.py",
            "purpose": "the planning dispatch — roles author change "
                       "artifacts, validate/review/design/close",
            "verbs": verbs,
            "exits": _exit_constants()}


def _build_subparsers(sub) -> None:
    p = sub.add_parser("roles")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    for name, help_ in (
            ("validate",
             "N1: dispatch the plane's validator for the change and "
             "write the signed verdict record (the caller never runs "
             "it)"),
            ("graph",
             "N3: dispatch the plane once to produce the change's "
             "signed graph record — artifact list, dependency edges, "
             "each conditional artifact's own inclusion conditions"),
            ("status",
             "dispatch the plane's artifact status for the change and "
             "write the signed status record")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--change", required=True)
        p.add_argument("--repo", required=True, type=Path)
        p.add_argument("--task-dir", default=None, type=Path)
        p.add_argument("--mode", default="code.normal")
        p.add_argument("--timeout", type=int, default=600,
                       help="seconds for the plane session (a tool "
                            "dispatch runs one command, not a round of "
                            "authoring)")
    p = sub.add_parser("prompt")
    p.add_argument("--change", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--package-file", required=True, type=Path)
    p.add_argument("--mode", default="code.normal")
    p = sub.add_parser("dispatch")
    p.add_argument("--change", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--package-file", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--mode", default="code.normal")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--frames-file", default=None, type=Path,
                   help="offline judge mode: judge this frame file and "
                        "exit — no client, no billing")
    p.add_argument("--baseline-file", default=None, type=Path,
                   help="offline judge mode: the pre-dispatch baseline "
                        "paths (a JSON list) the destructive-command scan "
                        "judges against")
    p.add_argument("--split-project", default=None, type=Path,
                   help="offline judge mode: the project a split round "
                        "may only read — frames showing a write inside it "
                        "fail the judge, naming the path")
    p.add_argument("--project-manifest", default=None, type=Path,
                   help="offline judge mode: the pre-round project "
                        "manifest (--split-project) compared "
                        "byte-for-byte after the frames")
    p.add_argument("--accept-partial-view", action="store_true",
                   help="a human accepted the narrower view (sparse or "
                        "partial checkout); the acceptance is recorded "
                        "and the dispatch proceeds")
    p = sub.add_parser("phase")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--package-file", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--mode", default="code.normal")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--concurrency", type=int, default=2,
                   help="roles dispatched at once; 1 runs the same kind "
                        "of run serially (the baseline)")
    p.add_argument("--accept-partial-view", action="store_true",
                   help="a human accepted the narrower view; recorded "
                        "and the phase proceeds")
    p = sub.add_parser("decide")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--design", default=None, choices=["skip"],
                   help="record skipping the design pass (with --why); "
                        "deliver then reports design_declined instead "
                        "of design_unverified")
    p.add_argument("--artifact", default=None,
                   help="the conditional artifact the decision is about "
                        "(e.g. design)")
    p.add_argument("--condition", default=None,
                   help='the instruction\'s own condition that applies '
                        '(verbatim); the role is dispatched')
    p.add_argument("--skip", action="store_true",
                   help="none of the conditions applies; the role is "
                        "never dispatched")
    p.add_argument("--reason", default=None,
                   help="why no condition applies (required with "
                        "--skip)")
    p.add_argument("--decided-by", required=True,
                   help="who decided — stated by the caller, never "
                        "assumed; an agent records itself as an agent")
    p = sub.add_parser("review")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--mode", default="code.normal",
                   help="the client mode; team is refused with the "
                        "three recorded reasons")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--concurrency", type=int, default=2,
                   help="reviewers dispatched at once")
    p.add_argument("--axes", default=None,
                   help='the axes for this round, each with a reason: '
                        '"axis: reason, axis: reason" — chosen from the '
                        'named list in the configuration')
    p.add_argument("--stage", choices=["reviewers", "synthesis",
                                       "revision", "all"],
                   default="all",
                   help="reviewers stops after the findings are "
                        "recorded; revision resumes from them")
    p.add_argument("--accept-partial-view", action="store_true",
                   help="a human accepted the narrower view; recorded "
                        "and the round proceeds")
    p = sub.add_parser("boundary")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path,
                   help="where the baseline is kept (default "
                        "<repo>/.ai-dlc/tasks/<change>-planning)")
    p.add_argument("--frames-file", default=None, type=Path,
                   help="frame file to scan for foreign service stops")
    p = sub.add_parser("accept")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--counts-approved", action="store_true",
                   help="a human approved the requirement/scenario count "
                        "change")
    p = sub.add_parser("initiative",
                       help="phase-chain automation: register, advance, "
                            "or query an initiative manifest")
    isub = p.add_subparsers(dest="action", required=True)
    r = isub.add_parser("register",
                        help="create or extend an initiative manifest "
                             "from a list of phase change ids")
    r.add_argument("--initiative", required=True,
                   help="initiative id (the manifest file name stem)")
    r.add_argument("--repo", required=True, type=Path)
    r.add_argument("--phases", required=True,
                   help="comma-separated change ids in phase order")
    r.add_argument("--title", default=None,
                   help="human-readable title (defaults to the id)")
    r.add_argument("--created-by", default=None,
                   help="who created the initiative")
    a = isub.add_parser("advance",
                        help="mark a closed change delivered and queue "
                             "the next phase's task skeleton")
    a.add_argument("--change", required=True,
                   help="the closed change id to advance from")
    a.add_argument("--repo", required=True, type=Path)
    s = isub.add_parser("status",
                        help="print an initiative's phases and statuses "
                             "as JSON")
    s.add_argument("--initiative", required=True)
    s.add_argument("--repo", required=True, type=Path)
    p = sub.add_parser("close")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--branch", default=None,
                   help="task branch to merge (default task/<change>)")
    p.add_argument("--skip-specs", action="store_true",
                   help="pass --skip-specs to the upstream archive "
                        "(infrastructure or doc-only changes)")
    p.add_argument("--keep-task-branch", action="store_true",
                   help="record the task branch's and worktree's retention "
                        "instead of removing them after the merge")
    p.add_argument("--mode", default="code.normal",
                   help="the gateway profile the archive dispatch runs in")
    p.add_argument("--timeout", type=int, default=600,
                   help="per-command timeout for the archive dispatch")
    p = sub.add_parser("sweep")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--branch", default=None,
                   help="task branch to remove once merged (default "
                        "task/<change>)")
    p.add_argument("--purge-openspec", action="store_true",
                   help="also remove the openspec/ tree (a voided run); "
                        "default retains it for a person to commit")
    p.add_argument("--keep-record", action="store_true",
                   help="retain the .ai-dlc task record with a recorded "
                        "reason instead of removing it")
    p = sub.add_parser("classify",
                       help="the target's class, probed through the "
                            "gateway's own view of the path")
    p.add_argument("--repo", required=True, type=Path)
    p = sub.add_parser("stage",
                       help="stage a copy — only for a target the plane "
                            "cannot see at all")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p = sub.add_parser("snapshot",
                       help="a tree's manifest, every file hashed — the "
                            "before/after proof a round is judged against")
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--out", default=None, type=Path)
    p = sub.add_parser("untouched",
                       help="compare a tree against a pre-round manifest, "
                            "byte-for-byte, bookkeeping included")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--tree", required=True, type=Path)
    p = sub.add_parser("migrate",
                       help="N6: move the repo's openspec tree into the "
                            "plane's home, one time — after this the spec "
                            "surface lives plane-side and the repo loses "
                            "its openspec/ for the working period (R5)")
    p.add_argument("--repo", required=True, type=Path)
    p = sub.add_parser("sandbox",
                       help="report the unit's writable paths; refuse a "
                            "draft that widens them")
    p.add_argument("--unit", default=None,
                   help="unit file to report (default the live gateway "
                        "unit)")
    p.add_argument("--audit-unit", default=None, type=Path,
                   help="a drafted unit file; any writable path it adds "
                        "is refused with the remedy named")
    p = sub.add_parser("design",
                       help="v2 four-phase design flow: D0 SELECT → D1 "
                            "SPECIFY → D3 VERIFY (D2 BUILD is the main "
                            "session's job). --retrofit runs the legacy "
                            "N1 single-session dispatch")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p.add_argument("--template", default=None,
                   help="name the template/skill to use (else the role "
                        "picks one by frontmatter)")
    p.add_argument("--system", default=None,
                   help="name the design system to pair with it")
    p.add_argument("--mode", default="code.normal")
    p.add_argument("--timeout", type=int, default=1800,
                   help="seconds for the design session (design rounds "
                        "run long — any-directory's read-in-place "
                        "measured 792s)")
    p.add_argument("--shard", type=int, default=1,
                   help="retrofit: split the surface into N shards "
                        "dispatched concurrently (reuses cmd_phase's "
                        "pool). First shard fixes template sha, "
                        "subsequent reuse (Z5)")
    p.add_argument("--retrofit", action="store_true",
                   help="run the legacy N1 single-session dispatch (the "
                        "1800s full-rewrite path) instead of the v2 "
                        "four-phase flow")
    p = sub.add_parser("design-index",
                       help="build or show the OpenDesign index "
                            "(candidates + tree_id + IDF table)")
    p.add_argument("--root", default=str(OPENDESIGN_ROOT), type=Path)
    p.add_argument("action", choices=["build", "show"],
                   help="build writes the index; show prints a summary")
    p = sub.add_parser("design-scope",
                       help="the design applicability measurement on "
                            "its own: the change's product surface by "
                            "extension class (web / deck)")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p = sub.add_parser("codegraph-scope",
                       help="the codegraph applicability measurement on "
                            "its own: which of the change's files already "
                            "existed at base_sha (net-new files have no "
                            "graph to query)")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p = sub.add_parser("codegraph",
                       help="local code-graph tool: build (re)index the "
                            "graph, or brief a change's impact surface")
    csub = p.add_subparsers(dest="action", required=True)
    b = csub.add_parser("build",
                        help="(re)build the local code graph for the repo "
                             "via a session dispatch against the pinned "
                             "Understand-Anything skill tree")
    b.add_argument("--repo", required=True, type=Path)
    br = csub.add_parser("brief",
                         help="query the code graph for a change's impact "
                              "surface and produce codegraph/impact-brief.md "
                              "via a session dispatch")
    br.add_argument("--change", required=True)
    br.add_argument("--repo", required=True, type=Path)
    br.add_argument("--task-dir", default=None, type=Path)
    br.add_argument("--mode", default="code.normal")
    br.add_argument("--timeout", type=int, default=600)
    p = sub.add_parser("design-pick",
                       help="A1: pick one OpenDesign skill for the change "
                            "by frontmatter matching — no session, no model, "
                            "millisecond. Writes the selection to "
                            "state.json.design_selection")
    p.add_argument("--change", required=True)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--task-dir", default=None, type=Path)
    p = sub.add_parser("design-pin",
                       help="write (--write) or verify the OpenDesign "
                            "pin beside the tree — the digest contract "
                            "the design dispatch checks")
    p.add_argument("--root", default=str(OPENDESIGN_ROOT), type=Path)
    p.add_argument("--tag", default=None,
                   help="the tag the pin names (with --write)")
    p.add_argument("--write", action="store_true")
    p = sub.add_parser("codegraph-pin",
                       help="write (--write) or verify the Understand-"
                            "Anything pin beside the skill tree — the "
                            "digest contract the codegraph dispatch checks")
    p.add_argument("--root", default=str(UNDERSTAND_ANYTHING_ROOT), type=Path)
    p.add_argument("--tag", default=None,
                   help="the tag the pin names (with --write)")
    p.add_argument("--write", action="store_true")
    p = sub.add_parser("scaffold",
                       help="W10: generate a four-file spec skeleton "
                            "(change.md, proposal.md, design.md, tasks.md) "
                            "for a new change — each with explicit <!-- FILL --> "
                            "placeholders so an unfilled scaffold is caught "
                            "before the plane runs")
    p.add_argument("--change", required=True)
    p.add_argument("--kind", default="site",
                   help="the change kind — determines which design "
                        "template is included (default: site)")
    p.add_argument("--repo", default=None, type=Path,
                   help="the repository root (default: current "
                        "directory)")
    p = sub.add_parser("next",
                       help="ask the system what to do next — a read-only "
                            "query that returns a directly executable "
                            "command (U-B). Delegates to report.cmd_next "
                            "so both executables agree (N2).")
    p.add_argument("--task-dir", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)

    p = sub.add_parser("suggest",
                       help="given free text and the repo state, list up to "
                            "4 candidate automation routes with tradeoffs — "
                            "read-only, never chooses or executes (G3).")
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--change", default=None,
                   help="optional change id; when given, the change's "
                        "state.json reshapes the rationales")
    p.add_argument("text", help="the free-text request to classify")

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
    if args.cmd == "next":
        sys.exit(cmd_next(args.task_dir, args.repo.resolve()))
    if args.cmd == "suggest":
        sys.exit(cmd_suggest(args.repo.resolve(), args.change, args.text))
    if args.cmd == "roles":
        sys.exit(cmd_roles(args.change, args.repo.resolve()))
    if args.cmd in ("validate", "graph", "status"):
        fn = {"validate": cmd_validate, "graph": cmd_graph,
              "status": cmd_status}[args.cmd]
        sys.exit(fn(args.change, args.repo.resolve(), args.task_dir,
                    args.mode, args.timeout))
    if args.cmd == "prompt":
        sys.exit(cmd_prompt(args.change, args.role, args.package_file,
                            args.mode))
    if args.cmd == "dispatch":
        sys.exit(cmd_dispatch(args.change, args.role, args.package_file,
                              args.task_dir, args.mode, args.timeout,
                              args.frames_file,
                              args.accept_partial_view,
                              args.baseline_file,
                              args.split_project,
                              args.project_manifest))
    if args.cmd == "phase":
        sys.exit(cmd_phase(args.change, args.repo.resolve(),
                           args.package_file, args.task_dir, args.mode,
                           args.timeout, args.concurrency,
                           args.accept_partial_view))
    if args.cmd == "decide":
        if args.design:
            if args.artifact or args.condition or args.skip:
                ap.error("--design takes no artifact arguments")
            if not (args.reason or "").strip():
                ap.error("--design skip requires --why")
            sys.exit(cmd_decide(args.change, args.repo.resolve(),
                                args.task_dir, None, None, args.reason,
                                args.decided_by, args.design))
        if args.artifact is None:
            ap.error("decide takes --artifact or --design")
        if args.skip == (args.condition is not None):
            ap.error("decide takes exactly one of --condition or --skip")
        sys.exit(cmd_decide(args.change, args.repo.resolve(),
                            args.task_dir, args.artifact,
                            args.condition, args.reason,
                            args.decided_by))
    if args.cmd == "review":
        sys.exit(cmd_review(args.change, args.repo.resolve(),
                            args.task_dir, args.mode, args.timeout,
                            args.concurrency, args.axes, args.stage,
                            args.accept_partial_view))
    if args.cmd == "boundary":
        sys.exit(cmd_boundary(args.change, args.repo.resolve(),
                              args.task_dir,
                              getattr(args, "frames_file", None)))
    if args.cmd == "accept":
        sys.exit(cmd_accept(args.change, args.repo.resolve(), args.task_dir,
                            args.counts_approved))
    if args.cmd == "initiative":
        if args.action == "register":
            sys.exit(init_register(args.initiative, args.repo.resolve(),
                                   args.phases.split(","),
                                   args.title, args.created_by))
        if args.action == "advance":
            sys.exit(init_advance(args.change, args.repo.resolve()))
        if args.action == "status":
            sys.exit(init_status(args.initiative, args.repo.resolve()))
    if args.cmd == "close":
        sys.exit(cmd_close(args.change, args.repo.resolve(), args.task_dir,
                           args.branch, args.skip_specs,
                           args.keep_task_branch, args.mode, args.timeout))
    if args.cmd == "sweep":
        sys.exit(cmd_sweep(args.change, args.repo.resolve(), args.task_dir,
                           args.purge_openspec, args.keep_record,
                           args.branch))
    if args.cmd == "classify":
        sys.exit(cmd_classify(args.repo.resolve()))
    if args.cmd == "stage":
        sys.exit(cmd_stage(args.change, args.repo.resolve()))
    if args.cmd == "snapshot":
        sys.exit(cmd_snapshot(args.tree.resolve(), args.out))
    if args.cmd == "untouched":
        sys.exit(cmd_untouched(args.manifest, args.tree.resolve()))
    if args.cmd == "migrate":
        sys.exit(cmd_migrate(args.repo.resolve()))
    if args.cmd == "sandbox":
        sys.exit(cmd_sandbox(args.unit, args.audit_unit))
    if args.cmd == "design":
        sys.exit(cmd_design(args.change, args.repo.resolve(),
                            args.task_dir, args.template, args.system,
                            args.mode, args.timeout, args.shard,
                            args.retrofit))
    if args.cmd == "scaffold":
        sys.exit(cmd_scaffold(args.change, args.kind,
                              args.repo.resolve() if args.repo else None))
    if args.cmd == "design-scope":
        sys.exit(cmd_design_scope(args.change, args.repo.resolve(),
                                  args.task_dir))
    if args.cmd == "codegraph-scope":
        sys.exit(cmd_codegraph_scope(args.change, args.repo.resolve(),
                                     args.task_dir))
    if args.cmd == "codegraph":
        if args.action == "build":
            sys.exit(cmd_codegraph_build(args.repo.resolve()))
        if args.action == "brief":
            sys.exit(cmd_codegraph_brief(args.change, args.repo.resolve(),
                                         args.task_dir, args.mode,
                                         args.timeout))
    if args.cmd == "design-pick":
        sys.exit(cmd_design_pick(args.change, args.repo.resolve(),
                                 args.task_dir))
    if args.cmd == "design-pin":
        sys.exit(cmd_design_pin(args.root, args.tag, args.write))
    if args.cmd == "codegraph-pin":
        sys.exit(cmd_codegraph_pin(args.root, args.tag, args.write))
    if args.cmd == "design-index":
        sys.exit(cmd_design_index(args.root, args.action))
    ap.error(f"unhandled {args.cmd}")


if __name__ == "__main__":
    main()
