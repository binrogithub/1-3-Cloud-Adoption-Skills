#!/usr/bin/env python3
"""dream — memory maintenance loop (MiMo Code design + 5.3 merged).

One nightly/on-demand pass over native Claude Code / Mem0 project memory:
  1. dedup near-identical memory entries (task + decisions signature),          [5.4]
  2. validate that every `files_touched[]` path still exists — repair the       [5.4]
     "confidently wrong" stale entries in the SOURCE files by annotating them
     with a parser-safe ` # STALE` marker (or dropping them under --drop-stale),
  3. compress survivors into a deterministic L3 maintenance index,              [5.4]
  4. detect conflicts: a new episode decision that contradicts an existing      [5.3]
     approved L3 rule or a CLAUDE.md rule -> write a conflict-candidate to
     inbox/ and a PROPOSED CLAUDE.md patch (never auto-applied; human gate).

Design-merged from MiMo Code (MIT); harness not forked. Schedulable via
[[loop]]/[[schedule]] or cron; also invokable as the `code-dreaming` skill.
Mem0 ingest of the L3 index is optional and guarded.

Stdlib-only for parsing/validation. Dry-run by default. Never edits CLAUDE.md.
"""

import argparse
import difflib
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.project_scope import (
        memory_matches_project,
        native_memory_relation,
        project_scope,
        resolve_native_memory,
        should_apply_scope_filter,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from project_scope import (
        memory_matches_project,
        native_memory_relation,
        project_scope,
        resolve_native_memory,
        should_apply_scope_filter,
    )

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# --- 5.3 conflict detection (deterministic, surfaces candidates for review) ---
# A decision conflicts with an existing rule when they share the same subject
# AND the existing rule is ABSOLUTE ("only/always/never/…") while the new
# decision explicitly WIDENS or contradicts it ("also/not only/instead/…").
# Precision over recall on purpose: a flagged conflict goes to a human, so we
# would rather miss a fuzzy one than flood inbox/ with false positives.
_ABSOLUTE_MARKERS = ("only", "always", "never", "must not", "cannot", "no longer required")
_WIDEN_MARKERS = ("also", "not only", "in addition", "as well", "instead",
                  "no longer", "additionally", "rather than")
_STOP = {"the", "and", "for", "with", "after", "before", "that", "this", "must",
         "should", "from", "into", "when", "then", "than", "fires", "fired",
         "triggered", "trigger", "triggers", "state", "used", "uses"}


def significant_tokens(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9-]+", s.lower())
            if len(t) > 3 and t not in _STOP}


def _strip_frontmatter(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


def read_existing_rules(semantic_dir: Path, claude_md: Path | None) -> list:
    """Collect existing approved rules to check new decisions against.

    Returns [(source_label, rule_line)] from L3 store/*.md bodies and, if given,
    the bullet lines of a CLAUDE.md."""
    rules: list = []
    store = semantic_dir / "store"
    if store.exists():
        for f in sorted(store.glob("*.md")):
            for line in _strip_frontmatter(f.read_text(encoding="utf-8")).splitlines():
                t = line.strip()
                if t and not t.startswith(("#", "|", "-", "```")) and len(t) > 12:
                    rules.append((f"L3:{f.name}", t))
    if claude_md and claude_md.exists():
        for line in claude_md.read_text(encoding="utf-8").splitlines():
            t = line.strip()
            if re.match(r"^[-*]\s+", t) and len(t) > 12:
                rules.append((f"CLAUDE.md", re.sub(r"^[-*]\s+", "", t)))
    return rules


def detect_conflicts(kept: list, existing_rules: list) -> list:
    """Flag decisions that contradict an absolute existing rule. One per (rule,
    subject) pair. Returns conflict dicts for inbox/ + patch generation."""
    conflicts, seen = [], set()
    for fp, fields, _stale in kept:
        decisions = fields.get("decisions") or []
        if isinstance(decisions, str):
            decisions = [decisions]
        for d in decisions:
            dl, dt = d.lower(), significant_tokens(d)
            if not any(w in dl for w in _WIDEN_MARKERS):
                continue
            for src, rule in existing_rules:
                rl, rt = rule.lower(), significant_tokens(rule)
                if len(dt & rt) < 2:
                    continue
                if not any(a in rl for a in _ABSOLUTE_MARKERS):
                    continue
                key = (src, frozenset(dt & rt))
                if key in seen:
                    continue
                seen.add(key)
                conflicts.append({"episode": fp.name, "decision": d.strip(),
                                  "source": src, "rule": rule.strip(),
                                  "date": fields.get("date", "")})
                break
    return conflicts


def propose_claude_patch(claude_md: Path, conflicts: list) -> str:
    """Unified diff that ANNOTATES each conflicting CLAUDE.md line with a review
    marker. Not applied — written to inbox/ for a human to `git apply`."""
    cc = [c for c in conflicts if c["source"] == "CLAUDE.md"]
    if not claude_md.exists() or not cc:
        return ""
    original = claude_md.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    out = []
    for line in lines:
        bare = re.sub(r"^[-*]\s+", "", line.strip())
        hit = next((c for c in cc if c["rule"] == bare and "DREAM-CONFLICT" not in line), None)
        if hit:
            nl = "\n" if line.endswith("\n") else ""
            body = line[:-1] if nl else line
            out.append(f'{body}  <!-- DREAM-CONFLICT ({hit["date"]}): new evidence in '
                       f'{hit["episode"]} — "{hit["decision"]}". Review & update. -->{nl}')
        else:
            out.append(line)
    if out == lines:
        return ""
    return "".join(difflib.unified_diff(lines, out,
                   fromfile="a/CLAUDE.md", tofile="b/CLAUDE.md"))

# Parser-safe marker appended to a stale files_touched[] entry. It lives INSIDE
# the quoted scalar so the minimal YAML-subset parser (which strips the quotes
# but not trailing `#` comments) round-trips the value cleanly and the schema
# still sees a plain string list item — no new key is introduced.
STALE_MARKER = " # STALE (missing)"
SYMBOL_STALE_MARKER = " # STALE (symbol)"
_SYMBOL_KEYS = ("symbols", "symbols_touched")
_IGNORED_SYMBOL_DIRS = {
    ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", "__pycache__",
    "node_modules", "vendor", "build", "dist", ".venv", "venv",
}
_BINARY_SUFFIXES = {
    ".7z", ".a", ".bin", ".bz2", ".class", ".dll", ".dylib", ".exe", ".gif",
    ".gz", ".ico", ".jar", ".jpeg", ".jpg", ".o", ".pdf", ".png", ".pyc",
    ".so", ".tar", ".tgz", ".webp", ".zip",
}


def _claude_project_key(path: Path) -> str:
    """Return Claude Code's project directory key for an absolute path."""
    return "-" + "-".join(part for part in path.resolve().parts if part != "/")


def resolve_native_memory_dir(start: Path | None = None) -> Path:
    """Resolve the native Claude Code project memory dir for this repo.

    Prefer the deepest existing Claude project memory directory for cwd or one of
    its parents; otherwise return the deterministic cwd mapping.
    """
    return resolve_native_memory(start).memory_dir


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


def derive_markdown_fields(text: str, path: Path) -> dict:
    """Tolerate native/plain Markdown memory files without legacy metadata."""
    title = first_heading(text) or path.stem.replace("-", " ").replace("_", " ")
    decisions: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[-*]\s+", stripped):
            stripped = re.sub(r"^[-*]\s+", "", stripped).strip()
        decisions.append(stripped)
    if not decisions and title:
        decisions.append(title)
    return {"task": title, "decisions": decisions, "files_touched": []}


def parse_frontmatter(text: str) -> dict:
    """Minimal YAML-subset frontmatter parser (scalars + simple `- ` lists)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fields: dict = {}
    current_key = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s*-\s+", line):
            item = re.sub(r"^\s*-\s+", "", line).strip().strip('"')
            if current_key:
                # Promote an empty scalar to a list on first list item.
                if not isinstance(fields.get(current_key), list):
                    fields[current_key] = []
                fields[current_key].append(item)
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if val == "[]":
                fields[key] = []
            elif val == "":
                fields[key] = ""  # may be promoted to a list by following `- ` items
            else:
                fields[key] = val.strip().strip('"')
    return fields


def memory_fields(text: str, path: Path) -> dict:
    fields = parse_frontmatter(text)
    return fields if fields else derive_markdown_fields(text, path)


def episode_signature(fields: dict) -> str:
    """Stable signature for dedup: task + sorted decisions."""
    decisions = fields.get("decisions") or []
    if isinstance(decisions, str):
        decisions = [decisions]
    basis = (str(fields.get("task", "")).strip().lower()
             + "|" + "|".join(sorted(d.strip().lower() for d in decisions)))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def validate_paths(files_touched, repo_root: Path) -> tuple[list, list]:
    """Split files_touched into (existing, stale) relative to repo_root."""
    if not files_touched:                       # None / "" / [] — frontmatter w/o the key
        return [], []
    if isinstance(files_touched, str):
        files_touched = [files_touched]
    existing, stale = [], []
    for rel in files_touched:
        rel = rel.strip()
        if not rel:
            continue
        (existing if (repo_root / rel).exists() else stale).append(rel)
    return existing, stale


def _strip_marker(value: str, marker: str) -> str:
    return value[: -len(marker)] if value.endswith(marker) else value


def normalize_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in value if str(v).strip()]


def explicit_symbols(fields: dict) -> list[str]:
    """Return explicit frontmatter symbols from supported keys."""
    out: list[str] = []
    seen: set[str] = set()
    for key in _SYMBOL_KEYS:
        for sym in normalize_list(fields.get(key)):
            base = _strip_marker(sym, SYMBOL_STALE_MARKER).strip()
            if base and base not in seen:
                seen.add(base)
                out.append(base)
    return out


def heuristic_symbols(text: str) -> list[str]:
    """Extract high-confidence code-span symbols from a Markdown body.

    These are report-only candidates. Explicit frontmatter symbols are the only
    values rewritten by dream because code spans often include commands, paths,
    or package names that are not repo symbols.
    """
    body = _strip_frontmatter(text)
    out: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]{2,})`", body):
        sym = match.group(1)
        if sym in seen:
            continue
        if not re.search(r"[A-Z_]", sym) and "_" not in sym:
            # Lowercase words like `timeout` are too noisy.
            continue
        seen.add(sym)
        out.append(sym)
    return out


def _symbol_search_paths(repo_root: Path):
    for path in repo_root.rglob("*"):
        if any(part in _IGNORED_SYMBOL_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        yield path


def symbol_exists(symbol: str, repo_root: Path) -> bool:
    """Return whether a symbol-like token appears in the repo."""
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--quiet", "--fixed-strings"]
        for ignored in sorted(_IGNORED_SYMBOL_DIRS):
            cmd.extend(["--glob", f"!{ignored}/**"])
        cmd.extend([symbol, str(repo_root)])
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except OSError:
            pass

    needle = symbol.encode("utf-8")
    for path in _symbol_search_paths(repo_root):
        try:
            if needle in path.read_bytes():
                return True
        except OSError:
            continue
    return False


def validate_symbols(symbols, repo_root: Path) -> tuple[list, list]:
    """Split symbols into (existing, stale) relative to repo_root."""
    existing, stale = [], []
    for sym in normalize_list(symbols):
        base = _strip_marker(sym, SYMBOL_STALE_MARKER).strip()
        if not base:
            continue
        (existing if symbol_exists(base, repo_root) else stale).append(base)
    return existing, stale


def _item_value(line: str) -> str:
    """Extract the (unquoted) scalar value of a `  - "..."` frontmatter list item."""
    return re.sub(r"^\s*-\s+", "", line).strip().strip('"')


def rewrite_files_touched(text: str, stale: list, drop: bool) -> tuple[str, bool]:
    """Edit ONLY the files_touched[] block of the frontmatter.

    Stale entries are annotated in place with a trailing ` # STALE (missing)`
    marker (default) or removed entirely (drop=True). Every other key, the body,
    key ordering, indentation and quoting style are left byte-identical.

    Returns (new_text, changed); changed is False when the file is already at the
    target state (idempotent re-run).
    """
    m = FRONTMATTER_RE.match(text)
    if not m or not stale:
        return text, False
    stale_set = {s.strip() for s in stale}

    fm_lines = m.group(1).split("\n")
    out: list = []
    changed = False
    in_block = False  # inside the files_touched: list region

    for line in fm_lines:
        is_list_item = bool(re.match(r"^\s*-\s+", line))
        is_key = (":" in line) and not is_list_item

        if in_block and not is_list_item:
            in_block = False  # a new key (or blank) ends the files_touched block

        if is_key:
            key = line.split(":", 1)[0].strip()
            in_block = (key == "files_touched")
            out.append(line)
            continue

        if in_block and is_list_item:
            value = _item_value(line)
            base = value[: -len(STALE_MARKER)] if value.endswith(STALE_MARKER) else value
            already_marked = value.endswith(STALE_MARKER)
            if base in stale_set:
                if drop:
                    changed = True  # skip the line entirely
                    continue
                if already_marked:
                    out.append(line)  # idempotent: leave as-is
                else:
                    indent = line[: len(line) - len(line.lstrip())]
                    out.append(f'{indent}- "{base}{STALE_MARKER}"')
                    changed = True
                continue
            out.append(line)
            continue

        out.append(line)

    if not changed:
        return text, False

    # If drop emptied the list, collapse `files_touched:` to `files_touched: []`.
    rebuilt: list = []
    i = 0
    while i < len(out):
        line = out[i]
        if re.match(r"^\s*files_touched\s*:\s*$", line):
            # peek: any following list items before the next key/end?
            has_items = (i + 1 < len(out)) and bool(re.match(r"^\s*-\s+", out[i + 1]))
            if not has_items:
                indent = line[: len(line) - len(line.lstrip())]
                rebuilt.append(f"{indent}files_touched: []")
                i += 1
                continue
        rebuilt.append(line)
        i += 1

    new_fm = "\n".join(rebuilt)
    new_text = text[: m.start(1)] + new_fm + text[m.end(1):]
    return new_text, True


def rewrite_stale_symbols(text: str, stale: list) -> tuple[str, bool]:
    """Annotate stale explicit symbol frontmatter entries in place."""
    m = FRONTMATTER_RE.match(text)
    if not m or not stale:
        return text, False
    stale_set = {s.strip() for s in stale}

    fm_lines = m.group(1).split("\n")
    out: list[str] = []
    changed = False
    in_block = False

    for line in fm_lines:
        is_list_item = bool(re.match(r"^\s*-\s+", line))
        is_key = (":" in line) and not is_list_item

        if in_block and not is_list_item:
            in_block = False

        if is_key:
            key = line.split(":", 1)[0].strip()
            in_block = key in _SYMBOL_KEYS
            out.append(line)
            continue

        if in_block and is_list_item:
            value = _item_value(line)
            base = _strip_marker(value, SYMBOL_STALE_MARKER).strip()
            if base in stale_set:
                if value.endswith(SYMBOL_STALE_MARKER):
                    out.append(line)
                else:
                    indent = line[: len(line) - len(line.lstrip())]
                    out.append(f'{indent}- "{base}{SYMBOL_STALE_MARKER}"')
                    changed = True
                continue
        out.append(line)

    if not changed:
        return text, False
    new_fm = "\n".join(out)
    return text[: m.start(1)] + new_fm + text[m.end(1):], True


def memory_health(memory_dir: Path, planned_index: str,
                  planned_entries: int,
                  budget_lines: int, budget_kb: int) -> dict:
    """Measure real memory when present, else planned index only if non-empty."""
    memory_md = memory_dir / "MEMORY.md"
    if memory_md.exists():
        target = memory_md
        text = memory_md.read_text(encoding="utf-8")
    elif (memory_dir / "semantic" / "dream-index.md").exists():
        target = memory_dir / "semantic" / "dream-index.md"
        text = target.read_text(encoding="utf-8")
    elif planned_entries:
        target = memory_dir / "semantic" / "dream-index.md"
        text = planned_index
    else:
        target = memory_dir
        text = ""
    lines = len(text.splitlines())
    size_bytes = len(text.encode("utf-8"))
    limit_bytes = budget_kb * 1024
    status = "OK" if lines <= budget_lines and size_bytes <= limit_bytes else "OVER"
    kb = size_bytes / 1024
    return {
        "target": target,
        "lines": lines,
        "kb": kb,
        "budget_lines": budget_lines,
        "budget_kb": budget_kb,
        "status": status,
        "line": f"memory: {lines}/{budget_lines} lines, {kb:.1f}/{budget_kb} KB - {status}",
    }


def would_prune_candidates(kept: list, duplicates: list[Path], limit: int = 5) -> list[str]:
    """Return human-review prune candidates without deleting anything."""
    out: list[str] = []
    for dup in duplicates:
        out.append(f"duplicate: {dup.name}")
    stale_entries = [(fp, fields, stale) for fp, fields, stale in kept if stale]
    for fp, _fields, stale in stale_entries:
        out.append(f"stale-paths: {fp.name} ({', '.join(stale)})")
    for fp, fields, _stale in sorted(kept, key=lambda item: str(item[1].get("date", ""))):
        if len(out) >= limit:
            break
        decisions = normalize_list(fields.get("decisions"))
        if len(decisions) <= 1:
            out.append(f"low-signal: {fp.name}")
    return out[:limit]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--memory-dir",
                   help="Memory root to maintain. Default: native Claude Code project memory.")
    p.add_argument("--repo-root", default=".",
                   help="Repo root for files_touched[] path validation.")
    p.add_argument("--repo-claude", default=None,
                   help="CLAUDE.md to check conflicts against (default: <repo-root>/CLAUDE.md).")
    p.add_argument("--apply", action="store_true",
                   help="Write the maintenance index and repair stale paths in source files. Default is dry-run.")
    p.add_argument("--drop-stale", action="store_true",
                   help="Remove stale files_touched[] entries instead of annotating them with ' # STALE'.")
    p.add_argument("--ingest", action="store_true", help="Ingest the maintenance index into Mem0 (guarded).")
    p.add_argument("--config", default="assets/mem0.config.yaml", help="Mem0 config for --ingest.")
    p.add_argument("--verify-symbols", action="store_true",
                   help="Verify explicit symbols/symbols_touched entries against --repo-root.")
    p.add_argument("--health-budget-lines", type=int, default=200,
                   help="Target max lines for MEMORY.md health reporting.")
    p.add_argument("--health-budget-kb", type=int, default=10,
                   help="Target max KiB for MEMORY.md health reporting.")
    p.add_argument("--scope-filter", choices=["auto", "on", "off"], default="auto",
                   help="Filter out parent-workspace memories not matching --repo-root. "
                        "auto applies only when default native memory resolves to a parent.")
    return p


def maybe_ingest_mem0(text: str, config_path: Path) -> str:
    try:
        from mem0 import Memory  # type: ignore
    except ImportError:
        return ("Mem0 not installed; skipping ingest. "
                "Install vendored backbone: pip install -e vendor/mem0 (or `pip install mem0ai`).")
    if not config_path.exists():
        return f"Mem0 config not found: {config_path}; skipping ingest."
    memory = Memory.from_config(config_path=str(config_path))
    memory.add(text)
    return "Ingested L3 index into Mem0."


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve()
    explicit_memory_dir = bool(args.memory_dir)
    native_resolution = None if explicit_memory_dir else resolve_native_memory(repo_root)
    memory_dir = (Path(args.memory_dir).expanduser() if explicit_memory_dir
                  else native_resolution.memory_dir)
    explicit_native_relation = native_memory_relation(memory_dir, repo_root) if explicit_memory_dir else None
    source_dir = memory_dir / "episodic"
    if not source_dir.exists():
        source_dir = memory_dir

    if not source_dir.exists():
        print(f"No memory dir: {source_dir}. Pass --memory-dir to an existing native/Mem0 export.", file=sys.stderr)
        return 1

    files = sorted(fp for fp in source_dir.glob("*.md") if fp.name != "MEMORY.md")
    inherited_parent_memory = bool(
        (native_resolution and not native_resolution.exact)
        or (explicit_native_relation and not explicit_native_relation.exact)
    )
    apply_scope_filter = should_apply_scope_filter(args.scope_filter, inherited_parent_memory=inherited_parent_memory)
    scope = project_scope(repo_root)
    scoped_files: list[Path] = []
    out_of_scope: list[Path] = []
    for fp in files:
        if apply_scope_filter and not memory_matches_project(fp.read_text(encoding="utf-8", errors="ignore"), scope):
            out_of_scope.append(fp)
        else:
            scoped_files.append(fp)
    seen: dict[str, Path] = {}
    duplicates: list[Path] = []
    kept: list[tuple[Path, dict, list]] = []  # (path, fields, stale_paths)
    total_stale = 0
    stale_symbols_by_file: dict[Path, list[str]] = {}
    heuristic_symbols_by_file: dict[Path, list[str]] = {}

    for fp in scoped_files:
        text = fp.read_text(encoding="utf-8")
        fields = memory_fields(text, fp)
        sig = episode_signature(fields)
        if sig in seen:
            duplicates.append(fp)
            continue
        seen[sig] = fp
        _existing, stale = validate_paths(fields.get("files_touched"), repo_root)
        total_stale += len(stale)
        if args.verify_symbols:
            explicit = explicit_symbols(fields)
            _existing_symbols, stale_symbols = validate_symbols(explicit, repo_root)
            if stale_symbols:
                stale_symbols_by_file[fp] = stale_symbols
            heur = [s for s in heuristic_symbols(text) if s not in explicit]
            _existing_heur, stale_heur = validate_symbols(heur, repo_root)
            if stale_heur:
                heuristic_symbols_by_file[fp] = stale_heur
        kept.append((fp, fields, stale))

    # Build a deterministic maintenance index of survivors (filename-sorted, no timestamps).
    index_header = ["---", "kind: maintenance-index", "source: dream",
                    f"entries: {len(kept)}", "---", "", "# Memory Maintenance Index (dream)", ""]
    digest_lines = list(index_header)
    index_lines = []
    for fp, fields, stale in kept:
        task = fields.get("task", fp.stem)
        date = fields.get("date", "")
        flag = f"  [STALE PATHS: {', '.join(stale)}]" if stale else ""
        digest_lines.append(f"- ({date}) {task}{flag}")
        link_target = fp.relative_to(memory_dir) if fp.is_relative_to(memory_dir) else fp.name
        index_lines.append(f"- [{task}]({link_target}) — {date}")
    digest = "\n".join(digest_lines) + "\n"
    health = memory_health(memory_dir, digest, len(kept), args.health_budget_lines, args.health_budget_kb)
    prune_candidates = (would_prune_candidates(kept, duplicates)
                        if health["status"] == "OVER" else [])
    digest = digest.rstrip() + "\n\n## Health\n\n" + health["line"] + "\n"
    if prune_candidates:
        digest += "\n## Would prune\n\n" + "\n".join(f"- {c}" for c in prune_candidates) + "\n"

    # --- 5.3: conflict detection over the kept episodes ---
    claude_md = (Path(args.repo_claude) if args.repo_claude
                 else repo_root / "CLAUDE.md")
    existing_rules = read_existing_rules(memory_dir / "semantic",
                                         claude_md if claude_md.exists() else None)
    conflicts = detect_conflicts(kept, existing_rules)
    patch = propose_claude_patch(claude_md, conflicts) if claude_md.exists() else ""

    mode = "APPLY" if args.apply else "DRY RUN (use --apply to write)"
    repair_verb = "drop" if args.drop_stale else "annotate"
    print(f"# dream — {mode}")
    print(f"  memory root      : {memory_dir}")
    print(f"  entries scanned  : {len(files)}")
    print(f"  scope filter     : {args.scope_filter} ({'on' if apply_scope_filter else 'off'})")
    print(f"  out-of-scope skipped: {len(out_of_scope)}")
    print(f"  duplicates       : {len(duplicates)}")
    print(f"  stale paths found: {total_stale}")
    print(f"  stale symbols found: {sum(len(v) for v in stale_symbols_by_file.values())}")
    print(f"  heuristic symbol warnings: {sum(len(v) for v in heuristic_symbols_by_file.values())}")
    print(f"  kept (-> index)  : {len(kept)}")
    print(f"  conflicts found  : {len(conflicts)}")
    print(f"  health           : {health['line']} ({health['target']})")
    for c in conflicts:
        print(f"    [CONFLICT] {c['source']}: \"{c['rule'][:50]}\" vs {c['episode']}")
    for fp, symbols in stale_symbols_by_file.items():
        print(f"    [STALE SYMBOL] {fp.name}: {', '.join(symbols)}")
    for fp, symbols in heuristic_symbols_by_file.items():
        print(f"    [SYMBOL WARNING] {fp.name}: {', '.join(symbols)}")
    for cand in prune_candidates:
        print(f"    would prune: {cand}")
    for fp in out_of_scope:
        print(f"    [OUT-OF-SCOPE] {fp.name}")

    files_rewritten = 0
    stale_repaired = 0
    for fp, fields, stale in kept:
        if not stale:
            continue
        text = fp.read_text(encoding="utf-8")
        new_text, changed = rewrite_files_touched(text, stale, args.drop_stale)
        if not changed:
            continue
        if args.apply:
            fp.write_text(new_text, encoding="utf-8")
            print(f"  [OK] repaired {len(stale)} stale path(s) in {fp} ({repair_verb})")
        else:
            print(f"  would repair {len(stale)} stale path(s) in {fp} ({repair_verb})")
        files_rewritten += 1
        stale_repaired += len(stale)
    print(f"  files rewritten  : {files_rewritten}")
    print(f"  stale paths repaired: {stale_repaired}")

    symbol_files_rewritten = 0
    stale_symbols_repaired = 0
    for fp, stale_symbols in stale_symbols_by_file.items():
        text = fp.read_text(encoding="utf-8")
        new_text, changed = rewrite_stale_symbols(text, stale_symbols)
        if not changed:
            continue
        if args.apply:
            fp.write_text(new_text, encoding="utf-8")
            print(f"  [OK] repaired {len(stale_symbols)} stale symbol(s) in {fp}")
        else:
            print(f"  would repair {len(stale_symbols)} stale symbol(s) in {fp}")
        symbol_files_rewritten += 1
        stale_symbols_repaired += len(stale_symbols)
    print(f"  symbol files rewritten  : {symbol_files_rewritten}")
    print(f"  stale symbols repaired  : {stale_symbols_repaired}")

    if args.apply:
        semantic_dir = memory_dir / "semantic"
        semantic_dir.mkdir(parents=True, exist_ok=True)
        digest_path = semantic_dir / "dream-index.md"
        digest_path.write_text(digest, encoding="utf-8")
        print(f"  [OK] wrote {digest_path}")
        for dup in duplicates:
            dup.unlink()
            print(f"  [OK] removed duplicate {dup}")
        if args.ingest:
            print("  " + maybe_ingest_mem0(digest, Path(args.config)))
        # 5.3: write conflict candidates + proposed CLAUDE.md patch to inbox/
        if conflicts:
            inbox = memory_dir / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            for i, c in enumerate(conflicts, 1):
                cand = inbox / f"conflict-{c['date'] or 'undated'}-{i}.md"
                cand.write_text(
                    "---\ntype: conflict-candidate\nstatus: needs_human_review\n"
                    f"source: {c['source']}\nepisode: {c['episode']}\nseverity: medium\n---\n"
                    f"# Conflict Candidate {i}\n\n## Existing Rule ({c['source']})\n{c['rule']}\n\n"
                    f"## New Observation ({c['episode']})\n{c['decision']}\n\n"
                    "## Recommended Action\nReview and update the rule; apply the proposed "
                    "CLAUDE.md patch below if correct.\n", encoding="utf-8")
                print(f"  [OK] wrote {cand}")
            if patch:
                patch_path = inbox / "claude-md.proposed.patch"
                patch_path.write_text(patch, encoding="utf-8")
                print(f"  [OK] wrote {patch_path} (NOT applied — run `git apply` after review)")
    else:
        for dup in duplicates:
            print(f"  would remove duplicate: {dup}")
        if conflicts:
            print(f"  would write {len(conflicts)} conflict-candidate(s) to inbox/"
                  + ("  + a proposed CLAUDE.md patch" if patch else ""))

    return 0


if __name__ == "__main__":
    sys.exit(main())
