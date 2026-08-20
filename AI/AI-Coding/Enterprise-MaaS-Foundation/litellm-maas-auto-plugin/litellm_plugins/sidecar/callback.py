"""Bounded Sidecar dispatch for the GLM-5.2 mainline.

PRD: docs/PRD-glm52-mainline-sidecars.md

Sidecars (Vision: Luna/Luna-Pro; Premium: Opus 5) never produce the final user
response. They receive purpose-built bounded payloads, return structured
context, and that context is injected into the GLM-5.2 request. GLM-5.2 owns
every final answer (invariant I1).

This module is mounted as /app/sidecar.py and imported by smart_router.
It is NOT a registered LiteLLM callback — it has no proxy_handler_instance.
smart_router calls ``await sidecar.process_request(data, key)`` in its
async_pre_call_hook.

Invariants (PRD §5):
  I1  GLM-5.2 produces every successful final response.
  I3  A Sidecar never receives the full conversation.
  I5  No recursive dispatch: recursion bypass checks the authenticated key.
  I6  Same image bytes → same cached caption.
  I7  One recovery attempt per failure fingerprint.
  I8  Both visual models fail → no GLM call for that image.
  I9  Same-provider fallback only (glm-5.1, 196608 cap).
  I10 Client metadata alone can never claim Sidecar identity.

Fail-open policy: any sidecar error that is NOT a typed contract error
(InvalidImageInput, ImageLimitExceeded, VisionSidecarUnavailable) is swallowed
by smart_router's fail-open wrapper and the request proceeds on GLM mainline
without sidecar enrichment. The typed errors propagate to the client as
HTTP 400/413/502.
"""

from __future__ import annotations

import asyncio
import base64
import contextvars
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Canonical request context (PRD-plugin-convergence §7.1). ResidencyPolicy is
# inherited so there is one authoritative implementation shared by Router and
# Sidecar. The import is wrapped so tests that load sidecar in isolation still
# work if _request_context is not yet in sys.modules.
try:
    import _request_context  # type: ignore
except ImportError:
    # Fallback: define a minimal base so the class below still works.
    class _request_context:  # type: ignore
        class ResidencyPolicy:
            ALLOW = "allow"
            CHINA_ONLY = "china-only"
            __slots__ = ("mode",)

            def __init__(self, mode: str = "allow"):
                self.mode = mode if mode in (self.ALLOW, self.CHINA_ONLY) else self.ALLOW

            @property
            def is_china_only(self):
                return self.mode == self.CHINA_ONLY

            @property
            def allows_egress(self):
                return self.mode == self.ALLOW

            @classmethod
            def from_key(cls, key):
                return cls(cls.ALLOW)

log = logging.getLogger("sidecar")

# ── Configuration (PRD §15) ─────────────────────────────────────────────────

SIDECAR_BASE_URL = os.getenv("SIDECAR_BASE_URL", "http://127.0.0.1:4000")
SIDECAR_API_KEY = os.getenv("SIDECAR_API_KEY", "")
SIDECAR_CACHE_DIR = os.getenv("SIDECAR_CACHE_DIR", "/app/cache")

VISION_PRIMARY_MODEL = os.getenv("VISION_PRIMARY_MODEL", "vision-openrouter")
VISION_SECONDARY_MODEL = os.getenv(
    "VISION_SECONDARY_MODEL", "vision-openrouter-secondary"
)
PREMIUM_SIDECAR_MODEL = os.getenv("PREMIUM_SIDECAR_MODEL", "premium-openrouter")

VISION_CACHE_TTL_SECONDS = int(os.getenv("VISION_CACHE_TTL_SECONDS", "2592000"))
VISION_CACHE_MAX_BYTES = int(os.getenv("VISION_CACHE_MAX_BYTES", "536870912"))
VISION_CACHE_MAX_ENTRIES = int(os.getenv("VISION_CACHE_MAX_ENTRIES", "100000"))

VISION_MAX_IMAGES = int(os.getenv("VISION_MAX_IMAGES", "4"))
VISION_MAX_IMAGE_BYTES = int(os.getenv("VISION_MAX_IMAGE_BYTES", "20971520"))
VISION_MAX_TOTAL_BYTES = int(os.getenv("VISION_MAX_TOTAL_BYTES", "41943040"))
VISION_TIMEOUT_SECONDS = float(os.getenv("VISION_TIMEOUT_SECONDS", "60"))
VISION_CAPTION_MAX_TOKENS = int(os.getenv("VISION_CAPTION_MAX_TOKENS", "4096"))

PREMIUM_TIMEOUT_SECONDS = float(os.getenv("PREMIUM_TIMEOUT_SECONDS", "90"))
PREMIUM_LEDGER_TTL_SECONDS = int(os.getenv("PREMIUM_LEDGER_TTL_SECONDS", "900"))
PREMIUM_MAX_DISTINCT_INTERVENTIONS = int(
    os.getenv("PREMIUM_MAX_DISTINCT_INTERVENTIONS_PER_SESSION", "3")
)
PREMIUM_MAX_PAYLOAD_TOKENS = int(os.getenv("PREMIUM_MAX_PAYLOAD_TOKENS", "8000"))

# Caption prompt/schema version — bump when the instruction or JSON schema
# changes. Cached captions with a mismatched version are quarantined (treated
# as misses), so a prompt change safely invalidates the cache.
CAPTION_SCHEMA_VERSION = 1
PREMIUM_SCHEMA_VERSION = 1

MAINLINE_MODEL = "claude-glm-5.2"

# ── Typed errors (propagate to client as HTTP errors) ───────────────────────


class SidecarError(Exception):
    """Base for typed sidecar contract errors that propagate to the client."""

    http_status = 500
    error_code = "SIDECAR_ERROR"


class InvalidImageInput(SidecarError):
    """Invalid image encoding, MIME type, file signature, or remote URL."""

    http_status = 400
    error_code = "INVALID_IMAGE_INPUT"


class ImageLimitExceeded(SidecarError):
    """Image count or byte limit exceeded."""

    http_status = 413
    error_code = "IMAGE_LIMIT_EXCEEDED"


class VisionSidecarUnavailable(SidecarError):
    """Both Luna and Luna Pro failed — no GLM call for this image (I8)."""

    http_status = 502
    error_code = "VISION_SIDECAR_UNAVAILABLE"


class SidecarPolicyDenied(SidecarError):
    """Sidecar call denied by authenticated data-residency policy (PRD §7.1).

    Raised before any external network call when a china-only key triggers a
    Vision cache miss or a Premium/tool-repair trigger. The request stays
    local: parsing, hashing, schema validation, and cache lookup are permitted.
    """

    http_status = 403
    error_code = "SIDECAR_POLICY_DENIED"


# ── Metrics (degrade to no-ops if prometheus_client is unavailable) ─────────

try:
    from prometheus_client import Counter as _Counter

    SIDECAR_REQUESTS = _Counter(
        "sidecar_requests_total",
        "Sidecar model calls by kind, model, and outcome",
        ["kind", "model", "outcome"],
    )
    VISION_CACHE_REQUESTS = _Counter(
        "vision_cache_requests_total",
        "Caption cache lookups by outcome",
        ["outcome"],
    )
    VISION_FALLBACKS = _Counter(
        "vision_fallbacks_total",
        "Vision primary→secondary fallbacks",
        ["from", "to", "reason"],
    )
    PREMIUM_TRIGGERS = _Counter(
        "premium_triggers_total",
        "Premium recovery triggers by signal type",
        ["signal"],
    )
    PREMIUM_INTERVENTIONS = _Counter(
        "premium_interventions_total",
        "Premium interventions by outcome",
        ["outcome"],
    )
    PREMIUM_HARD_STOPS = _Counter(
        "premium_hard_stops_total",
        "Premium hard-stops by reason",
        ["reason"],
    )
    SIDECAR_RECURSION_BLOCKS = _Counter(
        "sidecar_recursion_blocks_total",
        "Forged sidecar recursion attempts blocked (I5/I10)",
    )
    SIDECAR_POLICY_DENIALS = _Counter(
        "sidecar_policy_denials_total",
        "Sidecar calls denied by authenticated residency policy",
        ["kind"],
    )
    MAINLINE_FINAL_RESPONSES = _Counter(
        "mainline_final_responses_total",
        "Final responses produced by the mainline model",
        ["model"],
    )
except Exception:  # pragma: no cover

    class _Noop:
        def labels(self, **_kw):
            return self

        def inc(self, _v=1):
            return None

    SIDECAR_REQUESTS = VISION_CACHE_REQUESTS = VISION_FALLBACKS = _Noop()
    PREMIUM_TRIGGERS = PREMIUM_INTERVENTIONS = PREMIUM_HARD_STOPS = _Noop()
    SIDECAR_RECURSION_BLOCKS = MAINLINE_FINAL_RESPONSES = _Noop()
    SIDECAR_POLICY_DENIALS = _Noop()


# ── Image extraction (PRD §8.1) ─────────────────────────────────────────────

# File signatures (magic bytes) for MIME validation.
_FILE_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif": b"GIF87a",
    "image/gif2": b"GIF89a",
    "image/webp": b"RIFF",
    "image/bmp": b"BM",
}

# MIME types we accept for vision sidecar dispatch.
_ACCEPTED_MIME_TYPES = frozenset({
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/bmp",
})

# Data-URI pattern: data:<mime>;base64,<data>
_DATA_URL_RE = re.compile(r"^data:([^;,]+);base64,(.+)$", re.DOTALL)

# Remote URL schemes rejected in this release (PRD §8.1, §4 non-goal).
_REMOTE_URL_RE = re.compile(r"^https?://", re.I)

# Block types that carry image data at the content-block level.
_IMAGE_BLOCK_TYPES = frozenset({"image", "image_url", "input_image"})


class ImageRef:
    """A discovered image and its location for in-place replacement.

    ``source_path`` is a tuple identifying where the block lives so
    replace_with_captions can find it again: (msg_key, msg_index, content_path)
    where content_path is a tuple of indices to recurse into nested structures
    (e.g. tool_result.content[]).
    """

    __slots__ = (
        "media_type", "raw_b64", "decoded_bytes", "sha256",
        "source_path", "block_ref",
    )

    def __init__(self, media_type, raw_b64, decoded_bytes, source_path, block_ref):
        self.media_type = media_type
        self.raw_b64 = raw_b64
        self.decoded_bytes = decoded_bytes
        self.sha256 = hashlib.sha256(decoded_bytes).hexdigest()
        self.source_path = source_path
        self.block_ref = block_ref  # the actual dict block, for in-place mutation


def _decode_base64(raw: str) -> bytes:
    """Decode base64, raising InvalidImageInput on malformed data."""
    try:
        # Validate padding and characters.
        return base64.b64decode(raw, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise InvalidImageInput("malformed base64 image data: %s" % exc)


def _validate_mime_and_signature(media_type: str, decoded: bytes) -> None:
    """Validate declared MIME type and file signature (magic bytes)."""
    mt = (media_type or "").lower().strip()
    if mt not in _ACCEPTED_MIME_TYPES:
        raise InvalidImageInput(
            "unsupported image MIME type: %r (accepted: %s)"
            % (media_type, sorted(_ACCEPTED_MIME_TYPES))
        )
    # GIF has two valid signatures; check both.
    sigs_to_check = []
    if mt in ("image/gif",):
        sigs_to_check = [b"GIF87a", b"GIF89a"]
    elif mt in _FILE_SIGNATURES:
        sigs_to_check = [_FILE_SIGNATURES[mt]]
    # JPEG has a 3-byte common prefix but variants differ; only check the 2-byte
    # SOI marker \xff\xd8.
    if mt in ("image/jpeg", "image/jpg"):
        if not decoded.startswith(b"\xff\xd8"):
            raise InvalidImageInput(
                "file signature does not match declared MIME type %r" % media_type
            )
        return
    if mt == "image/webp":
        # RIFF....WEBP
        if not decoded.startswith(b"RIFF") or decoded[8:12] != b"WEBP":
            raise InvalidImageInput(
                "file signature does not match declared MIME type %r" % media_type
            )
        return
    for sig in sigs_to_check:
        if decoded.startswith(sig):
            return
    raise InvalidImageInput(
        "file signature does not match declared MIME type %r" % media_type
    )


def _extract_from_block(block: dict, source_path: tuple) -> Optional[ImageRef]:
    """Extract an ImageRef from a single content block, or None if not an image.

    Raises InvalidImageInput for remote URLs (rejected in this release).
    """
    if not isinstance(block, dict):
        return None
    btype = block.get("type")

    # Anthropic image: {"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}
    if btype == "image":
        source = block.get("source") or {}
        if not isinstance(source, dict):
            return None
        stype = source.get("type")
        if stype == "base64":
            media_type = source.get("media_type", "")
            raw_b64 = source.get("data", "")
            if not raw_b64:
                return None
            decoded = _decode_base64(raw_b64)
            _validate_mime_and_signature(media_type, decoded)
            return ImageRef(media_type, raw_b64, decoded, source_path, block)
        if stype == "url":
            url = source.get("url", "")
            if _REMOTE_URL_RE.match(url):
                raise InvalidImageInput(
                    "remote image URLs are not supported in this release: %s" % url[:100]
                )
            return None
        return None

    # OpenAI image_url: {"type": "image_url", "image_url": {"url": "data:..."}}
    if btype == "image_url":
        iu = block.get("image_url")
        if isinstance(iu, dict):
            url = iu.get("url", "")
        else:
            url = iu if isinstance(iu, str) else ""
        if not url:
            return None
        match = _DATA_URL_RE.match(url)
        if match:
            media_type = match.group(1)
            raw_b64 = match.group(2)
            decoded = _decode_base64(raw_b64)
            _validate_mime_and_signature(media_type, decoded)
            return ImageRef(media_type, raw_b64, decoded, source_path, block)
        if _REMOTE_URL_RE.match(url):
            raise InvalidImageInput(
                "remote image URLs are not supported in this release: %s" % url[:100]
            )
        return None

    # OpenAI input_image (Responses API): {"type": "input_image", "image_url": "data:..."}
    if btype == "input_image":
        iu = block.get("image_url")
        url = iu.get("url", "") if isinstance(iu, dict) else (iu if isinstance(iu, str) else "")
        if not url:
            return None
        match = _DATA_URL_RE.match(url)
        if match:
            media_type = match.group(1)
            raw_b64 = match.group(2)
            decoded = _decode_base64(raw_b64)
            _validate_mime_and_signature(media_type, decoded)
            return ImageRef(media_type, raw_b64, decoded, source_path, block)
        if _REMOTE_URL_RE.match(url):
            raise InvalidImageInput(
                "remote image URLs are not supported in this release: %s" % url[:100]
            )
        return None

    return None


def _iter_content_blocks(content: Any):
    """Yield (index, block) for list content; for string content, yield nothing."""
    if isinstance(content, list):
        for idx, block in enumerate(content):
            yield idx, block


def extract_images(data: dict) -> List[ImageRef]:
    """Recursively extract all images from every message in the payload.

    Scans ALL messages (history + current) because Claude Code resends historical
    tool results. Recurses into tool_result.content[] for nested images (the
    Claude Code Read tool returns images inside tool_result blocks).

    Deduplicates by SHA-256(decoded_bytes) — the same image appearing in
    multiple positions is processed once, but replaced everywhere.

    Raises InvalidImageInput for remote URLs or malformed images.
    """
    images = []
    seen_hashes = set()
    for msg_key in ("messages", "input"):
        messages = data.get(msg_key)
        if not isinstance(messages, list):
            continue
        for msg_idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block_idx, block in enumerate(content):
                if not isinstance(block, dict):
                    continue
                # Top-level image block.
                ref = _extract_from_block(
                    block, (msg_key, msg_idx, (block_idx,))
                )
                if ref is not None:
                    if ref.sha256 not in seen_hashes:
                        images.append(ref)
                        seen_hashes.add(ref.sha256)
                    continue
                # Nested in tool_result.content[].
                if block.get("type") == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        for inner_idx, inner_block in enumerate(inner):
                            ref = _extract_from_block(
                                inner_block,
                                (msg_key, msg_idx, (block_idx, inner_idx)),
                            )
                            if ref is not None and ref.sha256 not in seen_hashes:
                                images.append(ref)
                                seen_hashes.add(ref.sha256)
    return images


def validate_and_limit(images: List[ImageRef]) -> List[ImageRef]:
    """Enforce image count and byte limits (PRD §8.2).

    Raises ImageLimitExceeded on count/size violation.
    Validation of base64/MIME/signature is done at extraction time.
    """
    if len(images) > VISION_MAX_IMAGES:
        raise ImageLimitExceeded(
            "too many images: %d (limit %d)" % (len(images), VISION_MAX_IMAGES)
        )
    total = 0
    for img in images:
        size = len(img.decoded_bytes)
        if size > VISION_MAX_IMAGE_BYTES:
            raise ImageLimitExceeded(
                "image too large: %d bytes (limit %d)"
                % (size, VISION_MAX_IMAGE_BYTES)
            )
        total += size
    if total > VISION_MAX_TOTAL_BYTES:
        raise ImageLimitExceeded(
            "total image bytes too large: %d (limit %d)"
            % (total, VISION_MAX_TOTAL_BYTES)
        )
    return images


# ── Caption injection (PRD §8.5) ────────────────────────────────────────────

_CAPTION_TEMPLATE = (
    "[vision-caption sha256={sha256} schema=v{schema_version}]\n"
    "Summary: {summary}\n"
    "Visible text:\n{visible_text}\n"
    "Errors:\n{errors}\n"
    "Layout: {layout}\n"
    "Uncertainties:\n{uncertainties}\n"
    "[/vision-caption]"
)


def render_caption_text(sha256: str, caption_obj: dict) -> str:
    """Render a validated caption JSON object into the deterministic template."""
    def _bullet_list(items):
        if not items:
            return "- (none)"
        return "\n".join("- %s" % (item,) for item in items)

    return _CAPTION_TEMPLATE.format(
        sha256=sha256,
        schema_version=CAPTION_SCHEMA_VERSION,
        summary=caption_obj.get("summary", ""),
        visible_text=_bullet_list(caption_obj.get("visible_text", [])),
        errors=_bullet_list(caption_obj.get("errors", [])),
        layout=caption_obj.get("layout", ""),
        uncertainties=_bullet_list(caption_obj.get("uncertainties", [])),
    )


def replace_with_captions(data: dict, captions_by_hash: Dict[str, str]) -> None:
    """Replace every image block in-place with its caption text block.

    Preserves adjacent text blocks and tool IDs. Operates on all messages
    (history + current) so historical images are replaced too — this is what
    makes text references to earlier images work without re-calling the visual
    model (PRD §8.1).
    """
    for msg_key in ("messages", "input"):
        messages = data.get(msg_key)
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            _replace_in_content(msg, "content", captions_by_hash)


def _replace_in_content(msg: dict, content_key: str, captions_by_hash: Dict[str, str]) -> None:
    """Replace image blocks in msg[content_key], recursing into tool_result.content[]."""
    content = msg.get(content_key)
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        # Top-level image block → replace with caption text.
        if block.get("type") in _IMAGE_BLOCK_TYPES:
            sha = _block_sha256(block)
            if sha and sha in captions_by_hash:
                block.clear()
                block["type"] = "text"
                block["text"] = captions_by_hash[sha]
            continue
        # Nested in tool_result.content[].
        if block.get("type") == "tool_result":
            inner = block.get("content")
            if isinstance(inner, list):
                for inner_block in inner:
                    if (
                        isinstance(inner_block, dict)
                        and inner_block.get("type") in _IMAGE_BLOCK_TYPES
                    ):
                        sha = _block_sha256(inner_block)
                        if sha and sha in captions_by_hash:
                            inner_block.clear()
                            inner_block["type"] = "text"
                            inner_block["text"] = captions_by_hash[sha]


def _block_sha256(block: dict) -> Optional[str]:
    """Compute the SHA-256 of the decoded image bytes in a block (for matching)."""
    try:
        ref = _extract_from_block(block, ())
        return ref.sha256 if ref else None
    except SidecarError:
        return None


# ── Caption JSON schema validation (PRD §8.3) ───────────────────────────────

_CAPTION_MAX_FIELD_LEN = 4096
_CAPTION_MAX_LIST_ITEMS = 100


def validate_caption(obj: Any) -> dict:
    """Validate a caption response against the schema (PRD §8.3).

    Raises ValueError on missing fields, wrong types, or size violations.
    """
    if not isinstance(obj, dict):
        raise ValueError("caption response is not a JSON object")
    required = {"summary", "visible_text", "errors", "layout", "uncertainties"}
    missing = required - set(obj)
    if missing:
        raise ValueError("caption missing fields: %s" % sorted(missing))
    if not isinstance(obj["summary"], str):
        raise ValueError("caption.summary must be a string")
    if not isinstance(obj["layout"], str):
        raise ValueError("caption.layout must be a string")
    for key in ("visible_text", "errors", "uncertainties"):
        val = obj[key]
        if not isinstance(val, list):
            raise ValueError("caption.%s must be a list" % key)
        if len(val) > _CAPTION_MAX_LIST_ITEMS:
            raise ValueError("caption.%s too many items (max %d)" % (key, _CAPTION_MAX_LIST_ITEMS))
        for item in val:
            if not isinstance(item, str):
                raise ValueError("caption.%s items must be strings" % key)
            if len(item) > _CAPTION_MAX_FIELD_LEN:
                raise ValueError("caption.%s item too long" % key)
    if len(obj["summary"]) > _CAPTION_MAX_FIELD_LEN:
        raise ValueError("caption.summary too long")
    if len(obj["layout"]) > _CAPTION_MAX_FIELD_LEN:
        raise ValueError("caption.layout too long")
    return obj


# ── Premium response schema validation (PRD §10.4) ──────────────────────────

_PREMIUM_MAX_FIELD_LEN = 4096


def validate_premium(obj: Any) -> dict:
    """Validate a premium recovery response (PRD §10.4).

    Raises ValueError on missing fields, wrong types, or size violations.
    """
    if not isinstance(obj, dict):
        raise ValueError("premium response is not a JSON object")
    required = {
        "diagnosis", "next_action", "stop_conditions",
        "prohibited_retries", "user_visible_blocker",
    }
    missing = required - set(obj)
    if missing:
        raise ValueError("premium missing fields: %s" % sorted(missing))
    for key in ("diagnosis", "next_action", "user_visible_blocker"):
        if not isinstance(obj[key], str):
            raise ValueError("premium.%s must be a string" % key)
        if len(obj[key]) > _PREMIUM_MAX_FIELD_LEN:
            raise ValueError("premium.%s too long" % key)
    for key in ("stop_conditions", "prohibited_retries"):
        val = obj[key]
        if not isinstance(val, list):
            raise ValueError("premium.%s must be a list" % key)
        for item in val:
            if not isinstance(item, str):
                raise ValueError("premium.%s items must be strings" % key)
            if len(item) > _PREMIUM_MAX_FIELD_LEN:
                raise ValueError("premium.%s item too long" % key)
    return obj


# ── Caption cache (PRD §9) ──────────────────────────────────────────────────

import fcntl  # noqa: E402 — cross-process per-hash locking


class CaptionCache:
    """SHA-256 caption cache with atomic writes and LRU eviction.

    Storage: <root>/captions/v1/<sha256>.json
    Dir mode 0700, file mode 0600. Atomic writes via temp+fsync+rename.
    Per-hash asyncio.Lock (in-process) + fcntl.flock (cross-process) prevents
    duplicate sidecar calls across workers.

    Never stores image bytes, data URIs, API keys, request bodies, or user
    prompts — only the rendered caption and metadata.
    """

    def __init__(
        self,
        root: str,
        ttl_seconds: int = VISION_CACHE_TTL_SECONDS,
        max_bytes: int = VISION_CACHE_MAX_BYTES,
        max_entries: int = VISION_CACHE_MAX_ENTRIES,
        prompt_version: int = CAPTION_SCHEMA_VERSION,
    ):
        self.root = Path(root) / "captions" / "v1"
        self.ttl_seconds = ttl_seconds
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.prompt_version = prompt_version
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()
        self._ensure_root()

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            pass  # fail-open — cache disabled, captions still work without cache

    async def get_lock(self, sha256: str) -> asyncio.Lock:
        """Get or create the per-hash asyncio lock."""
        async with self._locks_guard:
            lock = self._locks.get(sha256)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[sha256] = lock
            return lock

    def _entry_path(self, sha256: str) -> Path:
        return self.root / ("%s.json" % sha256)

    def _lockfile_path(self, sha256: str) -> Path:
        return self.root / ("%s.lock" % sha256)

    def cross_process_lock(self, sha256: str):
        """Context manager: acquire an exclusive cross-process flock on the
        per-hash lockfile (PRD §7.8, C7).

        fcntl.flock is automatically released when the file descriptor closes
        (process exit, crash) — no stale-lock problem. Combined with the
        in-process asyncio.Lock (get_lock), this guarantees one Vision
        generation per image hash across proxy workers.

        Usage:
            with cache.cross_process_lock(sha):
                # cache recheck → Luna → Luna Pro → cache.put
        """
        import contextlib

        @contextlib.contextmanager
        def _cm():
            lockfile = self._lockfile_path(sha256)
            fh = None
            try:
                self._ensure_root()
                fh = open(lockfile, "w")
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                yield
            except OSError:
                # Lock unavailable / filesystem doesn't support flock — fail-open.
                # The in-process asyncio.Lock still prevents duplicates within one worker.
                yield
            finally:
                if fh is not None:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                    fh.close()

        return _cm()

    def cross_process_lock_async(self, sha256: str):
        """Async context manager: acquire flock via asyncio.to_thread so the
        event loop is not blocked while waiting (PRD v2 §7.8 R8).

        Usage:
            async with cache.cross_process_lock_async(sha):
                # cache recheck → Luna → Luna Pro → cache.put
        """
        import contextlib

        class _AsyncLock:
            def __init__(self, cache, sha):
                self._cache = cache
                self._sha = sha
                self._fh = None

            async def __aenter__(self):
                lockfile = self._cache._lockfile_path(self._sha)
                try:
                    self._cache._ensure_root()
                    self._fh = open(lockfile, "w")
                    # R8: wrap the blocking flock in to_thread so the event loop
                    # is not stalled while another worker holds the lock.
                    await asyncio.to_thread(fcntl.flock, self._fh.fileno(), fcntl.LOCK_EX)
                except OSError:
                    # Lock unavailable / filesystem doesn't support flock — fail-open.
                    self._fh = None
                return self

            async def __aexit__(self, *exc):
                if self._fh is not None:
                    try:
                        await asyncio.to_thread(fcntl.flock, self._fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                    self._fh.close()
                return False

        return _AsyncLock(self, sha256)

    def get(self, sha256: str) -> Optional[str]:
        """Return the rendered caption on a hit, None on miss/expired/corrupt.

        Updates last-access on hit. A corrupt or version-mismatched entry is
        quarantined (deleted) and treated as a miss.
        """
        path = self._entry_path(sha256)
        try:
            with path.open("r", encoding="utf-8") as f:
                entry = json.load(f)
        except OSError:
            return None  # file missing — a plain miss, nothing to quarantine
        except ValueError:
            # Corrupt JSON — quarantine, count, treat as a miss (PRD §9.2).
            self._quarantine(path)
            VISION_CACHE_REQUESTS.labels(outcome="corrupt").inc()
            return None
        if not isinstance(entry, dict):
            self._quarantine(path)
            VISION_CACHE_REQUESTS.labels(outcome="corrupt").inc()
            return None
        # Version mismatch → quarantine (prompt/schema changed).
        if entry.get("prompt_version") != self.prompt_version:
            self._quarantine(path)
            VISION_CACHE_REQUESTS.labels(outcome="expired").inc()
            return None
        # TTL check.
        last_access = entry.get("last_access", 0)
        if time.time() - last_access > self.ttl_seconds:
            self._quarantine(path)
            VISION_CACHE_REQUESTS.labels(outcome="expired").inc()
            return None
        rendered = entry.get("rendered_caption")
        if not isinstance(rendered, str) or not rendered:
            self._quarantine(path)
            VISION_CACHE_REQUESTS.labels(outcome="corrupt").inc()
            return None
        # Update last-access (best-effort, non-atomic is fine for access time).
        entry["last_access"] = time.time()
        try:
            self._atomic_write(path, json.dumps(entry, ensure_ascii=False))
        except OSError:
            pass
        VISION_CACHE_REQUESTS.labels(outcome="hit").inc()
        return rendered

    def put(self, sha256: str, rendered_caption: str, source_model: str) -> None:
        """Write a caption entry atomically (temp+fsync+rename, mode 0600)."""
        path = self._entry_path(sha256)
        now = time.time()
        entry = {
            "sha256": sha256,
            "schema_version": CAPTION_SCHEMA_VERSION,
            "prompt_version": self.prompt_version,
            "rendered_caption": rendered_caption,
            "source_model": source_model,
            "created_at": now,
            "last_access": now,
        }
        try:
            self._atomic_write(path, json.dumps(entry, ensure_ascii=False))
            VISION_CACHE_REQUESTS.labels(outcome="miss").inc()
        except OSError:
            pass  # fail-open — cache write failure doesn't break the request

    def _quarantine(self, path: Path) -> None:
        """Delete a corrupt/version-mismatched entry (treat as miss)."""
        try:
            path.unlink()
        except OSError:
            pass

    def _atomic_write(self, path: Path, data: str) -> None:
        """Write via temp file + fsync + atomic rename. File mode 0600.

        The temp file is unique per writer (pid + random) so concurrent workers
        never collide on the same .tmp name (PRD §7.8).
        """
        import os as _os
        tmp = path.with_suffix(".tmp.%d.%s" % (_os.getpid(), _os.urandom(8).hex()))
        with tmp.open("w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.chmod(0o600)
        os.replace(tmp, path)  # atomic on same filesystem

    def evict_if_needed(self) -> None:
        """LRU eviction by last-access time. Runs outside the request path."""
        try:
            entries = []
            for p in self.root.glob("*.json"):
                try:
                    with p.open("r", encoding="utf-8") as f:
                        entry = json.load(f)
                    if isinstance(entry, dict):
                        entries.append((p, entry.get("last_access", 0), p.stat().st_size))
                except (OSError, ValueError):
                    continue
        except OSError:
            return
        if not entries:
            return
        total_bytes = sum(e[2] for e in entries)
        total_entries = len(entries)
        if total_bytes <= self.max_bytes and total_entries <= self.max_entries:
            return
        # Sort by last_access ascending (LRU first).
        entries.sort(key=lambda e: e[1])
        for path, _la, size in entries:
            if total_bytes <= self.max_bytes and total_entries <= self.max_entries:
                break
            try:
                path.unlink()
                total_bytes -= size
                total_entries -= 1
            except OSError:
                pass


# Module-level cache instance (lazy-initialized to avoid import-time disk access).
_caption_cache: Optional[CaptionCache] = None


def get_caption_cache() -> CaptionCache:
    global _caption_cache
    if _caption_cache is None:
        _caption_cache = CaptionCache(SIDECAR_CACHE_DIR)
    return _caption_cache


# ── Loopback HTTP client (PRD §6) ───────────────────────────────────────────

import urllib.request  # noqa: E402
import urllib.error  # noqa: E402


class SidecarCallError(Exception):
    """A sidecar model call failed (HTTP error, timeout, or invalid response)."""


async def call_model(
    model: str,
    messages: list,
    *,
    max_tokens: int = 4096,
    timeout: float = 60.0,
    temperature: Optional[float] = None,
    kind: str = "vision",
) -> dict:
    """POST to the loopback gateway /v1/chat/completions with the internal key.

    Returns the parsed JSON response. Raises SidecarCallError on any failure.
    Uses urllib in a thread (asyncio.to_thread) — no new dependencies.

    Generic LiteLLM retries are disabled (num_retries=0) — the explicit
    two-attempt sequence (Luna → Luna Pro) is the complete retry budget.

    PRD §7.1 (C2): evaluates authenticated residency policy BEFORE the network
    call. A china-only key never reaches OpenRouter — the check is at this
    boundary (defense in depth), so a router ordering mistake can't bypass it.
    """
    # Residency check at the network boundary (PRD §7.1, C2).
    _current_residency().check_egress(kind)

    if not SIDECAR_API_KEY:
        raise SidecarCallError("SIDECAR_API_KEY is not configured")
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "num_retries": 0,
        # PRD-release-closure §3.4: disable LiteLLM fallbacks for internal
        # Sidecar calls. The two-attempt sequence (Luna → Luna Pro) is the
        # complete budget. LiteLLM must not silently fall back to a text model
        # (e.g. glm-5.1-fallback) when a Vision model fails.
        "fallbacks": [],
    }
    if temperature is not None:
        body["temperature"] = temperature
    return await asyncio.to_thread(_call_model_sync, model, body, timeout)


def _call_model_sync(model: str, body: dict, timeout: float) -> dict:
    url = SIDECAR_BASE_URL.rstrip("/") + "/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": "Bearer %s" % SIDECAR_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SidecarCallError(
            "sidecar call to %s failed: HTTP %d" % (model, exc.code)
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SidecarCallError("sidecar call to %s failed: %s" % (model, exc))


def _extract_response_text(response: dict) -> str:
    """Extract the text content from a chat/completions response."""
    try:
        choices = response.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return ""
    except (TypeError, KeyError, IndexError):
        return ""


# ── Vision sidecar dispatch (PRD §8) ────────────────────────────────────────

CAPTION_INSTRUCTION = (
    "You are a vision assistant analyzing a single image for a coding agent. "
    "Describe what is visible in structured JSON with these exact fields:\n"
    '  "summary": objective description of the image,\n'
    '  "visible_text": array of verbatim strings in reading order,\n'
    '  "errors": array of verbatim error messages and codes,\n'
    '  "layout": relative position and hierarchy of relevant elements,\n'
    '  "uncertainties": array of details that cannot be read reliably.\n'
    "Rules:\n"
    "- Do NOT make recommendations or suggestions.\n"
    "- Do NOT call any tools.\n"
    "- Do NOT execute or describe code execution.\n"
    "- Do NOT make claims not grounded in the image.\n"
    "- Respond with ONLY the JSON object, no markdown fences, no prose."
)


def _build_caption_messages(image: ImageRef) -> list:
    """Build the bounded vision payload: one image + fixed instruction."""
    return [
        {"role": "user", "content": [
            {"type": "text", "text": CAPTION_INSTRUCTION},
            {"type": "image_url", "image_url": {
                "url": "data:%s;base64,%s" % (image.media_type, image.raw_b64),
            }},
        ]},
    ]


async def caption_image(
    image: ImageRef,
    *,
    call_model=None,
    cache: Optional[CaptionCache] = None,
) -> str:
    """Caption a single image: cache lookup → Luna → Luna Pro → strict failure.

    Returns the rendered caption text. Raises VisionSidecarUnavailable if both
    models fail (I8). ``call_model`` is injectable for testing.
    """
    if call_model is None:
        call_model = _default_call_model_for_vision
    if cache is None:
        cache = get_caption_cache()

    cached = cache.get(image.sha256)
    if cached is not None:
        return cached

    _current_residency().check_egress("vision")

    lock = await cache.get_lock(image.sha256)
    async with lock:
        async with cache.cross_process_lock_async(image.sha256):
            cached = cache.get(image.sha256)
            if cached is not None:
                return cached
            messages = _build_caption_messages(image)
            # Attempt 1: Luna (primary).
            caption_obj = await _try_caption(VISION_PRIMARY_MODEL, messages, call_model)
            if caption_obj is not None:
                rendered = render_caption_text(image.sha256, caption_obj)
                cache.put(image.sha256, rendered, VISION_PRIMARY_MODEL)
                return rendered
            # Attempt 2: Luna Pro (secondary, exactly once).
            VISION_FALLBACKS.labels(
                **{"from": VISION_PRIMARY_MODEL},
                to=VISION_SECONDARY_MODEL, reason="primary_failed",
            ).inc()
            caption_obj = await _try_caption(VISION_SECONDARY_MODEL, messages, call_model)
            if caption_obj is not None:
                rendered = render_caption_text(image.sha256, caption_obj)
                cache.put(image.sha256, rendered, VISION_SECONDARY_MODEL)
                return rendered
            # Both failed → strict failure (I8).
            raise VisionSidecarUnavailable(
                "both vision models failed for image sha256=%s" % image.sha256[:16]
            )


async def _try_caption(
    model: str, messages: list, call_model
) -> Optional[dict]:
    """Try one caption call. Returns validated caption obj or None on failure."""
    try:
        response = await call_model(
            model, messages,
            max_tokens=VISION_CAPTION_MAX_TOKENS,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        text = _extract_response_text(response)
        if not text:
            SIDECAR_REQUESTS.labels(kind="vision", model=model, outcome="empty").inc()
            return None
        obj = json.loads(text)
        validate_caption(obj)
        SIDECAR_REQUESTS.labels(kind="vision", model=model, outcome="success").inc()
        return obj
    except (SidecarCallError, ValueError, json.JSONDecodeError) as exc:
        # Transport failure, bad JSON, or schema violation → this model failed.
        # The two-attempt budget (Luna → Luna Pro) handles it; both failing
        # raises VisionSidecarUnavailable.
        SIDECAR_REQUESTS.labels(kind="vision", model=model, outcome="error").inc()
        log.warning("vision caption failed on %s: %s: %s", model, type(exc).__name__, exc)
        return None
    # Any OTHER exception is unexpected — let it propagate so process_request's
    # fail-open wrapper can swallow it (do not convert it into a model failure).


async def _default_call_model_for_vision(model, messages, *, max_tokens, timeout, temperature=None):
    """Default call_model binding for vision (passes through to call_model)."""
    return await call_model(model, messages, max_tokens=max_tokens, timeout=timeout, temperature=temperature)


async def process_vision(data: dict, *, call_model=None, cache=None) -> dict:
    """Extract images, caption each, inject captions in-place.

    Returns a dict with vision stats for metrics. Raises InvalidImageInput,
    ImageLimitExceeded, or VisionSidecarUnavailable (which propagate to the
    client). On success, all image blocks are replaced with caption text.
    """
    images = extract_images(data)
    if not images:
        return {"images": 0, "cache_hits": 0, "cache_misses": 0}
    validate_and_limit(images)
    captions_by_hash = {}
    hits = 0
    misses = 0
    if cache is None:
        cache = get_caption_cache()
    for image in images:
        # Check cache first for stats (caption_image also checks, but we want
        # the hit/miss count even when the image appears in multiple positions).
        pre = cache.get(image.sha256)
        if pre is not None:
            captions_by_hash[image.sha256] = pre
            hits += 1
            continue
        misses += 1
        caption = await caption_image(image, call_model=call_model, cache=cache)
        captions_by_hash[image.sha256] = caption
    replace_with_captions(data, captions_by_hash)
    # Run eviction from the production path after a cache miss (PRD §7.8).
    # Throttled: only when there was at least one miss (no point evicting on a
    # pure-hit request). evict_if_needed itself is a no-op when under caps.
    if misses:
        try:
            cache.evict_if_needed()
        except Exception:
            pass  # eviction failure must never break the request
    return {"images": len(images), "cache_hits": hits, "cache_misses": misses}


# ── Premium recovery sidecar (PRD §10) ──────────────────────────────────────

# Secret-named fields redacted from tool arguments before fingerprinting/logging.
_SECRET_FIELD_NAMES = frozenset({
    "key", "token", "password", "passwd", "api_key", "apikey",
    "secret", "authorization", "auth", "credential", "access_token",
    "refresh_token", "private_key", "session_key",
})

# Raw tool-call markup detection (request-side: last assistant message).
_RAW_TOOL_MARKUP_RE = re.compile(r"<tool_call|<function_call|</\w+_tool>")


def _redact_args(args: Any) -> Any:
    """Redact secret-named fields from tool arguments (PRD §10.2, §13)."""
    if isinstance(args, dict):
        return {
            k: ("***" if k.lower() in _SECRET_FIELD_NAMES else _redact_args(v))
            for k, v in args.items()
        }
    if isinstance(args, list):
        return [_redact_args(item) for item in args]
    return args


def _canonicalize_args(args: Any) -> str:
    """Canonicalize tool arguments for fingerprinting (sorted keys, redacted)."""
    redacted = _redact_args(args)
    try:
        return json.dumps(redacted, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(redacted)


def _session_anchor(data: dict) -> str:
    """Stable task/session anchor for fingerprinting (PRD §10.2)."""
    metadata = data.get("metadata") or {}
    if isinstance(metadata, dict):
        sid = metadata.get("session_id")
        if sid:
            return str(sid)
    # Fall back to the first user message text (stable across turns).
    for msg_key in ("messages", "input"):
        for msg in (data.get(msg_key) or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content[:512]
                if isinstance(content, list):
                    return " ".join(
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") in {"text", "input_text"}
                    )[:512]
    return ""


def detect_triggers(data: dict) -> List[dict]:
    """Detect deterministic failure signals (PRD §10.1).

    Returns a list of normalized signal dicts. Keywords, task complexity,
    context length, and model self-assessment are NOT triggers.

    Three signal types:
      1. tool_error: tool_result with is_error=true, non-zero exit, timeout, or
         permission denial.
      2. raw_tool_markup: raw <tool_call markup in the last assistant message
         while tools are declared.
      3. tool_loop: glm_loop_breaker.detect_cycle identifies a period 1-3
         tool-call cycle repeated at least 3 times.
    """
    signals = []
    messages = data.get("messages") or data.get("input") or []
    if not isinstance(messages, list):
        return signals

    # Signal 1: tool_result failures.
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            if _is_tool_failure(block):
                signals.append({
                    "kind": "tool_error",
                    "tool_use_id": block.get("tool_use_id", ""),
                    "content": _tool_result_text(block),
                })

    # Signal 2: raw tool markup in last assistant message while tools declared.
    has_tools = isinstance(data.get("tools"), list) and len(data["tools"]) > 0
    if has_tools:
        for msg in reversed(messages):
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            text = _assistant_text(msg)
            if text and _RAW_TOOL_MARKUP_RE.search(text):
                signals.append({
                    "kind": "raw_tool_markup",
                    "text_prefix": text[:256],
                })
            break  # only the last assistant message

    # Signal 3: tool-call loop (period 1-3, >= 3 repetitions).
    loop_signal = _detect_loop_signal(messages)
    if loop_signal:
        signals.append(loop_signal)

    return signals


def _is_tool_failure(block: dict) -> bool:
    """Check if a tool_result block reports failure (PRD §10.1 signal 1)."""
    if block.get("is_error") is True:
        return True
    text = _tool_result_text(block).lower()
    # Non-zero exit code, timeout, or permission denial indicators.
    failure_markers = (
        "exit code: ", "command not found", "permission denied",
        "timed out", "timeout", "killed", "segfault",
        "traceback", "error:", "failed", "is_error",
    )
    # Check for non-zero exit code specifically.
    if "exit code:" in text:
        import re as _re
        m = _re.search(r"exit code:\s*(\d+)", text)
        if m and m.group(1) != "0":
            return True
    return any(marker in text for marker in failure_markers)


def _tool_result_text(block: dict) -> str:
    """Extract text from a tool_result block."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""


def _assistant_text(msg: dict) -> str:
    """Extract text from an assistant message."""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _detect_loop_signal(messages: list) -> Optional[dict]:
    """Detect a tool-call loop using glm_loop_breaker's logic (PRD §10.1 signal 3).

    Imports glm_loop_breaker lazily to avoid a circular import at module load.
    """
    try:
        import glm_loop_breaker  # type: ignore
    except ImportError:
        return None
    try:
        seq = glm_loop_breaker._tool_call_sequence(messages)
        period, reps = glm_loop_breaker.detect_cycle(seq)
        if period and reps >= 3:
            return {
                "kind": "tool_loop",
                "period": period,
                "repetitions": reps,
            }
    except Exception:
        pass
    return None


def fingerprint_signal(signal: dict, session_anchor: str) -> str:
    """Compute a stable failure fingerprint (PRD §10.2).

    Excludes volatile tool-call IDs (they are freshly generated every turn, so
    including them would make every recurrence look like a new fingerprint).
    Includes the failure kind, the error content / markup / cycle signature,
    and the session anchor.
    """
    parts = [signal.get("kind", ""), session_anchor]
    if signal.get("kind") == "tool_error":
        # tool_use_id is intentionally excluded — it changes every turn.
        parts.append(signal.get("content", "")[:256])
    elif signal.get("kind") == "raw_tool_markup":
        parts.append(signal.get("text_prefix", ""))
    elif signal.get("kind") == "tool_loop":
        parts.append(str(signal.get("period", 0)))
        parts.append(str(signal.get("repetitions", 0)))
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ── Intervention ledger (PRD §10.3) ─────────────────────────────────────────

class InterventionLedger:
    """Node-local persistent ledger for premium interventions.

    Storage: <root>/premium-ledger/v1/<sha256>.json
    15 min retention (PRD-remove-tool-disabling §5.2), atomic write, mode 0600.
    Max 3 distinct interventions per session (cost protection — stops calling
    Premium, does NOT remove tools); same fingerprint never sent to Premium twice.
    """

    def __init__(
        self,
        root: str,
        ttl_seconds: int = PREMIUM_LEDGER_TTL_SECONDS,
        max_per_session: int = PREMIUM_MAX_DISTINCT_INTERVENTIONS,
    ):
        self.root = Path(root) / "premium-ledger" / "v1"
        self.ttl_seconds = ttl_seconds
        self.max_per_session = max_per_session
        self._ensure_root()

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            pass

    def _session_dir(self, session_anchor: str) -> Path:
        sid = hashlib.sha256(session_anchor.encode("utf-8")).hexdigest()[:16]
        d = self.root / sid
        try:
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            pass
        return d

    def is_repeat(self, fp: str, session_anchor: str) -> bool:
        """True if this fingerprint has already been intervened on."""
        path = self._session_dir(session_anchor) / ("%s.json" % fp)
        if not path.exists():
            return False
        try:
            with path.open("r", encoding="utf-8") as f:
                entry = json.load(f)
            if time.time() - entry.get("time", 0) > self.ttl_seconds:
                return False  # expired
            return True
        except (OSError, ValueError):
            return False

    def count_session(self, session_anchor: str) -> int:
        """Count distinct interventions for this session (non-expired)."""
        d = self._session_dir(session_anchor)
        count = 0
        try:
            for p in d.glob("*.json"):
                try:
                    with p.open("r", encoding="utf-8") as f:
                        entry = json.load(f)
                    if time.time() - entry.get("time", 0) <= self.ttl_seconds:
                        count += 1
                except (OSError, ValueError):
                    continue
        except OSError:
            pass
        return count

    def should_intervene(self, fp: str, session_anchor: str) -> bool:
        """True if Premium should be called (first occurrence, under session cap).

        NOTE: this is a non-atomic read-check. For cross-worker safety use
        claim() which holds a flock around the check+record sequence.
        """
        if self.is_repeat(fp, session_anchor):
            return False
        if self.count_session(session_anchor) >= self.max_per_session:
            return False
        return True

    def _ledger_lock(self, fp: str, session_anchor: str):
        """Cross-process flock around the per-fingerprint claim (PRD §7.7)."""
        import contextlib

        @contextlib.contextmanager
        def _cm():
            d = self._session_dir(session_anchor)
            lockfile = d / ("%s.lock" % fp)
            fh = None
            try:
                fh = open(lockfile, "w")
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                yield
            except OSError:
                yield  # fail-open
            finally:
                if fh is not None:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                    fh.close()

        return _cm()

    def _session_lock(self, session_anchor: str):
        """Cross-process flock at the SESSION level (PRD v2 §7.8 R8).

        Protects the per-session maximum across different fingerprints with a
        session-level atomic operation. Without this, concurrent claims on
        DIFFERENT fingerprints would each acquire their own per-fingerprint lock
        and all see count_session < max simultaneously.
        """
        import contextlib

        @contextlib.contextmanager
        def _cm():
            d = self._session_dir(session_anchor)
            d.mkdir(parents=True, exist_ok=True)
            lockfile = d / "_session.lock"
            fh = None
            try:
                fh = open(lockfile, "w")
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                yield
            except OSError:
                yield  # fail-open
            finally:
                if fh is not None:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                    fh.close()

        return _cm()

    def claim(self, fp: str, session_anchor: str) -> bool:
        """Atomically claim a fingerprint for intervention (PRD §7.7, C7).

        Holds a cross-process flock around the read-check-write so concurrent
        workers racing on the same fingerprint produce exactly one claimant.
        Returns True if this caller is the first claimant (may call Premium).
        Returns False if the fingerprint is already claimed/expired or the
        session cap is reached.

        The claim is recorded immediately as a pending entry. The caller MUST
        call record_outcome() to finalize it (success or failure). A pending
        entry counts as "already intervened" so a crashed claim doesn't reopen
        the one-shot budget.

        R8: the session cap check is protected by a session-level lock so
        concurrent claims on different fingerprints cannot all exceed the cap.
        """
        with self._ledger_lock(fp, session_anchor):
            if self.is_repeat(fp, session_anchor):
                return False
            # R8: session-level lock around the cap check + write so concurrent
            # claims on different fingerprints serialize at the session level.
            # The write MUST happen inside the session lock so the next claimant
            # sees the updated count.
            with self._session_lock(session_anchor):
                if self.count_session(session_anchor) >= self.max_per_session:
                    return False
                # Record a pending claim immediately so concurrent/repeat callers
                # see it as already-intervened (PRD §7.7: a failed attempt must not
                # become eligible again on the next turn).
                self._write_entry(fp, session_anchor, {"status": "pending"})
            return True

    def record_outcome(self, fp: str, session_anchor: str, advice: dict, success: bool) -> None:
        """Finalize a claim with the outcome (PRD §7.7).

        Both success and failure finalize the claim — a failed Premium attempt
        consumes the fingerprint and cannot re-claim next turn.
        """
        with self._ledger_lock(fp, session_anchor):
            self._write_entry(fp, session_anchor, {
                "status": "success" if success else "failed",
                "advice": advice,
            })

    def _write_entry(self, fp: str, session_anchor: str, extra: dict) -> None:
        """Write a ledger entry atomically (unique temp, mode 0600)."""
        path = self._session_dir(session_anchor) / ("%s.json" % fp)
        entry = {
            "fingerprint": fp,
            "time": time.time(),
        }
        entry.update(extra)
        try:
            tmp = path.with_suffix(".tmp.%d.%s" % (os.getpid(), os.urandom(8).hex()))
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            tmp.chmod(0o600)
            os.replace(tmp, path)
        except OSError:
            pass

    def record(self, fp: str, session_anchor: str, advice: dict) -> None:
        """Record a successful intervention atomically (legacy API).

        Prefer claim() + record_outcome() for cross-worker safety.
        """
        self._write_entry(fp, session_anchor, {"status": "success", "advice": advice})


_ledger: Optional[InterventionLedger] = None


def get_ledger() -> InterventionLedger:
    global _ledger
    if _ledger is None:
        _ledger = InterventionLedger(SIDECAR_CACHE_DIR)
    return _ledger


# ── Premium payload + hard-stop (PRD §10.4, §10.5) ──────────────────────────

PREMIUM_INSTRUCTION = (
    "You are a recovery advisor for a coding agent that has hit a tool failure "
    "or loop. Analyze the failure and provide ONE materially different next "
    "step. Respond in structured JSON with these exact fields:\n"
    '  "diagnosis": why the current strategy failed,\n'
    '  "next_action": one materially different next step,\n'
    '  "stop_conditions": array of conditions under which tools must not be retried,\n'
    '  "prohibited_retries": array of failed calls or strategies not to repeat,\n'
    '  "user_visible_blocker": what to report if recovery fails.\n'
    "Respond with ONLY the JSON object, no markdown fences, no prose."
)


def _build_premium_payload(data: dict, signal: dict) -> list:
    """Build the bounded premium payload (PRD §10.4).

    Capped at PREMIUM_MAX_PAYLOAD_TOKENS. Contains only: task summary, failure
    signature, last relevant tool calls + verbatim error results, strategies
    attempted, tools still available. Excludes full conversation, image bytes,
    and GLM sampling parameters.
    """
    messages = data.get("messages") or []
    # Task summary: first user message (truncated).
    task_summary = _session_anchor(data)[:1000]
    # Last few tool calls and results (truncated).
    recent = _recent_tool_history(messages, max_items=6)
    # Available tools (names only, no schemas — bounded).
    tool_names = [
        t.get("name", "") for t in (data.get("tools") or [])
        if isinstance(t, dict) and t.get("name")
    ][:20]
    payload_text = (
        "Task summary: %s\n\n"
        "Failure signal: %s\n\n"
        "Recent tool history:\n%s\n\n"
        "Available tools: %s\n\n"
        "Strategies already attempted: (see recent tool history above)"
    ) % (
        task_summary,
        json.dumps(signal, ensure_ascii=False)[:2000],
        recent,
        ", ".join(tool_names),
    )
    # Truncate to the token cap (~4 bytes/token).
    max_chars = PREMIUM_MAX_PAYLOAD_TOKENS * 4
    if len(payload_text) > max_chars:
        payload_text = payload_text[:max_chars]
    return [
        {"role": "user", "content": PREMIUM_INSTRUCTION + "\n\n" + payload_text},
    ]


def _recent_tool_history(messages: list, max_items: int = 6) -> str:
    """Extract the last few tool calls and results (bounded, redacted)."""
    items = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    items.append(
                        "tool_use: %s args=%s"
                        % (block.get("name", ""), _canonicalize_args(block.get("input", ""))[:200])
                    )
        if role == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    items.append(
                        "tool_result: %s"
                        % _tool_result_text(block)[:200]
                    )
    return "\n".join(items[-max_items:])


def _inject_premium_advice(data: dict, advice: dict) -> None:
    """Inject validated premium advice as a [premium-recovery] text block."""
    block_text = (
        "[premium-recovery]\n"
        "Diagnosis: %s\n"
        "Next action: %s\n"
        "Stop conditions: %s\n"
        "Prohibited retries: %s\n"
        "[/premium-recovery]"
    ) % (
        advice.get("diagnosis", ""),
        advice.get("next_action", ""),
        ", ".join(advice.get("stop_conditions", [])),
        ", ".join(advice.get("prohibited_retries", [])),
    )
    _inject_system_text(data, block_text)


def _inject_system_text(data: dict, text: str) -> None:
    """Inject text into the latest user message (or append a new one)."""
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return
    last = messages[-1]
    if isinstance(last, dict) and last.get("role") == "user":
        content = last.get("content")
        if isinstance(content, str):
            last["content"] = content + "\n\n" + text
        elif isinstance(content, list):
            content.append({"type": "text", "text": text})
        else:
            last["content"] = [{"type": "text", "text": text}]
    else:
        messages.append({"role": "user", "content": [{"type": "text", "text": text}]})


def _hard_stop(data: dict, signal: dict, reason: str) -> int:
    """Record a repeat failure. Does NOT modify the request (PRD-remove-tool-disabling §5.1).

    Previously this removed tools and tool_choice, which turned a recoverable
    tool error into whole-session capability loss for the ledger TTL. The
    model was expected to honor a text instruction instead; it did not — it
    emitted raw tool-call markup as prose, producing fabricated success.

    Now this only increments the hard-stop counter and logs. The request
    object (tools, tool_choice, messages) is left untouched. Repeat-failure
    semantics: "do not give the same advice again", not "disable tools".
    """
    PREMIUM_HARD_STOPS.labels(reason=reason).inc()
    log.warning(
        "[sidecar] repeat failure fingerprint=%s reason=%s — advice already "
        "given, not intervening again (tools left intact)",
        signal.get("kind", "unknown"), reason,
    )
    return 1


async def process_premium(data: dict, *, call_model=None) -> dict:
    """Process premium recovery signals (PRD §10).

    Returns a dict with premium stats. On first occurrence of a failure
    fingerprint: call Premium once, inject advice. On repeat: increment the
    hard-stop counter and log — the request is NOT modified (tools stay
    intact). Premium unavailable → same count-only path.
    """
    if call_model is None:
        call_model = _default_call_model_for_premium
    signals = detect_triggers(data)
    if not signals:
        return {"triggers": 0, "interventions": 0, "hard_stops": 0}

    session_anchor = _session_anchor(data)
    ledger = get_ledger()
    interventions = 0
    hard_stops = 0

    for signal in signals:
        PREMIUM_TRIGGERS.labels(signal=signal["kind"]).inc()
        fp = fingerprint_signal(signal, session_anchor)

        # PRD §7.1 (C2): china-only key → hard-stop without contacting Premium.
        if not _current_residency().allows_egress:
            SIDECAR_POLICY_DENIALS.labels(kind="premium").inc()
            hard_stops += _hard_stop(data, signal, "policy_denied")
            continue

        # PRD §7.7 (C7): atomically claim the fingerprint across workers.
        if ledger.claim(fp, session_anchor):
            payload = _build_premium_payload(data, signal)
            try:
                response = await call_model(
                    PREMIUM_SIDECAR_MODEL, payload,
                    max_tokens=VISION_CAPTION_MAX_TOKENS,
                    timeout=PREMIUM_TIMEOUT_SECONDS,
                )
                text = _extract_response_text(response)
                obj = json.loads(text)
                validate_premium(obj)
                _inject_premium_advice(data, obj)
                ledger.record_outcome(fp, session_anchor, obj, success=True)
                interventions += 1
                PREMIUM_INTERVENTIONS.labels(outcome="success").inc()
                SIDECAR_REQUESTS.labels(kind="premium", model=PREMIUM_SIDECAR_MODEL, outcome="success").inc()
            except (SidecarCallError, ValueError, json.JSONDecodeError) as exc:
                ledger.record_outcome(fp, session_anchor, {}, success=False)
                PREMIUM_INTERVENTIONS.labels(outcome="error").inc()
                SIDECAR_REQUESTS.labels(kind="premium", model=PREMIUM_SIDECAR_MODEL, outcome="error").inc()
                log.warning("premium call failed: %s: %s", type(exc).__name__, exc)
                hard_stops += _hard_stop(data, signal, "premium_unavailable")
            except Exception as exc:
                ledger.record_outcome(fp, session_anchor, {}, success=False)
                PREMIUM_INTERVENTIONS.labels(outcome="error").inc()
                log.warning("premium unexpected error: %s: %s", type(exc).__name__, exc)
                hard_stops += _hard_stop(data, signal, "premium_error")
        else:
            # Repeat fingerprint or session cap → hard-stop, no Premium call.
            hard_stops += _hard_stop(data, signal, "repeat_fingerprint")

    return {"triggers": len(signals), "interventions": interventions, "hard_stops": hard_stops}


async def _default_call_model_for_premium(model, messages, *, max_tokens, timeout, temperature=None):
    """Default call_model binding for premium."""
    return await call_model(model, messages, max_tokens=max_tokens, timeout=timeout, temperature=temperature)


# ── Tool-argument repair (PRD-tool-argument-guard §10, §13.2) ───────────────
#
# A bounded Premium call that repairs invalid tool arguments. Called by the
# tool_argument_guard when deterministic normalization fails. Premium returns
# {"arguments": {...}} which is validated against the original request schema
# by the caller. One call per fingerprint per session (ledger-enforced).

TOOL_REPAIR_INSTRUCTION = (
    "You are a tool-argument repair assistant. The model generated tool "
    "arguments that do not match the tool's JSON Schema. Fix the arguments so "
    "they validate against the schema. Do NOT change the tool name, introduce "
    "another tool call, or add prose. Respond in structured JSON with this "
    "exact field:\n"
    '  "arguments": the corrected arguments object.\n'
    "Respond with ONLY the JSON object, no markdown fences, no prose."
)

TOOL_REPAIR_MAX_OUTPUT_TOKENS = int(os.getenv("TOOL_ARG_PREMIUM_MAX_OUTPUT_TOKENS", "2048"))
TOOL_REPAIR_TIMEOUT = float(os.getenv("TOOL_ARG_PREMIUM_TIMEOUT_SECONDS", "30"))
PREMIUM_REPAIR_ENABLED = os.getenv("TOOL_ARG_PREMIUM_REPAIR", "true").lower() in (
    "1", "true", "yes", "on",
)


def _has_secret_field(args: Any) -> bool:
    """Recursively detect secret-bearing fields (PRD §10.1).

    If present, external repair is disabled (the payload would need to
    disclose secrets to Premium).
    """
    if isinstance(args, dict):
        for k, v in args.items():
            if k.lower() in _SECRET_FIELD_NAMES:
                return True
            if _has_secret_field(v):
                return True
    elif isinstance(args, list):
        for item in args:
            if _has_secret_field(item):
                return True
    return False


def _tool_repair_fingerprint(
    tool_name: str, schema_hash: str, invalid_args: Any, errors: list, session_anchor: str,
) -> str:
    """Fingerprint for tool-argument repair (PRD §10.4 ledger integration).

    Contains: session anchor, tool name, schema hash, canonical invalid-input
    shape/value hash after secret detection, validator keyword/path set.
    Excludes volatile call IDs.
    """
    canonical = _canonicalize_args(invalid_args)
    keyword_paths = "|".join(
        "%s@%s" % (e.get("keyword", ""), e.get("path", ""))
        for e in errors[:10]
    )
    raw = "|".join([
        "invalid_tool_parameters",
        session_anchor,
        tool_name,
        schema_hash,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        keyword_paths,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _build_tool_repair_payload(
    tool_name: str, input_schema: dict, invalid_input: Any, validation_errors: list,
) -> list:
    """Build the bounded repair payload (PRD §10.2).

    Contains ONLY: tool_name, input_schema, invalid_input, validation_errors.
    Excludes the full conversation, system prompt, unrelated tools, image
    bytes, tool results, and model sampling parameters.
    """
    payload = {
        "tool_name": tool_name,
        "input_schema": input_schema,
        "invalid_input": _redact_args(invalid_input),
        "validation_errors": validation_errors[:20],
    }
    payload_text = TOOL_REPAIR_INSTRUCTION + "\n\n" + json.dumps(payload, ensure_ascii=False)
    # Bound the payload (~4 bytes/token, capped at PREMIUM_MAX_PAYLOAD_TOKENS).
    max_chars = PREMIUM_MAX_PAYLOAD_TOKENS * 4
    if len(payload_text) > max_chars:
        payload_text = payload_text[:max_chars]
    return [{"role": "user", "content": payload_text}]


def validate_tool_repair(obj: Any) -> dict:
    """Validate a tool-repair response (PRD §10.3).

    Premium must return exactly {"arguments": {...}}. Raises ValueError on
    missing fields, wrong types, or extra fields.
    """
    if not isinstance(obj, dict):
        raise ValueError("repair response is not a JSON object")
    if "arguments" not in obj:
        raise ValueError("repair missing field: arguments")
    if not isinstance(obj["arguments"], dict):
        raise ValueError("repair.arguments must be a JSON object")
    # Reject extra fields — Premium cannot change the tool name or add prose.
    extra = set(obj) - {"arguments"}
    if extra:
        raise ValueError("repair has unexpected fields: %s" % sorted(extra))
    return obj


async def repair_tool_arguments(
    tool_name: str,
    input_schema: dict,
    invalid_input: Any,
    validation_errors: list,
    session_anchor: str,
    *,
    call_model=None,
) -> Optional[dict]:
    """Call Premium once to repair invalid tool arguments (PRD §10).

    Returns the repaired arguments dict, or None if repair is unavailable,
    the fingerprint is a repeat, or the arguments contain secret-bearing
    fields. The caller (tool_argument_guard) validates the returned args
    against the original schema before using them.

    One call per fingerprint per session (ledger-enforced, I7).
    """
    if not PREMIUM_REPAIR_ENABLED:
        return None
    # Secret-bearing inputs skip Premium (PRD §10.1).
    if _has_secret_field(invalid_input):
        return None
    # PRD §7.1 (C2): a china-only key must not contact Premium for tool repair.
    # Return None so the caller falls through to safe rejection (no egress).
    if not _current_residency().allows_egress:
        SIDECAR_POLICY_DENIALS.labels(kind="tool_repair").inc()
        return None
    if call_model is None:
        call_model = _default_call_model_for_premium

    schema_hash = hashlib.sha256(
        json.dumps(input_schema, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    fp = _tool_repair_fingerprint(tool_name, schema_hash, invalid_input, validation_errors, session_anchor)

    ledger = get_ledger()
    # PRD §7.7 (C7): atomically claim the fingerprint across workers.
    if not ledger.claim(fp, session_anchor):
        # Repeat fingerprint or session cap — no Premium call (I7).
        return None

    payload = _build_tool_repair_payload(tool_name, input_schema, invalid_input, validation_errors)
    try:
        response = await call_model(
            PREMIUM_SIDECAR_MODEL, payload,
            max_tokens=TOOL_REPAIR_MAX_OUTPUT_TOKENS,
            timeout=TOOL_REPAIR_TIMEOUT,
        )
        text = _extract_response_text(response)
        obj = json.loads(text)
        validate_tool_repair(obj)
        ledger.record_outcome(fp, session_anchor, {"tool": tool_name, "kind": "invalid_tool_parameters"}, success=True)
        PREMIUM_INTERVENTIONS.labels(outcome="success").inc()
        SIDECAR_REQUESTS.labels(
            kind="tool_repair", model=PREMIUM_SIDECAR_MODEL, outcome="success",
        ).inc()
        return obj["arguments"]
    except (SidecarCallError, ValueError, json.JSONDecodeError) as exc:
        # Finalize the claim as failed so a retry doesn't re-call Premium (PRD §7.7).
        ledger.record_outcome(fp, session_anchor, {}, success=False)
        PREMIUM_INTERVENTIONS.labels(outcome="error").inc()
        SIDECAR_REQUESTS.labels(
            kind="tool_repair", model=PREMIUM_SIDECAR_MODEL, outcome="error",
        ).inc()
        log.warning("tool repair failed: %s: %s", type(exc).__name__, exc)
        return None
    except Exception as exc:
        ledger.record_outcome(fp, session_anchor, {}, success=False)
        log.warning("tool repair unexpected error: %s: %s", type(exc).__name__, exc)
        return None


# ── Orchestration (PRD §6) ──────────────────────────────────────────────────


def _sidecar_key_hash() -> str:
    """SHA-256 of the configured SIDECAR_API_KEY (LiteLLM stores keys hashed)."""
    return hashlib.sha256(SIDECAR_API_KEY.encode("utf-8")).hexdigest()


def is_internal_key(user_api_key_dict) -> bool:
    """True when the authenticated key is the configured internal sidecar key.

    This is the recursion bypass (I5/I10): a request carrying sidecar metadata
    but NOT the trusted key is blocked. The check is on key IDENTITY, not
    client-controlled metadata.

    LiteLLM's UserAPIKeyAuth stores the key as a SHA-256 hash in the ``token``
    field (and exposes it via ``.api_key``). So we compare the hash of the
    configured SIDECAR_API_KEY against the authenticated key's token. We also
    accept a raw-key match (for tests that pass the raw key directly in a
    plain dict).

    ``user_api_key_dict`` is a Pydantic UserAPIKeyAuth model in production (NOT
    a plain dict), so we use getattr — which works for both Pydantic models and
    plain dicts (tests).
    """
    if not SIDECAR_API_KEY or user_api_key_dict is None:
        return False
    # The authenticated key identity: LiteLLM uses 'token' / 'api_key' (hashed),
    # or tests may pass 'key' (raw). getattr works for both Pydantic models and dicts.
    authed = (
        getattr(user_api_key_dict, "token", None)
        or getattr(user_api_key_dict, "api_key", None)
        or (user_api_key_dict.get("key") if isinstance(user_api_key_dict, dict) else None)
        or ""
    )
    if not authed:
        return False
    # Raw-key match (tests) or hashed-key match (LiteLLM production).
    return authed == SIDECAR_API_KEY or authed == _sidecar_key_hash()


# ── Data residency policy (PRD §7.1, C2) ────────────────────────────────────

# The residency decision is carried via a contextvar so call_model (the network
# boundary) can check it without threading an explicit param through every
# caption/repair function. Set by orchestrate_sidecars / process_request from
# the authenticated user_api_key_dict — never from client request metadata.
_residency_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "sidecar_residency", default=None
)


class ResidencyPolicy(_request_context.ResidencyPolicy):
    """Authenticated data-residency policy for sidecar egress (PRD §7.1).

    Inherits from _request_context.ResidencyPolicy (the canonical, shared
    implementation) and overrides check_egress to use this module's
    SidecarPolicyDenied and SIDECAR_POLICY_DENIALS counter.

    Derived ONLY from the authenticated key's server-controlled tags/metadata,
    never from client request metadata. A router ordering mistake must not
    bypass it — the check is at the call_model network boundary (defense in depth).

    Modes:
      "allow"     — default; sidecar calls permitted.
      "china-only" — local parsing/hashing/cache-lookup permitted; cache miss or
                     Premium/repair trigger → SIDECAR_POLICY_DENIED (403) before
                     any external call. No OpenRouter spend.
    """

    def check_egress(self, kind: str) -> None:
        """Raise SIDECAR_POLICY_DENIED if this policy blocks external egress.

        ``kind`` is the sidecar kind label for metrics: "vision" or "premium".
        Called at the network boundary (call_model) and at the cache-miss /
        trigger decision point.
        """
        if not self.allows_egress:
            SIDECAR_POLICY_DENIALS.labels(kind=kind).inc()
            raise SidecarPolicyDenied(
                "sidecar egress denied by residency policy (%s) for kind=%s"
                % (self.mode, kind)
            )


# ── Request-scoped residency store (PRD v2 §7.1 R1) ──────────────────────────
# The contextvar resets in process_request's finally before the streaming
# iterator runs. This store survives so response-time tool-argument repair
# can enforce china-only egress. Per-process (single-host deployment).
_residency_store: Dict[str, "ResidencyPolicy"] = {}


def set_residency_for_request(request_id: str, policy: "ResidencyPolicy") -> None:
    _residency_store[request_id] = policy


def get_residency_for_request(request_id: str):
    return _residency_store.get(request_id)


def clear_residency_for_request(request_id: str) -> None:
    _residency_store.pop(request_id, None)


def _current_residency() -> ResidencyPolicy:
    """Return the residency policy from the contextvar, or a default allow."""
    policy = _residency_ctx.get()
    if policy is None:
        return ResidencyPolicy()
    return policy


async def process_request(
    data: dict,
    user_api_key_dict=None,
    *,
    call_model=None,
    cache=None,
) -> dict:
    """Orchestrate vision + premium sidecars for a request.

    Called by smart_router in async_pre_call_hook. Mutates data in place:
    - Images are extracted, captioned, and replaced with text (vision sidecar).
    - Failure signals trigger premium recovery or hard-stop (premium sidecar).
    - After processing, the model is NOT forced here — smart_router forces
      claude-glm-5.2 after this returns (I1).

    Raises InvalidImageInput, ImageLimitExceeded, VisionSidecarUnavailable,
    SidecarPolicyDenied (which smart_router re-raises to the client). Other
    errors are swallowed by smart_router's fail-open wrapper.

    ``call_model`` and ``cache`` are injectable for testing (mock transport /
    isolated cache).

    PRD §7.1 (C2): the authenticated residency policy is set in a contextvar
    so call_model (the network boundary) can check it. china-only keys get
    local parsing/hashing/cache-lookup but no external egress.
    """
    if not isinstance(data, dict):
        return data

    # Set the residency policy from the authenticated key (PRD §7.1).
    # This contextvar is read by call_model at the network boundary.
    policy = ResidencyPolicy.from_key(user_api_key_dict)
    token = _residency_ctx.set(policy)
    try:
        return await _process_request_inner(data, call_model=call_model, cache=cache)
    finally:
        _residency_ctx.reset(token)


async def _process_request_inner(
    data: dict,
    *,
    call_model=None,
    cache=None,
) -> dict:
    """Inner orchestration — runs with the residency contextvar already set."""
    result = {"vision": None, "premium": None}

    # Vision sidecar: extract + caption + inject.
    try:
        result["vision"] = await process_vision(data, call_model=call_model, cache=cache)
    except (InvalidImageInput, ImageLimitExceeded, VisionSidecarUnavailable, SidecarPolicyDenied):
        raise  # typed errors propagate
    except Exception as exc:
        # Fail-open: log and continue without vision enrichment.
        log.warning("vision sidecar fail-open: %s: %s", type(exc).__name__, exc)
        result["vision"] = {"error": type(exc).__name__}

    # Premium sidecar: detect failures + recover/hard-stop.
    try:
        result["premium"] = await process_premium(data, call_model=call_model)
    except SidecarPolicyDenied:
        raise  # typed policy error propagates
    except Exception as exc:
        log.warning("premium sidecar fail-open: %s: %s", type(exc).__name__, exc)
        result["premium"] = {"error": type(exc).__name__}

    return result