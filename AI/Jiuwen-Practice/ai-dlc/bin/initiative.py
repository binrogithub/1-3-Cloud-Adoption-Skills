"""bin/initiative — phase-chain automation (plan.py initiative)

An initiative is a machine-readable record of the phases a multi-stage
proposal defines.  register writes the manifest; advance is the hook
that closes one phase and queues the next; status is the read-only view.
See docs/prd-phase-chain-automation.md and the design.md / spec.md under
openspec/changes/phase-chain-automation/.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import cmd_init, load_json, now_iso, save_json  # noqa: E402


# ── paths ───────────────────────────────────────────────────────────

def _initiatives_dir(repo: Path) -> Path:
    return repo / ".ai-dlc" / "initiatives"


def _manifest_path(repo: Path, initiative_id: str) -> Path:
    return _initiatives_dir(repo) / f"{initiative_id}.json"


def _all_manifests(repo: Path) -> list[Path]:
    d = _initiatives_dir(repo)
    return sorted(d.glob("*.json")) if d.is_dir() else []


def _default_task_dir(repo: Path, change_id: str) -> Path:
    return repo / ".ai-dlc" / "tasks" / f"{change_id}-planning"


# ── manifest helpers ────────────────────────────────────────────────

def _find_manifest_for_change(repo: Path,
                              change_id: str) -> tuple[Path, dict] | None:
    """Scan .ai-dlc/initiatives/*.json for a phase whose change_id matches.
    A plain filesystem scan — no daemon, no polling (design.md §The close
    hook)."""
    for mp in _all_manifests(repo):
        m = load_json(mp, {})
        for ph in m.get("phases", []):
            if ph.get("change_id") == change_id:
                return mp, m
    return None


def _collect_existing_change_ids(repo: Path) -> set[str]:
    """Every change_id already registered in any manifest — for the
    single-owner enforcement (INV-5)."""
    ids: set[str] = set()
    for mp in _all_manifests(repo):
        m = load_json(mp, {})
        for ph in m.get("phases", []):
            cid = ph.get("change_id")
            if cid:
                ids.add(cid)
    return ids


# ── repo-level events ───────────────────────────────────────────────

def _repo_event(repo_path: Path, **kw) -> None:
    """Append a human-visible event to the repo's .ai-dlc/events.jsonl in
    the same one-line-JSON format task events use."""
    kw.setdefault("event", kw.pop("kind", "NOTE"))
    kw["ts"] = now_iso()
    el = repo_path / ".ai-dlc" / "events.jsonl"
    el.parent.mkdir(parents=True, exist_ok=True)
    with el.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


# ── register ────────────────────────────────────────────────────────

def cmd_register(initiative_id: str, repo: Path, phases: list[str],
                 title: str | None = None,
                 created_by: str | None = None) -> int:
    mp = _manifest_path(repo, initiative_id)
    existing = load_json(mp, None)

    if existing is not None:
        # Extending an existing initiative — append only the new tail
        # (spec: Extending an existing initiative).  Phases already
        # present are never rewritten.
        current_phases = existing.get("phases", [])
        current_len = len(current_phases)
        new_tail = phases[current_len:] if len(phases) > current_len else []
        if not new_tail:
            print(json.dumps({
                "registered": True, "initiative_id": initiative_id,
                "repo": str(repo), "appended": 0,
                "total_phases": current_len,
                "note": ("no new phases beyond the stored length — "
                         "nothing appended"),
            }, indent=2, ensure_ascii=False))
            return 0
        # Single-owner enforcement: check the new tail against every
        # change id in every manifest (including this one's existing
        # phases) and within the tail itself.
        existing_ids = _collect_existing_change_ids(repo)
        seen_in_tail: set[str] = set()
        for cid in new_tail:
            if cid in seen_in_tail:
                print(json.dumps({
                    "registered": False, "initiative_id": initiative_id,
                    "rejected_change_id": cid,
                    "why": (f"change id {cid!r} appears more than once "
                            "in the new phase list"),
                }, indent=2, ensure_ascii=False))
                return 1
            seen_in_tail.add(cid)
            if cid in existing_ids:
                print(json.dumps({
                    "registered": False, "initiative_id": initiative_id,
                    "rejected_change_id": cid,
                    "why": (f"change id {cid!r} already names a phase "
                            "in another (or the same) initiative "
                            "manifest"),
                }, indent=2, ensure_ascii=False))
                return 1
        for i, cid in enumerate(new_tail):
            current_phases.append({
                "seq": current_len + i + 1,
                "change_id": cid,
                "status": "pending",
            })
        existing["phases"] = current_phases
        save_json(mp, existing)
        print(json.dumps({
            "registered": True, "initiative_id": initiative_id,
            "repo": str(repo), "appended": len(new_tail),
            "total_phases": len(current_phases), "manifest": str(mp),
        }, indent=2, ensure_ascii=False))
        return 0

    # New manifest — validate all phase change ids first.
    seen: set[str] = set()
    for cid in phases:
        if cid in seen:
            print(json.dumps({
                "registered": False, "initiative_id": initiative_id,
                "rejected_change_id": cid,
                "why": (f"change id {cid!r} appears more than once "
                        "in the phase list"),
            }, indent=2, ensure_ascii=False))
            return 1
        seen.add(cid)
    existing_ids = _collect_existing_change_ids(repo)
    for cid in phases:
        if cid in existing_ids:
            print(json.dumps({
                "registered": False, "initiative_id": initiative_id,
                "rejected_change_id": cid,
                "why": (f"change id {cid!r} already names a phase "
                        "in another initiative manifest"),
            }, indent=2, ensure_ascii=False))
            return 1
    manifest = {
        "initiative_id": initiative_id,
        "title": title or initiative_id,
        "created_by": created_by or "unknown",
        "created_at": now_iso(),
        "status": "active",
        "phases": [
            {"seq": i + 1, "change_id": cid, "status": "pending"}
            for i, cid in enumerate(phases)
        ],
    }
    save_json(mp, manifest)
    print(json.dumps({
        "registered": True, "initiative_id": initiative_id,
        "repo": str(repo), "appended": len(phases),
        "total_phases": len(phases), "manifest": str(mp),
    }, indent=2, ensure_ascii=False))
    return 0


# ── advance ────────────────────────────────────────────────────────

def cmd_advance(change_id: str, repo: Path) -> int:
    found = _find_manifest_for_change(repo, change_id)
    if found is None:
        # No manifest owns this change — no-op (INV-6 / standalone task).
        print(json.dumps({
            "advanced": False, "change": change_id, "repo": str(repo),
            "why": ("no initiative manifest owns this change id — "
                    "no-op"),
        }, indent=2, ensure_ascii=False))
        return 0
    mp, manifest = found
    initiative_id = manifest.get("initiative_id", mp.stem)

    # Locate the phase and mark it delivered.
    phase_idx = None
    for i, ph in enumerate(manifest.get("phases", [])):
        if ph.get("change_id") == change_id:
            phase_idx = i
            break
    phase = manifest["phases"][phase_idx]
    phase["status"] = "delivered"
    save_json(mp, manifest)

    # Determine the next phase.
    next_idx = phase_idx + 1
    if next_idx >= len(manifest["phases"]):
        # No next phase — initiative is complete.
        manifest["status"] = "complete"
        save_json(mp, manifest)
        _repo_event(repo, event="INITIATIVE_COMPLETE",
                    initiative_id=initiative_id,
                    change_id=change_id, repo=str(repo))
        print(json.dumps({
            "advanced": True, "initiative_id": initiative_id,
            "change": change_id, "repo": str(repo),
            "delivered": change_id, "initiative_status": "complete",
        }, indent=2, ensure_ascii=False))
        return 0

    next_phase = manifest["phases"][next_idx]
    next_status = next_phase.get("status")

    if next_status == "blocked":
        # Human paused — leave it untouched (spec: The next phase is
        # blocked).
        print(json.dumps({
            "advanced": True, "initiative_id": initiative_id,
            "change": change_id, "repo": str(repo),
            "delivered": change_id,
            "next_phase": next_phase["change_id"],
            "next_status": "blocked",
            "note": "next phase is blocked — left untouched",
        }, indent=2, ensure_ascii=False))
        return 0

    if next_status != "pending":
        # Already queued or delivered — nothing to queue.
        print(json.dumps({
            "advanced": True, "initiative_id": initiative_id,
            "change": change_id, "repo": str(repo),
            "delivered": change_id,
            "next_phase": next_phase["change_id"],
            "next_status": next_status,
            "note": (f"next phase is {next_status!r} — not pending, "
                     "nothing to queue"),
        }, indent=2, ensure_ascii=False))
        return 0

    # Next phase is pending — create the task skeleton through the same
    # initialization path a human uses (INV-3 / spec: clean-slate).
    next_change_id = next_phase["change_id"]
    task_dir = _default_task_dir(repo, next_change_id)
    try:
        # cmd_init prints its own JSON object; a caller of `advance`
        # expects exactly one JSON object on stdout for the command it
        # ran, so cmd_init's is captured rather than interleaved.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_init(task_dir, repo, "planned",
                          next_change_id, next_change_id)
    except Exception as exc:
        # Failure isolation (INV-4): leave next phase pending, surface
        # the failure, the delivered phase stays delivered.
        print(json.dumps({
            "advanced": True, "initiative_id": initiative_id,
            "change": change_id, "repo": str(repo),
            "delivered": change_id,
            "next_phase": next_change_id,
            "next_status": "pending",
            "init_failed": str(exc),
            "note": ("task skeleton creation failed — next phase "
                     "remains pending; the delivered phase is "
                     "unaffected"),
        }, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    if rc != 0:
        print(json.dumps({
            "advanced": True, "initiative_id": initiative_id,
            "change": change_id, "repo": str(repo),
            "delivered": change_id,
            "next_phase": next_change_id,
            "next_status": "pending",
            "init_failed": f"cmd_init returned {rc}",
            "note": ("task skeleton creation failed — next phase "
                     "remains pending; the delivered phase is "
                     "unaffected"),
        }, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    # Success — mark queued and emit the event.
    next_phase["status"] = "queued"
    save_json(mp, manifest)
    _repo_event(repo, event="INITIATIVE_PHASE_QUEUED",
                initiative_id=initiative_id,
                change_id=next_change_id,
                seq=next_phase.get("seq"), repo=str(repo))
    print(json.dumps({
        "advanced": True, "initiative_id": initiative_id,
        "change": change_id, "repo": str(repo),
        "delivered": change_id,
        "next_phase": next_change_id,
        "next_status": "queued", "task_dir": str(task_dir),
    }, indent=2, ensure_ascii=False))
    return 0


# ── status ─────────────────────────────────────────────────────────

def cmd_status(initiative_id: str, repo: Path) -> int:
    mp = _manifest_path(repo, initiative_id)
    manifest = load_json(mp, None)
    if manifest is None:
        print(json.dumps({
            "initiative_id": initiative_id, "repo": str(repo),
            "found": False, "why": "no manifest file at " + str(mp),
        }, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps({
        "initiative_id": manifest.get("initiative_id", initiative_id),
        "title": manifest.get("title"),
        "status": manifest.get("status", "active"),
        "phases": [
            {"seq": ph.get("seq"), "change_id": ph.get("change_id"),
             "status": ph.get("status")}
            for ph in manifest.get("phases", [])
        ],
    }, indent=2, ensure_ascii=False))
    return 0
