"""Offline SSE contract tests for the native MaaS Anthropic stream parser.

These tests verify the release-gate canary's SSE parser against fixtures that
encode the historical pretty-JSON (unprefixed line) and OpenAI ``[DONE]``
regressions, plus the valid thinking+text stream contract:

  * every non-empty line has a legal SSE prefix (``event:`` or ``data:``);
  * every ``data:`` payload is valid JSON;
  * no ``[DONE]`` marker appears;
  * ``thinking_delta`` only appears inside a thinking content block;
  * ``text_delta`` only appears inside a text content block;
  * the last event type is ``message_stop``;
  * event types are a subset of the known Anthropic streaming events.

The parser itself lives in ``tests/live_maas_probe.py`` so the live canary and
the offline tests share one implementation.  Live network probes are guarded
behind ``__main__`` and are never exercised by this test module.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from live_maas_probe import parse_sse as _parse_sse

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

# The full set of event types the native Anthropic streaming API may emit.
VALID_EVENT_TYPES = {
    "message_start",
    "content_block_start",
    "content_block_delta",
    "content_block_stop",
    "message_delta",
    "message_stop",
    "ping",
    "error",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture():
    """Return a callable that loads a fixture file by name."""

    def _load(name: str) -> str:
        path = FIXTURE_DIR / name
        return path.read_text()

    return _load


@pytest.fixture()
def parse_sse():
    """Return the parse_sse function under test."""
    return _parse_sse


# ---------------------------------------------------------------------------
# Valid stream contract
# ---------------------------------------------------------------------------


def test_valid_stream_passes(parse_sse, fixture):
    """A well-formed thinking+text stream must produce no errors and end with
    message_stop."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert result.event_types[-1] == "message_stop"
    assert result.errors == []


def test_valid_stream_event_types_are_subset(parse_sse, fixture):
    """Every event type in a valid stream must be a known Anthropic event."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    for et in result.event_types:
        assert et in VALID_EVENT_TYPES, f"unknown event type: {et}"


def test_valid_stream_has_expected_event_sequence(parse_sse, fixture):
    """The valid fixture should contain the full thinking+text lifecycle."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert result.event_types[0] == "message_start"
    assert "content_block_start" in result.event_types
    assert "content_block_delta" in result.event_types
    assert "content_block_stop" in result.event_types
    assert "message_delta" in result.event_types
    assert result.event_types[-1] == "message_stop"


def test_valid_stream_all_data_payloads_are_json(parse_sse, fixture):
    """Every data: line in the valid stream must parse as JSON."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert "invalid_json" not in result.errors


# ---------------------------------------------------------------------------
# Historical regressions
# ---------------------------------------------------------------------------


def test_pretty_json_and_done_regressions_fail(parse_sse, fixture):
    """The pretty-JSON (unprefixed) and OpenAI [DONE] regressions must be
    detected as errors."""
    assert "unprefixed" in parse_sse(fixture("invalid-pretty-json-stream.sse")).errors
    assert "openai_done" in parse_sse(fixture("invalid-done-stream.sse")).errors


def test_pretty_json_regression_has_unprefixed_error(parse_sse, fixture):
    """A raw JSON line without data: prefix must flag 'unprefixed'."""
    result = parse_sse(fixture("invalid-pretty-json-stream.sse"))
    assert "unprefixed" in result.errors


def test_done_regression_has_openai_done_error(parse_sse, fixture):
    """A [DONE] marker after message_stop must flag 'openai_done'."""
    result = parse_sse(fixture("invalid-done-stream.sse"))
    assert "openai_done" in result.errors


def test_done_regression_does_not_have_unprefixed_error(parse_sse, fixture):
    """The [DONE] line is prefixed with data: so it should not also flag
    unprefixed — it is a distinct, known regression."""
    result = parse_sse(fixture("invalid-done-stream.sse"))
    assert "unprefixed" not in result.errors


# ---------------------------------------------------------------------------
# Block / delta pairing
# ---------------------------------------------------------------------------


def test_thinking_delta_only_in_thinking_block(parse_sse, fixture):
    """thinking_delta must only appear while a thinking content block is open."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert "thinking_mismatch" not in result.errors


def test_text_delta_only_in_text_block(parse_sse, fixture):
    """text_delta must only appear while a text content block is open."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert "text_mismatch" not in result.errors


def test_thinking_delta_in_text_block_is_mismatch(parse_sse, fixture):
    """If a thinking_delta appears while a text block is open, flag it."""
    stream = (
        'event: message_start\n'
        'data: {"type":"message_start","message":{"id":"m","type":"message","role":"assistant","model":"glm-5.2","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
        'event: content_block_start\n'
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
        'event: content_block_delta\n'
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"oops"}}\n\n'
        'event: content_block_stop\n'
        'data: {"type":"content_block_stop","index":0}\n\n'
        'event: message_delta\n'
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":1}}\n\n'
        'event: message_stop\n'
        'data: {"type":"message_stop"}\n'
    )
    result = parse_sse(stream)
    assert "thinking_mismatch" in result.errors


def test_text_delta_in_thinking_block_is_mismatch(parse_sse, fixture):
    """If a text_delta appears while a thinking block is open, flag it."""
    stream = (
        'event: message_start\n'
        'data: {"type":"message_start","message":{"id":"m","type":"message","role":"assistant","model":"glm-5.2","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
        'event: content_block_start\n'
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}}\n\n'
        'event: content_block_delta\n'
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"oops"}}\n\n'
        'event: content_block_stop\n'
        'data: {"type":"content_block_stop","index":0}\n\n'
        'event: message_delta\n'
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":1}}\n\n'
        'event: message_stop\n'
        'data: {"type":"message_stop"}\n'
    )
    result = parse_sse(stream)
    assert "text_mismatch" in result.errors


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_every_data_payload_is_valid_json(parse_sse, fixture):
    """Every data: line in the valid stream must be valid JSON."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert "invalid_json" not in result.errors


def test_no_done_after_message_stop_in_valid_stream(parse_sse, fixture):
    """The valid stream must not contain [DONE] after message_stop."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert "openai_done" not in result.errors


def test_event_types_are_valid_subset(parse_sse, fixture):
    """All event types in the valid stream must be from the known set."""
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    unknown = [et for et in result.event_types if et not in VALID_EVENT_TYPES]
    assert unknown == []


def test_empty_input_has_no_errors(parse_sse):
    """An empty stream should not crash; it simply has no events."""
    result = parse_sse("")
    assert result.event_types == []
    # An empty stream has no message_stop — that is not an *error* tag, just
    # a structural fact the caller can check via event_types.
    assert result.errors == []


def test_parse_sse_accepts_path(parse_sse, fixture):
    """parse_sse should accept a file path as well as raw text."""
    path = FIXTURE_DIR / "valid-thinking-stream.sse"
    result = parse_sse(str(path))
    assert result.event_types[-1] == "message_stop"
    assert result.errors == []
