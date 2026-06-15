#!/usr/bin/env python3
"""distill — mine native/Mem0 memory into SOP review candidates.

Ported design from MiMo Code (MIT). Reads native Claude Code project memory or a
Mem0 Markdown export and mines groups of decisions that recur *together* across
memory entries (frequent co-occurring itemsets, not single-phrase frequency).
Emits *candidate* SOPs that explicitly require human/LLM review before
promotion. Harness not forked.

This is heuristic, dependency-free candidate mining: for each memory entry the
decisions are normalized into a deduped set, then recurring co-occurring groups
are surfaced via a small stdlib-only Apriori-style itemset pass. Output is a set
of review candidates, NOT finished SOPs — step bodies stay explicit review
placeholders. Dry-run by default. No secrets printed.
"""

import argparse
import re
import sys
from collections import Counter
from itertools import combinations
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
STOPWORDS = {"the", "a", "an", "to", "of", "and", "for", "in", "on", "with", "use", "using"}


def _claude_project_key(path: Path) -> str:
    """Return Claude Code's project directory key for an absolute path."""
    return "-" + "-".join(part for part in path.resolve().parts if part != "/")


def resolve_native_memory_dir(start: Path | None = None) -> Path:
    """Resolve the native Claude Code project memory dir for this repo."""
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
    return {"task": title, "decisions": decisions}


def parse_frontmatter(text: str) -> dict:
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


def normalize_phrase(text: str) -> str:
    """Collapse a decision into a comparable canonical phrase."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    return " ".join(words)


def decision_set(fields: dict) -> frozenset:
    """Normalize an episode's decisions into a deduped frozenset of phrases.

    Drops empties and collapses duplicates so each episode contributes a single
    set of distinct decisions (the unit of co-occurrence mining).
    """
    decisions = fields.get("decisions") or []
    if isinstance(decisions, str):
        decisions = [decisions]
    phrases = set()
    for d in decisions:
        norm = normalize_phrase(d)
        if norm:
            phrases.add(norm)
    return frozenset(phrases)


def memory_markdown_files(memory_dir: Path) -> list[Path]:
    source_dir = memory_dir / "episodic"
    if not source_dir.exists():
        source_dir = memory_dir
    return sorted(fp for fp in source_dir.glob("*.md") if fp.name != "MEMORY.md")


def mine_cooccurring(memory_dir: Path, min_support: int,
                     files: list[Path] | None = None,
                     max_group_size: int = 4) -> list[tuple[frozenset, int]]:
    """Return [(group_of_decisions, support_count)] for groups that co-occur.

    A group is a set of decisions that appear together in the same episode and
    whose identical membership recurs across >= min_support episodes. Groups are
    mined with an Apriori-style join+prune pass (size 2..max_group_size) over
    frequent individual decisions, plus the exact full-episode groups. Strictly
    subsumed groups (a subset of a larger kept group at equal/higher support) are
    dropped. Sorted by (support desc, size desc).
    """
    episodes: list[frozenset] = []
    for fp in files if files is not None else memory_markdown_files(memory_dir):
        ds = decision_set(memory_fields(fp.read_text(encoding="utf-8"), fp))
        if ds:
            episodes.append(ds)

    if not episodes:
        return []

    def support(group: frozenset) -> int:
        return sum(1 for ep in episodes if group <= ep)

    # Frequent single decisions (Apriori base).
    item_counts: Counter = Counter()
    for ep in episodes:
        for item in ep:
            item_counts[item] += 1
    frequent_items = {frozenset([i]) for i, c in item_counts.items() if c >= min_support}

    # Apriori: build frequent k-itemsets from frequent (k-1)-itemsets.
    group_support: dict[frozenset, int] = {}
    prev_frequent = frequent_items
    k = 2
    while prev_frequent and k <= max_group_size:
        # Candidate generation: union pairs of (k-1)-itemsets into k-itemsets.
        candidates: set[frozenset] = set()
        prev_list = list(prev_frequent)
        for i in range(len(prev_list)):
            for j in range(i + 1, len(prev_list)):
                union = prev_list[i] | prev_list[j]
                if len(union) == k:
                    # Prune: every (k-1)-subset must be frequent.
                    if all(frozenset(sub) in prev_frequent
                           for sub in combinations(union, k - 1)):
                        candidates.add(union)
        current_frequent: set[frozenset] = set()
        for cand in candidates:
            s = support(cand)
            if s >= min_support:
                group_support[cand] = s
                current_frequent.add(cand)
        prev_frequent = current_frequent
        k += 1

    # Also fold in exact full-episode groups (size >= 2) that recur themselves.
    exact_counts: Counter = Counter(ep for ep in episodes if len(ep) >= 2)
    for group, c in exact_counts.items():
        if c >= min_support and len(group) <= max_group_size:
            # Exact recurrence support is its co-occurrence support; reuse subset count.
            group_support[group] = max(group_support.get(group, 0), support(group))

    if not group_support:
        return []

    # Drop strictly subsumed groups: a subset of a larger group at equal/higher support.
    groups = sorted(group_support.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    kept: list[tuple[frozenset, int]] = []
    for group, sup in groups:
        subsumed = any(group < bigger and bsup >= sup for bigger, bsup in kept)
        if not subsumed:
            kept.append((group, sup))

    kept.sort(key=lambda kv: (-kv[1], -len(kv[0]), sorted(kv[0])))
    return kept


def render_candidates(candidates: list[tuple[frozenset, int]]) -> str:
    lines = ["---", "tier: L4", "source: distill", "status: candidate",
             "review_required: true", f"candidates: {len(candidates)}", "---", "",
             "# SOP Candidates (distill — needs review)", "",
             "Decision groups that recur *together* across available memory entries.",
             "These are mining candidates, NOT finished SOPs: every group below",
             "requires human/LLM review and step synthesis before promotion.", ""]
    for i, (group, count) in enumerate(candidates, 1):
        members = sorted(group)
        slug = re.sub(r"\s+", "-", "-".join(members))[:48].strip("-")
        lines += [f"## Candidate SOP {i}", f"- support: co-occurred in {count} episodes",
                  f"- group size: {len(members)} decisions",
                  "- member decisions:"]
        for m in members:
            lines.append(f"  - {m}")
        lines += [
            f"- candidate slash command: `/{slug}`",
            "- steps: <synthesize from member episodes — HUMAN/LLM REVIEW REQUIRED>",
            "",
        ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Heuristic co-occurrence candidate mining: surface decision "
                    "groups that recur together in native/Mem0 memory as SOP review "
                    "candidates (not finished SOPs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--memory-dir",
                   help="Memory root to mine. Default: native Claude Code project memory.")
    p.add_argument("--repo-root", default=".",
                   help="Repo root used for project-scope filtering.")
    p.add_argument("--scope-filter", choices=["auto", "on", "off"], default="auto",
                   help="Filter out parent-workspace memories not matching --repo-root. "
                        "auto applies only when default native memory resolves to a parent.")
    p.add_argument("--min-support", type=int, default=2,
                   help="Min memory entries a decision GROUP must co-occur in to become "
                        "a candidate (default: 2).")
    p.add_argument("--max-group-size", type=int, default=4,
                   help="Max number of decisions in a mined co-occurring group "
                        "(default: 4).")
    p.add_argument("--apply", action="store_true",
                   help="Write SOP candidate file. Default is dry-run.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve()
    explicit_memory_dir = bool(args.memory_dir)
    native_resolution = None if explicit_memory_dir else resolve_native_memory(repo_root)
    memory_dir = (Path(args.memory_dir).expanduser() if explicit_memory_dir
                  else native_resolution.memory_dir)
    explicit_native_relation = native_memory_relation(memory_dir, repo_root) if explicit_memory_dir else None
    if not memory_dir.exists():
        print(f"No memory dir: {memory_dir}. Pass --memory-dir to an existing native/Mem0 export.", file=sys.stderr)
        return 1

    files = memory_markdown_files(memory_dir)
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

    candidates = mine_cooccurring(memory_dir, args.min_support, scoped_files, args.max_group_size)
    mode = "APPLY" if args.apply else "DRY RUN (use --apply to write)"
    print(f"# distill — co-occurrence candidate mining — {mode}")
    print(f"  memory root      : {memory_dir}")
    print(f"  entries scanned  : {len(files)}")
    print(f"  scope filter     : {args.scope_filter} ({'on' if apply_scope_filter else 'off'})")
    print(f"  out-of-scope skipped: {len(out_of_scope)}")
    print(f"  min-support      : {args.min_support}")
    print(f"  max-group-size   : {args.max_group_size}")
    print(f"  candidates mined : {len(candidates)}")
    for group, count in candidates:
        members = ", ".join(sorted(group))
        print(f"    x{count}  [size {len(group)}]  {members}")

    if not candidates:
        print("  (no co-occurring decision groups met the support threshold)")
        return 0

    if args.apply:
        proc_dir = memory_dir / "procedural"
        proc_dir.mkdir(parents=True, exist_ok=True)
        out = proc_dir / "distilled-candidates.md"
        out.write_text(render_candidates(candidates), encoding="utf-8")
        print(f"  [OK] wrote {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
