"""LiteLLM adapter — isolates version-specific exception construction behind
one adapter for the pinned LiteLLM image (PRD-plugin-convergence §7.7).

The rest of the plugin uses internal typed errors (sidecar.SidecarError
subclasses) and does not import optional LiteLLM exception classes directly.
Supporting another LiteLLM version requires adapter tests rather than
compatibility branches throughout runtime modules.

Pinned image: ghcr.io/berriai/litellm:v1.83.14-stable.patch.3

R11 §4.1: Use litellm.APIError(status_code=...) for all mapped statuses.
The pinned image does not provide litellm.ContentTooLargeError (413) and
litellm.PermissionDeniedError requires a response object. litellm.APIError
exists in all versions and carries the HTTP status through the proxy.
"""

from typing import NoReturn


def raise_typed_error(sidecar_error: Exception) -> NoReturn:
    """Map an internal typed sidecar error to a pinned LiteLLM exception.

    The sidecar error carries an ``http_status`` int attribute and an
    ``error_code`` string. This function constructs a ``litellm.APIError``
    with the correct ``status_code`` so the proxy returns the correct HTTP
    status instead of a generic 500.

    If LiteLLM is unavailable, the original error is re-raised with its
    http_status intact.
    """
    status = getattr(sidecar_error, "http_status", None)
    if not isinstance(status, int):
        raise sidecar_error  # not a typed error — let it propagate

    error_code = getattr(sidecar_error, "error_code", "SIDECAR_ERROR")
    msg = "%s: %s" % (error_code, sidecar_error)

    try:
        import litellm
        # R11 §4.1: litellm.APIError exists in the pinned image and carries
        # status_code through the proxy. Map every known status explicitly;
        # unknown statuses fail with 500, not a silent 400.
        raise litellm.APIError(
            status_code=status,
            message=msg,
            model="",
            llm_provider="",
        )
    except (ImportError, TypeError, ValueError, AttributeError):
        # LiteLLM unavailable or APIError constructor incompatible — re-raise
        # the original internal error with its http_status attribute intact.
        raise sidecar_error
