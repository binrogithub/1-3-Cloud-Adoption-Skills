"""C-D3 — the six D3 design checks as a shared, dispatch-free module.

Extracted verbatim from plan.py's cmd_design_verify (E1/S1.4) so three
callers share one implementation:

  * plan.py design-verify  — D3 in task context (records skill_sha_match)
  * plan.py design-lint    — D2-time linter over any built tree (no task
                             state; skill_sha_match is omitted)
  * report.py deliver      — the D3-only re-verify path (E1/S1.2) via the
                             design-verify subprocess, never a D1 rewrite

The checks are mechanical and filesystem-only; they never read frames
and never open a session.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# the banned-word list D1 SPECIFY tells the ui-designer about, and D2
# builders meet through design-lint — the rules are stated, never implied
PLACEHOLDER_PATTERN = re.compile(
    r"\b(lorem\s+ipsum|TODO|FIXME|placeholder|FILL)\b", re.IGNORECASE)
BANNED_WORDS_DOC = ("lorem ipsum, TODO, FIXME, placeholder, FILL "
                    "(case-insensitive, as standalone words — this bans "
                    "the CSS/SVG `fill` property and HTML placeholder "
                    "attributes in delivered pages too)")

_SCANNED_PAGE_EXTS = ("*.html", "*.htm")
_SCANNED_STYLE_EXTS = ("*.css",)
_SCANNED_SCRIPT_EXTS = ("*.js", "*.ts")
_EXCLUDED_PREFIXES = ("design/", ".ai-dlc/", "openspec/")

EXPECTED_ARTIFACTS = ["tokens.css", "tokens.json", "components.md",
                      "pages.md", "assets.md"]


def _iter_files(repo: Path, exts):
    for ext in exts:
        for p in repo.rglob(ext):
            rel = p.relative_to(repo)
            if str(rel).startswith(_EXCLUDED_PREFIXES):
                continue
            try:
                yield rel, p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


def _spec_stands(state: dict) -> bool:
    spec = state.get("design_spec")
    return isinstance(spec, dict) and bool(spec.get("all_written"))


def run_checks(repo: Path, task_dir: Path | None = None,
               state: dict | None = None) -> dict:
    """The six checks. `task_dir` (or a preloaded `state`) supplies the
    records skill_sha_match compares; without them that one check is
    omitted rather than failed — lint mode judges the tree, not the
    bookkeeping."""
    repo = Path(repo).resolve()
    state = state if state is not None else {}
    if task_dir is not None and not state:
        try:
            state = json.loads((Path(task_dir) / "state.json")
                               .read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
    design_dir = repo / "design"
    selection = state.get("design_selection")
    design_spec = state.get("design_spec")

    checks: dict = {}
    # 1. design_artifacts_exist
    missing = [name for name in EXPECTED_ARTIFACTS
               if not (design_dir / name).is_file()
               or (design_dir / name).stat().st_size == 0]
    checks["design_artifacts_exist"] = {"pass": not missing,
                                        "missing": missing}
    # 2. tokens_json_valid
    tokens_json_path = design_dir / "tokens.json"
    if tokens_json_path.is_file():
        try:
            json.loads(tokens_json_path.read_text(encoding="utf-8"))
            checks["tokens_json_valid"] = {"pass": True}
        except (json.JSONDecodeError, OSError) as exc:
            checks["tokens_json_valid"] = {"pass": False, "error": str(exc)}
    else:
        checks["tokens_json_valid"] = {"pass": False,
                                       "error": "tokens.json not found"}
    # 3. skill_sha_match — only in task context
    if task_dir is not None or selection or design_spec:
        expected_sha = (selection or {}).get("skill_sha256")
        actual_sha = (design_spec or {}).get("skill_sha256")
        if expected_sha and actual_sha:
            checks["skill_sha_match"] = {
                "pass": expected_sha == actual_sha,
                "expected": expected_sha[:12],
                "actual": actual_sha[:12]}
        elif expected_sha and not actual_sha:
            checks["skill_sha_match"] = {"pass": False,
                                         "error": "no sha in design_spec "
                                                  "record"}
        else:
            checks["skill_sha_match"] = {
                "pass": False,
                "error": "no skill_sha256 in design_selection"}
    # 4. tokens_used
    token_values = set()
    tokens_css_path = design_dir / "tokens.css"
    if tokens_css_path.is_file():
        css_text = tokens_css_path.read_text(encoding="utf-8",
                                             errors="replace")
        for m in re.finditer(r"--[\w-]+\s*:\s*([^;]+);", css_text):
            val = m.group(1).strip()
            for unit_match in re.finditer(
                    r"(#[0-9a-fA-F]{3,8}|\d+px|\d+rem|\d+em|\d+%)", val):
                token_values.add(unit_match.group(1))
    rogue_values = []
    if token_values:
        for rel, text in _iter_files(repo, _SCANNED_PAGE_EXTS
                                     + _SCANNED_STYLE_EXTS):
            for m in re.finditer(
                    r"(#[0-9a-fA-F]{3,8}|\d+px|\d+rem|\d+em)", text):
                if m.group(1) not in token_values:
                    rogue_values.append({"file": str(rel),
                                         "value": m.group(1)})
    checks["tokens_used"] = {
        "pass": not rogue_values,
        "token_count": len(token_values),
        "rogue_count": len(rogue_values),
        "rogue_samples": rogue_values[:10],
    }
    # 5. components_conform
    components_md_path = design_dir / "components.md"
    spec_components = set()
    if components_md_path.is_file():
        cm_text = components_md_path.read_text(encoding="utf-8",
                                               errors="replace")
        for m in re.finditer(r"^##\s+(.+)$", cm_text, re.MULTILINE):
            spec_components.add(m.group(1).strip().lower())
    unlisted_components = []
    if spec_components:
        for rel, text in _iter_files(repo, _SCANNED_PAGE_EXTS):
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
    # 6. no_placeholder
    placeholder_hits = []
    for rel, text in _iter_files(repo, _SCANNED_PAGE_EXTS
                                 + _SCANNED_STYLE_EXTS
                                 + _SCANNED_SCRIPT_EXTS):
        for m in PLACEHOLDER_PATTERN.finditer(text):
            placeholder_hits.append({"file": str(rel), "match": m.group(0)})
    checks["no_placeholder"] = {
        "pass": not placeholder_hits,
        "hit_count": len(placeholder_hits),
        "hits_samples": placeholder_hits[:10],
    }
    return checks


def summarize(checks: dict) -> str:
    """design_verified when every check passes, else design_nonconforming
    (design_unspecified is decided by the caller — a missing spec never
    reaches run_checks)."""
    all_pass = all(c.get("pass", False) for c in checks.values())
    return "design_verified" if all_pass else "design_nonconforming"


def spec_stands(state: dict) -> bool:
    """E1: does a D1 design spec stand in this task state? report.py's
    deliver reads this before any auto-dispatch — a standing spec means
    D3 re-verify, never a D1 rewrite."""
    return _spec_stands(state)
