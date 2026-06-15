import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dream_signals  # noqa: E402


@dataclass
class FakeRecord:
    evidence_id: str
    role: str
    timestamp: str
    preview: str


def test_classify_matches_each_signal_class():
    assert dream_signals.classify("Actually no, that's wrong") == ["corrections"]
    assert dream_signals.classify("I prefer spaces; always use black") == ["preferences"]
    assert dream_signals.classify("let's go with postgres, we agreed") == ["decisions"]
    assert dream_signals.classify("again, every time the usual") == ["recurring"]
    assert dream_signals.classify("the weather is nice today") == []


def test_classify_returns_priority_order_for_multimatch():
    matches = dream_signals.classify("actually I prefer spaces, let's switch to tabs again")
    assert matches[0] == "corrections"
    assert set(matches) == {"corrections", "preferences", "decisions", "recurring"}
    assert dream_signals.primary_class("actually I prefer spaces") == "corrections"


def test_scan_records_sorts_by_priority_and_caps():
    records = [
        FakeRecord("ev-1", "user", "t1", "again as usual"),               # recurring
        FakeRecord("ev-2", "user", "t2", "actually that's not right"),    # corrections
        FakeRecord("ev-3", "user", "t3", "I prefer tabs"),                # preferences
        FakeRecord("ev-4", "assistant", "t4", "nothing notable here"),    # no signal
    ]
    hits = dream_signals.scan_records(records, limit=10)
    assert [h.signal_class for h in hits] == ["corrections", "preferences", "recurring"]
    assert dream_signals.class_counts(hits) == {
        "corrections": 1, "preferences": 1, "decisions": 0, "recurring": 1,
    }

    capped = dream_signals.scan_records(records, limit=1)
    assert len(capped) == 1
    assert capped[0].signal_class == "corrections"
