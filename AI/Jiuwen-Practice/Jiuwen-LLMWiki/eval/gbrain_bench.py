#!/usr/bin/env python3
"""gbrain retrieval-leg benchmark (PRD V6 AG-M1): CLI vs persistent MCP stdio.

Measures what one ask pays before the model is ever called: hybrid search plus
loading the evidence for the top-k pages, through both transports, n rounds.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llmwiki import config as config_mod  # noqa: E402
from llmwiki.store import open_store  # noqa: E402

QUERY = "What is the maximum size of a single OBS object?"


def leg(store, k: int) -> float:
    t0 = time.monotonic()
    slugs = store.search(QUERY, k)
    pages = [store.get(s) for s in slugs]
    dt = time.monotonic() - t0
    assert any(p is not None for p in pages), "retrieval leg returned nothing"
    return dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("-k", type=int, default=6)
    a = ap.parse_args()
    base = config_mod.load(a.config)

    cli_cfg = config_mod.load(a.config)
    cli_cfg.gbrain.backend = "gbrain"
    cli = open_store(cli_cfg)

    mcp_cfg = config_mod.load(a.config)
    mcp_cfg.gbrain.backend = "gbrain-mcp"
    mcp = open_store(mcp_cfg)

    cli_times = [leg(cli, a.k) for _ in range(a.n)]
    mcp_times = [leg(mcp, a.k) for _ in range(a.n)]
    # one warm round excluded implicitly: first MCP round includes handshake

    def stats(ts):
        ts = sorted(ts)
        best, med = ts[0], ts[len(ts) // 2]
        return best, med

    cb, cm = stats(cli_times)
    mb, mm = stats(mcp_times)
    print(f"retrieval leg (search + top-{a.k} evidence), {a.n} rounds, query={QUERY!r}")
    print(f"  CLI  : best {cb:.2f}s  median {cm:.2f}s   {[round(t,2) for t in cli_times]}")
    print(f"  MCP  : best {mb:.2f}s  median {mm:.2f}s   {[round(t,2) for t in mcp_times]}")
    speedup = cm / max(mm, 1e-6)
    print(f"  speedup (median): {speedup:.1f}x  -> {'PASS' if speedup >= 3 else 'FAIL'} (AG-M1 bar >=3x)")
    return 0 if speedup >= 3 else 1


if __name__ == "__main__":
    sys.exit(main())
