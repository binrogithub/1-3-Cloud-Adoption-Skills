"""Tests for mce/retrieve.py — the ported memory-retrieval subsystem.

Stdlib-only, FTS5 assumed available. All memory dirs use tmp_path; the real
home dir is never touched.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mce.retrieve import (
    build_fts_query,
    native_memory_dir,
    retrieve_approved_context,
    search,
)


# --------------------------------------------------------------------------
# build_fts_query
# --------------------------------------------------------------------------
class TestBuildFtsQuery:
    def test_multi_word_becomes_or_joined_phrase_quoted_tokens(self):
        assert build_fts_query("one two three") == '"one" OR "two" OR "three"'

    def test_single_word_is_phrase_quoted(self):
        assert build_fts_query("hello") == '"hello"'

    def test_fts5_specials_are_neutralized_into_tokens(self):
        # Colons, parens, asterisks are FTS5-significant; they must be stripped
        # to plain tokens and never reach the matcher as operators.
        out = build_fts_query("db:port (5433)*")
        assert out == '"db" OR "port" OR "5433"'
        # No raw FTS5 specials survive in the output.
        for special in (":", "(", ")", "*"):
            assert special not in out

    def test_adversarial_specials_do_not_crash_and_query_is_usable(self, tmp_path):
        # Build a real index and confirm the produced query actually executes
        # against FTS5 without raising (the whole point of phrase-quoting).
        (tmp_path / "a.md").write_text("the port number is 5433 on the db host")
        for raw in ('db:port (5433)*', 'a AND b', 'NOT "x" OR (y)*', "^foo$ bar-baz"):
            q = build_fts_query(raw)
            assert q is not None
            # Should not raise — query is safe to MATCH.
            results = search(raw, tmp_path, limit=5)
            assert isinstance(results, list)

    def test_cjk_yields_unicode_tokens(self):
        out = build_fts_query("路由 回退")
        assert out == '"路由" OR "回退"'

    def test_mixed_cjk_and_ascii(self):
        out = build_fts_query("路由 fallback")
        assert out == '"路由" OR "fallback"'

    def test_empty_string_returns_none(self):
        assert build_fts_query("") is None

    def test_whitespace_only_returns_none(self):
        assert build_fts_query("   \t\n  ") is None

    def test_punctuation_only_returns_none(self):
        assert build_fts_query("!!! ... *** --- :::") is None

    def test_embedded_double_quotes_are_stripped(self):
        out = build_fts_query('say "hi" there')
        # Tokenizer already splits on non-word chars, so quotes never become
        # part of a token; assert no stray inner quotes corrupt the phrasing.
        assert out == '"say" OR "hi" OR "there"'
        # Every token is wrapped in exactly one pair of quotes (no doubles).
        assert '""' not in out

    def test_underscore_is_a_word_char(self):
        # \w includes underscore, so snake_case stays one token.
        assert build_fts_query("snake_case_token") == '"snake_case_token"'


# --------------------------------------------------------------------------
# native_memory_dir
# --------------------------------------------------------------------------
class TestNativeMemoryDir:
    def test_shape_for_known_path(self):
        result = native_memory_dir(Path("/home/user/proj"))
        assert result == Path.home() / ".claude" / "projects" / "-home-user-proj" / "memory"

    def test_key_is_dash_joined_path_parts(self):
        result = native_memory_dir(Path("/a/b/c"))
        # parts are ['/', 'a', 'b', 'c']; root '/' dropped, dash-joined, leading dash.
        assert result.parent.name == "-a-b-c"
        assert result.name == "memory"

    def test_ends_in_claude_projects_memory(self):
        result = native_memory_dir(Path("/x/y"))
        parts = result.parts
        assert parts[-1] == "memory"
        assert parts[-3] == "projects"
        assert parts[-4] == ".claude"


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------
def _make_corpus(base: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        p = base / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return base


class TestSearch:
    def test_most_relevant_file_ranks_first(self, tmp_path):
        _make_corpus(tmp_path, {
            "routing.md": "routing fallback strategy. routing routing routing fallback fallback.",
            "billing.md": "billing invoices and payment processing pipeline.",
            "auth.md": "authentication tokens and session management.",
        })
        hits = search("routing fallback", tmp_path, limit=5)
        assert hits, "expected at least one hit"
        assert Path(hits[0]["path"]).name == "routing.md"

    def test_top_hit_always_kept_even_when_bm25_collapses(self, tmp_path):
        # A tiny corpus where every doc contains the term -> BM25 ~ 0 for all.
        # The #1 result must still be retained (the i==0 keep guarantee).
        _make_corpus(tmp_path, {
            "a.md": "alpha",
            "b.md": "alpha",
        })
        hits = search("alpha", tmp_path, limit=5)
        assert len(hits) >= 1
        # Even though score may be ~0, index-0 survives the floor.
        assert hits[0]["path"].endswith(".md")

    def test_unrelated_file_dropped_by_relative_score_floor(self, tmp_path):
        # One strongly-matching file plus one weakly-matching file. The weak
        # match should fall below floor_ratio * topscore and be dropped, while
        # the strong match stays.
        _make_corpus(tmp_path, {
            "strong.md": " ".join(["kubernetes"] * 50) + " orchestration scheduler pods",
            "weak.md": "general notes mentioning kubernetes once here.",
            "noise.md": "completely different content about cooking recipes.",
        })
        hits = search("kubernetes orchestration scheduler", tmp_path, limit=5,
                      floor_ratio=0.5)
        names = {Path(h["path"]).name for h in hits}
        assert "strong.md" in names
        # With a high floor ratio, the weakly-matching doc is trimmed.
        assert "weak.md" not in names
        assert "noise.md" not in names

    def test_empty_dir_returns_empty(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert search("anything", empty, limit=5) == []

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        assert search("anything", missing, limit=5) == []

    def test_query_with_no_matches_returns_empty(self, tmp_path):
        _make_corpus(tmp_path, {"a.md": "apples bananas cherries"})
        assert search("zzzznonexistentword", tmp_path, limit=5) == []

    def test_empty_query_returns_empty(self, tmp_path):
        _make_corpus(tmp_path, {"a.md": "content"})
        assert search("   ", tmp_path, limit=5) == []

    def test_limit_caps_results(self, tmp_path):
        # Many strongly-matching docs so the floor keeps them all; limit must cap.
        files = {f"doc{i}.md": "shared term shared term shared term" for i in range(10)}
        _make_corpus(tmp_path, files)
        hits = search("shared term", tmp_path, limit=3)
        assert len(hits) == 3

    def test_recurses_into_subdirectories(self, tmp_path):
        _make_corpus(tmp_path, {
            "sub/nested.md": "deeply nested searchable widget content",
            "top.md": "unrelated stuff",
        })
        hits = search("widget", tmp_path, limit=5)
        assert any(Path(h["path"]).name == "nested.md" for h in hits)

    def test_floor_ratio_zero_keeps_everything_up_to_limit(self, tmp_path):
        _make_corpus(tmp_path, {
            "strong.md": " ".join(["term"] * 50),
            "weak.md": "term appears once",
        })
        hits = search("term", tmp_path, limit=5, floor_ratio=0.0)
        assert len(hits) == 2

    def test_score_is_higher_better(self, tmp_path):
        # search flips bm25 so returned scores rank descending.
        _make_corpus(tmp_path, {
            "strong.md": " ".join(["needle"] * 30),
            "weak.md": "needle once",
        })
        hits = search("needle", tmp_path, limit=5, floor_ratio=0.0)
        scores = [h["score"] for h in hits]
        assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------
# retrieve_approved_context
# --------------------------------------------------------------------------
class TestRetrieveApprovedContext:
    def test_returns_header(self, tmp_path):
        _make_corpus(tmp_path, {"a.md": "routing fallback content"})
        out = retrieve_approved_context("routing", memory_dir=tmp_path)
        assert out.startswith("# Retrieved Approved Context")

    def test_includes_matched_file_basename_and_score(self, tmp_path):
        _make_corpus(tmp_path, {"routing.md": "routing fallback strategy details"})
        out = retrieve_approved_context("routing", memory_dir=tmp_path)
        assert "routing.md" in out
        assert "score=" in out

    def test_respects_max_items(self, tmp_path):
        files = {f"doc{i}.md": "shared keyword keyword keyword" for i in range(8)}
        _make_corpus(tmp_path, files)
        out = retrieve_approved_context("keyword", max_items=2, max_tokens=100000,
                                        memory_dir=tmp_path)
        # Count rendered "## " section headers (one per included hit).
        section_headers = [ln for ln in out.splitlines() if ln.startswith("## ")]
        assert len(section_headers) == 2

    def test_truncates_under_tight_token_budget(self, tmp_path):
        files = {f"doc{i}.md": "shared keyword " * 40 for i in range(5)}
        _make_corpus(tmp_path, files)
        loose = retrieve_approved_context("keyword", max_items=5, max_tokens=100000,
                                          memory_dir=tmp_path)
        tight = retrieve_approved_context("keyword", max_items=5, max_tokens=1,
                                          memory_dir=tmp_path)
        loose_sections = [ln for ln in loose.splitlines() if ln.startswith("## ")]
        tight_sections = [ln for ln in tight.splitlines() if ln.startswith("## ")]
        # A tight budget yields strictly fewer rendered sections.
        assert len(tight_sections) < len(loose_sections)

    def test_no_match_emits_placeholder_line(self, tmp_path):
        _make_corpus(tmp_path, {"a.md": "apples bananas"})
        out = retrieve_approved_context("zzzznope", memory_dir=tmp_path)
        assert "_no approved memory matched the query._" in out
        # Header is still present even with no matches.
        assert out.startswith("# Retrieved Approved Context")

    def test_empty_dir_emits_placeholder(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        out = retrieve_approved_context("anything", memory_dir=empty)
        assert "_no approved memory matched the query._" in out
