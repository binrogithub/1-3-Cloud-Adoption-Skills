"""Pytest conftest: centralize the litellm stub so every test module sees a
consistent stub regardless of collection order. Without this, the first test
file to stub litellm sets sys.modules["litellm"], and later files skip their
stub (guarding on `if "litellm" not in sys.modules`) — leaving submodules like
litellm._logging unset, which breaks callback imports.
"""

import logging
import sys
import types


def _ensure_litellm_stub() -> None:
    """Ensure a minimal litellm + litellm._logging + integrations.custom_logger
    stub exists in sys.modules. Idempotent: safe to call multiple times."""
    if "litellm" not in sys.modules:
        sys.modules["litellm"] = types.ModuleType("litellm")
    litellm = sys.modules["litellm"]
    # token_counter default; individual tests override as needed.
    if not hasattr(litellm, "token_counter"):
        litellm.token_counter = lambda **kwargs: 100

    if "litellm._logging" not in sys.modules:
        _log_mod = types.ModuleType("litellm._logging")
        _log_mod.verbose_proxy_logger = logging.getLogger("litellm_test")
        sys.modules["litellm._logging"] = _log_mod

    if "litellm.integrations" not in sys.modules:
        sys.modules["litellm.integrations"] = types.ModuleType("litellm.integrations")

    if "litellm.integrations.custom_logger" not in sys.modules:
        _cl = types.ModuleType("litellm.integrations.custom_logger")
        class CustomLogger:
            pass
        _cl.CustomLogger = CustomLogger
        sys.modules["litellm.integrations.custom_logger"] = _cl


_ensure_litellm_stub()


import pytest


@pytest.fixture(autouse=True)
def _reset_litellm_token_counter():
    """Reset litellm.token_counter before each test so a test that monkey-patches
    it (e.g. test_smart_router's boundary tests) doesn't leak into the next test."""
    litellm = sys.modules.get("litellm")
    if litellm is not None:
        litellm.token_counter = lambda **kwargs: 100
    yield
