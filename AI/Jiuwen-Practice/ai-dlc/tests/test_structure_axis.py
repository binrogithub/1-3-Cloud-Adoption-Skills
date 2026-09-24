"""structure-axis — tests.

A brief carrying >=2 data-display markers (odds table, live scores)
boosts candidates whose od.scenario declares the data-board shape —
a betting board and a tourism landing no longer land on the same
marketing template.

Run:  python3 -m pytest tests/test_structure_axis.py -v
"""
import importlib.util
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_sa", _BIN / "bin" / "plan.py")


def _kw(q):
    return {"query_tokens": plan._tokenize_query(q),
            "text": q.lower()}


def _landing():
    """A marketing landing candidate: name/triggers dominate the
    word 'landing' (the Panama/VerdeBet collision shape)."""
    return {"name": "open landing", "dir": "open-landing",
            "triggers": ["landing page", "marketing"],
            "description": "editorial landing marketing page",
            "scenario": "marketing", "category": "brand-page"}


def _board():
    """A data-board candidate: scenario declares the shape."""
    return {"name": "live board", "dir": "live-board",
            "triggers": ["realtime data"],
            "description": "live operations board",
            "scenario": "operation", "category": "web"}


class TestStructureAxis:
    def test_data_brief_prefers_the_board(self):
        q = _kw("marketing site with odds table and live scores")
        board = plan._score_candidate(_board(), q, None)
        landing = plan._score_candidate(_landing(), q, None)
        assert board > landing, \
            f"the data-board shape must outrank the landing word: " \
            f"board={board} landing={landing}"

    def test_plain_marketing_brief_keeps_the_landing(self):
        q = _kw("marketing landing page for a tourism site")
        board = plan._score_candidate(_board(), q, None)
        landing = plan._score_candidate(_landing(), q, None)
        assert landing > board

    def test_single_marker_does_not_fire(self):
        """One stray marker is not a shape declaration — the axis
        needs >=2 distinct markers."""
        q = _kw("marketing landing page with a table")
        b1 = plan._score_candidate(_board(), q, None)
        q2 = _kw("marketing landing page")
        b2 = plan._score_candidate(_board(), q2, None)
        assert b1 == b2, "single marker must not change the score"

    def test_matched_features_carries_the_axis(self):
        feats = plan._matched_features(
            _board(), {"odds", "table", "live"})
        assert "structure_axis" in feats

    def test_zh_markers_fire(self):
        q = _kw("体育盘口 实时赔率 表格 站点")
        board = plan._score_candidate(_board(), q, None)
        landing = plan._score_candidate(_landing(), q, None)
        assert board > landing
