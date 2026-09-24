#!/usr/bin/env python3
"""Run a deterministic RC/GA evidence gate for one candidate artifact."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any

from css_stability_release_gate import check as check_css_stability

ROOT = Path(__file__).resolve().parents[1]
GATES = ROOT / "config" / "release" / "gates-v1.json"
HEX64 = set("0123456789abcdef")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|api[_-]?token|bearer[_-]?token|rundeck_api_token|password|secret)"
    r"\s*[=:]\s*[\"']?([A-Za-z0-9_./+\-=]{16,})"
)
PLACEHOLDER_WORDS = {"replace", "example", "sample", "changeme", "secret-manager-reference", "your"}
EVIDENCE_REQUIRED = {
    "schema_version", "epic_id", "task_id", "run_id", "attempt", "commit",
    "artifact_sha256", "config_sha256", "case_manifest_sha256",
    "environment_manifest_ref", "started_at", "finished_at", "status",
    "evidence_refs", "reason",
}


def load_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"release input must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"release input must be a JSON object: {path}")
    return value


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= HEX64


def _looks_real(value: str) -> bool:
    lowered = value.lower()
    return not any(word in lowered for word in PLACEHOLDER_WORDS) and "<" not in value and ">" not in value


def scan_credentials(root: Path) -> list[str]:
    """Return file locations containing credential-shaped values, never values."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"credential scan root must be a regular directory: {root}")
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        if any(_looks_real(match.group(1)) for match in SECRET_ASSIGNMENT.finditer(text)):
            hits.append(str(path.relative_to(root)))
    return hits


def scan_artifact(artifact: Path) -> list[str]:
    """Scan a release tarball without extracting it into the workspace."""
    if artifact.is_symlink() or not artifact.is_file():
        return []
    hits: list[str] = []
    try:
        with tarfile.open(artifact, "r:*") as archive:
            for member in sorted(archive.getmembers(), key=lambda item: item.name):
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                data = stream.read()
                if b"\x00" in data:
                    continue
                text = data.decode("utf-8", errors="replace")
                if any(_looks_real(match.group(1)) for match in SECRET_ASSIGNMENT.finditer(text)):
                    hits.append(member.name)
    except (OSError, tarfile.TarError):
        return []
    return hits


def validate_evidence_entry(item: dict[str, Any], artifact_sha: Any,
                           requirements: dict[str, Any] | None = None) -> list[str]:
    """Validate the release evidence envelope without requiring jsonschema."""
    errors = sorted(EVIDENCE_REQUIRED - set(item))
    if errors:
        return [f"missing:{field}" for field in errors]
    if item.get("schema_version") != 1:
        errors.append("schema_version")
    if item.get("artifact_sha256") != artifact_sha or not valid_sha(item.get("artifact_sha256")):
        errors.append("artifact_sha256")
    for field in ("config_sha256", "case_manifest_sha256"):
        if not valid_sha(item.get(field)):
            errors.append(field)
    if not isinstance(item.get("epic_id"), str) or not re.fullmatch(r"REL-[0-9]{2}", item["epic_id"]):
        errors.append("epic_id")
    if not isinstance(item.get("task_id"), str) or not re.fullmatch(r"REL-[0-9]{2}-[0-9]{2}", item["task_id"]):
        errors.append("task_id")
    if not isinstance(item.get("run_id"), str) or not item["run_id"]:
        errors.append("run_id")
    if not isinstance(item.get("attempt"), int) or isinstance(item.get("attempt"), bool) or item["attempt"] < 1:
        errors.append("attempt")
    if not isinstance(item.get("commit"), str) or len(item["commit"]) < 7:
        errors.append("commit")
    if item.get("status") not in {"PASS", "FAIL", "BLOCKED", "N/A"}:
        errors.append("status")
    if not isinstance(item.get("environment_manifest_ref"), str) or not item["environment_manifest_ref"]:
        errors.append("environment_manifest_ref")
    try:
        started = dt.datetime.fromisoformat(str(item["started_at"]).replace("Z", "+00:00"))
        finished = dt.datetime.fromisoformat(str(item["finished_at"]).replace("Z", "+00:00"))
        if finished < started:
            errors.append("time_order")
    except (TypeError, ValueError):
        errors.append("timestamp")
    refs = item.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs")
    else:
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) \
                    or not ref.get("path") or not valid_sha(ref.get("sha256")) \
                    or not isinstance(ref.get("kind"), str) or not ref.get("kind"):
                errors.append(f"evidence_ref:{index}")
    if not isinstance(item.get("reason"), str) or not item["reason"]:
        errors.append("reason")
    requirements = requirements or {}
    if requirements.get("mode") and item.get("mode") != requirements["mode"]:
        errors.append("mode")
    if "min_duration_seconds" in requirements:
        duration = item.get("duration_seconds")
        if not isinstance(duration, (int, float)) or duration < requirements["min_duration_seconds"]:
            errors.append("duration_seconds")
    if requirements.get("event_bearing") and item.get("event_bearing") is not True:
        errors.append("event_bearing")
    if requirements.get("restore_drill") and item.get("restore_drill") is not True:
        errors.append("restore_drill")
    return sorted(set(errors))


def check(stage: str, manifest_path: Path, evidence_root: Path, gates_path: Path = GATES,
          scan_root: Path | None = None,
          css_evidence_root: Path | None = None) -> dict[str, Any]:
    manifest = load_object(manifest_path)
    gates = load_object(gates_path)
    artifact_sha = manifest.get("artifact_sha256")
    reasons: list[str] = []
    if manifest.get("schema_version") != 1:
        reasons.append("manifest_schema_invalid")
    if not valid_sha(artifact_sha):
        reasons.append("artifact_sha256_missing_or_invalid")
    required_key = "rc_required_tasks" if stage == "rc" else "ga_required_tasks"
    required = gates.get(required_key)
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        reasons.append("gate_definition_invalid")
        required = []
    evidence = manifest.get("evidence")
    if not isinstance(evidence, list):
        reasons.append("manifest_evidence_missing")
        evidence = []
    by_task: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("task_id"), str):
            reasons.append("evidence_entry_invalid")
            continue
        by_task.setdefault(item["task_id"], []).append(item)
    accepted: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    invalid: list[str] = []
    invalid_fields: dict[str, list[str]] = {}
    task_requirements = gates.get("task_requirements", {})
    if not isinstance(task_requirements, dict):
        task_requirements = {}
    for task_id in required:
        entries = by_task.get(task_id, [])
        current = [item for item in entries if item.get("artifact_sha256") == artifact_sha
                   and item.get("status") in {"PASS", "VERIFIED", "DONE"}]
        if len(current) == 1:
            fields = validate_evidence_entry(current[0], artifact_sha,
                                              task_requirements.get(task_id))
            if fields:
                invalid.append(task_id)
                invalid_fields[task_id] = fields
            else:
                accepted.append(task_id)
        elif not entries:
            missing.append(task_id)
        elif any(item.get("artifact_sha256") != artifact_sha for item in entries):
            stale.append(task_id)
        else:
            invalid.append(task_id)
    if missing:
        reasons.append("required_evidence_missing")
    if stale:
        reasons.append("evidence_artifact_mismatch")
    if invalid:
        reasons.append("required_evidence_not_passed")
    if not evidence_root.exists() or evidence_root.is_symlink() or not evidence_root.is_dir():
        reasons.append("evidence_root_invalid")
    credential_hits = scan_credentials(scan_root) if scan_root is not None else []
    if scan_root is None and isinstance(manifest.get("artifact"), str):
        credential_hits = scan_artifact(Path(manifest["artifact"]))
    if credential_hits:
        reasons.append("credential_leak_detected")
    css_release = None
    if css_evidence_root is not None:
        css_release = check_css_stability(css_evidence_root)
        if css_release.get("status") != "READY":
            reasons.append("css_stability_not_ready")
    return {
        "schema_version": 1, "stage": stage, "manifest": str(manifest_path),
        "artifact_sha256": artifact_sha, "required_count": len(required),
        "accepted_count": len(accepted), "missing": missing, "stale": stale,
        "invalid": invalid, "invalid_fields": invalid_fields, "credential_hits": credential_hits,
        "reasons": sorted(set(reasons)),
        "status": "GO" if not reasons else "NO_GO",
        "css_stability": css_release,
        "release_decision": {
            "stage": stage, "status": "GO" if not reasons else "NO_GO",
            "artifact_sha256": artifact_sha, "accepted_tasks": accepted,
            "remaining_blockers": sorted(set(reasons)), "tag_created": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check one AutoOps release candidate evidence set.")
    parser.add_argument("--stage", choices=("rc", "ga"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--gates", type=Path, default=GATES)
    parser.add_argument("--scan-root", type=Path,
                        help="Optional extracted artifact directory to scan for credential-shaped values")
    parser.add_argument("--css-evidence-dir", type=Path,
                        help="Optional CSS stability evidence directory required for this release")
    args = parser.parse_args(argv)
    try:
        result = check(args.stage, args.manifest, args.evidence_root, args.gates, args.scan_root,
                       args.css_evidence_dir)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 1, "stage": args.stage, "status": "NO_GO",
                  "reasons": ["release_input_error"], "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
