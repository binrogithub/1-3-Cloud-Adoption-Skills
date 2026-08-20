#!/usr/bin/env python3
"""Unit tests for tool_argument_guard: schema extraction, JSON assembly,
validation, and limits (PRD §7, §8.2, §8.3). No live keys needed.

Run: python3 tests/test_tool_argument_guard.py
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("TOOL_ARG_GUARD_MODE", "enforce")

_TAG_PATH = Path(__file__).resolve().parents[1] / "litellm_plugins" / "tool_argument_guard" / "callback.py"
_tag_spec = importlib.util.spec_from_file_location("tag_callback", _TAG_PATH)
_tag_mod = importlib.util.module_from_spec(_tag_spec)
_tag_spec.loader.exec_module(_tag_mod)

SchemaMap = _tag_mod.SchemaMap
assemble_partial_json = _tag_mod.assemble_partial_json
build_schema_map = _tag_mod.build_schema_map
check_limits = _tag_mod.check_limits
is_available = _tag_mod.is_available
is_enforce = _tag_mod.is_enforce
normalize_arguments = _tag_mod.normalize_arguments
record_validation_failure = _tag_mod.record_validation_failure
validate_arguments = _tag_mod.validate_arguments
LimitExceeded = _tag_mod.LimitExceeded

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("%s: PASS" % name)
    else:
        FAIL += 1
        print("%s: FAIL" % name)


# ── jsonschema availability ─────────────────────────────────────────────────

check("jsonschema available", is_available())
check("enforce mode active", is_enforce())


# ── Schema extraction (PRD §7) ──────────────────────────────────────────────

# Anthropic form: {name, input_schema}
sm = build_schema_map({"tools": [
    {"name": "TaskCreate", "input_schema": {
        "type": "object",
        "properties": {"subject": {"type": "string"}, "description": {"type": "string"}},
        "required": ["subject"],
        "additionalProperties": False,
    }},
]})
check("anthropic form extracted", sm.has_tools)
check("anthropic form name found", sm.get("TaskCreate") is not None)
check("anthropic form hash set", len(sm.hash_of("TaskCreate")) == 16)

# OpenAI form: {type: function, function: {name, parameters}}
sm2 = build_schema_map({"tools": [
    {"type": "function", "function": {"name": "Bash", "parameters": {
        "type": "object", "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }}},
]})
check("openai form extracted", sm2.get("Bash") is not None)

# Alt form: {name, parameters}
sm3 = build_schema_map({"tools": [
    {"name": "Read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
]})
check("alt form extracted", sm3.get("Read") is not None)

# Empty / no tools
check("no tools -> empty map", not build_schema_map({}).has_tools)
check("non-dict request -> empty map", not build_schema_map(None).has_tools)
check("empty tools list -> empty map", not build_schema_map({"tools": []}).has_tools)

# Duplicate tool names with different schemas -> keep first, warn
sm4 = build_schema_map({"tools": [
    {"name": "X", "input_schema": {"type": "object"}},
    {"name": "X", "input_schema": {"type": "string"}},
]})
check("duplicate name keeps first", sm4.get("X") == {"type": "object"})

# Remote $ref rejected
sm5 = build_schema_map({"tools": [
    {"name": "Bad", "input_schema": {"$ref": "https://example.com/schema.json"}},
]})
check("remote $ref rejected", sm5.get("Bad") is None)

# Local $ref allowed
sm6 = build_schema_map({"tools": [
    {"name": "Good", "input_schema": {
        "definitions": {"item": {"type": "string"}},
        "$ref": "#/definitions/item",
    }},
]})
check("local $ref allowed", sm6.get("Good") is not None)

# Oversized schema rejected
big_schema = {"type": "object", "properties": {str(i): {"type": "string"} for i in range(20000)}}
sm7 = build_schema_map({"tools": [{"name": "Big", "input_schema": big_schema}]})
check("oversized schema rejected", sm7.get("Big") is None)


# ── JSON assembly (PRD §8.3) ────────────────────────────────────────────────

# Whole object in one fragment
obj, err = assemble_partial_json(['{"taskId":"t1","status":"pending"}'])
check("single fragment parse", obj == {"taskId": "t1", "status": "pending"} and err is None)

# Split across arbitrary boundaries
for split_at in range(1, 30):
    full = '{"taskId":"t1","status":"pending"}'
    frags = [full[:split_at], full[split_at:]]
    obj, err = assemble_partial_json(frags)
    assert obj == {"taskId": "t1", "status": "pending"}, (split_at, err)
check("split-across-boundaries parse", True)

# Multiple fragments
obj, err = assemble_partial_json(['{"task', 'Id":"', 't1"}'])
check("multi-fragment parse", obj == {"taskId": "t1"} and err is None)

# Malformed JSON -> error, no ad hoc repair
obj, err = assemble_partial_json(['{"taskId":'])
check("malformed json returns error", obj is None and err is not None)

# Truncated
obj, err = assemble_partial_json(['{"taskId":"t1"'])
check("truncated json returns error", obj is None and err is not None)

# Empty fragments
obj, err = assemble_partial_json([])
check("empty fragments -> error", obj is None and err is not None)


# ── Validation (PRD §8.3) ───────────────────────────────────────────────────

TASKUPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
    },
    "required": ["taskId", "status"],
    "additionalProperties": False,
}

# Valid
ok, errs = validate_arguments({"taskId": "t1", "status": "pending"}, TASKUPDATE_SCHEMA)
check("valid args pass", ok and errs == [])

# Missing required field
ok, errs = validate_arguments({"status": "pending"}, TASKUPDATE_SCHEMA)
check("missing required detected", not ok)
check("missing required keyword", any(e["keyword"] == "required" for e in errs))

# Wrong type (numeric taskId, schema requires string)
ok, errs = validate_arguments({"taskId": 1, "status": "pending"}, TASKUPDATE_SCHEMA)
check("wrong type detected", not ok)
check("wrong type keyword", any(e["keyword"] == "type" for e in errs))

# Invalid enum
ok, errs = validate_arguments({"taskId": "t1", "status": "done"}, TASKUPDATE_SCHEMA)
check("invalid enum detected", not ok)
check("enum keyword", any(e["keyword"] == "enum" for e in errs))

# Additional property (additionalProperties:false)
ok, errs = validate_arguments({"taskId": "t1", "status": "pending", "extra": 1}, TASKUPDATE_SCHEMA)
check("additional property detected", not ok)
check("additionalProperties keyword", any(e["keyword"] == "additionalProperties" for e in errs))

# Errors have redacted structure (keyword, path, schema_path, expected)
ok, errs = validate_arguments({"taskId": 1}, TASKUPDATE_SCHEMA)
check("error has keyword", all("keyword" in e for e in errs))
check("error has path", all("path" in e for e in errs))
check("error has schema_path", all("schema_path" in e for e in errs))
check("error has expected", all("expected" in e for e in errs))
# Path is classified, not raw
check("path is $-prefixed", all(e["path"].startswith("$") for e in errs))

# Root type not object when schema requires object
ok, errs = validate_arguments([], TASKUPDATE_SCHEMA)
check("non-object root rejected", not ok)

# Schema permitting non-object root
str_schema = {"type": "string"}
ok, errs = validate_arguments("hello", str_schema)
check("string root permitted by string schema", ok)

# record_validation_failure does not raise
record_validation_failure("TaskUpdate", "abc123", errs)


# ── Limits (PRD §8.2) ───────────────────────────────────────────────────────

# Within limits
try:
    check_limits(5, [100, 200, 300], 600)
    check("within limits ok", True)
except LimitExceeded:
    check("within limits ok", False)

# Too many calls
try:
    check_limits(100, [10], 10)
    check("too many calls raises", False)
except LimitExceeded as e:
    check("too many calls raises", e.limit == "tool_calls_per_message")

# Per-call bytes exceeded
try:
    check_limits(1, [100000], 100000)
    check("per-call bytes raises", False)
except LimitExceeded as e:
    check("per-call bytes raises", "arg_bytes_call_0" in e.limit)

# Total buffer bytes exceeded
try:
    check_limits(1, [10], 300000)
    check("total buffer bytes raises", False)
except LimitExceeded as e:
    check("total buffer bytes raises", e.limit == "total_buffer_bytes")


# ── Concurrent isolation: SchemaMap is request-scoped ───────────────────────

sm_a = build_schema_map({"tools": [{"name": "A", "input_schema": {"type": "object"}}]})
sm_b = build_schema_map({"tools": [{"name": "B", "input_schema": {"type": "string"}}]})
check("request A has A not B", sm_a.get("A") is not None and sm_a.get("B") is None)
check("request B has B not A", sm_b.get("B") is not None and sm_b.get("A") is None)


# ── Normalization: generic rules (PRD §9.1) ─────────────────────────────────

# R1: single wrapper removal {"input": {...}} -> {...}
r1_schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
norm, applied = normalize_arguments({"input": {"x": "hi"}}, r1_schema, "Test")
check("R1 wrapper removed", norm == {"x": "hi"} and "R1-wrapper" in applied)

# R1 not applied when inner doesn't validate
norm, applied = normalize_arguments({"input": {"y": 1}}, r1_schema, "Test")
check("R1 not applied when inner invalid", norm == {"input": {"y": 1}} and "R1-wrapper" not in applied)

# R1 not applied when more than one field
norm, applied = normalize_arguments({"input": {"x": "hi"}, "other": 1}, r1_schema, "Test")
check("R1 not applied with extra fields", "R1-wrapper" not in applied)

# R2: snake-to-camel task_id -> taskId
r2_schema = {
    "type": "object",
    "properties": {"taskId": {"type": "string"}, "status": {"type": "string"}},
    "required": ["taskId"],
    "additionalProperties": False,
}
norm, applied = normalize_arguments({"task_id": "t1", "status": "pending"}, r2_schema, "TaskUpdate")
check("R2 snake-to-camel", norm.get("taskId") == "t1" and "task_id" not in norm)
check("R2 rule recorded", "R2-snake-camel" in applied)

# R2 not applied when target already exists (no overwrite)
norm, applied = normalize_arguments({"task_id": "t1", "taskId": "t2"}, r2_schema, "TaskUpdate")
check("R2 no overwrite", norm.get("taskId") == "t2" and "task_id" in norm)

# R2 not applied when target not a schema property
r2b_schema = {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}
norm, applied = normalize_arguments({"task_id": "t1"}, r2b_schema, "Test")
check("R2 no target property", norm.get("task_id") == "t1")

# R3: int -> string (lossless)
r3_schema = {"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]}
norm, applied = normalize_arguments({"taskId": 42}, r3_schema, "TaskUpdate")
check("R3 int->string", norm["taskId"] == "42" and "R3-primitive-coerce" in applied)

# R3: digit-only string -> int (round trip identical)
r3b_schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
norm, applied = normalize_arguments({"count": "42"}, r3b_schema, "Test")
check("R3 string->int", norm["count"] == 42 and "R3-primitive-coerce" in applied)

# R3: non-digit string NOT coerced to int
norm, applied = normalize_arguments({"count": "4.2"}, r3b_schema, "Test")
check("R3 non-digit not coerced", norm["count"] == "4.2")

# R3: bool not coerced (isinstance(True, int) is True but we exclude bool)
r3c_schema = {"type": "object", "properties": {"flag": {"type": "string"}}}
norm, applied = normalize_arguments({"flag": True}, r3c_schema, "Test")
check("R3 bool not coerced to string", norm["flag"] is True)

# R4: schema defaults inserted
r4_schema = {
    "type": "object",
    "properties": {"x": {"type": "string"}, "y": {"type": "string", "default": "def"}},
    "required": ["x"],
}
norm, applied = normalize_arguments({"x": "hi"}, r4_schema, "Test")
check("R4 default inserted", norm.get("y") == "def" and "R4-schema-defaults" in applied)

# R4: existing value not overwritten by default
norm, applied = normalize_arguments({"x": "hi", "y": "custom"}, r4_schema, "Test")
check("R4 no overwrite existing", norm.get("y") == "custom")

# R5: unknown fields removed when additionalProperties:false
r5_schema = {
    "type": "object",
    "properties": {"x": {"type": "string"}},
    "required": ["x"],
    "additionalProperties": False,
}
norm, applied = normalize_arguments({"x": "hi", "junk": 1}, r5_schema, "Test")
check("R5 unknown removed", "junk" not in norm and "R5-remove-unknown" in applied)

# R5: unknown alias candidate NOT removed (R2 handles it)
r5b_schema = {
    "type": "object",
    "properties": {"taskId": {"type": "string"}},
    "required": ["taskId"],
    "additionalProperties": False,
}
norm, applied = normalize_arguments({"task_id": "t1"}, r5b_schema, "TaskUpdate")
check("R5 alias candidate not removed", norm.get("taskId") == "t1")

# R5: not applied when additionalProperties not false
r5c_schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
norm, applied = normalize_arguments({"x": "hi", "junk": 1}, r5c_schema, "Test")
check("R5 not applied without additionalProperties:false", "junk" in norm)

# R6: null -> {} when schema permits empty object with no required
r6_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
norm, applied = normalize_arguments(None, r6_schema, "TaskList")
check("R6 null->empty", norm == {} and "R6-null-empty" in applied)

# R6: null NOT normalized when schema has required fields
r6b_schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
norm, applied = normalize_arguments(None, r6b_schema, "TaskList")
check("R6 null not normalized with required", norm is None and "R6-null-empty" not in applied)


# ── Normalization: Todo/Task rules (PRD §9.2) ───────────────────────────────

# RT: status enum mapping todo->pending, doing->in_progress, done->completed
status_schema = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
    },
    "required": ["taskId", "status"],
    "additionalProperties": False,
}
for src, dst in [("todo", "pending"), ("doing", "in_progress"), ("done", "completed")]:
    norm, applied = normalize_arguments({"taskId": "t1", "status": src}, status_schema, "TaskUpdate")
    check("RT status %s->%s" % (src, dst), norm["status"] == dst)

# RT: status enum NOT mapped when target not in schema enum
restricted_schema = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["open", "closed"]},
    },
    "required": ["taskId", "status"],
}
norm, applied = normalize_arguments({"taskId": "t1", "status": "done"}, restricted_schema, "TaskUpdate")
check("RT status not mapped when enum lacks target", norm["status"] == "done")

# RT: TodoWrite activeForm copied from content
todowrite_schema = {
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "activeForm": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["content", "activeForm", "status"],
            },
        },
    },
    "required": ["todos"],
}
norm, applied = normalize_arguments(
    {"todos": [{"content": "Running tests", "activeForm": "", "status": "in_progress"}]},
    todowrite_schema, "TodoWrite",
)
check("RT activeForm copied from content", norm["todos"][0]["activeForm"] == "Running tests")
check("RT activeForm rule recorded", "RT-todowrite-activeform" in applied)

# RT: activeForm NOT copied when content is empty (no source value)
norm, applied = normalize_arguments(
    {"todos": [{"content": "", "activeForm": "", "status": "in_progress"}]},
    todowrite_schema, "TodoWrite",
)
check("RT activeForm not copied from empty content", norm["todos"][0]["activeForm"] == "")

# RT: activeForm NOT touched when already present
norm, applied = normalize_arguments(
    {"todos": [{"content": "Running tests", "activeForm": "Testing", "status": "in_progress"}]},
    todowrite_schema, "TodoWrite",
)
check("RT activeForm not overwritten", norm["todos"][0]["activeForm"] == "Testing")

# RT: activeForm rule not applied for non-TodoWrite tools
norm, applied = normalize_arguments(
    {"todos": [{"content": "x", "activeForm": "", "status": "in_progress"}]},
    todowrite_schema, "TaskUpdate",
)
check("RT activeForm not applied for non-TodoWrite", "RT-todowrite-activeform" not in applied)


# ── Normalization: combined + revalidation ──────────────────────────────────

# Full pipeline: task_id -> taskId + numeric->string + status done->completed
combined_schema = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
    },
    "required": ["taskId", "status"],
    "additionalProperties": False,
}
norm, applied = normalize_arguments({"task_id": 1, "status": "done"}, combined_schema, "TaskUpdate")
ok, errs = validate_arguments(norm, combined_schema)
check("combined normalization valid", ok)
check("combined taskId string", norm["taskId"] == "1")
check("combined status completed", norm["status"] == "completed")
check("combined no task_id", "task_id" not in norm)

# Refusal: missing semantic field with no source (PRD §9.2 — never invent)
# TaskUpdate missing taskId entirely — normalization cannot synthesize it
norm, applied = normalize_arguments({"status": "done"}, combined_schema, "TaskUpdate")
ok, errs = validate_arguments(norm, combined_schema)
check("missing semantic field not synthesized", not ok)
check("missing taskId still missing", "taskId" not in norm)


# ── Startup validation (PRD §7.2) ───────────────────────────────────────────

# The loaded module is in enforce mode with jsonschema available — startup OK.
check("startup validation passes for enforce+jsonschema", True)  # import succeeded


def test_startup_rejects_unknown_mode():
    """PRD §7.2: an unknown TOOL_ARG_GUARD_MODE must prevent startup."""
    import tempfile
    # Reload the module with a bad mode env var.
    old_mode = os.environ.get("TOOL_ARG_GUARD_MODE")
    os.environ["TOOL_ARG_GUARD_MODE"] = "invalid-mode"
    try:
        spec = importlib.util.spec_from_file_location("tag_bad_mode", _TAG_PATH)
        mod = importlib.util.module_from_spec(spec)
        raised = False
        try:
            spec.loader.exec_module(mod)
        except RuntimeError as e:
            raised = True
            assert "invalid" in str(e).lower() or "TOOL_ARG_GUARD_MODE" in str(e)
        assert raised, "unknown mode must prevent startup (raise RuntimeError)"
    finally:
        if old_mode is not None:
            os.environ["TOOL_ARG_GUARD_MODE"] = old_mode
        else:
            os.environ.pop("TOOL_ARG_GUARD_MODE", None)


def test_startup_accepts_known_modes():
    """PRD §7.2: off, observe, and enforce are valid modes."""
    for mode in ("off", "observe", "enforce"):
        old_mode = os.environ.get("TOOL_ARG_GUARD_MODE")
        os.environ["TOOL_ARG_GUARD_MODE"] = mode
        try:
            spec = importlib.util.spec_from_file_location("tag_mode_%s" % mode, _TAG_PATH)
            mod = importlib.util.module_from_spec(spec)
            # enforce requires jsonschema; if not available it raises (tested elsewhere).
            # off and observe should always import cleanly.
            if mode == "enforce" and not _tag_mod.is_available():
                # jsonschema unavailable — enforce must raise (expected in minimal envs).
                raised = False
                try:
                    spec.loader.exec_module(mod)
                except RuntimeError:
                    raised = True
                assert raised, "enforce without jsonschema must raise"
            else:
                spec.loader.exec_module(mod)
                assert mod.MODE == mode
        finally:
            if old_mode is not None:
                os.environ["TOOL_ARG_GUARD_MODE"] = old_mode
            else:
                os.environ.pop("TOOL_ARG_GUARD_MODE", None)


def test_all_checks_pass():
    """Pytest entry point: assert every module-level check() succeeded."""
    assert FAIL == 0, "%d checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
