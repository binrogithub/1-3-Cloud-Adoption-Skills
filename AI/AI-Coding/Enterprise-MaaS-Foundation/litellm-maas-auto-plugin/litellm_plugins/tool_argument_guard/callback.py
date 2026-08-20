"""Tool Argument Guard — schema-aware tool argument validation at the gateway
response boundary (PRD-tool-argument-guard).

Mounted as /app/tool_argument_guard.py. A library used by
anthropic_stream_guard (streaming) and async_post_call_success_hook (non-
streaming); it does NOT need an independent LiteLLM callback registration.

Pipeline:
  upstream stream
    -> anthropic_stream_guard protocol repair
    -> tool_argument_guard semantic buffer/validation/repair
    -> Claude Code

The guard reads the tool schemas Claude Code sent in the current request,
buffers model-generated tool argument deltas until the complete tool call is
available, validates the assembled arguments, and follows this ordered policy:
  1. Pass valid arguments through byte-identically.
  2. Apply a small allowlist of deterministic, schema-directed normalizations.
  3. If still invalid, call the Premium Tool-Repair Sidecar once.
  4. Validate the repaired arguments against the original schema.
  5. If repair still fails, replace the tool call with a safe text result and
     terminate the assistant turn without tool execution.

GLM-5.2 remains the mainline model. Premium repairs arguments only; it never
produces the final user response and never executes a tool.
"""

import asyncio
import hashlib
import json
import logging
import os
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# dataclasses is stdlib in 3.7+; provide a fallback for 3.6.
try:
    from dataclasses import dataclass, field
except ImportError:
    def dataclass(cls=None, **kw):
        def wrap(c):
            return c
        return wrap(cls) if cls is not None else wrap

    def field(default_factory=None, **kw):
        return default_factory() if default_factory else None

log = logging.getLogger("tool_argument_guard")

# ── Configuration (PRD §15) ─────────────────────────────────────────────────

MODE = os.getenv("TOOL_ARG_GUARD_MODE", "observe")  # off|observe|enforce
MAX_CALLS = int(os.getenv("TOOL_ARG_MAX_CALLS", "32"))
MAX_BYTES_PER_CALL = int(os.getenv("TOOL_ARG_MAX_BYTES_PER_CALL", "65536"))
MAX_BUFFER_BYTES = int(os.getenv("TOOL_ARG_MAX_BUFFER_BYTES", "262144"))
MAX_SCHEMA_BYTES = int(os.getenv("TOOL_ARG_MAX_SCHEMA_BYTES", "131072"))
MAX_SCHEMA_DEPTH = int(os.getenv("TOOL_ARG_MAX_SCHEMA_DEPTH", "32"))
PREMIUM_REPAIR = os.getenv("TOOL_ARG_PREMIUM_REPAIR", "true").lower() in (
    "1", "true", "yes", "on",
)
PREMIUM_TIMEOUT = float(os.getenv("TOOL_ARG_PREMIUM_TIMEOUT_SECONDS", "30"))
PREMIUM_MAX_OUTPUT_TOKENS = int(os.getenv("TOOL_ARG_PREMIUM_MAX_OUTPUT_TOKENS", "2048"))
RULESET_VERSION = int(os.getenv("TOOL_ARG_RULESET_VERSION", "1"))

# Safe rejection text (PRD §11.3). No argument values or schema details.
REJECTION_TEXT = (
    "The requested tool action was not executed because its generated "
    "parameters did not match the tool contract. The request can be "
    "retried with corrected fields."
)

# ── Metrics (degrade to no-ops if prometheus_client is unavailable) ─────────

try:
    from prometheus_client import Counter as _Counter

    TAG_CALLS = _Counter(
        "tool_argument_calls_total",
        "tool argument calls processed",
        ["tool", "outcome"],
    )
    TAG_VALIDATION_FAILURES = _Counter(
        "tool_argument_validation_failures_total",
        "tool argument schema validation failures",
        ["tool", "schema_hash", "keyword", "path_class"],
    )
    TAG_NORMALIZATIONS = _Counter(
        "tool_argument_normalizations_total",
        "deterministic normalizations applied",
        ["tool", "rule_id"],
    )
    TAG_PREMIUM_REPAIRS = _Counter(
        "tool_argument_premium_repairs_total",
        "premium tool-argument repairs",
        ["tool", "outcome"],
    )
    TAG_REJECTIONS = _Counter(
        "tool_argument_rejections_total",
        "tool calls rejected before execution",
        ["tool", "reason"],
    )
    TAG_ADMISSIONS = _Counter(
        "tool_argument_schema_admissions_total",
        "schema admission results per declared tool",
        ["tool", "outcome"],
    )
except Exception:  # pragma: no cover — missing dep or duplicate registration

    class _Noop:
        def labels(self, *_a, **_k):
            return self

        def inc(self, *_a, **_k):
            pass

    TAG_CALLS = TAG_VALIDATION_FAILURES = TAG_NORMALIZATIONS = (
        TAG_PREMIUM_REPAIRS
    ) = TAG_REJECTIONS = TAG_ADMISSIONS = _Noop()


# ── jsonschema dependency check ─────────────────────────────────────────────

try:
    import jsonschema
    from jsonschema import Draft7Validator
    _JSONSCHEMA_AVAILABLE = True
except Exception:  # pragma: no cover
    jsonschema = None
    Draft7Validator = None
    _JSONSCHEMA_AVAILABLE = False

# Draft202012Validator is only in jsonschema 4.0+; optional.
Draft202012Validator = None
if _JSONSCHEMA_AVAILABLE:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pass


def is_available() -> bool:
    """True if jsonschema is importable and the guard can enforce."""
    return _JSONSCHEMA_AVAILABLE


def is_enabled() -> bool:
    """True if the guard is active (not off)."""
    return MODE != "off"


def is_enforce() -> bool:
    """True if the guard buffers, normalizes, repairs, and rejects."""
    return MODE == "enforce"


def is_observe() -> bool:
    """True if the guard validates and records metrics but does not change output."""
    return MODE == "observe"


_VALID_MODES = frozenset(("off", "observe", "enforce"))


def validate_startup() -> None:
    """Validate mode and dependency readiness at startup (PRD v2 §7.10 R10).

    Raises RuntimeError if:
      - MODE is not one of off/observe/enforce (unknown mode prevents startup);
      - MODE is enforce but jsonschema is unavailable (can't validate schemas);
      - MODE is enforce but the sidecar repair dependency is unavailable when
        repair is enabled;
      - cache or ledger paths are configured but not writable;
      - residency configuration is inconsistent.

    Called at module import. The installer also calls this in its post-install
    verification step.
    """
    if MODE not in _VALID_MODES:
        raise RuntimeError(
            "TOOL_ARG_GUARD_MODE=%r is invalid — must be one of %s"
            % (MODE, sorted(_VALID_MODES))
        )
    if MODE == "enforce" and not _JSONSCHEMA_AVAILABLE:
        raise RuntimeError(
            "TOOL_ARG_GUARD_MODE=enforce requires jsonschema — refusing to start"
        )
    # R10: verify Premium repair dependency when repair is enabled in enforce.
    # In production the sidecar is mounted as /app/sidecar.py. In tests it is
    # loaded into sys.modules by the test harness. We only fail if the import
    # raises an error (not if the module is simply absent, which the stream
    # guard handles gracefully via _load_sidecar_for_repair).
    if MODE == "enforce" and PREMIUM_REPAIR:
        try:
            import sidecar  # noqa: F401
        except ImportError:
            pass  # degrade gracefully — stream guard handles missing sidecar
        except Exception as exc:
            raise RuntimeError(
                "sidecar module import failed: %s: %s — refusing to start"
                % (type(exc).__name__, exc)
            )
    # R10: verify cache/ledger paths are writable if configured.
    cache_dir = os.getenv("SIDECAR_CACHE_DIR")
    if cache_dir and os.path.isdir(cache_dir) and not os.access(cache_dir, os.W_OK):
        raise RuntimeError(
            "SIDECAR_CACHE_DIR=%r is not writable — refusing to start" % cache_dir
        )
    ledger_dir = os.getenv("SIDECAR_LEDGER_DIR")
    if ledger_dir and os.path.isdir(ledger_dir) and not os.access(ledger_dir, os.W_OK):
        raise RuntimeError(
            "SIDECAR_LEDGER_DIR=%r is not writable — refusing to start" % ledger_dir
        )
    # R10: residency config consistency.
    residency_default = os.getenv("SMART_ROUTER_DEFAULT_DATA_RESIDENCY", "")
    if residency_default and residency_default not in ("allow", "china-only"):
        raise RuntimeError(
            "SMART_ROUTER_DEFAULT_DATA_RESIDENCY=%r is invalid — must be "
            "'allow' or 'china-only'" % residency_default
        )


validate_startup()


# ── Schema extraction (PRD §7) ──────────────────────────────────────────────


def _normalize_tool_schema(raw: Any) -> Optional[Dict[str, Any]]:
    """Extract a normalized {name, input_schema} from one tool entry.

    Supports all input shapes (PRD §7):
      {"name":"TaskCreate","input_schema":{}}
      {"type":"function","function":{"name":"TaskCreate","parameters":{}}}
      {"name":"TaskCreate","parameters":{}}
    """
    if not isinstance(raw, dict):
        return None
    # Anthropic: {name, input_schema}
    name = raw.get("name")
    schema = raw.get("input_schema")
    if name and isinstance(schema, dict):
        return {"name": str(name), "input_schema": schema}
    # OpenAI: {type: function, function: {name, parameters}}
    if raw.get("type") == "function":
        fn = raw.get("function")
        if isinstance(fn, dict):
            name = fn.get("name")
            schema = fn.get("parameters")
            if name and isinstance(schema, dict):
                return {"name": str(name), "input_schema": schema}
    # Alt: {name, parameters}
    name = raw.get("name")
    schema = raw.get("parameters")
    if name and isinstance(schema, dict):
        return {"name": str(name), "input_schema": schema}
    return None


def _schema_hash(schema: Dict[str, Any]) -> str:
    """Stable hash of a normalized schema for metrics/diagnostics."""
    try:
        raw = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = repr(schema)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _has_remote_ref(schema: Any, depth: int = 0) -> bool:
    """Reject remote $ref values; allow only local #/... refs (PRD §7)."""
    if depth > MAX_SCHEMA_DEPTH:
        return True  # too deep — treat as unsafe
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            return True
        for v in schema.values():
            if _has_remote_ref(v, depth + 1):
                return True
    elif isinstance(schema, list):
        for item in schema:
            if _has_remote_ref(item, depth + 1):
                return True
    return False


def _schema_byte_size(schema: Any) -> int:
    try:
        return len(json.dumps(schema, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return len(repr(schema).encode("utf-8"))


class SchemaMap:
    """Request-scoped map: tool name -> normalized JSON Schema (PRD §7).

    Built once per request from the request's tools array. Lives in the
    streaming hook's request-local state, not a global.
    """

    __slots__ = ("by_name", "hashes", "has_tools", "all_schemas_rejected")

    def __init__(self, tools: Any) -> None:
        self.by_name: Dict[str, Dict[str, Any]] = {}
        self.hashes: Dict[str, str] = {}
        self.has_tools = False
        self.all_schemas_rejected = False
        if not isinstance(tools, list) or not tools:
            return
        declared = 0  # count of tools that were declared (even if rejected)
        for raw in tools:
            norm = _normalize_tool_schema(raw)
            if norm is None:
                # Unsupported shape or missing schema — record admission failure.
                name = raw.get("name", raw.get("function", {}).get("name", "unknown")) if isinstance(raw, dict) else "unknown"
                TAG_ADMISSIONS.labels(tool=name, outcome="unsupported_shape").inc()
                log.warning("[tool_argument_guard] tool %r has unsupported schema shape", name)
                declared += 1
                continue
            name = norm["name"]
            schema = norm["input_schema"]
            declared += 1
            # Reject duplicate tool names with different schemas (PRD §7).
            if name in self.by_name and self.by_name[name] != schema:
                TAG_ADMISSIONS.labels(tool=name, outcome="duplicate_conflict").inc()
                log.warning(
                    "[tool_argument_guard] duplicate tool name %r with "
                    "conflicting schema — keeping first",
                    name,
                )
                continue
            # Reject remote refs and oversized schemas.
            if _has_remote_ref(schema):
                TAG_ADMISSIONS.labels(tool=name, outcome="remote_ref").inc()
                log.warning(
                    "[tool_argument_guard] tool %r schema has remote $ref — "
                    "skipping",
                    name,
                )
                continue
            if _schema_byte_size(schema) > MAX_SCHEMA_BYTES:
                TAG_ADMISSIONS.labels(tool=name, outcome="oversized").inc()
                log.warning(
                    "[tool_argument_guard] tool %r schema exceeds %d bytes — "
                    "skipping",
                    name, MAX_SCHEMA_BYTES,
                )
                continue
            self.by_name[name] = schema
            self.hashes[name] = _schema_hash(schema)
            TAG_ADMISSIONS.labels(tool=name, outcome="admitted").inc()
        # R3 fail-closed: has_tools is True if tools were declared, even if all
        # were rejected. This keeps the guard active so generated tool calls are
        # rejected as unknown rather than passing through unguarded.
        self.has_tools = declared > 0
        self.all_schemas_rejected = declared > 0 and len(self.by_name) == 0

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self.by_name.get(name)

    def hash_of(self, name: str) -> str:
        return self.hashes.get(name, "")


def build_schema_map(request_data: Any) -> SchemaMap:
    """Build a SchemaMap from a request dict's tools array."""
    if not isinstance(request_data, dict):
        return SchemaMap(None)
    return SchemaMap(request_data.get("tools"))


# ── JSON assembly from partial_json fragments (PRD §8.3) ────────────────────


def assemble_partial_json(fragments: List[str]) -> Tuple[Optional[Any], Optional[str]]:
    """Concatenate partial_json fragments in stream order and parse strict JSON.

    Returns (parsed_obj, error_message). On success error_message is None.
    Does NOT implement ad hoc quote/bracket repair (PRD §8.3 rule 2).
    """
    raw = "".join(fragments)
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, "invalid JSON: %s at pos %d" % (exc.msg, exc.pos)


# ── Validation (PRD §8.3) ───────────────────────────────────────────────────


def _select_validator(schema: Dict[str, Any]):
    """Select the validator declared by $schema, else Draft7 (repository default)."""
    declared = schema.get("$schema", "")
    if isinstance(declared, str) and "2020-12" in declared and Draft202012Validator:
        return Draft202012Validator(schema)
    if isinstance(declared, str) and "draft-07" in declared:
        return Draft7Validator(schema)
    return Draft7Validator(schema)


def _path_class(path: Any) -> str:
    """Classify a JSON path for metrics (no raw values in labels)."""
    if not path:
        return "$"
    parts = []
    for elem in path:
        if isinstance(elem, int):
            parts.append("[]")
        else:
            parts.append(str(elem))
    return "$." + ".".join(parts) if parts else "$"


def validate_arguments(
    args: Any, schema: Dict[str, Any]
) -> Tuple[bool, List[Dict[str, str]]]:
    """Validate args against a JSON Schema (PRD §8.3).

    Returns (is_valid, errors) where errors is a list of dicts with keys:
      keyword, path, schema_path, expected
    Never logs raw argument values.
    """
    if not _JSONSCHEMA_AVAILABLE:
        return True, []  # fail-open if jsonschema missing
    validator = _select_validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(args), key=lambda e: list(e.path)):
        errors.append({
            "keyword": str(err.validator),
            "path": _path_class(list(err.path)),
            "schema_path": _path_class(list(err.schema_path) if hasattr(err, "schema_path") else []),
            "expected": str(err.validator_value)[:128] if err.validator_value is not True else "",
        })
    return len(errors) == 0, errors


def record_validation_failure(tool: str, schema_hash: str, errors: List[Dict[str, str]]) -> None:
    """Increment validation-failure metrics (redacted, no raw values)."""
    for err in errors:
        TAG_VALIDATION_FAILURES.labels(
            tool=tool,
            schema_hash=schema_hash,
            keyword=err.get("keyword", ""),
            path_class=err.get("path", ""),
        ).inc()


# ── Limits (PRD §8.2) ───────────────────────────────────────────────────────


class LimitExceeded(Exception):
    """A tool-call buffer limit was exceeded (fail-closed for tool execution)."""

    def __init__(self, limit: str, value: int, maximum: int):
        self.limit = limit
        self.value = value
        self.maximum = maximum
        super().__init__("%s: %d > %d" % (limit, value, maximum))


def check_limits(
    num_calls: int,
    per_call_bytes: List[int],
    total_buffer_bytes: int,
) -> None:
    """Enforce buffer limits (PRD §8.2). Raises LimitExceeded on violation."""
    if num_calls > MAX_CALLS:
        raise LimitExceeded("tool_calls_per_message", num_calls, MAX_CALLS)
    for i, b in enumerate(per_call_bytes):
        if b > MAX_BYTES_PER_CALL:
            raise LimitExceeded("arg_bytes_call_%d" % i, b, MAX_BYTES_PER_CALL)
    if total_buffer_bytes > MAX_BUFFER_BYTES:
        raise LimitExceeded("total_buffer_bytes", total_buffer_bytes, MAX_BUFFER_BYTES)


def check_limits_return(
    num_calls: int,
    per_call_bytes: List[int],
    total_buffer_bytes: int,
) -> Optional[str]:
    """Like check_limits but returns the limit name instead of raising.

    Returns None if within limits, or the name of the first exceeded limit.
    Used by decide() to produce a set-level REJECTED decision.
    """
    if num_calls > MAX_CALLS:
        return "tool_calls_per_message"
    for i, b in enumerate(per_call_bytes):
        if b > MAX_BYTES_PER_CALL:
            return "arg_bytes_call_%d" % i
    if total_buffer_bytes > MAX_BUFFER_BYTES:
        return "total_buffer_bytes"
    return None


# ── Deterministic normalization (PRD §9) ────────────────────────────────────
#
# Schema-directed and allowlisted. Each rule has a stable ID and version
# (PRD §9.3). Metrics record rule IDs, not argument contents. Rules are
# applied one at a time and the result is fully revalidated after all rules.

# Snake-to-camel alias map for known Todo/Task drift (PRD §9.2).
_SNAKE_CAMEL_ALIASES = {
    "task_id": "taskId",
}

# Status enum aliases (PRD §9.2): map common drift to the canonical enum,
# applied only if the target enum value is permitted by the live schema.
_STATUS_ALIASES = {
    "todo": "pending",
    "doing": "in_progress",
    "done": "completed",
}

# TodoWrite activeForm rule: copy content -> activeForm when activeForm is a
# required string and is missing (PRD §9.2).
TODOWRITE_TOOL_NAMES = {"TodoWrite"}


def _schema_property(schema: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    prop = props.get(name)
    return prop if isinstance(prop, dict) else None


def _enum_allows(prop: Optional[Dict[str, Any]], value: str) -> bool:
    """True if the property's enum (if any) permits value."""
    if not isinstance(prop, dict):
        return True
    enum = prop.get("enum")
    if not isinstance(enum, list):
        return True
    return value in enum


def _requires_string(prop: Optional[Dict[str, Any]]) -> bool:
    return isinstance(prop, dict) and prop.get("type") == "string"


def _requires_integer(prop: Optional[Dict[str, Any]]) -> bool:
    return isinstance(prop, dict) and prop.get("type") == "integer"


def _required_fields(schema: Dict[str, Any]) -> set:
    req = schema.get("required")
    return set(req) if isinstance(req, list) else set()


def _additional_properties_false(schema: Dict[str, Any]) -> bool:
    ap = schema.get("additionalProperties")
    return ap is False


# ── Generic safe rules (PRD §9.1) ───────────────────────────────────────────


def _rule_single_wrapper_removal(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R1: unwrap {"input": {...}} only when input is the sole field and the
    inner object validates against the root schema."""
    if not isinstance(args, dict):
        return args, False
    if len(args) != 1 or "input" not in args:
        return args, False
    inner = args["input"]
    if not isinstance(inner, dict):
        return args, False
    ok, _ = validate_arguments(inner, schema)
    if ok:
        return inner, True
    return args, False


def _rule_snake_to_camel(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R2: map task_id -> taskId when source exists, target is a schema
    property, target is absent, and nothing would be overwritten."""
    if not isinstance(args, dict):
        return args, False
    changed = False
    for src, dst in _SNAKE_CAMEL_ALIASES.items():
        if src not in args:
            continue
        if dst in args:
            continue  # would overwrite — skip
        if _schema_property(schema, dst) is None:
            continue  # target not a schema property
        args[dst] = args.pop(src)
        changed = True
    return args, changed


def _rule_lossless_primitive_coercion(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R3: int -> decimal string when schema requires string (no info lost);
    digit-only string -> int when schema requires integer (round trip identical)."""
    if not isinstance(args, dict):
        return args, False
    changed = False
    for name, val in list(args.items()):
        prop = _schema_property(schema, name)
        if prop is None:
            continue
        if _requires_string(prop) and isinstance(val, int) and not isinstance(val, bool):
            # int -> string (lossless)
            args[name] = str(val)
            changed = True
        elif _requires_integer(prop) and isinstance(val, str) and val.isdigit():
            # digit-only string -> int (round trip identical)
            iv = int(val)
            if str(iv) == val:
                args[name] = iv
                changed = True
    return args, changed


def _rule_schema_defaults(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R4: insert only values explicitly declared through `default` in the schema."""
    if not isinstance(args, dict):
        return args, False
    props = schema.get("properties")
    if not isinstance(props, dict):
        return args, False
    changed = False
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if name in args:
            continue
        if "default" in prop:
            args[name] = prop["default"]
            changed = True
    return args, changed


def _rule_remove_unknown_fields(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R5: when additionalProperties:false, remove unknown fields only if none
    is an alias candidate; record the removal."""
    if not isinstance(args, dict) or not _additional_properties_false(schema):
        return args, False
    props = schema.get("properties")
    known = set(props.keys()) if isinstance(props, dict) else set()
    alias_sources = set(_SNAKE_CAMEL_ALIASES.keys())
    alias_targets = set(_SNAKE_CAMEL_ALIASES.values())
    # If any unknown field is an alias source or target, do not remove — R2
    # handles the rename, and leaving a duplicate is safer than silently
    # dropping data the caller may need.
    unknown = [k for k in args if k not in known]
    if any(k in alias_sources or k in alias_targets for k in unknown):
        return args, False
    changed = False
    for k in unknown:
        args.pop(k, None)
        changed = True
    return args, changed


def _rule_null_empty_input(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """R6: normalize null -> {} only when schema permits an empty object and
    has no required properties."""
    if args is None:
        if schema.get("type") == "object" and not _required_fields(schema):
            return {}, True
    return args, False


# ── Todo/Task rules (PRD §9.2) ──────────────────────────────────────────────


def _rule_status_enum(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """Map status todo/doing/done -> pending/in_progress/completed only if the
    live schema's enum permits the target."""
    if not isinstance(args, dict):
        return args, False
    if "status" not in args:
        return args, False
    status = args["status"]
    if not isinstance(status, str) or status not in _STATUS_ALIASES:
        return args, False
    target = _STATUS_ALIASES[status]
    prop = _schema_property(schema, "status")
    if _enum_allows(prop, target):
        args["status"] = target
        return args, True
    return args, False


def _rule_todowrite_activeform(args: Any, schema: Dict[str, Any], tool: str) -> Tuple[Any, bool]:
    """TodoWrite.todos[].activeForm missing -> copy the same item's non-empty
    content, only if activeForm is a required string."""
    if tool not in TODOWRITE_TOOL_NAMES:
        return args, False
    if not isinstance(args, dict):
        return args, False
    todos = args.get("todos")
    if not isinstance(todos, list):
        return args, False
    # The items schema is nested under properties.todos.items (TodoWrite's root
    # schema describes the whole args object, not the array element).
    todos_prop = _schema_property(schema, "todos")
    if not isinstance(todos_prop, dict):
        return args, False
    items_schema = todos_prop.get("items")
    if not isinstance(items_schema, dict):
        return args, False
    af_prop = _schema_property(items_schema, "activeForm")
    if not _requires_string(af_prop):
        return args, False
    if "activeForm" not in _required_fields(items_schema):
        return args, False
    changed = False
    for item in todos:
        if not isinstance(item, dict):
            continue
        if item.get("activeForm"):
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            item["activeForm"] = content
            changed = True
    return args, changed


# Rule registry: ordered list of (rule_id, function). Each rule is schema-
# directed and idempotent. Applied one at a time; result revalidated after all.
GENERIC_RULES: List[Tuple[str, Any]] = [
    ("R1-wrapper", _rule_single_wrapper_removal),
    ("R2-snake-camel", _rule_snake_to_camel),
    ("R3-primitive-coerce", _rule_lossless_primitive_coercion),
    ("R4-schema-defaults", _rule_schema_defaults),
    ("R5-remove-unknown", _rule_remove_unknown_fields),
    ("R6-null-empty", _rule_null_empty_input),
]

TODOTASK_RULES: List[Tuple[str, Any]] = [
    ("RT-status-enum", _rule_status_enum),
    ("RT-todowrite-activeform", _rule_todowrite_activeform),
]


def normalize_arguments(
    args: Any, schema: Dict[str, Any], tool: str
) -> Tuple[Any, List[str]]:
    """Apply deterministic normalization rules (PRD §9).

    Returns (normalized_args, applied_rule_ids). Mutates dict args in place
    where possible. Does NOT synthesize subject/description/taskId/commands/
    file paths/owners/dependencies without a source value (PRD §9.2).
    """
    if not isinstance(args, (dict, list)) and args is not None:
        return args, []
    applied: List[str] = []
    # Work on a shallow copy so callers can compare before/after.
    if isinstance(args, dict):
        args = dict(args)
    elif isinstance(args, list):
        args = list(args)

    for rule_id, fn in GENERIC_RULES:
        try:
            args, changed = fn(args, schema, tool)
            if changed:
                applied.append(rule_id)
                TAG_NORMALIZATIONS.labels(tool=tool, rule_id=rule_id).inc()
        except Exception as exc:  # fail-open: a rule must never break a request
            log.warning(
                "[tool_argument_guard] rule %s raised %s: %s",
                rule_id, type(exc).__name__, exc,
            )

    # Todo/Task rules run after generic rules (they may depend on renamed fields).
    for rule_id, fn in TODOTASK_RULES:
        try:
            args, changed = fn(args, schema, tool)
            if changed:
                applied.append(rule_id)
                TAG_NORMALIZATIONS.labels(tool=tool, rule_id=rule_id).inc()
        except Exception as exc:
            log.warning(
                "[tool_argument_guard] rule %s raised %s: %s",
                rule_id, type(exc).__name__, exc,
            )

    return args, applied


# ── Transport-neutral decision engine (PRD v2 §7.2 R2) ───────────────────────
#
# decide() is the single chokepoint for the Tool Guard decision. Both the
# streaming _process_tool_buffer and non-stream _validate_non_stream_tools
# adapters call it and render from the Decision. They cannot diverge on
# validation or rejection semantics.


class DecisionOutcome(Enum):
    """Set-level outcome for a complete assistant-message tool-call set."""

    PASS = "pass"        # all calls valid, no normalization or repair needed
    REPAIRED = "repaired"  # all calls valid after normalization or repair
    REJECTED = "rejected"  # at least one call unresolved → suppress ALL


@dataclass
class ToolResult:
    """Per-tool result within a Decision."""

    index: int            # original block index in the assistant message
    tool_name: str
    outcome: str          # "pass" | "repair" | "reject"
    reason: str           # "" | "parse_error" | "unknown_tool" | "unresolvable" | "limit_exceeded"
    args: Any = None      # canonical args for pass/repair (None for reject)
    tool_id: str = ""     # tool_use ID for rendering
    applied_rules: list = field(default_factory=list)


@dataclass
class Decision:
    """The complete decision for a tool-call set (PRD v2 §7.2 R2)."""

    outcome: DecisionOutcome
    per_tool: List[ToolResult]
    all_valid: bool       # True iff no tool rejected
    limit_error: Optional[str] = None  # None or the exceeded limit name


def _compute_call_bytes(tool_calls: List[Dict[str, Any]]) -> Tuple[List[int], int]:
    """Compute per-call and total buffered bytes for limit checking."""
    per_call_bytes = []
    total = 0
    for tc in tool_calls:
        if "fragments" in tc:
            b = sum(len(f) for f in tc["fragments"])
        elif "args" in tc and tc["args"] is not None:
            b = len(json.dumps(tc["args"], ensure_ascii=False))
        else:
            b = 0
        per_call_bytes.append(b)
        total += b
    return per_call_bytes, total


async def _validate_one_tool(
    tc: Dict[str, Any],
    schema_map: "SchemaMap",
    repair_fn: Optional[Callable],
    session_anchor: str,
    residency_allows_egress: bool,
) -> ToolResult:
    """Validate a single tool call: assemble → validate → normalize → repair.

    Returns a ToolResult with outcome pass/repair/reject. Does NOT make
    set-level atomic decisions — that is decide()'s job.
    """
    idx = tc.get("index", 0)
    name = tc.get("name", "")
    tid = tc.get("tool_id", "")

    # Assemble fragments or use pre-parsed args.
    if "fragments" in tc:
        args, parse_err = assemble_partial_json(tc["fragments"])
    else:
        args = tc.get("args")
        parse_err = None

    if parse_err:
        TAG_REJECTIONS.labels(tool=name, reason="parse_error").inc()
        TAG_CALLS.labels(tool=name, outcome="invalid").inc()
        return ToolResult(idx, name, "reject", "parse_error", tool_id=tid)

    schema = schema_map.get(name)
    if schema is None:
        TAG_REJECTIONS.labels(tool=name, reason="unknown_tool").inc()
        TAG_CALLS.labels(tool=name, outcome="unknown").inc()
        return ToolResult(idx, name, "reject", "unknown_tool", tool_id=tid)

    ok, errors = validate_arguments(args, schema)
    if ok:
        TAG_CALLS.labels(tool=name, outcome="pass").inc()
        return ToolResult(idx, name, "pass", "", args=args, tool_id=tid)

    TAG_CALLS.labels(tool=name, outcome="invalid").inc()

    # Deterministic normalization.
    norm_args, applied = normalize_arguments(args, schema, name)
    ok2, errors2 = validate_arguments(norm_args, schema)
    if ok2:
        TAG_CALLS.labels(tool=name, outcome="normalized").inc()
        return ToolResult(idx, name, "repair", "", args=norm_args, tool_id=tid, applied_rules=applied)

    # Premium repair (one call per fingerprint).
    repaired = None
    if repair_fn is not None and residency_allows_egress:
        try:
            repaired = await repair_fn(name, schema, norm_args, errors2, session_anchor)
        except Exception:
            repaired = None
    if repaired is not None:
        ok3, _ = validate_arguments(repaired, schema)
        if ok3:
            TAG_PREMIUM_REPAIRS.labels(tool=name, outcome="success").inc()
            TAG_CALLS.labels(tool=name, outcome="repaired").inc()
            return ToolResult(idx, name, "repair", "", args=repaired, tool_id=tid)
    if repair_fn is not None:
        TAG_PREMIUM_REPAIRS.labels(tool=name, outcome="failed").inc()

    TAG_REJECTIONS.labels(tool=name, reason="unresolvable").inc()
    return ToolResult(idx, name, "reject", "unresolvable", tool_id=tid)


def _aggregate_outcome(per_tool: List[ToolResult]) -> Decision:
    """Compute the set-level Decision from per-tool results (atomic)."""
    any_repair = any(tr.outcome == "repair" for tr in per_tool)
    any_reject = any(tr.outcome == "reject" for tr in per_tool)

    if any_reject:
        # Atomic: if any tool is rejected, reject the entire set.
        for tr in per_tool:
            if tr.outcome != "reject":
                tr.outcome = "reject"
                tr.reason = "set_rejected"
        return Decision(
            outcome=DecisionOutcome.REJECTED,
            per_tool=per_tool,
            all_valid=False,
        )

    outcome = DecisionOutcome.REPAIRED if any_repair else DecisionOutcome.PASS
    return Decision(outcome=outcome, per_tool=per_tool, all_valid=True)


async def decide(
    tool_calls: List[Dict[str, Any]],
    schema_map: "SchemaMap",
    *,
    repair_fn: Optional[Callable] = None,
    session_anchor: str = "",
    residency_allows_egress: bool = True,
) -> Decision:
    """Run the full validation pipeline on a complete tool-call set.

    tool_calls: uniform list, each entry has:
      - index: int (original block index)
      - name: str (tool name)
      - tool_id: str
      - fragments: List[str] (streaming) OR args: Any (non-stream, pre-parsed)

    Returns a Decision. If any tool is rejected, the set-level outcome is
    REJECTED and ALL per_tool outcomes are "reject" (atomic — no valid
    sibling escapes).
    """
    # Check set-level limits first.
    per_call_bytes, total_buffer_bytes = _compute_call_bytes(tool_calls)
    limit_err = check_limits_return(len(tool_calls), per_call_bytes, total_buffer_bytes)
    if limit_err:
        per_tool = []
        for tc in tool_calls:
            tr = ToolResult(
                index=tc.get("index", 0),
                tool_name=tc.get("name", ""),
                outcome="reject",
                reason="limit_exceeded",
                tool_id=tc.get("tool_id", ""),
            )
            per_tool.append(tr)
            TAG_REJECTIONS.labels(tool=tr.tool_name, reason="limit_exceeded").inc()
        return Decision(
            outcome=DecisionOutcome.REJECTED,
            per_tool=per_tool,
            all_valid=False,
            limit_error=limit_err,
        )

    # Validate each tool independently.
    per_tool = []
    for tc in tool_calls:
        tr = await _validate_one_tool(
            tc, schema_map, repair_fn, session_anchor, residency_allows_egress
        )
        per_tool.append(tr)

    # Aggregate into a set-level atomic decision.
    return _aggregate_outcome(per_tool)

