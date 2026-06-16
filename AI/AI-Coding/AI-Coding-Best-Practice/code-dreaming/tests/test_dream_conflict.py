"""Tests for the 5.3 conflict-detection folded into dream."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dream  # noqa: E402


def _ep(decision, date="2026-06-14"):
    return (Path(f"{date}-x.md"), {"date": date, "decisions": [decision]}, [])


def test_conflict_flagged_when_absolute_rule_widened():
    rules = [("CLAUDE.md", "Fallback is triggered only after timeout.")]
    kept = [_ep("Fallback must also be triggered after provider health-check "
                "failure, not only after timeout.")]
    c = dream.detect_conflicts(kept, rules)
    assert len(c) == 1
    assert c[0]["source"] == "CLAUDE.md"


def test_no_conflict_when_decision_agrees():
    rules = [("CLAUDE.md", "Fallback is triggered only after timeout.")]
    kept = [_ep("Fallback fires after request timeout.")]  # no widen marker
    assert dream.detect_conflicts(kept, rules) == []


def test_no_conflict_on_unrelated_subject():
    rules = [("CLAUDE.md", "Never use floating point for money settlement.")]
    kept = [_ep("Fallback must also fire on health-check failure, not only timeout.")]
    assert dream.detect_conflicts(kept, rules) == []


def test_no_conflict_when_rule_not_absolute():
    rules = [("L3:RB.md", "Fallback is triggered after request timeout.")]  # no only/always
    kept = [_ep("Fallback must also be triggered after health-check failure, not only timeout.")]
    assert dream.detect_conflicts(kept, rules) == []


def test_validate_paths_tolerates_missing_key(tmp_path):
    # real native memory files have frontmatter but often no files_touched key,
    # so fields.get("files_touched") is None — must not crash (regression).
    assert dream.validate_paths(None, tmp_path) == ([], [])
    assert dream.validate_paths("", tmp_path) == ([], [])
    assert dream.validate_paths([], tmp_path) == ([], [])
    (tmp_path / "a.txt").write_text("x")
    assert dream.validate_paths("a.txt", tmp_path) == (["a.txt"], [])
    assert dream.validate_paths("gone.txt", tmp_path) == ([], ["gone.txt"])


def test_proposed_patch_annotates_not_rewrites(tmp_path):
    cm = tmp_path / "CLAUDE.md"
    cm.write_text("# R\n\n- Fallback is triggered only after timeout.\n", encoding="utf-8")
    conflicts = [{"source": "CLAUDE.md", "rule": "Fallback is triggered only after timeout.",
                  "episode": "e.md", "decision": "also health-check", "date": "2026-06-14"}]
    patch = dream.propose_claude_patch(cm, conflicts)
    assert "DREAM-CONFLICT" in patch and patch.startswith("--- a/CLAUDE.md")
    # original on disk is untouched (patch is a proposal, not an edit)
    assert "DREAM-CONFLICT" not in cm.read_text(encoding="utf-8")


def test_symbol_validation_marks_explicit_symbols_only(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("class ExistingThing:\n    pass\n", encoding="utf-8")
    mem = tmp_path / "memory"
    episodic = mem / "episodic"
    episodic.mkdir(parents=True)
    entry = episodic / "entry.md"
    entry.write_text(
        "---\n"
        "task: symbols\n"
        "symbols:\n"
        "  - ExistingThing\n"
        "  - DeletedThing\n"
        "files_touched: []\n"
        "---\n"
        "# Symbols\n\n"
        "The body mentions `MaybeDeleted` but this is heuristic only.\n",
        encoding="utf-8",
    )

    rc = dream.main([
        "--memory-dir", str(mem),
        "--repo-root", str(repo),
        "--verify-symbols",
        "--apply",
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "[STALE SYMBOL] entry.md: DeletedThing" in out
    assert "[SYMBOL WARNING] entry.md: MaybeDeleted" in out
    text = entry.read_text(encoding="utf-8")
    assert '  - "DeletedThing # STALE (symbol)"' in text
    assert "MaybeDeleted # STALE" not in text


def test_symbol_rewrite_is_idempotent(tmp_path):
    text = (
        "---\n"
        "symbols:\n"
        "  - \"Gone # STALE (symbol)\"\n"
        "---\n"
        "Body\n"
    )
    new_text, changed = dream.rewrite_stale_symbols(text, ["Gone"])
    assert new_text == text
    assert changed is False


def test_memory_health_line_written_to_index(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "memory"
    episodic = mem / "episodic"
    episodic.mkdir(parents=True)
    (episodic / "entry.md").write_text(
        "---\n"
        "task: health\n"
        "date: 2026-06-14\n"
        "decisions:\n"
        "  - Keep it compact.\n"
        "files_touched: []\n"
        "---\n",
        encoding="utf-8",
    )

    rc = dream.main([
        "--memory-dir", str(mem),
        "--repo-root", str(repo),
        "--health-budget-lines", "3",
        "--health-budget-kb", "1",
        "--apply",
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "memory:" in out
    index = (mem / "semantic" / "dream-index.md").read_text(encoding="utf-8")
    assert "## Health" in index
    assert "memory:" in index


def test_empty_memory_health_reports_zero(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "memory"
    mem.mkdir()

    rc = dream.main(["--memory-dir", str(mem), "--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "entries scanned  : 0" in out
    assert "memory: 0/200 lines" in out


def test_existing_dream_index_counts_toward_health_when_no_memory_md(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "memory"
    semantic = mem / "semantic"
    semantic.mkdir(parents=True)
    (semantic / "dream-index.md").write_text("# Existing\n\n- Item\n", encoding="utf-8")

    rc = dream.main(["--memory-dir", str(mem), "--repo-root", str(repo)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "entries scanned  : 0" in out
    assert "memory: 3/200 lines" in out


def test_over_budget_reports_would_prune(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "memory"
    episodic = mem / "episodic"
    episodic.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("\n".join(["line"] * 5), encoding="utf-8")
    for name in ("a.md", "b.md"):
        (episodic / name).write_text(
            "---\n"
            "task: dup\n"
            "date: 2026-06-14\n"
            "decisions:\n"
            "  - Same decision.\n"
            "files_touched: []\n"
            "---\n",
            encoding="utf-8",
        )

    rc = dream.main([
        "--memory-dir", str(mem),
        "--repo-root", str(repo),
        "--health-budget-lines", "1",
        "--health-budget-kb", "1",
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "OVER" in out
    assert "would prune: duplicate: b.md" in out
