import asyncio
import copy
import importlib
import inspect
import json
import logging
import sys
import types
from pathlib import Path

import pytest


PLUGIN_MODULE = "litellm_plugins.cc_glm52_guard"
EXPECTED_EXECUTION_MODEL = "glm-5.2"
EXPECTED_VISION_MODEL = "vision-openrouter"


@pytest.fixture(scope="session")
def plugin_module():
    try:
        return importlib.import_module(PLUGIN_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == "litellm_plugins" or exc.name == PLUGIN_MODULE:
            pytest.skip(
                f"{PLUGIN_MODULE} is not implemented yet; EPIC-10 contract tests skipped"
            )
        if exc.name == "litellm" or exc.name.startswith("litellm."):
            _install_litellm_import_stub()
            sys.modules.pop(PLUGIN_MODULE, None)
            sys.modules.pop(f"{PLUGIN_MODULE}.callback", None)
            return importlib.import_module(PLUGIN_MODULE)
        raise


def load_fixture(name):
    fixture_path = Path(__file__).parent / "fixtures" / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def run_guard(plugin_module, request_body):
    """Run the plugin request transform without a live LiteLLM service."""
    body = copy.deepcopy(request_body)
    candidate_callables = [
        getattr(plugin_module, name, None)
        for name in (
            "prepare_request",
            "transform_request",
            "route_request",
            "guard_request",
            "process_request",
        )
    ]

    handler = getattr(plugin_module, "proxy_handler_instance", None)
    if handler is not None:
        candidate_callables.extend(
            getattr(handler, name, None)
            for name in (
                "prepare_request",
                "transform_request",
                "route_request",
                "guard_request",
                "process_request",
                "pre_call_hook",
                "async_pre_call_hook",
            )
        )

    candidate_callables = [fn for fn in candidate_callables if callable(fn)]
    if not candidate_callables:
        pytest.fail(
            "cc_glm52_guard imported, but no request transform entrypoint was found. "
            "Expose one of prepare_request/transform_request/route_request/guard_request "
            "or proxy_handler_instance.async_pre_call_hook."
        )

    errors = []
    for fn in candidate_callables:
        for args, kwargs in _call_shapes(fn):
            trial = copy.deepcopy(body)
            try:
                result = fn(*args(trial), **kwargs(trial))
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
                return _normalize_result(trial, result)
            except TypeError as exc:
                errors.append(f"{_callable_name(fn)}: {exc}")

    pytest.fail(
        "No cc_glm52_guard request transform entrypoint accepted the EPIC-10 test "
        f"call shapes. Tried: {'; '.join(errors)}"
    )


def _call_shapes(fn):
    names = set(inspect.signature(fn).parameters)

    shapes = []
    shapes.append((lambda body: (body,), lambda body: {}))
    shapes.append((lambda body: (), lambda body: {"data": body}))
    shapes.append(
        (
            lambda body: (),
            lambda body: {
                "data": body,
                "call_type": "completion",
                "user_api_key_dict": {},
                "cache": None,
            },
        )
    )

    if {"user_api_key_dict", "cache", "data", "call_type"}.issubset(names):
        shapes.insert(
            0,
            (
                lambda body: ({}, None, body, "completion"),
                lambda body: {},
            ),
        )

    return shapes


def _normalize_result(mutated_body, result):
    if result is None:
        return mutated_body
    if isinstance(result, dict) and isinstance(result.get("data"), dict):
        return result["data"]
    if isinstance(result, dict):
        return result
    pytest.fail(f"Unexpected cc_glm52_guard transform result type: {type(result)!r}")


def _callable_name(fn):
    owner = getattr(getattr(fn, "__self__", None), "__class__", type("", (), {}))
    owner_name = getattr(owner, "__name__", "")
    fn_name = getattr(fn, "__name__", repr(fn))
    return f"{owner_name}.{fn_name}" if owner_name else fn_name


def _install_litellm_import_stub():
    litellm = types.ModuleType("litellm")
    logging_module = types.ModuleType("litellm._logging")
    integrations = types.ModuleType("litellm.integrations")
    custom_logger = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:
        pass

    logging_module.verbose_proxy_logger = logging.getLogger("cc_glm52_guard_test")
    custom_logger.CustomLogger = CustomLogger

    sys.modules.setdefault("litellm", litellm)
    sys.modules.setdefault("litellm._logging", logging_module)
    sys.modules.setdefault("litellm.integrations", integrations)
    sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)


def route_model(body):
    metadata = body.get("metadata") or {}
    routing = metadata.get("routing") if isinstance(metadata, dict) else {}
    guard_audit = metadata.get("cc_glm52_guard") if isinstance(metadata, dict) else {}
    litellm_metadata = body.get("litellm_metadata") or {}
    extra_body = body.get("extra_body") or {}
    extra_audit = (
        extra_body.get("cc_glm52_guard_audit")
        if isinstance(extra_body, dict)
        else {}
    )

    for container in (routing, guard_audit, extra_audit, metadata, litellm_metadata, body):
        if not isinstance(container, dict):
            continue
        for key in ("internal_route_model", "route_model", "target_model", "model"):
            value = container.get(key)
            if isinstance(value, str) and value:
                return value

    return None


def context_management(body):
    value = body.get("context_management")
    assert isinstance(value, dict), "context_management must be a dict"
    return value


def edits_by_type(body):
    edits = context_management(body).get("edits")
    assert isinstance(edits, list), "context_management.edits must be a list"
    return {edit.get("type"): edit for edit in edits if isinstance(edit, dict)}


def trigger_value(edit):
    trigger = edit.get("trigger") or {}
    assert trigger.get("type") == "input_tokens"
    return trigger.get("value")
