"""Multi-signal retrieval (PRD-design §5.5 / epic D7).

FTS5-based retrieval subsystem to stdlib sqlite3:
  - buildFtsQuery()  <- vendor/mimo-code/opencode/src/memory/fts-query.ts
  - BM25 + relative score-floor search  <- .../memory/service.ts (search)
  - reconcile/walk  <- .../memory/reconcile.ts

Algorithm and SQL are reused verbatim; only the host language differs. New
first-party logic is limited to the token-budget / inject_policy trim the PRD
adds on top (§5.5.2/§5.5.4).
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

# Ported from fts-query.ts: tokenize on Unicode letter/number/underscore runs,
# phrase-quote each token, OR-join. Phrase quotes neutralize FTS5 specials;
# OR (not AND) keeps recall high and lets BM25 rank. \w+ with re.UNICODE keeps
# CJK recall (openclaw PR #20767).
_TOKEN_RE = re.compile(r"[^\W]+", re.UNICODE)


def build_fts_query(raw: str) -> str | None:
    tokens = [t for t in _TOKEN_RE.findall(raw) if t]
    if not tokens:
        return None
    return " OR ".join('"%s"' % t.replace('"', "") for t in tokens)


def native_memory_dir(start: Path | None = None) -> Path:
    """native Claude Code project memory dir (paths.ts `cc` scope)."""
    repo = (start or Path.cwd()).resolve()
    key = "-" + "-".join(p for p in repo.parts if p != "/")
    return Path.home() / ".claude" / "projects" / key / "memory"


def _build_index(con: sqlite3.Connection, memory_dir: Path) -> int:
    con.execute(
        "CREATE VIRTUAL TABLE memory_fts USING fts5(path, body, tokenize='unicode61')"
    )
    n = 0
    for md in sorted(memory_dir.rglob("*.md")):
        con.execute(
            "INSERT INTO memory_fts(path, body) VALUES (?, ?)",
            (str(md), md.read_text(encoding="utf-8", errors="replace")),
        )
        n += 1
    return n


def search(query: str, memory_dir: Path | None = None, limit: int = 5,
           floor_ratio: float = 0.15):
    """BM25 search with relative score floor (service.ts search, ported)."""
    memory_dir = memory_dir or native_memory_dir()
    fts = build_fts_query(query)
    if not fts or not memory_dir.exists():
        return []
    con = sqlite3.connect(":memory:")
    try:
        if not _build_index(con, memory_dir):
            return []
        fetch = min(limit * 3, 50)  # over-fetch so the floor can trim noise
        rows = con.execute(
            "SELECT path, snippet(memory_fts, 1, '<<', '>>', '...', 32) AS s, "
            "bm25(memory_fts) AS score FROM memory_fts "
            "WHERE memory_fts MATCH ? ORDER BY score LIMIT ?",
            (fts, fetch),
        ).fetchall()
    except sqlite3.OperationalError:
        return []  # FTS5 not compiled in
    finally:
        con.close()
    # bm25() lower=better -> flip to higher=better; keep #1, drop below floor.
    mapped = [{"path": p, "snippet": s, "score": -sc} for p, s, sc in rows]
    if not mapped:
        return []
    cutoff = mapped[0]["score"] * floor_ratio if floor_ratio > 0 else -1e30
    kept = [r for i, r in enumerate(mapped) if i == 0 or r["score"] >= cutoff]
    return kept[:limit]


def retrieve_approved_context(query: str, max_items: int = 5, max_tokens: int = 2000,
                              memory_dir: Path | None = None) -> str:
    """Top-k approved context under a token budget (§5.5.2). New first-party trim."""
    hits, used, lines = search(query, memory_dir, limit=max_items), 0, []
    lines.append("# Retrieved Approved Context\n")
    for h in hits:
        cost = len(h["snippet"]) // 4 + 1
        if used + cost > max_tokens:
            break
        used += cost
        lines.append(f"## {os.path.basename(h['path'])}  (score={h['score']:.2f})")
        lines.append(h["snippet"] + "\n")
    if not hits:
        lines.append("_no approved memory matched the query._")
    return "\n".join(lines)
