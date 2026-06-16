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
        FakeRecord("ev-1", "human", "t1", "again as usual"),               # recurring
        FakeRecord("ev-2", "human", "t2", "actually that's not right"),    # corrections
        FakeRecord("ev-3", "human", "t3", "I prefer tabs"),                # preferences
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


# --- E3 new tests ---


def test_system_role_record_is_skipped():
    """S3.1: system-role records must not generate signal hits."""
    records = [
        FakeRecord("ev-sys", "system", "t1", "actually that's not right"),
    ]
    hits = dream_signals.scan_records(records)
    assert hits == [], "system records must be filtered out"


def test_attachment_role_record_is_skipped():
    """S3.1: attachment-role records (e.g. SKILL.md content) must not generate hits."""
    records = [
        FakeRecord("ev-att", "attachment", "t1", "I prefer tabs; actually no"),
    ]
    hits = dream_signals.scan_records(records)
    assert hits == [], "attachment records must be filtered out"


def test_human_role_correction_detected():
    """S3.1: human-role records with correction language ARE scanned."""
    records = [
        FakeRecord("ev-h", "human", "t1", "that's wrong, please use X instead"),
    ]
    hits = dream_signals.scan_records(records)
    assert len(hits) == 1
    assert hits[0].signal_class == "corrections"


def test_confidently_wrong_not_flagged():
    """S3.2: the phrase 'confidently wrong' (from SKILL.md) must NOT match."""
    text = "flags signals where the model was confidently wrong"
    assert "corrections" not in dream_signals.classify(text), (
        "'confidently wrong' should no longer match the corrections class"
    )


def test_thats_wrong_approach_is_flagged():
    """S3.2: 'wrong approach' contextual pattern must be detected as a correction."""
    text = "thats wrong approach here, try pytest instead"
    classes = dream_signals.classify(text)
    assert "corrections" in classes, (
        "'wrong approach' must match the corrections class"
    )


def test_actually_no_pattern_still_works():
    """Regression S3.3: existing 'actually' pattern must still fire."""
    records = [
        FakeRecord("ev-r", "assistant", "t1", "actually no, that is not correct"),
    ]
    hits = dream_signals.scan_records(records)
    assert len(hits) == 1
    assert hits[0].signal_class == "corrections"
