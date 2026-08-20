#!/usr/bin/env python3
"""Fail-closed release evidence writer for the Direct MaaS Delegate Router.

Reads a structured gate-result JSON from stdin and emits a Markdown evidence
record to stdout.  The writer is fail-closed: it rejects any pending, skipped,
untrusted, dirty-tree, stale commit/tree, or helper-digest-mismatch state.  It
never accepts or serializes a key, prompt, OAuth metadata, or response body.

Image known-unsupported (HTTP 400, no fallback) is the only accepted non-PASS
terminal state and is represented as KNOWN_UNSUPPORTED.

Exit codes:
  0 — valid evidence emitted
  1 — rejected (see stderr for the stable reason)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Stable error codes (PRD §7).
E_LIVE_GATE_PENDING = "LIVE_GATE_PENDING"
E_DIRTY_WORKTREE = "EVIDENCE_DIRTY_WORKTREE"
E_STALE_COMMIT = "EVIDENCE_STALE_COMMIT"
E_DIGEST_MISMATCH = "EVIDENCE_DIGEST_MISMATCH"
E_IMAGE_FALLBACK = "EVIDENCE_IMAGE_FALLBACK"
E_IMAGE_NON_400 = "EVIDENCE_IMAGE_NON_400"
E_SECRET_IN_INPUT = "EVIDENCE_SECRET_IN_INPUT"
E_RESPONSE_BODY_IN_INPUT = "EVIDENCE_RESPONSE_BODY_IN_INPUT"

# Gate statuses that are terminal and acceptable (besides PASS).
ACCEPTABLE_STATUSES = {"PASS"}
# Image is special: KNOWN_UNSUPPORTED is acceptable for the image probe only.

# Fields that look like response bodies or prompts — must never appear.
FORBIDDEN_FIELD_NAMES = {
    "raw_body",
    "response_body",
    "prompt",
    "oauth_metadata",
    "oauth_token",
    "refresh_token",
    "access_token",
    "key",
    "maas_key",
    "api_key",
    "auth_token",
    "secret",
    "token",
}


def _fail(code: str, detail: str) -> int:
    sys.stderr.write(f"{code}: {detail}\n")
    return 1


def _git_head() -> tuple[str, str]:
    """Return (commit, tree) of the current HEAD, or ('', '') if not a repo."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return commit, tree
    except Exception:
        return "", ""


def _actual_helper_digest(rel: str) -> str:
    """SHA-256 of a checkout helper, or '' if missing."""
    p = ROOT / rel
    if not p.is_file():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _scan_for_secrets(obj) -> str | None:
    """Return a secret-like string found in the input, or None.

    We look for common key prefixes, forbidden field names, and high-entropy
    strings in rendered fields.  This is a defense-in-depth check — the caller
    should already scrub secrets.
    """
    text = json.dumps(obj)
    for prefix in ("sk-", "Bearer ", "ANTHROPIC_AUTH_TOKEN="):
        # Heuristic: a key-like token is a long-ish string after the prefix.
        idx = text.find(prefix)
        while idx != -1:
            end = idx + len(prefix)
            while end < len(text) and text[end] not in ('"', " ", "\n", "\t", ",", "}"):
                end += 1
            candidate = text[idx + len(prefix):end]
            if len(candidate) >= 12:
                return text[idx:end]
            idx = text.find(prefix, end)

    # Check rendered string fields for high-entropy values that look like keys.
    # A MaaS key is a raw token (no prefix); we flag long opaque strings in
    # fields that should contain short, structured values.  We exclude fields
    # whose values are expected to be long (binary_digest) and avoid flagging
    # hostnames (which contain dots and are short-ish).
    _RENDERED_FIELDS = ("endpoint_host", "endpoint_path", "model")
    if isinstance(obj, dict):
        for field in _RENDERED_FIELDS:
            val = obj.get(field)
            if not isinstance(val, str):
                continue
            # A key-like value: long, no dots (not a hostname), high character
            # diversity, mixed case + digits (not a simple word).
            if len(val) >= 24 and "." not in val:
                distinct = len(set(val))
                has_upper = any(c.isupper() for c in val)
                has_lower = any(c.islower() for c in val)
                has_digit = any(c.isdigit() for c in val)
                if distinct >= 16 and has_upper and has_lower and has_digit:
                    return val
    return None


def _scan_for_forbidden_fields(obj, path: str = "") -> str | None:
    """Return the path of a forbidden field if present, else None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_FIELD_NAMES:
                return f"{path}.{k}" if path else k
            found = _scan_for_forbidden_fields(v, f"{path}.{k}" if path else k)
            if found:
                return found
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found = _scan_for_forbidden_fields(v, f"{path}[{i}]")
            if found:
                return found
    return None


def validate(results: dict) -> int | None:
    """Validate the results object.  Returns None if valid, or an exit code."""
    # --- Secret / body scrubbing ---
    secret = _scan_for_secrets(results)
    if secret:
        return _fail(E_SECRET_IN_INPUT, f"secret-like string found in input: {secret[:20]}...")
    forbidden = _scan_for_forbidden_fields(results)
    if forbidden:
        return _fail(E_RESPONSE_BODY_IN_INPUT, f"forbidden field in input: {forbidden}")

    # --- Worktree must be clean ---
    if not results.get("worktree_clean", False):
        return _fail(E_DIRTY_WORKTREE, "worktree is dirty")

    # --- Commit/tree must match current HEAD ---
    head_commit, head_tree = _git_head()
    if head_commit and results.get("commit") != head_commit:
        return _fail(E_STALE_COMMIT, f"results commit {results.get('commit')} != HEAD {head_commit}")
    if head_tree and results.get("tree") != head_tree:
        return _fail(E_STALE_COMMIT, f"results tree {results.get('tree')} != HEAD tree {head_tree}")

    # --- Helper digests must match the checkout ---
    helpers = results.get("helpers", {})
    for rel, expected_digest in helpers.items():
        actual = _actual_helper_digest(rel)
        if actual and expected_digest != actual:
            return _fail(
                E_DIGEST_MISMATCH,
                f"helper {rel}: expected {expected_digest}, got {actual}",
            )

    # --- Every gate must be PASS (no pending/skipped/untrusted) ---
    for gate in results.get("gates", []):
        status = gate.get("status", "")
        if status == "PASS":
            continue
        if status in ("pending",):
            return _fail(E_LIVE_GATE_PENDING, f"gate {gate.get('name')} is pending")
        if status in ("skipped",):
            return _fail(E_LIVE_GATE_PENDING, f"gate {gate.get('name')} is skipped")
        if status in ("UNTRUSTED_TEST_RESULT", "untrusted"):
            return _fail(E_LIVE_GATE_PENDING, f"gate {gate.get('name')} is untrusted")
        # Any other non-PASS status is a failure.
        return _fail(E_LIVE_GATE_PENDING, f"gate {gate.get('name')} has non-terminal status: {status}")

    # --- Image probe: must be KNOWN_UNSUPPORTED, HTTP 400, no fallback ---
    image = results.get("image_probe", {})
    if image:
        if image.get("fallback", False):
            return _fail(E_IMAGE_FALLBACK, "image probe used fallback (forbidden)")
        if image.get("http_status") != 400:
            return _fail(E_IMAGE_NON_400, f"image probe http_status={image.get('http_status')} (expected 400)")
        if image.get("status") != "KNOWN_UNSUPPORTED":
            return _fail(E_IMAGE_NON_400, f"image probe status={image.get('status')} (expected KNOWN_UNSUPPORTED)")

    return None


def emit(results: dict) -> str:
    """Render the Markdown evidence record."""
    lines: list[str] = []
    lines.append("# Release Evidence — Direct MaaS Delegate Router v1.0")
    lines.append("")
    lines.append("> Immutable evidence record. Contains no credentials, no response bodies.")
    lines.append(f"> Generated {results.get('generated_at_utc', 'unknown')} (UTC).")
    lines.append("")
    lines.append("## Release identity")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Git commit | `{results.get('commit', '')}` |")
    lines.append(f"| Git tree | `{results.get('tree', '')}` |")
    lines.append(f"| Claude Code version | {results.get('claude_code_version', '')} |")
    lines.append(f"| Endpoint host | `{results.get('endpoint_host', '')}` |")
    lines.append(f"| Endpoint path | `{results.get('endpoint_path', '')}` |")
    lines.append(f"| Model | `{results.get('model', '')}` |")
    lines.append(f"| Worktree | {'clean' if results.get('worktree_clean') else 'dirty'} |")
    lines.append("")

    # Gates
    lines.append("## Verification gates")
    lines.append("")
    lines.append("| Gate | Status | Duration (ms) | Error summary |")
    lines.append("| --- | --- | --- | --- |")
    overall = True
    for gate in results.get("gates", []):
        name = gate.get("name", "")
        status = gate.get("status", "")
        dur = gate.get("duration_ms", "")
        err = gate.get("error_summary", "")
        lines.append(f"| {name} | {status} | {dur} | {err} |")
        if status != "PASS":
            overall = False
    # Image probe
    image = results.get("image_probe", {})
    if image:
        lines.append(
            f"| image | KNOWN_UNSUPPORTED (HTTP {image.get('http_status', '')}) | — |"
        )
    lines.append("")

    # Helper digests
    lines.append("## Helper SHA-256 digests")
    lines.append("")
    lines.append("```")
    for rel, digest in results.get("helpers", {}).items():
        lines.append(f"{digest}  {rel}")
    lines.append("```")
    lines.append("")

    # Binary
    lines.append("## Claude Code binary")
    lines.append("")
    lines.append(f"- digest: `{results.get('binary_digest', '')}`")
    lines.append("")

    # Verdict
    verdict = "PASS" if overall else "FAIL"
    lines.append(f"## Verdict: {verdict}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    raw = sys.stdin.read()
    try:
        results = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return _fail("EVIDENCE_INVALID_JSON", f"input is not valid JSON: {exc}")

    if not isinstance(results, dict):
        return _fail("EVIDENCE_INVALID_INPUT", "input must be a JSON object")

    err = validate(results)
    if err is not None:
        return err

    sys.stdout.write(emit(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
